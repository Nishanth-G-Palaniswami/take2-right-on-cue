"""Live runs: configuration, access gate, per-run limits, projection and orchestration.

Nothing here talks to Streamlit. Every client comes from `GENERATION_FACTORIES` (or
the dry-run fakes) and is wrapped by the spending guard in `ledger.py`; tests
replace the factories, so no real request is ever made.
"""

from __future__ import annotations

import hmac
import logging
import os
import threading
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Literal

from . import dryrun, gemini, openai_responses, review, scoring
from .ledger import BudgetExceeded, Ledger, LedgerError, guard_clients, max_call_cost
from .runs import InputFile, ModelSpec, RunResult, _build_request, new_run_id
from .transcript import TranscriptError, parse_transcript

log = logging.getLogger("rightoncue.live")

HOSTED_ENV = review.HOSTED_ENV  # "RIGHTONCUE_HOSTED"
ACCESS_CODE_ENV = "RIGHTONCUE_ACCESS_CODE"
BUDGET_ENV = "RIGHTONCUE_BUDGET_USD"
DATA_DIR_ENV = "RIGHTONCUE_DATA_DIR"
MAX_SAMPLES_ENV = "RIGHTONCUE_MAX_SAMPLES"
DRY_RUN_ENV = "RIGHTONCUE_DRY_RUN"
DRY_RUN_DELAY_ENV = "RIGHTONCUE_DRY_RUN_DELAY_S"
DEFAULT_LOCAL_DATA_DIR = review.REPO_ROOT / "data"  # git-ignored; local mode only
DEFAULT_MAX_SAMPLES = 2
LEDGER_FILE = "ledger.jsonl"
DRY_RUN_LEDGER_FILE = "ledger.dry-run.jsonl"  # simulated spend never touches the real ledger
MAX_DRY_RUN_DELAY_S = 600.0

# Output cap for budgeted fresh runs, in tokens (reasoning / thinking included).
# The saved evaluation's replies used 16-90 output tokens (gpt-5.4 16-90,
# gpt-5.4-mini 19-63, gemini-3.5-flash 18-64; reasoning effort none / thinking
# MINIMAL, so ~0 reasoning tokens). 400 is over 4x the longest saved reply, so a
# normal reply is never cut, while each call's output cost stays bounded
# (gpt-5.4: 400 x $15/M = $0.006). A reply that reaches it comes back incomplete
# and is shown as an operational failure.
OUTPUT_CAP = 400
# Hosted fresh runs use the settings the saved evaluation measured (no reviewer
# choice): they keep reasoning and thinking near zero, inside the cap.
HOSTED_REASONING_EFFORT = "none"
HOSTED_THINKING_LEVEL = "MINIMAL"
JUDGE_VERSION = scoring.DEFAULT_JUDGE_VERSION
# Per-run limits, checked before any call.
MAX_PROMPT_CHARS = 12_000
MAX_TRANSCRIPT_CHARS = 12_000
MAX_TURNS = 40
# The projection needs the judge requests before the replies exist. It assumes a
# reply of OUTPUT_CAP tokens takes at most this many bytes in the judge request (a
# saved reply is at most ~340 characters; English is ~4 bytes per token). This is an
# estimate for the up-front refusal only: every judge call reserves the maximum
# from its real request bytes, so the budget holds either way.
PROJECTED_REPLY_BYTES_PER_TOKEN = 16
# Access gate: failed attempts are counted process-wide (a reload or a new session
# can't reset them); after MAX_FAILED_ATTEMPTS, nobody can try for COOLDOWN_S.
MAX_FAILED_ATTEMPTS = 5
COOLDOWN_S = 60.0


class ConfigError(ValueError):
    """An environment variable for live mode has an invalid value."""


class RunInputError(ValueError):
    """The reviewer's run is invalid (limits, models, transcript). Safe to show."""


class RunBusy(RuntimeError):
    """Another paid run holds the process-wide run lock."""


