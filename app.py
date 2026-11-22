"""Right on Cue: a reviewer-facing Streamlit app. Logic lives in rightoncue.review."""

from __future__ import annotations

import html
import math
import os
from typing import Any

import streamlit as st

from rightoncue import budget, dryrun, gemini, live, openai_responses, review, scoring
from rightoncue.transcript import parse_transcript

# The judge prompt paths are relative to the repository root.
os.chdir(review.REPO_ROOT)

st.set_page_config(page_title="Right on Cue", layout="wide", initial_sidebar_state="collapsed")

JUDGE = scoring.DEFAULT_JUDGE_VERSION
DEFAULT_SELECTION = {"case": "H3", "prompt": "v2", "sample": "1"}
MUTED = "#6b7280"
DRY_RUN_BANNER = "Dry run: no API calls or charges. Replies are placeholders and are not scored."
# Dry run, at the click and on the result. Keyed on cfg.dry_run (the flag that builds
# the offline fakes) and, on cards, on the record's own dry-run marker.
DRY_RUN_BUTTON = "Simulate run"
DRY_RUN_NO_CHARGE = "No API calls or charges"
SIMULATED_BADGE = "Simulated reply · Unscored"
# A reply whose first judgment and its one retry both came back invalid or failed.
NO_VALID_SCORE = "Needs review · no valid score"

# ------------------------------------------------------------------------- helpers


def para(text: str, *, size: str = "1rem", muted: bool = False, weight: int = 400) -> None:
    """Verbatim text, HTML-escaped, wrapping at any width (no markdown, no LaTeX)."""
    color = MUTED if muted else "inherit"
    st.html(
        f'<div style="white-space:pre-wrap;overflow-wrap:anywhere;line-height:1.55;'
        f'font-size:{size};font-weight:{weight};color:{color}">{html.escape(text)}</div>'
    )


def badge(color: str, text: str) -> str:
    return f":{color}-badge[{text.replace('[', '(').replace(']', ')')}]"


def select(label: str, name: str, options: list[str]) -> str:
    """A horizontal radio whose value lives in the URL query string."""
    wanted = st.query_params.get(name)
    default = DEFAULT_SELECTION[name]
    index = options.index(wanted) if wanted in options else (
        options.index(default) if default in options else 0
    )
    value = st.radio(label, options, index=index, horizontal=True, key=f"sel_{name}")
    if st.query_params.get(name) != value:
        st.query_params[name] = value
    return value


_VERDICT_COLOR = {
    "acceptable": "green",
    "not acceptable": "red",
    "needs review": "orange",
    "judge failed": "orange",
    "unscored": "gray",
}
_FAILURE_TITLE = {
    "generation_failed": "Generation failed (operational failure)",
    "incomplete": "Incomplete (operational failure)",
    "missing": "Missing (operational failure)",
    "duplicate": "Duplicate records (operational failure)",
}


def render_card(card: review.Card) -> None:
    with st.container(border=True):
        para(card.model, size="1.05rem", weight=600)
        if card.reported_model:
            para(f"reported: {card.reported_model}", size="0.78rem", muted=True)
        elif card.state == "reply":
            para("reported: served version unconfirmed", size="0.78rem", muted=True)
        if card.operational_failure:
            st.error(_FAILURE_TITLE[card.state])
            para(card.note, size="0.85rem", muted=True)
            return
        para(card.reply if card.reply and card.reply.strip() else "(empty reply)")
        if card.reported_model == dryrun.DRY_MODEL:  # a placeholder judgment is not a judgment
            st.markdown(badge("gray", SIMULATED_BADGE))
            return
        total = f" · {card.total}/8" if card.total is not None else ""
        decision = card.decision or "unscored"
        if decision in ("needs review", "judge failed") and card.failed_judge_attempts >= live.JUDGE_ATTEMPTS:
            st.markdown(badge(_VERDICT_COLOR["needs review"], NO_VALID_SCORE))
        else:
            st.markdown(badge(_VERDICT_COLOR[decision], f"{JUDGE}: {decision}{total}"))
        if card.human_accept is not None:
            st.markdown(
                badge(
                    "green" if card.human_accept else "red",
                    f"Human label: {'accepted' if card.human_accept else 'rejected'}",
                )
            )
            if decision in ("acceptable", "not acceptable") and (
                (decision == "acceptable") != card.human_accept
            ):
                para("The judge and the human reviewer disagree on this reply.", size="0.82rem", muted=True)
        if card.violations:
            kinds = ", ".join(v.type for v in card.violations)
            if card.critical_findings:
                st.info(
                    f"The judge listed a critical flag ({kinds}). The human reviewer checked it and "
                    "found it absent. The raw verdict stands."
                )
            else:
                st.info(
                    f"The judge listed a critical flag ({kinds}). judge-v1 can list a flag "
                    "whose own rationale denies it; read the details."
                )
        with st.expander("Scores, checks and reasoning"):
            render_details(card)


