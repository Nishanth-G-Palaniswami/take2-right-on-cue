"""next-turn command line interface."""

from __future__ import annotations

import argparse
import os
import sys
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from . import budget as budget_guard
from . import gemini, holdout, openai_responses, scoring
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

    score = sub.add_parser(
        "score", help="score a run's saved replies (code checks, judge, decision)"
    )
    score.add_argument("run_dir", type=Path)
    score.add_argument("--scores-dir", type=Path, default=Path("scores"))
    score.add_argument("--notes", type=Path, default=Path("cases/notes.toml"))
    score.add_argument(
        "--judge-version",
        choices=list(scoring.JUDGE_PROMPTS),
        default=scoring.DEFAULT_JUDGE_VERSION,
        help=f"judge prompt version (default {scoring.DEFAULT_JUDGE_VERSION})",
    )
    score.add_argument(
        "--budget-usd",
        default=None,
        help="stop before any judge call that could take the recorded spend of the "
        "--budget-run runs over this many USD (needs --budget-run)",
    )
    score.add_argument(
        "--budget-run",
        action="append",
        type=Path,
        dest="budget_runs",
        default=None,
        help="a run whose recorded spend counts toward --budget-usd; repeat, and "
        "include the run being scored",
    )

    plan = sub.add_parser(
        "pair-plan", help="fix the holdout pair mapping and write its salted commitment"
    )
    plan.add_argument("--case", required=True, action="append", dest="cases")
    plan.add_argument("--model", required=True, action="append", dest="models")
    plan.add_argument("--prompt-version", required=True)
    plan.add_argument("--private-out", required=True, type=Path)
    plan.add_argument("--commitment-out", required=True, type=Path)

    verify = sub.add_parser(
        "verify-commitment", help="check a private plan or review key against its commitment"
    )
    verify.add_argument("--private", required=True, type=Path)
    verify.add_argument("--commitment", required=True, type=Path)

    review = sub.add_parser(
        "review-sheet", help="write the combined blind accept/reject sheet for two runs"
    )
    review.add_argument("--run", required=True, action="append", type=Path, dest="runs")
    review.add_argument("--out", required=True, type=Path)
    review.add_argument("--private-key", required=True, type=Path)

    psheet = sub.add_parser("pair-sheet", help="write the blind A/B/tie pair sheet")
    psheet.add_argument("--plan-private", required=True, type=Path)
    psheet.add_argument("--commitment", required=True, type=Path)
    psheet.add_argument("--run", required=True, type=Path)
    psheet.add_argument("--out", required=True, type=Path)
    psheet.add_argument("--review-sheet", required=True, type=Path)
    psheet.add_argument("--review-commitment", required=True, type=Path)

    judge_choices = list(scoring.JUDGE_PROMPTS)
    pcomp = sub.add_parser(
        "pair-compare", help="after reveal: human A/B/tie against the judge's raw verdicts"
    )
    pcomp.add_argument("--plan", required=True, type=Path)
    pcomp.add_argument("--commitment", required=True, type=Path)
    pcomp.add_argument("--run", required=True, type=Path)
    pcomp.add_argument("--pair-sheet", required=True, type=Path)
    pcomp.add_argument("--scores-dir", type=Path, default=Path("scores"))
    pcomp.add_argument(
        "--judge-version", choices=judge_choices, default=scoring.DEFAULT_JUDGE_VERSION
    )
    pcomp.add_argument("--json-out", type=Path, default=None)

    rcomp = sub.add_parser(
        "review-compare", help="after reveal: human accept/reject against the judge"
    )
    rcomp.add_argument("--key", required=True, type=Path)
    rcomp.add_argument("--commitment", required=True, type=Path)
    rcomp.add_argument("--sheet", required=True, type=Path)
    rcomp.add_argument("--scores-dir", type=Path, default=Path("scores"))
    rcomp.add_argument(
        "--judge-version", choices=judge_choices, default=scoring.DEFAULT_JUDGE_VERSION
    )
    rcomp.add_argument("--json-out", type=Path, default=None)
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


_DECISION_LABEL = {
    "needs_review": "NEEDS REVIEW",
    "judge_failed": "JUDGE FAILED",
    "budget_stopped": "BUDGET STOPPED (not judged)",
}
_UNSCORED_NOTE = {
    "incomplete": "reply was incomplete; not scored",
    "generation_failed": "reply failed to generate; not scored",
    "missing": "no saved record for this slot; not scored",
    "duplicate": "more than one saved record for this slot; not scored",
    "stopped": "not scored: scoring stopped after a fatal judge error",
}