@dataclass(frozen=True)
class LiveConfig:
    hosted: bool
    access_code: str | None = field(repr=False)  # never shown, logged or stored in a session
    budget_nano: int | None
    data_dir: Path | None
    max_samples: int
    dry_run: bool
    dry_run_delay_s: float

    @property
    def ledger_path(self) -> Path:
        if self.data_dir is None:
            raise ConfigError(f"{DATA_DIR_ENV} is not set")
        return self.data_dir / (DRY_RUN_LEDGER_FILE if self.dry_run else LEDGER_FILE)

    @property
    def runs_dir(self) -> Path:
        if self.data_dir is None:
            raise ConfigError(f"{DATA_DIR_ENV} is not set")
        return self.data_dir / "runs"

    @property
    def scores_dir(self) -> Path:
        if self.data_dir is None:
            raise ConfigError(f"{DATA_DIR_ENV} is not set")
        return self.data_dir / "scores"


def _flag(env: Mapping[str, str], name: str) -> bool:
    value = env.get(name, "")
    if value in ("", "0"):
        return False
    if value == "1":
        return True
    raise ConfigError(f"{name} must be 1 or 0 (or unset), got {value!r}")


def parse_budget(text: str) -> int:
    """A positive USD amount, in nano-USD (exact, no float)."""
    try:
        value = Decimal(text.strip())
    except InvalidOperation:
        raise ConfigError(f"{BUDGET_ENV}: {text!r} is not a number") from None
    if not value.is_finite() or value <= 0:
        raise ConfigError(f"{BUDGET_ENV}: must be a positive amount in USD, got {text!r}")
    nano = value * 10**9
    if nano != nano.to_integral_value():
        raise ConfigError(f"{BUDGET_ENV}: {text!r} has more precision than 1e-9 USD")
    return int(nano)


def _data_dir(env: Mapping[str, str], hosted: bool) -> Path | None:
    raw = env.get(DATA_DIR_ENV, "").strip()
    if not raw:
        return None if hosted else DEFAULT_LOCAL_DATA_DIR
    path = Path(raw)
    if not path.is_absolute():
        path = review.REPO_ROOT / path
    path = path.resolve()
    root = review.REPO_ROOT.resolve()
    committed = [root / d for d in ("runs", "scores", "holdout", "holdout-private", "prompts", "cases", "docs")]
    if path == root or any(path.is_relative_to(c) for c in committed) or any(
        c.is_relative_to(path / "runs") or c.is_relative_to(path / "scores") for c in committed
    ):
        raise ConfigError(
            f"{DATA_DIR_ENV}: {path.as_posix()} would put fresh runs or scores in the "
            "repository's committed folders; choose a separate directory"
        )
    return path


def load_config(env: Mapping[str, str]) -> LiveConfig:
    """Read and validate the live-mode variables. Raises ConfigError for a bad value."""
    hosted = _flag(env, HOSTED_ENV)
    dry_run = _flag(env, DRY_RUN_ENV)
    code = env.get(ACCESS_CODE_ENV, "")
    budget_text = env.get(BUDGET_ENV, "")
    budget_nano = parse_budget(budget_text) if budget_text.strip() else None
    samples_text = env.get(MAX_SAMPLES_ENV, "").strip()
    if samples_text:
        if not samples_text.isdigit() or not 1 <= int(samples_text) <= review.MAX_SAMPLES:
            raise ConfigError(
                f"{MAX_SAMPLES_ENV}: must be a whole number from 1 to {review.MAX_SAMPLES}, "
                f"got {samples_text!r}"
            )
        max_samples = int(samples_text)
    else:
        max_samples = DEFAULT_MAX_SAMPLES
    delay = 0.0
    if dry_run and env.get(DRY_RUN_DELAY_ENV, "").strip():  # honoured only in dry run
        raw = env[DRY_RUN_DELAY_ENV].strip()
        try:
            delay = float(Decimal(raw))
        except InvalidOperation:
            raise ConfigError(f"{DRY_RUN_DELAY_ENV}: {raw!r} is not a number") from None
        if not 0 <= delay <= MAX_DRY_RUN_DELAY_S:
            raise ConfigError(f"{DRY_RUN_DELAY_ENV}: must be from 0 to {MAX_DRY_RUN_DELAY_S:g} seconds")
    return LiveConfig(
        hosted=hosted,
        access_code=code if code.strip() else None,
        budget_nano=budget_nano,
        data_dir=_data_dir(env, hosted),
        max_samples=max_samples,
        dry_run=dry_run,
        dry_run_delay_s=delay,
    )


