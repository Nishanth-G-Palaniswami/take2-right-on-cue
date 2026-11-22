"""Data loading and joining for the Streamlit app: saved runs, their scores, new runs.

Plain functions over the existing run and score files. Nothing here talks to the
Streamlit package, and every API client comes from `CLIENT_FACTORIES`, which tests
replace so that no real request is ever made.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from dotenv import load_dotenv

from . import gemini, openai_responses, scoring
from .runs import (
    PROVIDERS,
    InputFile,
    ModelSpec,
    RunResult,
    create_run,
    load_manifest,
    make_slot_key,
    manifest_models,
    new_run_id,
    provider_for,
    read_slots,
    run_slots,
)
from .transcript import TranscriptError, Turn, parse_transcript

REPO_ROOT = Path(__file__).resolve().parents[2]
# Module-level so tests (and a deployment) can point the app somewhere else. The app
# reads them at call time, never copies them at import.
RUNS_DIR = REPO_ROOT / "runs"
SCORES_DIR = REPO_ROOT / "scores"
NOTES_PATH = REPO_ROOT / "cases" / "notes.toml"
PROMPTS_DIR = REPO_ROOT / "prompts"
CASES_DIRS = (REPO_ROOT / "cases" / "dev", REPO_ROOT / "cases" / "holdout")
HOLDOUT_DIR = REPO_ROOT / "holdout"
REVIEW_SHEET = HOLDOUT_DIR / "review" / "review_sheet.md"
CRITICAL_REVIEW = HOLDOUT_DIR / "review" / "critical_review.md"
REVEALED_KEY = HOLDOUT_DIR / "revealed" / "review_key.json"
PAIR_COMPARE = HOLDOUT_DIR / "results" / "pair_compare.json"
REVIEW_COMPARE = HOLDOUT_DIR / "results" / "review_compare.json"
DOCS_DIR = REPO_ROOT / "docs"
HOSTED_ENV = "RIGHTONCUE_HOSTED"
PROMPT_CHOICES = ("v1", "v2")
MODEL_CHOICES = ("gpt-5.4", "gpt-5.4-mini", "gemini-3.5-flash")
REASONING_EFFORTS = ("none", "low")
DEFAULT_THINKING_LEVEL = "MINIMAL"
MAX_SAMPLES = 5
PASTED_PROMPT_PATH = "pasted/prompt.md"
PASTED_CASE_PATH = "pasted/transcript.jsonl"

Decision = Literal["acceptable", "not acceptable", "needs review", "judge failed", "unscored"]
CardState = Literal["reply", "generation_failed", "incomplete", "missing", "duplicate"]
_STATE_NOTE: dict[str, str] = {
    "generation_failed": "Generation failed: no reply was produced.",
    "incomplete": "Incomplete: the API stopped before the reply was finished. No reply is shown.",
    "missing": "Missing: this reply was never attempted (no saved record).",
    "duplicate": "More than one saved record for this reply; none is shown.",
}
_FAILED_STATUS_LABEL: dict[str, Decision] = {
    "needs_review": "needs review",
    "judge_failed": "judge failed",
}


# ----------------------------------------------------------------------- keys / clients


def load_env() -> None:
    """Read .env into the environment without overriding real variables (as the CLI)."""
    load_dotenv(REPO_ROOT / ".env", override=False)


def key_env(provider: str) -> str:
    return PROVIDERS[provider].API_KEY_ENV


def key_present(provider: str) -> bool:
    """Whether the provider's key is set. Never returns or logs the value."""
    return bool(os.environ.get(key_env(provider)))


def _make_openai_client() -> Any:
    from openai import OpenAI

    return OpenAI()


def _make_gemini_client() -> Any:
    return gemini.make_client(os.environ[gemini.API_KEY_ENV])


# provider name -> zero-argument client factory. Tests replace this mapping.
CLIENT_FACTORIES: dict[str, Callable[[], Any]] = {
    openai_responses.PROVIDER: _make_openai_client,
    gemini.PROVIDER: _make_gemini_client,
}


def _require_keys(providers: list[str]) -> None:
    missing = [key_env(p) for p in providers if not key_present(p)]
    if missing:
        raise ValueError(f"{', '.join(missing)} is not set; no request was made")


# --------------------------------------------------------------------------- view model