def render_details(card: review.Card) -> None:
    if card.scores:
        parts = " · ".join(
            f"{scoring.DIMENSION_LABELS[d]} {card.scores[d]}" for d in scoring.DIMENSIONS
        )
        para(f"{parts} · total {card.total}/8", weight=600)
    else:
        para("Not scored by the judge.", muted=True)
    if card.single_turn_pass is not None:
        if card.single_turn_pass:
            para("Single-turn check: pass")
        else:
            para("Single-turn check: FAIL. " + "; ".join(card.single_turn_failures))
        para("Diagnostic flags: " + (", ".join(card.flags) or "none"))
    if card.reasons:
        if card.decision == "not acceptable":  # a valid rejection only
            heading = "Why it was not acceptable"
        elif card.decision in ("needs review", "judge failed"):
            heading = "Why this judgment needs review"
        else:  # unscored: no judge call was made (e.g. the budget stopped scoring)
            heading = "Why it was not scored"
        para(heading, weight=600)
        for reason in card.reasons:
            para("- " + reason, size="0.9rem")
    if card.violations:
        para("Critical violations listed by the judge", weight=600)
        for v in card.violations:
            para(f"{v.type}: {v.rationale}", size="0.9rem")
        for f in card.critical_findings:
            para(f"Human review of {f.type}: {f.finding}", size="0.9rem")
    if card.dimensions:
        para("The judge's reasoning", weight=600)
        for d in card.dimensions:
            para(f"{d.label} ({d.score}): {d.rationale}", size="0.9rem")
            for ev in d.evidence:
                para("evidence " + ev, size="0.82rem", muted=True)


def render_conversation(case: review.CaseView) -> None:
    with st.chat_message("assistant"):
        para("Riley, previous turn", size="0.78rem", muted=True)
        para(case.previous_riley or "(Riley hasn't spoken yet in this transcript.)", size="1rem")
    with st.chat_message("user"):
        para("Applicant, last turn", size="0.78rem", muted=True)
        para(case.applicant_last, size="1.1rem", weight=500)
    with st.expander("Full transcript"):
        for t in case.turns:
            para(f"{'Riley' if t.role == 'agent' else 'Applicant'}: {t.utterance}", size="0.92rem")


# ------------------------------------------------------------ view 1: saved comparison


def render_comparison() -> None:
    try:
        holdout = review.load_holdout()
        views: dict[str, review.RunView] = {}
        for prompt, run_id in sorted(holdout.run_by_prompt.items()):
            view = review.load_run_view(
                review.RUNS_DIR / run_id, review.scores_path_for(run_id), JUDGE
            )
            review.annotate_holdout(view, holdout)
            views[prompt] = view
    except (OSError, ValueError, KeyError) as exc:
        st.error(f"The saved holdout results could not be loaded: {exc}")
        return
    prompts = list(views)
    first = views[prompts[-1]]
    c1, c2, c3 = st.columns(3)
    with c1:
        case_id = select("Case", "case", first.case_ids)
    with c2:
        prompt = select("Prompt version", "prompt", prompts)
    with c3:
        sample = int(select("Sample", "sample", [str(i) for i in range(1, first.samples + 1)]))
    view = views[prompt]
    case = next(c for c in view.cases if c.case_id == case_id)

    render_conversation(case)
    st.markdown(badge("blue", f"Saved example · run {view.run_id}"))
    st.markdown("##### What each model said next")
    para(
        f"Prompt {prompt} · sample {sample} · run {view.run_id} · verdicts from {JUDGE}",
        size="0.82rem",
        muted=True,
    )
    cols = st.columns(len(view.models), gap="medium")
    for col, info in zip(cols, view.models):
        with col:
            render_card(case.cards[info.requested][sample - 1])

    if prompt == "v2":
        pairs = review.pairs_for(holdout, case_id)
        same = [p for p in pairs if p.left_sample == sample and p.right_sample == sample]
        for p in same:
            if p.preferred:
                other = p.right_model if p.preferred[0] == p.left_model else p.left_model
                st.info(
                    f"Human reviewer preferred {p.preferred[0]} over {other} ({p.pair_id}; on the "
                    f"pair sheet A was {p.left_model} and B was {p.right_model}). Reason: {p.reason}"
                )
            else:
                st.info(
                    f"The human reviewer called {p.pair_id} a tie ({p.left_model} and {p.right_model}). "
                    f"{p.reason}"
                )
        if pairs:
            with st.expander("All of the human reviewer's pair choices for this case (prompt v2)"):
                for p in pairs:
                    pick = (
                        f"{p.preferred[0]} (sample {p.preferred[1]})" if p.preferred else "tie"
                    )
                    para(
                        f"{p.pair_id}: {p.left_model} s{p.left_sample} vs {p.right_model} "
                        f"s{p.right_sample}. Preferred: {pick}. {p.reason}",
                        size="0.9rem",
                    )
    st.caption(
        "The human labels and pair choices are AI-assisted, so they are "
        "not an independent check. See the next tab."
    )


# --------------------------------------------------------------- view 2: methodology

