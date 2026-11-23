"""app.py through streamlit.testing. Offline: no key, no .env, only fake clients."""

import html
import json
import re
from pathlib import Path
from typing import Any

import pytest
from streamlit.testing.v1 import AppTest
from test_gemini import FakeGeminiClient
from test_run import FakeClient
from test_scoring import judge

from rightoncue import review

REPO = Path(__file__).parent.parent
APP = str(REPO / "app.py")
V2 = "20261122T024715Z-182705"
V1 = "20261122T024845Z-8babdd"
MODELS = ["gpt-5.4", "gpt-5.4-mini", "gemini-3.5-flash"]


@pytest.fixture(autouse=True)
def offline(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(REPO)  # app.py changes directory; this restores it afterwards
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv(review.HOSTED_ENV, raising=False)
    for name in ("RIGHTONCUE_ACCESS_CODE", "RIGHTONCUE_BUDGET_USD", "RIGHTONCUE_DATA_DIR",
                 "RIGHTONCUE_MAX_SAMPLES", "RIGHTONCUE_DRY_RUN", "RIGHTONCUE_DRY_RUN_DELAY_S"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(review, "load_env", lambda: None)  # never read the real .env

    def boom() -> Any:
        raise AssertionError("a real client must not be built in an offline test")

    monkeypatch.setattr(review, "CLIENT_FACTORIES", {"openai": boom, "gemini": boom})


def run_app(**params: str) -> AppTest:
    at = AppTest.from_file(APP, default_timeout=60)
    for k, v in params.items():
        at.query_params[k] = v
    return at.run()


def body(at: AppTest) -> str:
    """All visible text: html bodies (unescaped) and markdown, one per line."""
    parts = [html.unescape(re.sub(r"<[^>]+>", "", e.proto.body)) for e in at.get("html")]
    parts += [m.value for m in at.markdown]
    return "\n".join(parts)


def badges(at: AppTest, marker: str) -> list[str]:
    """The verdict / label badges (not the rendered documents that mention them)."""
    return [m.value for m in at.markdown if m.value.startswith(":") and "-badge[" in m.value and marker in m.value]


def saved_reply(run_id: str, case: str, model: str, sample: int) -> str:
    view = review.load_run_view(review.RUNS_DIR / run_id, review.scores_path_for(run_id), "judge-v1")
    c = next(c for c in view.cases if c.case_id == case)
    reply = c.cards[model][sample - 1].reply
    assert reply
    return reply


def v3_reply(case: str, model: str, sample: int) -> str:
    run_dir, scores = review.saved_runs(review.load_holdout())["v3"]
    view = review.load_run_view(run_dir, scores, "judge-v1")
    reply = next(c for c in view.cases if c.case_id == case).cards[model][sample - 1].reply
    assert reply
    return reply


def test_default_view_is_h3_v3_sample_1() -> None:
    """The bare URL opens on the final prompt: H3, v3, sample 1, from the v3 retest run."""
    at = run_app()
    assert not at.exception
    assert [at.radio(key=k).value for k in ("sel_case", "sel_prompt", "sel_sample")] == ["H3", "v3", "1"]
    assert (at.query_params["case"], at.query_params["prompt"], at.query_params["sample"]) == ("H3", "v3", "1")
    assert at.radio(key="sel_prompt").options == ["v1", "v2", "v3"]
    assert at.radio(key="sel_case").options == ["H1", "H2", "H3", "H4"]
    text = body(at)
    assert "Can you guarantee that I'd be on days if I took this job?" in text
    for model in MODELS:
        assert v3_reply("H3", model, 1) in text
    assert review.V3_RETEST_RUN_ID in text
    verdicts = badges(at, "judge-v1:")
    assert len(verdicts) == 3 and all("/8" in v for v in verdicts)
    # no human labelled the v3 replies, so none is shown; the recommended setup is marked once
    assert badges(at, "Human label:") == []
    assert badges(at, "Recommended setup") == [":violet-badge[Recommended setup: GPT-5.4 + v3]"]
    assert not [i for i in at.info if "Human reviewer preferred" in i.value]
    assert any(c.value.startswith("No human has labelled the v3 replies yet") for c in at.caption)


def test_v2_deep_link_keeps_the_holdout_run_with_labels_and_pairs() -> None:
    at = run_app(case="H3", prompt="v2", sample="1")
    assert not at.exception
    assert [at.radio(key=k).value for k in ("sel_case", "sel_prompt", "sel_sample")] == ["H3", "v2", "1"]
    text = body(at)
    for model in MODELS:
        assert saved_reply(V2, "H3", model, 1) in text
    assert len(badges(at, "Human label:")) == 3
    assert badges(at, "Recommended setup") == []
    # the owner's pair choice P08 (H3, sample 1) is shown, and the model name is its preferred one
    assert any("Human reviewer preferred gpt-5.4 over gpt-5.4-mini (P08" in i.value for i in at.info)


def test_switching_prompt_keeps_the_case_and_sample() -> None:
    at = run_app(case="H4", prompt="v3", sample="2")
    assert not at.exception
    for model in MODELS:
        assert v3_reply("H4", model, 2) in body(at)
    at.radio(key="sel_prompt").set_value("v2").run()
    assert not at.exception
    assert [at.radio(key=k).value for k in ("sel_case", "sel_prompt", "sel_sample")] == ["H4", "v2", "2"]
    assert (at.query_params["case"], at.query_params["prompt"], at.query_params["sample"]) == ("H4", "v2", "2")
    for model in MODELS:
        assert saved_reply(V2, "H4", model, 2) in body(at)
    at.radio(key="sel_prompt").set_value("v3").run()
    assert [at.radio(key=k).value for k in ("sel_case", "sel_prompt", "sel_sample")] == ["H4", "v3", "2"]


def test_query_params_select_case_prompt_and_sample() -> None:
    at = run_app(case="H1", prompt="v1", sample="2")
    assert not at.exception
    assert [at.radio(key=k).value for k in ("sel_case", "sel_prompt", "sel_sample")] == ["H1", "v1", "2"]
    text = body(at)
    for model in MODELS:
        assert saved_reply(V1, "H1", model, 2) in text
    assert V1 in text
    # prompt v1 has no owner pair choices
    assert not [i for i in at.info if "Human reviewer preferred" in i.value]


def test_switching_a_radio_updates_the_url() -> None:
    at = run_app()
    at.radio(key="sel_case").set_value("H2").run()
    assert not at.exception
    assert at.query_params["case"] == "H2"
    assert v3_reply("H2", "gpt-5.4", 1) in body(at)


def test_invalid_query_param_falls_back_to_the_default() -> None:
    at = run_app(case="H9", prompt="v4", sample="7")
    assert not at.exception
    assert [at.radio(key=k).value for k in ("sel_case", "sel_prompt", "sel_sample")] == ["H3", "v3", "1"]


def test_failed_generation_is_an_operational_failure_not_a_reply() -> None:
    at = run_app(case="H4", prompt="v1", sample="2")
    assert not at.exception
    errors = [e.value for e in at.error if "operational" in e.value]
    assert errors == ["Generation failed (operational failure)"]
    # the other two models still show replies, with verdicts and owner labels
    assert len(badges(at, "judge-v1:")) == 2
    assert len(badges(at, "Human label:")) == 2


def test_critical_flag_shows_the_owners_finding() -> None:
    at = run_app(case="H3", prompt="v2", sample="1")
    flags = [i.value for i in at.info if "critical flag" in i.value]
    # H3-04 and H3-08 are the flagged H3 replies; both were reviewed as absent
    at2 = run_app(case="H2", prompt="v2", sample="1")
    flags2 = [i.value for i in at2.info if "critical flag" in i.value]
    assert flags2 and all("found it absent. The raw verdict stands." in f for f in flags2)
    assert all("raw verdict stands" in f for f in flags)


def test_details_expander_has_scores_checks_and_reasoning() -> None:
    at = run_app()
    labels = [e.label for e in at.expander]
    assert labels.count("Scores, checks and reasoning") == 3
    text = body(at)
    assert "next action" in text and "Single-turn check" in text and "The judge's reasoning" in text


def test_method_tab_shows_headline_numbers_and_history() -> None:
    at = run_app()
    assert not at.exception
    assert [m.value for m in at.metric] == ["31 of 47", "2 of 12"]
    text = body(at)
    assert "Experiment history" in text and "judge-v4" in text and "not adopted" in text
    # the plain-language notes beside each metric, the disclosure and the next change
    assert "The 16 disagreements come from two cases." in text
    assert "Why exact pair agreement is low." in text
    captions = [c.value for c in at.caption]
    assert any(c.startswith("Both figures come from the original holdout, prompts v1 and v2, and compare the judge with AI-assisted") for c in captions)
    assert "What I would change next" in text and "asking once about optional certifications" in text
    assert "published measurements stay at 31 of 47 and 2 of 12" in text


def test_method_tab_agrees_with_the_report_on_judge_v5_and_h2() -> None:
    at = run_app()
    assert not at.exception
    md = [m.value for m in at.tabs[1].markdown]  # includes the rendered report
    report = (REPO / "docs" / "report.md").read_text(encoding="utf-8")
    # "What I would change next": the app's own paragraph is the report's, word for word
    change_next = md[md.index("#### What I would change next") + 1]
    assert change_next in report
    assert "case wording alone doesn't get judge-v1 there" in change_next
    assert change_next.endswith("The published measurements stay at 31 of 47 and 2 of 12.")
    assert not any("proposed improvement, not a result" in v for v in md)
    # judge-v5 and both H2 rounds: tested, not adopted, linking the report's evidence
    titles = ("- **judge-v5.**", "- **H2 criteria, round 1.**", "- **H2 criteria, round 2.**")
    entries = [v for v in md if v.startswith(titles)]
    assert [e.split(".**")[0] for e in entries] == [t.removesuffix(".**") for t in titles]
    for entry in entries:
        assert "not adopted" in entry
        urls = re.findall(r"\]\((https://[^)\s]+)\)", entry)
        assert len(urls) == 1 and "/blob/a2dd8d9d1604d79b526cf08bf1f65c2c0c1f37df/" in urls[0]
        assert urls[0] in report
    # the published judge-v1 figures are unchanged
    assert [m.value for m in at.metric] == ["31 of 47", "2 of 12"]


def test_method_tab_leads_with_the_v3_retest() -> None:
    at = run_app()
    assert not at.exception
    tab = at.tabs[1]
    md = [m.value for m in tab.markdown]
    heads = [v for v in md if v.startswith("###")]
    assert heads[:3] == ["### How it was evaluated", "#### What changed with prompt v3?", "#### Original v1/v2 judge–reviewer agreement"]
    text = "\n".join(md)
    # the same-case counts from the saved judge-v1 records: v2 holdout run -> v3 retest
    for row in ("| gpt-5.4 (recommended with v3) | 4/8 | 6/8 |", "| gpt-5.4-mini | 4/8 | 5/8 |",
                "| gemini-3.5-flash | 6/8 | 5/8 |", "| **All three** | **14/24** | **16/24** |"):
        assert row in text, row
    assert "H3: gpt-5.4 0 → 2, gpt-5.4-mini 0 → 1, gemini-3.5-flash 2 → 1" in text
    assert "H1 (2 of 2 for every model), H2 (0 of 2 for every model), H4 (2 of 2 for every model)" in text
    assert "retest on the original cases" in text
    assert "the human reviewer accepted both of its v2 H3 replies, which judge-v1 rejected" in text
    assert "ChatGPT assigned all 96 labels using the transcripts and Nishanth’s summary of feedback" in text
    assert "gpt-5.4 5 → 11, gpt-5.4-mini 5 → 11, gemini-3.5-flash 6 → 6" in text
    # the original agreement figures stay, under their own heading
    assert [m.value for m in at.metric] == ["31 of 47", "2 of 12"]


def _cards_by_id() -> dict[str, review.Card]:
    holdout = review.load_holdout()
    out: dict[str, review.Card] = {}
    for run_id in holdout.run_by_prompt.values():
        view = review.load_run_view(review.RUNS_DIR / run_id, review.scores_path_for(run_id), "judge-v1")
        review.annotate_holdout(view, holdout)
        out.update({c.neutral_id: c for c in view.all_cards() if c.neutral_id})
    return out


def test_agreement_notes_match_the_committed_records() -> None:
    """Every count and quote beside the agreement metrics is derived from the records."""
    cards = _cards_by_id()
    disagree = sorted(
        nid for nid, c in cards.items()
        if c.decision in ("acceptable", "not acceptable") and (c.decision == "acceptable") != c.human_accept
    )
    assert len(disagree) == 47 - 31
    assert [n for n in disagree if n.startswith("H2")] == [f"H2-{i:02d}" for i in range(1, 13)]
    assert all(cards[n].human_accept for n in disagree if n.startswith("H2"))
    assert [n for n in disagree if cards[n].human_accept and n.startswith("H3")] == ["H3-02", "H3-04", "H3-08"]
    assert [n for n in disagree if not cards[n].human_accept] == ["H3-09"]
    # H3-02: the shown reply is the recorded reply, and each judge excerpt is in the
    # recorded rationale of a dimension the judge scored 1
    h302 = cards["H3-02"]
    assert h302.decision == "not acceptable"
    rationale = {d.label: (d.score, d.rationale) for d in h302.dimensions}
    for label, excerpt in [
        ("next action", "it fails to clearly answer the known fact that day shifts are offered in the unit"),
        ("grounding", "it omits the available fact that day shifts are offered"),
    ]:
        score, text = rationale[label]
        assert score == 1 and excerpt in text
    assert "12-hour day shifts from 7 a.m. to 7 p.m." in (h302.reply or "")
    assert (cards["H3-06"].decision, cards["H3-06"].total) == ("acceptable", 8)
    # pairs: the judge's ties, the reviewer's tie and the two exact matches
    pairs = json.loads((review.PAIR_COMPARE).read_text(encoding="utf-8"))["pairs"]
    judge_ties = [p for p in pairs if p["machine"] == "tie"]
    assert len(judge_ties) == 9 and {p["case"] for p in judge_ties} == {"H1", "H2", "H4"}
    assert [p["pair_id"] for p in pairs if p["human"] == "tie"] == ["P06"]
    assert sorted(p["pair_id"] for p in pairs if p["human"] == p["machine"]) == ["P06", "P09"]
    assert sorted(p["pair_id"] for p in pairs if p["machine"] != "tie" and p["human"] != p["machine"]) == ["P07", "P08"]
    # the page shows exactly these records
    at = run_app()
    text = body(at)
    assert f"“{h302.reply}”" in text
    assert "it fails to clearly answer the known fact that day shifts are offered in the unit" in text
    assert "it omits the available fact that day shifts are offered" in text
    assert any("H3-06, scored 8/8" in c.value for c in at.caption)
    for fact in ("H2, 12.", "H3, 4.", "(H3-02, H3-04, H3-08)", "(H3-09)", "tied 9 of 12 pairs", "(P06, an H2 pair)", "(P09)", "(P07, P08)"):
        assert fact in text, fact


def test_hosted_mode_has_no_live_evaluation(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(review.HOSTED_ENV, "1")
    at = run_app()
    assert not at.exception
    assert not [b for b in at.button if b.key in ("live_generate", "live_score")]
    assert not at.multiselect
    assert any("not available in this hosted replay" in i.value for i in at.info)
    assert len(badges(at, "judge-v1:")) == 3  # replay still works


# ------------------------------------------------------------------- live mode


def test_live_without_keys_is_disabled_and_explained() -> None:
    at = run_app()
    assert not at.exception
    assert at.button(key="live_generate").disabled
    errors = " ".join(e.value for e in at.error)
    assert "gpt-5.4: OPENAI_API_KEY is not set, so generation is disabled" in errors
    captions = [c.value for c in at.caption]
    assert "OPENAI_API_KEY: not set" in captions and "GEMINI_API_KEY: not set" in captions
    # the confirmation checkbox alone does not enable it
    at.checkbox(key="live_confirm_gen_0").set_value(True).run()
    assert at.button(key="live_generate").disabled


def test_live_never_shows_a_key_value(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "sk-secret-value-123")
    at = run_app()
    assert "sk-secret-value-123" not in body(at) + " ".join(c.value for c in at.caption)
    assert "OPENAI_API_KEY: present" in [c.value for c in at.caption]


def test_live_pasted_transcript_errors_are_shown() -> None:
    at = run_app()
    at.radio(key="live_case_src").set_value("Paste JSONL").run()
    at.text_area(key="live_case_text").set_value("not json").run()
    assert any(e.value.startswith("Transcript: line 1: invalid JSON") for e in at.error)
    assert at.button(key="live_generate").disabled
    at.text_area(key="live_case_text").set_value('{"role":"agent","utterance":"Hi"}').run()
    assert any("last turn must be from 'user'" in e.value for e in at.error)


def test_live_generate_and_score_with_fake_clients(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    runs, scores = tmp_path / "runs", tmp_path / "scores"
    monkeypatch.setattr(review, "RUNS_DIR", runs)
    monkeypatch.setattr(review, "SCORES_DIR", scores)
    monkeypatch.setenv("OPENAI_API_KEY", "fake-openai")
    monkeypatch.setenv("GEMINI_API_KEY", "fake-gemini")
    openai_fake = FakeClient(["Fake OpenAI words $5 *not bold*.", judge()])
    gemini_fake = FakeGeminiClient(["Fake Gemini words."])
    monkeypatch.setattr(
        review, "CLIENT_FACTORIES", {"openai": lambda: openai_fake, "gemini": lambda: gemini_fake}
    )
    at = AppTest.from_file(APP, default_timeout=60)
    at.run()  # the holdout tab can't load from the empty tmp runs dir; live mode is what's tested
    at.multiselect(key="live_models").set_value(["gpt-5.4-mini", "gemini-3.5-flash"])
    at.number_input(key="live_samples").set_value(1).run()
    # keys present and input valid: only the unticked paid box keeps Generate disabled
    assert not at.tabs[2].error
    assert at.button(key="live_generate").label == "Generate"
    assert at.button(key="live_generate").disabled
    assert at.checkbox(key="live_confirm_gen_0").label == "I understand this makes 2 paid API call(s) with my own keys."
    at.checkbox(key="live_confirm_gen_0").set_value(True).run()
    assert not at.button(key="live_generate").disabled
    assert any("Generating makes 2 paid call(s)" in i.value for i in at.info)
    at.button(key="live_generate").click().run()
    assert not at.exception
    text = body(at)
    assert "Fake OpenAI words $5 *not bold*." in text  # verbatim, not rendered as markdown
    assert "Fake Gemini words." in text
    [run_dir] = [p for p in runs.iterdir()]
    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["prompt"]["path"] == "prompts/v3.md"
    assert [m["model"] for m in manifest["models"]] == ["gpt-5.4-mini", "gemini-3.5-flash"]
    assert len(openai_fake.calls) == 1 and len(gemini_fake.calls) == 1
    assert not scores.exists()
    assert badges(at, "unscored")

    # scoring needs its own confirmation, with a fresh checkbox after generating
    assert at.button(key="live_score").disabled
    assert any("Scoring makes 2 paid judge call(s)" in i.value for i in at.info)
    at.checkbox(key="live_confirm_score_1").set_value(True).run()
    assert not at.button(key="live_score").disabled
    # the fake OpenAI client has one judge answer left; the Gemini reply needs a second
    openai_fake.outputs.append(judge())
    at.button(key="live_score").click().run()
    assert not at.exception
    assert (scores / f"{run_dir.name}.jsonl").is_file()
    verdicts = badges(at, "judge-v1: acceptable · 8/8")
    assert len(verdicts) == 2
    assert len(openai_fake.calls) == 3  # one generation, two judge calls