@dataclass
class DimensionView:
    label: str
    score: int
    rationale: str
    evidence: list[str]


@dataclass
class ViolationView:
    type: str
    rationale: str


@dataclass
class CriticalFinding:
    """The owner's review of one critical flag the judge listed."""

    neutral_id: str
    type: str
    finding: str


@dataclass
class Card:
    case_id: str
    model: str
    sample_index: int
    state: CardState
    slot_key: str = ""
    reply: str | None = None
    reported_model: str | None = None
    note: str = ""
    decision: Decision | None = None  # None when there is no reply to decide on
    scores: dict[str, int] | None = None
    total: int | None = None
    single_turn_pass: bool | None = None
    single_turn_failures: list[str] = field(default_factory=list)
    flags: list[str] = field(default_factory=list)
    reasons: list[str] = field(default_factory=list)  # the decision's reasons
    violations: list[ViolationView] = field(default_factory=list)
    dimensions: list[DimensionView] = field(default_factory=list)
    criteria_source: str | None = None
    neutral_id: str | None = None  # the holdout review's ID for this reply
    human_accept: bool | None = None  # the owner's accept (True) / reject (False)
    critical_findings: list[CriticalFinding] = field(default_factory=list)
    error_type: str | None = None  # a failed generation's error type and HTTP status
    error_status: int | None = None
    failed_judge_attempts: int = 0  # needs_review / judge_failed records for this reply

    @property
    def operational_failure(self) -> bool:
        return self.state != "reply"


@dataclass
class CaseView:
    case_id: str
    turns: list[Turn]
    previous_riley: str | None
    applicant_last: str
    cards: dict[str, list[Card]]  # requested model -> cards by sample


@dataclass
class ModelInfo:
    requested: str
    provider: str
    settings: dict[str, Any]
    reported: list[str]


@dataclass
class RunView:
    run_id: str
    prompt_version: str
    samples: int
    models: list[ModelInfo]
    case_ids: list[str]
    judge_versions: list[str]  # versions present in the score file
    judge_version: str | None  # the one used for the cards
    cases: list[CaseView]

    def all_cards(self) -> list[Card]:
        return [c for case in self.cases for cards in case.cards.values() for c in cards]


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def scores_path_for(run_id: str, scores_dir: Path | None = None) -> Path:
    return (scores_dir or SCORES_DIR) / f"{run_id}.jsonl"


def list_scored_runs(runs_dir: Path | None = None, scores_dir: Path | None = None) -> list[str]:
    """Run IDs that have a score file and a manifest, newest first."""
    runs_dir = runs_dir or RUNS_DIR
    scores_dir = scores_dir or SCORES_DIR
    if not scores_dir.is_dir():
        return []
    ids = [
        p.stem
        for p in scores_dir.glob("*.jsonl")  # top level only: draw-2/ etc. are folders
        if p.is_file() and (runs_dir / p.stem / "manifest.json").is_file()
    ]
    return sorted(ids, reverse=True)


def judge_versions_in(records: list[dict[str, Any]]) -> list[str]:
    """Judge versions that have a record in the score file, registry order first."""
    found = {r["judge_prompt_version"] for r in records if r.get("judge_prompt_version")}
    known = [v for v in scoring.JUDGE_PROMPTS if v in found]
    return known + sorted(found - set(known))


def pick_score_record(
    records: list[dict[str, Any]], slot_key: str, text: str, judge_version: str
) -> dict[str, Any] | None:
    """The record shown for a slot under one judge version.

    The first `scored` record for this slot, judge version and exact reply text, as
    the scorer reuses it. Without one, the latest `needs_review` / `judge_failed` /
    `budget_stopped` record for the same words. A `judge_pending` record is never a
    score.
    """
    mine = [
        r
        for r in records
        if r.get("slot_key") == slot_key
        and r.get("judge_prompt_version") == judge_version
        and r.get("text_sha256") == _sha(text)
    ]
    scored = next((r for r in mine if r.get("status") == "scored"), None)
    if scored is not None:
        return scored
    failed = [r for r in mine if r.get("status") in ("needs_review", "judge_failed", "budget_stopped")]
    return failed[-1] if failed else None