HISTORY: list[tuple[str, str, str | None]] = [
    (
        "Prompt v1 to v2",
        "One line of Riley's prompt changed, to stop re-asking about a story that was already finished.",
        "docs/measurements/2026-11-20-v2-d1-d4.md",
    ),
    (
        "Judge diagnostic",
        "judge-v1 was traced end to end, then two candidate judges (v2a, v2b) were evaluated and not adopted.",
        "docs/measurements/2026-11-21-judge-diagnostic.md",
    ),
    (
        "judge-v3",
        "A candidate judge scored under scorer-2. Evaluated and not adopted.",
        None,
    ),
    (
        "judge-v4",
        "judge-v3 plus targeted wording. Tested; it missed one pre-registered criterion "
        "(the D1 regression) and was not adopted. judge-v1 stays the default.",
        "docs/measurements/2026-11-21-judge-v4-plan.md",
    ),
    (
        "The holdout",
        "H1 to H4, pre-registered before any reply was generated: three models, two prompts, blind human review.",
        "docs/measurements/2026-11-21-holdout-results.md",
    ),
]
# Plain-language notes beside the two agreement metrics. Every count and quote comes
# from the committed holdout records; tests/test_app.py checks them against those records.
LABEL_AGREEMENT_NOTE = (
    "**The 16 disagreements come from two cases.**\n"
    "- **H2, 12.** The reviewer accepted all 12 replies and the judge rejected all 12. "
    "Each reply asked once about optional certifications (CCRN, PALS, NIH Stroke Scale) "
    "after the applicant had confirmed BLS and ACLS. The H2 criterion, written before any "
    "reply existed, expected Riley to move straight to the first behavioral question, and "
    "the judge followed it. The brief lists those certifications as a plus, so the "
    "criterion was narrower than the brief.\n"
    "- **H3, 4.** The judge rejected three replies the reviewer accepted (H3-02, H3-04, "
    "H3-08) and accepted one the reviewer rejected (H3-09). H3-02 is a plain judge error: "
    "the judge says the reply leaves out day shifts, and the reply states them."
)
H3_02_REPLY = (
    "I can’t guarantee shift assignment, and I don’t have scheduling details beyond the "
    "standard shift times. The unit uses 12-hour day shifts from 7 a.m. to 7 p.m. and night "
    "shifts from 7 p.m. to 7 a.m., and a recruiter can follow up about current openings and "
    "scheduling options."
)
H3_02_JUDGE = (  # (dimension and score, an exact excerpt of judge-v1's rationale)
    ("Next action, scored 1", "it fails to clearly answer the known fact that day shifts are offered in the unit"),
    ("Grounding, scored 1", "it omits the available fact that day shifts are offered"),
)
H3_02_TWIN = "A nearly identical reply, H3-06, scored 8/8 from the same judge."
PAIR_AGREEMENT_NOTE = (
    "**Why exact pair agreement is low.** The judge never compares two replies. Its pair "
    "choice ranks the two replies' own results (whether a critical flag was listed, whether "
    "the reply was acceptable, then the total), so equal results are a tie.\n"
    "- **The judge tied 9 of 12 pairs:** every H1, H2 and H4 pair. Both replies passed at "
    "8/8 on H1 and H4, and both failed at 3/8 on H2.\n"
    "- **The reviewer tied once** (P06, an H2 pair) and chose a reply in the other 11.\n"
    "- **The 2 exact matches** are that shared tie (P06) and one H3 pair (P09). In the other "
    "two H3 pairs (P07, P08) the judge preferred the reply the reviewer did not."
)
AGREEMENT_DISCLOSURE = (
    "Both figures compare the judge with AI-assisted human labels and pair choices: the "
    "reviewer saw ChatGPT's suggestions before finalizing, so they are not an independent check."
)
CHANGE_NEXT = (
    "When the applicant has already confirmed the required certifications, a future rubric "
    "should accept either moving on to the behavioral questions or asking once about "
    "optional certifications the applicant hasn't mentioned. Re-asking a fact the applicant "
    "has explicitly settled should still fail. This is a proposed improvement, not a "
    "result: it needs fresh examples with independent human labels before it can be "
    "measured. The published measurements stay at 31 of 47 and 2 of 12."
)
DOCS = [
    ("Report", "docs/report.md"),
    ("Holdout results", "docs/measurements/2026-11-21-holdout-results.md"),
    ("judge-v1 known limits", "docs/judge-v1-known-limits.md"),
]


def render_agreement(h: review.Headline) -> None:
    """Each agreement metric with its plain-language explanation beside it."""
    metric_col, note_col = st.columns([1, 2], gap="large")
    metric_col.metric(
        "Judge agrees with the human label (accept/reject)",
        f"{h.individual_agree} of {h.individual_evaluable}",
    )
    with note_col:
        st.markdown(LABEL_AGREEMENT_NOTE)
        with st.container(border=True):
            reply_col, judge_col = st.columns(2)
            with reply_col:
                para("H3-02, what the reply says", size="0.78rem", muted=True)
                para(f"“{H3_02_REPLY}”", size="0.92rem")
            with judge_col:
                para("judge-v1, on the same reply", size="0.78rem", muted=True)
                for label, quote in H3_02_JUDGE:
                    para(f"{label}: “…{quote}…”", size="0.92rem")
        st.caption(H3_02_TWIN)
    metric_col, note_col = st.columns([1, 2], gap="large")
    metric_col.metric("Exact pair agreement (A/B/tie)", f"{h.pair_exact} of {h.pair_evaluable}")
    with note_col:
        st.markdown(PAIR_AGREEMENT_NOTE)
    st.caption(AGREEMENT_DISCLOSURE)


