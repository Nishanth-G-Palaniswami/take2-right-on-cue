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
from typing import Any, Callable

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
                record.update(
                    status="ok" if response.status == "completed" else "incomplete",
                    output_text=response.output_text,
                    returned_model=response.model,
                    response_id=response.id,
                    response_status=response.status,
                    incomplete_details=dump.get("incomplete_details"),
                    usage=dump.get("usage"),
                    raw_response=dump,
                )
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

_SHEET_FIELDS = (
    "Preference (A / B / tie):",
    "Words that tipped it:",
    "One-sentence reason:",
    "Accept A? (y/n):",
    "Accept B? (y/n):",
)


def _label(i: int) -> str:
    return chr(ord("A") + i)


def render_blind(run_dir: Path) -> str:
    """Return the blind view text; also writes blind_key.json and blind_sheet.md."""
    manifest = load_manifest(run_dir)
    slots = {s["slot_key"]: s for s in read_slots(run_dir)}
    key_path = run_dir / "blind_key.json"
    blind_key: dict[str, dict[str, str]] = (
        json.loads(key_path.read_text(encoding="utf-8")) if key_path.exists() else {}
    )
    run_id = manifest["run_id"]
    version = manifest["prompt"]["version"]
    model = manifest["model"]
    n = manifest["samples_per_case"]
    changed = False
    view: list[str] = []
    sheet: list[str] = []
    for case in manifest["cases"]:
        cid = case["case_id"]
        usable_keys = []
        for i in range(1, n + 1):
            key = make_slot_key(run_id, cid, version, model, i)
            slot = slots.get(key)
            if slot is not None and slot["status"] != "generation_failed":
                usable_keys.append(key)
        failed = n - len(usable_keys)
        if cid not in blind_key:
            secrets.SystemRandom().shuffle(usable_keys)
            blind_key[cid] = {_label(i): k for i, k in enumerate(usable_keys)}
            changed = True
        lines = [
            f"=== CASE {cid} ===",
            "Applicant's last utterance:",
            case["turns"][-1]["utterance"],
            "",
        ]
        for label, key in blind_key[cid].items():
            reply = slots[key]["output_text"]
            lines += [
                f"<<<<<<<< REPLY {label} >>>>>>>>",
                reply if reply != "" else "(empty reply)",
                f"<<<<<<<< END REPLY {label} >>>>>>>>",
                "",
            ]
        if failed:
            lines += [f"{failed} of {n} samples failed to generate", ""]
        view.extend(lines)
        sheet.extend(lines)
        sheet.extend([*_SHEET_FIELDS, ""])
    if changed:
        _write_json(key_path, blind_key)
    (run_dir / "blind_sheet.md").write_text(
        "\n".join(sheet), encoding="utf-8", newline="\n"
    )
    return "\n".join(view)