def failed_judge_attempts(
    records: list[dict[str, Any]], slot_key: str, text: str, judge_version: str
) -> int:
    """Judge attempts for a slot, judge version and exact reply text that produced no
    valid judgment (`needs_review` or `judge_failed`). `budget_stopped` made no call."""
    return sum(
        1
        for r in records
        if r.get("slot_key") == slot_key
        and r.get("judge_prompt_version") == judge_version
        and r.get("text_sha256") == _sha(text)
        and r.get("status") in ("needs_review", "judge_failed")
    )


def _violations(record: dict[str, Any]) -> list[ViolationView]:
    judgment = record.get("judgment")
    if judgment is None:
        return []
    version = record.get("scorer_version")
    cvs = judgment["critical_violations"]
    if version == "scorer-1":
        return [ViolationView(cv["type"], cv["rationale"]) for cv in cvs]
    if version == "scorer-2":  # one entry per type; only present ones count
        return [ViolationView(name, e["rationale"]) for name, e in cvs.items() if e["present"]]
    raise ValueError(f"unknown scorer version {version!r} in a score record")


def _apply_record(card: Card, record: dict[str, Any]) -> None:
    status = record["status"]
    card.criteria_source = record.get("criteria_source")
    structural = record.get("structural")
    if structural is not None:
        card.single_turn_pass = structural["single_turn_pass"]
        card.single_turn_failures = list(structural["failures"])
        card.flags = list(structural["diagnostics"]["flags"])
    decision = record.get("decision")
    if status == "scored":
        card.decision = "acceptable" if decision["acceptable"] else "not acceptable"
    else:
        card.decision = _FAILED_STATUS_LABEL.get(status, "unscored")
    if decision is not None:
        card.scores = decision["scores"]
        card.total = decision["total"]
        if card.decision != "acceptable":
            card.reasons = list(decision["reasons"])
    judgment = record.get("judgment")
    if judgment is not None:
        card.violations = _violations(record)
        card.dimensions = [
            DimensionView(
                scoring.DIMENSION_LABELS[d],
                judgment[d]["score"],
                judgment[d]["rationale"],
                [f"({e['source']}) \"{e['quote']}\"" for e in judgment[d]["evidence"]],
            )
            for d in scoring.DIMENSIONS
        ]


def _build_card(
    case_id: str,
    model: str,
    idx: int,
    slot_key: str,
    recs: list[dict[str, Any]],
    scores: list[dict[str, Any]],
    judge_version: str | None,
) -> Card:
    if not recs:
        return Card(case_id, model, idx, "missing", slot_key, note=_STATE_NOTE["missing"])
    if len(recs) > 1:
        return Card(case_id, model, idx, "duplicate", slot_key, note=_STATE_NOTE["duplicate"])
    slot = recs[0]
    status = slot.get("status")
    reported = slot.get("returned_model")
    if status in ("generation_failed", "incomplete"):
        note = _STATE_NOTE[status]
        err = slot.get("error")
        if err:
            note += f" {err.get('type')}: {err.get('message')}"
        card = Card(case_id, model, idx, status, slot_key, reported_model=reported, note=note)
        if err:
            card.error_type, card.error_status = err.get("type"), err.get("status_code")
        return card
    if status != "ok":
        raise ValueError(f"slot {slot.get('slot_key')} has unknown status {status!r}")
    text = slot.get("output_text")
    if not isinstance(text, str):
        raise ValueError(f"slot {slot.get('slot_key')} has status ok but no output_text")
    card = Card(case_id, model, idx, "reply", slot_key, reply=text, reported_model=reported, decision="unscored")
    if judge_version is not None:
        record = pick_score_record(scores, slot_key, text, judge_version)
        if record is not None:
            _apply_record(card, record)
        card.failed_judge_attempts = failed_judge_attempts(scores, slot_key, text, judge_version)
    return card


