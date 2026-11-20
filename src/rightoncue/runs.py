"""Run directory storage: manifest, slots, resume, blind view."""

from __future__ import annotations

import hashlib
import json
import os
import platform
import secrets
import subprocess
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable, Literal

import openai

from .openai_responses import build_request, generate
from .transcript import parse_transcript

FATAL_ERRORS = (
    openai.AuthenticationError,
    openai.PermissionDeniedError,
    openai.BadRequestError,
    openai.NotFoundError,
)
RECOVERABLE_ERRORS = (
    openai.RateLimitError,
    openai.APIConnectionError,  # parent of APITimeoutError
    openai.InternalServerError,
)

PARAMS_NOTE = (
    "Only model, instructions, input and reasoning.effort are sent. Every other "
    "generation parameter (temperature, max_output_tokens, store, ...) is left to "
    "the API defaults."
)


@dataclass
class InputFile:
    path: str
    raw: bytes

    @property
    def sha256(self) -> str:
        return hashlib.sha256(self.raw).hexdigest()

    @property
    def text(self) -> str:
        return self.raw.decode("utf-8").lstrip("﻿")

    @property
    def stem(self) -> str:
        return Path(self.path).stem


def new_run_id() -> str:
    return datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ") + "-" + secrets.token_hex(3)


def _git_state() -> dict[str, Any]:
    try:
        sha = subprocess.run(
            ["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True
        ).stdout.strip()
        dirty = bool(
            subprocess.run(
                ["git", "status", "--porcelain"],
                capture_output=True,
                text=True,
                check=True,
            ).stdout.strip()
        )
    except (OSError, subprocess.CalledProcessError):
        return {"head_sha": None, "dirty": None}
    return {"head_sha": sha, "dirty": dirty}


def _write_json(path: Path, data: Any) -> None:
    path.write_text(
        json.dumps(data, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def create_run(
    runs_dir: Path,
    run_id: str,
    prompt: InputFile,
    cases: list[InputFile],
    model: str,
    reasoning_effort: str,
    samples: int,
    client_max_retries: int,
    client_timeout: str,
) -> tuple[Path, dict[str, Any]]:
    """Write manifest.json (before any API call) and return (run_dir, manifest)."""
    run_dir = runs_dir / run_id
    run_dir.mkdir(parents=True, exist_ok=False)
    case_entries: list[dict[str, Any]] = []
    for case in cases:
        turns = parse_transcript(case.text)
        case_entries.append(
            {
                "case_id": case.stem,
                "path": case.path,
                "sha256": case.sha256,
                "raw_text": case.text,
                "turns": [t.model_dump() for t in turns],
                "request": build_request(prompt.text, turns, model, reasoning_effort),
            }
        )
    manifest: dict[str, Any] = {
        "run_id": run_id,
        "created_at": datetime.now(UTC).isoformat(),
        "git": _git_state(),
        "openai_sdk_version": openai.__version__,
        "python_version": platform.python_version(),
        "client": {"max_retries": client_max_retries, "timeout": client_timeout},
        "prompt": {
            "path": prompt.path,
            "version": prompt.stem,
            "sha256": prompt.sha256,
            "text": prompt.text,
        },
        "cases": case_entries,
        "model": model,
        "reasoning_effort": reasoning_effort,
        "samples_per_case": samples,
        "generation_params_note": PARAMS_NOTE,
    }
    _write_json(run_dir / "manifest.json", manifest)
    return run_dir, manifest


def load_manifest(run_dir: Path) -> dict[str, Any]:
    return json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))


def read_slots(run_dir: Path) -> list[dict[str, Any]]:
    path = run_dir / "slots.jsonl"
    if not path.exists():
        return []
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").split("\n")
        if line.strip()
    ]


def make_slot_key(
    run_id: str, case_id: str, prompt_version: str, model: str, sample_index: int
) -> str:
    return f"{run_id}|{case_id}|{prompt_version}|{model}|{sample_index}"


def _append_slot(run_dir: Path, record: dict[str, Any]) -> None:
    line = json.dumps(record, ensure_ascii=False) + "\n"
    with open(run_dir / "slots.jsonl", "ab") as fh:
        fh.write(line.encode("utf-8"))
        fh.flush()
        os.fsync(fh.fileno())


@dataclass
class RunResult:
    attempted: int = 0
    skipped: int = 0
    failed: int = 0
    incomplete: int = 0
    empty: int = 0  # completed replies with no text (also counted as completed)
    abort_message: str | None = None
    records: list[dict[str, Any]] = field(default_factory=list)


