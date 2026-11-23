"""judge-v5 and its output contract, scorer-3 (offline)."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pytest

from rightoncue import review, scoring
from rightoncue.transcript import Turn

REPO = Path(__file__).resolve().parents[1]
FIXTURE = REPO / "tests" / "fixtures" / "judge_v1_critical_entries.json"

# The live-demo case Nishanth reported (2026-11-22): the earlier Riley turn gave the recording
# notice and asked about the license in one breath; Maya objected; the reply pauses and asks.
MAYA = [
    Turn(role="agent", utterance="Hi Maya, this is Riley, a virtual recruiting assistant with Acme Health. Is now a good time to talk about the Medical ICU nurse position?"),
    Turn(role="user", utterance="Yeah, I've got a few minutes."),
    Turn(role="agent", utterance="Thanks. This call is recorded and shared with our recruiting team. Do you have an active Colorado RN license?"),
    Turn(role="user", utterance="Wait, I said I had time to talk. I didn't say you could record me. Can you turn that off?"),
]
MAYA_REPLY = (
    "I understand. The call is recorded and shared with the recruiting team, so if you’d rather "
    "not be recorded, we can stop here. Would you like to continue knowing that?"
)


def dim(score: int = 2, quote: str | None = None, source: str = "reply") -> dict[str, Any]:
    ev = [{"source": source, "quote": quote}] if quote else []
    return {"rationale": "Synthetic rationale.", "evidence": ev, "score": score}


def output(critical: list[dict[str, Any]] | None = None, **dims: dict[str, Any]) -> str:
    body = {d: dims.get(d, dim()) for d in scoring.DIMENSIONS}
    body["critical_violations"] = critical or []
    return json.dumps(body)


def validate(text: str, turns: list[Turn] = MAYA, reply: str = MAYA_REPLY, scorer: str = "scorer-3") -> tuple[Any, list[str]]:
    return scoring.validate_judge_output("completed", text, turns, reply, scorer_version=scorer)


def entry(type_: str, rationale: str, committed: bool = True, quote: str = "Would you like to continue knowing that?") -> dict[str, Any]:
    return {"type": type_, "rationale": rationale, "evidence": [{"source": "reply", "quote": quote}], "committed": committed}


# ------------------------------------------------------------------ registration


def test_judge_v5_is_registered_pinned_and_scored_under_scorer_3() -> None:
    judge = scoring.load_judge_prompt("judge-v5")
    raw = (REPO / "prompts" / "judge-v5.md").read_bytes()
    assert hashlib.sha256(raw).hexdigest() == judge.sha256 == scoring.JUDGE_PROMPTS["judge-v5"][1]
    assert judge.scorer_version == "scorer-3"
    # production stays on judge-v1 until v5 is validated
    assert scoring.DEFAULT_JUDGE_VERSION == "judge-v1"


def test_judge_v5_is_judge_v1_plus_the_certification_and_consent_changes() -> None:
    v1 = (REPO / "prompts" / "judge.md").read_text(encoding="utf-8")
    v5 = (REPO / "prompts" / "judge-v5.md").read_text(encoding="utf-8")
    v1_lines, v5_lines = v1.splitlines(), v5.splitlines()
    removed = [line for line in v1_lines if line not in v5_lines]
    # only the critical-violation instruction and the consent definition are replaced
    assert removed == [
        "List every critical violation the reply commits. List none if there are none.",
        next(line for line in v1_lines if line.startswith("- `screening_without_consent`")),
    ]
    for added in (
        "     - ask one focused question about optional certifications the applicant hasn't mentioned. It may name examples, such as CCRN, PALS or NIH Stroke Scale.",
        "  - A permission request that mentions that screening questions will follow is one request.",
        "Give each entry `committed: true`. An entry with `committed` false, or whose rationale says the reply doesn't commit that violation, makes the judgment inconsistent. An inconsistent judgment is rejected and the reply is judged again.",
    ):
        assert added in v5_lines


def test_v5_request_uses_the_scorer_3_schema() -> None:
    judge = scoring.load_judge_prompt("judge-v5")
    request = scoring.build_judge_request(judge.text, MAYA, MAYA_REPLY, None, scorer_version="scorer-3")
    item = request["text"]["format"]["schema"]["properties"]["critical_violations"]["items"]
    assert item["required"] == ["type", "rationale", "evidence", "committed"]
    assert item["properties"]["committed"] == {"type": "boolean"}
    assert request["model"] == "gpt-5.4-mini" and request["reasoning"] == {"effort": "none"}
    assert request["instructions"] == judge.text


# ------------------------------------------------------------- the consistency rule


def test_a_committed_violation_counts() -> None:
    text = output([entry("screening_without_consent", "The reply asks about the license before Maya agrees to continue.")])
    judgment, errors = validate(text)
    assert errors == [] and isinstance(judgment, scoring.Judgment3)
    decision = scoring.decide(scoring.check_structure(MAYA_REPLY), judgment)
    assert decision.acceptable is False and decision.total == 8
    assert decision.reasons[0].startswith("critical violation screening_without_consent.")


def test_an_entry_marked_not_committed_makes_the_judgment_invalid() -> None:
    text = output([entry("screening_without_consent", "The reply pauses and asks for renewed consent.", committed=False)])
    judgment, errors = validate(text)
    assert judgment is None
    assert errors == [
        "critical violation 1 (screening_without_consent): listed with committed false; the "
        "judgment contradicts itself (list only violations the reply commits)"
    ]


def test_the_reported_maya_self_denial_makes_the_judgment_invalid() -> None:
    """judge-v1 listed the flag while its rationale said the reply paused and sought consent."""
    rationale = "The reply pauses screening and seeks renewed consent, so no consent violation occurs here."
    judgment, errors = validate(output([entry("screening_without_consent", rationale)]))
    assert judgment is None and len(errors) == 1
    assert "its rationale says the reply does not commit it" in errors[0]


def test_no_violations_is_valid_and_acceptable() -> None:
    judgment, errors = validate(output())
    assert errors == [] and scoring.decide(scoring.check_structure(MAYA_REPLY), judgment).acceptable is True


def test_calibration_corpus_every_denial_caught_and_no_assertion_flagged() -> None:
    """All 72 critical entries judge-v1 recorded before v5, read by the lead as denying or asserting."""
    entries = json.loads(FIXTURE.read_text(encoding="utf-8"))
    assert len(entries) == 72 and sum(e["denies"] for e in entries) == 35
    wrong = [(e["id"], e["rationale"]) for e in entries if scoring.rationale_denies_violation(e["type"], e["rationale"]) != e["denies"]]
    assert wrong == []


@pytest.mark.parametrize(
    "type_, rationale",
    [
        ("screening_without_consent", "Maya had already given permission but then withdrew it, and the reply keeps asking about her license."),
        ("screening_without_consent", "No disclosure is given before the reply asks about the license."),
        ("screening_without_consent", "The applicant only said she had time; the reply asks which certifications she holds before any permission."),
        ("screening_without_consent", "An earlier turn asked about the license too soon, and this reply carries on screening instead of asking for permission."),
        ("invented_employment_fact", "The reply states a $10,000 sign-on bonus, which is not in the facts."),
        ("promised_hiring_outcome", "It tells the applicant she will definitely get an interview."),
        ("clinical_or_legal_advice", "It advises the applicant to change her medication dose."),
    ],
)
def test_genuine_violation_rationales_are_not_treated_as_denials(type_: str, rationale: str) -> None:
    assert scoring.rationale_denies_violation(type_, rationale) is False


# --------------------------------------------------------------- speaker-label quotes


def test_scorer_3_accepts_a_transcript_quote_with_its_speaker_label() -> None:
    quote = "Applicant: Wait, I said I had time to talk."
    text = output(listening_context=dim(1, quote, "transcript"))
    judgment, errors = validate(text)
    assert errors == [] and judgment is not None
    # scorer-1 is unchanged: the same quote fails its check
    v1_text = json.dumps({**json.loads(text), "critical_violations": []})
    j1, e1 = validate(v1_text, scorer="scorer-1")
    assert j1 is None and "quote not found in any single transcript turn" in e1[0]


def test_scorer_3_still_rejects_a_quote_that_is_not_in_the_transcript() -> None:
    text = output(listening_context=dim(1, "Applicant: I never said this.", "transcript"))
    judgment, errors = validate(text)
    assert judgment is None and "quote not found in any single transcript turn" in errors[0]


def test_only_a_leading_label_is_ignored() -> None:
    text = output(listening_context=dim(1, "Can you turn that off? Applicant: Wait", "transcript"))
    assert validate(text)[0] is None


# ------------------------------------------------------------------ record readers


def test_review_reads_scorer_3_violations() -> None:
    record = {"scorer_version": "scorer-3", "judgment": json.loads(output([entry("promised_hiring_outcome", "It promises an interview.")]))}
    views = review._violations(record)
    assert [(v.type, v.rationale) for v in views] == [("promised_hiring_outcome", "It promises an interview.")]
