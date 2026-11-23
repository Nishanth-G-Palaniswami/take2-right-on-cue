"""Talk to Riley: a typed practice call, one fresh run per applicant message.

Nothing here imports Streamlit. Each Send is a fresh run (gpt-5.4, prompt v3, 1 sample)
under the data directory, whose case is the conversation so far, so evaluating a reply
scores that run and later turns can't reach the judge. Every paid call takes the
process-wide run lock (non-blocking) and goes through the ledger's guarded clients.

The session-state helpers at the bottom take a plain mutable mapping (the app passes
`st.session_state`); every key starts with "pc_". Disk is the truth: a reply or a
judgment is adopted from the run's slots.jsonl and the score file, so a result that was
written but never stored in the session (an interrupted or overlapping script run) is
picked up again without a second call.
"""

from __future__ import annotations

import json
import secrets
import threading
from collections.abc import Callable, MutableMapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from . import gemini, live, openai_responses, review, scoring
from .ledger import BudgetExceeded
from .runs import InputFile, load_manifest, new_run_id, read_slots
from .transcript import Turn

MODEL = "gpt-5.4"
PROMPT_PATH = review.PROMPTS_DIR / "v3.md"
CASE_PATH = "practice/conversation.jsonl"  # stem "conversation": no entry in cases/notes.toml
MAX_MESSAGE_CHARS = 600
APPLICANT_NAME = "Alex"
OPENING = (
    "Hi Alex, this is Riley, a virtual recruiting assistant with Acme Health. I'm calling "
    "about the Medical ICU nurse position you applied for. Is now a good time to talk for "
    "a few minutes?"
)
# The most canonical-JSON bytes one character can cost: a control character is escaped
# as \u0001 (6 bytes). A message of N such characters bounds every N-character message.
WORST_CASE_CHAR = "\u0001"
# For the length limits (characters of the JSONL transcript), an ordinary character.
PLAIN_CHAR = "x"
BUSY = "Another run is in progress, try again shortly."
FATAL_JUDGE_ERRORS = tuple(cls.__name__ for cls in openai_responses.FATAL_ERRORS)

# Serialises the adopt / fail updates of a practice conversation's session state: two
# script runs of one session can overlap (Streamlit's fast reruns), and both may try to
# store the same reply. Held only for in-memory updates, never around a call.
_STATE_LOCK = threading.Lock()


class MessageError(ValueError):
    """The applicant's message is empty or too long. Safe to show."""


# ------------------------------------------------------------------ conversation


def prompt_file() -> InputFile:
    return review.read_input(PROMPT_PATH)


def conversation_jsonl(turns: list[Turn]) -> str:
    """The turns in the existing transcript format, one JSON object per line."""
    return "".join(
        json.dumps({"role": t.role, "utterance": t.utterance}, ensure_ascii=False) + "\n"
        for t in turns
    )


def case_file(turns: list[Turn]) -> InputFile:
    return InputFile(CASE_PATH, conversation_jsonl(turns).encode("utf-8"))


def clean_message(raw: str) -> str:
    """The trimmed message, 1 to MAX_MESSAGE_CHARS characters (code points)."""
    text = raw.strip()
    if not text:
        raise MessageError("Type a message first.")
    if len(text) > MAX_MESSAGE_CHARS:
        raise MessageError(
            f"Your message is {len(text):,} characters; the limit is {MAX_MESSAGE_CHARS}."
        )
    return text


def limit_errors(turns: list[Turn]) -> list[str]:
    """Why a run with this transcript (ending on the applicant) can't start: MAX_TURNS,
    MAX_TRANSCRIPT_CHARS and the transcript format, as live.validate_run checks them."""
    return live.validate_run(prompt_file().text, case_file(turns).text, [MODEL], 1, 1)


def next_turn_limit_errors(turns: list[Turn]) -> list[str]:
    """Limit errors for the smallest next message (one ordinary character)."""
    return limit_errors([*turns, Turn(role="user", utterance=PLAIN_CHAR)])


def reply_max_nano(turns: list[Turn]) -> int:
    """The maximum cost of Riley's reply to this transcript: the real request, as the
    ledger's guard reserves it (live.project_run builds it exactly as the runner)."""
    return live.project_run(prompt_file(), case_file(turns), [MODEL], 1).generation_nano


