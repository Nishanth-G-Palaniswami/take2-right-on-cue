"""Holdout blind review: pair plan, combined review sheet, pair sheet, comparisons.

Secrets (the pair mapping, the review key, every salt) are written only to the
private files. Nothing here returns them in a message meant for stdout/stderr,
and no exception message carries them. The compare functions run after reveal,
so their reports may name models.

Every file is created with exclusive create, as UTF-8 without BOM and with LF
line endings, and is never rewritten. Nothing is written inside a run folder or
a directory of runs.
"""

from __future__ import annotations

import hashlib
import json
import os
import random
import re
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from . import scoring
from .runs import ManifestError, make_slot_key, provider_for

PAIR_PLAN_SCHEMA = "pair-plan-1"
PAIR_COMMITMENT_SCHEMA = "pair-plan-commitment-1"
REVIEW_KEY_SCHEMA = "review-key-2"
REVIEW_COMMITMENT_SCHEMA = "review-key-commitment-2"

CANONICAL_JSON = (
    'json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":"))'
)
PAIR_ALGORITHM = (
    'sha256((salt + "\\n" + canonical_json(plan)).encode("utf-8")).hexdigest(), '
    f"where canonical_json(obj) = {CANONICAL_JSON}"
)
REVIEW_ALGORITHM = (
    'sha256((salt + "\\n" + canonical_json({"entries": entries, "unavailable": '
    'unavailable})).encode("utf-8")).hexdigest(), '
    f"where canonical_json(obj) = {CANONICAL_JSON}"
)
EMPTY_REPLY_LINE = "(empty reply)"
REPLY_PREFIX = "> "
OPERATIONAL_KINDS = ("failed", "incomplete")  # generation failures: not shown, counted
OPERATIONAL_REASON = "operational failure (reply unavailable)"
# (first model index, first sample, second model index, second sample); M1=0.
PAIRINGS: tuple[tuple[int, int, int, int], ...] = (
    (0, 1, 1, 1),
    (0, 2, 2, 1),
    (1, 2, 2, 2),
)
PAIR_RULE = (
    "Per case, three pairs: (M1 sample 1 vs M2 sample 1), (M1 sample 2 vs M3 "
    "sample 1), (M2 sample 2 vs M3 sample 2), where M1, M2, M3 are the models in "
    "the order listed. Balance: for each pairing, the first-named model is on the "
    "left in exactly half of the cases, chosen with secrets.SystemRandom(), and on "
    "the right in the others. The order of the three pairs within a case is "
    "shuffled with secrets.SystemRandom(); pair IDs P01, P02, ... follow case order, "
    "then the shuffled pair order."
)

REVIEW_SHEET_NAME = "review_sheet.md"
REVIEW_COMMITMENT_NAME = "review_key_commitment.json"
PAIR_SHEET_NAME = "pair_sheet.md"

REVIEW_HEADER = "Review key commitment: "
PAIR_HEADER = "Pair plan commitment: "
NOTES_LINE = "Notes (optional):"
CHOICE_LINE = "Choice (A / B / tie):"
REASON_LINE = "Reason:"

_SAFE_ID = re.compile(r"[A-Za-z0-9._-]+")
_HEX64 = re.compile(r"[0-9a-f]{64}")
_ACCEPT = re.compile(r"^Accept (\S+)\? \(y/n\):(.*)$")
_CHOICE = re.compile(r"^Choice \(A / B / tie\):(.*)$")
_PAIR_TITLE = re.compile(r"^=== PAIR (\S+) ===\s*$")
_CASE_TITLE = re.compile(r"^=== CASE (\S+) ===\s*$")
FINGERPRINT_PREFIX = "Fingerprint: "
_REPLY_OPEN = re.compile(r"^<<<<<<<< REPLY (\S+) >>>>>>>>\s*$")
_REPLY_CLOSE = re.compile(r"^<<<<<<<< END REPLY (\S+) >>>>>>>>\s*$")
_SIDE_OPEN = re.compile(r"^<<<<<<<< (A|B) >>>>>>>>\s*$")
_SIDE_CLOSE = re.compile(r"^<<<<<<<< END (A|B) >>>>>>>>\s*$")
_FINGERPRINT = re.compile(r"^Fingerprint: (\S*)\s*$")
_REASON = re.compile(r"^Reason:(.*)$")
_PRIVATE_PLAN_KEYS = {"schema", "salt", "plan"}
_PRIVATE_KEY_KEYS = {"schema", "salt", "entries", "unavailable"}


class HoldoutInputError(ValueError):
    """An input problem; the command refuses and changes nothing (exit 2).

    Messages never contain a salt, a pair mapping or a review-key mapping.
    """


class CommitmentError(Exception):
    """A private file does not match its commitment. Never carries private content."""


# ------------------------------------------------------------------ primitives


