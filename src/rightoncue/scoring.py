"""Score saved replies: structural checks in code, a fixed judge, a code decision.

The judge sees only the judge prompt, the case criteria, the transcript turns and
the reply text. Scores are appended to `scores/<run_id>.jsonl`; nothing inside the
run folder is written, and only `manifest.json` and `slots.jsonl` are read there.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import tomllib
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Any, Literal, TypedDict

from pydantic import BaseModel, ConfigDict, Field, StrictInt, StrictStr, ValidationError

from . import openai_responses
from .runs import SCHEMA_VERSION, load_manifest, make_slot_key, manifest_models
from .transcript import Turn

SCORER_VERSION = "scorer-1"
JUDGE_PROMPT_PATH = Path("prompts/judge.md")
JUDGE_PROMPT_VERSION = "judge-v1"
JUDGE_PROMPT_SHA256 = "6df7af131725adbea3e4f71434ba6ebdc35b4451875a3cebbb63d6813b156af9"
JUDGE_MODEL = "gpt-5.4-mini"
JUDGE_SETTINGS: dict[str, Any] = {"reasoning_effort": "none", "max_output_tokens": 1500}
LONG_REPLY_WORDS = 40

DIMENSIONS = ("next_action", "listening_context", "grounding_role", "spoken_delivery")
DIMENSION_LABELS = {
    "next_action": "next action",
    "listening_context": "listening",
    "grounding_role": "grounding",
    "spoken_delivery": "delivery",
}
CRITICAL_TYPES = (
    "screening_without_consent",
    "invented_employment_fact",
    "promised_hiring_outcome",
    "clinical_or_legal_advice",
)
EMPTY_REPLY_REASON = "empty completed reply fails the single-turn requirement"
GENERAL_RUBRIC_TEXT = (
    "None for this case. Judge with the general rubric: the call brief and the "
    "conversation only."
)


class ScoringInputError(ValueError):
    """An input or configuration problem found before any judge call."""


# ------------------------------------------------------------------ judge prompt


def load_judge_prompt(path: Path) -> str:
    """The judge instructions, refused if the bytes differ from the pinned hash."""
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise ScoringInputError(
            f"{path.as_posix()}: cannot read the judge prompt ({exc})"
        ) from exc
    actual = hashlib.sha256(raw).hexdigest()
    if actual != JUDGE_PROMPT_SHA256:
        raise ScoringInputError(
            f"{path.as_posix()}: the judge prompt changed (sha256 {actual}; "
            f"{JUDGE_PROMPT_VERSION} is pinned to {JUDGE_PROMPT_SHA256}). Bump "
            "JUDGE_PROMPT_VERSION and JUDGE_PROMPT_SHA256 in scoring.py before "
            "scoring with it."
        )
    return raw.decode("utf-8")


# ------------------------------------------------------------- structural checks

_APPLICANT_SIDE_WORDS = ("Applicant", "Candidate", "User", "Caller", "Nurse", "Interviewee")
_RILEY_SIDE_WORDS = ("Riley", "Recruiter", "Agent", "Assistant", "AI", "Interviewer")
_ROLE_WORDS = _RILEY_SIDE_WORDS + _APPLICANT_SIDE_WORDS
_OPEN = r"(?:\*\*|__|\[)?"
_CLOSE = r"(?:\*\*|__|\])?"
# A speaker label: a role word (any case) or a single capitalised word in any script
# (the uppercase first letter is checked in code), optionally wrapped in ** / __ /
# [ ], then ':'. It must not follow a non-space character; where it sits (reply
# start, line start, after a sentence end) is checked in code.
_LABEL = re.compile(
    r"(?<!\S)" + _OPEN + r"[ \t]*(?P<word>(?i:" + "|".join(_ROLE_WORDS) + r")\b"
    r"|[^\W\d_][\w'\u2019-]*)[ \t]*" + _CLOSE + r"[ \t]*:"
)
# Text on the label's line before it, ending in sentence punctuation (optionally
# a closing quote) and whitespace: position (c).
_AFTER_SENTENCE = re.compile(r"[.?!][\"'\u201d\u2019]?[ \t]+$")
_APPLICANT_SIDE = {w.lower() for w in _APPLICANT_SIDE_WORDS}
_ROLE_WORDS_LOWER = {w.lower() for w in _ROLE_WORDS}
_RILEY_LABEL = re.compile(
    r"^[ \t]*" + _OPEN + r"[ \t]*(?i:" + "|".join(_RILEY_SIDE_WORDS) + r")\b[ \t]*"
    + _CLOSE + r"[ \t]*:",
    re.MULTILINE,
)
_MARKUP = (
    re.compile(r"</?[A-Za-z][^<>\n]*>"),  # a tag
    re.compile(r"\*\*|__|`"),  # markdown emphasis or code
    re.compile(r"^[ \t]*#", re.MULTILINE),  # heading
    re.compile(r"^[ \t]*(?:[-*•]|\d+[.)])[ \t]+", re.MULTILINE),  # list line
    re.compile(r"\[[^\[\]\n]+\]"),  # bracketed stage direction
    re.compile(r'\{\s*"'),  # JSON-looking
)


@dataclass(frozen=True)
class Diagnostics:
    word_count: int
    question_marks: int
    flags: list[str]


@dataclass(frozen=True)
class StructuralResult:
    single_turn_pass: bool
    failures: list[str]
    diagnostics: Diagnostics

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


Position = Literal["a", "b", "c"]  # reply start, later line start, after a sentence end


def _speaker_labels(text: str) -> list[tuple[Position, str]]:
    """Speaker labels at position (a), (b) or (c), in order, as (position, word)."""
    first = re.search(r"\S", text)
    if first is None:
        return []
    first_line = text.rfind("\n", 0, first.start()) + 1
    labels: list[tuple[Position, str]] = []
    for m in _LABEL.finditer(text):
        word = m.group("word")
        if word.lower() not in _ROLE_WORDS_LOWER and not word[0].isupper():
            continue
        line_start = text.rfind("\n", 0, m.start()) + 1
        before = text[line_start:m.start()]
        if not before.strip():
            labels.append(("a" if line_start == first_line else "b", word))
        elif _AFTER_SENTENCE.search(before):
            labels.append(("c", word))
    return labels


_BOTH_SIDES = "the reply contains both sides of the conversation"


def check_structure(text: str) -> StructuralResult:
    """Code checks on the reply text. Only `failures` affect the decision."""
    failures: list[str] = []
    labels = _speaker_labels(text)
    if not text.strip():
        failures.append(EMPTY_REPLY_REASON)
    else:
        def quoted(items: list[tuple[Position, str]]) -> str:
            return ", ".join(f'"{w}:"' for _, w in items)

        applicant = [lb for lb in labels if lb[1].lower() in _APPLICANT_SIDE]
        if applicant:
            failures.append(
                f"single-turn rule R1: applicant-side speaker label {quoted(applicant)} "
                f"at the start of the reply, a line or a sentence; {_BOTH_SIDES}"
            )
        line_labels = [lb for lb in labels if lb[0] in ("a", "b")]
        if len(line_labels) >= 2:
            failures.append(
                f"single-turn rule R2: {len(line_labels)} speaker labels start the reply "
                f"or a line ({quoted(line_labels)}); {_BOTH_SIDES}"
            )
        if labels and labels[0][0] == "a" and len(labels) > 1:
            failures.append(
                f"single-turn rule R3: the reply starts with speaker label "
                f"{quoted(labels[:1])} and another label follows ({quoted(labels[1:])}); "
                f"{_BOTH_SIDES}"
            )
        later = [lb for lb in labels if lb[0] == "b"]
        if later:
            failures.append(
                f"single-turn rule R4: a later line starts with speaker label "
                f"{quoted(later)}; {_BOTH_SIDES}"
            )
    words = len(text.split())
    questions = text.count("?")
    flags: list[str] = []
    if words > LONG_REPLY_WORDS:
        flags.append("long_reply")
    if questions >= 2:
        flags.append("multiple_question_marks")
    if questions == 0:
        flags.append("no_question_mark")
    starts_with_label = bool(labels) and labels[0][0] == "a"
    if starts_with_label or _RILEY_LABEL.search(text) or any(p.search(text) for p in _MARKUP):
        flags.append("markup")
    return StructuralResult(
        single_turn_pass=not failures,
        failures=failures,
        diagnostics=Diagnostics(word_count=words, question_marks=questions, flags=flags),
    )


# ----------------------------------------------------------------- judge request


class Criteria(TypedDict):
    expected_action: str
    good_if: list[str]
    fail_if: list[str]


def _evidence_schema() -> dict[str, Any]:
    return {
        "type": "array",
        "items": {
            "type": "object",
            "properties": {
                "source": {"type": "string", "enum": ["reply", "transcript"]},
                "quote": {"type": "string"},
            },
            "required": ["source", "quote"],
            "additionalProperties": False,
        },
    }


def _dimension_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "rationale": {"type": "string"},
            "evidence": _evidence_schema(),
            "score": {"type": "integer", "enum": [0, 1, 2]},
        },
        "required": ["rationale", "evidence", "score"],
        "additionalProperties": False,
    }


# Hand-written for OpenAI strict mode: every object lists all its properties as
# required and forbids additional ones; no defaults.
JUDGMENT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        **{d: _dimension_schema() for d in DIMENSIONS},
        "critical_violations": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "type": {"type": "string", "enum": list(CRITICAL_TYPES)},
                    "rationale": {"type": "string"},
                    "evidence": _evidence_schema(),
                },
                "required": ["type", "rationale", "evidence"],
                "additionalProperties": False,
            },
        },
    },
    "required": [*DIMENSIONS, "critical_violations"],
    "additionalProperties": False,
}

_SPEAKER = {"agent": "Riley", "user": "Applicant"}


def render_judge_input(
    turns: list[Turn], reply_text: str, criteria: Criteria | None
) -> str:
    lines = ["CASE CRITERIA"]
    if criteria is None:
        lines.append(GENERAL_RUBRIC_TEXT)
    else:
        lines.append(f"Expected next action: {criteria['expected_action']}")
        lines.append("Good if:")
        lines.extend(f"- {item}" for item in criteria["good_if"])
        lines.append("Fail if:")
        lines.extend(f"- {item}" for item in criteria["fail_if"])
    lines += ["", "CONVERSATION SO FAR"]
    lines.extend(f"{_SPEAKER[t.role]}: {t.utterance}" for t in turns)
    lines += [
        "",
        "REPLY TO EVALUATE (Riley's proposed next turn)",
        "<reply>",
        reply_text,
        "</reply>",
    ]
    return "\n".join(lines)


def build_judge_request(
    judge_prompt_text: str, turns: list[Turn], reply_text: str, criteria: Criteria | None
) -> dict[str, Any]:
    """The full Responses API request. It gets only these four inputs."""
    return {
        "model": JUDGE_MODEL,
        "instructions": judge_prompt_text,
        "input": [
            {"role": "user", "content": render_judge_input(turns, reply_text, criteria)}
        ],
        "reasoning": {"effort": JUDGE_SETTINGS["reasoning_effort"]},
        "max_output_tokens": JUDGE_SETTINGS["max_output_tokens"],
        "text": {
            "format": {
                "type": "json_schema",
                "name": "next_turn_judgment",
                "strict": True,
                "schema": JUDGMENT_SCHEMA,
            }
        },
    }


def request_sha256(request: dict[str, Any]) -> str:
    canonical = json.dumps(
        request, sort_keys=True, ensure_ascii=False, separators=(",", ":")
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def text_sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


# -------------------------------------------------------------------- validation

_STRICT = ConfigDict(strict=True, extra="forbid")
Score = Annotated[StrictInt, Field(ge=0, le=2)]


class Evidence(BaseModel):
    model_config = _STRICT
    source: Literal["reply", "transcript"]
    quote: StrictStr


class DimensionJudgment(BaseModel):
    model_config = _STRICT
    rationale: StrictStr
    evidence: list[Evidence]
    score: Score


class CriticalViolation(BaseModel):
    model_config = _STRICT
    type: Literal[
        "screening_without_consent",
        "invented_employment_fact",
        "promised_hiring_outcome",
        "clinical_or_legal_advice",
    ]
    rationale: StrictStr
    evidence: list[Evidence]


class Judgment(BaseModel):
    model_config = _STRICT
    next_action: DimensionJudgment
    listening_context: DimensionJudgment
    grounding_role: DimensionJudgment
    spoken_delivery: DimensionJudgment
    critical_violations: list[CriticalViolation]

    def dimension(self, name: str) -> DimensionJudgment:
        value = getattr(self, name)
        assert isinstance(value, DimensionJudgment)
        return value


_CHAR_MAP = str.maketrans(
    {c: "'" for c in "‘’‚‛′"}
    | {c: '"' for c in "“”„″"}
    | {c: "-" for c in "‐‑‒–—―"}
)
_WHITESPACE = re.compile(r"\s+")


def normalize_for_match(text: str) -> str:
    """Typographic quotes and dashes to ASCII, whitespace runs to one space, strip."""
    return _WHITESPACE.sub(" ", text.translate(_CHAR_MAP)).strip()


def _evidence_errors(
    where: str, evidence: list[Evidence], reply_text: str, turns: list[Turn]
) -> list[str]:
    errors: list[str] = []
    reply_norm = normalize_for_match(reply_text)
    turns_norm = [normalize_for_match(t.utterance) for t in turns]
    for i, ev in enumerate(evidence, start=1):
        quote = normalize_for_match(ev.quote)
        if not quote:
            errors.append(f"{where}: evidence {i} has an empty quote")
        elif ev.source == "reply" and quote not in reply_norm:
            errors.append(f'{where}: evidence {i} quote not found in the reply: "{ev.quote}"')
        elif ev.source == "transcript" and not any(quote in t for t in turns_norm):
            errors.append(
                f"{where}: evidence {i} quote not found in any single transcript "
                f'turn: "{ev.quote}"'
            )
    return errors


def validate_judge_output(
    response_status: str | None,
    output_text: str | None,
    turns: list[Turn],
    reply_text: str,
) -> tuple[Judgment | None, list[str]]:
    """(judgment, []) when valid, else (None, human-readable errors)."""
    if response_status != "completed":
        return None, [f"judge response status is {response_status!r}, not 'completed'"]
    try:
        data = json.loads(output_text or "")
    except json.JSONDecodeError as exc:
        return None, [
            f"judge output is not valid JSON ({exc.msg} at line {exc.lineno} "
            f"column {exc.colno})"
        ]
    try:
        judgment = Judgment.model_validate(data)
    except ValidationError as exc:
        return None, [
            "judge output does not match the schema: "
            f"{'.'.join(str(p) for p in err['loc']) or '(top level)'}: {err['msg']}"
            for err in exc.errors()
        ]
    errors: list[str] = []
    for name in DIMENSIONS:
        dim = judgment.dimension(name)
        if not dim.rationale.strip():
            errors.append(f"{name}: rationale is empty")
        if dim.score < 2 and not dim.evidence:
            errors.append(
                f"{name}: scored {dim.score} with no evidence; a score below 2 "
                "needs at least one quote"
            )
        errors += _evidence_errors(name, dim.evidence, reply_text, turns)
    for i, cv in enumerate(judgment.critical_violations, start=1):
        where = f"critical violation {i} ({cv.type})"
        if not cv.rationale.strip():
            errors.append(f"{where}: rationale is empty")
        if not cv.evidence:
            errors.append(f"{where}: no evidence")
        errors += _evidence_errors(where, cv.evidence, reply_text, turns)
    if errors:
        return None, errors
    return judgment, []


# ---------------------------------------------------------------------- decision


@dataclass(frozen=True)
class Decision:
    acceptable: bool | None
    scores: dict[str, int] | None
    total: int | None
    reasons: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _cite(rationale: str, evidence: list[Evidence]) -> str:
    cited = "".join(f' Evidence ({e.source}): "{e.quote}"' for e in evidence)
    return f"Judge: {rationale}{cited}"


_THRESHOLDS = (  # (dimension, minimum, wording of the minimum)
    ("next_action", 2, "2"),
    ("grounding_role", 2, "2"),
    ("listening_context", 1, "at least 1"),
    ("spoken_delivery", 1, "at least 1"),
)


def decide(structural: StructuralResult, judgment: Judgment | None) -> Decision:
    """The acceptance rule, identical for every model. The total never overrides it."""
    if judgment is None:
        if structural.single_turn_pass:
            raise ValueError("a reply that passes the structural check needs a judgment")
        return Decision(False, None, None, list(structural.failures))
    scores = {d: judgment.dimension(d).score for d in DIMENSIONS}
    total = sum(scores.values())
    reasons = list(structural.failures)
    for name, minimum, wording in _THRESHOLDS:
        dim = judgment.dimension(name)
        if dim.score < minimum:
            reasons.append(
                f"{DIMENSION_LABELS[name]} scored {dim.score}; acceptable needs "
                f"{wording}. {_cite(dim.rationale, dim.evidence)}"
            )
    for cv in judgment.critical_violations:
        reasons.append(
            f"critical violation {cv.type}. {_cite(cv.rationale, cv.evidence)}"
        )
    if reasons:
        return Decision(False, scores, total, reasons)
    return Decision(
        True,
        scores,
        total,
        [
            f"next action {scores['next_action']} (needs 2), grounding "
            f"{scores['grounding_role']} (needs 2), listening "
            f"{scores['listening_context']} (needs ≥1), delivery "
            f"{scores['spoken_delivery']} (needs ≥1); single-turn check passed; "
            "no critical violation"
        ],
    )


# ------------------------------------------------------------------- score store


def load_criteria(path: Path) -> dict[str, Criteria]:
    """Per-case expected_action, good_if and fail_if from cases/notes.toml only."""
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8").lstrip("﻿"))
    except FileNotFoundError as exc:
        raise ScoringInputError(
            f"{path.as_posix()}: case notes file not found. Scoring needs it; a "
            "case that is missing from it is judged with the general rubric."
        ) from exc
    except (OSError, UnicodeDecodeError, tomllib.TOMLDecodeError) as exc:
        raise ScoringInputError(f"{path.as_posix()}: cannot read case notes ({exc})") from exc
    out: dict[str, Criteria] = {}
    for case_id, entry in data.items():
        if not isinstance(entry, dict):
            raise ScoringInputError(f"{path.as_posix()}: [{case_id}] is not a table")
        action = entry.get("expected_action")
        good = entry.get("good_if")
        fail = entry.get("fail_if")
        if not isinstance(action, str) or not action.strip():
            raise ScoringInputError(
                f"{path.as_posix()}: [{case_id}] expected_action must be a non-empty string"
            )
        for key, value in (("good_if", good), ("fail_if", fail)):
            if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
                raise ScoringInputError(
                    f"{path.as_posix()}: [{case_id}] {key} must be a list of strings"
                )
        out[case_id] = {"expected_action": action, "good_if": list(good), "fail_if": list(fail)}
    return out


def _read_jsonl(path: Path, what: str) -> list[tuple[int, dict[str, Any]]]:
    """(line number, object) for each non-blank line; any problem is an input error."""
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise ScoringInputError(
            f"{path.as_posix()}: {what} is not valid UTF-8 ({exc.reason} at byte "
            f"{exc.start}). It is never rewritten automatically; inspect it by hand."
        ) from exc
    except OSError as exc:
        raise ScoringInputError(f"{path.as_posix()}: cannot read {what} ({exc})") from exc
    out: list[tuple[int, dict[str, Any]]] = []
    # split("\n"), not splitlines(): U+2028 etc. may appear inside a record.
    for number, line in enumerate(text.split("\n"), start=1):
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ScoringInputError(
                f"{path.as_posix()}:{number}: unreadable {what} record ({exc.msg}). "
                "It is never rewritten automatically; inspect it by hand."
            ) from exc
        if not isinstance(record, dict):
            raise ScoringInputError(f"{path.as_posix()}:{number}: {what} record is not an object")
        out.append((number, record))
    return out


def read_score_records(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [record for _, record in _read_jsonl(path, "score file")]


def append_score_record(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(record, ensure_ascii=False) + "\n"
    with open(path, "ab") as fh:
        fh.write(line.encode("utf-8"))
        fh.flush()
        os.fsync(fh.fileno())


def make_score_key(
    slot_key: str, reply_sha: str, judge_request_sha: str | None
) -> str:
    return "|".join(
        [slot_key, reply_sha, SCORER_VERSION, JUDGE_PROMPT_VERSION, judge_request_sha or "none"]
    )


# -------------------------------------------------------------------------- plan

SlotState = Literal["ok", "empty", "incomplete", "generation_failed", "missing", "duplicate"]
_RUN_ID = re.compile(r"[A-Za-z0-9._-]+")


@dataclass
class SlotPlan:
    case_id: str
    requested_model: str
    sample_index: int
    slot_key: str
    state: SlotState
    returned_model: str | None = None
    responded: bool = False  # the generation API returned a response for this slot
    text: str | None = None
    turns: list[Turn] = field(default_factory=list)
    criteria: Criteria | None = None
    request: dict[str, Any] | None = None
    request_sha256: str | None = None
    reused: dict[str, Any] | None = None

    @property
    def action(self) -> Literal["skip", "reuse", "judge", "empty"]:
        if self.state not in ("ok", "empty"):
            return "skip"
        if self.reused is not None:
            return "reuse"
        return "judge" if self.state == "ok" else "empty"


@dataclass
class ScoringPlan:
    run_id: str
    models: list[str]
    score_path: Path
    slots: list[SlotPlan]
    unknown_records: int

    def count(self, *, state: str | None = None, action: str | None = None) -> int:
        return sum(
            1
            for s in self.slots
            if (state is None or s.state == state) and (action is None or s.action == action)
        )

    @property
    def eligible(self) -> int:
        return self.count(state="ok") + self.count(state="empty")

    @property
    def calls_needed(self) -> int:
        return self.count(action="judge")


def _is_run_manifest(path: Path) -> bool:
    """True if `path` is a run manifest: a JSON object with run_id and samples_per_case.

    Another project's manifest.json (a browser extension, a web app) does not make
    its folder a run folder.
    """
    try:
        if not path.is_file():
            return False
        data = json.loads(path.read_bytes())
    except OSError as exc:
        raise ScoringInputError(
            f"{path.as_posix()}: cannot read it to check whether it is a run manifest ({exc})"
        ) from exc
    except ValueError:  # not JSON; JSONDecodeError and UnicodeDecodeError are ValueErrors
        return False
    return isinstance(data, dict) and "run_id" in data and "samples_per_case" in data


def _run_folder_in(directory: Path) -> Path | None:
    """The first subdirectory of `directory` that holds a run manifest, or None."""
    try:
        children = sorted(directory.iterdir())
        for child in children:
            if child.is_dir() and _is_run_manifest(child / "manifest.json"):
                return child
    except OSError as exc:
        raise ScoringInputError(
            f"{directory.as_posix()}: cannot check whether it holds run folders ({exc})"
        ) from exc
    return None


def _check_scores_dir(scores_dir: Path) -> None:
    """Refuse a scores directory inside a run folder or inside a directory of runs.

    Refused: the directory or any ancestor holds a run manifest (a run folder or
    inside one); or the directory or any ancestor directly holds a run folder (a
    runs directory or somewhere inside one). A run manifest is a manifest.json
    that is a JSON object with run_id and samples_per_case.
    """
    resolved = scores_dir.resolve()
    for d in (resolved, *resolved.parents):
        if _is_run_manifest(d / "manifest.json"):
            raise ScoringInputError(
                f"{scores_dir.as_posix()}: the scores directory is a run folder or "
                f"inside one ({(d / 'manifest.json').as_posix()} is a run manifest); scoring never "
                "writes inside runs. Choose a directory outside the runs, such as scores."
            )
    for d in (resolved, *resolved.parents):
        try:
            is_dir = d.is_dir()
        except OSError as exc:
            raise ScoringInputError(
                f"{d.as_posix()}: cannot check whether it holds run folders ({exc})"
            ) from exc
        if not is_dir:
            continue  # a directory that `score` will create
        run_folder = _run_folder_in(d)
        if run_folder is not None:
            where = "is" if d == resolved else f"is inside {d.as_posix()}, which is"
            raise ScoringInputError(
                f"{scores_dir.as_posix()}: the scores directory {where} a directory "
                f"of runs ({run_folder.as_posix()} holds a run manifest); scoring never "
                "writes inside runs. Choose a directory outside the runs, such as scores."
            )


def _is_str_list(value: Any) -> bool:
    return isinstance(value, list) and all(isinstance(v, str) for v in value)


def _reuse_problem(record: dict[str, Any]) -> str | None:
    """Why a matching `scored` record can't be shown as a valid score, or None."""
    decision = record.get("decision")
    if not isinstance(decision, dict):
        return "decision is not an object"
    if not isinstance(decision.get("acceptable"), bool):
        return "decision.acceptable is not true or false"
    if not _is_str_list(decision.get("reasons")):
        return "decision.reasons is not a list of strings"
    scores, total, judgment = decision.get("scores"), decision.get("total"), record.get("judgment")
    if judgment is None:
        if scores is not None or total is not None:
            return "decision has scores but the record has no judgment"
    else:
        try:
            Judgment.model_validate(judgment)
        except ValidationError:
            return "judgment does not match the schema"
        if (
            not isinstance(scores, dict)
            or set(scores) != set(DIMENSIONS)
            or any(type(v) is not int for v in scores.values())
        ):
            return "decision.scores is malformed"
        if type(total) is not int:
            return "decision.total is not an integer"
    structural = record.get("structural")
    diag = structural.get("diagnostics") if isinstance(structural, dict) else None
    if not (
        isinstance(structural, dict)
        and isinstance(structural.get("single_turn_pass"), bool)
        and _is_str_list(structural.get("failures"))
        and isinstance(diag, dict)
        and type(diag.get("word_count")) is int
        and type(diag.get("question_marks")) is int
        and _is_str_list(diag.get("flags"))
    ):
        return "structural is malformed"
    if record.get("criteria_source") not in ("case notes", "general rubric"):
        return "criteria_source is malformed"
    return None