def hosted_problems(cfg: LiveConfig, env: Mapping[str, str]) -> list[str]:
    """Why hosted live mode is unavailable (variable names only, never values)."""
    problems: list[str] = []
    if cfg.access_code is None:
        problems.append(f"{ACCESS_CODE_ENV} is not set")
    if cfg.budget_nano is None:
        problems.append(f"{BUDGET_ENV} is not set")
    if cfg.data_dir is None:
        problems.append(f"{DATA_DIR_ENV} is not set (required in hosted mode)")
    if not cfg.dry_run:
        for provider in (openai_responses.PROVIDER, gemini.PROVIDER):
            if not env.get(review.key_env(provider)):
                problems.append(f"{review.key_env(provider)} is not set")
    return problems


_logged: set[str] = set()


def log_once(message: str) -> None:
    """Log a server-side warning once per process (the page reruns on every click)."""
    if message not in _logged:
        _logged.add(message)
        log.warning(message)


def open_ledger(cfg: LiveConfig) -> Ledger:
    """The ledger, proven writable and readable. Raises LedgerError otherwise."""
    if cfg.budget_nano is None:
        raise ConfigError(f"{BUDGET_ENV} is not set")
    ledger = Ledger(cfg.ledger_path, cfg.budget_nano)
    ledger.ensure_writable()
    ledger.state()
    return ledger


# ------------------------------------------------------------------- access gate

_GATE_LOCK = threading.Lock()
_gate: dict[str, float] = {"failures": 0, "until": 0.0}
clock: Callable[[], float] = time.monotonic  # tests replace it


def gate_wait_s() -> float:
    """Seconds left in the process-wide cooldown (0 when attempts are allowed)."""
    with _GATE_LOCK:
        return max(0.0, _gate["until"] - clock())


def try_unlock(entered: str, expected: str | None) -> Literal["unlocked", "wrong", "cooldown", "empty"]:
    """Constant-time comparison of UTF-8 bytes. Failed attempts count process-wide."""
    if not expected:  # compare_digest(b"", b"") is True: an empty code never unlocks
        raise ValueError("no access code is configured")
    with _GATE_LOCK:
        now = clock()
        if now < _gate["until"]:
            return "cooldown"
        if not entered:
            return "empty"
        if hmac.compare_digest(entered.encode("utf-8"), expected.encode("utf-8")):
            _gate["failures"] = 0
            return "unlocked"
        _gate["failures"] += 1
        log.warning("live mode: a wrong access code was entered (%d in a row)", int(_gate["failures"]))
        if _gate["failures"] >= MAX_FAILED_ATTEMPTS:
            _gate["failures"] = 0
            _gate["until"] = now + COOLDOWN_S
            log.warning("live mode: access code cooldown for %g s", COOLDOWN_S)
            return "cooldown"
        return "wrong"


def reset_gate() -> None:
    """For tests."""
    with _GATE_LOCK:
        _gate["failures"] = 0
        _gate["until"] = 0.0


# ---------------------------------------------------------------- per-run limits


def validate_run(
    prompt_text: str, case_text: str, models: list[str], samples: Any, max_samples: int
) -> list[str]:
    """Every reason the run can't start; empty when it can. No call is made."""
    errors: list[str] = []
    if not models:
        errors.append("Select at least one model.")
    unknown = [m for m in models if m not in review.MODEL_CHOICES]
    if unknown:
        errors.append(f"Unsupported model(s): {', '.join(unknown)}.")
    if len(set(models)) != len(models):
        errors.append("A model is selected twice.")
    if type(samples) is not int or not 1 <= samples <= max_samples:
        errors.append(f"Samples must be from 1 to {max_samples}.")
    if not prompt_text.strip():
        errors.append("Prompt: the prompt is empty.")
    elif len(prompt_text) > MAX_PROMPT_CHARS:
        errors.append(f"Prompt: {len(prompt_text):,} characters; the limit is {MAX_PROMPT_CHARS:,}.")
    if len(case_text) > MAX_TRANSCRIPT_CHARS:
        errors.append(f"Transcript: {len(case_text):,} characters; the limit is {MAX_TRANSCRIPT_CHARS:,}.")
    else:
        try:
            turns = parse_transcript(case_text)
        except TranscriptError as exc:
            errors.append(f"Transcript: line {exc.line}: {exc.reason}")
        else:
            if len(turns) > MAX_TURNS:
                errors.append(f"Transcript: {len(turns)} turns; the limit is {MAX_TURNS}.")
    return errors