def next_reply_max_nano(turns: list[Turn], chars: int = MAX_MESSAGE_CHARS) -> int:
    """The maximum cost of the next reply for any message of up to `chars` characters:
    the placeholder costs the most bytes any character can."""
    return reply_max_nano([*turns, Turn(role="user", utterance=WORST_CASE_CHAR * chars)])


# ---------------------------------------------------------------------- replies


@dataclass(frozen=True)
class ReplyOutcome:
    """A practice run's single slot, as saved."""

    run_id: str
    status: Literal["ok", "empty", "incomplete", "failed"]
    text: str | None = None
    error_type: str | None = None  # a failure's error type and HTTP status only
    error_status: int | None = None

    @property
    def charge_uncertain(self) -> bool:
        """A failure with no HTTP response (timeout, connection error): the request may
        still have been processed and charged."""
        return self.status == "failed" and self.error_status is None and self.error_type != "response_status"


def run_dir(cfg: live.LiveConfig, run_id: str) -> Path:
    return cfg.runs_dir / run_id


def slot_outcome(cfg: live.LiveConfig, run_id: str) -> ReplyOutcome | None:
    """The run's saved slot, or None when it has none (never started, or still running)."""
    records = read_slots(run_dir(cfg, run_id)) if run_dir(cfg, run_id).is_dir() else []
    if not records:
        return None
    if len(records) > 1:
        raise ValueError(f"practice run {run_id} has {len(records)} slot records; expected one")
    rec = records[0]
    status = rec.get("status")
    if status == "ok":
        text = rec.get("output_text")
        if isinstance(text, str) and text.strip():
            return ReplyOutcome(run_id, "ok", text)
        return ReplyOutcome(run_id, "empty")
    if status == "incomplete":
        return ReplyOutcome(run_id, "incomplete")
    if status == "generation_failed":
        err = rec.get("error") or {}
        return ReplyOutcome(run_id, "failed", error_type=err.get("type"), error_status=err.get("status_code"))
    raise ValueError(f"practice run {run_id}: unknown slot status {status!r}")


def saved_reply(cfg: live.LiveConfig, run_id: str) -> str | None:
    """The run's saved reply text when its slot is ok, else None."""
    out = slot_outcome(cfg, run_id)
    return out.text if out is not None and out.status == "ok" else None


def send(
    cfg: live.LiveConfig, turns: list[Turn], on_start: Callable[[str], None] | None = None
) -> ReplyOutcome:
    """Generate Riley's one reply to `turns` (ending on the applicant's message).

    Raises RunInputError (limits, message length), RunBusy (the run lock is held),
    BudgetExceeded (the actual request's maximum is more than the remaining budget; no
    call), LedgerError. `on_start(run_id)` is called before the paid call. Any other
    exception from the runner (an unclassified provider error) propagates; the ledger
    has then settled the call at its maximum.
    """
    if not turns or turns[-1].role != "user":
        raise live.RunInputError("The conversation must end on the applicant's message.")
    if len(turns[-1].utterance) > MAX_MESSAGE_CHARS or not turns[-1].utterance.strip():
        raise live.RunInputError(f"The message must be 1 to {MAX_MESSAGE_CHARS} characters.")
    prompt, case = prompt_file(), case_file(turns)
    errors = live.validate_run(prompt.text, case.text, [MODEL], 1, 1)
    if errors:
        raise live.RunInputError(" ".join(errors))
    lock = live.run_lock()
    if not lock.acquire(blocking=False):
        raise live.RunBusy(BUSY)
    try:
        ledger = live.open_ledger(cfg)
        needed = live.project_run(prompt, case, [MODEL], 1).generation_nano
        if needed > ledger.remaining():  # re-checked under the run lock
            raise BudgetExceeded(
                "The remaining budget can't cover Riley's next reply; no call was made."
            )
        gen, _ = live.guarded_clients(cfg, ledger, [openai_responses.PROVIDER])
        run_id = new_run_id()
        if on_start is not None:
            on_start(run_id)
        review.generate(
            prompt, case, [MODEL], 1, live.HOSTED_REASONING_EFFORT, live.HOSTED_THINKING_LEVEL,
            runs_dir=cfg.runs_dir, clients=gen, max_output_tokens=live.OUTPUT_CAP,
            gemini_retry_options=gemini.NO_RETRY_OPTIONS, run_id=run_id,
        )
    finally:
        lock.release()
    out = slot_outcome(cfg, run_id)
    if out is None:  # run_slots appends the record before it returns
        raise RuntimeError(f"practice run {run_id} returned without a slot record")
    return out


