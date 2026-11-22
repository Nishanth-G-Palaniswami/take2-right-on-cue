"""Run directory storage: manifest, slots, resume, blind view."""

from __future__ import annotations

import hashlib
import json
import os
import platform
import re
import secrets
import subprocess
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable, Literal, Mapping

import google.genai
import openai

from . import gemini, openai_responses
from .transcript import Turn, parse_transcript

SCHEMA_VERSION = 2
PROVIDERS: dict[str, Any] = {
    openai_responses.PROVIDER: openai_responses,
    gemini.PROVIDER: gemini,
}


MAX_REPLIES_PER_CASE = 26  # blind letters A-Z
_MODEL_ID_REST = re.compile(r"[A-Za-z0-9._-]+")


def provider_for(model: str) -> str:
    """Provider from the model ID prefix; anything else is an input error.

    After the prefix the ID must be non-empty and use only letters, digits,
    '.', '-' and '_' (no whitespace).
    """
    for prefix, provider in (
        ("gpt-", openai_responses.PROVIDER),
        ("gemini-", gemini.PROVIDER),
    ):
        if model.startswith(prefix):
            if not _MODEL_ID_REST.fullmatch(model[len(prefix):]):
                raise ValueError(
                    f"invalid model ID {model!r}: after {prefix!r} it needs at least "
                    "one character, and only letters, digits, '.', '-' and '_' "
                    "are allowed (no spaces)"
                )
            return provider
    raise ValueError(
        f"unknown model {model!r}: model IDs must start with 'gpt-' (OpenAI) or "
        "'gemini-' (Gemini)"
    )


class ManifestError(ValueError):
    """manifest.json can't be read as a valid run (unsupported schema, duplicate model)."""


@dataclass
class ModelSpec:
    model: str
    provider: str
    settings: dict[str, Any]  # openai: reasoning_effort; gemini: thinking_level
    client: dict[str, Any]  # client configuration recorded in the manifest


def _build_request(spec: ModelSpec, prompt_text: str, turns: list[Turn]) -> dict[str, Any]:
    """One model's request; settings["max_output_tokens"], when present, caps it."""
    cap = spec.settings.get("max_output_tokens")
    if spec.provider == openai_responses.PROVIDER:
        return openai_responses.build_request(
            prompt_text, turns, spec.model, spec.settings["reasoning_effort"], cap
        )
    if spec.provider == gemini.PROVIDER:
        return gemini.build_request(
            prompt_text, turns, spec.model, spec.settings["thinking_level"], cap
        )
    raise ValueError(f"unknown provider {spec.provider!r}")


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
    models: list[ModelSpec],
    samples: int,
    max_output_tokens: int | None = None,
) -> tuple[Path, dict[str, Any]]:
    """Write manifest.json (schema 2, before any API call); return (run_dir, manifest).

    `max_output_tokens` (default None: requests and manifest exactly as before) caps
    every model's reply. It is recorded in each model's settings (and so in every
    slot record), in every request and in the generation parameters note.
    """
    if not models:
        raise ValueError("at least one model is required")
    if max_output_tokens is not None:
        if type(max_output_tokens) is not int or max_output_tokens <= 0:
            raise ValueError(
                f"max_output_tokens must be a positive integer, got {max_output_tokens!r}"
            )
        if any("max_output_tokens" in m.settings for m in models):
            raise ValueError("max_output_tokens is set both as a parameter and in a model's settings")
        models = [
            ModelSpec(m.model, m.provider, {**m.settings, "max_output_tokens": max_output_tokens}, m.client)
            for m in models
        ]
    names = [m.model for m in models]
    if len(set(names)) != len(names):
        raise ValueError(f"duplicate model in {names}")
    for m in models:
        if provider_for(m.model) != m.provider:
            raise ValueError(f"model {m.model!r} is not a {m.provider!r} model")
    if len(models) * samples > MAX_REPLIES_PER_CASE:
        raise ValueError(
            f"{len(models)} models x {samples} samples = {len(models) * samples} "
            f"replies per case; the blind review has letters for at most "
            f"{MAX_REPLIES_PER_CASE}"
        )
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
                "requests": {
                    m.model: _build_request(m, prompt.text, turns) for m in models
                },
            }
        )
    providers = list(dict.fromkeys(m.provider for m in models))
    manifest: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "run_id": run_id,
        "created_at": datetime.now(UTC).isoformat(),
        "git": _git_state(),
        "openai_sdk_version": openai.__version__,
        "google_genai_sdk_version": google.genai.__version__,
        "python_version": platform.python_version(),
        "prompt": {
            "path": prompt.path,
            "version": prompt.stem,
            "sha256": prompt.sha256,
            "text": prompt.text,
        },
        "cases": case_entries,
        "models": [
            {
                "model": m.model,
                "provider": m.provider,
                "settings": m.settings,
                "client": m.client,
            }
            for m in models
        ],
        "samples_per_case": samples,
        "generation_params_note": {
            p: PROVIDERS[p].PARAMS_NOTE if max_output_tokens is None else PROVIDERS[p].PARAMS_NOTE_CAPPED
            for p in providers
        },
    }
    _write_json(run_dir / "manifest.json", manifest)
    return run_dir, manifest