def _reported(sp: scoring.SlotPlan) -> str:
    if sp.returned_model:
        return sp.returned_model
    if sp.state == "missing":
        return "none (no saved record)"
    if sp.state == "duplicate":
        return "not determined (duplicate records)"
    return "served version unconfirmed" if sp.responded else "none (no response received)"


def _print_score_outcome(outcome: scoring.Outcome, last_case: list[str]) -> None:
    sp = outcome.slot
    if not last_case or last_case[0] != sp.case_id:
        print(f"\n=== CASE {sp.case_id} ===")
        last_case[:] = [sp.case_id]
    head = (
        f"\n{sp.case_id} | requested {sp.requested_model} / reported "
        f"{_reported(sp)} | sample {sp.sample_index}"
    )
    rec = outcome.record
    if rec is None:
        print(f"{head}\n  {_UNSCORED_NOTE[outcome.kind]}")
        return
    print(head)
    print(f"  Reply: \"{sp.text}\"")
    decision = rec["decision"]
    if rec["status"] == "scored":
        label = "ACCEPTABLE" if decision["acceptable"] else "NOT ACCEPTABLE"
    else:
        label = _DECISION_LABEL[rec["status"]]
    print(f"  Decision: {label}")
    print("  Reasons:")
    for reason in decision["reasons"]:
        print(f"    - {reason}")
    scores = decision["scores"]
    if scores is None:
        print("  Scores: not judged")
    else:
        parts = " · ".join(
            f"{scoring.DIMENSION_LABELS[d]} {scores[d]}" for d in scoring.DIMENSIONS
        )
        print(f"  Scores: {parts} · total {decision['total']}/8")
    judgment = rec["judgment"]
    if judgment is not None:
        print("  Judge:")
        for d in scoring.DIMENSIONS:
            dim = judgment[d]
            print(f"    {scoring.DIMENSION_LABELS[d]} ({dim['score']}): {dim['rationale']}")
            for ev in dim["evidence"]:
                print(f"      evidence ({ev['source']}): \"{ev['quote']}\"")
        scorer_version = rec["scorer_version"]
        if scorer_version == "scorer-1":
            violations = judgment["critical_violations"]
        elif scorer_version == "scorer-2":  # one entry per type; only present ones count
            violations = [
                {"type": name, **entry}
                for name, entry in judgment["critical_violations"].items()
                if entry["present"]
            ]
        else:
            raise ValueError(f"unknown scorer version {scorer_version!r} in a score record")
        if not violations:
            print("    critical violations: none")
        for cv in violations:
            print(f"    critical violation {cv['type']}: {cv['rationale']}")
            for ev in cv["evidence"]:
                print(f"      evidence ({ev['source']}): \"{ev['quote']}\"")
    if rec["status"] == "needs_review" and rec["judge_output_text"] is not None:
        print(f"  Judge output (verbatim): {rec['judge_output_text']}")
    st = rec["structural"]
    diag = st["diagnostics"]
    single = "pass" if st["single_turn_pass"] else f"FAIL ({'; '.join(st['failures'])})"
    print(
        f"  checks: single-turn: {single}; words {diag['word_count']}; question "
        f"marks {diag['question_marks']}; flags: {', '.join(diag['flags']) or 'none'}"
    )
    print(f"  criteria: {rec['criteria_source']}")
    print(f"  score: {outcome.source}")


def _print_score_summary(
    plan: scoring.ScoringPlan, result: scoring.ScoringResult
) -> None:
    print("\nSummary")
    for model in plan.models:
        outs = [o for o in result.outcomes if o.slot.requested_model == model]
        kinds = [o.kind for o in outs]
        states = [o.slot.state for o in outs]
        present = [o.slot for o in outs if o.slot.state not in ("missing", "duplicate")]
        reported = sorted({s.returned_model for s in present if s.returned_model})
        if any(s.responded and not s.returned_model for s in present):
            reported.append("served version unconfirmed")
        acceptable = sum(
            1 for o in outs if o.kind == "scored" and o.record["decision"]["acceptable"]  # type: ignore[index]
        )
        print(f"Model {model}:")
        print(f"  Requested model: {model}")
        print(
            f"  Reported model: {', '.join(reported) if reported else 'none (no response received)'}"
        )
        ok = states.count("ok") + states.count("empty")
        print(
            f"  Slots: {len(outs)} expected, {ok} ok {_plural(ok, 'reply', 'replies')} "
            f"({states.count('empty')} empty), {states.count('incomplete')} incomplete, "
            f"{states.count('generation_failed')} generation failed, "
            f"{states.count('missing')} missing"
            + (f", {states.count('duplicate')} duplicate" if "duplicate" in states else "")
        )
        print(
            f"  Scores: {acceptable} acceptable, {kinds.count('scored') - acceptable} "
            f"not acceptable, {kinds.count('needs_review')} needs review, "
            f"{kinds.count('judge_failed')} judge failed"
            + (f", {kinds.count('stopped')} not scored (stopped)" if "stopped" in kinds else "")
            + (
                f", {kinds.count('budget_stopped')} unscored (budget)"
                if "budget_stopped" in kinds
                else ""
            )
        )
    tokens = (
        f"input tokens {result.input_tokens}, output tokens {result.output_tokens}"
        if result.calls_with_usage
        else "no usage reported"
    )
    print(_judge_line(plan.judge))
    print(f"Judge calls this run: {result.calls} ({tokens})")
    print(f"Scores file: {plan.score_path.as_posix()}")