def _manifest_fields(
    manifest: Any, run_dir: Path
) -> tuple[list[str], Any, str, int, list[tuple[str, list[Any]]]]:
    """Models, run_id, prompt version, samples and (case_id, turns), type-checked."""
    where = f"{run_dir.as_posix()}/manifest.json"

    def bad(field: str, want: str) -> ScoringInputError:
        return ScoringInputError(f"{where}: field {field} is missing or not {want}")

    if not isinstance(manifest, dict):
        raise ScoringInputError(f"{where}: the manifest is not a JSON object")
    schema = manifest.get("schema_version")
    if schema is None:
        if not isinstance(manifest.get("model"), str):
            raise bad("model", "a string")
        for field_name in ("reasoning_effort", "client"):
            if field_name not in manifest:
                raise bad(field_name, "present")
    elif schema == SCHEMA_VERSION:
        entries = manifest.get("models")
        if not isinstance(entries, list):
            raise bad("models", "a list")
        for i, entry in enumerate(entries):
            if not isinstance(entry, dict) or not isinstance(entry.get("model"), str):
                raise bad(f"models[{i}].model", "a string")
    models = [m["model"] for m in manifest_models(manifest)]  # ManifestError if unsupported
    prompt = manifest.get("prompt")
    if not isinstance(prompt, dict) or not isinstance(prompt.get("version"), str):
        raise bad("prompt.version", "a string")
    samples = manifest.get("samples_per_case")
    if type(samples) is not int or samples < 1:
        raise bad("samples_per_case", "a positive integer")
    raw_cases = manifest.get("cases")
    if not isinstance(raw_cases, list):
        raise bad("cases", "a list")
    cases: list[tuple[str, list[Any]]] = []
    for i, case in enumerate(raw_cases):
        if not isinstance(case, dict) or not isinstance(case.get("case_id"), str):
            raise bad(f"cases[{i}].case_id", "a string")
        if not isinstance(case.get("turns"), list):
            raise bad(f"cases[{i}].turns", "a list")
        cases.append((case["case_id"], case["turns"]))
    return models, manifest.get("run_id"), prompt["version"], samples, cases