def run_slots(
    client: Any,
    run_dir: Path,
    manifest: dict[str, Any],
    on_slot: Callable[[dict[str, Any]], None] | None = None,
) -> RunResult:
    run_id = manifest["run_id"]
    version = manifest["prompt"]["version"]
    model = manifest["model"]
    done = {s["slot_key"] for s in read_slots(run_dir)}
    result = RunResult()
    for case in manifest["cases"]:
        for idx in range(1, manifest["samples_per_case"] + 1):
            key = make_slot_key(run_id, case["case_id"], version, model, idx)
            if key in done:
                result.skipped += 1
                continue
            record: dict[str, Any] = {
                "slot_key": key,
                "case_id": case["case_id"],
                "prompt_version": version,
                "requested_model": model,
                "sample_index": idx,
            }
            started = datetime.now(UTC)
            t0 = time.monotonic()
            fatal = False
            try:
                response, dump = generate(client, case["request"])
            except (*FATAL_ERRORS, *RECOVERABLE_ERRORS) as exc:
                fatal = isinstance(exc, FATAL_ERRORS)
                record.update(
                    status="generation_failed",
                    output_text=None,
                    returned_model=None,
                    response_id=None,
                    response_status=None,
                    incomplete_details=None,
                    usage=None,
                    raw_response=None,
                    error={
                        "type": type(exc).__name__,
                        "message": str(exc),
                        "status_code": getattr(exc, "status_code", None),
                    },
                )
            else:
                if response.status == "completed":
                    status = "ok"
                elif response.status == "incomplete":
                    status = "incomplete"
                else:
                    status = "generation_failed"
                record.update(
                    status=status,
                    output_text=response.output_text,
                    returned_model=response.model,
                    response_id=response.id,
                    response_status=response.status,
                    incomplete_details=dump.get("incomplete_details"),
                    usage=dump.get("usage"),
                    raw_response=dump,
                )
                if status == "generation_failed":
                    record["error"] = {
                        "type": "response_status",
                        "message": f"response status {response.status!r}",
                        "status_code": None,
                    }
            record.update(
                started_at=started.isoformat(),
                finished_at=datetime.now(UTC).isoformat(),
                latency_ms=round((time.monotonic() - t0) * 1000),
            )
            _append_slot(run_dir, record)
            done.add(key)
            result.attempted += 1
            result.records.append(record)
            if record["status"] == "generation_failed":
                result.failed += 1
            elif record["status"] == "incomplete":
                result.incomplete += 1
            elif not (record["output_text"] or "").strip():
                result.empty += 1
            if on_slot is not None:
                on_slot(record)
            if fatal:
                err = record["error"]
                result.abort_message = (
                    f"aborting remaining slots: {err['type']} (HTTP "
                    f"{err['status_code']}): {err['message']}. Check your API key, "
                    "model name and request settings."
                )
                return result
    return result


# ---------------------------------------------------------------- blind view


class RunNotReadyError(Exception):
    """Some case has fewer recorded expected slots than the manifest requires."""

    def __init__(self, lines: list[str]) -> None:
        super().__init__("\n".join(lines))
        self.lines = lines


class BlindKeyError(Exception):
    """The blind key/sheet pair cannot be created or matched safely."""


@dataclass
class BlindReview:
    text: str
    sheet_status: Literal["created", "preserved"]
    problems: list[str]


LEGACY_NOTE = (
    "This review's key was saved before text fingerprints were recorded, so the "
    "words can't be checked against what was first shown. Each reply below is the "
    "only text saved for its slot."
)
ONE_REPLY_NOTE = "Only one eligible reply, so a pairwise preference can't be collected."
NO_REPLY_NOTE = "No eligible replies for this case; nothing to judge."


def _label(i: int) -> str:
    return chr(ord("A") + i)


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _candidates(records: list[dict[str, Any]]) -> list[str]:
    """Distinct usable texts (status ok, non-empty) among a slot's records."""
    out: list[str] = []
    for r in records:
        text = r.get("output_text")
        if r.get("status") == "ok" and isinstance(text, str) and text.strip():
            if text not in out:
                out.append(text)
    return out


def _entry_key(entry: Any) -> str:
    return entry if isinstance(entry, str) else entry["slot_key"]


def _plural(n: int, one: str, many: str) -> str:
    return one if n == 1 else many


def _sheet_fields(labels: list[str]) -> list[str]:
    n = len(labels)
    if n == 0:
        return []
    if n == 1:
        return [f"Accept {labels[0]}? (y/n):", "One-sentence reason:", ""]
    return [
        f"Preference ({' / '.join(labels)} / tie):",
        "Words that tipped it:",
        "One-sentence reason:",
        *[f"Accept {lb}? (y/n):" for lb in labels],
        "",
    ]