# -------------------------------------------------------------------- projection


@dataclass(frozen=True)
class Projection:
    generation_nano: int
    judge_nano: int
    generation_calls: int
    judge_calls: int

    @property
    def total_nano(self) -> int:
        return self.generation_nano + self.judge_nano


def _settings(model: str, effort: str, thinking: str) -> dict[str, Any]:
    if review.provider_for(model) == openai_responses.PROVIDER:
        return {"reasoning_effort": effort, "max_output_tokens": OUTPUT_CAP}
    return {"thinking_level": thinking, "max_output_tokens": OUTPUT_CAP}


def project_run(
    prompt: InputFile, case: InputFile, models: list[str], samples: int,
    effort: str = HOSTED_REASONING_EFFORT, thinking: str = HOSTED_THINKING_LEVEL,
) -> Projection:
    """The run's maximum cost: the sum of every call's maximum, from the real requests.

    Generation requests are built exactly as the runner builds them. Judge requests
    are built with a placeholder reply of OUTPUT_CAP x PROJECTED_REPLY_BYTES_PER_TOKEN
    bytes (see that constant).
    """
    turns = parse_transcript(case.text)
    gen = 0
    for model in models:
        spec = ModelSpec(model, review.provider_for(model), _settings(model, effort, thinking), {})
        request = _build_request(spec, prompt.text, turns)
        gen += max_call_cost(request, model, OUTPUT_CAP) * samples
    judge = scoring.load_judge_prompt(JUDGE_VERSION)
    criteria = scoring.load_criteria(review.NOTES_PATH).get(case.stem)
    placeholder = "x" * (OUTPUT_CAP * PROJECTED_REPLY_BYTES_PER_TOKEN)
    jreq = scoring.build_judge_request(
        judge.text, turns, placeholder, criteria, scorer_version=judge.scorer_version
    )
    replies = len(models) * samples
    per_judge = max_call_cost(jreq, jreq["model"], jreq["max_output_tokens"])
    return Projection(gen, per_judge * replies, replies, replies)


# --------------------------------------------------------------------- clients


def _no_retry_openai() -> Any:
    from openai import OpenAI

    return OpenAI(max_retries=0)


def _no_retry_gemini() -> Any:
    return gemini.make_client(os.environ[gemini.API_KEY_ENV], gemini.NO_RETRY_OPTIONS)


# provider -> zero-argument factory for a client that makes exactly one HTTP request
# per call. Tests replace this mapping.
GENERATION_FACTORIES: dict[str, Callable[[], Any]] = {
    openai_responses.PROVIDER: _no_retry_openai,
    gemini.PROVIDER: _no_retry_gemini,
}


def guarded_clients(cfg: LiveConfig, ledger: Ledger, providers: list[str]) -> tuple[dict[str, Any], Any]:
    """(generation clients by provider, judge client), all behind the ledger.

    In dry run only the offline fakes are built, whatever keys exist. Otherwise the
    keys are checked first, then the no-retry factories are called.
    """
    if cfg.dry_run:
        openai_inner: Any = dryrun.DryRunOpenAI(cfg.dry_run_delay_s)
        inner = {
            p: openai_inner if p == openai_responses.PROVIDER else dryrun.DryRunGemini(cfg.dry_run_delay_s)
            for p in providers
        }
    else:
        review._require_keys(list(dict.fromkeys([*providers, openai_responses.PROVIDER])))
        openai_inner = GENERATION_FACTORIES[openai_responses.PROVIDER]()
        inner = {
            p: openai_inner if p == openai_responses.PROVIDER else GENERATION_FACTORIES[p]()
            for p in providers
        }
    return guard_clients(inner, openai_inner, ledger)