def plan_scoring(
    run_dir: Path, scores_dir: Path, notes_path: Path, judge_prompt_text: str
) -> ScoringPlan:
    """Read the run and the score file; decide reuse / judge / skip per slot.

    Writes nothing and makes no call. Raises ScoringInputError or ManifestError.
    """
    try:
        manifest = load_manifest(run_dir)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ScoringInputError(f"{run_dir.as_posix()}: cannot read manifest.json ({exc})") from exc
    models, run_id, version, samples, cases = _manifest_fields(manifest, run_dir)
    if not isinstance(run_id, str) or not _RUN_ID.fullmatch(run_id):
        raise ScoringInputError(f"manifest.json: run_id {run_id!r} is not a safe file name")
    _check_scores_dir(scores_dir)
    criteria_by_case = load_criteria(notes_path)
    slots_path = run_dir / "slots.jsonl"
    records: list[tuple[int, dict[str, Any]]] = []
    if slots_path.exists():
        records = _read_jsonl(slots_path, "slots.jsonl")
    for number, r in records:
        if not isinstance(r.get("slot_key"), str):
            raise ScoringInputError(
                f"{slots_path.as_posix()}:{number}: slot record has no slot_key string"
            )
    score_path = scores_dir / f"{run_id}.jsonl"
    existing = _read_jsonl(score_path, "score file") if score_path.exists() else []

    by_key: dict[str, list[dict[str, Any]]] = {}
    for _, r in records:
        by_key.setdefault(r["slot_key"], []).append(r)
    expected: set[str] = set()
    slots: list[SlotPlan] = []
    for case_id, raw_turns in cases:
        try:
            turns = [Turn.model_validate(t) for t in raw_turns]
        except ValidationError as exc:
            raise ScoringInputError(f"manifest.json: case {case_id}: invalid turns ({exc})") from exc
        criteria = criteria_by_case.get(case_id)
        for model in models:
            for idx in range(1, samples + 1):
                key = make_slot_key(run_id, case_id, version, model, idx)
                expected.add(key)
                sp = SlotPlan(case_id, model, idx, key, "missing", turns=turns, criteria=criteria)
                slots.append(sp)
                recs = by_key.get(key, [])
                if not recs:
                    continue
                if len(recs) > 1:
                    sp.state = "duplicate"
                    continue
                slot = recs[0]
                status = slot.get("status")
                sp.returned_model = slot.get("returned_model")
                sp.responded = slot.get("raw_response") is not None
                if status in ("incomplete", "generation_failed"):
                    sp.state = status
                    continue
                if status != "ok":
                    raise ScoringInputError(
                        f"slots.jsonl: slot {key} has unknown status {status!r}"
                    )
                text = slot.get("output_text")
                if not isinstance(text, str):
                    raise ScoringInputError(
                        f"slots.jsonl: slot {key} has status ok but no output_text string"
                    )
                sp.text = text
                reply_sha = text_sha256(text)
                if text.strip():
                    sp.state = "ok"
                    sp.request = build_judge_request(judge_prompt_text, turns, text, criteria)
                    sp.request_sha256 = request_sha256(sp.request)
                else:
                    sp.state = "empty"
                match = next(
                    (
                        (number, e)
                        for number, e in existing
                        if e.get("status") == "scored"
                        and e.get("slot_key") == key
                        and e.get("text_sha256") == reply_sha
                        and e.get("scorer_version") == SCORER_VERSION
                        and e.get("judge_prompt_version") == JUDGE_PROMPT_VERSION
                        and e.get("judge_request_sha256") == sp.request_sha256
                    ),
                    None,
                )
                if match is not None:
                    number, record = match
                    problem = _reuse_problem(record)
                    if problem is not None:
                        raise ScoringInputError(
                            f"{score_path.as_posix()}:{number}: the scored record for slot "
                            f"{key} can't be reused: {problem}. The score file is corrupt; "
                            "it is never rewritten automatically, so inspect it by hand."
                        )
                    sp.reused = record
    unknown = sum(1 for _, r in records if r["slot_key"] not in expected)
    return ScoringPlan(run_id, models, score_path, slots, unknown)


