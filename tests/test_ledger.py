"""The spending ledger and the guarded clients. Offline: fake clients only.

All usage and amounts below are SYNTHETIC TEST DATA.
"""

from __future__ import annotations

import json
import subprocess
import sys
import threading
from pathlib import Path
from typing import Any

import pytest
from google.genai import types
from test_gemini import FakeGeminiClient, gemini_spec, gresp
from test_run import FakeClient, FakeResponse, openai_spec
from test_scoring import REGISTRY, judge

from rightoncue import budget, gemini, ledger, openai_responses, review, scoring
from rightoncue.ledger import (
    BudgetExceeded,
    GuardedGemini,
    GuardedOpenAI,
    Ledger,
    LedgerError,
    UnknownModelPrice,
    canonical_bytes,
)
from rightoncue.runs import InputFile, create_run, read_slots, run_slots
from rightoncue.transcript import Turn

REPO = Path(__file__).parent.parent
TURNS = [Turn(role="agent", utterance="Hi"), Turn(role="user", utterance="Hello")]
CASE = b'{"role":"agent","utterance":"Hi"}\n{"role":"user","utterance":"Hello"}\n'
USD = 10**9


def entries(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def zero_retry(fake: Any) -> Any:
    fake.max_retries = 0
    return fake


# ------------------------------------------------------------------ the ledger


def test_reserve_then_settle_counts_the_actual(tmp_path: Path) -> None:
    led = Ledger(tmp_path / "ledger.jsonl", 1 * USD)
    rid = led.reserve("generation", "gpt-5.4", 5_000)
    assert led.spend() == 5_000  # open: its maximum
    led.settle(rid, "generation", "gpt-5.4", 1_200, "usage")
    assert led.spend() == 1_200
    reserve, settle = entries(led.path)
    assert reserve["type"] == "reserve" and reserve["id"] == rid and reserve["max_nano"] == 5_000
    assert reserve["kind"] == "generation" and reserve["model"] == "gpt-5.4"
    assert reserve["at"].endswith("+00:00") and reserve["budget_nano"] == USD
    assert settle == {**settle, "type": "settle", "id": rid, "actual_nano": 1_200, "basis": "usage"}


def test_a_crash_between_reserve_and_settle_counts_the_maximum(tmp_path: Path) -> None:
    led = Ledger(tmp_path / "ledger.jsonl", USD)
    led.reserve("judge", "gpt-5.4-mini", 7_777)
    # the process dies here: no settle entry
    fresh = Ledger(tmp_path / "ledger.jsonl", USD)
    assert fresh.state() == ledger.LedgerState(spent_nano=7_777, open_reservations=1, settled=0)


def test_refusal_at_the_exact_boundary(tmp_path: Path) -> None:
    led = Ledger(tmp_path / "ledger.jsonl", 10_000)
    led.settle(led.reserve("generation", "gpt-5.4", 6_000), "generation", "gpt-5.4", 6_000, "usage")
    before = led.path.read_bytes()
    with pytest.raises(BudgetExceeded, match="no request was made"):
        led.reserve("generation", "gpt-5.4", 4_001)
    assert led.path.read_bytes() == before  # nothing written on refusal
    led.reserve("generation", "gpt-5.4", 4_000)  # spend + max == budget is allowed
    assert led.spend() == 10_000
    with pytest.raises(BudgetExceeded):
        led.reserve("generation", "gpt-5.4", 1)


def test_concurrent_reservations_never_exceed_the_budget(tmp_path: Path) -> None:
    led = Ledger(tmp_path / "ledger.jsonl", 10 * 1_000)
    won: list[str] = []
    refused: list[int] = []
    start = threading.Barrier(32)

    def worker() -> None:
        start.wait()
        try:
            won.append(led.reserve("judge", "gpt-5.4-mini", 1_000))
        except BudgetExceeded:
            refused.append(1)

    threads = [threading.Thread(target=worker) for _ in range(32)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert len(won) == 10 and len(refused) == 22
    assert led.spend() == 10_000 and len(entries(led.path)) == 10


def test_spend_persists_across_a_new_process(tmp_path: Path) -> None:
    led = Ledger(tmp_path / "ledger.jsonl", USD)
    led.settle(led.reserve("generation", "gpt-5.4", 900), "generation", "gpt-5.4", 400, "usage")
    led.reserve("judge", "gpt-5.4-mini", 250)  # left open
    code = (
        "import sys; from pathlib import Path; from rightoncue.ledger import Ledger; "
        "print(Ledger(Path(sys.argv[1]), 10**9).spend())"
    )
    out = subprocess.run(
        [sys.executable, "-c", code, str(led.path)], capture_output=True, text=True, check=True
    )
    assert out.stdout.strip() == "650"


def test_torn_final_reserve_is_ignored_and_the_next_append_is_clean(tmp_path: Path) -> None:
    led = Ledger(tmp_path / "ledger.jsonl", USD)
    led.settle(led.reserve("generation", "gpt-5.4", 900), "generation", "gpt-5.4", 400, "usage")
    with open(led.path, "ab") as fh:
        fh.write(b'{"type":"reserve","id":"torn","at":"2026')  # killed mid-write
    assert led.spend() == 400
    led.reserve("judge", "gpt-5.4-mini", 100)
    assert led.spend() == 500
    assert all(e["id"] != "torn" for e in entries(led.path))  # every line parses
    assert led.path.read_bytes().endswith(b"\n")


def test_torn_final_settle_leaves_the_reservation_at_its_maximum(tmp_path: Path) -> None:
    led = Ledger(tmp_path / "ledger.jsonl", USD)
    rid = led.reserve("generation", "gpt-5.4", 900)
    with open(led.path, "ab") as fh:
        fh.write(f'{{"type":"settle","id":"{rid}","at":"x","kind":"generation","mo'.encode())
    assert led.state().spent_nano == 900 and led.state().open_reservations == 1


def test_complete_final_line_without_newline_counts(tmp_path: Path) -> None:
    led = Ledger(tmp_path / "ledger.jsonl", USD)
    rid = led.reserve("generation", "gpt-5.4", 900)
    line = json.dumps({"type": "settle", "id": rid, "at": "x", "kind": "generation",
                       "model": "gpt-5.4", "actual_nano": 300, "basis": "usage"})
    with open(led.path, "ab") as fh:
        fh.write(line.encode())
    assert led.spend() == 300
    led.reserve("judge", "gpt-5.4-mini", 5)
    assert led.spend() == 305 and len(entries(led.path)) == 3


@pytest.mark.parametrize(
    "bad",
    [
        b"not json\n",
        b'{"type":"reserve","id":"a","kind":"generation","model":"m","max_nano":-1}\n',
        b'{"type":"settle","id":"zz","kind":"judge","model":"m","actual_nano":1,"basis":"usage"}\n',
        b'{"type":"mystery","id":"a","kind":"judge","model":"m"}\n',
    ],
)
def test_a_corrupt_line_before_the_last_raises(tmp_path: Path, bad: bytes) -> None:
    led = Ledger(tmp_path / "ledger.jsonl", USD)
    led.reserve("generation", "gpt-5.4", 900)
    with open(led.path, "ab") as fh:
        fh.write(bad)
    led_path_size = led.path.stat().st_size
    with pytest.raises(LedgerError):
        led.spend()
    with pytest.raises(LedgerError):
        led.reserve("generation", "gpt-5.4", 1)  # never a silent zero, never a call
    assert led.path.stat().st_size == led_path_size


def test_settled_twice_is_corruption(tmp_path: Path) -> None:
    led = Ledger(tmp_path / "ledger.jsonl", USD)
    rid = led.reserve("generation", "gpt-5.4", 900)
    led.settle(rid, "generation", "gpt-5.4", 1, "usage")
    led.settle(rid, "generation", "gpt-5.4", 1, "usage")
    with pytest.raises(LedgerError, match="settled twice"):
        led.spend()


def test_new_ledger_file_and_directory_are_fsynced(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    synced: list[Path] = []
    monkeypatch.setattr(ledger, "_fsync_dir", lambda d: synced.append(d))
    led = Ledger(tmp_path / "new" / "ledger.jsonl", USD)
    led.ensure_writable()
    assert led.path.is_file() and synced == [tmp_path / "new"]
    led.ensure_writable()
    assert synced == [tmp_path / "new"]  # only on first creation


def test_unwritable_location_is_a_ledger_error(tmp_path: Path) -> None:
    blocker = tmp_path / "file"
    blocker.write_text("x")
    with pytest.raises(LedgerError, match="cannot open the ledger"):
        Ledger(blocker / "ledger.jsonl", USD).ensure_writable()


# ----------------------------------------------------------- prices and maxima


def test_prices_reuse_budget_constants_and_unknown_models_raise() -> None:
    assert ledger.prices_for("gpt-5.4") == budget.OPENAI_PRICES["gpt-5.4"] == (2_500, 15_000)
    assert ledger.prices_for("gpt-5.4-mini") == (750, 4_500)
    assert ledger.prices_for("gemini-3.5-flash") == (1_500, 7_500)
    with pytest.raises(UnknownModelPrice):
        ledger.prices_for("gpt-9")
    with pytest.raises(UnknownModelPrice):
        ledger.prices_for("gemini-3.6-flash")


def test_judge_maximum_equals_the_budget_guards(monkeypatch: pytest.MonkeyPatch) -> None:
    for version, (path, sha) in REGISTRY.items():
        monkeypatch.setitem(scoring.JUDGE_PROMPTS, version, (REPO / path, sha))
    j = scoring.load_judge_prompt("judge-v1")
    req = scoring.build_judge_request(j.text, TURNS, "A reply é.", None, scorer_version=j.scorer_version)
    assert ledger.max_call_cost(req, req["model"], req["max_output_tokens"]) == budget.max_call_cost(req)


def test_missing_cap_is_refused() -> None:
    req = openai_responses.build_request("P", TURNS, "gpt-5.4", "none")
    with pytest.raises(BudgetExceeded, match="no positive max_output_tokens"):
        ledger.max_call_cost(req, "gpt-5.4", None)


# --------------------------------------------------------------- guarded clients


def test_guarded_openai_generation_reserves_bytes_and_cap_then_settles_usage(tmp_path: Path) -> None:
    led = Ledger(tmp_path / "l.jsonl", USD)
    fake = zero_retry(FakeClient(["Hello there."]))
    guarded = GuardedOpenAI(fake, led, "generation")
    req = openai_responses.build_request("Be Riley é.", TURNS, "gpt-5.4", "none", 400)
    resp = guarded.responses.create(**req)
    assert resp.output_text == "Hello there." and fake.calls == [req]
    reserve, settle = entries(led.path)
    assert reserve["max_nano"] == canonical_bytes(req) * 2_500 + 400 * 15_000
    assert canonical_bytes(req) == len(
        json.dumps(req, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()
    )
    assert settle["actual_nano"] == 5 * 2_500 + 3 * 15_000 and settle["basis"] == "usage"
    assert openai_responses.client_settings(guarded) == {"max_retries": 0, "timeout": "60"}


def test_guarded_openai_refuses_a_retrying_client(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="max_retries=0"):
        GuardedOpenAI(FakeClient([]), Ledger(tmp_path / "l.jsonl", USD), "judge")


def test_a_raised_call_settles_at_the_maximum_and_reraises(tmp_path: Path) -> None:
    led = Ledger(tmp_path / "l.jsonl", USD)
    fake = zero_retry(FakeClient([TimeoutError("slow")]))
    req = openai_responses.build_request("P", TURNS, "gpt-5.4-mini", "none", 400)
    with pytest.raises(TimeoutError):
        GuardedOpenAI(fake, led, "generation").responses.create(**req)
    reserve, settle = entries(led.path)
    assert settle["actual_nano"] == reserve["max_nano"]
    assert settle["basis"] == "maximum_raised" and settle["error"] == "TimeoutError"


def test_missing_usage_settles_at_the_maximum(tmp_path: Path) -> None:
    led = Ledger(tmp_path / "l.jsonl", USD)
    resp = FakeResponse("Hi.")
    resp.usage = None  # type: ignore[assignment]
    fake = zero_retry(FakeClient([]))
    fake.responses.create = lambda **kw: resp
    req = openai_responses.build_request("P", TURNS, "gpt-5.4", "none", 400)
    GuardedOpenAI(fake, led, "generation").responses.create(**req)
    reserve, settle = entries(led.path)
    assert settle["actual_nano"] == reserve["max_nano"] and settle["basis"] == "maximum_no_usage"


def test_refused_call_makes_no_request(tmp_path: Path) -> None:
    led = Ledger(tmp_path / "l.jsonl", 1_000)
    fake = zero_retry(FakeClient(["never"]))
    req = openai_responses.build_request("P", TURNS, "gpt-5.4", "none", 400)
    with pytest.raises(BudgetExceeded):
        GuardedOpenAI(fake, led, "generation").responses.create(**req)
    assert fake.calls == [] and not led.path.exists()


def test_unknown_model_makes_no_request(tmp_path: Path) -> None:
    fake = zero_retry(FakeClient(["never"]))
    req = openai_responses.build_request("P", TURNS, "gpt-9", "none", 400)
    with pytest.raises(UnknownModelPrice):
        GuardedOpenAI(fake, Ledger(tmp_path / "l.jsonl", USD), "generation").responses.create(**req)
    assert fake.calls == []


def test_guarded_gemini_reserves_real_request_bytes_and_settles_with_thinking(tmp_path: Path) -> None:
    led = Ledger(tmp_path / "l.jsonl", USD)
    fake = FakeGeminiClient(["Hi."])
    req = gemini.build_request("Be Riley é.", TURNS, "gemini-3.5-flash", "MINIMAL", 400)
    gemini.generate(GuardedGemini(fake, led), req)
    assert fake.calls[0]["config"].max_output_tokens == 400
    assert fake.calls[0]["config"].automatic_continuation is False
    reserve, settle = entries(led.path)
    assert reserve["max_nano"] == canonical_bytes(req) * 1_500 + 400 * 7_500
    # gresp usage: prompt 11, candidates 4, thoughts 6 (thoughts are output)
    assert settle["actual_nano"] == 11 * 1_500 + (4 + 6) * 7_500


def test_gemini_thoughts_none_count_as_zero_and_missing_candidates_keep_the_maximum(tmp_path: Path) -> None:
    led = Ledger(tmp_path / "l.jsonl", USD)
    r1 = gresp("Hi.")
    r1.usage_metadata.thoughts_token_count = None  # type: ignore[union-attr]
    r2 = gresp("Hi.")
    r2.usage_metadata.candidates_token_count = None  # type: ignore[union-attr]
    fake = FakeGeminiClient([r1, r2])
    req = gemini.build_request("P", TURNS, "gemini-3.5-flash", "MINIMAL", 400)
    gemini.generate(GuardedGemini(fake, led), req)
    gemini.generate(GuardedGemini(fake, led), req)
    _, s1, r, s2 = entries(led.path)
    assert s1["actual_nano"] == 11 * 1_500 + 4 * 7_500
    assert s2["actual_nano"] == r["max_nano"] and s2["basis"] == "maximum_no_usage"


def test_gemini_uncapped_or_continuing_request_is_refused(tmp_path: Path) -> None:
    led = Ledger(tmp_path / "l.jsonl", USD)
    fake = FakeGeminiClient(["never"])
    with pytest.raises(BudgetExceeded, match="automatic continuation"):
        gemini.generate(GuardedGemini(fake, led), gemini.build_request("P", TURNS, "gemini-3.5-flash", "MINIMAL"))
    req = gemini.build_request("P", TURNS, "gemini-3.5-flash", "MINIMAL", 400)
    del req["config"]["max_output_tokens"]
    with pytest.raises(BudgetExceeded, match="max_output_tokens"):
        gemini.generate(GuardedGemini(fake, led), req)
    assert fake.calls == [] and not led.path.exists()


def test_runner_through_guards_stops_cleanly_at_the_budget(tmp_path: Path) -> None:
    """The runner is unchanged: a refused call propagates, and no slot is written for it."""
    run_dir, manifest = create_run(
        tmp_path / "runs", "RID", InputFile("prompts/v1.md", b"prompt"),
        [InputFile("cases/c0.jsonl", CASE)], [openai_spec("gpt-5.4")], 3, max_output_tokens=400,
    )
    req = manifest["cases"][0]["requests"]["gpt-5.4"]
    one = ledger.max_call_cost(req, "gpt-5.4", 400)
    actual = 5 * 2_500 + 3 * 15_000
    led = Ledger(tmp_path / "l.jsonl", actual + one)  # room for exactly two calls
    fake = zero_retry(FakeClient(["a", "b", "c"]))
    with pytest.raises(BudgetExceeded):
        run_slots({"openai": GuardedOpenAI(fake, led, "generation")}, run_dir, manifest)
    assert len(fake.calls) == 2 and len(read_slots(run_dir)) == 2
    assert led.spend() == 2 * actual


def test_each_scoring_attempt_is_its_own_reservation(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """An app-level retry (re-scoring a needs_review reply) reserves again."""
    for version, (path, sha) in REGISTRY.items():
        monkeypatch.setitem(scoring.JUDGE_PROMPTS, version, (REPO / path, sha))
    monkeypatch.setattr(review, "CLIENT_FACTORIES", {})
    run_dir, manifest = create_run(
        tmp_path / "runs", "RID", InputFile("prompts/v1.md", b"prompt"),
        [InputFile("cases/c0.jsonl", CASE)], [openai_spec("gpt-5.4-mini")], 1, max_output_tokens=400,
    )
    led = Ledger(tmp_path / "l.jsonl", USD)
    fake = zero_retry(FakeClient(["A fine reply.", "not json", judge()]))
    run_slots({"openai": GuardedOpenAI(fake, led, "generation")}, run_dir, manifest)
    judge_client = GuardedOpenAI(fake, led, "judge")
    review.score_run(run_dir, "judge-v1", scores_dir=tmp_path / "scores", client=judge_client)
    review.score_run(run_dir, "judge-v1", scores_dir=tmp_path / "scores", client=judge_client)
    kinds = [(e["type"], e["kind"]) for e in entries(led.path)]
    assert kinds == [("reserve", "generation"), ("settle", "generation"),
                     ("reserve", "judge"), ("settle", "judge"), ("reserve", "judge"), ("settle", "judge")]
    statuses = [json.loads(x)["status"] for x in (tmp_path / "scores" / "RID.jsonl").read_text().splitlines()]
    assert statuses == ["needs_review", "scored"]


# ---------------------------------------------------------- the generation cap


def test_cap_is_recorded_in_settings_requests_slots_and_note(tmp_path: Path) -> None:
    run_dir, manifest = create_run(
        tmp_path, "RID", InputFile("prompts/v1.md", b"prompt"), [InputFile("cases/c0.jsonl", CASE)],
        [openai_spec("gpt-5.4"), gemini_spec("gemini-3.5-flash")], 1, max_output_tokens=400,
    )
    on_disk = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    assert on_disk == manifest
    assert [m["settings"]["max_output_tokens"] for m in manifest["models"]] == [400, 400]
    reqs = manifest["cases"][0]["requests"]
    assert reqs["gpt-5.4"]["max_output_tokens"] == 400
    assert reqs["gemini-3.5-flash"]["config"]["max_output_tokens"] == 400
    assert reqs["gemini-3.5-flash"]["config"]["automatic_continuation"] is False
    assert manifest["generation_params_note"] == {
        "openai": openai_responses.PARAMS_NOTE_CAPPED, "gemini": gemini.PARAMS_NOTE_CAPPED,
    }
    run_slots({"openai": FakeClient(["x"]), "gemini": FakeGeminiClient(["y"])}, run_dir, manifest)
    assert all(s["settings"]["max_output_tokens"] == 400 for s in read_slots(run_dir))
    config = types.GenerateContentConfig.model_validate(reqs["gemini-3.5-flash"]["config"])
    assert config.max_output_tokens == 400


def test_uncapped_requests_are_unchanged() -> None:
    assert "max_output_tokens" not in openai_responses.build_request("P", TURNS, "gpt-5.4", "none")
    assert "max_output_tokens" not in gemini.build_request("P", TURNS, "g", "MINIMAL")["config"]
    assert openai_responses.build_request("P", TURNS, "gpt-5.4", "none", None) == {
        "model": "gpt-5.4", "instructions": "P",
        "input": [{"role": "assistant", "content": "Hi"}, {"role": "user", "content": "Hello"}],
        "reasoning": {"effort": "none"},
    }


@pytest.mark.parametrize("cap", [0, -5, 1.5, "400", True])
def test_invalid_cap_is_refused_before_any_file(tmp_path: Path, cap: Any) -> None:
    with pytest.raises(ValueError, match="max_output_tokens"):
        create_run(tmp_path, "RID", InputFile("prompts/v1.md", b"p"), [InputFile("cases/c.jsonl", CASE)],
                   [openai_spec("gpt-5.4")], 1, max_output_tokens=cap)
    assert list(tmp_path.iterdir()) == []


def test_gemini_no_retry_client_makes_one_attempt() -> None:
    """Built offline (no request): the SDK's retry stop is one attempt."""
    from google.genai import _api_client

    client = gemini.make_client("fake-key-not-used", gemini.NO_RETRY_OPTIONS)
    options = client._api_client._http_options.retry_options
    assert options.attempts == 1
    assert _api_client.retry_args(options)["stop"].max_attempt_number == 1
    assert gemini.client_settings(gemini.NO_RETRY_OPTIONS)["retry_options"] == {"attempts": 1}
    assert gemini.client_settings()["retry_options"]["attempts"] == 3  # the CLI default is unchanged