# ----------------------------------------------------------------- orchestration

_RUN_LOCK = threading.Lock()  # at most one paid run at a time per process


@dataclass
class FreshOutcome:
    run_id: str
    run_dir: Path
    messages: list[str] = field(default_factory=list)  # safe to show on a public page
    generation: RunResult | None = None


def _safe_abort(result: RunResult) -> str | None:
    """The runner's abort message without the provider's error text."""
    if result.abort_message is None:
        return None
    err = next((r["error"] for r in reversed(result.records) if r.get("error")), {})
    return (
        f"Generation stopped after a fatal provider error ({err.get('type')}, HTTP "
        f"{err.get('status_code')}); the remaining replies were not attempted."
    )


def run_fresh(
    cfg: LiveConfig,
    prompt: InputFile,
    case: InputFile,
    models: list[str],
    samples: int,
    on_slot: Callable[[dict[str, Any]], None] | None = None,
    effort: str = HOSTED_REASONING_EFFORT,
    thinking: str = HOSTED_THINKING_LEVEL,
    on_start: Callable[[str], None] | None = None,
) -> FreshOutcome:
    """Generate and score one fresh run under the data directory, behind the ledger.

    Raises RunInputError for invalid input, RunBusy when another run is in progress,
    BudgetExceeded when the projection exceeds the remaining budget (no call made),
    and LedgerError when the ledger can't be used. A budget refusal in the middle of
    the run stops it and is reported in the outcome's messages. `on_start(run_id)`
    is called before the first paid call, so an interrupted run can still be shown.
    """
    errors = validate_run(prompt.text, case.text, models, samples, cfg.max_samples)
    if errors:
        raise RunInputError(" ".join(errors))
    if not _RUN_LOCK.acquire(blocking=False):
        raise RunBusy("Another run is in progress, try again shortly.")
    try:
        ledger = open_ledger(cfg)
        projection = project_run(prompt, case, models, samples, effort, thinking)
        remaining = ledger.remaining()  # re-checked under the run lock
        if projection.total_nano > remaining:
            raise BudgetExceeded(
                "This run's projected maximum cost is more than the remaining budget; "
                "no call was made. Choose fewer models or samples."
            )
        gen_clients, judge_client = guarded_clients(cfg, ledger, review.providers_for(models))
        run_id = new_run_id()
        outcome = FreshOutcome(run_id, cfg.runs_dir / run_id)
        if on_start is not None:
            on_start(run_id)
        try:
            _, result = review.generate(
                prompt, case, models, samples, effort, thinking,
                runs_dir=cfg.runs_dir, on_slot=on_slot, clients=gen_clients,
                max_output_tokens=OUTPUT_CAP, gemini_retry_options=gemini.NO_RETRY_OPTIONS,
                run_id=run_id,
            )
        except BudgetExceeded as exc:
            outcome.messages.append(f"Generation stopped: {exc}. Replies not generated are shown as missing.")
        else:
            outcome.generation = result
            if (msg := _safe_abort(result)) is not None:
                outcome.messages.append(msg)
        if not outcome.run_dir.is_dir():
            return outcome  # create_run never ran: nothing to score
        try:
            _, scored = review.score_run(
                outcome.run_dir, JUDGE_VERSION, scores_dir=cfg.scores_dir, client=judge_client
            )
        except BudgetExceeded as exc:
            outcome.messages.append(f"Scoring stopped: {exc}. Replies not scored are shown as unscored.")
        else:
            if scored.fatal_message is not None:
                err = next(
                    (o.record.get("error") for o in reversed(scored.outcomes) if o.record and o.record.get("error")),
                    None,
                ) or {}
                outcome.messages.append(
                    f"Scoring stopped after a fatal judge error ({err.get('type')}, HTTP "
                    f"{err.get('status_code')}); no further judge calls were made."
                )
        return outcome
    finally:
        _RUN_LOCK.release()


def run_lock() -> threading.Lock:
    """The process-wide paid-run lock (local budgeted runs take it too)."""
    return _RUN_LOCK