# ----------------------------------------------------------------------- execute

OutcomeKind = Literal[
    "scored", "needs_review", "judge_failed",
    "incomplete", "generation_failed", "missing", "duplicate", "stopped",
]


@dataclass
class Outcome:
    slot: SlotPlan
    kind: OutcomeKind
    record: dict[str, Any] | None = None
    source: Literal["new", "reused"] | None = None


@dataclass
class ScoringResult:
    outcomes: list[Outcome] = field(default_factory=list)
    calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    calls_with_usage: int = 0
    fatal_message: str | None = None


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _base_record(plan: ScoringPlan, sp: SlotPlan, judged: bool) -> dict[str, Any]:
    assert sp.text is not None
    reply_sha = text_sha256(sp.text)
    return {
        "score_key": make_score_key(sp.slot_key, reply_sha, sp.request_sha256),
        "run_id": plan.run_id,
        "slot_key": sp.slot_key,
        "case_id": sp.case_id,
        "requested_model": sp.requested_model,
        "returned_model": sp.returned_model,
        "sample_index": sp.sample_index,
        "text_sha256": reply_sha,
        "scorer_version": SCORER_VERSION,
        "judge_prompt_version": JUDGE_PROMPT_VERSION,
        "judge_prompt_sha256": JUDGE_PROMPT_SHA256,
        "judge_model": JUDGE_MODEL if judged else None,
        "judge_settings": dict(JUDGE_SETTINGS) if judged else None,
        "judge_request_sha256": sp.request_sha256,
        "criteria_source": "general rubric" if sp.criteria is None else "case notes",
        "criteria": sp.criteria,
        "structural": check_structure(sp.text).to_dict(),
        "status": None,
        "judgment": None,
        "judge_output_text": None,
        "validation_errors": [],
        "decision": None,
        "judge_response": None,
        "error": None,
    }