# ------------------------------------------------------------------- evaluation


def run_turns(cfg: live.LiveConfig, run_id: str) -> list[Turn]:
    """The turns the run's reply answered (and the judge sees), from its manifest."""
    manifest = load_manifest(run_dir(cfg, run_id))
    return [Turn.model_validate(t) for t in manifest["cases"][0]["turns"]]


def judge_max_nano(cfg: live.LiveConfig, run_id: str) -> int:
    """The evaluation's maximum: the first judge call plus the one retry."""
    manifest = load_manifest(run_dir(cfg, run_id))
    case = InputFile(CASE_PATH, manifest["cases"][0]["raw_text"].encode("utf-8"))
    return live.project_run(prompt_file(), case, [MODEL], 1).judge_nano


@dataclass(frozen=True)
class Judgment:
    """What the score file holds for a practice reply."""

    record: dict[str, Any] | None  # the record to show (see judgment())
    scored: bool  # a valid verdict exists (any judge version): never judged again
    failed_attempts: int  # needs_review / judge_failed under live.JUDGE_VERSION
    last_fatal: bool  # the latest failed attempt was a fatal error: no retry after it
    last_uncertain: bool  # the latest failed attempt got no HTTP response

    @property
    def calls_allowed(self) -> int:
        if self.scored or self.last_fatal:
            return 0
        return max(0, live.JUDGE_ATTEMPTS - self.failed_attempts)

    @property
    def judge_version(self) -> str | None:
        return self.record.get("judge_prompt_version") if self.record else None

    @property
    def scorer_version(self) -> str | None:
        return self.record.get("scorer_version") if self.record else None


def _reply_slot(cfg: live.LiveConfig, run_id: str) -> tuple[str, str]:
    records = read_slots(run_dir(cfg, run_id)) if run_dir(cfg, run_id).is_dir() else []
    ok = [r for r in records if r.get("status") == "ok" and isinstance(r.get("output_text"), str)
          and r["output_text"].strip()]
    if len(ok) != 1:
        raise live.RunInputError("This turn has no saved reply to evaluate.")
    return ok[0]["slot_key"], ok[0]["output_text"]


def judgment(cfg: live.LiveConfig, run_id: str) -> Judgment:
    """The reply's judgments on disk. The record shown is a scored one (under
    live.JUDGE_VERSION first, else the latest under any version), else the latest
    failed attempt under live.JUDGE_VERSION, else None."""
    slot_key, text = _reply_slot(cfg, run_id)
    records = scoring.read_score_records(review.scores_path_for(run_id, cfg.scores_dir))
    sha = scoring.text_sha256(text)
    mine = [r for r in records if r.get("slot_key") == slot_key and r.get("text_sha256") == sha]
    scored = [r for r in mine if r.get("status") == "scored"]
    current = [r for r in scored if r.get("judge_prompt_version") == live.JUDGE_VERSION]
    failed = [r for r in mine if r.get("status") in live.RETRYABLE_JUDGE_STATUSES
              and r.get("judge_prompt_version") == live.JUDGE_VERSION]
    last_err = (failed[-1].get("error") or {}) if failed else {}
    record = (current or scored)[0 if current else -1] if scored else (failed[-1] if failed else None)
    return Judgment(
        record=record,
        scored=bool(scored),
        failed_attempts=review.failed_judge_attempts(records, slot_key, text, live.JUDGE_VERSION),
        last_fatal=last_err.get("type") in FATAL_JUDGE_ERRORS,
        last_uncertain=bool(failed) and failed[-1].get("status") == "judge_failed"
        and last_err.get("status_code") is None,
    )


@dataclass
class EvalOutcome:
    run_id: str
    calls: int  # judge calls made by this evaluation (0: already judged)
    messages: list[str] = field(default_factory=list)  # safe to show


