"""app.py hosted live mode through streamlit.testing. Offline: fake or dry-run clients.

All usage and amounts below are SYNTHETIC TEST DATA.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import openai
import pytest
from streamlit.testing.v1 import AppTest
from test_app import badges, body
from test_gemini import FakeGeminiClient
from test_run import FakeClient
from test_scoring import judge

from rightoncue import gemini, live, review
from rightoncue.ledger import Ledger

REPO = Path(__file__).parent.parent
APP = str(REPO / "app.py")
CODE = "correct horse battery"
LIVE_ENV = (
    "RIGHTONCUE_HOSTED", "RIGHTONCUE_ACCESS_CODE", "RIGHTONCUE_BUDGET_USD", "RIGHTONCUE_DATA_DIR",
    "RIGHTONCUE_MAX_SAMPLES", "RIGHTONCUE_DRY_RUN", "RIGHTONCUE_DRY_RUN_DELAY_S",
)


def boom(*a: Any, **k: Any) -> Any:
    raise AssertionError("a real client must not be built in an offline test")


@pytest.fixture(autouse=True)
def offline(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(REPO)
    for name in LIVE_ENV + ("OPENAI_API_KEY", "GEMINI_API_KEY"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(review, "load_env", lambda: None)
    monkeypatch.setattr(review, "CLIENT_FACTORIES", {"openai": boom, "gemini": boom})
    monkeypatch.setattr(live, "GENERATION_FACTORIES", {"openai": boom, "gemini": boom})
    monkeypatch.setattr(openai, "OpenAI", boom)
    monkeypatch.setattr(gemini, "make_client", boom)
    live.reset_gate()
    live._logged.clear()


def hosted_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, **extra: str) -> Path:
    data = tmp_path / "data"
    env = {"RIGHTONCUE_HOSTED": "1", "RIGHTONCUE_ACCESS_CODE": CODE, "RIGHTONCUE_BUDGET_USD": "5.00",
           "RIGHTONCUE_DATA_DIR": str(data), "OPENAI_API_KEY": "sk-fake-value-1",
           "GEMINI_API_KEY": "gm-fake-value-2", **extra}
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    return data


def run() -> AppTest:
    return AppTest.from_file(APP, default_timeout=60).run()


def everything(at: AppTest) -> str:
    """Every rendered string we can reach: html, markdown, alerts, captions, labels."""
    parts = [body(at)]
    for group in (at.info, at.error, at.warning, at.caption, at.success):
        parts += [e.value for e in group]
    parts += [str(w.value) for w in at.text_input] + [str(w.value) for w in at.text_area]
    return "\n".join(parts)


def saved_comparison_ok(at: AppTest) -> None:
    assert not at.exception
    assert len(badges(at, "judge-v1:")) == 3
    assert [m.value for m in at.metric] == ["31 of 47", "2 of 12"]


def unlock(at: AppTest, code: str = CODE) -> AppTest:
    at.text_input[0].input(code)
    return next(b for b in at.button if b.label == "Unlock").click().run()


# ---------------------------------------------------------------- unavailable


@pytest.mark.parametrize("missing", ["RIGHTONCUE_ACCESS_CODE", "RIGHTONCUE_BUDGET_USD", "RIGHTONCUE_DATA_DIR", "GEMINI_API_KEY"])
def test_hosted_live_unavailable_without_a_requirement(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture, missing: str
) -> None:
    hosted_env(monkeypatch, tmp_path)
    monkeypatch.delenv(missing)
    caplog.set_level(logging.WARNING, logger="rightoncue.live")
    at = run()
    saved_comparison_ok(at)
    assert any("not available in this hosted replay" in i.value for i in at.info)
    assert not at.text_input and not at.multiselect
    page = everything(at)
    assert missing not in page and "RIGHTONCUE" not in page
    assert missing in caplog.text  # the specifics are in the server log
    assert CODE not in caplog.text and "sk-fake-value-1" not in caplog.text
    assert not (tmp_path / "data").exists()


@pytest.mark.parametrize("value", ["abc", "-1", "0"])
def test_invalid_budget_keeps_the_saved_comparison(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture, value: str
) -> None:
    hosted_env(monkeypatch, tmp_path, RIGHTONCUE_BUDGET_USD=value)
    caplog.set_level(logging.WARNING, logger="rightoncue.live")
    at = run()
    saved_comparison_ok(at)
    assert [e.value for e in at.error] == [
        "Live runs are unavailable: this server's live-mode configuration is invalid. "
        "The saved comparison is unaffected."
    ]
    assert "RIGHTONCUE_BUDGET_USD" in caplog.text and "RIGHTONCUE_BUDGET_USD" not in everything(at)


def test_corrupt_ledger_keeps_the_saved_comparison(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    data = hosted_env(monkeypatch, tmp_path)
    data.mkdir()
    (data / "ledger.jsonl").write_bytes(b"garbage\n{}\n")
    at = run()
    saved_comparison_ok(at)
    assert any("spending records can't be read or written" in e.value for e in at.error)
    assert not at.text_input


def test_unwritable_data_dir_keeps_the_saved_comparison(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    blocker = tmp_path / "not-a-dir"
    blocker.write_text("x")
    hosted_env(monkeypatch, tmp_path, RIGHTONCUE_DATA_DIR=str(blocker))
    at = run()
    saved_comparison_ok(at)
    assert any("spending records can't be read or written" in e.value for e in at.error)


def test_exhausted_budget_keeps_the_saved_comparison(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    data = hosted_env(monkeypatch, tmp_path, RIGHTONCUE_BUDGET_USD="0.001")
    led = Ledger(data / "ledger.jsonl", 1_000_000)
    led.settle(led.reserve("judge", "gpt-5.4-mini", 1_000_000), "judge", "gpt-5.4-mini", 1_000_000, "usage")
    at = run()
    saved_comparison_ok(at)
    assert any("budget exhausted" in e.value for e in at.error)
    assert not at.text_input  # no gate either
    assert "$" not in everything(at).split("Live runs")[-1]  # no exact dollars before unlocking


# ----------------------------------------------------------------------- gate


def test_gate_locked_shows_only_the_code_field(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    hosted_env(monkeypatch, tmp_path)
    at = run()
    saved_comparison_ok(at)
    assert [w.label for w in at.text_input] == ["Access code"]
    assert at.text_input[0].proto.type == at.text_input[0].proto.PASSWORD
    assert "Live runs: budget available." in [c.value for c in at.caption]
    assert not at.multiselect and not [b for b in at.button if b.key == "hl_run"]
    assert "$" not in everything(at).split("Live runs: budget available.")[-1]


def test_wrong_then_right_code_and_the_code_never_leaks(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    hosted_env(monkeypatch, tmp_path)
    caplog.set_level(logging.DEBUG)
    at = run()
    at = unlock(at, "wrong guess")
    assert "That code is not right." in [e.value for e in at.error]
    assert not at.multiselect
    at = unlock(at, CODE)
    assert not at.exception
    assert at.multiselect(key="hl_models")
    assert not [w for w in at.text_input if w.label == "Access code"]
    state = {k: at.session_state[k] for k in at.session_state}
    leaked = [CODE, "wrong guess"]
    for secret in leaked:
        assert secret not in everything(at)
        assert secret not in repr(state)
        assert secret not in caplog.text
        assert all(secret not in str(v) for v in at.query_params.values())
    assert state.get("hl_unlocked") is True


def test_five_wrong_codes_start_a_process_wide_cooldown(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    hosted_env(monkeypatch, tmp_path)
    now = [500.0]
    monkeypatch.setattr(live, "clock", lambda: now[0])
    at = run()
    for _ in range(5):
        at = unlock(at, "nope")
    assert any("Too many wrong codes" in w.value for w in at.warning)
    # a reload (a new session) is still in the cooldown, and the right code can't be sent
    other = run()
    assert any("Too many wrong codes. Try again in 60 seconds." in w.value for w in other.warning)
    assert next(b for b in other.button if b.label == "Unlock").disabled
    now[0] += live.COOLDOWN_S + 1
    other = unlock(run(), CODE)
    assert other.multiselect(key="hl_models")


# --------------------------------------------------------------- the full flow


def committed_snapshot() -> dict[str, int]:
    return {p.relative_to(REPO).as_posix(): p.stat().st_mtime_ns
            for d in ("runs", "scores") for p in (REPO / d).rglob("*") if p.is_file()}


def test_full_hosted_flow_with_fake_clients(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    data = hosted_env(monkeypatch, tmp_path)
    o = FakeClient(["Thanks for that. What drew you to nights?", judge(), judge()])
    o.max_retries = 0
    g = FakeGeminiClient(["Got it. How long have you been in the ICU?"])
    monkeypatch.setattr(live, "GENERATION_FACTORIES", {"openai": lambda: o, "gemini": lambda: g})
    before = committed_snapshot()

    at = unlock(run())
    assert at.selectbox(key="hl_prompt_src").options == ["prompts/v1.md", "prompts/v2.md"]
    at.selectbox(key="hl_prompt_src").set_value("prompts/v2.md")
    at.selectbox(key="hl_case_src").set_value("holdout/H3.jsonl")
    at.multiselect(key="hl_models").set_value(["gpt-5.4-mini", "gemini-3.5-flash"])
    at.number_input(key="hl_samples").set_value(1)
    at.run()
    assert at.number_input(key="hl_samples").max == 2
    proj = [i.value for i in at.info if "Projected maximum cost" in i.value]
    assert len(proj) == 1 and "2 generation call(s) and up to 2 judge call(s)" in proj[0]
    assert at.button(key="hl_run").disabled  # not confirmed yet
    at.checkbox(key="hl_confirm_0").set_value(True).run()
    saved_badges = len(badges(at, "judge-v1: acceptable · 8/8"))
    at.button(key="hl_run").click().run()
    assert not at.exception, at.exception

    fresh = [i.value for i in at.info if i.value.startswith("Fresh run: generated just now, not part of the saved evaluation · run ")]
    assert len(fresh) == 1
    run_id = fresh[0].rsplit(" ", 1)[-1]
    text = body(at)
    assert "Thanks for that. What drew you to nights?" in text and "Got it. How long have you been in the ICU?" in text
    assert len(badges(at, "judge-v1: acceptable · 8/8")) == saved_badges + 2
    assert any(b.startswith(":blue-badge[Saved example · run ") for b in badges(at, "Saved example"))
    # files: the tmp data dir only
    assert (data / "runs" / run_id / "manifest.json").is_file()
    assert (data / "scores" / f"{run_id}.jsonl").is_file()
    rows = [json.loads(x) for x in (data / "ledger.jsonl").read_text(encoding="utf-8").splitlines()]
    assert [r["type"] for r in rows] == ["reserve", "settle"] * 4
    manifest = json.loads((data / "runs" / run_id / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["prompt"]["path"] == "prompts/v2.md" and manifest["cases"][0]["case_id"] == "H3"
    assert committed_snapshot() == before
    # a repeat needs a fresh confirmation
    assert at.checkbox(key="hl_confirm_1").value is False and at.button(key="hl_run").disabled


def test_edited_prompt_is_recorded_as_pasted(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    data = hosted_env(monkeypatch, tmp_path, RIGHTONCUE_DRY_RUN="1")
    at = unlock(run())
    at.text_area(key="hl_prompt_text_prompts/v1.md").set_value("You are Riley. Ask one question.")
    at.run()
    at.checkbox(key="hl_confirm_0").set_value(True).run()
    at.button(key="hl_run").click().run()
    assert not at.exception
    [run_dir] = list((data / "runs").iterdir())
    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["prompt"]["path"] == "pasted/prompt.md"
    assert manifest["prompt"]["text"] == "You are Riley. Ask one question."


def test_projection_over_remaining_budget_refuses_up_front(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    hosted_env(monkeypatch, tmp_path, RIGHTONCUE_BUDGET_USD="0.02", RIGHTONCUE_DRY_RUN="1")
    at = unlock(run())
    at.multiselect(key="hl_models").set_value(["gpt-5.4", "gpt-5.4-mini", "gemini-3.5-flash"])
    at.number_input(key="hl_samples").set_value(2)
    at.checkbox(key="hl_confirm_0").set_value(True).run()
    assert any("more than the remaining budget" in e.value for e in at.error)
    assert at.button(key="hl_run").disabled


def test_another_run_in_progress(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    hosted_env(monkeypatch, tmp_path, RIGHTONCUE_DRY_RUN="1")
    at = unlock(run())
    at.checkbox(key="hl_confirm_0").set_value(True).run()
    lock = live.run_lock()
    assert lock.acquire(blocking=False)
    try:
        at.button(key="hl_run").click().run()
    finally:
        lock.release()
    assert "Another run is in progress, try again shortly." in [w.value for w in at.warning]


# ---------------------------------------------------------------------- dry run


def test_dry_run_banner_and_flow_never_build_real_clients(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    data = hosted_env(monkeypatch, tmp_path, RIGHTONCUE_DRY_RUN="1")  # real-looking keys are set
    banner = "Dry run: no model was called; replies and scores are placeholders."
    at = run()
    assert at.warning[0].value == banner
    at = unlock(at)
    assert any(c.value.startswith("Simulated spend (dry run): $0.000000 of the $5.000000 cap.") for c in at.caption)
    at.checkbox(key="hl_confirm_0").set_value(True).run()
    at.button(key="hl_run").click().run()
    assert not at.exception, at.exception
    assert at.warning[0].value == banner
    assert "Dry run placeholder: no model was called." in body(at)
    assert not (data / "ledger.jsonl").exists()
    assert (data / "ledger.dry-run.jsonl").stat().st_size > 0
    assert any(c.value.startswith("Simulated spend (dry run): $0.00") and "$0.000000 of" not in c.value for c in at.caption)


def test_no_banner_without_dry_run() -> None:
    at = run()
    assert not [w for w in at.warning if w.value.startswith("Dry run")]


# ------------------------------------------------------------- local, budgeted


def committed_listing() -> dict[str, tuple[int, int]]:
    """Every file under the committed runs/ and scores/: (size, mtime)."""
    return {
        p.relative_to(REPO).as_posix(): (p.stat().st_size, p.stat().st_mtime_ns)
        for d in ("runs", "scores") for p in (REPO / d).rglob("*")
    } | {d: (0, 0) for d in ("runs", "scores")}


def local_guarded_generate_and_score(at: AppTest, data: Path) -> str:
    """Generate one reply, score it; return the run ID. review.RUNS_DIR / SCORES_DIR are
    deliberately NOT replaced: the committed folders must stay untouched on their own."""
    at.number_input(key="live_samples").set_value(1)
    at.checkbox(key="live_confirm_gen_0").set_value(True).run()
    assert any("each capped at 400 output tokens" in i.value and "Projected maximum cost" in i.value for i in at.info)
    at.button(key="live_generate").click().run()
    assert not at.exception, at.exception
    [run_dir] = list((data / "runs").iterdir())
    assert any(c.value == f"Saved to {run_dir.as_posix()}; scores go to "
               f"{(data / 'scores' / (run_dir.name + '.jsonl')).as_posix()}." for c in at.caption)
    at.checkbox(key="live_confirm_score_1").set_value(True).run()
    at.button(key="live_score").click().run()
    assert not at.exception, at.exception
    assert (data / "scores" / f"{run_dir.name}.jsonl").is_file()
    assert (run_dir / "manifest.json").is_file() and (run_dir / "slots.jsonl").is_file()
    return run_dir.name


def test_local_budgeted_run_writes_only_to_the_data_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    data = tmp_path / "data"
    monkeypatch.setenv("RIGHTONCUE_BUDGET_USD", "1")
    monkeypatch.setenv("RIGHTONCUE_DATA_DIR", str(data))
    monkeypatch.setenv("OPENAI_API_KEY", "fake")
    o = FakeClient(["A short reply.", judge()])
    o.max_retries = 0
    monkeypatch.setattr(live, "GENERATION_FACTORIES", {"openai": lambda: o, "gemini": boom})
    before = committed_listing()
    run_id = local_guarded_generate_and_score(AppTest.from_file(APP, default_timeout=60).run(), data)
    assert committed_listing() == before
    assert not (REPO / "runs" / run_id).exists() and not (REPO / "scores" / f"{run_id}.jsonl").exists()
    assert o.calls[0]["max_output_tokens"] == 400 and len(o.calls) == 2
    rows = [json.loads(x) for x in (data / "ledger.jsonl").read_text().splitlines()]
    assert [(r["type"], r["kind"]) for r in rows] == [
        ("reserve", "generation"), ("settle", "generation"), ("reserve", "judge"), ("settle", "judge")
    ]


def test_local_dry_run_writes_only_to_the_data_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    data = tmp_path / "data"
    monkeypatch.setenv("RIGHTONCUE_DRY_RUN", "1")
    monkeypatch.setenv("RIGHTONCUE_BUDGET_USD", "1")
    monkeypatch.setenv("RIGHTONCUE_DATA_DIR", str(data))
    before = committed_listing()
    at = AppTest.from_file(APP, default_timeout=60).run()
    assert at.warning[0].value.startswith("Dry run: no model was called")
    run_id = local_guarded_generate_and_score(at, data)
    assert committed_listing() == before
    assert not (REPO / "runs" / run_id).exists() and not (REPO / "scores" / f"{run_id}.jsonl").exists()
    assert "Dry run placeholder: no model was called." in body(at)
    assert not (data / "ledger.jsonl").exists() and (data / "ledger.dry-run.jsonl").is_file()


def test_local_mode_without_a_budget_writes_no_ledger(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(live, "DEFAULT_LOCAL_DATA_DIR", tmp_path / "data")
    at = run()
    assert not at.exception
    assert not (tmp_path / "data").exists()


# ------------------------------------------------------------- leak surfaces


def test_unclassified_provider_error_shows_a_generic_message(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    import httpx2

    hosted_env(monkeypatch, tmp_path)
    req = httpx2.Request("POST", "https://x")
    err = openai.ConflictError("conflict detail sk-proj-****wxyz", response=httpx2.Response(409, request=req), body=None)
    o = FakeClient([err])
    o.max_retries = 0
    monkeypatch.setattr(live, "GENERATION_FACTORIES", {"openai": lambda: o, "gemini": boom})
    caplog.set_level(logging.ERROR, logger="rightoncue.live")
    at = unlock(run())
    at.checkbox(key="hl_confirm_0").set_value(True).run()
    at.button(key="hl_run").click().run()
    assert not at.exception
    assert any(e.value.startswith("The run stopped on an unexpected error.") for e in at.error)
    assert "wxyz" not in everything(at) and "conflict detail" not in everything(at)
    assert "ConflictError" in caplog.text
    rows = [json.loads(x) for x in (tmp_path / "data" / "ledger.jsonl").read_text().splitlines()]
    assert rows[-1]["basis"] == "maximum_raised"  # the call is counted at its maximum
    assert live.run_lock().acquire(blocking=False)
    live.run_lock().release()


def test_local_env_file_is_read_before_the_live_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A RIGHTONCUE_* value kept in .env applies on the first script run too."""
    def fake_load_env() -> None:
        import os

        os.environ.setdefault("RIGHTONCUE_BUDGET_USD", "1")
        os.environ.setdefault("RIGHTONCUE_DATA_DIR", str(tmp_path / "data"))

    monkeypatch.setattr(review, "load_env", fake_load_env)
    monkeypatch.setenv("RIGHTONCUE_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.delenv("RIGHTONCUE_BUDGET_USD", raising=False)
    try:
        at = run()
        assert not at.exception
        assert any(c.value.startswith("Spend: $0.000000 of the $1.000000 cap.") for c in at.caption)
    finally:
        import os

        os.environ.pop("RIGHTONCUE_BUDGET_USD", None)


def test_hosted_mode_never_reads_the_env_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    hosted_env(monkeypatch, tmp_path)
    monkeypatch.setattr(review, "load_env", boom)
    at = run()
    assert not at.exception and [w.label for w in at.text_input] == ["Access code"]


def test_sdk_validation_error_is_not_shown_on_the_public_page(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """A pydantic ValidationError is a ValueError; only our RunInputError text is shown."""
    import pydantic

    try:
        pydantic.TypeAdapter(int).validate_python("secret-response-body")
    except pydantic.ValidationError as exc:
        err = exc
    hosted_env(monkeypatch, tmp_path)
    o = FakeClient([err])
    o.max_retries = 0
    monkeypatch.setattr(live, "GENERATION_FACTORIES", {"openai": lambda: o, "gemini": boom})
    caplog.set_level(logging.ERROR, logger="rightoncue.live")
    at = unlock(run())
    at.checkbox(key="hl_confirm_0").set_value(True).run()
    at.button(key="hl_run").click().run()
    assert not at.exception
    assert any(e.value.startswith("The run stopped on an unexpected error.") for e in at.error)
    assert "secret-response-body" not in everything(at)
    assert "ValidationError" in caplog.text


def test_our_own_input_errors_are_shown(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    hosted_env(monkeypatch, tmp_path, RIGHTONCUE_DRY_RUN="1")
    real = live.run_fresh

    def run_fresh_with_three_samples(cfg: Any, prompt: Any, case: Any, models: Any, samples: Any, **kw: Any) -> Any:
        return real(cfg, prompt, case, models, 3, **kw)  # past the hosted limit of 2

    monkeypatch.setattr(live, "run_fresh", run_fresh_with_three_samples)
    at = unlock(run())
    at.checkbox(key="hl_confirm_0").set_value(True).run()
    at.button(key="hl_run").click().run()
    assert "Samples must be from 1 to 2." in [e.value for e in at.error]