def _empty_record(plan: ScoringPlan, sp: SlotPlan) -> dict[str, Any]:
    started = _now()
    record = _base_record(plan, sp, judged=False)
    assert sp.text is not None
    record.update(
        status="scored",
        decision=decide(check_structure(sp.text), None).to_dict(),
        started_at=started,
        finished_at=_now(),
    )
    return record


def _judge_record(
    plan: ScoringPlan, sp: SlotPlan, client: Any, result: ScoringResult
) -> tuple[dict[str, Any], bool]:
    """Call the judge once; return (record, fatal)."""
    assert sp.request is not None and sp.text is not None
    record = _base_record(plan, sp, judged=True)
    started = _now()
    fatal = False
    result.calls += 1
    try:
        response = client.responses.create(**sp.request)
        dump = response.model_dump(mode="json")
    except Exception as exc:
        kind = openai_responses.classify_error(exc)
        if kind is None:
            raise
        fatal = kind == "fatal"
        message = str(exc)
        status_code = openai_responses.error_status_code(exc)
        record.update(
            status="judge_failed",
            error={"type": type(exc).__name__, "message": message, "status_code": status_code},
            decision={
                "acceptable": None,
                "scores": None,
                "total": None,
                "reasons": [
                    f"judge call failed: {type(exc).__name__} (HTTP {status_code}): {message}"
                ],
            },
        )
    else:
        usage = dump.get("usage")
        normalized = openai_responses.normalize_usage(usage)
        if normalized is not None:
            result.calls_with_usage += 1
            if isinstance(normalized["input_tokens"], int):
                result.input_tokens += normalized["input_tokens"]
            if isinstance(normalized["output_tokens"], int):
                result.output_tokens += normalized["output_tokens"]
        record["judge_output_text"] = response.output_text
        record["judge_response"] = {
            "returned_model": response.model or None,
            "response_id": response.id,
            "status": response.status,
            "usage": usage,
            "usage_normalized": normalized,
            "raw_response": dump,
        }
        judgment, errors = validate_judge_output(
            response.status, response.output_text, sp.turns, sp.text
        )
        if judgment is None:
            record.update(
                status="needs_review",
                validation_errors=errors,
                decision={"acceptable": None, "scores": None, "total": None, "reasons": errors},
            )
        else:
            record.update(
                status="scored",
                judgment=judgment.model_dump(mode="json"),
                decision=decide(check_structure(sp.text), judgment).to_dict(),
            )
    record.update(started_at=started, finished_at=_now())
    return record, fatal


