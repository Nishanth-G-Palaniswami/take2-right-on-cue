"""Right on Cue: a reviewer-facing Streamlit app. Logic lives in rightoncue.review."""

from __future__ import annotations

import html
import os
from typing import Any

import streamlit as st

from rightoncue import gemini, openai_responses, review, scoring
from rightoncue.transcript import parse_transcript

# The judge prompt paths are relative to the repository root.
os.chdir(review.REPO_ROOT)

st.set_page_config(page_title="Right on Cue", layout="wide", initial_sidebar_state="collapsed")

JUDGE = scoring.DEFAULT_JUDGE_VERSION
DEFAULT_SELECTION = {"case": "H3", "prompt": "v2", "sample": "1"}
MUTED = "#6b7280"

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
        total = f" · {card.total}/8" if card.total is not None else ""
        decision = card.decision or "unscored"
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
        para("Why it was not acceptable", weight=600)
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
DOCS = [
    ("Report", "docs/report.md"),
    ("Holdout results", "docs/measurements/2026-11-21-holdout-results.md"),
    ("judge-v1 known limits", "docs/judge-v1-known-limits.md"),
]


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
        m1, m2 = st.columns(2)
        m1.metric(
            "Judge agrees with the human label (accept/reject)",
            f"{h.individual_agree} of {h.individual_evaluable}",
        )
        m2.metric("Exact pair agreement (A/B/tie)", f"{h.pair_exact} of {h.pair_evaluable}")
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


def render_live() -> None:
    if review.hosted():
        st.info(
            "Live evaluation is not available in this hosted replay. Run the app locally "
            "with your own API keys to generate and score new replies: `uv sync`, then "
            "`uv run streamlit run app.py`."
        )
        return
    review.load_env()
    st.markdown("### Run an evaluation with your own keys")
    st.caption("Generation and scoring are paid API calls billed to your keys.")
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
    blocked = review.blocked_models(models)
    for model, why in blocked.items():
        st.error(
            f"{model}: {why}, so generation is disabled for it. "
            "Put the key in the environment or a .env file."
        )

    calls = review.generation_calls(models, samples)
    st.info(
        f"Generating makes {calls} paid call(s) to the selected models (no output cap). "
        f"Scoring afterwards makes up to {calls} judge calls to {scoring.JUDGE_MODEL}."
    )
    confirmed = st.checkbox(
        f"I understand this makes {calls} paid API call(s) with my own keys.",
        key=f"live_confirm_gen_{counter}",
    )
    can_generate = bool(models) and not blocked and not errors and confirmed
    if st.button("Generate", disabled=not can_generate, key="live_generate"):
        progress = st.empty()
        done: list[str] = []

        def on_slot(rec: dict[str, Any]) -> None:
            done.append(rec["status"])
            progress.caption(f"{len(done)} of {calls} replies attempted")

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

    run_id = st.session_state.get("live_run_id")
    if run_id is None:
        return
    st.divider()
    st.markdown(f"### Run {run_id}")
    st.caption(f"Saved to runs/{run_id}; scores go to scores/{run_id}.jsonl.")
    run_dir = review.RUNS_DIR / run_id
    scores_path = review.scores_path_for(run_id)

    def has_scores() -> bool:
        return scores_path.exists() and JUDGE in review.judge_versions_in(
            scoring.read_score_records(scores_path)
        )

    view = review.load_run_view(run_dir, scores_path, JUDGE if has_scores() else None)
    needed = review.judge_calls_needed(view)
    has_key = review.key_present(openai_responses.PROVIDER)
    if needed and not has_key:
        st.error(f"{review.key_env(openai_responses.PROVIDER)} is not set, so scoring is disabled.")
    st.info(f"Scoring makes {needed} paid judge call(s) to {scoring.JUDGE_MODEL}.")
    ok = st.checkbox(
        f"I understand scoring makes {needed} paid API call(s) with my own key.",
        key=f"live_confirm_score_{st.session_state['live_n']}",
    )
    if st.button(f"Score with {JUDGE}", disabled=not (needed and has_key and ok), key="live_score"):
        try:
            review.score_run(run_dir, JUDGE)
        except ValueError as exc:  # ScoringInputError is a ValueError
            st.error(str(exc))
        else:
            st.session_state["live_n"] += 1
            view = review.load_run_view(run_dir, scores_path, JUDGE)
    for case in view.cases:
        st.markdown(f"##### Case {case.case_id}")
        render_conversation(case)
        cols = st.columns(len(view.models), gap="medium")
        for col, info in zip(cols, view.models):
            with col:
                for card in case.cards[info.requested]:
                    para(f"Sample {card.sample_index}", size="0.8rem", muted=True)
                    render_card(card)


# ---------------------------------------------------------------------------- page

st.html(
    "<style>[data-testid='stMainBlockContainer']{padding-top:2.5rem}"
    " h1{font-size:2.1rem !important;padding-bottom:0.25rem !important}</style>"
)
st.title("Right on Cue")
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
