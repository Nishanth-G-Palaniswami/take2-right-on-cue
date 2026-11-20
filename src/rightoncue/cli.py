"""next-turn command line interface."""

from __future__ import annotations

import argparse
import os
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from .runs import (
    BlindKeyError,
    InputFile,
    RunNotReadyError,
    create_run,
    new_run_id,
    render_blind,
    run_slots,
)
from .transcript import TranscriptError, parse_transcript

EFFORTS = ["none", "minimal", "low", "medium", "high", "xhigh", "max"]


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="next-turn")
    sub = parser.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run", help="generate N independent replies per case")
    run.add_argument("--prompt", required=True, type=Path)
    run.add_argument("--case", required=True, action="append", type=Path, dest="cases")
    run.add_argument("--model", default="gpt-5.4-mini")
    run.add_argument("--samples", type=int, default=2)
    run.add_argument("--reasoning-effort", default="none", choices=EFFORTS)
    run.add_argument("--runs-dir", type=Path, default=Path("runs"))

    show = sub.add_parser("show", help="print the blinded reply view for a run")
    show.add_argument("run_dir", type=Path)
    return parser


def _read_input(path: Path) -> InputFile:
    return InputFile(path=path.as_posix(), raw=path.read_bytes())


def _cmd_run(
    args: argparse.Namespace, client_factory: Callable[[], Any] | None = None
) -> int:
    errors: list[str] = []
    if not 1 <= args.samples <= 5:
        errors.append("--samples: must be between 1 and 5")

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

    if client_factory is not None:
        client = client_factory()
    else:
        load_dotenv(override=False)
        if not os.environ.get("OPENAI_API_KEY"):
            print(
                "OPENAI_API_KEY is not set. Put it in a .env file in the current "
                "directory (OPENAI_API_KEY=...). No request was made.",
                file=sys.stderr,
            )
            return 2

        from openai import OpenAI

        client = OpenAI()
    run_id = new_run_id()
    run_dir, manifest = create_run(
        args.runs_dir,
        run_id,
        prompt,
        cases,
        args.model,
        args.reasoning_effort,
        args.samples,
        client.max_retries,
        str(client.timeout),
    )
    print(f"run_id: {run_id}")

    def progress(rec: dict) -> None:
        usage = rec["usage"] or {}
        reasoning = (usage.get("output_tokens_details") or {}).get("reasoning_tokens")
        extra = ""
        if rec["status"] == "incomplete":
            reason = (rec["incomplete_details"] or {}).get("reason")
            extra = f" (reason: {reason})" if reason else " (reason unknown)"
        print(
            f"  {rec['case_id']} sample {rec['sample_index']}: {rec['status']}{extra} "
            f"in={usage.get('input_tokens')} out={usage.get('output_tokens')} "
            f"reasoning={reasoning}"
        )

    result = run_slots(client, run_dir, manifest, on_slot=progress)
    total = len(cases) * args.samples
    completed = result.attempted - result.incomplete - result.failed
    print(
        f"Summary: {result.attempted} of {total} slots attempted: {completed} "
        f"completed, {result.incomplete} incomplete, {result.failed} failed"
    )
    if result.empty:
        print(
            f"Note: {result.empty} completed "
            f"{'reply' if result.empty == 1 else 'replies'} had no text."
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
    client_factory: Callable[[], Any] | None = None,
) -> int:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    sys.stderr.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    args = _build_parser().parse_args(argv)
    return _cmd_run(args, client_factory) if args.command == "run" else _cmd_show(args)


if __name__ == "__main__":
    sys.exit(main())