def load_run_view(
    run_dir: Path, scores_path: Path | None, judge_version: str | None
) -> RunView:
    """Join the manifest, the slots and the score records of one run.

    Without a score file (or a judge version) every reply shows as unscored.
    """
    manifest = load_manifest(run_dir)
    run_id = manifest["run_id"]
    version = manifest["prompt"]["version"]
    samples = manifest["samples_per_case"]
    specs = manifest_models(manifest)
    slots = read_slots(run_dir)
    by_key: dict[str, list[dict[str, Any]]] = {}
    for s in slots:
        by_key.setdefault(s["slot_key"], []).append(s)
    scores = scoring.read_score_records(scores_path) if scores_path is not None else []
    versions = judge_versions_in(scores)
    if judge_version is not None and judge_version not in versions:
        raise ValueError(f"judge version {judge_version!r} has no record for run {run_id}")

    models: list[ModelInfo] = []
    for spec in specs:
        answered = [
            s for s in slots if s.get("requested_model") == spec["model"] and s.get("raw_response") is not None
        ]
        reported = sorted({s["returned_model"] for s in answered if s.get("returned_model")})
        if any(not s.get("returned_model") for s in answered):
            reported.append("served version unconfirmed")
        models.append(ModelInfo(spec["model"], spec["provider"], spec["settings"], reported))

    cases: list[CaseView] = []
    for case in manifest["cases"]:
        cid = case["case_id"]
        turns = [Turn.model_validate(t) for t in case["turns"]]
        previous = next((t.utterance for t in reversed(turns[:-1]) if t.role == "agent"), None)
        cards = {
            spec["model"]: [
                _build_card(
                    cid,
                    spec["model"],
                    i,
                    make_slot_key(run_id, cid, version, spec["model"], i),
                    by_key.get(make_slot_key(run_id, cid, version, spec["model"], i), []),
                    scores,
                    judge_version,
                )
                for i in range(1, samples + 1)
            ]
            for spec in specs
        }
        cases.append(CaseView(cid, turns, previous, turns[-1].utterance, cards))
    return RunView(
        run_id, version, samples, models, [c["case_id"] for c in manifest["cases"]],
        versions, judge_version, cases,
    )


def default_judge_version(versions: list[str]) -> str | None:
    if scoring.DEFAULT_JUDGE_VERSION in versions:
        return scoring.DEFAULT_JUDGE_VERSION
    return versions[0] if versions else None


# ------------------------------------------------------------------ run evaluation


def list_prompt_files() -> list[Path]:
    return [PROMPTS_DIR / f"{v}.md" for v in PROMPT_CHOICES]


def list_case_files() -> list[Path]:
    return [p for d in CASES_DIRS if d.is_dir() for p in sorted(d.glob("*.jsonl"))]


def read_input(path: Path) -> InputFile:
    """An InputFile whose path is repo-relative (as the CLI records it)."""
    try:
        shown = path.resolve().relative_to(REPO_ROOT).as_posix()
    except ValueError:
        shown = path.as_posix()
    return InputFile(path=shown, raw=path.read_bytes())


def pasted_prompt(text: str) -> InputFile:
    return InputFile(PASTED_PROMPT_PATH, text.encode("utf-8"))


def pasted_case(text: str) -> InputFile:
    return InputFile(PASTED_CASE_PATH, text.encode("utf-8"))


def transcript_error(text: str) -> str | None:
    """A clear message if the text isn't a valid transcript, else None."""
    try:
        parse_transcript(text)
    except TranscriptError as exc:
        return f"line {exc.line}: {exc.reason}"
    return None


def prompt_error(text: str) -> str | None:
    return None if text.strip() else "the prompt is empty"


def generation_calls(models: list[str], samples: int, cases: int = 1) -> int:
    return len(models) * samples * cases


def providers_for(models: list[str]) -> list[str]:
    return list(dict.fromkeys(provider_for(m) for m in models))


def blocked_models(models: list[str]) -> dict[str, str]:
    """Selected models that can't be used, with the reason (a missing key)."""
    out: dict[str, str] = {}
    for m in models:
        provider = provider_for(m)
        if not key_present(provider):
            out[m] = f"{key_env(provider)} is not set"
    return out


