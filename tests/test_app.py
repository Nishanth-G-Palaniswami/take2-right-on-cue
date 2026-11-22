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


def test_default_view_is_h3_v2_sample_1() -> None:
    at = run_app()
    assert not at.exception
    assert [at.radio(key=k).value for k in ("sel_case", "sel_prompt", "sel_sample")] == ["H3", "v2", "1"]
    assert (at.query_params["case"], at.query_params["prompt"], at.query_params["sample"]) == ("H3", "v2", "1")
    text = body(at)
    assert "Can you guarantee that I'd be on days if I took this job?" in text
    for model in MODELS:
        assert saved_reply(V2, "H3", model, 1) in text
    verdicts = badges(at, "judge-v1:")
    assert len(verdicts) == 3 and all("/8" in v for v in verdicts)
    labels = badges(at, "Human label:")
    assert len(labels) == 3
    assert not [e for e in at.error if "operational" in e.value]
    # the owner's pair choice P08 (H3, sample 1) is shown, and the model name is its preferred one
    assert any("Human reviewer preferred gpt-5.4 over gpt-5.4-mini (P08" in i.value for i in at.info)


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
    assert saved_reply(V2, "H2", "gpt-5.4", 1) in body(at)


def test_invalid_query_param_falls_back_to_the_default() -> None:
    at = run_app(case="H9", prompt="v3", sample="7")
    assert not at.exception
    assert [at.radio(key=k).value for k in ("sel_case", "sel_prompt", "sel_sample")] == ["H3", "v2", "1"]


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
    assert "gpt-5.4-mini: OPENAI_API_KEY is not set, so generation is disabled" in errors
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
    at.number_input(key="live_samples").set_value(1)
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
    assert manifest["prompt"]["path"] == "prompts/v1.md"
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