def _judge_line(judge: scoring.JudgePrompt) -> str:
    return (
        f"Judge: {judge.version} ({judge.path.as_posix()}, sha256 {judge.sha256[:12]}), "
        f"model {scoring.JUDGE_MODEL}"
    )


def _cmd_score(
    args: argparse.Namespace,
    client_factories: Mapping[str, Callable[[], Any]] | None = None,
) -> int:
    if not (args.run_dir / "manifest.json").exists():
        print(f"{args.run_dir}: no manifest.json; not a run directory", file=sys.stderr)
        return 2
    try:
        judge = scoring.load_judge_prompt(args.judge_version)
        plan = scoring.plan_scoring(args.run_dir, args.scores_dir, args.notes, judge)
    except (scoring.ScoringInputError, ManifestError) as exc:
        print(str(exc), file=sys.stderr)
        print("No judge call was made.", file=sys.stderr)
        return 2

    guard: budget_guard.Budget | None = None
    spend: budget_guard.Spend | None = None
    if args.budget_usd is not None or args.budget_runs is not None:
        try:
            guard, spend = _budget_setup(args, plan)
        except budget_guard.BudgetInputError as exc:
            print(str(exc), file=sys.stderr)
            print("No judge call was made.", file=sys.stderr)
            return 2

    reuse = plan.count(action="reuse")
    empty = plan.count(state="empty")
    duplicates = plan.count(state="duplicate")
    print(f"run_id: {plan.run_id}")
    print(
        f"Plan: {plan.eligible} eligible {_plural(plan.eligible, 'reply', 'replies')} "
        f"(status ok): {reuse} reuse a valid score, {plan.calls_needed} need a judge "
        f"call; {empty} of them empty (no judge call, fails the single-turn check). "
        f"Not scored: {plan.count(state='incomplete')} incomplete, "
        f"{plan.count(state='generation_failed')} generation failed, "
        f"{plan.count(state='missing')} missing"
        + (f", {duplicates} duplicate" if duplicates else "")
        + "."
    )
    print(_judge_line(plan.judge))
    if plan.interrupted_attempts:
        n = plan.interrupted_attempts
        print(
            f"Interrupted attempts: {n} ({_plural(n, 'a budgeted judge call was', 'budgeted judge calls were')} "
            "started but never recorded; each counts its maximum cost and its reply "
            "is judged again)"
        )
    if guard is not None and spend is not None:
        _print_budget_start(guard, spend)
    problems: list[str] = []
    if duplicates:
        problems.append(
            f"{duplicates} reply {_plural(duplicates, 'slot has', 'slots have')} more "
            "than one saved record and "
            f"{_plural(duplicates, 'was', 'were')} not scored."
        )
    if plan.unknown_records:
        n = plan.unknown_records
        problems.append(
            f"{n} saved {_plural(n, 'record matches', 'records match')} no expected "
            f"reply slot and {_plural(n, 'was', 'were')} ignored."
        )

    client: Any | None = None
    if plan.calls_needed:
        if client_factories is not None:
            if openai_responses.PROVIDER not in client_factories:
                raise ValueError("no client factory for provider: openai")
            factory = client_factories[openai_responses.PROVIDER]
            # Under a budget the SDK must not retry on its own: every billable request
            # has to pass the guard. The guarded rerun of `score` is the retry.
            client = factory(max_retries=0) if guard is not None else factory()
        else:
            load_dotenv(override=False)
            env = openai_responses.API_KEY_ENV
            if not os.environ.get(env):
                print(
                    f"{env} is not set. Put it in a .env file in the current "
                    f"directory ({env}=...).",
                    file=sys.stderr,
                )
                print("No request was made.", file=sys.stderr)
                return 2
            from openai import OpenAI

            client = OpenAI(max_retries=0) if guard is not None else OpenAI()
        if guard is not None and getattr(client, "max_retries", 0) != 0:
            print(
                "The judge client would retry on its own, which the budget guard can't "
                "see; no judge call was made.",
                file=sys.stderr,
            )
            return 2

    last_case: list[str] = []
    result = scoring.execute_plan(
        plan, client, on_outcome=lambda o: _print_score_outcome(o, last_case), budget=guard
    )
    _print_score_summary(plan, result)
    if guard is not None:
        stopped = sum(1 for o in result.outcomes if o.kind == "budget_stopped")
        print(
            f"Budget: {budget_guard.fmt_usd(guard.spent_this_command)} recorded this command "
            "(actual usage, or a call's maximum where usage is missing); spend now "
            f"{budget_guard.fmt_usd(guard.spent)} of {budget_guard.fmt_usd(guard.limit)}; "
            f"{stopped} {_plural(stopped, 'reply', 'replies')} unscored (budget)."
        )
    if problems:
        print("\nProblems found:", file=sys.stderr)
        for problem in problems:
            print(f"  - {problem}", file=sys.stderr)
    if result.fatal_message:
        print(result.fatal_message, file=sys.stderr)
    bad = (
        duplicates
        or plan.unknown_records
        or result.fatal_message
        or any(o.kind in ("needs_review", "judge_failed", "budget_stopped") for o in result.outcomes)
    )
    return 1 if bad else 0