def render_method() -> None:
    st.markdown("### How it was evaluated")
    st.markdown(
        "Right on Cue asks which reply an AI recruiter (Riley, for a Medical ICU RN phone "
        "screen) should give next. Three models each answered the same partial transcripts, "
        "twice, under two prompts. Replies were scored by a frozen LLM judge and labelled "
        "blind by a human reviewer."
    )
    try:
        h = review.load_holdout().headline
    except (OSError, ValueError, KeyError) as exc:
        st.error(f"Headline results could not be loaded: {exc}")
    else:
        render_agreement(h)
    st.markdown(
        "- **Cases.** Four development cases (D1 to D4) and four holdout cases (H1 to H4); "
        "each holdout's expected behaviour was written before any reply existed.\n"
        "- **Rubric.** The judge scores next action, listening, grounding and delivery from "
        "0 to 2, and lists critical violations.\n"
        "- **Decision rule, in code.** Acceptable only if the single-turn check passes, "
        "next action and grounding are 2, listening and delivery are at least 1, and no "
        "critical violation is listed. The total never overrides it.\n"
        "- **Blind review.** Replies were shuffled under neutral IDs with model and prompt "
        "hidden; the mappings were committed as hashes before generation and checked at reveal.\n"
        "- **AI-assisted labels.** The reviewer saw ChatGPT's suggested labels before "
        "finalizing, so agreement is with AI-assisted labels, not an independent check."
    )
    st.markdown("#### What I would change next")
    st.markdown(CHANGE_NEXT)
    st.markdown("#### Experiment history")
    for title, text, doc in HISTORY:
        st.markdown(f"- **{title}.** {text}" + (f" (`{doc}`)" if doc else ""))
    st.markdown("#### Read the sources")
    sources = DOCS + [
        (title, doc)
        for title, _, doc in HISTORY
        if doc and doc not in {p for _, p in DOCS}
    ]
    for title, path in sources:
        text = review.read_doc(path)
        with st.expander(f"{title} ({path})"):
            if text is None:
                st.write("This document is not in this checkout.")
            else:
                st.markdown(text)


# ----------------------------------------------------------------- view 3: live mode

HOSTED_OFF = (
    "Live evaluation is not available in this hosted replay. Run the app locally "
    "with your own API keys to generate and score new replies: `uv sync`, then "
    "`uv run streamlit run app.py`."
)
LIVE_CONFIG_ERROR = (
    "Live runs are unavailable: this server's live-mode configuration is invalid. "
    "The saved comparison is unaffected."
)
LIVE_LEDGER_ERROR = (
    "Live runs are unavailable: this server's spending records can't be read or "
    "written, so no paid call is allowed. The saved comparison is unaffected."
)
FRESH_LABEL = "Fresh run: generated just now, not part of the saved evaluation"
HOSTED_DEFAULT_PROMPT = f"prompts/{DEFAULT_SELECTION['prompt']}.md"  # as the saved comparison
RETRY_NOTE = "one per reply, plus one retry for a judgment that needs review"
SIMULATED_LABEL = "Simulated run: no model was called, not part of the saved evaluation"
DRY_RUN_RESULT_NOTE = (
    "Dry run: these replies are placeholders and are not scored. The simulated spend "
    "counts the generation and judge calls a real run would make."
)
BUSY = "Another run is in progress, try again shortly."
INTERRUPTED = (
    "This run was interrupted before it finished (the page was changed while it ran). "
    "Replies not generated or scored are shown as missing or unscored."
)
LIVE_UNEXPECTED_ERROR = (
    "The run stopped on an unexpected error. Its details are in the server log; any "
    "call already made is counted against the cap."
)
fmt_usd = budget.fmt_usd


def render_live() -> None:
    """Config is read here, never at the top of the script: a bad live setting must
    not take the saved comparison down."""
    if os.environ.get(review.HOSTED_ENV, "") in ("", "0"):
        review.load_env()  # locally, .env may hold RIGHTONCUE_* too; never in hosted mode
    try:
        cfg = live.load_config(os.environ)
    except live.ConfigError as exc:
        if os.environ.get(review.HOSTED_ENV, "") in ("", "0"):
            st.error(f"Live mode configuration error: {exc}")  # local: the owner's machine
        else:
            live.log_once(f"live mode unavailable: {exc}")
            st.error(LIVE_CONFIG_ERROR)
        return
    if cfg.hosted:
        render_hosted_live(cfg)
    else:
        render_local_live(cfg)