def manifest_models(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    """The run's models in generation order, for both manifest schemas.

    A legacy manifest (no schema_version) is one OpenAI model with a string
    `model`, a top-level `reasoning_effort` and one `request` per case.
    """
    version = manifest.get("schema_version")
    if version is None:
        return [
            {
                "model": manifest["model"],
                "provider": openai_responses.PROVIDER,
                "settings": {"reasoning_effort": manifest["reasoning_effort"]},
                "client": manifest["client"],
            }
        ]
    if version == SCHEMA_VERSION:
        models = list(manifest["models"])
        names = [m["model"] for m in models]
        if len(set(names)) != len(names):
            # No model name in the message: it can surface before blind review.
            raise ManifestError("manifest.json lists the same model more than once")
        return models
    raise ManifestError(f"manifest.json: unsupported schema_version {version!r}")


def case_request(
    manifest: dict[str, Any], case: dict[str, Any], model: str
) -> dict[str, Any]:
    if manifest.get("schema_version") is None:
        return case["request"]
    return case["requests"][model]


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
    clients: Mapping[str, Any],
    run_dir: Path,
    manifest: dict[str, Any],
    on_slot: Callable[[dict[str, Any]], None] | None = None,
) -> RunResult:
    """Generate every missing slot: case, then model (manifest order), then sample.

    `clients` maps a provider name ("openai", "gemini") to its SDK client.
    """
    run_id = manifest["run_id"]
    version = manifest["prompt"]["version"]
    models = manifest_models(manifest)
    missing = sorted({m["provider"] for m in models} - set(clients))
    if missing:
        raise ValueError(f"no client for provider(s): {', '.join(missing)}")
    done = {s["slot_key"] for s in read_slots(run_dir)}
    result = RunResult()
    for case in manifest["cases"]:
        for spec in models:
            model = spec["model"]
            provider = spec["provider"]
            adapter = PROVIDERS[provider]
            client = clients[provider]
            request = case_request(manifest, case, model)
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
                    "provider": provider,
                    "settings": spec["settings"],
                    "sample_index": idx,
                }
                started = datetime.now(UTC)
                t0 = time.monotonic()
                fatal = False
                try:
                    response, dump = adapter.generate(client, request)
                except Exception as exc:
                    kind = adapter.classify_error(exc)
                    if kind is None:
                        raise
                    fatal = kind == "fatal"
                    record.update(
                        status="generation_failed",
                        output_text=None,
                        returned_model=None,
                        reported_model_note=None,
                        response_id=None,
                        response_status=None,
                        incomplete_details=None,
                        usage=None,
                        usage_normalized=None,
                        raw_response=None,
                        error={
                            "type": type(exc).__name__,
                            "message": str(exc),
                            "status_code": adapter.error_status_code(exc),
                        },
                    )
                else:
                    record.update(adapter.slot_fields(response, dump))
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
                        "aborting all remaining slots of the run after a fatal "
                        f"error from {model}: {err['type']} (HTTP "
                        f"{err['status_code']}): {err['message']}. Check your API "
                        "key, model name and request settings."
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
    if not 0 <= i < MAX_REPLIES_PER_CASE:
        raise ValueError(f"no blind letter for reply index {i}")
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
    models = [m["model"] for m in manifest_models(manifest)]
    per_case = len(models) * manifest["samples_per_case"]
    if per_case > MAX_REPLIES_PER_CASE:
        raise BlindKeyError(
            f"This run has {per_case} replies per case, but the blind review has "
            f"letters for at most {MAX_REPLIES_PER_CASE} (A-Z). Nothing was written."
        )
    by_key: dict[str, list[dict[str, Any]]] = {}
    for r in records:
        by_key.setdefault(r["slot_key"], []).append(r)
    # Every model x sample for each case; letters are shuffled across all of them.
    expected: dict[str, list[str]] = {
        c["case_id"]: [
            make_slot_key(run_id, c["case_id"], version, model, i)
            for model in models
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