def canonical_json(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def commitment_hash(salt: str, obj: Any) -> str:
    return hashlib.sha256((salt + "\n" + canonical_json(obj)).encode("utf-8")).hexdigest()


def _text_sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _json_text(data: Any) -> str:
    return json.dumps(data, indent=2, ensure_ascii=False) + "\n"


def _plural(n: int, one: str, many: str) -> str:
    return one if n == 1 else many


def _check_not_in_runs(target: Path) -> None:
    """Refuse a file target inside a run folder or inside a directory of runs.

    Same rule as the scorer's scores-directory guard: no ancestor of the file
    may be a run folder, and no ancestor may directly hold a run folder.
    """
    parent = target.resolve().parent
    try:
        for d in (parent, *parent.parents):
            if scoring._is_run_manifest(d / "manifest.json"):
                raise HoldoutInputError(
                    f"{target.as_posix()}: inside a run folder ({d.as_posix()}); "
                    "holdout files are never written inside runs."
                )
        for d in (parent, *parent.parents):
            if not d.is_dir():
                continue
            run_folder = scoring._run_folder_in(d)
            if run_folder is not None:
                raise HoldoutInputError(
                    f"{target.as_posix()}: inside a directory of runs ({d.as_posix()} "
                    f"holds {run_folder.as_posix()}); holdout files are never written "
                    "inside runs."
                )
    except scoring.ScoringInputError as exc:
        raise HoldoutInputError(str(exc)) from None
    except OSError as exc:
        raise HoldoutInputError(
            f"{target.as_posix()}: cannot check whether it is inside runs ({exc})"
        ) from None


def _check_targets(targets: list[Path]) -> None:
    """All targets distinct, absent and outside runs; else refuse before writing."""
    resolved = [t.resolve() for t in targets]
    if len(set(resolved)) != len(resolved):
        raise HoldoutInputError(
            "output paths must be distinct: "
            + ", ".join(t.as_posix() for t in targets)
        )
    for t in targets:
        for d in (t.parent, *t.parent.parents):
            if d.exists() and not d.is_dir():
                raise HoldoutInputError(
                    f"{t.as_posix()}: {d.as_posix()} is a file, not a directory; "
                    "nothing was written."
                )
    existing = [t for t in targets if t.exists()]
    if existing:
        raise HoldoutInputError(
            "refusing to overwrite: "
            + ", ".join(t.as_posix() for t in existing)
            + " already "
            + _plural(len(existing), "exists", "exist")
            + ". Files are write-once; nothing was written."
        )
    for t in targets:
        _check_not_in_runs(t)


def _create_exclusive(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "x", encoding="utf-8", newline="\n") as fh:
        fh.write(content)
        fh.flush()
        os.fsync(fh.fileno())


def write_new_files(files: list[tuple[Path, str]]) -> None:
    """Create every file in order with exclusive create; never overwrite.

    Everything is checked first. If a file appears between the check and its
    creation (a concurrent command), stop: the files already created are named
    in the error and left as they are (nothing is deleted or rewritten).
    """
    _check_targets([p for p, _ in files])
    created: list[Path] = []
    for path, content in files:
        try:
            _create_exclusive(path, content)
        except FileExistsError:
            done = ", ".join(p.as_posix() for p in created) or "none"
            raise HoldoutInputError(
                f"{path.as_posix()} was created by something else while this command "
                f"ran; it was not overwritten. Files created by this command: {done}."
            ) from None
        created.append(path)


def _read_json_object(path: Path, what: str) -> dict[str, Any]:
    """A JSON object from `path`; errors name the path only, never the content."""
    try:
        text = path.read_bytes().decode("utf-8").lstrip("﻿")
    except FileNotFoundError:
        raise HoldoutInputError(f"{path.as_posix()}: {what} not found") from None
    except OSError as exc:
        raise HoldoutInputError(
            f"{path.as_posix()}: cannot read {what} ({type(exc).__name__})"
        ) from None
    except UnicodeDecodeError:
        raise HoldoutInputError(f"{path.as_posix()}: {what} is not valid UTF-8") from None
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise HoldoutInputError(
            f"{path.as_posix()}: {what} is not valid JSON (line {exc.lineno}, "
            f"column {exc.colno})"
        ) from None
    if not isinstance(data, dict):
        raise HoldoutInputError(f"{path.as_posix()}: {what} is not a JSON object")
    return data


def _read_sheet_lines(path: Path, what: str) -> list[str]:
    """Lines of an owner-edited sheet: BOM stripped, split on LF, CR stripped."""
    try:
        text = path.read_bytes().decode("utf-8").lstrip("﻿")
    except FileNotFoundError:
        raise HoldoutInputError(f"{path.as_posix()}: {what} not found") from None
    except OSError as exc:
        raise HoldoutInputError(
            f"{path.as_posix()}: cannot read {what} ({type(exc).__name__})"
        ) from None
    except UnicodeDecodeError:
        raise HoldoutInputError(f"{path.as_posix()}: {what} is not valid UTF-8") from None
    return [line.rstrip("\r") for line in text.split("\n")]


def _outside_blocks(
    lines: list[str], opener: re.Pattern[str], closer: re.Pattern[str], path: Path
) -> list[str]:
    """The lines outside reply blocks (block lines are replaced by "").

    Reply text can't then be mistaken for a header, a label or a choice. A block
    opened and never closed is an input error.
    """
    out: list[str] = []
    open_label: str | None = None
    for line in lines:
        if open_label is not None:
            close = closer.match(line)
            if close and close.group(1) == open_label:
                open_label = None
            out.append("")
            continue
        opened = opener.match(line)
        if opened:
            open_label = opened.group(1)
            out.append("")
            continue
        out.append(line)
    if open_label is not None:
        raise HoldoutInputError(
            f"{path.as_posix()}: a reply block is opened and never closed; the sheet's "
            "delimiter lines must stay unchanged"
        )
    return out


def _review_lines(path: Path) -> list[str]:
    return _outside_blocks(
        _read_sheet_lines(path, "review sheet"), _REPLY_OPEN, _REPLY_CLOSE, path
    )


def _pair_lines(path: Path) -> list[str]:
    return _outside_blocks(
        _read_sheet_lines(path, "pair sheet"), _SIDE_OPEN, _SIDE_CLOSE, path
    )


# ------------------------------------------------------------------- pair plan


def make_pair_plan(
    cases: list[str],
    models: list[str],
    prompt_version: str,
    rng: random.Random | None = None,
) -> dict[str, Any]:
    """The pair plan; raises HoldoutInputError on invalid input.

    `rng` defaults to secrets.SystemRandom() (fresh OS randomness); tests may
    pass a seeded random.Random.
    """
    errors: list[str] = []
    if len(models) != 3:
        errors.append(f"--model: exactly three models are required, got {len(models)}")
    if len(set(models)) != len(models):
        errors.append("--model: the same model is listed more than once")
    for m in models:
        try:
            provider_for(m)
        except ValueError as exc:
            errors.append(f"--model: {exc}")
    if len(cases) < 2 or len(cases) % 2:
        errors.append(
            f"--case: an even number of cases (at least 2) is required for balanced "
            f"placement, got {len(cases)}"
        )
    if len(set(cases)) != len(cases):
        errors.append("--case: the same case is listed more than once")
    for c in cases:
        if not _SAFE_ID.fullmatch(c):
            errors.append(
                f"--case: {c!r} is not a valid case ID (letters, digits, '.', '-', '_')"
            )
    if not _SAFE_ID.fullmatch(prompt_version):
        errors.append(
            f"--prompt-version: {prompt_version!r} is not valid (letters, digits, "
            "'.', '-', '_')"
        )
    if errors:
        raise HoldoutInputError("\n".join(errors))

    rng = rng or secrets.SystemRandom()
    half = len(cases) // 2
    first_left = [set(rng.sample(cases, half)) for _ in PAIRINGS]
    pairs: list[dict[str, Any]] = []
    for case in cases:
        in_case: list[dict[str, Any]] = []
        for p, (mi, si, mj, sj) in enumerate(PAIRINGS):
            first = {"model": models[mi], "sample": si}
            second = {"model": models[mj], "sample": sj}
            left, right = (first, second) if case in first_left[p] else (second, first)
            in_case.append({"case": case, "left": left, "right": right})
        rng.shuffle(in_case)
        pairs.extend(in_case)
    for n, pair in enumerate(pairs, start=1):
        pair["pair_id"] = f"P{n:02d}"
    return {
        "prompt_version": prompt_version,
        "models": list(models),
        "cases": list(cases),
        "pairs": [
            {"pair_id": p["pair_id"], "case": p["case"], "left": p["left"], "right": p["right"]}
            for p in pairs
        ],
    }


def create_pair_plan(
    cases: list[str],
    models: list[str],
    prompt_version: str,
    private_out: Path,
    commitment_out: Path,
) -> str:
    """Write the private plan and its commitment (write-once); return the hash."""
    if private_out.resolve().parent == commitment_out.resolve().parent:
        raise HoldoutInputError(
            f"{private_out.as_posix()}: the private plan must not sit in the same folder "
            f"as the commitment ({commitment_out.as_posix()}); use a separate folder "
            "such as holdout-private/. Nothing was written."
        )
    _check_targets([private_out, commitment_out])
    plan = make_pair_plan(cases, models, prompt_version)
    salt = secrets.token_hex(32)
    digest = commitment_hash(salt, plan)
    private = {"schema": PAIR_PLAN_SCHEMA, "salt": salt, "plan": plan}
    commitment = {
        "schema": PAIR_COMMITMENT_SCHEMA,
        "algorithm": PAIR_ALGORITHM,
        "sha256": digest,
        "prompt_version": prompt_version,
        "models": list(models),
        "cases": list(cases),
        "pair_rule": PAIR_RULE,
        "created_at": _now(),
    }
    write_new_files(
        [(private_out, _json_text(private)), (commitment_out, _json_text(commitment))]
    )
    return digest


# ---------------------------------------------------------- private file shapes


def _bad(path: Path, field: str, want: str) -> HoldoutInputError:
    return HoldoutInputError(f"{path.as_posix()}: field {field} is missing or not {want}")


def _str_list(value: Any) -> bool:
    return isinstance(value, list) and all(isinstance(v, str) for v in value)


def _check_private_apart(private: Path, public_dir: Path, what: str) -> None:
    """Refuse a private file inside a directory that holds public output."""
    target = private.resolve()
    if public_dir.resolve() in target.parents:
        raise HoldoutInputError(
            f"{private.as_posix()}: a private file must not be written inside {what} "
            f"({public_dir.as_posix()}), where public files are opened; use a "
            "separate folder such as holdout-private/. Nothing was written."
        )


def _check_top_keys(data: dict[str, Any], allowed: set[str], path: Path) -> None:
    extra = sorted(set(data) - allowed)
    if extra:
        # the count only: a private file's field names are private content too
        raise HoldoutInputError(
            f"{path.as_posix()}: {len(extra)} unexpected top-level "
            f"{_plural(len(extra), 'field', 'fields')}; allowed: {', '.join(sorted(allowed))}"
        )


def _salt(data: dict[str, Any], path: Path) -> str:
    salt = data.get("salt")
    if not isinstance(salt, str) or not salt:
        raise _bad(path, "salt", "a non-empty string")
    return salt


def load_pair_private(path: Path) -> tuple[str, dict[str, Any]]:
    """(salt, plan) from a private pair-plan file, shape-checked by hand."""
    data = _read_json_object(path, "private pair plan")
    if data.get("schema") != PAIR_PLAN_SCHEMA:
        raise HoldoutInputError(
            f"{path.as_posix()}: not a private pair plan (schema must be {PAIR_PLAN_SCHEMA!r})"
        )
    _check_top_keys(data, _PRIVATE_PLAN_KEYS, path)
    salt = _salt(data, path)
    plan = data.get("plan")
    if not isinstance(plan, dict):
        raise _bad(path, "plan", "an object")
    if not isinstance(plan.get("prompt_version"), str):
        raise _bad(path, "plan.prompt_version", "a string")
    if not _str_list(plan.get("models")) or len(plan["models"]) != 3:
        raise _bad(path, "plan.models", "a list of three strings")
    if not _str_list(plan.get("cases")):
        raise _bad(path, "plan.cases", "a list of strings")
    pairs = plan.get("pairs")
    if not isinstance(pairs, list):
        raise _bad(path, "plan.pairs", "a list")
    ids: set[str] = set()
    for i, pair in enumerate(pairs):
        where = f"plan.pairs[{i}]"
        if not isinstance(pair, dict):
            raise _bad(path, where, "an object")
        if not isinstance(pair.get("pair_id"), str) or pair["pair_id"] in ids:
            raise _bad(path, f"{where}.pair_id", "a unique string")
        ids.add(pair["pair_id"])
        if pair.get("case") not in plan["cases"]:
            raise _bad(path, f"{where}.case", "one of plan.cases")
        for side in ("left", "right"):
            s = pair.get(side)
            if (
                not isinstance(s, dict)
                or s.get("model") not in plan["models"]
                or type(s.get("sample")) is not int
            ):
                raise _bad(path, f"{where}.{side}", "an object with a plan model and an integer sample")
    return salt, plan


def load_review_key(
    path: Path,
) -> tuple[str, dict[str, dict[str, Any]], list[dict[str, Any]]]:
    """(salt, entries, unavailable) from a private review key, shape-checked by hand."""
    data = _read_json_object(path, "private review key")
    if data.get("schema") != REVIEW_KEY_SCHEMA:
        raise HoldoutInputError(
            f"{path.as_posix()}: not a private review key (schema must be {REVIEW_KEY_SCHEMA!r})"
        )
    _check_top_keys(data, _PRIVATE_KEY_KEYS, path)
    salt = _salt(data, path)
    entries = data.get("entries")
    if not isinstance(entries, dict):
        raise _bad(path, "entries", "an object")
    for e in entries.values():
        where = "an entry"  # never the neutral ID: it would sit next to its fields
        if not isinstance(e, dict):
            raise _bad(path, where, "an object")
        for f in ("run_id", "slot_key", "prompt_version", "model", "text_sha256"):
            if not isinstance(e.get(f), str):
                raise _bad(path, f"{f} of {where}", "a string")
        if type(e.get("sample_index")) is not int:
            raise _bad(path, f"sample_index of {where}", "an integer")
    unavailable = data.get("unavailable")
    if not isinstance(unavailable, list):
        raise _bad(path, "unavailable", "a list")
    for u in unavailable:
        where = "an unavailable slot"
        if not isinstance(u, dict):
            raise _bad(path, where, "an object")
        for f in ("run_id", "case_id", "slot_key", "prompt_version", "model"):
            if not isinstance(u.get(f), str):
                raise _bad(path, f"{f} of {where}", "a string")
        if type(u.get("sample_index")) is not int:
            raise _bad(path, f"sample_index of {where}", "an integer")
        if u.get("kind") not in OPERATIONAL_KINDS:
            raise _bad(path, f"kind of {where}", f"one of {', '.join(OPERATIONAL_KINDS)}")
    if not entries and not unavailable:
        raise HoldoutInputError(f"{path.as_posix()}: the review key has no replies")
    return salt, entries, unavailable


def review_key_material(
    entries: dict[str, dict[str, Any]], unavailable: list[dict[str, Any]]
) -> dict[str, Any]:
    """What the review commitment's salted hash covers."""
    return {"entries": entries, "unavailable": unavailable}


def unavailable_counts(unavailable: list[dict[str, Any]]) -> dict[str, int]:
    return {kind: sum(1 for u in unavailable if u["kind"] == kind) for kind in OPERATIONAL_KINDS}


def load_commitment(path: Path) -> dict[str, Any]:
    data = _read_json_object(path, "commitment")
    if data.get("schema") not in (PAIR_COMMITMENT_SCHEMA, REVIEW_COMMITMENT_SCHEMA):
        raise HoldoutInputError(
            f"{path.as_posix()}: not a commitment file (schema must be "
            f"{PAIR_COMMITMENT_SCHEMA!r} or {REVIEW_COMMITMENT_SCHEMA!r})"
        )
    if not isinstance(data.get("sha256"), str) or not _HEX64.fullmatch(data["sha256"]):
        raise _bad(path, "sha256", "a 64-character lowercase hex string")
    return data


def _check_fields(commitment: dict[str, Any], expected: dict[str, Any]) -> None:
    for name, want in expected.items():
        if commitment.get(name) != want:
            raise CommitmentError(
                f"the commitment's {name} does not match the private file"
            )


def verify_pair_plan(private: Path, commitment: Path) -> tuple[dict[str, Any], str]:
    """(plan, hash) if the private plan matches its commitment.

    Raises HoldoutInputError for an unreadable or malformed file and
    CommitmentError for a schema mismatch or a hash mismatch.
    """
    com = load_commitment(commitment)
    if com["schema"] != PAIR_COMMITMENT_SCHEMA:
        raise CommitmentError(
            f"schema mismatch: {commitment.as_posix()} is {com['schema']!r}, not a "
            f"{PAIR_COMMITMENT_SCHEMA!r} commitment"
        )
    salt, plan = load_pair_private(private)
    if commitment_hash(salt, plan) != com["sha256"]:
        raise CommitmentError(
            "the salted hash of the private plan does not match the committed "
            f"sha256 {com['sha256']}"
        )
    _check_fields(
        com,
        {
            "algorithm": PAIR_ALGORITHM,
            "pair_rule": PAIR_RULE,
            "prompt_version": plan["prompt_version"],
            "models": plan["models"],
            "cases": plan["cases"],
        },
    )
    problem = plan_rule_problem(plan)
    if problem is not None:
        raise CommitmentError(f"the plan does not follow the published pair rule: {problem}")
    return plan, com["sha256"]


def plan_rule_problem(plan: dict[str, Any]) -> str | None:
    """Which part of the published pair rule a (shape-checked) plan breaks, or None.

    The message names the broken check only: never a case, pair, model or side.
    """
    cases, models, pairs = plan["cases"], plan["models"], plan["pairs"]
    if len(set(models)) != 3:
        return "the plan does not have three distinct models"
    if len(cases) < 2 or len(cases) % 2 or len(set(cases)) != len(cases):
        return "the plan does not have an even number (at least 2) of distinct cases"
    if [p["pair_id"] for p in pairs] != [f"P{n:02d}" for n in range(1, len(pairs) + 1)]:
        return "the pair IDs are not P01, P02, ... in order"
    if [p["case"] for p in pairs] != [c for c in cases for _ in PAIRINGS]:
        return "the pairs are not three per case in case order"
    pairing_of = {
        (models[mi], si, models[mj], sj): k for k, (mi, si, mj, sj) in enumerate(PAIRINGS)
    }
    first_left = [0] * len(PAIRINGS)
    every_slot = sorted((m, i) for m in models for i in (1, 2))
    for case in cases:
        seen: set[int] = set()
        used: list[tuple[str, int]] = []
        for p in (p for p in pairs if p["case"] == case):
            left = (p["left"]["model"], p["left"]["sample"])
            right = (p["right"]["model"], p["right"]["sample"])
            used += [left, right]
            if left + right in pairing_of:
                k = pairing_of[left + right]
                first_left[k] += 1
            elif right + left in pairing_of:
                k = pairing_of[right + left]
            else:
                return "a pair does not follow the sample rule"
            if k in seen:
                return "a pairing appears more than once in a case"
            seen.add(k)
        if sorted(used) != every_slot:
            return "a model and sample is not used exactly once in a case"
    if any(n != len(cases) // 2 for n in first_left):
        return (
            "the first-named model is not on the left in exactly half of the cases "
            "for every pairing"
        )
    return None


def verify_review_key(
    private: Path, commitment: Path
) -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    """(entries, unavailable, commitment) if the private key matches its commitment.

    Besides the hash, the commitment's public metadata (shown IDs, unavailable
    counts by kind, run IDs, case IDs, reply count) must equal what the key implies.
    """
    com = load_commitment(commitment)
    if com["schema"] != REVIEW_COMMITMENT_SCHEMA:
        raise CommitmentError(
            f"schema mismatch: {commitment.as_posix()} is {com['schema']!r}, not a "
            f"{REVIEW_COMMITMENT_SCHEMA!r} commitment"
        )
    salt, entries, unavailable = load_review_key(private)
    if commitment_hash(salt, review_key_material(entries, unavailable)) != com["sha256"]:
        raise CommitmentError(
            "the salted hash of the private review key does not match the committed "
            f"sha256 {com['sha256']}"
        )
    run_ids = list(
        dict.fromkeys([e["run_id"] for e in entries.values()] + [u["run_id"] for u in unavailable])
    )
    case_ids = list(
        dict.fromkeys([rid.rsplit("-", 1)[0] for rid in entries] + [u["case_id"] for u in unavailable])
    )
    _check_fields(
        com,
        {
            "algorithm": REVIEW_ALGORITHM,
            "n_replies": len(entries),
            "unavailable": unavailable_counts(unavailable),
        },
    )
    ids = com.get("ids")
    if not _str_list(ids) or len(set(ids)) != len(ids) or sorted(ids) != sorted(entries):
        raise CommitmentError("the commitment's ids do not match the private file")
    if sorted(com.get("run_ids") or []) != sorted(run_ids):
        raise CommitmentError("the commitment's run_ids do not match the private file")
    if sorted(com.get("case_ids") or []) != sorted(case_ids):
        raise CommitmentError("the commitment's case_ids do not match the private file")
    return entries, unavailable, com


def verify_any(private: Path, commitment: Path) -> tuple[str, str]:
    """(kind, hash) for either kind of private file; dispatches on its schema."""
    data = _read_json_object(private, "private file")
    schema = data.get("schema")
    if schema == PAIR_PLAN_SCHEMA:
        _, digest = verify_pair_plan(private, commitment)
        return "pair plan", digest
    if schema == REVIEW_KEY_SCHEMA:
        _, _, com = verify_review_key(private, commitment)
        return "review key", com["sha256"]
    raise CommitmentError(
        f"schema mismatch: {private.as_posix()} is neither a {PAIR_PLAN_SCHEMA!r} "
        f"nor a {REVIEW_KEY_SCHEMA!r} private file"
    )


def _verified_plan(private: Path, commitment: Path) -> tuple[dict[str, Any], str]:
    try:
        return verify_pair_plan(private, commitment)
    except CommitmentError as exc:
        raise HoldoutInputError(f"commitment NOT verified: {exc}. Nothing was done.") from None


def _verified_key(
    private: Path, commitment: Path
) -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    try:
        return verify_review_key(private, commitment)
    except CommitmentError as exc:
        raise HoldoutInputError(f"commitment NOT verified: {exc}. Nothing was done.") from None


# ------------------------------------------------------------------------- runs


@dataclass
class RunData:
    run_dir: Path
    run_id: str
    prompt_version: str
    models: list[str]
    samples: int
    cases: list[tuple[str, list[dict[str, Any]]]]
    by_key: dict[str, list[dict[str, Any]]]


def load_run(run_dir: Path) -> RunData:
    """A run's manifest fields and slot records; read-only."""
    if not (run_dir / "manifest.json").is_file():
        raise HoldoutInputError(f"{run_dir.as_posix()}: no manifest.json; not a run directory")
    try:
        manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
        models, run_id, version, samples, cases = scoring._manifest_fields(manifest, run_dir)
        records: list[tuple[int, dict[str, Any]]] = []
        if (run_dir / "slots.jsonl").exists():
            records = scoring._read_jsonl(run_dir / "slots.jsonl", "slots.jsonl")
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise HoldoutInputError(f"{run_dir.as_posix()}: cannot read the run ({exc})") from None
    except (scoring.ScoringInputError, ManifestError) as exc:
        raise HoldoutInputError(str(exc)) from None
    if not isinstance(run_id, str) or not _SAFE_ID.fullmatch(run_id):
        raise HoldoutInputError(f"{run_dir.as_posix()}/manifest.json: run_id is not a safe name")
    by_key: dict[str, list[dict[str, Any]]] = {}
    for number, r in records:
        if not isinstance(r.get("slot_key"), str):
            raise HoldoutInputError(
                f"{run_dir.as_posix()}/slots.jsonl:{number}: slot record has no slot_key string"
            )
        by_key.setdefault(r["slot_key"], []).append(r)
    return RunData(run_dir, run_id, version, models, samples, cases, by_key)


SHOWN_STATES = ("ok", "empty")


def _slot_state(recs: list[dict[str, Any]]) -> str:
    """ok / empty (shown); failed / incomplete (operational, not shown); or an
    integrity problem: missing, duplicate, unknown status, malformed."""
    if not recs:
        return "missing"
    if len(recs) > 1:
        return "duplicate"
    status = recs[0].get("status")
    if status == "generation_failed":
        return "failed"
    if status == "incomplete":
        return "incomplete"
    if status != "ok":
        return "unknown status"
    text = recs[0].get("output_text")
    if not isinstance(text, str):
        return "malformed"
    return "ok" if text.strip() else "empty"


def render_reply(text: str) -> list[str]:
    """Sheet lines for a reply: a bare "(empty reply)" line for an empty reply;
    otherwise every non-empty line prefixed with "> ", so no reply line can equal
    a column-0 delimiter, header, title or answer line. Lines are split on CR as
    well as LF, so an editor normalising line endings can't create a new line.
    Fingerprints and SHA-256s are always of the raw text, never of these lines.
    """
    if not text.strip():
        return [EMPTY_REPLY_LINE]
    return [REPLY_PREFIX + line if line else "" for line in re.split(r"\r\n|\r|\n", text)]


def _context_lines(case_id: str, turns: list[dict[str, Any]]) -> list[str]:
    """Riley's previous turn (or a note) and the applicant's last turn, as `show`."""
    agent_idx = max(
        (i for i, t in enumerate(turns[:-1]) if t["role"] == "agent"), default=None
    )
    lines = [f"=== CASE {case_id} ===", "Riley's previous turn:"]
    if agent_idx is None:
        lines.append("(Riley hasn't spoken yet in this transcript.)")
        skipped = len(turns) - 1
        where = ""
    else:
        lines.append(turns[agent_idx]["utterance"])
        skipped = len(turns) - 1 - agent_idx - 1
        where = " after Riley's last turn"
    if skipped > 0:
        lines.append(
            f"({skipped} earlier applicant {_plural(skipped, 'turn', 'turns')}"
            f"{where} {_plural(skipped, 'is', 'are')} not shown.)"
        )
    lines += ["Applicant's last turn:", turns[-1]["utterance"], ""]
    return lines


# --------------------------------------------------------------- review sheet


@dataclass
class ReviewSheetResult:
    sheet: Path
    private_key: Path
    commitment: Path
    sha256: str
    n_replies: int
    n_cases: int
    unavailable: dict[str, int]


def _review_preconditions(runs: list[RunData]) -> list[str]:
    """Integrity problems that block the combined sheet, without model names.

    Failed and incomplete generations are operational failures, not problems:
    they are left off the sheet and counted. Missing, duplicate, unknown-status
    and malformed slots, and records matching no expected slot, are refused.
    """
    problems: list[str] = []
    a, b = runs
    if a.run_id == b.run_id:
        problems.append(f"both --run arguments are the same run ({a.run_id})")
    ids_a = [c for c, _ in a.cases]
    ids_b = [c for c, _ in b.cases]
    if sorted(ids_a) != sorted(ids_b):
        problems.append(
            f"the runs have different case IDs: {a.run_id} has {', '.join(ids_a)}; "
            f"{b.run_id} has {', '.join(ids_b)}"
        )
    else:
        turns_b = dict(b.cases)
        for cid, turns in a.cases:
            if turns != turns_b[cid]:
                problems.append(f"case {cid}: the transcript turns differ between the runs")
    for run in runs:
        if len({c for c, _ in run.cases}) != len(run.cases):
            problems.append(f"run {run.run_id}: a case is listed more than once")
        expected: set[str] = set()
        for cid, _ in run.cases:
            counts: dict[str, int] = {}
            for model in run.models:
                for idx in range(1, run.samples + 1):
                    key = make_slot_key(run.run_id, cid, run.prompt_version, model, idx)
                    expected.add(key)
                    state = _slot_state(run.by_key.get(key, []))
                    if state not in SHOWN_STATES and state not in OPERATIONAL_KINDS:
                        counts[state] = counts.get(state, 0) + 1
            for kind, n in sorted(counts.items()):
                problems.append(
                    f"run {run.run_id}: case {cid}: {n} {kind} {_plural(n, 'slot', 'slots')}"
                )
        stray = sum(len(v) for k, v in run.by_key.items() if k not in expected)
        if stray:
            problems.append(
                f"run {run.run_id}: {stray} saved "
                f"{_plural(stray, 'record matches', 'records match')} no expected slot"
            )
    return problems


def _counts_text(counts: dict[str, int]) -> str:
    return ", ".join(f"{kind} {n}" for kind, n in counts.items())


def create_review_sheet(
    run_dirs: list[Path], out_dir: Path, private_key: Path
) -> ReviewSheetResult:
    if len(run_dirs) != 2:
        raise HoldoutInputError(f"--run: exactly two runs are required, got {len(run_dirs)}")
    sheet_path = out_dir / REVIEW_SHEET_NAME
    commitment_path = out_dir / REVIEW_COMMITMENT_NAME
    _check_private_apart(private_key, out_dir, "--out")
    _check_targets([private_key, commitment_path, sheet_path])
    runs = [load_run(d) for d in run_dirs]
    problems = _review_preconditions(runs)
    if problems:
        raise HoldoutInputError(
            "cannot build the review sheet:\n"
            + "\n".join(f"  - {p}" for p in problems)
            + "\nNothing was written."
        )

    rng = secrets.SystemRandom()
    entries: dict[str, dict[str, Any]] = {}
    texts: dict[str, str] = {}
    unavailable: list[dict[str, Any]] = []
    case_ids = [c for c, _ in runs[0].cases]
    per_case: dict[str, list[str]] = {}
    for cid in case_ids:
        # one item per slot: identical texts from distinct slots each get an ID
        items: list[tuple[RunData, str, int, str, str]] = []
        for run in runs:
            for model in run.models:
                for idx in range(1, run.samples + 1):
                    key = make_slot_key(run.run_id, cid, run.prompt_version, model, idx)
                    state = _slot_state(run.by_key[key])
                    if state in OPERATIONAL_KINDS:
                        unavailable.append(
                            {
                                "run_id": run.run_id,
                                "case_id": cid,
                                "slot_key": key,
                                "prompt_version": run.prompt_version,
                                "model": model,
                                "sample_index": idx,
                                "kind": state,
                            }
                        )
                        continue
                    items.append((run, model, idx, key, run.by_key[key][0]["output_text"]))
        if len(items) > 99:
            raise HoldoutInputError(
                f"case {cid}: {len(items)} replies; neutral IDs allow at most 99 per case"
            )
        rng.shuffle(items)
        per_case[cid] = []
        for n, (run, model, idx, key, text) in enumerate(items, start=1):
            rid = f"{cid}-{n:02d}"
            entries[rid] = {
                "run_id": run.run_id,
                "slot_key": key,
                "prompt_version": run.prompt_version,
                "model": model,
                "sample_index": idx,
                "text_sha256": _text_sha(text),
            }
            texts[rid] = text
            per_case[cid].append(rid)

    salt = secrets.token_hex(32)
    digest = commitment_hash(salt, review_key_material(entries, unavailable))
    counts = unavailable_counts(unavailable)
    key_doc = {
        "schema": REVIEW_KEY_SCHEMA,
        "salt": salt,
        "entries": entries,
        "unavailable": unavailable,
    }
    commitment = {
        "schema": REVIEW_COMMITMENT_SCHEMA,
        "algorithm": REVIEW_ALGORITHM,
        "sha256": digest,
        "run_ids": [r.run_id for r in runs],
        "case_ids": case_ids,
        "n_replies": len(entries),
        "ids": list(entries),
        "unavailable": counts,
        "created_at": _now(),
    }
    turns_by_case = dict(runs[0].cases)
    lines = [
        "# Holdout review sheet",
        "",
        f"{REVIEW_HEADER}{digest}",
        "",
        "For each reply, write y (accept) or n (reject) after the colon on its",
        "Accept line. Leave the reply text and the other lines unchanged. Reply",
        f"lines start with '{REPLY_PREFIX.strip()}'; a reply with no text shows as {EMPTY_REPLY_LINE}.",
        "",
    ]
    if unavailable:
        lines += [
            f"{len(unavailable)} {_plural(len(unavailable), 'reply', 'replies')} could not "
            f"be shown (operational failures: {_counts_text(counts)}).",
            "",
        ]
    for cid in case_ids:
        lines += _context_lines(cid, turns_by_case[cid])
        for rid in per_case[cid]:
            lines += [
                f"<<<<<<<< REPLY {rid} >>>>>>>>",
                *render_reply(texts[rid]),
                f"<<<<<<<< END REPLY {rid} >>>>>>>>",
                "",
            ]
        if not per_case[cid]:
            lines += ["(No reply can be shown for this case.)", ""]
        lines += [f"Accept {rid}? (y/n):" for rid in per_case[cid]]
        lines += [NOTES_LINE, ""]
    write_new_files(
        [
            (private_key, _json_text(key_doc)),
            (commitment_path, _json_text(commitment)),
            (sheet_path, "\n".join(lines)),
        ]
    )
    return ReviewSheetResult(
        sheet_path, private_key, commitment_path, digest, len(entries), len(case_ids), counts
    )


def _sheet_commitment(lines: list[str], header: str, path: Path) -> str:
    found = [ln[len(header):].strip() for ln in lines if ln.startswith(header)]
    if len(found) != 1:
        raise HoldoutInputError(
            f"{path.as_posix()}: expected exactly one '{header.strip()}' line, found {len(found)}"
        )
    return found[0]


def parse_review_sheet(path: Path) -> tuple[str, dict[str, str]]:
    """(commitment header, {neutral ID: value after the colon, trimmed}).

    Only lines outside reply blocks are read, so reply text can't pose as a
    header or a label. A repeated ID is an input error.
    """
    lines = _review_lines(path)
    header = _sheet_commitment(lines, REVIEW_HEADER, path)
    labels: dict[str, str] = {}
    duplicates: list[str] = []
    for line in lines:
        m = _ACCEPT.match(line)
        if m:
            rid = m.group(1)
            if rid in labels:
                duplicates.append(rid)
            labels[rid] = m.group(2).strip()
    if duplicates:
        raise HoldoutInputError(
            f"{path.as_posix()}: Accept line repeated for {', '.join(sorted(set(duplicates)))}"
        )
    return header, labels


def check_review_labels(sheet: Path, review_commitment: Path, run_id: str) -> int:
    """Number of labels, if the review sheet is the committed one, the commitment
    covers `run_id`, the sheet's Accept IDs are exactly the commitment's `ids`
    (each once, none missing, none extra) and every value is exactly y or n.

    Errors name counts and neutral IDs only, never models.
    """
    com = load_commitment(review_commitment)
    if com["schema"] != REVIEW_COMMITMENT_SCHEMA:
        raise HoldoutInputError(
            f"{review_commitment.as_posix()}: not a review-key commitment "
            f"(schema must be {REVIEW_COMMITMENT_SCHEMA!r})"
        )
    run_ids, ids = com.get("run_ids"), com.get("ids")
    if not _str_list(run_ids):
        raise _bad(review_commitment, "run_ids", "a list of strings")
    if not _str_list(ids) or len(set(ids)) != len(ids):
        raise _bad(review_commitment, "ids", "a list of distinct strings")
    header, labels = parse_review_sheet(sheet)  # a repeated Accept ID is refused there
    errors: list[str] = []
    if header != com["sha256"]:
        errors.append("its 'Review key commitment' line does not match the review commitment")
    if run_id not in run_ids:
        errors.append(f"the review commitment does not cover run {run_id}")
    missing = [rid for rid in ids if rid not in labels]
    extra = [rid for rid in labels if rid not in set(ids)]
    if missing:
        errors.append(f"{len(missing)} committed IDs have no Accept line: {', '.join(missing)}")
    if extra:
        errors.append(f"{len(extra)} Accept lines are not committed IDs: {', '.join(extra)}")
    blank = [rid for rid, v in labels.items() if v == ""]
    invalid = [rid for rid, v in labels.items() if v not in ("", "y", "n")]
    if blank:
        errors.append(f"blank: {', '.join(blank)}")
    if invalid:
        errors.append(f"not exactly y or n: {', '.join(invalid)}")
    if errors:
        raise HoldoutInputError(
            f"{sheet.as_posix()}: the review labels are not ready for the pair sheet: "
            + "; ".join(errors)
            + ". Nothing was written."
        )
    return len(labels)


# ------------------------------------------------------------------ pair sheet


@dataclass
class PairSheetResult:
    sheet: Path
    n_pairs: int  # shown
    n_total: int
    n_unavailable: int
    n_cases: int
    n_labels_checked: int


def _check_run_matches_plan(run: RunData, plan: dict[str, Any]) -> None:
    errors: list[str] = []
    if run.prompt_version != plan["prompt_version"]:
        errors.append(
            f"run {run.run_id} uses prompt version {run.prompt_version!r}; the plan is "
            f"for {plan['prompt_version']!r}"
        )
    if sorted(run.models) != sorted(plan["models"]):
        errors.append(
            f"run {run.run_id} models ({', '.join(run.models)}) do not match the plan's "
            f"models ({', '.join(plan['models'])})"
        )
    run_cases = [c for c, _ in run.cases]
    if sorted(run_cases) != sorted(plan["cases"]):
        errors.append(
            f"run {run.run_id} cases ({', '.join(run_cases)}) do not match the plan's "
            f"cases ({', '.join(plan['cases'])})"
        )
    if errors:
        raise HoldoutInputError("\n".join(errors) + "\nNothing was written.")


def _side_key(run: RunData, case: str, side: dict[str, Any]) -> str:
    return make_slot_key(run.run_id, case, run.prompt_version, side["model"], side["sample"])


def pair_fingerprint(a_text: str, b_text: str) -> str:
    """SHA-256 of canonical_json([A text, B text]); ties a pair sheet to its run."""
    return hashlib.sha256(canonical_json([a_text, b_text]).encode("utf-8")).hexdigest()


def _pair_texts(
    run: RunData, plan: dict[str, Any], what: str
) -> tuple[dict[str, tuple[str, str]], list[str]]:
    """({pair ID: (A text, B text)} for showable pairs, [unavailable pair IDs]).

    A pair with a failed or incomplete reply is unavailable (an operational
    failure). An empty reply is shown. A missing, duplicate, unknown-status or
    malformed slot refuses the command, with counts only: no pair ID, side, case
    or model, which with per-model failure counts could reveal the placement.
    """
    texts: dict[str, tuple[str, str]] = {}
    unavailable: list[str] = []
    counts: dict[str, int] = {}
    total = 0
    for pair in plan["pairs"]:
        found: list[str] = []
        operational = False
        for side in ("left", "right"):
            total += 1
            recs = run.by_key.get(_side_key(run, pair["case"], pair[side]), [])
            state = _slot_state(recs)
            if state in SHOWN_STATES:
                found.append(recs[0]["output_text"])
            elif state in OPERATIONAL_KINDS:
                operational = True
            else:
                counts[state] = counts.get(state, 0) + 1
        if operational:
            unavailable.append(pair["pair_id"])
        elif len(found) == 2:
            texts[pair["pair_id"]] = (found[0], found[1])
    if counts:
        bad = sum(counts.values())
        detail = ", ".join(f"{kind} {n}" for kind, n in sorted(counts.items()))
        raise HoldoutInputError(
            f"cannot build the {what}: {bad} of {total} pair replies "
            f"{_plural(bad, 'has', 'have')} an integrity problem ({detail}). Nothing was written."
        )
    return texts, unavailable


def create_pair_sheet(
    plan_private: Path,
    commitment: Path,
    run_dir: Path,
    out_dir: Path,
    review_sheet: Path,
    review_commitment: Path,
) -> PairSheetResult:
    sheet_path = out_dir / PAIR_SHEET_NAME
    private_dir = plan_private.resolve().parent
    out_resolved = out_dir.resolve()
    if out_resolved == private_dir or private_dir in out_resolved.parents:
        raise HoldoutInputError(
            f"{out_dir.as_posix()}: the pair sheet must not be written inside the folder "
            f"that holds the private plan ({private_dir.as_posix()}). Nothing was written."
        )
    _check_targets([sheet_path])
    plan, digest = _verified_plan(plan_private, commitment)
    run = load_run(run_dir)
    _check_run_matches_plan(run, plan)
    n_labels = check_review_labels(review_sheet, review_commitment, run.run_id)
    texts, unavailable = _pair_texts(run, plan, "pair sheet")
    total = len(plan["pairs"])

    turns_by_case = dict(run.cases)
    pairs = sorted((p for p in plan["pairs"] if p["pair_id"] in texts), key=lambda p: p["pair_id"])
    lines = [
        "# Holdout pair sheet",
        "",
        f"{PAIR_HEADER}{digest}",
        "",
        "For each pair, write A, B or tie after the colon on its Choice line, and a",
        "reason after its Reason line. Leave the reply text, the <<<<<<<< >>>>>>>>",
        "delimiter lines and the Fingerprint lines unchanged. Reply lines start with",
        f"'{REPLY_PREFIX.strip()}'; a reply with no text shows as {EMPTY_REPLY_LINE}.",
        "",
    ]
    if unavailable:
        lines += [f"{len(unavailable)} of {total} pairs cannot be shown.", ""]
    current_case: str | None = None
    for pair in pairs:
        if pair["case"] != current_case:
            current_case = pair["case"]
            lines += _context_lines(current_case, turns_by_case[current_case])
        pid = pair["pair_id"]
        a_text, b_text = texts[pid]
        lines += [
            f"=== PAIR {pid} ===",
            "<<<<<<<< A >>>>>>>>",
            *render_reply(a_text),
            "<<<<<<<< END A >>>>>>>>",
            "",
            "<<<<<<<< B >>>>>>>>",
            *render_reply(b_text),
            "<<<<<<<< END B >>>>>>>>",
            "",
            f"{FINGERPRINT_PREFIX}{pair_fingerprint(a_text, b_text)}",
            CHOICE_LINE,
            REASON_LINE,
            "",
        ]
    write_new_files([(sheet_path, "\n".join(lines))])
    return PairSheetResult(
        sheet_path, len(pairs), total, len(unavailable), len(plan["cases"]), n_labels
    )


@dataclass
class PairAnswer:
    choice: Literal["A", "B", "tie", "missing"]
    reason: str
    fingerprint: str


def parse_pair_sheet(path: Path, pair_ids: list[str], digest: str) -> dict[str, PairAnswer]:
    """{pair ID: answer} from a filled pair sheet; only lines outside the A/B
    delimiters are read. Structural problems and invalid choices are input errors;
    a blank choice is "missing" and a blank reason is "".
    """
    lines = _pair_lines(path)
    if _sheet_commitment(lines, PAIR_HEADER, path) != digest:
        raise HoldoutInputError(
            f"{path.as_posix()}: this pair sheet was made from a different pair plan "
            "(its commitment line does not match)"
        )
    raw: dict[str, str] = {}
    prints: dict[str, str] = {}
    reasons: dict[str, list[str]] = {}
    errors: list[str] = []
    current: str | None = None
    in_reason = False
    seen_titles: list[str] = []
    for line in lines:
        title = _PAIR_TITLE.match(line)
        if title or _CASE_TITLE.match(line):
            current = title.group(1) if title else None
            if title:
                seen_titles.append(current)  # type: ignore[arg-type]
            in_reason = False
            continue
        fp = _FINGERPRINT.match(line)
        choice = _CHOICE.match(line)
        reason = _REASON.match(line)
        if (fp or choice or reason) and current is None:
            errors.append("a Fingerprint, Choice or Reason line outside any pair")
            continue
        if fp:
            in_reason = False
            if current in prints:
                errors.append(f"{current}: more than one Fingerprint line")
            prints[current] = fp.group(1)  # type: ignore[index]
        elif choice:
            in_reason = False
            if current in raw:
                errors.append(f"{current}: more than one Choice line")
            raw[current] = choice.group(1).strip()  # type: ignore[index]
        elif reason:
            in_reason = True
            reasons.setdefault(current, []).append(reason.group(1))  # type: ignore[arg-type]
        elif in_reason and current is not None:
            reasons[current].append(line)
    if sorted(seen_titles) != sorted(pair_ids) or len(set(seen_titles)) != len(seen_titles):
        errors.append(
            "the sheet's pairs do not match the plan's pairs "
            f"({len(seen_titles)} titles for {len(pair_ids)} pairs)"
        )
    for what, have in (("Choice", raw), ("Fingerprint", prints)):
        absent = [p for p in pair_ids if p not in have]
        if absent:
            errors.append(f"no {what} line for {', '.join(absent)}")
    out: dict[str, PairAnswer] = {}
    for pid in pair_ids:
        value = raw.get(pid)
        if value is None or pid not in prints:
            continue
        low = value.lower()
        parsed: Literal["A", "B", "tie", "missing"]
        if low == "":
            parsed = "missing"
        elif low == "a":
            parsed = "A"
        elif low == "b":
            parsed = "B"
        elif low == "tie":
            parsed = "tie"
        else:
            errors.append(f"{pid}: choice {value!r} is not A, B or tie")
            continue
        out[pid] = PairAnswer(parsed, "\n".join(reasons.get(pid, [])).strip(), prints[pid])
    if errors:
        raise HoldoutInputError(f"{path.as_posix()}: " + "; ".join(errors))
    return out


# ---------------------------------------------------------------- machine verdicts


def _score_records(scores_dir: Path, run_id: str) -> list[dict[str, Any]]:
    path = scores_dir / f"{run_id}.jsonl"
    if not path.is_file():
        raise HoldoutInputError(f"{path.as_posix()}: score file not found for run {run_id}")
    try:
        return scoring.read_score_records(path)
    except scoring.ScoringInputError as exc:
        raise HoldoutInputError(str(exc)) from None


def first_scored(
    records: list[dict[str, Any]], slot_key: str, judge_version: str, text_sha256: str
) -> dict[str, Any] | None:
    """The first record with this slot key, reply-text SHA-256, judge version and
    status scored. A record for different words (another text SHA) doesn't count,
    as in the scorer's own reuse identity.
    """
    return next(
        (
            r
            for r in records
            if r.get("slot_key") == slot_key
            and r.get("text_sha256") == text_sha256
            and r.get("judge_prompt_version") == judge_version
            and r.get("status") == "scored"
        ),
        None,
    )


UNSCORED_INVALID = "unscored (invalid or failed judgment)"
UNSCORED_BUDGET = "unscored (budget)"
UNSCORED_NONE = "unscored (no judge record)"


def unscored_reason(
    records: list[dict[str, Any]], slot_key: str, judge_version: str, text_sha256: str
) -> str:
    """Why a reply has no scored record: the latest attempt for the same slot,
    judge version and words decides (budget_stopped -> budget; needs_review or
    judge_failed -> invalid or failed judgment, however many attempts); no
    attempt at all is its own reason."""
    attempts = [
        r
        for r in records
        if r.get("slot_key") == slot_key
        and r.get("text_sha256") == text_sha256
        and r.get("judge_prompt_version") == judge_version
    ]
    if not attempts:
        return UNSCORED_NONE
    if attempts[-1].get("status") == "budget_stopped":
        return UNSCORED_BUDGET
    return UNSCORED_INVALID


def _acceptable(record: dict[str, Any]) -> bool:
    decision = record.get("decision")
    if not isinstance(decision, dict) or not isinstance(decision.get("acceptable"), bool):
        raise HoldoutInputError(
            f"score record for {record.get('slot_key')}: decision.acceptable is not true or false"
        )
    return decision["acceptable"]


@dataclass(frozen=True)
class Rank:
    clean: int
    acceptable: int
    total: int
    single_turn_pass: bool
    critical_entries: int

    def as_tuple(self) -> tuple[int, int, int]:
        return (self.clean, self.acceptable, self.total)


def rank_of(record: dict[str, Any]) -> Rank:
    """The rank tuple from a raw scorer-1 record (listed criticals count as-is)."""
    where = f"score record for {record.get('slot_key')}"
    if record.get("scorer_version") != "scorer-1":
        raise HoldoutInputError(
            f"{where}: scorer version {record.get('scorer_version')!r}; the pair "
            "comparison reads scorer-1 critical-violation lists only"
        )
    acceptable = _acceptable(record)
    total = record["decision"].get("total")
    if total is not None and type(total) is not int:
        raise HoldoutInputError(f"{where}: decision.total is not an integer or null")
    structural = record.get("structural")
    if not isinstance(structural, dict) or not isinstance(
        structural.get("single_turn_pass"), bool
    ):
        raise HoldoutInputError(f"{where}: structural.single_turn_pass is not true or false")
    passed = structural["single_turn_pass"]
    judgment = record.get("judgment")
    if judgment is None:
        if passed:
            raise HoldoutInputError(
                f"{where}: no judgment, but the reply passes the single-turn check"
            )
        entries = 0
    else:
        if not isinstance(judgment, dict) or not isinstance(
            judgment.get("critical_violations"), list
        ):
            raise HoldoutInputError(f"{where}: judgment.critical_violations is not a list")
        entries = len(judgment["critical_violations"])
    return Rank(
        clean=1 if passed and entries == 0 else 0,
        acceptable=1 if acceptable else 0,
        total=-1 if total is None else total,
        single_turn_pass=passed,
        critical_entries=entries,
    )


Outcome3 = Literal["A", "B", "tie"]
RANK_KEYS = ("clean", "acceptable", "total")


def machine_result(
    left: Rank, right: Rank
) -> tuple[Outcome3, Literal["clean", "acceptable", "total", "tie"], bool]:
    """(result, deciding key, raw critical entry decisive)."""
    for i, key in enumerate(RANK_KEYS):
        lv, rv = left.as_tuple()[i], right.as_tuple()[i]
        if lv != rv:
            loser = right if lv > rv else left
            decisive = key == "clean" and loser.single_turn_pass and loser.critical_entries > 0
            return ("A" if lv > rv else "B"), key, decisive  # type: ignore[return-value]
    return "tie", "tie", False


# ---------------------------------------------------------------- pair compare


def _empty_confusion() -> dict[str, dict[str, int]]:
    return {h: {m: 0 for m in ("A", "B", "tie")} for h in ("A", "B", "tie")}


def pair_compare(
    plan_private: Path,
    commitment: Path,
    run_dir: Path,
    pair_sheet: Path,
    scores_dir: Path,
    judge_version: str,
) -> dict[str, Any]:
    plan, digest = _verified_plan(plan_private, commitment)
    run = load_run(run_dir)
    _check_run_matches_plan(run, plan)
    texts, unavailable = _pair_texts(run, plan, "pair comparison")
    shown_ids = [p["pair_id"] for p in plan["pairs"] if p["pair_id"] in texts]
    answers = parse_pair_sheet(pair_sheet, shown_ids, digest)
    if all(a.choice == "missing" for a in answers.values()):
        raise HoldoutInputError(
            f"{pair_sheet.as_posix()}: every Choice line is blank. Fill in and commit the "
            "pair sheet before comparing; nothing was compared or printed."
        )
    mismatched = [
        pid for pid in sorted(shown_ids) if answers[pid].fingerprint != pair_fingerprint(*texts[pid])
    ]
    if mismatched:
        raise HoldoutInputError(
            f"{pair_sheet.as_posix()}: the Fingerprint line does not match run "
            f"{run.run_id} for {', '.join(mismatched)}; this sheet was not made from "
            "this run's replies. Nothing was compared."
        )
    records = _score_records(scores_dir, run.run_id)

    rows: list[dict[str, Any]] = []
    for pair in sorted(plan["pairs"], key=lambda p: p["pair_id"]):
        pid = pair["pair_id"]
        shown = pid in texts
        sides: dict[str, dict[str, Any]] = {}
        ranks: dict[str, Rank | None] = {}
        reasons: list[str] = []
        for i, side in enumerate(("left", "right")):
            key = _side_key(run, pair["case"], pair[side])
            rank: Rank | None = None
            reason: str | None = None
            if shown:
                text_sha = _text_sha(texts[pid][i])
                rec = first_scored(records, key, judge_version, text_sha)
                if rec is not None:
                    rank = rank_of(rec)
                else:
                    reason = unscored_reason(records, key, judge_version, text_sha)
            ranks[side] = rank
            sides[side] = {
                "model": pair[side]["model"],
                "sample": pair[side]["sample"],
                "slot_key": key,
                "scored": rank is not None,
                "unscored_reason": reason,
                "rank": list(rank.as_tuple()) if rank else None,
                "single_turn_pass": rank.single_turn_pass if rank else None,
                "critical_entries": rank.critical_entries if rank else None,
            }
        left, right = ranks["left"], ranks["right"]
        if left is None or right is None:
            machine, decided, decisive = "missing", None, False
        else:
            machine, decided, decisive = machine_result(left, right)
        human = answers[pid].choice if shown else "missing"
        if not shown:
            reasons = [OPERATIONAL_REASON]
        else:
            if human == "missing":
                reasons.append("human blank")
            for side in ("left", "right"):
                r = sides[side]["unscored_reason"]
                if r is not None and r not in reasons:
                    reasons.append(r)
        evaluable = not reasons
        rows.append(
            {
                "pair_id": pid,
                "case": pair["case"],
                "shown": shown,
                "left": sides["left"],
                "right": sides["right"],
                "human": human,
                "machine": machine,
                "deciding_key": decided,
                "raw_critical_decisive": decisive,
                "evaluable": evaluable,
                "exact_match": (human == machine) if evaluable else None,
                "missing_reasons": reasons,
                "human_reason": answers[pid].reason if shown else "",
            }
        )
    evaluable_rows = [r for r in rows if r["evaluable"]]
    exact = sum(1 for r in evaluable_rows if r["exact_match"])
    confusion = _empty_confusion()
    for r in evaluable_rows:
        confusion[r["human"]][r["machine"]] += 1
    chosen = [r for r in rows if r["human"] != "missing"]
    by_reason: dict[str, int] = {}
    for r in rows:
        for reason in r["missing_reasons"]:
            by_reason[reason] = by_reason.get(reason, 0) + 1
    return {
        "run_id": run.run_id,
        "judge_prompt_version": judge_version,
        "plan_commitment_sha256": digest,
        "pairs": rows,
        "summary": {
            "total_pairs": len(rows),
            "shown_pairs": len(shown_ids),
            "unavailable_pairs": len(unavailable),
            "evaluable": len(evaluable_rows),
            "exact_matches": exact,
            "exact_match_fraction": (exact / len(evaluable_rows)) if evaluable_rows else None,
            "confusion_human_by_machine": confusion,
            "human_ties": sum(1 for r in rows if r["human"] == "tie"),
            "machine_ties": sum(1 for r in rows if r["machine"] == "tie"),
            "human_chosen": len(chosen),
            "chosen_without_reason": sum(1 for r in chosen if not r["human_reason"]),
            "missing_by_reason": by_reason,
            "missing": [
                {"pair_id": r["pair_id"], "reasons": r["missing_reasons"]}
                for r in rows
                if not r["evaluable"]
            ],
        },
    }


def _fmt_rank(rank: list[int] | None) -> str:
    return "unscored" if rank is None else "(" + ",".join(str(v) for v in rank) + ")"


def _table(header: list[str], rows: list[list[str]]) -> list[str]:
    widths = [max(len(header[i]), *(len(r[i]) for r in rows)) for i in range(len(header))]
    fmt = "  ".join(f"{{:<{w}}}" for w in widths)
    return [fmt.format(*header).rstrip()] + [fmt.format(*r).rstrip() for r in rows]


def format_pair_report(report: dict[str, Any]) -> str:
    s = report["summary"]
    lines = [
        f"Pair comparison: run {report['run_id']}, judge {report['judge_prompt_version']}",
        "Rank tuple: (clean, acceptable, total); clean = single-turn pass and no raw "
        "critical entry.",
        "",
    ]
    lines += _table(
        ["pair", "case", "left (A)", "right (B)", "human", "machine", "A rank",
         "B rank", "decided by", "raw critical decisive"],
        [
            [
                r["pair_id"],
                r["case"],
                f"{r['left']['model']} s{r['left']['sample']}",
                f"{r['right']['model']} s{r['right']['sample']}",
                r["human"] if r["shown"] else "not shown",
                r["machine"],
                _fmt_rank(r["left"]["rank"]),
                _fmt_rank(r["right"]["rank"]),
                r["deciding_key"] or "-",
                "yes" if r["raw_critical_decisive"] else "no",
            ]
            for r in report["pairs"]
        ],
    )
    lines += ["", "Reasons:"]
    for r in report["pairs"]:
        if not r["shown"]:
            continue
        text = r["human_reason"].replace("\n", " / ") if r["human_reason"] else "(none)"
        lines.append(f"{r['pair_id']}: {text}")
    n, k = s["evaluable"], s["exact_matches"]
    frac = "n/a" if s["exact_match_fraction"] is None else f"{s['exact_match_fraction']:.3f}"
    lines += [
        "",
        f"Evaluable pairs: {n} of {s['total_pairs']}",
        f"Exact matches: {k} of {n} ({frac})",
        "",
        "Confusion over evaluable pairs (rows human, columns machine):",
    ]
    conf = s["confusion_human_by_machine"]
    lines += _table(
        ["human \\ machine", "A", "B", "tie"],
        [[h, *(str(conf[h][m]) for m in ("A", "B", "tie"))] for h in ("A", "B", "tie")],
    )
    lines += [
        "",
        f"Human ties: {s['human_ties']} of {s['total_pairs']} pairs",
        f"Machine ties: {s['machine_ties']} of {s['total_pairs']} pairs",
        f"Chosen pairs without a reason: {s['chosen_without_reason']} of {s['human_chosen']}",
    ]
    if s["missing"]:
        lines.append(
            "Missing: "
            + ", ".join(f"{m['pair_id']} ({'; '.join(m['reasons'])})" for m in s["missing"])
        )
        lines.append(
            "Missing by reason: "
            + ", ".join(f"{reason} {n}" for reason, n in s["missing_by_reason"].items())
        )
    else:
        lines.append("Missing: none")
    return "\n".join(lines)


# -------------------------------------------------------------- review compare


def _counts() -> dict[str, Any]:
    return {
        "shown": 0,
        "human_accepted": 0,
        "judge_acceptable": 0,
        "unscored": 0,
        "unscored_by_reason": {},
        "operational_failures": 0,
        "evaluable": 0,
        "agree": 0,
    }


def review_compare(
    key_path: Path,
    commitment: Path,
    sheet: Path,
    scores_dir: Path,
    judge_version: str,
) -> dict[str, Any]:
    entries, unavailable, com = _verified_key(key_path, commitment)
    header, labels = parse_review_sheet(sheet)
    if header != com["sha256"]:
        raise HoldoutInputError(
            f"{sheet.as_posix()}: this review sheet belongs to a different review key "
            "(its commitment line does not match)"
        )
    errors: list[str] = []
    missing = [rid for rid in entries if rid not in labels]
    extra = [rid for rid in labels if rid not in entries]
    blank = [rid for rid in entries if labels.get(rid) == ""]
    invalid = [rid for rid in entries if labels.get(rid) not in (None, "", "y", "n")]
    if missing:
        errors.append(f"no Accept line for {', '.join(missing)}")
    if extra:
        errors.append(f"Accept lines for unknown IDs {', '.join(extra)}")
    if blank:
        errors.append(f"blank labels: {', '.join(blank)}")
    if invalid:
        errors.append(f"labels not exactly y or n: {', '.join(invalid)}")
    if errors:
        raise HoldoutInputError(f"{sheet.as_posix()}: " + "; ".join(errors))

    run_ids = dict.fromkeys(
        [e["run_id"] for e in entries.values()] + [u["run_id"] for u in unavailable]
    )
    records_by_run = {run_id: _score_records(scores_dir, run_id) for run_id in run_ids}
    replies: list[dict[str, Any]] = []
    for rid in sorted(entries):
        e = entries[rid]
        records = records_by_run[e["run_id"]]
        # e["text_sha256"]: the slot's words when the sheet was made (committed)
        rec = first_scored(records, e["slot_key"], judge_version, e["text_sha256"])
        judge = None if rec is None else _acceptable(rec)
        reason = (
            None if rec is not None
            else unscored_reason(records, e["slot_key"], judge_version, e["text_sha256"])
        )
        human = labels[rid] == "y"
        replies.append(
            {
                "id": rid,
                "case": rid.rsplit("-", 1)[0],
                "run_id": e["run_id"],
                "prompt_version": e["prompt_version"],
                "model": e["model"],
                "sample_index": e["sample_index"],
                "human_accept": human,
                "judge_acceptable": judge,
                "unscored_reason": reason,
                "agree": None if judge is None else judge == human,
            }
        )

    def tally(group_keys: tuple[str, ...]) -> list[dict[str, Any]]:
        groups: dict[tuple[str, ...], dict[str, Any]] = {}
        for r in replies:
            c = groups.setdefault(tuple(r[k] for k in group_keys), _counts())
            c["shown"] += 1
            c["human_accepted"] += int(r["human_accept"])
            if r["judge_acceptable"] is None:
                c["unscored"] += 1
                c["unscored_by_reason"][r["unscored_reason"]] = (
                    c["unscored_by_reason"].get(r["unscored_reason"], 0) + 1
                )
            else:
                c["evaluable"] += 1
                c["judge_acceptable"] += int(r["judge_acceptable"])
                c["agree"] += int(r["agree"])
        for u in unavailable:
            row = {"case": u["case_id"], "prompt_version": u["prompt_version"], "model": u["model"]}
            c = groups.setdefault(tuple(row[k] for k in group_keys), _counts())
            c["operational_failures"] += 1
        return [{**dict(zip(group_keys, k)), **v} for k, v in sorted(groups.items())]

    return {
        "run_ids": com.get("run_ids"),
        "judge_prompt_version": judge_version,
        "review_commitment_sha256": com["sha256"],
        "n_replies": len(replies),
        "operational_failures": unavailable_counts(unavailable),
        "by_prompt_model": tally(("prompt_version", "model")),
        "by_case_prompt_model": tally(("case", "prompt_version", "model")),
        "disagreements": [r for r in replies if r["agree"] is False],
        "unscored": [{"id": r["id"], "reason": r["unscored_reason"]} for r in replies if r["judge_acceptable"] is None],
        "replies": replies,
    }


def _count_cells(c: dict[str, Any]) -> list[str]:
    reasons = "; ".join(f"{k} {v}" for k, v in sorted(c["unscored_by_reason"].items()))
    return [
        str(c["shown"]),
        f"{c['human_accepted']}/{c['shown']}",
        f"{c['judge_acceptable']}/{c['shown']}",
        str(c["unscored"]) + (f" ({reasons})" if reasons else ""),
        str(c["operational_failures"]),
        str(c["evaluable"]),
        f"{c['agree']}/{c['evaluable']}",
    ]


def format_review_report(report: dict[str, Any]) -> str:
    cols = [
        "shown", "human accepted", "judge acceptable", "unscored (reason)",
        "operational failures (not shown)", "evaluable", "agreement (evaluable)",
    ]
    ops = report["operational_failures"]
    lines = [
        f"Review comparison: runs {', '.join(report['run_ids'] or [])}, judge "
        f"{report['judge_prompt_version']}, {report['n_replies']} replies shown; "
        f"operational failures not shown: {_counts_text(ops)}",
        "",
        "By prompt and model:",
    ]
    lines += _table(
        ["prompt", "model", *cols],
        [[c["prompt_version"], c["model"], *_count_cells(c)] for c in report["by_prompt_model"]],
    )
    lines += ["", "By case, prompt and model:"]
    lines += _table(
        ["case", "prompt", "model", *cols],
        [
            [c["case"], c["prompt_version"], c["model"], *_count_cells(c)]
            for c in report["by_case_prompt_model"]
        ],
    )
    lines += ["", "Disagreements:"]
    if report["disagreements"]:
        lines += _table(
            ["id", "prompt", "model", "sample", "human", "judge"],
            [
                [
                    d["id"], d["prompt_version"], d["model"], str(d["sample_index"]),
                    "accept" if d["human_accept"] else "reject",
                    "acceptable" if d["judge_acceptable"] else "not acceptable",
                ]
                for d in report["disagreements"]
            ],
        )
    else:
        lines.append("none")
    lines.append(
        "Unscored: "
        + (
            ", ".join(f"{u['id']} ({u['reason']})" for u in report["unscored"])
            if report["unscored"]
            else "none"
        )
    )
    return "\n".join(lines)


def check_json_out(path: Path, scores_dir: Path) -> None:
    """Refuse a report path that exists, is inside runs or inside the scores dir."""
    target = path.resolve()
    sd = scores_dir.resolve()
    if target == sd or sd in target.parents:
        raise HoldoutInputError(
            f"{path.as_posix()}: inside the scores directory; reports are never written there"
        )
    _check_targets([path])


def write_json_report(path: Path, report: dict[str, Any], scores_dir: Path) -> None:
    """Write a report once; never inside runs or the scores directory."""
    check_json_out(path, scores_dir)
    write_new_files([(path, _json_text(report))])