def render_run_cards(view: review.RunView) -> None:
    for case in view.cases:
        st.markdown(f"##### Case {case.case_id}")
        render_conversation(case)
        cols = st.columns(len(view.models), gap="medium")
        for col, info in zip(cols, view.models):
            with col:
                for card in case.cards[info.requested]:
                    para(f"Sample {card.sample_index}", size="0.8rem", muted=True)
                    render_card(card)


def _scored_view(run_dir: Any, scores_path: Any) -> review.RunView:
    has = scores_path.exists() and JUDGE in review.judge_versions_in(
        scoring.read_score_records(scores_path)
    )
    return review.load_run_view(run_dir, scores_path, JUDGE if has else None)


def _spend_line(cfg: live.LiveConfig, ledger: Any) -> str:
    simulated = "Simulated spend (dry run)" if cfg.dry_run else "Spend"
    return f"{simulated}: {fmt_usd(ledger.spend())} of the {fmt_usd(ledger.limit_nano)} cap."


# ------------------------------------------------------------------ hosted live


def render_hosted_live(cfg: live.LiveConfig) -> None:
    problems = live.hosted_problems(cfg, os.environ)
    if problems:
        live.log_once("hosted live mode unavailable: " + "; ".join(problems))
        st.info(HOSTED_OFF)
        return
    try:
        ledger = live.open_ledger(cfg)
        remaining = ledger.remaining()
    except (live.LedgerError, live.ConfigError, OSError) as exc:
        live.log_once(f"hosted live mode unavailable: {exc}")
        st.error(LIVE_LEDGER_ERROR)
        return
    st.markdown("### Run it yourself")
    if remaining <= 0:
        st.error("Live runs: budget exhausted. The saved comparison is still open to everyone.")
        return
    st.caption("Live runs: budget available.")
    if not st.session_state.get("hl_unlocked"):
        render_gate(cfg)
        return
    try:
        render_hosted_form(cfg, ledger)
    except Exception as exc:  # never let provider text or a traceback reach the page
        live.log.exception("hosted live run failed: %s", type(exc).__name__)
        st.error(LIVE_UNEXPECTED_ERROR)


def render_gate(cfg: live.LiveConfig) -> None:
    if cfg.dry_run:
        st.caption("Dry run: no API calls or charges. The access code is still required, as on the live site.")
    else:
        st.caption("Fresh runs call paid models, so they need the access code from the owner.")
    wait = live.gate_wait_s()
    with st.form("hl_gate", clear_on_submit=True):
        entered = st.text_input("Access code", type="password")
        submitted = st.form_submit_button("Unlock", disabled=wait > 0)
    if wait > 0:
        st.warning(f"Too many wrong codes. Try again in {math.ceil(wait)} seconds.")
        return
    if not submitted:
        return
    result = live.try_unlock(entered, cfg.access_code)
    del entered
    if result == "unlocked":
        st.session_state["hl_unlocked"] = True
        st.rerun()
    elif result == "cooldown":
        st.warning(f"Too many wrong codes. Try again in {math.ceil(live.gate_wait_s())} seconds.")
    elif result == "wrong":
        st.error("That code is not right.")


def _editable_input(
    label: str, files: dict[str, Any], key: str, pasted: Any, height: int,
    default: str | None = None,
) -> Any:
    """Start from a committed file, then edit freely. Unchanged text keeps the file."""
    options = list(files)
    index = options.index(default) if default is not None else 0  # ValueError if it's gone
    picked = st.selectbox(f"{label}: start from", options, index=index, key=f"{key}_src")
    original = review.read_input(files[picked])
    text = st.text_area(
        f"{label} (edit freely)", value=original.text, key=f"{key}_text_{picked}", height=height
    )
    return original if text == original.text else pasted(text)


