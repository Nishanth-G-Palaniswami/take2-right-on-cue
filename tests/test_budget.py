"""Budget guard for `score`, and pins that keep unbudgeted scoring unchanged.

Fully offline: fake judges and synthetic runs only. All replies and usage below
are SYNTHETIC TEST DATA.
"""

from __future__ import annotations

import hashlib
import json
import re
from decimal import Decimal
from pathlib import Path
from typing import Any

import httpx2
import openai
import pytest
from test_scoring import (  # noqa: F401  (offline is an autouse fixture)
    REPLY,
    FakeJudge,
    FakeJudgeResponse,
    Scorer,
    judge,
    make_run,
    offline,
    setup,
    slot,
    write_notes,
)

from rightoncue import budget, cli, gemini, holdout, scoring
from rightoncue.runs import InputFile, ModelSpec, create_run

REPO = Path(__file__).resolve().parents[1]


# ------------------------------------------------------------------ pins


def _masked(text: str, tmp_path: Path) -> str:
    text = text.replace(tmp_path.as_posix(), "<TMP>").replace(str(tmp_path), "<TMP>")
    text = text.replace(REPO.as_posix(), "<REPO>").replace(str(REPO), "<REPO>")
    return re.sub(r'"(started_at|finished_at)": "[^"]*"', r'"\1": "<T>"', text)


