"""next-turn command line interface."""

from __future__ import annotations

import argparse
import os
import sys
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from . import gemini, openai_responses
from .runs import (
    MAX_REPLIES_PER_CASE,
    PROVIDERS,
    BlindKeyError,
    ManifestError,
    InputFile,
    ModelSpec,
    RunNotReadyError,
    create_run,
    new_run_id,
    provider_for,
    render_blind,
    run_slots,
)
from .transcript import TranscriptError, parse_transcript

EFFORTS = ["none", "minimal", "low", "medium", "high", "xhigh", "max"]
DEFAULT_MODELS = ["gpt-5.4-mini"]


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="next-turn")
    sub = parser.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run", help="generate N independent replies per case")
    run.add_argument("--prompt", required=True, type=Path)
    run.add_argument("--case", required=True, action="append", type=Path, dest="cases")
    # default=None, not a list: argparse's append would add to a default list.
    run.add_argument(
        "--model",
        action="append",
        dest="models",
        default=None,
        help="repeat for several models (gpt-... or gemini-...); "
        f"default {DEFAULT_MODELS[0]}",
    )
    run.add_argument("--samples", type=int, default=2)
    run.add_argument(
        "--reasoning-effort",
        default="none",
        choices=EFFORTS,
        help="OpenAI models only",
    )
    run.add_argument(
        "--gemini-thinking-level",
        type=str.upper,
        choices=gemini.THINKING_LEVELS,
        default=None,
        help="required when any Gemini model is selected; no default",
    )
    run.add_argument("--runs-dir", type=Path, default=Path("runs"))

    show = sub.add_parser("show", help="print the blinded reply view for a run")
    show.add_argument("run_dir", type=Path)
    return parser


def _read_input(path: Path) -> InputFile:
    return InputFile(path=path.as_posix(), raw=path.read_bytes())


def _plural(n: int, one: str, many: str) -> str:
    return one if n == 1 else many


def _token_total(records: list[dict[str, Any]], field: str) -> str:
    values = [
        r["usage_normalized"][field]
        for r in records
        if r["usage_normalized"] is not None
        and isinstance(r["usage_normalized"][field], int)
    ]
    return str(sum(values)) if values else "n/a"


def _print_model_summary(spec: ModelSpec, records: list[dict[str, Any]], total: int) -> None:
    attempted = len(records)
    failed = sum(1 for r in records if r["status"] == "generation_failed")
    incomplete = sum(1 for r in records if r["status"] == "incomplete")
    completed = attempted - failed - incomplete
    empty = sum(
        1 for r in records if r["status"] == "ok" and not (r["output_text"] or "").strip()
    )
    answered = [r for r in records if r["raw_response"] is not None]
    reported: list[str] = sorted(
        {r["returned_model"] for r in answered if r["returned_model"] is not None}
    )
    if any(r["returned_model"] is None for r in answered):
        reported.append("served version unconfirmed")
    with_usage = sum(1 for r in records if r["usage_normalized"] is not None)
    print(f"Model {spec.model} ({spec.provider}):")
    print(f"  Requested model: {spec.model}")
    print(
        "  Reported model: "
        + (", ".join(reported) if reported else "none (no response received)")
    )
    print(
        f"  Summary: {attempted} of {total} slots attempted: {completed} "
        f"completed, {incomplete} incomplete, {failed} failed"
    )
    if empty:
        print(
            f"  Note: {empty} completed {_plural(empty, 'reply', 'replies')} "
            "had no text."
        )
    print(
        f"  Tokens: input={_token_total(records, 'input_tokens')} "
        f"output={_token_total(records, 'output_tokens')} "
        f"reasoning={_token_total(records, 'reasoning_tokens')} "
        f"({with_usage} {_plural(with_usage, 'reply', 'replies')} with usage)"
    )