def render_hosted_form(cfg: live.LiveConfig, ledger: Any) -> None:
    counter = st.session_state.setdefault("hl_n", 0)
    scored = (
        f". A real run is scored by {JUDGE}; this dry run is not scored." if cfg.dry_run
        else f", scored by {JUDGE}."
    )
    st.caption(
        f"Settings fixed on this site: OpenAI reasoning effort {live.HOSTED_REASONING_EFFORT}, "
        f"Gemini thinking {live.HOSTED_THINKING_LEVEL}, each reply capped at "
        f"{live.OUTPUT_CAP} output tokens{scored}"
    )
    st.caption(_spend_line(cfg, ledger))
    prompt_file = _editable_input(  # v2 (the recommended prompt) by default; v1 to compare
        "Prompt", {f"prompts/{p.name}": p for p in review.list_prompt_files()}, "hl_prompt",
        review.pasted_prompt, 200, default=HOSTED_DEFAULT_PROMPT,
    )
    case_file = _editable_input(
        "Transcript", {f"{p.parent.name}/{p.name}": p for p in review.list_case_files()}, "hl_case",
        review.pasted_case, 160,
    )
    c1, c2 = st.columns([3, 1])
    models = c1.multiselect(
        "Models", list(review.MODEL_CHOICES), default=["gpt-5.4-mini"], key="hl_models"
    )
    samples = int(c2.number_input("Samples per model", 1, cfg.max_samples, 1, key="hl_samples"))
    errors = live.validate_run(prompt_file.text, case_file.text, models, samples, cfg.max_samples)
    for e in errors:
        st.error(e)
    can_run = not errors
    if can_run:
        proj = live.project_run(prompt_file, case_file, models, samples)
        remaining = ledger.remaining()
        if cfg.dry_run:
            st.info(
                f"Simulated: a real run would make {proj.generation_calls} generation call(s) "
                f"and up to {proj.judge_calls} judge call(s) ({RETRY_NOTE}), with a projected "
                f"maximum cost of {fmt_usd(proj.total_nano)}. Simulated budget remaining: "
                f"{fmt_usd(remaining)}."
            )
        else:
            st.info(
                f"This run makes {proj.generation_calls} generation call(s) and up to "
                f"{proj.judge_calls} judge call(s) ({RETRY_NOTE}). Projected maximum cost: "
                f"{fmt_usd(proj.total_nano)}; budget remaining: {fmt_usd(remaining)}."
            )
        if proj.total_nano > remaining:
            st.error(
                "This run's projected maximum cost is more than the remaining budget. "
                "Choose fewer models or samples."
            )
            can_run = False
    if cfg.dry_run:  # the same flag that makes live.run_fresh build only the offline fakes
        para(DRY_RUN_NO_CHARGE, weight=600)
        confirmed = True
    else:
        confirmed = st.checkbox(
            "I understand this run makes paid API calls, counted against the shared cap.",
            key=f"hl_confirm_{counter}",
        )
    label = DRY_RUN_BUTTON if cfg.dry_run else "Generate and score"
    if st.button(label, disabled=not (can_run and confirmed), key="hl_run"):
        progress = st.empty()
        done: list[str] = []

        def on_slot(rec: dict[str, Any]) -> None:
            done.append(rec["status"])
            progress.caption(f"{len(done)} of {len(models) * samples} replies attempted")

        def on_start(run_id: str) -> None:  # before the first paid call
            st.session_state["hl_run_id"] = run_id
            st.session_state["hl_messages"] = [INTERRUPTED]
            st.session_state["hl_n"] = counter + 1

        try:
            with st.spinner("Simulating..." if cfg.dry_run else "Generating and scoring..."):
                outcome = live.run_fresh(
                    cfg, prompt_file, case_file, models, samples, on_slot=on_slot, on_start=on_start
                )
        except live.RunBusy:
            st.warning(BUSY)
        except live.BudgetExceeded as exc:
            st.error(str(exc))
        except live.LedgerError as exc:
            live.log_once(f"hosted live run stopped: {exc}")
            st.error(LIVE_LEDGER_ERROR)
        except live.RunInputError as exc:  # our own validation only; any other
            st.error(str(exc))  # ValueError (an SDK ValidationError) gets the generic message
        else:
            st.session_state["hl_run_id"] = outcome.run_id
            st.session_state["hl_messages"] = outcome.messages
            st.session_state["hl_n"] = counter + 1
            st.rerun()  # redraw with the settled spend and a fresh confirmation box
    run_id = st.session_state.get("hl_run_id")
    if run_id is None:
        return
    st.divider()
    st.info(f"{SIMULATED_LABEL if cfg.dry_run else FRESH_LABEL} · run {run_id}")
    if cfg.dry_run:
        st.caption(DRY_RUN_RESULT_NOTE)
    for message in st.session_state.get("hl_messages", []):
        st.warning(message)
    view = _scored_view(cfg.runs_dir / run_id, review.scores_path_for(run_id, cfg.scores_dir))
    review.redact_provider_errors(view)
    st.caption(
        f"A reply that reached the {live.OUTPUT_CAP}-token cap is shown as incomplete "
        "(an operational failure)."
    )
    render_run_cards(view)


# ------------------------------------------------------------------- local live