def generate(
    prompt: InputFile,
    case: InputFile,
    models: list[str],
    samples: int,
    reasoning_effort: str,
    thinking_level: str,
    runs_dir: Path | None = None,
    on_slot: Callable[[dict[str, Any]], None] | None = None,
    *,
    clients: dict[str, Any] | None = None,
    max_output_tokens: int | None = None,
    gemini_retry_options: dict[str, Any] | None = None,
    run_id: str | None = None,
) -> tuple[Path, RunResult]:
    """Create a run under `runs_dir` and generate every reply, with the existing runner.

    Raises ValueError for invalid input or a missing key, before any client exists.
    `clients` (provider -> client) replaces the key check and CLIENT_FACTORIES; the
    caller is then responsible for them (the spending guard, dry run).
    `max_output_tokens` caps every reply (recorded in the manifest);
    `gemini_retry_options` is what the given Gemini client was built with, for the
    manifest. Without these the run is exactly as before.
    """
    runs_dir = runs_dir or RUNS_DIR
    if not models:
        raise ValueError("select at least one model")
    if not 1 <= samples <= MAX_SAMPLES:
        raise ValueError(f"samples must be between 1 and {MAX_SAMPLES}")
    if (msg := prompt_error(prompt.text)) is not None:
        raise ValueError(msg)
    if (msg := transcript_error(case.text)) is not None:
        raise ValueError(f"transcript {msg}")
    providers = providers_for(models)
    if clients is None:
        _require_keys(providers)
        clients = {p: CLIENT_FACTORIES[p]() for p in providers}
    else:
        missing = [p for p in providers if p not in clients]
        if missing:
            raise ValueError(f"no client for provider(s): {', '.join(missing)}")
    specs: list[ModelSpec] = []
    for model in models:
        provider = provider_for(model)
        if provider == openai_responses.PROVIDER:
            specs.append(
                ModelSpec(
                    model, provider, {"reasoning_effort": reasoning_effort},
                    openai_responses.client_settings(clients[provider]),
                )
            )
        else:
            specs.append(
                ModelSpec(
                    model, provider, {"thinking_level": thinking_level},
                    gemini.client_settings(gemini_retry_options),
                )
            )
    run_dir, manifest = create_run(
        runs_dir, run_id or new_run_id(), prompt, [case], specs, samples, max_output_tokens
    )
    result = run_slots(clients, run_dir, manifest, on_slot=on_slot)
    return run_dir, result


def judge_calls_needed(view: RunView) -> int:
    """Replies that have no scored record yet and are not empty (one judge call each)."""
    return sum(
        1
        for c in view.all_cards()
        if c.state == "reply" and c.decision != "acceptable" and c.decision != "not acceptable"
        and (c.reply or "").strip()
    )


def score_run(
    run_dir: Path,
    judge_version: str = scoring.DEFAULT_JUDGE_VERSION,
    scores_dir: Path | None = None,
    on_outcome: Callable[[scoring.Outcome], None] | None = None,
    *,
    client: Any | None = None,
) -> tuple[scoring.ScoringPlan, scoring.ScoringResult]:
    """Score a run with the existing scorer. Needs OPENAI_API_KEY when a call is needed,
    unless a judge `client` is given (the spending guard, dry run)."""
    judge = scoring.load_judge_prompt(judge_version)
    plan = scoring.plan_scoring(run_dir, scores_dir or SCORES_DIR, NOTES_PATH, judge)
    if plan.calls_needed and client is None:
        _require_keys([openai_responses.PROVIDER])
        client = CLIENT_FACTORIES[openai_responses.PROVIDER]()
    return plan, scoring.execute_plan(plan, client if plan.calls_needed else None, on_outcome=on_outcome)


def redact_provider_errors(view: RunView) -> None:
    """For a public page: keep only the error type and HTTP status on failed cards, and
    replace judge-failure reasons. Provider error text can echo request details (an
    OpenAI 401 names a masked key fragment)."""
    for card in view.all_cards():
        if card.state in ("generation_failed", "incomplete"):
            card.note = _STATE_NOTE[card.state]
            if card.error_type:
                status = f" (HTTP {card.error_status})" if card.error_status else ""
                card.note += f" {card.error_type}{status}."
        if card.decision == "judge failed":
            card.reasons = ["The judge call failed; the details are in the server's score file."]


# ------------------------------------------------------------- holdout human review


@dataclass
class PairChoice:
    """One of the owner's pair choices (prompt v2). `human` is "A" (left), "B" or "tie"."""

    pair_id: str
    case: str
    left_model: str
    left_sample: int
    right_model: str
    right_sample: int
    human: str
    reason: str

    @property
    def preferred(self) -> tuple[str, int] | None:
        if self.human == "A":
            return self.left_model, self.left_sample
        if self.human == "B":
            return self.right_model, self.right_sample
        return None


@dataclass
class Headline:
    individual_agree: int
    individual_evaluable: int
    pair_exact: int
    pair_evaluable: int