def _budget_setup(
    args: argparse.Namespace, plan: scoring.ScoringPlan
) -> tuple[budget_guard.Budget, budget_guard.Spend]:
    """The guard for this command; raises BudgetInputError before any call."""
    if args.budget_usd is None:
        raise budget_guard.BudgetInputError("--budget-run: only applies with --budget-usd")
    limit = budget_guard.parse_usd(args.budget_usd)
    runs = args.budget_runs or []
    if not runs:
        raise budget_guard.BudgetInputError(
            "--budget-usd: needs --budget-run for every run whose spend counts, "
            "including the run being scored"
        )
    resolved = [r.resolve() for r in runs]
    if len(set(resolved)) != len(resolved):
        raise budget_guard.BudgetInputError("--budget-run: the same run is listed more than once")
    if args.run_dir.resolve() not in resolved:
        raise budget_guard.BudgetInputError(
            f"--budget-run: must include the run being scored ({args.run_dir.as_posix()})"
        )
    for r in runs:
        if not (r / "manifest.json").exists():
            raise budget_guard.BudgetInputError(
                f"--budget-run: {r.as_posix()} has no manifest.json; not a run directory"
            )
    try:
        ids = [scoring.load_manifest(r).get("run_id") for r in runs]
    except (OSError, ValueError) as exc:
        raise budget_guard.BudgetInputError(f"--budget-run: cannot read a manifest ({exc})") from None
    if len(set(ids)) != len(ids):
        raise budget_guard.BudgetInputError("--budget-run: two runs have the same run_id")
    for sp in plan.slots:  # every needed call must have a cost bound before any call
        if sp.action == "judge":
            budget_guard.max_call_cost(sp.request)  # type: ignore[arg-type]
    spend = budget_guard.spend_so_far(runs, args.scores_dir)
    return budget_guard.Budget(limit=limit, spent=spend.total), spend


def _print_budget_start(guard: budget_guard.Budget, spend: budget_guard.Spend) -> None:
    fmt = budget_guard.fmt_usd
    print(
        f"Budget: {fmt(guard.limit)}; spend so far {fmt(spend.total)} (generation "
        f"{fmt(spend.generation)}, judge {fmt(spend.judge)}) from recorded usage. "
        f"{budget_guard.GEMINI_NOTE}"
    )
    if spend.no_response:
        parts = ", ".join(f"{run} {n}" for run, n in sorted(spend.no_response.items()))
        print(
            f"Budget: calls that raised and returned no response are counted at $0 "
            f"(no usage was recorded): {parts}."
        )


# ---------------------------------------------------------------- holdout
# Before reveal these commands print only paths, counts and commitment hashes:
# never a salt, a pair mapping or a neutral-ID-to-run/model mapping.