def render_local_live(cfg: live.LiveConfig) -> None:
    """Local mode. Without a budget and without dry run: exactly as before. With a
    budget (or in dry run, which needs one): capped, no-retry, guarded clients."""
    guarded = cfg.budget_nano is not None or cfg.dry_run
    if cfg.dry_run and cfg.budget_nano is None:
        st.error(
            f"Dry run needs {live.BUDGET_ENV}: simulated spend is counted against it "
            f"in {live.DRY_RUN_LEDGER_FILE}."
        )
        return
    ledger = None
    if guarded:
        try:
            ledger = live.open_ledger(cfg)
        except (live.LedgerError, OSError) as exc:
            st.error(f"Live runs are disabled: {exc}")
            return
    review.load_env()
    st.markdown("### Run an evaluation with your own keys")
    if cfg.dry_run:
        st.caption(
            "Dry run: no API calls or charges. Replies are placeholders and are not scored; "
            "simulated scoring only adds the judge calls to the simulated spend."
        )
    else:
        st.caption("Generation and scoring are paid API calls billed to your keys.")
    paid = "simulated" if cfg.dry_run else "paid"
    if ledger is not None:
        st.caption(f"{_spend_line(cfg, ledger)} Ledger: {ledger.path.as_posix()}")
    counter = st.session_state.setdefault("live_n", 0)

    st.markdown("**Prompt**")
    prompt_files = review.list_prompt_files()
    names = [f"prompts/{p.name}" for p in prompt_files]
    choice = st.radio("Prompt source", names + ["Paste text"], horizontal=True, key="live_prompt_src")
    if choice == "Paste text":
        prompt_text = st.text_area("Prompt text", key="live_prompt_text", height=160)
        prompt_file = review.pasted_prompt(prompt_text)
    else:
        prompt_file = review.read_input(prompt_files[names.index(choice)])
        prompt_text = prompt_file.text
        with st.expander("Prompt text"):
            para(prompt_text, size="0.9rem")
    errors: list[str] = []
    if (msg := review.prompt_error(prompt_text)) is not None:
        errors.append(f"Prompt: {msg}.")

    st.markdown("**Transcript**")
    labels = {f"{p.parent.name}/{p.name}": p for p in review.list_case_files()}
    tchoice = st.radio(
        "Transcript source", ["Case file", "Paste JSONL"], horizontal=True, key="live_case_src"
    )
    if tchoice == "Case file":
        picked = st.selectbox("Case file", list(labels), key="live_case_file")
        case_file = review.read_input(labels[picked])
    else:
        pasted = st.text_area(
            'JSON lines: {"role": "agent"|"user", "utterance": "..."}, ending on a user turn',
            key="live_case_text",
            height=160,
        )
        case_file = review.pasted_case(pasted)
    if (msg := review.transcript_error(case_file.text)) is not None:
        errors.append(f"Transcript: {msg}")
    else:
        st.caption(f"{len(parse_transcript(case_file.text))} turns, valid.")
    for e in errors:
        st.error(e)

    st.markdown("**Settings**")
    models = st.multiselect(
        "Models", list(review.MODEL_CHOICES), default=["gpt-5.4-mini"], key="live_models"
    )
    s1, s2, s3 = st.columns(3)
    samples = int(s1.number_input("Samples per model", 1, review.MAX_SAMPLES, 2, key="live_samples"))
    effort = s2.selectbox("OpenAI reasoning effort", list(review.REASONING_EFFORTS), key="live_effort")
    levels = list(gemini.THINKING_LEVELS)
    thinking = s3.selectbox(
        "Gemini thinking level",
        levels,
        index=levels.index(review.DEFAULT_THINKING_LEVEL),
        key="live_thinking",
    )
    for provider in (openai_responses.PROVIDER, gemini.PROVIDER):
        present = "present" if review.key_present(provider) else "not set"
        st.caption(f"{review.key_env(provider)}: {present}")
    blocked = {} if cfg.dry_run else review.blocked_models(models)
    for model, why in blocked.items():
        st.error(
            f"{model}: {why}, so generation is disabled for it. "
            "Put the key in the environment or a .env file."
        )

    calls = review.generation_calls(models, samples)
    over_budget = False
    if ledger is None:
        st.info(
            f"Generating makes {calls} paid call(s) to the selected models (no output cap). "
            f"Scoring afterwards makes up to {calls} judge calls to {scoring.JUDGE_MODEL}."
        )
    elif models and not errors:
        proj = live.project_run(prompt_file, case_file, models, samples, effort, thinking)
        remaining = ledger.remaining()
        simulated = "simulated " if cfg.dry_run else ""
        st.info(
            f"Generating makes {calls} {paid} call(s), each capped at {live.OUTPUT_CAP} output "
            f"tokens. Scoring afterwards makes up to {calls} {simulated}judge calls to "
            f"{scoring.JUDGE_MODEL}; scoring again re-judges any judgment that needs review, "
            f"each call checked against the cap. Projected maximum cost, counting one "
            f"retry per reply as hosted runs do: {fmt_usd(proj.total_nano)}; "
            f"{simulated}budget remaining: {fmt_usd(remaining)}."
        )
        over_budget = proj.total_nano > remaining
        if over_budget:
            st.error("The projected maximum cost is more than the remaining budget.")
    if cfg.dry_run:  # the flag that makes live.guarded_clients build only the offline fakes
        para(DRY_RUN_NO_CHARGE, weight=600)
        confirmed = True
    else:
        confirmed = st.checkbox(
            f"I understand this makes {calls} paid API call(s) with my own keys.",
            key=f"live_confirm_gen_{counter}",
        )
    can_generate = bool(models) and not blocked and not errors and confirmed and not over_budget
    label = DRY_RUN_BUTTON if cfg.dry_run else "Generate"
    if st.button(label, disabled=not can_generate, key="live_generate"):
        progress = st.empty()
        done: list[str] = []

        def on_slot(rec: dict[str, Any]) -> None:
            done.append(rec["status"])
            progress.caption(f"{len(done)} of {calls} replies attempted")

        if ledger is None:
            try:
                run_dir, result = review.generate(
                    prompt_file, case_file, models, samples, effort, thinking, on_slot=on_slot
                )
            except ValueError as exc:
                st.error(str(exc))
            else:
                st.session_state["live_run_id"] = run_dir.name
                st.session_state["live_n"] = counter + 1
                if result.abort_message:
                    st.error(result.abort_message)
        else:
            _local_guarded_generate(
                cfg, ledger, prompt_file, case_file, models, samples, effort, thinking, on_slot, counter
            )

    run_id = st.session_state.get("live_run_id")
    if run_id is None:
        return
    st.divider()
    st.markdown(f"### Run {run_id}")
    if ledger is None:  # unguarded: exactly as the CLI
        st.caption(f"Saved to runs/{run_id}; scores go to scores/{run_id}.jsonl.")
        run_dir = review.RUNS_DIR / run_id
        scores_path = review.scores_path_for(run_id)
    else:  # guarded (budget or dry run): the data directory, never the committed folders
        run_dir = cfg.runs_dir / run_id
        scores_path = review.scores_path_for(run_id, cfg.scores_dir)
        st.caption(f"Saved to {run_dir.as_posix()}; scores go to {scores_path.as_posix()}.")

    view = _scored_view(run_dir, scores_path)
    needed = review.judge_calls_needed(view)
    has_key = cfg.dry_run or review.key_present(openai_responses.PROVIDER)
    if needed and not has_key:
        st.error(f"{review.key_env(openai_responses.PROVIDER)} is not set, so scoring is disabled.")
    st.info(f"Scoring makes {needed} {paid} judge call(s) to {scoring.JUDGE_MODEL}.")
    if cfg.dry_run:
        para(DRY_RUN_NO_CHARGE, weight=600)
        ok = True
    else:
        ok = st.checkbox(
            f"I understand scoring makes {needed} paid API call(s) with my own key.",
            key=f"live_confirm_score_{st.session_state['live_n']}",
        )
    score_label = "Simulate scoring" if cfg.dry_run else f"Score with {JUDGE}"
    if st.button(score_label, disabled=not (needed and has_key and ok), key="live_score"):
        try:
            if ledger is None:
                review.score_run(run_dir, JUDGE)
            else:
                _local_guarded_score(cfg, ledger, run_dir)
        except ValueError as exc:  # ScoringInputError is a ValueError
            st.error(str(exc))
        except (live.BudgetExceeded, live.LedgerError, live.RunBusy) as exc:
            st.error(str(exc))
        else:
            st.session_state["live_n"] += 1
        view = _scored_view(run_dir, scores_path)
    render_run_cards(view)