RACE_MESSAGE = (
    "Another show created this review at the same time; run show again."
)


def _create_exclusive(path: Path, content: str) -> None:
    """Write a new file; raise BlindKeyError if it already exists."""
    try:
        with open(path, "x", encoding="utf-8", newline="\n") as fh:
            fh.write(content)
            fh.flush()
            os.fsync(fh.fileno())
    except FileExistsError:
        raise BlindKeyError(f"{path.name}: {RACE_MESSAGE}") from None


def render_blind(run_dir: Path) -> BlindReview:
    """Build the blind view; create blind_key.json / blind_sheet.md only if needed.

    Raises RunNotReadyError (before touching any file) if any expected slot has no
    record, and BlindKeyError if the sheet exists but some case has no mapping.
    """
    manifest = load_manifest(run_dir)
    records = read_slots(run_dir)
    run_id = manifest["run_id"]
    version = manifest["prompt"]["version"]
    model = manifest["model"]
    by_key: dict[str, list[dict[str, Any]]] = {}
    for r in records:
        by_key.setdefault(r["slot_key"], []).append(r)
    expected: dict[str, list[str]] = {
        c["case_id"]: [
            make_slot_key(run_id, c["case_id"], version, model, i)
            for i in range(1, manifest["samples_per_case"] + 1)
        ]
        for c in manifest["cases"]
    }
    short = [
        f"{cid}: {have} of {len(keys)} samples recorded"
        for cid, keys in expected.items()
        if (have := sum(1 for k in keys if k in by_key)) < len(keys)
    ]
    if short:
        raise RunNotReadyError(short)

    problems: list[str] = []
    all_expected = {k for keys in expected.values() for k in keys}
    unknown = sum(1 for r in records if r["slot_key"] not in all_expected)
    if unknown:
        problems.append(
            f"{unknown} saved {_plural(unknown, 'record matches', 'records match')} "
            f"no expected reply slot and {_plural(unknown, 'was', 'were')} ignored."
        )

    key_path = run_dir / "blind_key.json"
    sheet_path = run_dir / "blind_sheet.md"
    sheet_exists = sheet_path.exists()
    key_exists = key_path.exists()
    blind_key: dict[str, dict[str, Any]] = {}
    if key_exists:
        try:
            blind_key = json.loads(key_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            blind_key = None  # type: ignore[assignment]
        if not isinstance(blind_key, dict):
            raise BlindKeyError(
                "blind_key.json is empty or unreadable, possibly from an interrupted "
                "show. It is never rewritten automatically. If blind_sheet.md does not "
                "exist yet, nothing was reviewed: delete blind_key.json and run show "
                "again. Nothing was written."
            )
    if key_exists and any(c["case_id"] not in blind_key for c in manifest["cases"]):
        raise BlindKeyError(
            "blind_key.json has no letter mapping for some case; an existing key is "
            "never rewritten. Nothing was written."
        )
    if not key_exists and sheet_exists:
        raise BlindKeyError(
            "blind_sheet.md exists but blind_key.json does not, so the sheet's "
            "letters can't be matched. Nothing was written."
        )

    changed = not key_exists
    legacy_used = False
    view: list[str] = []
    sheet: list[str] = []
    for case in manifest["cases"]:
        cid = case["case_id"]
        keys = expected[cid]
        if not key_exists:
            eligible = [k for k in keys if len(_candidates(by_key[k])) == 1]
            secrets.SystemRandom().shuffle(eligible)
            blind_key[cid] = {
                _label(i): {
                    "slot_key": k,
                    "text_sha256": _sha(_candidates(by_key[k])[0]),
                }
                for i, k in enumerate(eligible)
            }
        mapping = blind_key[cid]

        turns = case["turns"]
        agent_idx = max(
            (i for i, t in enumerate(turns[:-1]) if t["role"] == "agent"), default=None
        )
        lines = [f"=== CASE {cid} ===", "Riley's previous turn:"]
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

        shown: list[str] = []
        notices: list[str] = []
        for label, entry in mapping.items():
            recs = by_key.get(_entry_key(entry), [])
            text: str | None = None
            if isinstance(entry, str):
                # Old code showed the LAST record per slot whatever its status, so
                # the shown words are known only if all records carry one string.
                raw = {r.get("output_text") for r in recs}
                if len(raw) == 1 and isinstance(next(iter(raw)), str):
                    text = next(iter(raw))
                    legacy_used = True
                    bad = next(
                        (
                            r for r in recs
                            if r.get("status") != "ok" or not r["output_text"].strip()
                        ),
                        None,
                    )
                    if bad is not None:
                        what = (
                            "was incomplete" if bad.get("status") == "incomplete"
                            else "failed" if bad.get("status") != "ok"
                            else "had no text"
                        )
                        notices.append(
                            f"Reply {label}: this older review included a reply "
                            f"that {what}."
                        )
                else:
                    notices.append(
                        f"Reply {label}: this older review's key has no fingerprint "
                        "and the slot has differing records, so the words "
                        "originally shown can't be verified; no text is shown."
                    )
                    continue
            else:
                ok_texts = [
                    r["output_text"]
                    for r in recs
                    if r.get("status") == "ok" and isinstance(r.get("output_text"), str)
                ]
                matches = [t for t in ok_texts if _sha(t) == entry["text_sha256"]]
                if matches:
                    text = matches[0]
            # Any other record under a reviewed slot (any status) is a discrepancy.
            if text is not None and not isinstance(entry, str) and any(
                r.get("status") != "ok" or r.get("output_text") != text for r in recs
            ):
                notices.append(
                    f"Reply {label}: a later saved record differs from the reviewed "
                    "one; showing the originally reviewed words."
                )
            if text is None:
                notices.append(
                    f"Reply {label}: the reviewed text can't be found or verified "
                    "in slots.jsonl and is not shown."
                )
                continue
            shown.append(label)
            lines += [
                f"<<<<<<<< REPLY {label} >>>>>>>>",
                text if text != "" else "(empty reply)",
                f"<<<<<<<< END REPLY {label} >>>>>>>>",
                "",
            ]
        problems.extend(f"{cid}: {m}" for m in notices)

        mapped = {_entry_key(e) for e in mapping.values()}
        later = conflicts = 0
        counts = {"incomplete": 0, "failed": 0, "empty": 0}
        for k in keys:
            if k in mapped:
                continue
            recs = by_key[k]
            texts = _candidates(recs)
            if len(texts) == 1:
                later += 1
            elif len(texts) > 1:
                conflicts += 1
            else:
                st = recs[-1].get("status")
                bucket = (
                    "incomplete" if st == "incomplete" else "empty" if st == "ok" else "failed"
                )
                counts[bucket] += 1
        n = len(keys)
        status_lines: list[str] = []
        if c := counts["incomplete"]:
            status_lines.append(
                f"{c} of {n} replies {_plural(c, 'was', 'were')} incomplete and "
                f"{_plural(c, 'is', 'are')} not shown."
            )
        if c := counts["failed"]:
            status_lines.append(
                f"{c} of {n} replies failed to generate and "
                f"{_plural(c, 'is', 'are')} not shown."
            )
        if c := counts["empty"]:
            status_lines.append(
                f"{c} of {n} replies returned no text and "
                f"{_plural(c, 'is', 'are')} not shown."
            )
        flagged: list[str] = []
        if later:
            flagged.append(
                f"{later} eligible {_plural(later, 'reply was', 'replies were')} "
                "recorded after this review was frozen; "
                f"{_plural(later, 'it is', 'they are')} not part of this review and "
                f"{_plural(later, 'is', 'are')} not shown."
            )
        if conflicts:
            flagged.append(
                f"{conflicts} reply {_plural(conflicts, 'slot has', 'slots have')} "
                f"conflicting saved texts and {_plural(conflicts, 'is', 'are')} "
                "not eligible."
            )
        problems.extend(f"{cid}: {m}" for m in flagged)
        lines += notices + flagged + status_lines
        if len(shown) == 1:
            lines.append(ONE_REPLY_NOTE)
        elif not shown:
            lines.append(NO_REPLY_NOTE)
        lines.append("")
        view.extend(lines)
        sheet.extend(lines)
        sheet.extend(_sheet_fields(shown))

    if changed:
        _create_exclusive(
            key_path, json.dumps(blind_key, indent=2, ensure_ascii=False) + "\n"
        )
    if legacy_used:
        view = [LEGACY_NOTE, "", *view]
    if sheet_exists:
        status: Literal["created", "preserved"] = "preserved"
        view.append("Existing blind_sheet.md preserved; not rewritten.")
    else:
        status = "created"
        _create_exclusive(sheet_path, "\n".join(sheet))
        view.append("Created blind_sheet.md.")
    return BlindReview(text="\n".join(view), sheet_status=status, problems=problems)