def evaluate(cfg: live.LiveConfig, run_id: str) -> EvalOutcome:
    """Judge one practice reply with live.JUDGE_VERSION, at most JUDGE_ATTEMPTS calls in
    total across every evaluation of it: a first attempt, then one judge-only retry for
    needs_review / judge_failed, as live.run_fresh does. A reply with a valid verdict, a
    fatal judge error, or no attempt left makes no call.

    Raises RunBusy, BudgetExceeded (the projection is more than the remaining budget, or
    the guard refused the first call; no call), LedgerError, RunInputError.
    """
    lock = live.run_lock()
    if not lock.acquire(blocking=False):
        raise live.RunBusy(BUSY)
    try:
        state = judgment(cfg, run_id)  # re-read under the lock
        if state.calls_allowed == 0:
            return EvalOutcome(run_id, 0)
        ledger = live.open_ledger(cfg)
        if judge_max_nano(cfg, run_id) > ledger.remaining():
            raise BudgetExceeded(
                "The remaining budget can't cover this evaluation (one judge call plus one "
                "retry); no call was made."
            )
        _, judge_client = live.guarded_clients(cfg, ledger, [])
        out = EvalOutcome(run_id, 0)
        if state.failed_attempts == 0:
            _, first = review.score_run(
                run_dir(cfg, run_id), live.JUDGE_VERSION, scores_dir=cfg.scores_dir, client=judge_client
            )
            out.calls += first.calls
            if first.fatal_message is not None:
                out.messages.append(live._fatal_judge_message(first, "Scoring"))
                return out
            if not any(o.kind in live.RETRYABLE_JUDGE_STATUSES for o in first.outcomes):
                return out
        try:
            retried = live.retry_invalid_judgments(cfg, run_dir(cfg, run_id), judge_client)
        except BudgetExceeded as exc:
            out.messages.append(
                f"The judge retry stopped: {exc}. A judgment that needs review is shown "
                "without a valid score."
            )
        else:
            if retried is not None:
                out.calls += retried.calls
                if retried.fatal_message is not None:
                    out.messages.append(live._fatal_judge_message(retried, "The judge retry"))
        return out
    finally:
        lock.release()


# ------------------------------------------------- session state (no Streamlit)

State = MutableMapping[str, Any]
CONVERSATION_KEYS = ("pc_started", "pc_turns", "pc_pending", "pc_ended", "pc_evals")


def start(state: State) -> None:
    """A new conversation: the scripted opening only."""
    state["pc_turns"] = [{"role": "agent", "utterance": OPENING, "run_id": None}]
    state["pc_pending"] = None
    state["pc_ended"] = False
    state["pc_evals"] = {}
    state["pc_started"] = True


def clear(state: State) -> None:
    """Forget the conversation. The form counter (pc_n) keeps counting, so a stale form
    from the old conversation never matches a new one."""
    for key in CONVERSATION_KEYS:
        if key in state:
            del state[key]


def turns_of(state: State) -> list[Turn]:
    return [Turn(role=t["role"], utterance=t["utterance"]) for t in state.get("pc_turns", [])]


def begin_send(state: State, text: str) -> str:
    """Bump the form counter, append the applicant turn and write the pending record,
    together, before any paid call. Returns the pending record's token.

    Each session-state access can be interrupted (a Streamlit yield point), so the order
    matters: the counter first (the old form, and a queued second click on it, then match
    no widget), then the turn; a turn left without its pending record is turned into an
    interrupted send by reconcile(). No call is made before all three are written."""
    token = secrets.token_hex(8)
    state["pc_n"] = state.get("pc_n", 0) + 1
    state["pc_turns"] = [*state["pc_turns"], {"role": "user", "utterance": text, "run_id": None}]
    state["pc_pending"] = {"token": token, "state": "sending", "run_ids": [], "kind": None}
    return token


def begin_retry(state: State) -> str:
    """The same conversation again: the pending record goes back to sending, keeping
    every earlier attempt's run ID. The applicant turn is never appended again."""
    pending = state["pc_pending"]
    token = secrets.token_hex(8)
    state["pc_pending"] = {**pending, "token": token, "state": "sending", "kind": None}
    return token


def note_run_id(state: State, token: str, run_id: str) -> None:
    """on_start: remember the attempt's run ID, before its paid call."""
    with _STATE_LOCK:
        pending = state.get("pc_pending")
        if pending is not None and pending["token"] == token:
            state["pc_pending"] = {**pending, "run_ids": [*pending["run_ids"], run_id]}