def _holdout_error(exc: holdout.HoldoutInputError) -> int:
    print(str(exc), file=sys.stderr)
    return 2


def _cmd_pair_plan(args: argparse.Namespace) -> int:
    try:
        digest = holdout.create_pair_plan(
            args.cases, args.models, args.prompt_version, args.private_out, args.commitment_out
        )
    except holdout.HoldoutInputError as exc:
        return _holdout_error(exc)
    print(f"private pair plan: {args.private_out.as_posix()} (do not open before labels are committed)")
    print(f"commitment: {args.commitment_out.as_posix()}")
    print(f"commitment sha256: {digest}")
    return 0


def _cmd_verify_commitment(args: argparse.Namespace) -> int:
    try:
        kind, digest = holdout.verify_any(args.private, args.commitment)
    except (holdout.HoldoutInputError, holdout.CommitmentError) as exc:
        print(f"commitment NOT verified: {exc}", file=sys.stderr)
        return 1
    print(f"commitment verified ({kind}, sha256 {digest})")
    return 0


def _cmd_review_sheet(args: argparse.Namespace) -> int:
    try:
        res = holdout.create_review_sheet(args.runs, args.out, args.private_key)
    except holdout.HoldoutInputError as exc:
        return _holdout_error(exc)
    print(f"review sheet: {res.sheet.as_posix()}")
    print(f"private review key: {res.private_key.as_posix()} (do not open before labels are committed)")
    print(f"commitment: {res.commitment.as_posix()}")
    print(f"replies shown: {res.n_replies} across {res.n_cases} {_plural(res.n_cases, 'case', 'cases')}")
    not_shown = sum(res.unavailable.values())
    print(
        f"replies not shown (operational failures): {not_shown}"
        + (" (" + ", ".join(f"{k} {v}" for k, v in res.unavailable.items()) + ")" if not_shown else "")
    )
    print(f"commitment sha256: {res.sha256}")
    return 0


def _cmd_pair_sheet(args: argparse.Namespace) -> int:
    try:
        res = holdout.create_pair_sheet(
            args.plan_private, args.commitment, args.run, args.out,
            args.review_sheet, args.review_commitment,
        )
    except holdout.HoldoutInputError as exc:
        return _holdout_error(exc)
    print(f"review labels checked: {res.n_labels_checked}, all y or n")
    print(f"pair sheet: {res.sheet.as_posix()}")
    print(f"pairs shown: {res.n_pairs} of {res.n_total}")
    if res.n_unavailable:
        print(f"{res.n_unavailable} of {res.n_total} pairs cannot be shown")
    return 0


def _cmd_pair_compare(args: argparse.Namespace) -> int:
    try:
        if args.json_out is not None:
            holdout.check_json_out(args.json_out, args.scores_dir)
        report = holdout.pair_compare(
            args.plan, args.commitment, args.run, args.pair_sheet,
            args.scores_dir, args.judge_version,
        )
        if args.json_out is not None:
            holdout.write_json_report(args.json_out, report, args.scores_dir)
    except holdout.HoldoutInputError as exc:
        return _holdout_error(exc)
    print(holdout.format_pair_report(report))
    if args.json_out is not None:
        print(f"JSON report: {args.json_out.as_posix()}")
    return 0


def _cmd_review_compare(args: argparse.Namespace) -> int:
    try:
        if args.json_out is not None:
            holdout.check_json_out(args.json_out, args.scores_dir)
        report = holdout.review_compare(
            args.key, args.commitment, args.sheet, args.scores_dir, args.judge_version
        )
        if args.json_out is not None:
            holdout.write_json_report(args.json_out, report, args.scores_dir)
    except holdout.HoldoutInputError as exc:
        return _holdout_error(exc)
    print(holdout.format_review_report(report))
    if args.json_out is not None:
        print(f"JSON report: {args.json_out.as_posix()}")
    return 0


_HOLDOUT_COMMANDS: dict[str, Callable[[argparse.Namespace], int]] = {
    "pair-plan": _cmd_pair_plan,
    "verify-commitment": _cmd_verify_commitment,
    "review-sheet": _cmd_review_sheet,
    "pair-sheet": _cmd_pair_sheet,
    "pair-compare": _cmd_pair_compare,
    "review-compare": _cmd_review_compare,
}


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
    if args.command == "score":
        return _cmd_score(args, client_factories)
    if args.command in _HOLDOUT_COMMANDS:
        return _HOLDOUT_COMMANDS[args.command](args)
    return _cmd_show(args)


if __name__ == "__main__":
    sys.exit(main())
