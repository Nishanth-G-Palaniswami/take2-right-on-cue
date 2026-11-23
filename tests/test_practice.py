"""Talk to Riley (practice call): rightoncue.practice and its app view. Offline only.

Fake or dry-run clients; real client constructors raise if touched. All usage and
amounts below are SYNTHETIC TEST DATA.
"""

from __future__ import annotations

import json
import os
import threading
from pathlib import Path
from typing import Any

import httpx2
import openai
import pytest
from streamlit.testing.v1 import AppTest
from test_app import badges
from test_app_live import APP, LIVE_ENV, REPO, boom, committed_snapshot, everything, hosted_env, run, unlock
from test_live import invalid_judge, server_error
from test_run import FakeClient
from test_scoring import judge

from rightoncue import gemini, live, practice, review
from rightoncue.ledger import BudgetExceeded, Ledger
from rightoncue.transcript import Turn

MODE_PRACTICE = "Talk to Riley (practice call)"
UNEXPECTED = "The run stopped on an unexpected error."
UNCERTAIN = (
    "Riley's reply didn't arrive. The request may still have been processed and charged "
    "(the cap counted its maximum). Retry sends the conversation again and may be charged again."
)
OVER_BUDGET = "The remaining budget can't cover another reply. The conversation stays here."
FICTIONAL = "Use fictional details. Your typed conversation is saved on the server."
NEEDS_BUDGET = (
    "Talk to Riley (practice call) needs RIGHTONCUE_BUDGET_USD, so practice replies go to "
    "the data folder behind the spending cap, never to the committed runs/."
)
OPENING_NOT_EVALUABLE = "The scripted opening (turn 1) was not generated, so it can't be evaluated."
CACHED = " Cached: this reply was already scored, so no new judge call was made."


@pytest.fixture(autouse=True)
def offline(monkeypatch: pytest.MonkeyPatch) -> Any:
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
    yield
    assert not live.run_lock().locked(), "a test left the run lock held"


def fake(monkeypatch: pytest.MonkeyPatch, outputs: list[Any]) -> FakeClient:
    o = FakeClient(outputs)
    o.max_retries = 0
    monkeypatch.setattr(live, "GENERATION_FACTORIES", {"openai": lambda: o, "gemini": boom})
    return o


class BlockingClient(FakeClient):
    """Holds each call until released, so two requests overlap deterministically."""

    def __init__(self, outputs: list[Any]) -> None:
        super().__init__(outputs)
        self.max_retries = 0
        self.entered = threading.Event()
        self.release = threading.Event()

    def _create(self, **kwargs: Any) -> Any:
        self.entered.set()
        assert self.release.wait(20)
        return super()._create(**kwargs)


def cfg_now() -> live.LiveConfig:
    return live.load_config(os.environ)


def opening() -> list[Turn]:
    return [Turn(role="agent", utterance=practice.OPENING)]


def user(text: str) -> Turn:
    return Turn(role="user", utterance=text)


def agent(text: str) -> Turn:
    return Turn(role="agent", utterance=text)


def ledger_rows(data: Path, name: str = "ledger.jsonl") -> list[dict[str, Any]]:
    return [json.loads(x) for x in (data / name).read_text(encoding="utf-8").splitlines() if x]


def spend_down_to(data: Path, cfg: live.LiveConfig, target_remaining: int) -> None:
    """Another reviewer's settled spend, leaving exactly `target_remaining`."""
    led = live.open_ledger(cfg)
    filler = led.remaining() - target_remaining
    assert filler >= 0
    rid = led.reserve("judge", "gpt-5.4-mini", filler)
    led.settle(rid, "judge", "gpt-5.4-mini", filler, "usage")
    assert led.remaining() == target_remaining


def no_unexpected(at: AppTest) -> None:
    assert not at.exception, at.exception
    assert not [e for e in at.error if e.value.startswith(UNEXPECTED)]


def to_practice(at: AppTest) -> AppTest:
    at.radio(key="pc_mode").set_value(MODE_PRACTICE).run()
    no_unexpected(at)
    if [c for c in at.checkbox if c.key == "pc_ack"]:
        at.checkbox(key="pc_ack").set_value(True).run()
    at.button(key="pc_start").click().run()
    no_unexpected(at)
    return at


def hosted_practice(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, **extra: str) -> tuple[AppTest, Path]:
    data = hosted_env(monkeypatch, tmp_path, **extra)
    return to_practice(unlock(run())), data


def form_n(at: AppTest) -> int:
    return at.session_state["pc_n"]


def send_button(at: AppTest) -> Any:
    return next(b for b in at.button if b.label == "Send")


def has_send(at: AppTest) -> bool:
    return any(b.label == "Send" for b in at.button)


def say(at: AppTest, text: str) -> AppTest:
    at.text_area(key=f"pc_msg_{form_n(at)}").input(text)
    send_button(at).click().run()
    no_unexpected(at)
    return at


def turns(at: AppTest) -> list[tuple[str, str]]:
    return [(t["role"], t["utterance"]) for t in at.session_state["pc_turns"]]


def keys(at: AppTest) -> set[str]:
    return {b.key for b in at.button if b.key}


# ------------------------------------------------------------- 1. turn order