def adopt(state: State, run_id: str, text: str) -> bool:
    """Store a saved reply as Riley's turn, once. Only a run of the pending record is
    adopted; a run already in the conversation is never appended again."""
    with _STATE_LOCK:
        pending = state.get("pc_pending")
        if pending is None or run_id not in pending["run_ids"]:
            return False
        if any(t.get("run_id") == run_id for t in state.get("pc_turns", [])):
            state["pc_pending"] = None
            return False
        state["pc_turns"] = [*state["pc_turns"], {"role": "agent", "utterance": text, "run_id": run_id}]
        state["pc_pending"] = None
        return True


def fail(state: State, token: str | None, kind: str, **detail: Any) -> None:
    """Mark the pending send failed (the conversation is kept, awaiting a reply).
    `token` None applies to whichever record is pending (reconcile)."""
    with _STATE_LOCK:
        pending = state.get("pc_pending")
        if pending is None or (token is not None and pending["token"] != token):
            return
        state["pc_pending"] = {**pending, "state": "failed", "kind": kind, **detail}


def record_outcome(state: State, token: str | None, out: ReplyOutcome) -> None:
    if out.status == "ok":
        assert out.text is not None
        adopt(state, out.run_id, out.text)
    elif out.status == "failed":
        if out.charge_uncertain:
            fail(state, token, "uncertain")
        else:
            fail(state, token, "provider", error_type=out.error_type, error_status=out.error_status)
    else:
        fail(state, token, out.status)  # "incomplete" or "empty"


def adopt_saved(state: State, cfg: live.LiveConfig) -> bool:
    """Adopt an ok reply saved by any earlier attempt of the pending record."""
    pending = state.get("pc_pending")
    if pending is None:
        return False
    for run_id in pending["run_ids"]:
        if (text := saved_reply(cfg, run_id)) is not None:
            return adopt(state, run_id, text)
    return False


def reconcile(state: State, cfg: live.LiveConfig) -> Literal["none", "adopted", "failed", "waiting"]:
    """Resolve a pending send from disk, before any widget renders.

    An ok slot of any attempt is adopted; a failed or incomplete slot of the latest
    attempt marks the send failed; no slot while the run lock is held is still running
    ("waiting"); no slot while the lock is free was interrupted ("uncertain" when the
    attempt had a run ID, since its call may have been made). A conversation ending on
    the applicant with no pending record (begin_send interrupted) was interrupted too.
    """
    pending = state.get("pc_pending")
    convo = state.get("pc_turns") or []
    if pending is None and convo and convo[-1]["role"] == "user":
        state["pc_pending"] = {
            "token": secrets.token_hex(8), "state": "failed", "run_ids": [], "kind": "interrupted",
        }
        return "failed"
    if pending is None or pending["state"] != "sending":
        return "none"
    if adopt_saved(state, cfg):
        return "adopted"
    run_ids = pending["run_ids"]
    last = slot_outcome(cfg, run_ids[-1]) if run_ids else None
    if last is not None:
        record_outcome(state, None, last)
        return "failed"
    if live.run_lock().locked():
        return "waiting"
    fail(state, None, "uncertain" if run_ids else "interrupted")
    return "failed"


def begin_evaluation(state: State, run_id: str) -> str:
    token = secrets.token_hex(8)
    state["pc_evals"] = {**state.get("pc_evals", {}), run_id: {"token": token, "state": "evaluating"}}
    return token


def finish_evaluation(session: State, run_id: str, token: str | None, **result: Any) -> None:
    """Store an evaluation's result (state "done" or "failed") once, for its own token."""
    with _STATE_LOCK:
        evals = session.get("pc_evals", {})
        current = evals.get(run_id)
        if current is None or (token is not None and current.get("token") != token):
            return
        session["pc_evals"] = {**evals, run_id: {**current, **result}}


def reconcile_evaluations(state: State, cfg: live.LiveConfig) -> list[str]:
    """Resolve pending evaluations from the score file; returns those still running.

    A valid verdict, or any judgment once the run lock is free, finishes it (a judge
    call was made); nothing on disk with the lock free was interrupted (the call may
    have been made: the charge is uncertain)."""
    waiting: list[str] = []
    for run_id, ev in list(state.get("pc_evals", {}).items()):
        if ev.get("state") != "evaluating":
            continue
        j = judgment(cfg, run_id)
        if j.scored or (j.record is not None and not live.run_lock().locked()):
            finish_evaluation(state, run_id, None, state="done", calls=1, messages=[])
        elif live.run_lock().locked():
            waiting.append(run_id)
        else:
            finish_evaluation(state, run_id, None, state="failed", kind="uncertain")
    return waiting