def unbudgeted_fingerprint(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> str:
    """Requests, records (key order included), stdout, stderr and file bytes of a
    no-budget `score` over a mixed run, with timestamps and paths masked."""
    score = setup(
        tmp_path,
        [
            slot("RID", "C1", 1, REPLY),
            slot("RID", "C1", 2, "   "),
            slot("RID", "C1", 3, f"Got it. {REPLY}"),
            slot("RID", "C1", 4, "cut", status="incomplete"),
        ],
        samples=4,
    )
    fake = FakeJudge([judge(next_action=1), "not json"])
    first = score(fake)
    cap1 = capsys.readouterr()
    fake2 = FakeJudge([judge()])
    second = score(fake2)
    cap2 = capsys.readouterr()
    def m(text: str) -> str:
        return _masked(text, tmp_path)

    blob = json.dumps(
        {
            "exit": [first, second],
            "requests": m(json.dumps(fake.calls + fake2.calls, sort_keys=True, ensure_ascii=False)),
            "out": [m(cap1.out), m(cap2.out)],
            "err": [m(cap1.err), m(cap2.err)],
            "file": m((score.scores_dir / "RID.jsonl").read_text(encoding="utf-8")),
        },
        sort_keys=True,
        ensure_ascii=False,
    )
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()



UNBUDGETED_PIN = "7c7d2d84f2d8051d34d9b55492d0043bd5d558fa89c3778db846b9460408d819"


def test_unbudgeted_score_is_byte_for_byte_unchanged(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert unbudgeted_fingerprint(tmp_path, capsys) == UNBUDGETED_PIN


def test_frozen_pair_plan_constants() -> None:
    """The committed holdout/pair_plan_commitment.json depends on these exact texts."""
    pinned = {
        name: hashlib.sha256(getattr(holdout, name).encode("utf-8")).hexdigest()
        for name in ("PAIR_ALGORITHM", "PAIR_RULE", "PAIR_PLAN_SCHEMA", "PAIR_COMMITMENT_SCHEMA")
    }
    assert pinned == PAIR_CONSTANT_PINS


PAIR_CONSTANT_PINS: dict[str, str] = {
    "PAIR_ALGORITHM": "3eb2c507aa4a93927bfbb157dd4408b61441a6c1b21b566c5b0de32f8abcf0b2",
    "PAIR_RULE": "67daf3c5a96bf0696996e32b1fa86e81b27e0ceb836667ff0e3dec1ef573e3fe",
    "PAIR_PLAN_SCHEMA": "d0c54f8a5aaf12aed4450df49499e586f466136166a58172ab751ae1387c5a11",
    "PAIR_COMMITMENT_SCHEMA": "37823ee3f6485a7ea15ef11dffb6f9370f03ed9c41e84d9881047d0fcf92e365",
}


# ------------------------------------------------------------ budget guard

MINI = "gpt-5.4-mini"
JUDGE_CALL = 100 * 750 + 20 * 4_500  # FakeJudgeResponse usage at Mini rates, nano-USD
SIMPLE_CASE = b'{"role":"agent","utterance":"Hi"}\n{"role":"user","utterance":"Hello"}\n'


def gslot(run_id: str, idx: int, text: str | None = REPLY, *, model: str = MINI,
          usage: tuple[int, int] | None = (1_000, 50), **kw: Any) -> dict[str, Any]:
    """A generation slot with normalized usage (None: a response without usage)."""
    rec = slot(run_id, "C1", idx, text, model=model, **kw)
    rec["provider"] = "gemini" if model.startswith("gemini-") else "openai"
    rec["usage_normalized"] = (
        None if usage is None
        else {"input_tokens": usage[0], "output_tokens": usage[1], "reasoning_tokens": 7}
    )
    return rec


def gen_cost(n: int, tokens: tuple[int, int] = (1_000, 50), model: str = MINI) -> int:
    price = budget.OPENAI_PRICES[model]
    return n * (tokens[0] * price[0] + tokens[1] * price[1])


def usd(nano: int) -> str:
    return str(Decimal(nano) / budget.NANO_PER_USD)


def max_costs(run_dir: Path, scores_dir: Path, notes: Path) -> list[int]:
    plan = scoring.plan_scoring(run_dir, scores_dir, notes, scoring.load_judge_prompt("judge-v1"))
    return [budget.max_call_cost(sp.request) for sp in plan.slots if sp.action == "judge"]  # type: ignore[arg-type]


FACTORY_KWARGS: list[dict[str, Any]] = []  # how each judge client was built


def run_score(score: Scorer, judge_client: Any, *extra: str) -> int:
    def factory(**kwargs: Any) -> Any:
        FACTORY_KWARGS.append(kwargs)
        if judge_client is None:
            raise AssertionError("no judge client was expected")
        return judge_client

    return cli.main(
        ["score", str(score.run_dir), "--scores-dir", str(score.scores_dir),
         "--notes", str(score.notes), *extra],
        client_factories={"openai": factory},
    )


def budget_args(score: Scorer, nano: int, *runs: Path) -> list[str]:
    out = ["--budget-usd", usd(nano)]
    for r in runs or (score.run_dir,):
        out += ["--budget-run", str(r)]
    return out


def test_stops_before_a_call_that_would_exceed_and_records_the_rest(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    score = setup(tmp_path, [gslot("RID", i) for i in (1, 2, 3)], model=MINI, samples=3)
    m1, m2, m3 = max_costs(score.run_dir, score.scores_dir, score.notes)
    gen = gen_cost(3)
    limit = gen + JUDGE_CALL + m2 - 1  # first call fits; after it, the second doesn't
    assert gen + m1 <= limit
    fake = FakeJudge([judge()])
    assert run_score(score, fake, *budget_args(score, limit)) == 1
    out = capsys.readouterr().out
    assert len(fake.calls) == 1
    recs = score.records
    assert [r["status"] for r in recs] == ["scored", "budget_stopped", "budget_stopped"]
    first_stop, later = recs[1], recs[2]
    assert first_stop["budget"] == {
        "unit": "nano-USD", "spent": gen + JUDGE_CALL, "max_call": m2, "budget": limit,
    }
    assert later["budget"]["max_call"] == m3
    assert "stopped scoring before this call" in first_stop["decision"]["reasons"][0]
    assert "earlier in this command" in later["decision"]["reasons"][0]
    assert first_stop["judge_model"] is None and first_stop["judgment"] is None
    assert (
        f"spend so far {budget.fmt_usd(gen)} (generation {budget.fmt_usd(gen)}, judge $0.000000)"
        in out
    )
    assert budget.GEMINI_NOTE in out
    assert "Decision: BUDGET STOPPED (not judged)" in out
    assert "2 unscored (budget)" in out
    assert f"Budget: {budget.fmt_usd(JUDGE_CALL)} recorded this command" in out
    assert "2 replies unscored (budget)." in out


def test_boundary_equal_is_allowed_one_over_is_not(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    score = setup(tmp_path, [gslot("RID", 1)], model=MINI)
    (m1,) = max_costs(score.run_dir, score.scores_dir, score.notes)
    exact = gen_cost(1) + m1
    no_calls = FakeJudge([])  # a call would fail: none is allowed
    assert run_score(score, no_calls, *budget_args(score, exact - 1)) == 1
    assert no_calls.calls == []
    assert [r["status"] for r in score.records] == ["budget_stopped"]
    fake = FakeJudge([judge()])
    assert run_score(score, fake, *budget_args(score, exact)) == 0
    assert len(fake.calls) == 1
    assert [r["status"] for r in score.records] == ["budget_stopped", "scored"]


def test_retry_is_guarded_and_budget_stopped_is_never_reused(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    score = setup(tmp_path, [gslot("RID", 1)], model=MINI)
    assert run_score(score, FakeJudge(["not json"])) == 1  # needs_review, no budget
    (m1,) = max_costs(score.run_dir, score.scores_dir, score.notes)
    spent = gen_cost(1) + JUDGE_CALL
    no_calls = FakeJudge([])
    assert run_score(score, no_calls, *budget_args(score, spent + m1 - 1)) == 1  # the retry stops
    assert no_calls.calls == []
    assert [r["status"] for r in score.records] == ["needs_review", "budget_stopped"]
    fake = FakeJudge([judge()])
    assert run_score(score, fake) == 0  # without a budget the slot is judged again
    assert len(fake.calls) == 1
    assert [r["status"] for r in score.records] == ["needs_review", "budget_stopped", "scored"]


@pytest.mark.parametrize("failure", ["no usage", "raised"])
def test_a_call_without_usage_is_charged_its_maximum(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], failure: str
) -> None:
    score = setup(tmp_path, [gslot("RID", 1), gslot("RID", 2)], model=MINI, samples=2)
    m1, m2 = max_costs(score.run_dir, score.scores_dir, score.notes)
    # two calls fit only if the first is charged its actual JUDGE_CALL, not m1
    limit = gen_cost(2) + max(m1, JUDGE_CALL + m2)
    assert gen_cost(2) + m1 + m2 > limit
    first: Any
    if failure == "no usage":
        first = FakeJudgeResponse(judge())
        first.usage = None
    else:
        first = openai.APITimeoutError(request=httpx2.Request("POST", "https://x"))
    fake = FakeJudge([first, judge()])
    assert run_score(score, fake, *budget_args(score, limit)) == 1
    assert len(fake.calls) == 1
    assert score.records[-1]["status"] == "budget_stopped"
    assert score.records[-1]["budget"]["spent"] == gen_cost(2) + m1


def test_actual_usage_lets_the_next_call_through(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    score = setup(tmp_path, [gslot("RID", 1), gslot("RID", 2)], model=MINI, samples=2)
    m1, m2 = max_costs(score.run_dir, score.scores_dir, score.notes)
    limit = gen_cost(2) + max(m1, JUDGE_CALL + m2)
    fake = FakeJudge([judge(), judge()])
    assert run_score(score, fake, *budget_args(score, limit)) == 0
    assert len(fake.calls) == 2


def test_spend_counts_recorded_usage_across_two_runs(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    notes = write_notes(tmp_path)
    run_a = make_run(tmp_path, [gslot("RIDA", 1, model="gpt-5.4", usage=(800, 40))],
                     run_id="RIDA", model="gpt-5.4")
    score_a = Scorer(tmp_path, run_a, notes)
    assert run_score(score_a, FakeJudge([judge()])) == 0  # one judge record with usage
    run_b = make_run(tmp_path, [gslot("RIDB", 1), gslot("RIDB", 2, "   ")], run_id="RIDB",
                     model=MINI, samples=2)
    score_b = Scorer(tmp_path, run_b, notes)
    capsys.readouterr()
    fake = FakeJudge([judge()])
    assert run_score(score_b, fake, *budget_args(score_b, 10**9, run_a, run_b)) == 0
    out = capsys.readouterr().out
    gen = gen_cost(1, (800, 40), "gpt-5.4") + gen_cost(2)
    assert gen == 800 * 2_500 + 40 * 15_000 + 2 * (1_000 * 750 + 50 * 4_500)
    assert (
        f"spend so far {budget.fmt_usd(gen + JUDGE_CALL)} (generation {budget.fmt_usd(gen)}, "
        f"judge {budget.fmt_usd(JUDGE_CALL)})"
    ) in out
    assert f"spend now {budget.fmt_usd(gen + 2 * JUDGE_CALL)} of $1.000000" in out
    # the empty reply needed no call and is recorded as before
    recs = scoring.read_score_records(score_b.scores_dir / "RIDB.jsonl")
    assert [r["status"] for r in recs] == ["scored", "scored"]
    assert recs[1]["judge_model"] is None
    # reasoning tokens (7 per slot) are part of output tokens, not added again
    spend = budget.spend_so_far([run_a, run_b], score_b.scores_dir)
    assert (spend.generation, spend.judge) == (gen, 2 * JUDGE_CALL)


def make_gemini_run(root: Path, slots: list[dict[str, Any]]) -> Path:
    run_dir, _ = create_run(
        root / "runs", "RIDG", InputFile("prompts/v1.md", b"call prompt"),
        [InputFile("cases/C1.jsonl", SIMPLE_CASE)],
        [ModelSpec("gemini-3.5-flash", "gemini", {"thinking_level": "MINIMAL"}, gemini.client_settings())],
        1,
    )
    (run_dir / "slots.jsonl").write_text(
        "".join(json.dumps(s) + "\n" for s in slots), encoding="utf-8", newline="\n"
    )
    return run_dir


def test_gemini_generation_is_priced_at_zero(tmp_path: Path) -> None:
    run = make_gemini_run(tmp_path, [gslot("RIDG", 1, model="gemini-3.5-flash", usage=None)])
    spend = budget.spend_so_far([run], tmp_path / "scores")
    assert (spend.generation, spend.judge, spend.gemini_replies) == (0, 0, 1)
    run2 = make_gemini_run(
        tmp_path / "second", [gslot("RIDG", 1, model="gemini-3.5-flash", usage=(10**6, 10**6))]
    )
    assert budget.spend_so_far([run2], tmp_path / "scores").generation == 0


def test_missing_usage_is_refused_with_the_run(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    score = setup(tmp_path, [gslot("RID", 1, usage=None)], model=MINI)
    assert run_score(score, None, *budget_args(score, 10**9)) == 2
    err = capsys.readouterr().err
    assert "run RID: generation record" in err and "no recorded input and output tokens" in err
    assert "No judge call was made." in err
    assert not (score.scores_dir / "RID.jsonl").exists()
    # a judge record with a response but no usage
    score2 = setup(tmp_path / "j", [gslot("RID", 1)], model=MINI)
    response = FakeJudgeResponse(judge())
    response.usage = None
    assert run_score(score2, FakeJudge([response])) == 0
    capsys.readouterr()
    assert run_score(score2, None, *budget_args(score2, 10**9)) == 2
    assert "run RID: judge record" in capsys.readouterr().err


def test_calls_without_a_response_count_at_zero_and_are_reported(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    failed = gslot("RID", 2, None, status="generation_failed", usage=None)
    score = setup(tmp_path, [gslot("RID", 1), failed], model=MINI, samples=2)
    fake = FakeJudge([judge()])
    assert run_score(score, fake, *budget_args(score, 10**9)) == 0
    out = capsys.readouterr().out
    assert f"spend so far {budget.fmt_usd(gen_cost(1))}" in out
    assert "counted at $0 (no usage was recorded): RID 1." in out


@pytest.mark.parametrize(
    ("extra", "message"),
    [
        (["--budget-run", "RUN"], "only applies with --budget-usd"),
        (["--budget-usd", "0.40"], "needs --budget-run"),
        (["--budget-usd", "abc", "--budget-run", "RUN"], "is not a number"),
        (["--budget-usd", "0", "--budget-run", "RUN"], "positive amount"),
        (["--budget-usd", "-1", "--budget-run", "RUN"], "positive amount"),
        (["--budget-usd", "nan", "--budget-run", "RUN"], "positive amount"),
        (["--budget-usd", "0.0000000001", "--budget-run", "RUN"], "precision"),
        (["--budget-usd", "1", "--budget-run", "OTHER"], "must include the run being scored"),
        (["--budget-usd", "1", "--budget-run", "RUN", "--budget-run", "RUN"], "more than once"),
    ],
)
def test_budget_flag_errors(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], extra: list[str], message: str
) -> None:
    score = setup(tmp_path, [gslot("RID", 1)], model=MINI)
    other = make_run(tmp_path / "o", [gslot("RIDO", 1)], run_id="RIDO", model=MINI)
    args = [str(score.run_dir) if a == "RUN" else str(other) if a == "OTHER" else a for a in extra]
    assert run_score(score, None, *args) == 2
    assert message in capsys.readouterr().err
    assert not (score.scores_dir / "RID.jsonl").exists()


def test_unpriced_model_is_refused(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    score = setup(tmp_path, [gslot("RID", 1, model="gpt-x")])
    assert run_score(score, None, *budget_args(score, 10**9)) == 2
    assert "no price is fixed for model 'gpt-x'" in capsys.readouterr().err


def test_max_call_cost_bound_and_parse() -> None:
    request = {"model": MINI, "instructions": "é", "max_output_tokens": 1500}
    canonical = json.dumps(request, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    assert budget.max_call_cost(request) == len(canonical.encode("utf-8")) * 750 + 1500 * 4_500
    with pytest.raises(budget.BudgetInputError, match="max_output_tokens"):
        budget.max_call_cost({"model": MINI})
    assert budget.parse_usd("0.40") == 400_000_000
    assert budget.parse_usd("1e-9") == 1



# ------------------------------------------------- B-1: no hidden SDK retries


def test_budgeted_judge_client_has_no_sdk_retries(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    budgeted = setup(tmp_path / "b", [gslot("RID", 1)], model=MINI)
    FACTORY_KWARGS.clear()
    assert run_score(budgeted, FakeJudge([judge()]), *budget_args(budgeted, 10**9)) == 0
    assert FACTORY_KWARGS == [{"max_retries": 0}]
    plain = setup(tmp_path / "p", [gslot("RID", 1)], model=MINI)
    FACTORY_KWARGS.clear()
    assert run_score(plain, FakeJudge([judge()])) == 0  # no budget: built exactly as before
    assert FACTORY_KWARGS == [{}]


def test_real_budgeted_client_is_built_with_max_retries_0(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Without injected factories: OpenAI(max_retries=0) under a budget, OpenAI() without."""
    built: list[dict[str, Any]] = []

    class NoCallClient:
        def __init__(self, **kwargs: Any) -> None:
            built.append(kwargs)
            self.max_retries = kwargs.get("max_retries", 2)  # the SDK default is 2
            self.responses = self

        def create(self, **request: Any) -> Any:
            raise AssertionError("no judge call in this test")

    monkeypatch.setenv("OPENAI_API_KEY", "test-not-a-key")
    monkeypatch.setattr(cli, "load_dotenv", lambda **k: None)
    monkeypatch.setattr(openai, "OpenAI", NoCallClient)
    score = setup(tmp_path, [gslot("RID", 1)], model=MINI)
    (m1,) = max_costs(score.run_dir, score.scores_dir, score.notes)
    too_small = gen_cost(1) + m1 - 1  # the guard stops before the only call
    args = ["score", str(score.run_dir), "--scores-dir", str(score.scores_dir), "--notes", str(score.notes)]
    assert cli.main([*args, *budget_args(score, too_small)]) == 1
    assert built == [{"max_retries": 0}]
    built.clear()
    # unbudgeted: OpenAI() exactly as before (the call itself is not reached here)
    with pytest.raises(AssertionError, match="no judge call"):
        cli.main(args)
    assert built == [{}]


def test_a_client_that_would_retry_is_refused_under_a_budget(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    score = setup(tmp_path, [gslot("RID", 1)], model=MINI)
    retrying = FakeJudge([judge()])
    retrying.max_retries = 2  # type: ignore[attr-defined]
    assert run_score(score, retrying, *budget_args(score, 10**9)) == 2
    assert "would retry on its own" in capsys.readouterr().err
    assert retrying.calls == []


def test_charges_are_persisted_and_counted_by_the_next_command(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    score = setup(tmp_path, [gslot("RID", 1), gslot("RID", 2)], model=MINI, samples=2)
    m1, m2 = max_costs(score.run_dir, score.scores_dir, score.notes)
    gen = gen_cost(2)
    raised = openai.APITimeoutError(request=httpx2.Request("POST", "https://x"))
    # command 1: the first call raises (charged m1), the second exactly fits
    assert run_score(score, FakeJudge([raised, judge()]), *budget_args(score, gen + m1 + m2)) == 1
    recs = score.records
    assert [r["status"] for r in recs] == ["judge_failed", "scored"]
    assert recs[0][budget.CHARGE_FIELD] == m1  # no response: its maximum, persisted
    assert recs[1][budget.CHARGE_FIELD] == JUDGE_CALL  # actual usage, persisted
    spend = budget.spend_so_far([score.run_dir], score.scores_dir)
    assert spend.judge == m1 + JUDGE_CALL  # not $0 for the raised call
    # command 2: the retry fits only if the raised call were counted at $0
    limit = gen + JUDGE_CALL + m1 + m1 - 1
    assert gen + JUDGE_CALL + m1 <= limit  # would be allowed at $0
    no_calls = FakeJudge([])
    assert run_score(score, no_calls, *budget_args(score, limit)) == 1
    assert no_calls.calls == []
    last = score.records[-1]
    assert last["status"] == "budget_stopped"
    assert last["budget"]["spent"] == gen + m1 + JUDGE_CALL


def test_budget_stopped_and_unbudgeted_records_carry_no_charge(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    score = setup(tmp_path, [gslot("RID", 1), gslot("RID", 2)], model=MINI, samples=2)
    assert run_score(score, FakeJudge([judge()]), *budget_args(score, 1)) == 1  # $1e-9: stops
    assert [r["status"] for r in score.records] == ["budget_stopped", "budget_stopped"]
    assert all(budget.CHARGE_FIELD not in r for r in score.records)
    score2 = setup(tmp_path / "plain", [gslot("RID", 1)], model=MINI)
    assert run_score(score2, FakeJudge([judge()])) == 0
    assert budget.CHARGE_FIELD not in score2.records[0]


def test_invalid_persisted_charge_is_refused(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    score = setup(tmp_path, [gslot("RID", 1)], model=MINI)
    score.scores_dir.mkdir()
    (score.scores_dir / "RID.jsonl").write_text(
        json.dumps({"slot_key": "x", budget.CHARGE_FIELD: -5}) + "\n", encoding="utf-8", newline="\n"
    )
    with pytest.raises(budget.BudgetInputError, match="invalid budget_charged_nano"):
        budget.spend_so_far([score.run_dir], score.scores_dir)


# -------------------------------------------- pins for surviving mutations


def test_the_stop_is_sticky_even_for_a_later_cheaper_call(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    long_reply = "Thanks. " + "Could you tell me more about that? " * 120
    score = setup(tmp_path, [gslot("RID", 1), gslot("RID", 2, long_reply), gslot("RID", 3)],
                  model=MINI, samples=3)
    m1, m2, m3 = max_costs(score.run_dir, score.scores_dir, score.notes)
    assert m3 < m2
    limit = gen_cost(3) + JUDGE_CALL + m3  # slot 3 alone would fit; slot 2 doesn't
    assert gen_cost(3) + JUDGE_CALL + m2 > limit and gen_cost(3) + m1 <= limit
    fake = FakeJudge([judge(), judge()])
    assert run_score(score, fake, *budget_args(score, limit)) == 1
    assert len(fake.calls) == 1
    assert [r["status"] for r in score.records] == ["scored", "budget_stopped", "budget_stopped"]


def test_spend_counts_judge_records_of_every_judge_version(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    score = setup(tmp_path, [gslot("RID", 1)], model=MINI)
    assert run_score(score, FakeJudge([judge()]), "--judge-version", "judge-v2a") == 0
    assert scoring.read_score_records(score.scores_dir / "RID.jsonl")[0]["judge_prompt_version"] == "judge-v2a"
    capsys.readouterr()
    fake = FakeJudge([judge()])
    assert run_score(score, fake, *budget_args(score, 10**9)) == 0  # judge-v1 under a budget
    out = capsys.readouterr().out
    assert f"judge {budget.fmt_usd(JUDGE_CALL)})" in out  # the judge-v2a call counts


def test_every_needed_request_is_bounded_before_any_call(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    second = f"Second. {REPLY}"
    score = setup(tmp_path, [gslot("RID", 1), gslot("RID", 2, second)], model=MINI, samples=2)
    original = scoring.build_judge_request

    def unbounded_second(*args: Any, **kwargs: Any) -> dict[str, Any]:
        request = original(*args, **kwargs)
        if args[2] == second:
            request.pop("max_output_tokens")
        return request

    monkeypatch.setattr(scoring, "build_judge_request", unbounded_second)
    fake = FakeJudge([judge(), judge()])
    assert run_score(score, fake, *budget_args(score, 10**9)) == 2
    assert "max_output_tokens" in capsys.readouterr().err
    assert fake.calls == []  # refused up front, not after the first call
    assert not (score.scores_dir / "RID.jsonl").exists()