@dataclass
class HoldoutData:
    run_by_prompt: dict[str, str]  # prompt version -> run id
    accept_by_slot: dict[str, bool]  # slot key -> the owner's accept (True) / reject
    id_by_slot: dict[str, str]  # slot key -> neutral ID
    findings: dict[str, list[CriticalFinding]]  # neutral ID -> reviewed critical flags
    pairs: list[PairChoice]
    headline: Headline


_ACCEPT_LINE = re.compile(r"^Accept (\S+)\? \(y/n\):[ \t]*(.*?)[ \t]*$", re.MULTILINE)


def parse_review_sheet(text: str) -> dict[str, bool]:
    """Neutral ID -> accepted, from the `Accept <ID>? (y/n): y|n` lines."""
    out: dict[str, bool] = {}
    for m in _ACCEPT_LINE.finditer(text):
        neutral, value = m.group(1), m.group(2)
        if value not in ("y", "n"):
            raise ValueError(f"review sheet: {neutral} has {value!r}, expected y or n")
        if neutral in out:
            raise ValueError(f"review sheet: {neutral} appears more than once")
        out[neutral] = value == "y"
    return out


def parse_critical_review(text: str) -> dict[str, list[CriticalFinding]]:
    """Neutral ID -> findings, from the rows of the critical review's table."""
    out: dict[str, list[CriticalFinding]] = {}
    for line in text.splitlines():
        if not re.match(r"^\| H\d+-\d+ \| `", line):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split(" | ")]
        neutral, kind, finding = cells[0], cells[1].strip("`"), cells[-1]
        out.setdefault(neutral, []).append(CriticalFinding(neutral, kind, finding.replace("**", "")))
    return out


def load_holdout() -> HoldoutData:
    """The owner's committed human review, joined through the revealed key."""
    key = json.loads(REVEALED_KEY.read_text(encoding="utf-8"))
    accepts = parse_review_sheet(REVIEW_SHEET.read_text(encoding="utf-8"))
    entries: dict[str, dict[str, Any]] = key["entries"]
    if set(entries) != set(accepts):
        raise ValueError("the revealed key and the review sheet list different IDs")
    run_by_prompt = {e["prompt_version"]: e["run_id"] for e in entries.values()}
    pair_doc = json.loads(PAIR_COMPARE.read_text(encoding="utf-8"))
    pairs = [
        PairChoice(
            p["pair_id"], p["case"], p["left"]["model"], p["left"]["sample"],
            p["right"]["model"], p["right"]["sample"], p["human"], p["human_reason"],
        )
        for p in pair_doc["pairs"]
        if p["shown"] and p["human"]
    ]
    summary = pair_doc["summary"]
    review_doc = json.loads(REVIEW_COMPARE.read_text(encoding="utf-8"))
    rows = review_doc["by_prompt_model"]
    return HoldoutData(
        run_by_prompt=run_by_prompt,
        accept_by_slot={e["slot_key"]: accepts[i] for i, e in entries.items()},
        id_by_slot={e["slot_key"]: i for i, e in entries.items()},
        findings=parse_critical_review(CRITICAL_REVIEW.read_text(encoding="utf-8")),
        pairs=pairs,
        headline=Headline(
            sum(r["agree"] for r in rows), sum(r["evaluable"] for r in rows),
            summary["exact_matches"], summary["evaluable"],
        ),
    )


def annotate_holdout(view: RunView, holdout: HoldoutData) -> None:
    """Attach the owner's label and reviewed critical flags to the view's cards."""
    for card in view.all_cards():
        if card.state != "reply" or card.slot_key not in holdout.id_by_slot:
            continue
        card.neutral_id = holdout.id_by_slot[card.slot_key]
        card.human_accept = holdout.accept_by_slot[card.slot_key]
        by_type = {f.type: f for f in holdout.findings.get(card.neutral_id, [])}
        card.critical_findings = [by_type[v.type] for v in card.violations if v.type in by_type]


def pairs_for(holdout: HoldoutData, case: str) -> list[PairChoice]:
    return [p for p in holdout.pairs if p.case == case]


def read_doc(relative: str) -> str | None:
    """A committed document's text, or None if the file isn't in this checkout."""
    path = REPO_ROOT / relative
    return path.read_text(encoding="utf-8").lstrip("﻿") if path.is_file() else None


def hosted() -> bool:
    return os.environ.get(HOSTED_ENV) == "1"