def _cmd_run(
    args: argparse.Namespace,
    client_factories: Mapping[str, Callable[[], Any]] | None = None,
) -> int:
    errors: list[str] = []
    if not 1 <= args.samples <= 5:
        errors.append("--samples: must be between 1 and 5")

    selected: list[tuple[str, str]] = []  # (model, provider) in CLI order
    for model in args.models or DEFAULT_MODELS:
        try:
            provider = provider_for(model)
        except ValueError as exc:
            errors.append(f"--model: {exc}")
            continue
        if any(model == m for m, _ in selected):
            errors.append(f"--model: duplicate model {model!r}")
            continue
        selected.append((model, provider))
    providers = list(dict.fromkeys(p for _, p in selected))
    replies_per_case = len(selected) * args.samples
    if selected and replies_per_case > MAX_REPLIES_PER_CASE:
        errors.append(
            f"--model/--samples: {len(selected)} models x {args.samples} samples = "
            f"{replies_per_case} replies per case; the blind review has letters for "
            f"at most {MAX_REPLIES_PER_CASE} (A-Z)"
        )
    if gemini.PROVIDER in providers and args.gemini_thinking_level is None:
        errors.append(
            "--gemini-thinking-level: required when a Gemini model is selected "
            f"(one of {', '.join(gemini.THINKING_LEVELS)}); there is no default."
        )
    if gemini.PROVIDER not in providers and args.gemini_thinking_level is not None:
        errors.append(
            "--gemini-thinking-level: only applies to Gemini models, and none is "
            "selected."
        )

    prompt: InputFile | None = None
    try:
        prompt = _read_input(args.prompt)
        if not prompt.text.strip():
            errors.append(f"{prompt.path}:1: prompt file is empty")
    except (OSError, UnicodeDecodeError) as exc:
        errors.append(f"{args.prompt.as_posix()}:1: cannot read prompt ({exc})")

    cases: list[InputFile] = []
    seen: set[str] = set()
    for path in args.cases:
        try:
            case = _read_input(path)
            parse_transcript(case.text)
        except TranscriptError as exc:
            errors.append(f"{path.as_posix()}:{exc.line}: {exc.reason}")
            continue
        except (OSError, UnicodeDecodeError) as exc:
            errors.append(f"{path.as_posix()}:1: cannot read case ({exc})")
            continue
        if case.stem in seen:
            errors.append(f"{path.as_posix()}:1: duplicate case id {case.stem!r}")
            continue
        seen.add(case.stem)
        cases.append(case)
    if errors or prompt is None:
        for line in errors:
            print(line, file=sys.stderr)
        return 2

    clients: dict[str, Any] = {}
    if client_factories is not None:
        missing = [p for p in providers if p not in client_factories]
        if missing:
            raise ValueError(f"no client factory for provider(s): {', '.join(missing)}")
        clients = {p: client_factories[p]() for p in providers}
    else:
        load_dotenv(override=False)
        unset = [
            PROVIDERS[p].API_KEY_ENV
            for p in providers
            if not os.environ.get(PROVIDERS[p].API_KEY_ENV)
        ]
        if unset:
            for env in unset:
                print(
                    f"{env} is not set. Put it in a .env file in the current "
                    f"directory ({env}=...).",
                    file=sys.stderr,
                )
            print("No request was made.", file=sys.stderr)
            return 2
        if openai_responses.PROVIDER in providers:
            from openai import OpenAI

            clients[openai_responses.PROVIDER] = OpenAI()
        if gemini.PROVIDER in providers:
            clients[gemini.PROVIDER] = gemini.make_client(
                os.environ[gemini.API_KEY_ENV]
            )

    specs: list[ModelSpec] = []
    for model, provider in selected:
        if provider == openai_responses.PROVIDER:
            settings: dict[str, Any] = {"reasoning_effort": args.reasoning_effort}
            client_info = openai_responses.client_settings(clients[provider])
        else:
            settings = {"thinking_level": args.gemini_thinking_level}
            client_info = gemini.client_settings()
        specs.append(ModelSpec(model, provider, settings, client_info))

    run_id = new_run_id()
    run_dir, manifest = create_run(
        args.runs_dir, run_id, prompt, cases, specs, args.samples
    )
    print(f"run_id: {run_id}")

    def progress(rec: dict[str, Any]) -> None:
        usage = rec["usage_normalized"] or {}
        extra = ""
        if rec["status"] == "incomplete":
            reason = (rec["incomplete_details"] or {}).get("reason")
            extra = f" (reason: {reason})" if reason else " (reason unknown)"
        print(
            f"  {rec['case_id']} {rec['requested_model']} sample "
            f"{rec['sample_index']}: {rec['status']}{extra} "
            f"in={usage.get('input_tokens')} out={usage.get('output_tokens')} "
            f"reasoning={usage.get('reasoning_tokens')}"
        )

    result = run_slots(clients, run_dir, manifest, on_slot=progress)
    total = len(cases) * args.samples
    for spec in specs:
        _print_model_summary(
            spec,
            [r for r in result.records if r["requested_model"] == spec.model],
            total,
        )
    print(f"run directory: {run_dir}")
    if result.abort_message:
        print(result.abort_message, file=sys.stderr)
    bad = result.failed or result.incomplete or result.abort_message
    return 1 if bad else 0


def _cmd_show(args: argparse.Namespace) -> int:
    if not (args.run_dir / "manifest.json").exists():
        print(f"{args.run_dir}: no manifest.json; not a run directory", file=sys.stderr)
        return 2
    try:
        review = render_blind(args.run_dir)
    except RunNotReadyError as exc:
        for line in exc.lines:
            print(line, file=sys.stderr)
        print("Nothing was written.", file=sys.stderr)
        return 2
    except BlindKeyError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    except ManifestError as exc:
        print(f"{exc} Nothing was written.", file=sys.stderr)
        return 2
    print(review.text)
    if review.problems:
        print("\nProblems found:", file=sys.stderr)
        for problem in review.problems:
            print(f"  - {problem}", file=sys.stderr)
        return 1
    return 0


def main(
    argv: list[str] | None = None,
    *,
    client_factories: Mapping[str, Callable[[], Any]] | None = None,
) -> int:
    """Entry point. Tests inject `client_factories` (provider -> factory); then no
    .env is read, no key is checked and no real client is built."""
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    sys.stderr.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    args = _build_parser().parse_args(argv)
    if args.command == "run":
        return _cmd_run(args, client_factories)
    return _cmd_show(args)


if __name__ == "__main__":
    sys.exit(main())