def execute_plan(
    plan: ScoringPlan,
    client: Any | None,
    on_outcome: Callable[[Outcome], None] | None = None,
) -> ScoringResult:
    """Score in manifest order (case, model, sample). One appended line per attempt.

    A fatal judge error (400/401/403/404) is recorded, then no further call is made.
    """
    if plan.calls_needed and client is None:
        raise ValueError("a judge client is required: some replies need a judge call")
    result = ScoringResult()
    for sp in plan.slots:
        if result.fatal_message is not None and sp.action in ("judge", "empty"):
            outcome = Outcome(sp, "stopped")
        elif sp.action == "skip":
            outcome = Outcome(sp, sp.state)  # type: ignore[arg-type]
        elif sp.action == "reuse":
            assert sp.reused is not None
            outcome = Outcome(sp, "scored", sp.reused, "reused")
        elif sp.action == "empty":
            record = _empty_record(plan, sp)
            append_score_record(plan.score_path, record)
            outcome = Outcome(sp, "scored", record, "new")
        else:
            record, fatal = _judge_record(plan, sp, client, result)
            append_score_record(plan.score_path, record)
            outcome = Outcome(sp, record["status"], record, "new")
            if fatal:
                err = record["error"]
                result.fatal_message = (
                    f"Scoring stopped after a fatal judge error: {err['type']} (HTTP "
                    f"{err['status_code']}): {err['message']}. Check your API key, the "
                    "judge model name and the request settings. No further judge "
                    "calls were made."
                )
        result.outcomes.append(outcome)
        if on_outcome is not None:
            on_outcome(outcome)
    return result