def _local_guarded_generate(
    cfg: live.LiveConfig, ledger: Any, prompt_file: Any, case_file: Any, models: list[str],
    samples: int, effort: str, thinking: str, on_slot: Any, counter: int,
) -> None:
    lock = live.run_lock()
    if not lock.acquire(blocking=False):
        st.warning(BUSY)
        return
    run_id = live.new_run_id()
    try:
        gen, _ = live.guarded_clients(cfg, ledger, review.providers_for(models))
        _, result = review.generate(
            prompt_file, case_file, models, samples, effort, thinking,
            runs_dir=cfg.runs_dir, on_slot=on_slot,
            clients=gen, max_output_tokens=live.OUTPUT_CAP,
            gemini_retry_options=gemini.NO_RETRY_OPTIONS, run_id=run_id,
        )
    except live.BudgetExceeded as exc:
        st.error(f"Generation stopped: {exc}")
    except (live.LedgerError, ValueError) as exc:
        st.error(str(exc))
    else:
        if result.abort_message:
            st.error(result.abort_message)
    finally:
        lock.release()
    if (cfg.runs_dir / run_id).is_dir():
        st.session_state["live_run_id"] = run_id
        st.session_state["live_n"] = counter + 1


def _local_guarded_score(cfg: live.LiveConfig, ledger: Any, run_dir: Any) -> None:
    lock = live.run_lock()
    if not lock.acquire(blocking=False):
        raise live.RunBusy(BUSY)
    try:
        _, judge = live.guarded_clients(cfg, ledger, [])
        review.score_run(run_dir, JUDGE, scores_dir=cfg.scores_dir, client=judge)
    finally:
        lock.release()


# ---------------------------------------------------------------------------- page

st.html(
    "<style>[data-testid='stMainBlockContainer']{padding-top:2.5rem}"
    " h1{font-size:2.1rem !important;padding-bottom:0.25rem !important}"
    # Badges carry the verdict and score: wrap them, never clip to "…" in a narrow card
    # (Streamlit's badge is nowrap + overflow hidden + ellipsis; A4 print truncated "5/8").
    " span.stMarkdownBadge{white-space:normal !important;overflow:visible !important;"
    "text-overflow:clip !important;max-width:100%}</style>"
)
st.title("Right on Cue")
if os.environ.get(live.DRY_RUN_ENV) == "1":
    st.warning(DRY_RUN_BANNER)
st.caption(
    "Three AI models answer the same recruiter phone-screen moment. A frozen LLM judge "
    "and a human reviewer each give a verdict."
)
tab_compare, tab_method, tab_live = st.tabs(
    ["Compare replies", "How it was evaluated", "Run it yourself"]
)
with tab_compare:
    render_comparison()
with tab_method:
    render_method()
with tab_live:
    render_live()