def test_second_request_holds_the_conversation_in_order(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    o = fake(monkeypatch, ["Thanks, Alex. Is now still a good time?", "Great. What drew you to the ICU?"])
    at, data = hosted_practice(monkeypatch, tmp_path)
    say(at, "Hi Riley, yes, now works.")
    say(at, "I have five years in a cardiac ICU.")
    assert len(o.calls) == 2
    second = o.calls[1]
    assert second["input"] == [
        {"role": "assistant", "content": practice.OPENING},
        {"role": "user", "content": "Hi Riley, yes, now works."},
        {"role": "assistant", "content": "Thanks, Alex. Is now still a good time?"},
        {"role": "user", "content": "I have five years in a cardiac ICU."},
    ]
    assert second["instructions"] == (REPO / "prompts" / "v3.md").read_text(encoding="utf-8").lstrip("﻿")
    assert second["model"] == "gpt-5.4" and second["reasoning"] == {"effort": "none"}
    assert second["max_output_tokens"] == 400
    run_ids = [t["run_id"] for t in at.session_state["pc_turns"] if t["run_id"]]
    assert len(run_ids) == 2
    manifest = json.loads((data / "runs" / run_ids[1] / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["cases"][0]["path"] == "practice/conversation.jsonl"
    assert manifest["prompt"]["path"] == "prompts/v3.md"
    text = everything(at)
    assert "Scripted opening · written in advance, not generated" in text
    assert f"Riley · GPT-5.4 · run {run_ids[1]}" in text and "You, as Alex" in text


# ------------------------------------------------------------- 2. no leakage


def test_evaluation_sees_only_the_turns_before_the_reply(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    hosted_env(monkeypatch, tmp_path)
    o = fake(monkeypatch, ["Reply one: is now a good time?", "Reply two: how long on nights?", judge(), judge()])
    cfg = cfg_now()
    t1 = [*opening(), user("Message one, yes.")]
    r1 = practice.send(cfg, t1)
    t2 = [*t1, agent(r1.text or ""), user("Message two, three years.")]
    r2 = practice.send(cfg, t2)
    assert practice.evaluate(cfg, r1.run_id).calls == 1
    seen1 = o.calls[2]["input"][0]["content"]
    assert practice.OPENING in seen1 and "Message one, yes." in seen1 and "Reply one: is now a good time?" in seen1
    assert "Message two" not in seen1 and "Reply two" not in seen1
    assert practice.evaluate(cfg, r2.run_id).calls == 1
    seen2 = o.calls[3]["input"][0]["content"]
    for part in (practice.OPENING, "Message one, yes.", "Reply one: is now a good time?",
                 "Message two, three years.", "Reply two: how long on nights?"):
        assert part in seen2


def test_the_judge_context_expander_lists_the_runs_own_turns(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fake(monkeypatch, ["Reply one?", "Reply two?", judge()])
    at, _ = hosted_practice(monkeypatch, tmp_path)
    say(at, "Message one.")
    say(at, "Message two.")
    at.selectbox(key="pc_eval_pick").set_value("Turn 3: Reply one?").run()
    at.button(key="pc_eval").click().run()
    no_unexpected(at)
    [exp] = [e for e in at.expander if e.label.startswith("What the judge saw")]
    assert exp.label == "What the judge saw (the 2 turns before this reply)"
    inside = "\n".join(h.proto.body for h in exp.get("html"))
    assert "Message one." in inside and "Message two." not in inside and "Reply two?" not in inside
    assert any(c.value == "Scored by judge-v1 against only the 2 turns before this reply. No case criteria: "
               "the general rubric." for c in at.caption)


# -------------------------------------------------- 3. the budget mid-conversation


def test_budget_that_covers_one_reply_but_not_two(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    o = fake(monkeypatch, ["Thanks. What drew you to the ICU?", "never sent"])
    at, data = hosted_practice(monkeypatch, tmp_path)
    say(at, "Hello, yes.")
    cfg = cfg_now()
    now = practice.turns_of(at.session_state)
    # less than even the cheapest one-character message costs
    spend_down_to(data, cfg, practice.reply_max_nano([*now, user("A")]) - 1)
    at.run()
    no_unexpected(at)
    assert not has_send(at)
    assert OVER_BUDGET in [e.value for e in at.error]
    before = turns(at)
    with pytest.raises(BudgetExceeded):
        practice.send(cfg, [*now, user("A")])
    assert len(o.calls) == 1
    at.run()
    assert turns(at) == before and at.session_state["pc_pending"] is None


def test_a_short_message_fits_when_the_600_character_maximum_does_not(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    o = fake(monkeypatch, ["Thanks. What drew you to the ICU?"])
    at, data = hosted_practice(monkeypatch, tmp_path)
    cfg = cfg_now()
    smallest = practice.next_reply_max_nano(opening(), 1)
    long_text = "a" * 600
    long_cost = practice.reply_max_nano([*opening(), user(long_text)])
    assert long_cost > smallest
    spend_down_to(data, cfg, smallest + (long_cost - smallest) // 2)
    at.run()
    assert has_send(at)  # the one-character worst case fits
    line = next(c.value for c in at.caption if c.value.startswith("Next reply: up to "))
    assert line.endswith(
        " for a message of up to 600 characters; a shorter message is checked at its actual cost "
        f"when you send. Budget remaining: {review_fmt(live.open_ledger(cfg).remaining())}."
    )
    # the long message is refused before anything is appended; the draft stays
    say(at, long_text)
    remaining = live.open_ledger(cfg).remaining()
    assert (f"This message's maximum cost is {review_fmt(long_cost)}, more than the {review_fmt(remaining)} "
            "left in the budget. Your draft is kept; shorten it or end the call.") in [e.value for e in at.error]
    assert o.calls == [] and turns(at) == [("agent", practice.OPENING)] and form_n(at) == 0
    assert at.text_area(key="pc_msg_0").value == long_text
    # a short one goes through: one call
    say(at, "Yes, now works.")
    assert len(o.calls) == 1
    assert turns(at)[-2:] == [("user", "Yes, now works."), ("agent", "Thanks. What drew you to the ICU?")]
    assert at.text_area(key="pc_msg_1").value == ""  # a fresh form after the append


def review_fmt(nano: int) -> str:
    from rightoncue import budget

    return budget.fmt_usd(nano)


# --------------------------------------------------------------- 4. duplicates


def test_after_send_the_old_form_is_gone_and_reruns_resubmit_nothing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Proves: after a send the counter-keyed form is replaced, and plain reruns and an
    empty submit make no call. AppTest never delivers a click on a widget that is no
    longer in the tree, so this does not prove the browser's stale-click behaviour."""
    o = fake(monkeypatch, ["Thanks. What drew you to the ICU?", "never sent"])
    at, _ = hosted_practice(monkeypatch, tmp_path)
    at.text_area(key="pc_msg_0").input("Yes, now works.")
    stale = send_button(at)
    stale.click().run()
    no_unexpected(at)
    assert len(o.calls) == 1
    assert not [t for t in at.text_area if t.key == "pc_msg_0"]  # the old form is gone
    stale.click()  # the old form's submit: no widget of this run matches it
    at.run()
    at.run()  # plain reruns resubmit nothing
    assert len(o.calls) == 1
    assert turns(at) == [("agent", practice.OPENING), ("user", "Yes, now works."),
                         ("agent", "Thanks. What drew you to the ICU?")]
    send_button(at).click().run()  # an empty submission of the new form
    assert "Type a message first." in [e.value for e in at.error] and len(o.calls) == 1


def test_a_rerun_adopts_a_saved_reply_with_no_new_call(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    o = fake(monkeypatch, ["Thanks. What drew you to the ICU?", "never sent"])
    at, _ = hosted_practice(monkeypatch, tmp_path)
    cfg = cfg_now()
    convo = [*opening(), user("Yes, now works.")]
    saved = practice.send(cfg, convo)  # as if the script was interrupted after the call
    assert len(o.calls) == 1
    at.session_state["pc_turns"] = [
        {"role": "agent", "utterance": practice.OPENING, "run_id": None},
        {"role": "user", "utterance": "Yes, now works.", "run_id": None},
    ]
    at.session_state["pc_pending"] = {"token": "t", "state": "sending", "run_ids": [saved.run_id], "kind": None}
    at.run()
    no_unexpected(at)
    assert len(o.calls) == 1
    assert turns(at)[-1] == ("agent", "Thanks. What drew you to the ICU?")
    assert at.session_state["pc_turns"][-1]["run_id"] == saved.run_id
    assert at.session_state["pc_pending"] is None and has_send(at)
    at.run()
    assert len(turns(at)) == 3  # adopted once


def test_evaluate_twice_makes_one_judge_call_and_shows_the_cached_version(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    o = fake(monkeypatch, ["Thanks. What drew you to the ICU?", judge(), "never sent"])
    at, _ = hosted_practice(monkeypatch, tmp_path)
    say(at, "Yes, now works.")
    at.button(key="pc_eval").click().run()
    no_unexpected(at)
    assert len(o.calls) == 2
    assert "judge-v1: acceptable · 8/8" in " ".join(badges(at, "judge-v1:"))
    assert "Verdict by judge-v1 (scorer-1)." in [c.value for c in at.caption]
    at.button(key="pc_eval").click().run()
    no_unexpected(at)
    assert len(o.calls) == 2  # already scored: no call
    assert f"Verdict by judge-v1 (scorer-1).{CACHED}" in [c.value for c in at.caption]


def test_no_third_judge_attempt(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    o = fake(monkeypatch, ["Thanks. Are your BLS and ACLS both current?", invalid_judge(), invalid_judge(), "never sent"])
    at, _ = hosted_practice(monkeypatch, tmp_path)
    say(at, "Yes, now works.")
    at.button(key="pc_eval").click().run()
    no_unexpected(at)
    assert len(o.calls) == 3  # the reply, the first judgment and its one retry
    assert badges(at, "Needs review · no valid score") == [":orange-badge[Needs review · no valid score]"]
    captions = [c.value for c in at.caption]
    assert "No valid verdict from judge-v1 (scorer-1)." in captions
    assert not [c for c in captions if c.startswith(("Verdict by", "Scored by")) or CACHED.strip() in c]
    assert "The judge saw only the 2 turns before this reply. No case criteria: the general rubric." in captions
    assert "No further judge call is allowed for this reply." in captions
    assert "pc_eval" not in keys(at)  # both attempts used: no button
    rid = at.session_state["pc_turns"][-1]["run_id"]
    assert practice.evaluate(cfg_now(), rid).calls == 0 and len(o.calls) == 3


def test_a_later_evaluation_makes_only_the_one_remaining_attempt(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Entered with one failed attempt on disk (its retry was refused): one call, never a third."""
    hosted_env(monkeypatch, tmp_path)
    o = fake(monkeypatch, ["Thanks. Are your BLS and ACLS both current?", invalid_judge(), judge(), "never sent"])
    cfg = cfg_now()
    rid = practice.send(cfg, [*opening(), user("Yes, now works.")]).run_id

    def refuse(*a: Any, **k: Any) -> Any:
        raise BudgetExceeded("budget reached: no request was made")

    real = live.retry_invalid_judgments
    monkeypatch.setattr(live, "retry_invalid_judgments", refuse)
    first = practice.evaluate(cfg, rid)
    assert first.calls == 1 and first.messages[0].startswith("The judge retry stopped: budget reached")
    monkeypatch.setattr(live, "retry_invalid_judgments", real)
    state = practice.judgment(cfg, rid)
    assert (state.failed_attempts, state.calls_allowed) == (1, 1)
    assert practice.evaluate(cfg, rid).calls == 1
    assert practice.evaluate(cfg, rid).calls == 0
    assert len(o.calls) == 3  # 1 generation + 2 judge calls in total
    assert practice.judgment(cfg, rid).scored


def test_no_evaluation_after_a_fatal_judge_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    hosted_env(monkeypatch, tmp_path)
    fatal = openai.AuthenticationError(
        "bad key", response=httpx2.Response(401, request=httpx2.Request("POST", "https://x")), body=None
    )
    o = fake(monkeypatch, ["Thanks. What drew you to the ICU?", fatal, "never sent"])
    cfg = cfg_now()
    rid = practice.send(cfg, [*opening(), user("Yes, now works.")]).run_id
    first = practice.evaluate(cfg, rid)
    assert first.calls == 1 and first.messages == [
        "Scoring stopped after a fatal judge error (AuthenticationError, HTTP 401); no further judge calls were made."
    ]
    assert practice.evaluate(cfg, rid).calls == 0 and len(o.calls) == 2


def test_judge_timeouts_show_the_uncertain_charge(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    timeout = lambda: openai.APITimeoutError(request=httpx2.Request("POST", "https://x"))  # noqa: E731
    o = fake(monkeypatch, ["Thanks. What drew you to the ICU?", timeout(), timeout(), "never sent"])
    at, _ = hosted_practice(monkeypatch, tmp_path)
    say(at, "Yes, now works.")
    at.button(key="pc_eval").click().run()
    no_unexpected(at)
    assert len(o.calls) == 3  # the first judge call timed out, then its one retry
    assert ("The judge's answer didn't arrive. The request may still have been processed and charged "
            "(the cap counted its maximum). No further judge call is allowed for this reply.") in [w.value for w in at.warning]
    assert not [c for c in at.caption if CACHED.strip() in c.value]


def test_retry_evaluation_after_a_judge_timeout(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    o = fake(monkeypatch, ["Thanks. What drew you to the ICU?",
                           openai.APITimeoutError(request=httpx2.Request("POST", "https://x")), judge(), "never sent"])
    at, _ = hosted_practice(monkeypatch, tmp_path)
    say(at, "Yes, now works.")

    def refuse(*a: Any, **k: Any) -> Any:
        raise BudgetExceeded("budget reached: no request was made")

    real = live.retry_invalid_judgments
    monkeypatch.setattr(live, "retry_invalid_judgments", refuse)
    at.button(key="pc_eval").click().run()
    no_unexpected(at)
    assert len(o.calls) == 2
    assert ("The judge's answer didn't arrive. The request may still have been processed and charged (the cap "
            "counted its maximum). Retry evaluation sends it again and may be charged again.") in [w.value for w in at.warning]
    assert at.button(key="pc_eval").label == "Retry evaluation"
    monkeypatch.setattr(live, "retry_invalid_judgments", real)
    at.button(key="pc_eval").click().run()
    no_unexpected(at)
    assert len(o.calls) == 3 and "Verdict by judge-v1 (scorer-1)." in [c.value for c in at.caption]


def conflict() -> Exception:
    req = httpx2.Request("POST", "https://x")
    return openai.ConflictError("conflict detail sk-proj-****wxyz", response=httpx2.Response(409, request=req), body=None)


def judge_reserves(data: Path) -> int:
    return sum(1 for r in ledger_rows(data) if r["type"] == "reserve" and r["kind"] == "judge")


def test_an_unclassified_judge_error_still_counts_toward_the_cap(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """ConflictError is re-raised by the scorer with no score record; the attempt log
    still caps the reply at JUDGE_ATTEMPTS calls."""
    o = fake(monkeypatch, ["Thanks. What drew you to the ICU?", *[conflict() for _ in range(4)]])
    at, data = hosted_practice(monkeypatch, tmp_path)
    say(at, "Yes, now works.")
    clicks = 0
    while "pc_eval" in keys(at) and clicks < 4:
        at.button(key="pc_eval").click().run()
        no_unexpected(at)
        clicks += 1
    assert clicks == 2 and "pc_eval" not in keys(at)  # no button after the second attempt
    assert len(o.calls) == 3 and judge_reserves(data) == 2  # 1 generation + 2 judge calls
    warnings = [w.value for w in at.warning]
    assert ("The judge's answer didn't arrive. The request may still have been processed and charged "
            "(the cap counted its maximum). No further judge call is allowed for this reply.") in warnings
    assert "wxyz" not in everything(at) and "conflict detail" not in everything(at)
    rid = at.session_state["pc_turns"][-1]["run_id"]
    cfg = cfg_now()
    for _ in range(2):  # direct calls: no attempt left
        assert practice.evaluate(cfg, rid).calls == 0
    assert len(o.calls) == 3 and judge_reserves(data) == 2
    assert practice.judge_attempts_logged(cfg, rid) == 2


def test_the_first_unclassified_error_shows_the_retry_wording(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    o = fake(monkeypatch, ["Thanks. What drew you to the ICU?", conflict(), judge()])
    at, _ = hosted_practice(monkeypatch, tmp_path)
    say(at, "Yes, now works.")
    at.button(key="pc_eval").click().run()
    no_unexpected(at)
    assert ("The judge's answer didn't arrive. The request may still have been processed and charged (the cap "
            "counted its maximum). Retry evaluation sends it again and may be charged again.") in [w.value for w in at.warning]
    assert not [e for e in at.error if e.value.startswith("This stopped on an unexpected error")]
    assert at.button(key="pc_eval").label == "Retry evaluation"
    at.button(key="pc_eval").click().run()
    assert len(o.calls) == 3 and "Verdict by judge-v1 (scorer-1)." in [c.value for c in at.caption]


def test_the_counted_judge_refuses_past_the_cap_before_any_call(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    hosted_env(monkeypatch, tmp_path)
    fake(monkeypatch, ["Thanks. What drew you to the ICU?"])
    cfg = cfg_now()
    rid = practice.send(cfg, [*opening(), user("Yes, now works.")]).run_id
    inner = FakeClient(["a", "b", "never sent"])
    counted = practice._CountedJudge(inner, cfg, rid)
    counted.responses.create(model="m")
    counted.responses.create(model="m")
    with pytest.raises(practice.JudgeAttemptsExhausted):
        counted.responses.create(model="m")
    assert len(inner.calls) == 2 and practice.judge_attempts_logged(cfg, rid) == 2


def test_a_timeout_then_a_valid_verdict_shows_no_charge_warning(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    o = fake(monkeypatch, ["Thanks. What drew you to the ICU?",
                           openai.APITimeoutError(request=httpx2.Request("POST", "https://x")), judge()])
    at, _ = hosted_practice(monkeypatch, tmp_path)
    say(at, "Yes, now works.")
    at.button(key="pc_eval").click().run()
    no_unexpected(at)
    assert len(o.calls) == 3
    assert "Verdict by judge-v1 (scorer-1)." in [c.value for c in at.caption]
    assert not [w for w in at.warning if "didn't arrive" in w.value]


# ---------------------------------------------------------- 5. failure and retry


def test_provider_error_keeps_one_message_and_retry_makes_one_call(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    o = fake(monkeypatch, [server_error(), "Thanks. What drew you to the ICU?", "never sent"])
    at, _ = hosted_practice(monkeypatch, tmp_path)
    say(at, "Yes, now works.")
    assert len(o.calls) == 1
    assert turns(at) == [("agent", practice.OPENING), ("user", "Yes, now works.")]
    assert any(e.value.startswith("Riley's reply failed: a provider error (InternalServerError, HTTP 500).")
               for e in at.error)
    assert "boom" not in everything(at)  # never the provider's text
    assert not has_send(at) and {"pc_retry", "pc_end"} <= keys(at)
    at.button(key="pc_retry").click().run()
    no_unexpected(at)
    assert len(o.calls) == 2
    assert turns(at) == [("agent", practice.OPENING), ("user", "Yes, now works."),
                         ("agent", "Thanks. What drew you to the ICU?")]
    assert o.calls[0] == o.calls[1]  # the same conversation, sent again
    assert has_send(at) and "pc_retry" not in keys(at)


def test_an_incomplete_reply_is_a_failure_with_retry(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    cut = {"text": "Thanks, and could you tell me", "status": "incomplete", "details": {"reason": "max_output_tokens"}}
    o = fake(monkeypatch, [cut, "Thanks. What drew you to the ICU?"])
    at, _ = hosted_practice(monkeypatch, tmp_path)
    say(at, "Yes, now works.")
    assert any("reached the 400-token cap and was cut off, so it is not shown" in e.value for e in at.error)
    assert "could you tell me" not in everything(at)
    assert turns(at)[-1] == ("user", "Yes, now works.") and "pc_retry" in keys(at)
    at.button(key="pc_retry").click().run()
    assert len(o.calls) == 2 and turns(at)[-1] == ("agent", "Thanks. What drew you to the ICU?")
    assert [r for r, _ in turns(at)].count("user") == 1


def test_a_timeout_shows_the_uncertain_charge_and_retry_makes_one_more_call(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    timeout = openai.APITimeoutError(request=httpx2.Request("POST", "https://x"))
    o = fake(monkeypatch, [timeout, "Thanks. What drew you to the ICU?", "never sent"])
    at, data = hosted_practice(monkeypatch, tmp_path)
    say(at, "Yes, now works.")
    assert UNCERTAIN in [w.value for w in at.warning] and "pc_retry" in keys(at)
    rows = ledger_rows(data)
    assert rows[-1]["type"] == "settle" and rows[-1]["basis"] == "maximum_raised"  # counted at its maximum
    at.button(key="pc_retry").click().run()
    no_unexpected(at)
    assert len(o.calls) == 2 and turns(at)[-1] == ("agent", "Thanks. What drew you to the ICU?")


def test_retry_adopts_an_earlier_attempts_saved_reply_first(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    o = fake(monkeypatch, ["Thanks. What drew you to the ICU?", "never sent"])
    at, _ = hosted_practice(monkeypatch, tmp_path)
    saved = practice.send(cfg_now(), [*opening(), user("Yes, now works.")])
    at.session_state["pc_turns"] = [
        {"role": "agent", "utterance": practice.OPENING, "run_id": None},
        {"role": "user", "utterance": "Yes, now works.", "run_id": None},
    ]
    # a failed record whose earlier attempt did save a reply (its store was lost)
    at.session_state["pc_pending"] = {"token": "t", "state": "failed", "run_ids": [saved.run_id], "kind": "uncertain"}
    at.run()
    at.button(key="pc_retry").click().run()
    no_unexpected(at)
    assert len(o.calls) == 1 and turns(at)[-1] == ("agent", "Thanks. What drew you to the ICU?")


def test_unclassified_error_shows_no_provider_text(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    req = httpx2.Request("POST", "https://x")
    err = openai.ConflictError("conflict detail sk-proj-****wxyz", response=httpx2.Response(409, request=req), body=None)
    fake(monkeypatch, [err])
    at, _ = hosted_practice(monkeypatch, tmp_path)
    say(at, "Yes, now works.")
    assert UNCERTAIN in [w.value for w in at.warning]  # a run ID existed: the call may have been charged
    assert "wxyz" not in everything(at) and "conflict detail" not in everything(at)
    assert turns(at)[-1] == ("user", "Yes, now works.")


# --------------------------------------------------------- 6. the opening


def test_the_opening_is_never_an_evaluation_option(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fake(monkeypatch, ["Thanks. What drew you to the ICU?"])
    at, _ = hosted_practice(monkeypatch, tmp_path)
    assert not [s for s in at.selectbox if s.key == "pc_eval_pick"]
    assert OPENING_NOT_EVALUABLE in [c.value for c in at.caption]
    say(at, "Yes, now works.")
    assert at.selectbox(key="pc_eval_pick").options == ["Turn 3: Thanks. What drew you to the ICU?"]


# ------------------------------------------------------ 7. plain local mode


def test_plain_local_mode_offers_no_practice_and_writes_nothing() -> None:
    before = committed_snapshot()
    at = AppTest.from_file(APP, default_timeout=60).run()
    assert not at.exception
    assert not [r for r in at.radio if r.key == "pc_mode"]
    assert NEEDS_BUDGET in [c.value for c in at.caption]
    assert committed_snapshot() == before


def test_local_dry_run_practice_writes_only_to_the_data_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    data = tmp_path / "data"
    monkeypatch.setenv("RIGHTONCUE_DRY_RUN", "1")
    monkeypatch.setenv("RIGHTONCUE_BUDGET_USD", "1")
    monkeypatch.setenv("RIGHTONCUE_DATA_DIR", str(data))
    before = committed_snapshot()
    at = to_practice(AppTest.from_file(APP, default_timeout=60).run())
    say(at, "Yes, now works.")
    assert committed_snapshot() == before
    assert len(list((data / "runs").iterdir())) == 1 and not (data / "ledger.jsonl").exists()


# ------------------------------------------------------------ 8. the maximum


@pytest.mark.parametrize("char", ["\u0001", "\U0001F600"], ids=["control", "emoji"])
def test_shown_maximum_covers_the_ledger_reservation(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, char: str) -> None:
    data = hosted_env(monkeypatch, tmp_path)
    fake(monkeypatch, ["Thanks. What drew you to the ICU?"])
    cfg = cfg_now()
    shown = practice.next_reply_max_nano(opening())
    practice.send(cfg, [*opening(), user(char * practice.MAX_MESSAGE_CHARS)])
    [reserve] = [r for r in ledger_rows(data) if r["type"] == "reserve"]
    assert reserve["kind"] == "generation"
    assert shown >= reserve["max_nano"]
    if char == "\u0001":
        assert shown == reserve["max_nano"]  # the worst case is exact


# --------------------------------------------------------- 9. hosted and dry run


def test_hosted_practice_is_unreachable_before_unlocking(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    hosted_env(monkeypatch, tmp_path)
    at = run()
    assert not [r for r in at.radio if r.key == "pc_mode"]
    assert not {"pc_start", "pc_eval", "pc_retry"} & keys(at)
    at = unlock(at)
    assert at.radio(key="pc_mode").value == "Compare models on a transcript"
    assert at.multiselect(key="hl_models")  # the evaluator stays the default


def test_hosted_dry_run_builds_no_real_client_and_is_unscored(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    data = hosted_env(monkeypatch, tmp_path, RIGHTONCUE_DRY_RUN="1")  # factories raise if touched
    at = to_practice(unlock(run()))
    say(at, "Yes, now works.")
    rid = at.session_state["pc_turns"][-1]["run_id"]
    assert f"Simulated reply (dry run) · run {rid}" in everything(at)
    assert any(c.value.startswith("Simulated: Next reply: up to ") and "Simulated budget remaining" in c.value
               for c in at.caption)
    saved_verdicts = badges(at, "judge-v1:")
    at.button(key="pc_eval").click().run()
    no_unexpected(at)
    assert badges(at, "Simulated reply · Unscored") == [":gray-badge[Simulated reply · Unscored]"]
    assert badges(at, "judge-v1:") == saved_verdicts
    assert not [c for c in at.caption if c.value.startswith("Verdict by")]
    assert [(r["type"], r["kind"]) for r in ledger_rows(data, "ledger.dry-run.jsonl")] == [
        ("reserve", "generation"), ("settle", "generation"), ("reserve", "judge"), ("settle", "judge"),
    ]
    assert not (data / "ledger.jsonl").exists()


def test_fictional_details_warning_before_start(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    for dry in ("0", "1"):
        hosted_env(monkeypatch, tmp_path / dry, RIGHTONCUE_DRY_RUN=dry)
        at = unlock(run())
        at.radio(key="pc_mode").set_value(MODE_PRACTICE).run()
        assert FICTIONAL in [w.value for w in at.warning]
        assert "pc_start" in keys(at)
        if dry == "0":
            assert at.button(key="pc_start").disabled  # not acknowledged yet
            assert at.checkbox(key="pc_ack").label == (
                "I understand each reply and each evaluation is a paid API call, counted against the shared cap."
            )
        else:
            assert not [c for c in at.checkbox if c.key == "pc_ack"]
            assert not at.button(key="pc_start").disabled


def test_budget_exhausted_shows_the_conversation_read_only(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fake(monkeypatch, ["Thanks. What drew you to the ICU?"])
    at, data = hosted_practice(monkeypatch, tmp_path)
    say(at, "Yes, now works.")
    spend_down_to(data, cfg_now(), 0)
    at.run()
    no_unexpected(at)
    assert any("budget exhausted" in e.value for e in at.error)
    assert "Thanks. What drew you to the ICU?" in everything(at)
    assert not has_send(at) and not {"pc_eval", "pc_retry", "pc_end"} & keys(at)


# ----------------------------------------- overlapping requests (owner item 2)


def test_overlapping_send_calls_get_run_busy(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Proves: a second practice.send while the first holds the run lock raises RunBusy
    with no call. Function level only, not two overlapping Streamlit script runs."""
    hosted_env(monkeypatch, tmp_path)
    o = BlockingClient(["Thanks. What drew you to the ICU?", "never sent"])
    monkeypatch.setattr(live, "GENERATION_FACTORIES", {"openai": lambda: o, "gemini": boom})
    cfg = cfg_now()
    convo = [*opening(), user("Yes, now works.")]
    results: list[Any] = []
    first = threading.Thread(target=lambda: results.append(practice.send(cfg, convo)))
    first.start()
    try:
        assert o.entered.wait(20)
        with pytest.raises(live.RunBusy):
            practice.send(cfg, convo)
    finally:
        o.release.set()
        first.join(20)
    assert len(o.calls) == 1 and results[0].status == "ok"


def test_overlapping_evaluate_calls_get_run_busy(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Proves: a second practice.evaluate while the first holds the run lock raises
    RunBusy with no call. Function level only, not two overlapping Streamlit script runs."""
    hosted_env(monkeypatch, tmp_path)
    fake(monkeypatch, ["Thanks. What drew you to the ICU?"])
    cfg = cfg_now()
    rid = practice.send(cfg, [*opening(), user("Yes, now works.")]).run_id
    j = BlockingClient([judge(), "never sent"])
    monkeypatch.setattr(live, "GENERATION_FACTORIES", {"openai": lambda: j, "gemini": boom})
    results: list[Any] = []
    first = threading.Thread(target=lambda: results.append(practice.evaluate(cfg, rid)))
    first.start()
    try:
        assert j.entered.wait(20)
        with pytest.raises(live.RunBusy):
            practice.evaluate(cfg, rid)
    finally:
        j.release.set()
        first.join(20)
    assert len(j.calls) == 1 and results[0].calls == 1
    assert practice.evaluate(cfg, rid).calls == 0 and len(j.calls) == 1  # scored on disk: no call


# --------------------------------------------------- reconcile states (owner item 2)


def pending_state(run_ids: list[str]) -> dict[str, Any]:
    return {
        "pc_turns": [
            {"role": "agent", "utterance": practice.OPENING, "run_id": None},
            {"role": "user", "utterance": "Yes, now works.", "run_id": None},
        ],
        "pc_pending": {"token": "t", "state": "sending", "run_ids": run_ids, "kind": None},
    }


def test_reconcile_adopts_an_ok_record(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    hosted_env(monkeypatch, tmp_path)
    fake(monkeypatch, ["Thanks. What drew you to the ICU?"])
    cfg = cfg_now()
    rid = practice.send(cfg, [*opening(), user("Yes, now works.")]).run_id
    state = pending_state([rid])
    assert practice.reconcile(state, cfg) == "adopted"
    assert state["pc_turns"][-1] == {"role": "agent", "utterance": "Thanks. What drew you to the ICU?", "run_id": rid}
    assert state["pc_pending"] is None
    assert practice.reconcile(state, cfg) == "none" and len(state["pc_turns"]) == 3
    assert not practice.adopt({**state, "pc_pending": {"token": "u", "state": "sending", "run_ids": [rid], "kind": None}},
                              rid, "Thanks. What drew you to the ICU?")  # never appended twice


@pytest.mark.parametrize("output,kind", [
    (server_error(), "provider"),
    ({"text": "cut", "status": "incomplete", "details": None}, "incomplete"),
    (openai.APITimeoutError(request=httpx2.Request("POST", "https://x")), "uncertain"),
], ids=["failed", "incomplete", "timeout"])
def test_reconcile_marks_a_failed_record_failed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, output: Any, kind: str) -> None:
    hosted_env(monkeypatch, tmp_path)
    fake(monkeypatch, [output])
    cfg = cfg_now()
    rid = practice.send(cfg, [*opening(), user("Yes, now works.")]).run_id
    state = pending_state([rid])
    assert practice.reconcile(state, cfg) == "failed"
    assert state["pc_pending"]["state"] == "failed" and state["pc_pending"]["kind"] == kind
    assert len(state["pc_turns"]) == 2


def test_reconcile_without_a_record(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    hosted_env(monkeypatch, tmp_path)
    cfg = cfg_now()
    lock = live.run_lock()
    assert lock.acquire(blocking=False)
    try:
        assert practice.reconcile(pending_state(["20261122T000000Z-abcdef"]), cfg) == "waiting"
        assert practice.reconcile(pending_state([]), cfg) == "waiting"
    finally:
        lock.release()
    started = pending_state(["20261122T000000Z-abcdef"])
    assert practice.reconcile(started, cfg) == "failed" and started["pc_pending"]["kind"] == "uncertain"
    never = pending_state([])
    assert practice.reconcile(never, cfg) == "failed" and never["pc_pending"]["kind"] == "interrupted"


def test_reconcile_a_turn_left_without_its_pending_record(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """begin_send interrupted after the turn was appended: Retry, never a second Send form."""
    hosted_env(monkeypatch, tmp_path)
    state = {**pending_state([]), "pc_pending": None}
    assert practice.reconcile(state, cfg_now()) == "failed"
    assert state["pc_pending"]["kind"] == "interrupted" and len(state["pc_turns"]) == 2


def test_waiting_view_offers_check_again_and_no_send_or_retry(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    o = fake(monkeypatch, ["never sent"])
    at, _ = hosted_practice(monkeypatch, tmp_path)
    for k, v in pending_state(["20261122T000000Z-abcdef"]).items():
        at.session_state[k] = v
    lock = live.run_lock()
    assert lock.acquire(blocking=False)
    try:
        at.run()
        no_unexpected(at)
        assert "Riley's reply is still being generated." in [i.value for i in at.info]
        assert "pc_check" in keys(at) and not {"pc_retry", "pc_end"} & keys(at) and not has_send(at)
        at.button(key="pc_check").click().run()
        assert "Riley's reply is still being generated." in [i.value for i in at.info]
    finally:
        lock.release()
    at.run()
    assert UNCERTAIN in [w.value for w in at.warning] and "pc_retry" in keys(at)
    assert o.calls == []


def test_interrupted_send_without_a_run_id(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    o = fake(monkeypatch, ["Thanks. What drew you to the ICU?"])
    at, _ = hosted_practice(monkeypatch, tmp_path)
    for k, v in pending_state([]).items():
        at.session_state[k] = v
    at.run()
    assert ("The last send was interrupted before Riley's reply was saved. Your message is kept; "
            "Retry sends the same conversation again.") in [w.value for w in at.warning]
    at.button(key="pc_retry").click().run()
    assert len(o.calls) == 1 and [r for r, _ in turns(at)] == ["agent", "user", "agent"]


def test_pending_evaluation_reconciles_from_the_score_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    hosted_env(monkeypatch, tmp_path)
    fake(monkeypatch, ["Thanks. What drew you to the ICU?", judge()])
    cfg = cfg_now()
    rid = practice.send(cfg, [*opening(), user("Yes, now works.")]).run_id
    state: dict[str, Any] = {"pc_evals": {rid: {"token": "t", "state": "evaluating"}}}
    lock = live.run_lock()
    assert lock.acquire(blocking=False)
    try:
        assert practice.reconcile_evaluations(state, cfg) == [rid]  # nothing on disk, still running
    finally:
        lock.release()
    assert practice.reconcile_evaluations(state, cfg) == []
    assert state["pc_evals"][rid]["state"] == "failed" and state["pc_evals"][rid]["kind"] == "uncertain"
    practice.evaluate(cfg, rid)
    state = {"pc_evals": {rid: {"token": "t", "state": "evaluating"}}}
    assert practice.reconcile_evaluations(state, cfg) == []
    assert state["pc_evals"][rid]["state"] == "done"


class SpyLock:
    """Stands in for the run lock: reports a state, and fails the test if anyone takes it."""

    def __init__(self, held: bool) -> None:
        self.held = held

    def locked(self) -> bool:
        return self.held

    def acquire(self, blocking: bool = True) -> bool:
        raise AssertionError("the wait check must never take the run lock")


def test_the_wait_check_adopts_once_the_slot_appears_and_never_calls(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    hosted_env(monkeypatch, tmp_path)
    fake(monkeypatch, ["Thanks. What drew you to the ICU?"])
    cfg = cfg_now()
    rid = practice.send(cfg, [*opening(), user("Yes, now works.")]).run_id
    slots = practice.run_dir(cfg, rid) / "slots.jsonl"
    hidden = slots.with_name("slots.hidden")
    slots.rename(hidden)  # as if the call were still running
    monkeypatch.setattr(live, "GENERATION_FACTORIES", {"openai": boom, "gemini": boom})
    monkeypatch.setattr(live, "guarded_clients", boom)
    spy = SpyLock(held=True)
    monkeypatch.setattr(live, "_RUN_LOCK", spy)
    state = pending_state([rid])
    assert practice.poll_waiting(state, cfg) is True and state["pc_pending"]["state"] == "sending"
    hidden.rename(slots)
    spy.held = False
    assert practice.poll_waiting(state, cfg) is False
    assert state["pc_turns"][-1]["run_id"] == rid and state["pc_pending"] is None


def test_the_waiting_view_polls_with_a_bound(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    o = fake(monkeypatch, ["Thanks. What drew you to the ICU?"])
    at, _ = hosted_practice(monkeypatch, tmp_path)
    rid = practice.send(cfg_now(), [*opening(), user("Yes, now works.")]).run_id
    assert len(o.calls) == 1
    slots = practice.run_dir(cfg_now(), rid) / "slots.jsonl"
    hidden = slots.with_name("slots.hidden")
    slots.rename(hidden)
    for k, v in pending_state([rid]).items():
        at.session_state[k] = v
    lock = live.run_lock()
    assert lock.acquire(blocking=False)
    try:
        at.run()
        no_unexpected(at)
        assert "Riley's reply is still being generated." in [i.value for i in at.info]
        assert "Checking again automatically." in [c.value for c in at.caption]
        monkeypatch.setattr(practice, "WAIT_POLL_MAX_S", 0.0)
        at.run()
        assert "Stopped checking automatically. Use Check again." in [c.value for c in at.caption]
        assert "pc_check" in keys(at)
    finally:
        lock.release()
    hidden.rename(slots)
    at.run()
    no_unexpected(at)
    assert turns(at)[-1] == ("agent", "Thanks. What drew you to the ICU?") and len(o.calls) == 1
    assert "pc_wait_since" not in at.session_state


# ------------------------------------------------- judge version on the verdict (owner item 3)


def test_a_record_under_another_judge_version_shows_that_version(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    o = fake(monkeypatch, ["Thanks. What drew you to the ICU?", judge(), "never sent"])
    at, data = hosted_practice(monkeypatch, tmp_path)
    say(at, "Yes, now works.")
    rid = at.session_state["pc_turns"][-1]["run_id"]
    practice.evaluate(cfg_now(), rid)
    path = data / "scores" / f"{rid}.jsonl"
    [record] = [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines()]
    record["judge_prompt_version"] = "judge-v2a"  # scorer-1, written by hand
    path.write_text(json.dumps(record) + "\n", encoding="utf-8")
    calls = len(o.calls)
    at.button(key="pc_eval").click().run()
    no_unexpected(at)
    assert len(o.calls) == calls  # a valid verdict exists: no call
    assert f"Verdict by judge-v2a (scorer-1).{CACHED}" in [c.value for c in at.caption]
    tab = at.tabs[2]
    practice_badges = [m.value for m in tab.markdown if "-badge[" in m.value]
    assert ":green-badge[judge-v2a: acceptable · 8/8]" in practice_badges
    assert not [b for b in practice_badges if "judge-v1:" in b]


def test_render_card_judge_label_is_optional_and_defaults_to_none() -> None:
    """Existing callers pass no label and keep the JUDGE badge (checked by test_app_live)."""
    import ast

    src = (REPO / "app.py").read_text(encoding="utf-8")
    fn = next(n for n in ast.parse(src).body if isinstance(n, ast.FunctionDef) and n.name == "render_card")
    assert [a.arg for a in fn.args.kwonlyargs] == ["judge_label"]
    assert isinstance(fn.args.kw_defaults[0], ast.Constant) and fn.args.kw_defaults[0].value is None


# --------------------------------------------------- limits and session helpers


def test_limits_at_the_turn_cap() -> None:
    convo = opening()
    for i in range(live.MAX_TURNS // 2 - 1):  # 39 turns: one more message makes 40, allowed
        convo += [user(f"m{i}"), agent(f"r{i}")]
    assert len(convo) == live.MAX_TURNS - 1 and practice.next_turn_limit_errors(convo) == []
    convo += [user("m"), agent("r")]  # 41: the next message would make 42
    assert practice.next_turn_limit_errors(convo) == ["Transcript: 42 turns; the limit is 40."]


def test_over_the_limit_hides_send_with_a_warning(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fake(monkeypatch, ["never sent"])
    at, _ = hosted_practice(monkeypatch, tmp_path)
    monkeypatch.setattr(practice, "next_turn_limit_errors", lambda turns: ["Transcript: 42 turns; the limit is 40."])
    at.run()
    no_unexpected(at)
    assert ("This practice call has reached its length limit (40 turns or 12,000 characters). End it, "
            "evaluate a reply, or start a new call.") in [w.value for w in at.warning]
    assert not has_send(at) and "pc_end" in keys(at)


def test_messages_are_trimmed_and_capped() -> None:
    assert practice.clean_message("  hi  ") == "hi"
    with pytest.raises(practice.MessageError):
        practice.clean_message("   ")
    with pytest.raises(practice.MessageError):
        practice.clean_message("x" * 601)
    assert practice.clean_message("x" * 600) == "x" * 600


def test_end_and_new_call(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fake(monkeypatch, ["Thanks. What drew you to the ICU?"])
    at, _ = hosted_practice(monkeypatch, tmp_path)
    say(at, "Yes, now works.")
    at.button(key="pc_end").click().run()
    assert "Practice call ended. You can still evaluate any of Riley's replies." in [i.value for i in at.info]
    assert not has_send(at) and "pc_eval" in keys(at)
    n = form_n(at)
    at.button(key="pc_new").click().run()
    assert "pc_turns" not in at.session_state and "pc_start" in keys(at)
    assert form_n(at) == n  # the form counter keeps counting
