"""rightoncue.live: configuration, access gate, limits, projection, dry run and runs.

Offline: fake or dry-run clients only; real client constructors raise if touched.
All usage and amounts below are SYNTHETIC TEST DATA.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import openai
import pytest
from test_gemini import FakeGeminiClient
from test_run import FakeClient
from test_scoring import judge

from rightoncue import dryrun, gemini, ledger, live, review, scoring
from rightoncue.ledger import BudgetExceeded, Ledger
from rightoncue.runs import ModelSpec, _build_request
from rightoncue.transcript import parse_transcript

REPO = Path(__file__).parent.parent
CASE = '{"role":"agent","utterance":"Hi"}\n{"role":"user","utterance":"Hello"}\n'
USD = 10**9
LIVE_ENV = (
    "RIGHTONCUE_HOSTED", "RIGHTONCUE_ACCESS_CODE", "RIGHTONCUE_BUDGET_USD", "RIGHTONCUE_DATA_DIR",
    "RIGHTONCUE_MAX_SAMPLES", "RIGHTONCUE_DRY_RUN", "RIGHTONCUE_DRY_RUN_DELAY_S",
)


# Captured at import, before any fixture replaces them.
REAL_FACTORIES = dict(live.GENERATION_FACTORIES)
REAL_MAKE_CLIENT = gemini.make_client


def boom(*a: Any, **k: Any) -> Any:
    raise AssertionError("a real client must not be built in an offline test")


@pytest.fixture(autouse=True)
def offline(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(REPO)
    for name in LIVE_ENV + ("OPENAI_API_KEY", "GEMINI_API_KEY"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(review, "CLIENT_FACTORIES", {"openai": boom, "gemini": boom})
    monkeypatch.setattr(live, "GENERATION_FACTORIES", {"openai": boom, "gemini": boom})
    monkeypatch.setattr(openai, "OpenAI", boom)
    monkeypatch.setattr(gemini, "make_client", boom)
    live.reset_gate()


def cfg_for(tmp_path: Path, **env: str) -> live.LiveConfig:
    base = {"RIGHTONCUE_HOSTED": "1", "RIGHTONCUE_ACCESS_CODE": "open sesame",
            "RIGHTONCUE_BUDGET_USD": "5.00", "RIGHTONCUE_DATA_DIR": str(tmp_path / "data")}
    return live.load_config({**base, **env})


def entries(path: Path) -> list[dict[str, Any]]:
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x]


# ----------------------------------------------------------------- configuration


def test_defaults_without_any_variable() -> None:
    cfg = live.load_config({})
    assert (cfg.hosted, cfg.access_code, cfg.budget_nano, cfg.dry_run) == (False, None, None, False)
    assert cfg.data_dir == live.DEFAULT_LOCAL_DATA_DIR == review.REPO_ROOT / "data"
    assert cfg.max_samples == 2


def test_hosted_has_no_default_data_dir_or_budget() -> None:
    cfg = live.load_config({"RIGHTONCUE_HOSTED": "1"})
    assert cfg.data_dir is None and cfg.budget_nano is None


def test_budget_is_exact_nano_usd() -> None:
    assert live.load_config({"RIGHTONCUE_BUDGET_USD": "5.00"}).budget_nano == 5 * USD
    assert live.load_config({"RIGHTONCUE_BUDGET_USD": "0.000000001"}).budget_nano == 1


@pytest.mark.parametrize(
    "env,match",
    [
        ({"RIGHTONCUE_BUDGET_USD": "abc"}, "not a number"),
        ({"RIGHTONCUE_BUDGET_USD": "-1"}, "positive"),
        ({"RIGHTONCUE_BUDGET_USD": "0"}, "positive"),
        ({"RIGHTONCUE_BUDGET_USD": "NaN"}, "positive"),
        ({"RIGHTONCUE_BUDGET_USD": "0.0000000001"}, "precision"),
        ({"RIGHTONCUE_HOSTED": "true"}, "RIGHTONCUE_HOSTED must be 1 or 0"),
        ({"RIGHTONCUE_DRY_RUN": "yes"}, "RIGHTONCUE_DRY_RUN must be 1 or 0"),
        ({"RIGHTONCUE_MAX_SAMPLES": "0"}, "from 1 to 5"),
        ({"RIGHTONCUE_MAX_SAMPLES": "6"}, "from 1 to 5"),
        ({"RIGHTONCUE_MAX_SAMPLES": "two"}, "from 1 to 5"),
        ({"RIGHTONCUE_DATA_DIR": "."}, "committed folders"),
        ({"RIGHTONCUE_DATA_DIR": "runs/fresh"}, "committed folders"),
        ({"RIGHTONCUE_DATA_DIR": "scores"}, "committed folders"),
        ({"RIGHTONCUE_DRY_RUN": "1", "RIGHTONCUE_DRY_RUN_DELAY_S": "-1"}, "from 0 to"),
        ({"RIGHTONCUE_DRY_RUN": "1", "RIGHTONCUE_DRY_RUN_DELAY_S": "soon"}, "not a number"),
    ],
)
def test_bad_values_are_clear_errors(env: dict[str, str], match: str) -> None:
    with pytest.raises(live.ConfigError, match=match):
        live.load_config(env)


def test_relative_data_dir_resolves_against_the_repo() -> None:
    assert live.load_config({"RIGHTONCUE_DATA_DIR": "data/x"}).data_dir == (REPO / "data" / "x").resolve()


def test_delay_is_honoured_only_in_dry_run() -> None:
    assert live.load_config({"RIGHTONCUE_DRY_RUN_DELAY_S": "5"}).dry_run_delay_s == 0.0
    assert live.load_config({"RIGHTONCUE_DRY_RUN": "1", "RIGHTONCUE_DRY_RUN_DELAY_S": "2.5"}).dry_run_delay_s == 2.5


def test_access_code_is_not_in_the_repr(tmp_path: Path) -> None:
    assert "open sesame" not in repr(cfg_for(tmp_path))


def test_hosted_problems_name_variables_only(tmp_path: Path) -> None:
    cfg = live.load_config({"RIGHTONCUE_HOSTED": "1"})
    problems = live.hosted_problems(cfg, {"OPENAI_API_KEY": "sk-x"})
    assert problems == [
        "RIGHTONCUE_ACCESS_CODE is not set",
        "RIGHTONCUE_BUDGET_USD is not set",
        "RIGHTONCUE_DATA_DIR is not set (required in hosted mode)",
        "GEMINI_API_KEY is not set",
    ]
    full = cfg_for(tmp_path)
    assert live.hosted_problems(full, {"OPENAI_API_KEY": "a", "GEMINI_API_KEY": "b"}) == []
    assert live.hosted_problems(cfg_for(tmp_path, RIGHTONCUE_DRY_RUN="1"), {}) == []  # keys waived
    blank = cfg_for(tmp_path, RIGHTONCUE_ACCESS_CODE="   ")
    assert "RIGHTONCUE_ACCESS_CODE is not set" in live.hosted_problems(blank, {"OPENAI_API_KEY": "a", "GEMINI_API_KEY": "b"})


# --------------------------------------------------------------------- the gate


def test_gate_right_and_wrong_code(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.DEBUG)
    assert live.try_unlock("nope", "open sesame") == "wrong"
    assert live.try_unlock("open sesame ", "open sesame") == "wrong"
    assert live.try_unlock("", "open sesame") == "empty"
    assert live.try_unlock("open sesame", "open sesame") == "unlocked"
    assert live.try_unlock("ünïcödé", "ünïcödé") == "unlocked"
    assert "open sesame" not in caplog.text and "nope" not in caplog.text


def test_empty_configured_code_never_unlocks() -> None:
    for expected in ("", None):
        with pytest.raises(ValueError):
            live.try_unlock("", expected)


def test_attempt_limit_and_process_wide_cooldown(monkeypatch: pytest.MonkeyPatch) -> None:
    now = [1000.0]
    monkeypatch.setattr(live, "clock", lambda: now[0])
    for _ in range(4):
        assert live.try_unlock("bad", "good") == "wrong"
    assert live.try_unlock("bad", "good") == "cooldown"  # the fifth failure starts it
    assert live.gate_wait_s() == live.COOLDOWN_S
    # even the right code is refused during the cooldown, from any session
    assert live.try_unlock("good", "good") == "cooldown"
    now[0] += live.COOLDOWN_S - 0.5
    assert live.try_unlock("good", "good") == "cooldown"
    now[0] += 1
    assert live.gate_wait_s() == 0
    assert live.try_unlock("good", "good") == "unlocked"


# ---------------------------------------------------------------- per-run limits


def turns_text(n: int, last: str = "user") -> str:
    roles = ["agent", "user"] * n
    rows = roles[len(roles) - n:]
    rows[-1] = last
    return "\n".join(json.dumps({"role": r, "utterance": "x"}) for r in rows) + "\n"


def test_limits_accept_the_edges() -> None:
    assert live.validate_run("p" * 12_000, turns_text(40), ["gpt-5.4", "gemini-3.5-flash"], 2, 2) == []


@pytest.mark.parametrize(
    "prompt,case,models,samples,match",
    [
        ("p" * 12_001, CASE, ["gpt-5.4"], 1, "Prompt: 12,001 characters"),
        ("   ", CASE, ["gpt-5.4"], 1, "the prompt is empty"),
        ("p", turns_text(41), ["gpt-5.4"], 1, "41 turns; the limit is 40"),
        ("p", CASE + " " * 12_000, ["gpt-5.4"], 1, "Transcript: 12,0"),
        ("p", turns_text(3, last="agent"), ["gpt-5.4"], 1, "last turn must be from 'user'"),
        ("p", "not json", ["gpt-5.4"], 1, "invalid JSON"),
        ("p", CASE, [], 1, "at least one model"),
        ("p", CASE, ["gpt-4o"], 1, "Unsupported model"),
        ("p", CASE, ["gpt-5.4", "gpt-5.4"], 1, "selected twice"),
        ("p", CASE, ["gpt-5.4"], 0, "from 1 to 2"),
        ("p", CASE, ["gpt-5.4"], 3, "from 1 to 2"),
    ],
)
def test_limits_refuse(prompt: str, case: str, models: list[str], samples: int, match: str) -> None:
    errors = live.validate_run(prompt, case, models, samples, 2)
    assert any(match in e for e in errors), errors


# -------------------------------------------------------------------- projection


def test_projection_is_the_sum_of_per_call_maxima() -> None:
    prompt = review.read_input(REPO / "prompts" / "v2.md")
    case = review.read_input(REPO / "cases" / "holdout" / "H3.jsonl")
    models = ["gpt-5.4", "gpt-5.4-mini", "gemini-3.5-flash"]
    proj = live.project_run(prompt, case, models, 2)
    turns = parse_transcript(case.text)
    gen = 0
    for m in models:
        settings = ({"reasoning_effort": "none"} if m.startswith("gpt") else {"thinking_level": "MINIMAL"}) | {"max_output_tokens": 400}
        req = _build_request(ModelSpec(m, review.provider_for(m), settings, {}), prompt.text, turns)
        gen += ledger.max_call_cost(req, m, 400) * 2
    j = scoring.load_judge_prompt("judge-v1")
    criteria = scoring.load_criteria(review.NOTES_PATH)["H3"]
    jreq = scoring.build_judge_request(j.text, turns, "x" * 6_400, criteria, scorer_version=j.scorer_version)
    assert proj.generation_nano == gen
    # 6 replies, each judged at most twice: the first attempt and one judge-only retry
    assert proj.judge_nano == 12 * ledger.max_call_cost(jreq, "gpt-5.4-mini", 1500)
    assert (proj.generation_calls, proj.judge_calls) == (6, 12)
    assert proj.total_nano < USD // 2  # well inside the $5.00 allowance


# ---------------------------------------------------------------------- dry run


def test_dry_run_judgment_is_valid_judge_v1_and_replies_pass_the_checks() -> None:
    turns = parse_transcript(CASE)
    fake = dryrun.DryRunOpenAI()
    reply = fake.responses.create(model="gpt-5.4", input=[]).output_text
    assert reply.startswith(dryrun.DRY_NOTE)
    assert scoring.check_structure(reply).single_turn_pass
    judgment, errors = scoring.validate_judge_output(
        "completed", dryrun.placeholder_judgment(), turns, reply, scorer_version="scorer-1"
    )
    assert judgment is not None, errors
    g = dryrun.DryRunGemini()
    resp = g.models.generate_content(model="gemini-3.5-flash", contents=[], config={})
    fields = gemini.slot_fields(resp, resp.model_dump(mode="json"))
    assert fields["status"] == "ok" and fields["returned_model"] == dryrun.DRY_MODEL
    assert scoring.check_structure(fields["output_text"]).single_turn_pass


def test_dry_run_never_builds_a_real_client_even_with_keys(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "sk-real-looking")
    monkeypatch.setenv("GEMINI_API_KEY", "gm-real-looking")
    cfg = cfg_for(tmp_path, RIGHTONCUE_DRY_RUN="1")
    led = live.open_ledger(cfg)
    gen, judge_client = live.guarded_clients(cfg, led, ["openai", "gemini"])
    assert isinstance(gen["openai"]._inner, dryrun.DryRunOpenAI)
    assert isinstance(gen["gemini"]._inner, dryrun.DryRunGemini)
    assert isinstance(judge_client._inner, dryrun.DryRunOpenAI)


def prompt_and_case() -> tuple[Any, Any]:
    return (review.read_input(REPO / "prompts" / "v2.md"),
            review.read_input(REPO / "cases" / "holdout" / "H3.jsonl"))


def committed_snapshot() -> dict[str, int]:
    return {p.relative_to(REPO).as_posix(): p.stat().st_mtime_ns
            for d in ("runs", "scores") for p in (REPO / d).rglob("*") if p.is_file()}


def test_dry_run_fresh_run_is_accounted_in_its_own_ledger(tmp_path: Path) -> None:
    before = committed_snapshot()
    cfg = cfg_for(tmp_path, RIGHTONCUE_DRY_RUN="1")
    prompt, case = prompt_and_case()
    out = live.run_fresh(cfg, prompt, case, ["gpt-5.4", "gemini-3.5-flash"], 2)
    assert out.messages == []
    data = tmp_path / "data"
    assert not (data / "ledger.jsonl").exists()
    rows = entries(data / "ledger.dry-run.jsonl")
    settles = [e for e in rows if e["type"] == "settle"]
    assert [e["kind"] for e in settles] == ["generation"] * 4 + ["judge"] * 4
    assert {e["basis"] for e in settles} == {"usage"}
    gen_cost = {"gpt-5.4": 850 * 2_500 + 50 * 15_000, "gemini-3.5-flash": 850 * 1_500 + 30 * 7_500}
    assert [e["actual_nano"] for e in settles[:4]] == [gen_cost["gpt-5.4"]] * 2 + [gen_cost["gemini-3.5-flash"]] * 2
    assert all(e["actual_nano"] == 1_700 * 750 + 450 * 4_500 for e in settles[4:])
    view = review.load_run_view(out.run_dir, review.scores_path_for(out.run_id, data / "scores"), "judge-v1")
    assert all(c.decision == "acceptable" and c.reported_model == dryrun.DRY_MODEL for c in view.all_cards())
    manifest = json.loads((out.run_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["models"][0]["client"] == {"max_retries": 0, "timeout": "dry-run"}
    assert manifest["models"][1]["client"]["retry_options"] == {"attempts": 1}
    assert manifest["models"][1]["settings"] == {"thinking_level": "MINIMAL", "max_output_tokens": 400}
    assert committed_snapshot() == before


def fake_factories(monkeypatch: pytest.MonkeyPatch, openai_outputs: list[Any], gemini_outputs: list[Any]) -> tuple[Any, Any]:
    o = FakeClient(openai_outputs)
    o.max_retries = 0
    g = FakeGeminiClient(gemini_outputs)
    monkeypatch.setattr(live, "GENERATION_FACTORIES", {"openai": lambda: o, "gemini": lambda: g})
    monkeypatch.setenv("OPENAI_API_KEY", "fake")
    monkeypatch.setenv("GEMINI_API_KEY", "fake")
    return o, g


def test_fresh_run_with_fake_clients_goes_through_the_real_ledger(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    o, g = fake_factories(monkeypatch, ["Thanks. What drew you to the ICU?", judge(), judge()], ["Got it. How long on nights?"])
    out = live.run_fresh(cfg_for(tmp_path), *prompt_and_case(), ["gpt-5.4-mini", "gemini-3.5-flash"], 1)
    rows = entries(tmp_path / "data" / "ledger.jsonl")
    assert [(e["type"], e["kind"], e["model"]) for e in rows] == [
        ("reserve", "generation", "gpt-5.4-mini"), ("settle", "generation", "gpt-5.4-mini"),
        ("reserve", "generation", "gemini-3.5-flash"), ("settle", "generation", "gemini-3.5-flash"),
        ("reserve", "judge", "gpt-5.4-mini"), ("settle", "judge", "gpt-5.4-mini"),
        ("reserve", "judge", "gpt-5.4-mini"), ("settle", "judge", "gpt-5.4-mini"),
    ]
    assert o.calls[0]["max_output_tokens"] == 400 and o.calls[0]["reasoning"] == {"effort": "none"}
    assert g.calls[0]["config"].max_output_tokens == 400
    assert (out.run_dir.parent, out.run_dir.name) == (tmp_path / "data" / "runs", out.run_id)
    assert (tmp_path / "data" / "scores" / f"{out.run_id}.jsonl").is_file()


def test_projection_over_the_remaining_budget_makes_no_call(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    o, g = fake_factories(monkeypatch, ["never"], ["never"])
    cfg = cfg_for(tmp_path, RIGHTONCUE_BUDGET_USD="0.01")
    with pytest.raises(BudgetExceeded, match="projected maximum"):
        live.run_fresh(cfg, *prompt_and_case(), ["gpt-5.4"], 2)
    assert o.calls == [] and g.calls == []
    assert not (tmp_path / "data" / "runs").exists()


def test_second_run_while_one_is_in_progress_is_refused(tmp_path: Path) -> None:
    lock = live.run_lock()
    assert lock.acquire(blocking=False)
    try:
        with pytest.raises(live.RunBusy, match="Another run is in progress"):
            live.run_fresh(cfg_for(tmp_path, RIGHTONCUE_DRY_RUN="1"), *prompt_and_case(), ["gpt-5.4"], 1)
    finally:
        lock.release()
    assert not (tmp_path / "data").exists()


def test_invalid_run_is_refused_before_the_lock_or_the_ledger(tmp_path: Path) -> None:
    prompt, case = prompt_and_case()
    with pytest.raises(ValueError, match="from 1 to 2"):
        live.run_fresh(cfg_for(tmp_path, RIGHTONCUE_DRY_RUN="1"), prompt, case, ["gpt-5.4"], 3)
    assert not (tmp_path / "data").exists()


def test_run_lock_is_released_after_a_base_exception(tmp_path: Path) -> None:
    class Stop(BaseException):  # like Streamlit's StopException
        pass

    def on_slot(rec: dict[str, Any]) -> None:
        raise Stop()

    with pytest.raises(Stop):
        live.run_fresh(cfg_for(tmp_path, RIGHTONCUE_DRY_RUN="1"), *prompt_and_case(), ["gpt-5.4"], 1, on_slot=on_slot)
    assert live.run_lock().acquire(blocking=False)
    live.run_lock().release()


def test_budget_reached_mid_run_is_reported_not_raised(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The projection fits, but the ledger has been spent by someone else since."""
    cfg = cfg_for(tmp_path, RIGHTONCUE_DRY_RUN="1")
    prompt, case = prompt_and_case()
    proj = live.project_run(prompt, case, ["gpt-5.4"], 2)
    led = Ledger(cfg.ledger_path, cfg.budget_nano)  # type: ignore[arg-type]
    led.settle(led.reserve("judge", "gpt-5.4-mini", 0), "judge", "gpt-5.4-mini", 0, "usage")
    real_remaining = Ledger.remaining
    calls = {"n": 0}

    def remaining_then_spend(self: Ledger) -> int:  # another reviewer spends after the check
        value = real_remaining(self)
        if calls["n"] == 0:  # leave room for exactly one generation call's maximum
            spent = value - (proj.generation_nano // 2 + 1)
            r = self.reserve("judge", "gpt-5.4-mini", spent)
            self.settle(r, "judge", "gpt-5.4-mini", spent, "usage")
        calls["n"] += 1
        return value

    monkeypatch.setattr(Ledger, "remaining", remaining_then_spend)
    out = live.run_fresh(cfg, prompt, case, ["gpt-5.4"], 2)
    assert any(m.startswith("Generation stopped: budget reached") for m in out.messages)
    view = review.load_run_view(out.run_dir, None, None)
    assert [c.state for c in view.all_cards()] == ["reply", "missing"]
    assert led.spend() <= cfg.budget_nano  # type: ignore[operator]
    assert led.state().open_reservations == 0


def test_redaction_keeps_only_type_and_status(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import httpx2

    req = httpx2.Request("POST", "https://x")
    err = openai.AuthenticationError(
        "Incorrect API key provided: sk-proj-****abcd", response=httpx2.Response(401, request=req), body=None
    )
    fake_factories(monkeypatch, [err], [])
    out = live.run_fresh(cfg_for(tmp_path), *prompt_and_case(), ["gpt-5.4-mini"], 2)
    assert out.messages == [
        "Generation stopped after a fatal provider error (AuthenticationError, HTTP 401); "
        "the remaining replies were not attempted."
    ]
    view = review.load_run_view(out.run_dir, None, None)
    review.redact_provider_errors(view)
    card = view.cases[0].cards["gpt-5.4-mini"][0]
    assert card.note == "Generation failed: no reply was produced. AuthenticationError (HTTP 401)."
    assert "abcd" not in card.note


# ------------------------------------------------- production factories and SDK


def test_production_factories_build_no_retry_clients(monkeypatch: pytest.MonkeyPatch) -> None:
    """The real factories (every other test replaces them), with recording stand-ins."""
    built: list[tuple[str, Any]] = []
    monkeypatch.setattr(openai, "OpenAI", lambda **kw: built.append(("openai", kw)) or "o")
    monkeypatch.setattr(gemini, "make_client", lambda key, opts=None: built.append(("gemini", (key, opts))) or "g")
    monkeypatch.setenv("GEMINI_API_KEY", "gm-test")
    assert REAL_FACTORIES["openai"]() == "o"
    assert REAL_FACTORIES["gemini"]() == "g"
    assert built == [("openai", {"max_retries": 0}), ("gemini", ("gm-test", gemini.NO_RETRY_OPTIONS))]


def test_capped_gemini_request_through_the_real_sdk_is_one_capped_request() -> None:
    """The real SDK accepts the capped config: maxOutputTokens is sent, automatic
    continuation is applied client-side (not sent), and one request is made."""
    client = REAL_MAKE_CLIENT("fake-key-not-used", gemini.NO_RETRY_OPTIONS)
    seen: list[dict[str, Any]] = []

    class Sent(Exception):
        pass

    def capture(method: str, path: str, body: dict[str, Any], http_options: Any = None) -> Any:
        seen.append(body)
        raise Sent()

    client._api_client.request = capture
    req = gemini.build_request("Be Riley.", parse_transcript(CASE), "gemini-3.5-flash", "MINIMAL", 400)
    with pytest.raises(Sent):
        gemini.generate(client, req)
    assert len(seen) == 1
    assert seen[0]["generationConfig"]["maxOutputTokens"] == 400
    wire = json.dumps(seen[0], default=str)
    assert "automaticContinuation" not in wire and "automatic_continuation" not in wire


# --------------------------------------------------- interruption and the delay


def test_on_start_gets_the_run_id_before_the_first_call(tmp_path: Path) -> None:
    seen: list[str] = []

    def on_slot(rec: dict[str, Any]) -> None:
        assert seen and rec["slot_key"].startswith(seen[0] + "|")

    out = live.run_fresh(cfg_for(tmp_path, RIGHTONCUE_DRY_RUN="1"), *prompt_and_case(), ["gpt-5.4"], 1,
                         on_slot=on_slot, on_start=seen.append)
    assert seen == [out.run_id]


def test_dry_run_delay_leaves_an_open_reservation_during_the_call(tmp_path: Path) -> None:
    import threading
    import time

    cfg = cfg_for(tmp_path, RIGHTONCUE_DRY_RUN="1", RIGHTONCUE_DRY_RUN_DELAY_S="0.6")
    assert cfg.dry_run_delay_s == 0.6
    t = threading.Thread(target=live.run_fresh, args=(cfg, *prompt_and_case(), ["gpt-5.4"], 1))
    t.start()
    led = Ledger(cfg.ledger_path, cfg.budget_nano)  # type: ignore[arg-type]
    open_seen = None
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        if cfg.ledger_path.exists() and cfg.ledger_path.stat().st_size:
            state = led.state()
            if state.open_reservations:
                open_seen = state
                break
        time.sleep(0.02)
    t.join()
    assert open_seen is not None and open_seen.open_reservations == 1
    assert open_seen.spent_nano > 0  # mid-call, the maximum counts
    assert led.state().open_reservations == 0


def test_incomplete_capped_reply_is_an_operational_failure_with_no_judge_call(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    o, _ = fake_factories(
        monkeypatch, [{"text": "Thanks, and", "status": "incomplete", "details": {"reason": "max_output_tokens"}}], []
    )
    out = live.run_fresh(cfg_for(tmp_path), *prompt_and_case(), ["gpt-5.4-mini"], 1)
    rows = entries(tmp_path / "data" / "ledger.jsonl")
    assert [(r["type"], r["kind"]) for r in rows] == [("reserve", "generation"), ("settle", "generation")]
    view = review.load_run_view(out.run_dir, None, None)
    [card] = view.all_cards()
    assert card.state == "incomplete" and card.operational_failure and card.reply is None
    assert len(o.calls) == 1


# ------------------------------------------------------- one judge-only retry

SPEAKER_LABEL_QUOTE = "Applicant: not a turn in this transcript"  # fails judge-v1's quote check


def invalid_judge() -> str:
    """A judge-v1 judgment the quote check rejects: the scorer records it as needs_review."""
    from test_scoring import judge_dict

    d = judge_dict()
    d["listening_context"]["evidence"] = [{"source": "transcript", "quote": SPEAKER_LABEL_QUOTE}]
    return json.dumps(d)


def server_error() -> Exception:
    import httpx2

    req = httpx2.Request("POST", "https://x")
    return openai.InternalServerError("boom", response=httpx2.Response(500, request=req), body=None)


REPLY_WITH_QUOTE = "Thanks. Are your BLS and ACLS both current?"  # holds test_scoring.QUOTE


def score_rows(tmp_path: Path, run_id: str) -> list[dict[str, Any]]:
    return entries(tmp_path / "data" / "scores" / f"{run_id}.jsonl")


def judge_ledger_rows(tmp_path: Path) -> list[tuple[str, str]]:
    return [(e["type"], e["kind"]) for e in entries(tmp_path / "data" / "ledger.jsonl") if e["kind"] == "judge"]


def one_reply_run(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, judge_outputs: list[Any],
                  reply: str = REPLY_WITH_QUOTE) -> tuple[live.FreshOutcome, Any]:
    o, _ = fake_factories(monkeypatch, [reply, *judge_outputs], [])
    out = live.run_fresh(cfg_for(tmp_path), *prompt_and_case(), ["gpt-5.4-mini"], 1)
    return out, o


def test_needs_review_gets_one_judge_only_retry_with_the_saved_reply(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    out, o = one_reply_run(tmp_path, monkeypatch, [invalid_judge(), judge()])
    assert out.messages == []
    assert len(o.calls) == 3  # one generation, two judge calls; no second generation
    first, retry = o.calls[1], o.calls[2]
    assert first == retry  # the same judge request: the exact saved reply, the same transcript
    rows = score_rows(tmp_path, out.run_id)
    assert [r["status"] for r in rows] == ["needs_review", "scored"]  # both attempts kept
    assert rows[0]["slot_key"] == rows[1]["slot_key"] and rows[0]["text_sha256"] == rows[1]["text_sha256"]
    assert judge_ledger_rows(tmp_path) == [("reserve", "judge"), ("settle", "judge")] * 2
    [card] = review.load_run_view(out.run_dir, tmp_path / "data" / "scores" / f"{out.run_id}.jsonl", "judge-v1").all_cards()
    assert (card.decision, card.total, card.failed_judge_attempts) == ("acceptable", 8, 1)


def test_judge_failed_is_retried_once(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    out, o = one_reply_run(tmp_path, monkeypatch, [server_error(), judge()])
    assert [r["status"] for r in score_rows(tmp_path, out.run_id)] == ["judge_failed", "scored"]
    assert len(o.calls) == 3 and out.messages == []


def test_a_valid_rejection_is_final(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    out, o = one_reply_run(tmp_path, monkeypatch, [judge(next_action=1), "never sent"])
    assert len(o.calls) == 2  # no retry for a valid "not acceptable"
    rows = score_rows(tmp_path, out.run_id)
    assert [r["status"] for r in rows] == ["scored"] and rows[0]["decision"]["acceptable"] is False
    assert judge_ledger_rows(tmp_path) == [("reserve", "judge"), ("settle", "judge")]


def test_two_invalid_judgments_stop_after_the_retry(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    out, o = one_reply_run(tmp_path, monkeypatch, [invalid_judge(), invalid_judge(), "never sent"])
    assert len(o.calls) == 3  # never a third judge call
    assert [r["status"] for r in score_rows(tmp_path, out.run_id)] == ["needs_review", "needs_review"]
    [card] = review.load_run_view(out.run_dir, tmp_path / "data" / "scores" / f"{out.run_id}.jsonl", "judge-v1").all_cards()
    assert (card.decision, card.total, card.failed_judge_attempts) == ("needs review", None, 2)


def test_a_fatal_judge_error_is_not_retried(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import httpx2

    req = httpx2.Request("POST", "https://x")
    fatal = openai.AuthenticationError("bad key", response=httpx2.Response(401, request=req), body=None)
    out, o = one_reply_run(tmp_path, monkeypatch, [fatal, "never sent"])
    assert len(o.calls) == 2
    assert out.messages == [
        "Scoring stopped after a fatal judge error (AuthenticationError, HTTP 401); no further judge calls were made."
    ]


def test_retry_is_refused_by_the_cap_before_any_request(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    real_retry = live.retry_invalid_judgments
    monkeypatch.setattr(live, "retry_invalid_judgments", lambda *a, **k: None)  # leave one failed attempt
    out, o = one_reply_run(tmp_path, monkeypatch, [invalid_judge()])
    assert [r["status"] for r in score_rows(tmp_path, out.run_id)] == ["needs_review"]
    cfg = cfg_for(tmp_path)
    led = live.open_ledger(cfg)
    room = led.remaining()
    filler = led.reserve("judge", "gpt-5.4-mini", room - 1)  # another reviewer's spend
    led.settle(filler, "judge", "gpt-5.4-mini", room - 1, "usage")
    late = FakeClient(["never sent"])
    late.max_retries = 0
    _, guarded_judge = ledger.guard_clients({}, late, led)
    rows_before = score_rows(tmp_path, out.run_id)
    with pytest.raises(BudgetExceeded):
        real_retry(cfg, out.run_dir, guarded_judge)
    assert late.calls == []
    assert score_rows(tmp_path, out.run_id) == rows_before
    assert led.state().open_reservations == 0


def test_a_budget_refusal_of_the_retry_is_reported_not_raised(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def refuse(*a: Any, **k: Any) -> Any:
        raise BudgetExceeded("budget reached: the remaining allowance can't cover this call")

    monkeypatch.setattr(live, "retry_invalid_judgments", refuse)
    out, _ = one_reply_run(tmp_path, monkeypatch, [invalid_judge()])
    assert out.messages == [
        "The judge retry stopped: budget reached: the remaining allowance can't cover this call. "
        "A judgment that needs review is shown without a valid score."
    ]
    assert live.run_lock().acquire(blocking=False)
    live.run_lock().release()


def test_retry_refuses_a_reply_never_judged_or_already_retried(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    out, _ = one_reply_run(tmp_path, monkeypatch, [invalid_judge(), invalid_judge()])
    cfg = cfg_for(tmp_path)
    untouched = FakeClient(["never sent"])
    with pytest.raises(RuntimeError, match="2 failed judge attempt"):
        live.retry_invalid_judgments(cfg, out.run_dir, untouched)
    (tmp_path / "data" / "scores" / f"{out.run_id}.jsonl").unlink()  # as if never scored
    with pytest.raises(RuntimeError, match="0 failed judge attempt"):
        live.retry_invalid_judgments(cfg, out.run_dir, untouched)
    assert untouched.calls == []


def test_no_retry_needed_returns_none(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    out, _ = one_reply_run(tmp_path, monkeypatch, [judge()])
    assert live.retry_invalid_judgments(cfg_for(tmp_path), out.run_dir, FakeClient([])) is None
