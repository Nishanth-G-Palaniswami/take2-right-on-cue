"""Milestone 3 scorer tests. Fully offline: every judge is a fake client.

All replies, transcripts, notes and judge outputs below are SYNTHETIC TEST DATA,
written to exercise the scorer; none of them is a real model reply or judgment,
except in test_committed_ok_replies_pass_single_turn, which reads the committed runs.
"""

from __future__ import annotations

import builtins
import copy
import hashlib
import io
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import httpx2
import openai
import pytest

from rightoncue import cli, scoring
from rightoncue.runs import InputFile, ModelSpec, create_run, make_slot_key
from rightoncue.transcript import Turn

REPO = Path(__file__).resolve().parents[1]
JUDGE_PROMPT = REPO / "prompts" / "judge.md"

# --- synthetic test data ------------------------------------------------------

CASE = (
    '{"role":"agent","utterance":"Hi Sam, this is Riley with Acme Health. Is now a good time?"}\n'
    '{"role":"user","utterance":"Yes, now\'s fine."}\n'
    '{"role":"agent","utterance":"This call is recorded and shared with the recruiting team. Is it okay to continue?"}\n'
    '{"role":"user","utterance":"Sure, go ahead. I have BLS and ACLS, and I’d add NIHSS."}\n'
).encode("utf-8")
TURNS = [
    Turn(role="agent", utterance="Hi Sam, this is Riley with Acme Health. Is now a good time?"),
    Turn(role="user", utterance="Yes, now's fine."),
    Turn(role="agent", utterance="This call is recorded and shared with the recruiting team. Is it okay to continue?"),
    Turn(role="user", utterance="Sure, go ahead. I have BLS and ACLS, and I’d add NIHSS."),
]
REPLY = "Thanks. Are your BLS and ACLS both current?"
QUOTE = "BLS and ACLS both current"  # present in every synthetic reply used with judge()
NOTES = """
[C1]
split = "SPLITSENTINEL"
title = "TITLESENTINEL"
pair = "PAIRSENTINEL"
expected_action = "Ask whether BLS and ACLS are current."
good_if = ["Acknowledges the certifications.", "Asks one focused question."]
fail_if = ["Moves on without asking."]
why_included = "WHYSENTINEL"
"""


def judge_dict(
    next_action: Any = 2,
    listening: Any = 2,
    grounding: Any = 2,
    delivery: Any = 2,
    critical: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Synthetic judge output; a score below 2 gets a reply quote as evidence."""

    def dim(name: str, score: Any) -> dict[str, Any]:
        needs = isinstance(score, int) and not isinstance(score, bool) and score < 2
        return {
            "rationale": f"Synthetic {name} rationale.",
            "evidence": [{"source": "reply", "quote": QUOTE}] if needs else [],
            "score": score,
        }

    return {
        "next_action": dim("next action", next_action),
        "listening_context": dim("listening", listening),
        "grounding_role": dim("grounding", grounding),
        "spoken_delivery": dim("delivery", delivery),
        "critical_violations": critical or [],
    }


def judge(**kw: Any) -> str:
    return json.dumps(judge_dict(**kw))


class FakeJudgeResponse:
    def __init__(self, text: str, status: str = "completed") -> None:
        self.output_text = text
        self.status = status
        self.model = "gpt-5.4-mini-2026-03-17"
        self.id = "resp_judge"
        self.usage = {
            "input_tokens": 100,
            "output_tokens": 20,
            "output_tokens_details": {"reasoning_tokens": 0},
        }

    def model_dump(self, mode: str = "python") -> dict[str, Any]:
        return {"id": self.id, "model": self.model, "status": self.status, "usage": self.usage}


class FakeJudge:
    def __init__(self, outputs: list[Any]) -> None:
        self.outputs = list(outputs)
        self.calls: list[dict[str, Any]] = []
        self.responses = SimpleNamespace(create=self._create)

    def _create(self, **request: Any) -> FakeJudgeResponse:
        self.calls.append(copy.deepcopy(request))
        out = self.outputs.pop(0)
        if isinstance(out, Exception):
            raise out
        if isinstance(out, FakeJudgeResponse):
            return out
        return FakeJudgeResponse(out)


def http_error(cls: type, status: int) -> Exception:
    req = httpx2.Request("POST", "https://x")
    return cls("boom", response=httpx2.Response(status, request=req), body=None)


def boom(*a: Any, **k: Any) -> Any:
    raise AssertionError("must not be called in an offline test")


@pytest.fixture(autouse=True)
def offline(monkeypatch: pytest.MonkeyPatch) -> None:
    """No real key, no .env, no real client; the judge prompt read by absolute path."""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setattr(cli, "load_dotenv", boom)
    monkeypatch.setattr(openai, "OpenAI", boom)
    monkeypatch.setattr(scoring, "JUDGE_PROMPT_PATH", JUDGE_PROMPT)


def slot(
    run_id: str,
    case_id: str,
    idx: int,
    text: str | None,
    *,
    status: str = "ok",
    model: str = "gpt-x",
    version: str = "v1",
    returned: str | None = "gpt-x-2026",
) -> dict[str, Any]:
    return {
        "slot_key": make_slot_key(run_id, case_id, version, model, idx),
        "case_id": case_id,
        "prompt_version": version,
        "requested_model": model,
        "returned_model": returned,
        "sample_index": idx,
        "status": status,
        "output_text": text,
        "response_id": "resp_gen",
        # as run_slots writes it: no raw response when the generation call raised
        "raw_response": None if status == "generation_failed" else {"id": "resp_gen"},
    }


def make_run(
    root: Path,
    slots: list[dict[str, Any]],
    *,
    run_id: str = "RID",
    model: str = "gpt-x",
    prompt: str = "prompts/v1.md",
    prompt_text: bytes = b"call prompt",
    cases: tuple[str, ...] = ("C1",),
    samples: int = 1,
) -> Path:
    run_dir, _ = create_run(
        root / "runs",
        run_id,
        InputFile(prompt, prompt_text),
        [InputFile(f"cases/{c}.jsonl", CASE) for c in cases],
        [ModelSpec(model, "openai", {"reasoning_effort": "none"}, {"max_retries": 2})],
        samples,
    )
    (run_dir / "slots.jsonl").write_text(
        "".join(json.dumps(s, ensure_ascii=False) + "\n" for s in slots),
        encoding="utf-8",
        newline="\n",
    )
    return run_dir


def write_notes(root: Path, text: str = NOTES) -> Path:
    path = root / "notes.toml"
    path.write_text(text, encoding="utf-8", newline="\n")
    return path


class Scorer:
    """Runs `score` through the CLI with a fake judge factory."""

    def __init__(self, root: Path, run_dir: Path, notes: Path) -> None:
        self.root = root
        self.run_dir = run_dir
        self.notes = notes
        self.scores_dir = root / "scores"
        self.factory_calls = 0

    def __call__(self, judge: FakeJudge | None) -> int:
        def factory() -> FakeJudge:
            self.factory_calls += 1
            if judge is None:
                raise AssertionError("no judge call was expected")
            return judge

        return cli.main(
            [
                "score", str(self.run_dir),
                "--scores-dir", str(self.scores_dir),
                "--notes", str(self.notes),
            ],
            client_factories={"openai": factory},
        )

    @property
    def records(self) -> list[dict[str, Any]]:
        return scoring.read_score_records(self.scores_dir / "RID.jsonl")


def setup(tmp_path: Path, slots: list[dict[str, Any]], **kw: Any) -> Scorer:
    run_dir = make_run(tmp_path, slots, **kw)
    return Scorer(tmp_path, run_dir, write_notes(tmp_path))


def validated(text: str, reply: str = REPLY) -> scoring.Judgment:
    judgment, errors = scoring.validate_judge_output("completed", text, TURNS, reply)
    assert judgment is not None, errors
    return judgment


# --- decision rule --------------------------------------------------------------

PASSING = scoring.check_structure(REPLY)


def test_all_twos_acceptable() -> None:
    d = scoring.decide(PASSING, validated(judge()))
    assert d.acceptable is True and d.total == 8
    assert d.reasons == [
        "next action 2 (needs 2), grounding 2 (needs 2), listening 2 (needs ≥1), "
        "delivery 2 (needs ≥1); single-turn check passed; no critical violation"
    ]


def test_next_action_one_with_seven_of_eight_is_not_acceptable() -> None:
    d = scoring.decide(PASSING, validated(judge(next_action=1)))
    assert d.total == 7 and d.acceptable is False
    assert d.scores == {
        "next_action": 1, "listening_context": 2, "grounding_role": 2, "spoken_delivery": 2,
    }
    assert d.reasons == [
        "next action scored 1; acceptable needs 2. Judge: Synthetic next action "
        f'rationale. Evidence (reply): "{QUOTE}"'
    ]


@pytest.mark.parametrize(
    ("kw", "total", "reason_start"),
    [
        ({"grounding": 1}, 7, "grounding scored 1; acceptable needs 2."),
        ({"listening": 0}, 6, "listening scored 0; acceptable needs at least 1."),
        ({"delivery": 0}, 6, "delivery scored 0; acceptable needs at least 1."),
    ],
)
def test_each_threshold_fails(kw: dict[str, int], total: int, reason_start: str) -> None:
    d = scoring.decide(PASSING, validated(judge(**kw)))
    assert d.acceptable is False and d.total == total
    assert len(d.reasons) == 1 and d.reasons[0].startswith(reason_start)


def test_listening_one_delivery_one_is_acceptable_at_six() -> None:
    d = scoring.decide(PASSING, validated(judge(listening=1, delivery=1)))
    assert d.acceptable is True and d.total == 6
    assert "listening 1 (needs ≥1), delivery 1 (needs ≥1)" in d.reasons[0]


def test_critical_violation_with_all_twos_fails() -> None:
    cv = {
        "type": "invented_employment_fact",
        "rationale": "Synthetic: states a pay rate.",
        "evidence": [{"source": "reply", "quote": QUOTE}],
    }
    d = scoring.decide(PASSING, validated(judge(critical=[cv])))
    assert d.acceptable is False and d.total == 8
    assert d.reasons == [
        "critical violation invented_employment_fact. Judge: Synthetic: states a pay "
        f'rate. Evidence (reply): "{QUOTE}"'
    ]


def test_structural_failure_with_all_twos_fails() -> None:
    reply = f"Riley: {REPLY}\nApplicant: Yes, both are current."
    structural = scoring.check_structure(reply)
    assert not structural.single_turn_pass
    d = scoring.decide(structural, validated(judge(), reply=reply))
    assert d.acceptable is False and d.total == 8
    assert d.reasons == structural.failures
    assert [r.split(":")[0] for r in d.reasons] == [
        "single-turn rule R1", "single-turn rule R2", "single-turn rule R3", "single-turn rule R4",
    ]


def test_zero_question_marks_with_all_twos_is_acceptable() -> None:
    reply = "Of course, take your time. I can wait while you check BLS and ACLS both current dates."
    structural = scoring.check_structure(reply)
    assert structural.single_turn_pass
    assert "no_question_mark" in structural.diagnostics.flags
    d = scoring.decide(structural, validated(judge(), reply=reply))
    assert d.acceptable is True and d.total == 8


def test_empty_reply_decision() -> None:
    d = scoring.decide(scoring.check_structure("  \n"), None)
    assert d.to_dict() == {
        "acceptable": False,
        "scores": None,
        "total": None,
        "reasons": [scoring.EMPTY_REPLY_REASON],
    }
    assert scoring.EMPTY_REPLY_REASON == "empty completed reply fails the single-turn requirement"


# --- structural checks ----------------------------------------------------------


@pytest.mark.parametrize(
    "reply",
    [
        "Riley: Are you current?\nSam: Yes.",
        "**Riley:** Are you current?\n**Sam:** Yes.",
        "[Riley]: Are you current?\n[Interviewee]: Yes.",
        "Sure. Candidate: yes, both current.",
        "Great question. user: hi",
        "Okay.\nCALLER : yes",
        "Are both current?\nSam: Yes, both.",
        "Are both current?\nNurse: yes",
        "Riley: Are they current? Sam: Yes, both.",
        "Riley: Are both current?\nJos\u00e9: yes",
        "Are both current?\n\u00c9lodie: yes",
    ],
)
def test_both_sides_fail_single_turn(reply: str) -> None:
    assert not scoring.check_structure(reply).single_turn_pass


@pytest.mark.parametrize(
    ("reply", "rules", "label"),
    [
        ("Are both current?\nSam: Yes, both.", ["R4"], '"Sam:"'),
        ("Are both current?\nNurse: yes", ["R1", "R4"], '"Nurse:"'),
        ("Riley: Are they current? Sam: Yes, both.", ["R3"], '"Sam:"'),
        ('Thanks." Caller: yes', ["R1"], '"Caller:"'),
        ("Riley: Hi?\nSam: Yes.", ["R2", "R3", "R4"], '"Riley:", "Sam:"'),
        ("Riley: Are both current?\nJos\u00e9: yes", ["R2", "R3", "R4"], '"Jos\u00e9:"'),
        ("Are both current?\n\u00c9lodie: yes", ["R4"], '"\u00c9lodie:"'),
    ],
)
def test_single_turn_rule_messages(reply: str, rules: list[str], label: str) -> None:
    failures = scoring.check_structure(reply).failures
    assert [f.split(":")[0] for f in failures] == [f"single-turn rule {r}" for r in rules]
    assert any(label in f for f in failures), failures
    assert all(f.endswith("the reply contains both sides of the conversation") for f in failures)


@pytest.mark.parametrize(
    "reply",
    [
        "My next question is: describe a time you advocated for a patient.",
        "Thanks. Here is the second question: describe a time you advocated for a patient.",
        "Riley: Are your BLS and ACLS both current?",  # one label at the start: markup only
        "One question for you as a candidate: are both current?",
        "Thanks, that helps. Here is the second question: describe a time\u2026",
        "My next question is: describe\u2026",
        "Got it. Dr. Smith: is that your charge nurse?",  # a (c) label, not applicant-side
        "Thanks, that’s helpful. Are your BLS and ACLS both current?",
    ],
)
def test_not_both_sides(reply: str) -> None:
    assert scoring.check_structure(reply).single_turn_pass


def test_single_label_at_start_is_markup_only() -> None:
    for reply in ("Riley: Are both current?", "Note: are both current?", "**Riley:** Are both current?"):
        result = scoring.check_structure(reply)
        assert result.single_turn_pass and "markup" in result.diagnostics.flags, reply


def test_diagnostic_flags() -> None:
    long = " ".join(["word"] * 41) + "? And this?"
    flags = scoring.check_structure(long).diagnostics.flags
    assert flags == ["long_reply", "multiple_question_marks"]
    assert scoring.check_structure(" ".join(["w"] * 40) + "?").diagnostics.flags == []
    for marked in [
        "Riley: Are you current?", "<speak>Hi?</speak>", "**Hi?**", "`x`?", "# Hi?",
        "- Are you current?", "1. Are you current?", "[pauses] Are you current?",
        '{"reply": "Hi?"}',
    ]:
        assert "markup" in scoring.check_structure(marked).diagnostics.flags, marked
    d = scoring.check_structure(REPLY).diagnostics
    assert (d.word_count, d.question_marks, d.flags) == (8, 1, [])


def test_committed_ok_replies_pass_single_turn() -> None:
    """Every real saved reply with status ok passes the structural check."""
    files = sorted((REPO / "runs").glob("*/slots.jsonl"))
    assert files, "no committed runs found"
    checked = 0
    for path in files:
        for line in path.read_text(encoding="utf-8").split("\n"):
            if not line.strip():
                continue
            record = json.loads(line)
            if record["status"] != "ok":
                continue
            result = scoring.check_structure(record["output_text"])
            assert result.single_turn_pass, (path, record["output_text"], result.failures)
            assert "markup" not in result.diagnostics.flags, record["output_text"]
            checked += 1
    assert checked == 52  # every ok reply committed as of milestone 3


def test_plan_reads_every_committed_run_and_writes_nothing(tmp_path: Path) -> None:
    """Both manifest schemas (legacy and 2) plan without error; nothing is written."""
    prompt = scoring.load_judge_prompt(JUDGE_PROMPT)
    scores_dir = tmp_path / "scores"
    for run_dir in sorted((REPO / "runs").glob("*/")):
        plan = scoring.plan_scoring(run_dir, scores_dir, REPO / "cases" / "notes.toml", prompt)
        ok = sum(
            1
            for line in (run_dir / "slots.jsonl").read_text(encoding="utf-8").split("\n")
            if line.strip() and json.loads(line)["status"] == "ok"
        )
        assert plan.eligible == ok
    assert not scores_dir.exists()


# --- judge request --------------------------------------------------------------


def test_judge_request_shape_and_input_text() -> None:
    criteria: scoring.Criteria = {
        "expected_action": "Ask whether BLS and ACLS are current.",
        "good_if": ["Acknowledges.", "Asks once."],
        "fail_if": ["Moves on."],
    }
    req = scoring.build_judge_request("JUDGE PROMPT", TURNS[:2], REPLY, criteria)
    assert req == {
        "model": "gpt-5.4-mini",
        "instructions": "JUDGE PROMPT",
        "input": [{"role": "user", "content": req["input"][0]["content"]}],
        "reasoning": {"effort": "none"},
        "max_output_tokens": 1500,
        "text": {
            "format": {
                "type": "json_schema",
                "name": "next_turn_judgment",
                "strict": True,
                "schema": scoring.JUDGMENT_SCHEMA,
            }
        },
    }
    assert req["input"][0]["content"] == (
        "CASE CRITERIA\n"
        "Expected next action: Ask whether BLS and ACLS are current.\n"
        "Good if:\n- Acknowledges.\n- Asks once.\n"
        "Fail if:\n- Moves on.\n"
        "\n"
        "CONVERSATION SO FAR\n"
        "Riley: Hi Sam, this is Riley with Acme Health. Is now a good time?\n"
        "Applicant: Yes, now's fine.\n"
        "\n"
        "REPLY TO EVALUATE (Riley's proposed next turn)\n"
        "<reply>\n"
        f"{REPLY}\n"
        "</reply>"
    )


def test_general_rubric_block() -> None:
    req = scoring.build_judge_request("J", TURNS[:2], REPLY, None)
    assert req["input"][0]["content"].startswith(
        "CASE CRITERIA\nNone for this case. Judge with the general rubric: the call "
        "brief and the conversation only.\n\nCONVERSATION SO FAR\n"
    )


def test_schema_satisfies_openai_strict_mode() -> None:
    objects = 0

    def walk(node: Any) -> None:
        nonlocal objects
        if isinstance(node, dict):
            assert "default" not in node
            if node.get("type") == "object":
                objects += 1
                assert node["additionalProperties"] is False
                assert sorted(node["required"]) == sorted(node["properties"])
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)

    walk(scoring.JUDGMENT_SCHEMA)
    assert objects == 1 + 4 + 4 + 1 + 1  # top, dims, dim evidence, cv, cv evidence
    schema = scoring.JUDGMENT_SCHEMA
    assert list(schema["properties"]) == [*scoring.DIMENSIONS, "critical_violations"]
    for d in scoring.DIMENSIONS:
        dim = schema["properties"][d]
        assert list(dim["properties"]) == ["rationale", "evidence", "score"]
        assert dim["properties"]["score"] == {"type": "integer", "enum": [0, 1, 2]}
    cv = schema["properties"]["critical_violations"]["items"]["properties"]["type"]
    assert cv["enum"] == list(scoring.CRITICAL_TYPES)


# --- validation -----------------------------------------------------------------


def _set_score(d: dict[str, Any], value: Any) -> dict[str, Any]:
    d["next_action"]["score"] = value
    d["next_action"]["evidence"] = [{"source": "reply", "quote": QUOTE}]
    return d


def _invalid_cases() -> list[tuple[str, str, str]]:
    base = judge_dict
    cases: list[tuple[str, str, str]] = []
    for label, value in [("score 3", 3), ('score "2"', "2"), ("score 2.0", 2.0), ("score true", True)]:
        cases.append((label, json.dumps(_set_score(base(), value)), "does not match the schema: next_action.score"))
    missing = base()
    del missing["grounding_role"]
    cases.append(("missing dimension", json.dumps(missing), "grounding_role: Field required"))
    no_ev = base(listening=1)
    no_ev["listening_context"]["evidence"] = []
    cases.append(("score 1 no evidence", json.dumps(no_ev), "listening_context: scored 1 with no evidence"))
    cv = base(critical=[{"type": "promised_hiring_outcome", "rationale": "Synthetic.", "evidence": []}])
    cases.append(("critical no evidence", json.dumps(cv), "critical violation 1 (promised_hiring_outcome): no evidence"))
    invented = base(next_action=1)
    invented["next_action"]["evidence"] = [{"source": "reply", "quote": "your pay is $60 an hour"}]
    cases.append(("invented quote", json.dumps(invented), "quote not found in the reply"))
    ellipsis = base(next_action=1)
    ellipsis["next_action"]["evidence"] = [{"source": "reply", "quote": "Thanks... both current?"}]
    cases.append(("ellipsis quote", json.dumps(ellipsis), "quote not found in the reply"))
    spanning = base(listening=1)
    spanning["listening_context"]["evidence"] = [
        {"source": "transcript", "quote": "Is it okay to continue? Sure, go ahead."}
    ]
    cases.append(("spans two turns", json.dumps(spanning), "not found in any single transcript turn"))
    wrong_source = base(listening=1)
    wrong_source["listening_context"]["evidence"] = [{"source": "transcript", "quote": QUOTE}]
    cases.append(("reply quote claimed as transcript", json.dumps(wrong_source), "not found in any single transcript turn"))
    empty_quote = base(listening=1)
    empty_quote["listening_context"]["evidence"] = [{"source": "reply", "quote": "  "}]
    cases.append(("empty quote", json.dumps(empty_quote), "evidence 1 has an empty quote"))
    empty_rationale = base()
    empty_rationale["spoken_delivery"]["rationale"] = " "
    cases.append(("empty rationale", json.dumps(empty_rationale), "spoken_delivery: rationale is empty"))
    extra = base()
    extra["overall"] = 8
    cases.append(("extra field", json.dumps(extra), "overall: Extra inputs are not permitted"))
    cases.append(("not json", "Score: 2/2, looks good", "not valid JSON"))
    return cases


@pytest.mark.parametrize(("label", "text", "expected"), _invalid_cases(), ids=[c[0] for c in _invalid_cases()])
def test_invalid_judge_output(label: str, text: str, expected: str) -> None:
    judgment, errors = scoring.validate_judge_output("completed", text, TURNS, REPLY)
    assert judgment is None
    assert any(expected in e for e in errors), errors


def test_incomplete_judge_response_is_invalid() -> None:
    judgment, errors = scoring.validate_judge_output("incomplete", judge(), TURNS, REPLY)
    assert judgment is None and errors == ["judge response status is 'incomplete', not 'completed'"]


def test_quote_matching_normalises_quotes_dashes_whitespace_only() -> None:
    reply = "That’s great — thanks.  Are your BLS and ACLS both current?"
    d = judge_dict(listening=1, delivery=1)
    d["listening_context"]["evidence"] = [{"source": "reply", "quote": "That's great - thanks. Are"}]
    # a quote from a single transcript turn, straight apostrophe vs the turn's curly one
    d["spoken_delivery"]["evidence"] = [{"source": "transcript", "quote": "I have BLS and ACLS, and I'd add NIHSS."}]
    judgment, errors = scoring.validate_judge_output("completed", json.dumps(d), TURNS, reply)
    assert errors == [] and judgment is not None
    # matching stays case-sensitive
    d["listening_context"]["evidence"] = [{"source": "reply", "quote": "that's great"}]
    assert scoring.validate_judge_output("completed", json.dumps(d), TURNS, reply)[0] is None


# --- judge prompt pin -----------------------------------------------------------


def test_judge_prompt_hash_is_pinned() -> None:
    raw = JUDGE_PROMPT.read_bytes()
    assert b"\r\n" not in raw
    assert hashlib.sha256(raw).hexdigest() == scoring.JUDGE_PROMPT_SHA256
    assert scoring.load_judge_prompt(JUDGE_PROMPT) == raw.decode("utf-8")


def test_changed_judge_prompt_refused(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    changed = tmp_path / "judge.md"
    changed.write_bytes(JUDGE_PROMPT.read_bytes() + b"\nOne more rule.\n")
    with pytest.raises(scoring.ScoringInputError, match="judge prompt changed"):
        scoring.load_judge_prompt(changed)
    monkeypatch.setattr(scoring, "JUDGE_PROMPT_PATH", changed)
    score = setup(tmp_path, [slot("RID", "C1", 1, REPLY)])
    assert score(None) == 2
    err = capsys.readouterr().err
    assert "judge prompt changed" in err and "Bump JUDGE_PROMPT_VERSION and JUDGE_PROMPT_SHA256" in err
    assert "No judge call was made." in err
    assert score.factory_calls == 0 and not score.scores_dir.exists()


# --- CLI: end to end, exclusions, run folder untouched --------------------------


def test_cli_end_to_end(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    score = setup(
        tmp_path,
        [slot("RID", "C1", 1, REPLY), slot("RID", "C1", 2, f"Got it. {REPLY}")],
        samples=2,
    )
    fake = FakeJudge([judge(next_action=1), judge()])
    assert score(fake) == 0
    out = capsys.readouterr().out
    assert "Plan: 2 eligible replies (status ok): 0 reuse a valid score, 2 need a judge call" in out
    assert "=== CASE C1 ===" in out
    assert "C1 | requested gpt-x / reported gpt-x-2026 | sample 1" in out
    assert f'Reply: "{REPLY}"' in out
    assert "Decision: NOT ACCEPTABLE" in out and "Decision: ACCEPTABLE" in out
    assert "next action scored 1; acceptable needs 2. Judge: Synthetic next action rationale." in out
    assert (
        "Scores: next action 1 · listening 2 · grounding 2 · delivery 2 "
        "· total 7/8"
    ) in out
    assert "total 8/8" in out
    assert f'evidence (reply): "{QUOTE}"' in out
    assert "critical violations: none" in out
    assert "checks: single-turn: pass; words 8; question marks 1; flags: none" in out
    assert "criteria: case notes" in out and "score: new" in out
    assert "Slots: 2 expected, 2 ok replies (0 empty), 0 incomplete, 0 generation failed, 0 missing" in out
    assert "Scores: 1 acceptable, 1 not acceptable, 0 needs review, 0 judge failed" in out
    assert "Judge calls this run: 2 (input tokens 200, output tokens 40)" in out
    recs = score.records
    assert [r["status"] for r in recs] == ["scored", "scored"]
    first = recs[0]
    assert first["decision"]["acceptable"] is False and first["decision"]["total"] == 7
    assert first["judge_response"]["returned_model"] == "gpt-5.4-mini-2026-03-17"
    assert first["judge_response"]["usage_normalized"] == {
        "input_tokens": 100, "output_tokens": 20, "reasoning_tokens": 0,
    }
    assert first["judge_output_text"] == judge(next_action=1)
    req = fake.calls[0]
    assert first["judge_request_sha256"] == scoring.request_sha256(req)
    assert first["text_sha256"] == hashlib.sha256(REPLY.encode()).hexdigest()
    assert first["score_key"] == "|".join(
        [first["slot_key"], first["text_sha256"], "scorer-1", "judge-v1", first["judge_request_sha256"]]
    )
    assert first["judge_model"] == "gpt-5.4-mini"
    assert first["judge_settings"] == {"reasoning_effort": "none", "max_output_tokens": 1500}
    assert first["judge_prompt_sha256"] == scoring.JUDGE_PROMPT_SHA256
    assert first["criteria"]["expected_action"] == "Ask whether BLS and ACLS are current."
    assert set(first["criteria"]) == {"expected_action", "good_if", "fail_if"}
    assert req["instructions"] == JUDGE_PROMPT.read_text(encoding="utf-8")


def test_judge_input_excludes_run_identity_and_blind_material(tmp_path: Path) -> None:
    run_dir = make_run(
        tmp_path,
        [
            slot("RIDSENTINEL", "C1", 1, REPLY, model="gpt-SENTINELMODEL", version="vSENTINEL",
                 returned="gpt-SENTINELRETURNED"),
            slot("RIDSENTINEL", "C1", 2, f"Okay. {REPLY}", model="gpt-SENTINELMODEL",
                 version="vSENTINEL", returned=None),
        ],
        run_id="RIDSENTINEL",
        model="gpt-SENTINELMODEL",
        prompt="prompts/vSENTINEL.md",
        prompt_text=b"PROMPTTEXTSENTINEL",
        samples=2,
    )
    for name in ("blind_key.json", "blind_sheet.md", "label_notes.md", "label_corrections.md"):
        (run_dir / name).write_text(f"SENTINELBLIND {name}\n", encoding="utf-8")
    notes = write_notes(tmp_path)
    fake = FakeJudge([judge(), judge()])
    code = cli.main(
        ["score", str(run_dir), "--scores-dir", str(tmp_path / "scores"), "--notes", str(notes)],
        client_factories={"openai": lambda: fake},
    )
    assert code == 0 and len(fake.calls) == 2
    sentinels = [
        "SENTINEL", "RIDSENTINEL", "gpt-SENTINELMODEL", "SENTINELMODEL", "vSENTINEL",
        "SENTINELRETURNED", "SENTINELBLIND", "PROMPTTEXTSENTINEL", "resp_gen", "sample",
        "SPLITSENTINEL", "TITLESENTINEL", "PAIRSENTINEL", "WHYSENTINEL", "|",
    ]
    for req in fake.calls:
        seen = json.dumps({"instructions": req["instructions"], "input": req["input"]}, ensure_ascii=False)
        for s in sentinels:
            assert s not in seen, s
        assert req["model"] == scoring.JUDGE_MODEL


def test_score_never_opens_blind_or_label_files(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    score = setup(tmp_path, [slot("RID", "C1", 1, REPLY)])
    for name in ("blind_key.json", "blind_sheet.md", "label_notes.md", "label_corrections.md"):
        (score.run_dir / name).write_text("SENTINELBLIND\n", encoding="utf-8")
    opened: list[str] = []
    real_open = io.open

    def spy(file: Any, *a: Any, **k: Any) -> Any:
        opened.append(str(file))
        return real_open(file, *a, **k)

    monkeypatch.setattr(io, "open", spy)
    monkeypatch.setattr(builtins, "open", spy)
    assert score(FakeJudge([judge()])) == 0
    monkeypatch.undo()
    names = {Path(p).name for p in opened}
    assert {"manifest.json", "slots.jsonl", "RID.jsonl"} <= names
    assert not names & {"blind_key.json", "blind_sheet.md", "label_notes.md", "label_corrections.md"}


def _tree(root: Path) -> dict[str, str]:
    return {
        p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(root.rglob("*"))
        if p.is_file()
    }


def test_run_folder_is_byte_identical_and_only_score_file_is_new(tmp_path: Path) -> None:
    score = setup(tmp_path, [slot("RID", "C1", 1, REPLY), slot("RID", "C1", 2, "")], samples=2)
    for name in ("blind_key.json", "blind_sheet.md", "label_notes.md"):
        (score.run_dir / name).write_text("SENTINELBLIND\n", encoding="utf-8")
    before = _tree(tmp_path)
    assert score(FakeJudge([judge()])) == 0
    after = _tree(tmp_path)
    assert set(after) - set(before) == {"scores/RID.jsonl"}
    assert {k: v for k, v in after.items() if k != "scores/RID.jsonl"} == before


# --- reuse and retry ------------------------------------------------------------


def test_second_score_reuses_and_makes_no_call(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    score = setup(tmp_path, [slot("RID", "C1", 1, REPLY), slot("RID", "C1", 2, "")], samples=2)
    assert score(FakeJudge([judge(next_action=1)])) == 0
    capsys.readouterr()
    score.factory_calls = 0
    assert score(None) == 0
    out = capsys.readouterr().out
    assert (
        "2 eligible replies (status ok): 2 reuse a valid score, 0 need a judge call; "
        "1 of them empty" in out
    )
    assert "score: reused" in out and "score: new" not in out
    assert "total 7/8" in out and "Judge calls this run: 0" in out
    assert score.factory_calls == 0 and len(score.records) == 2


def test_reuse_needs_no_api_key(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    score = setup(tmp_path, [slot("RID", "C1", 1, REPLY)])
    assert score(FakeJudge([judge()])) == 0
    # no factories: the real path; load_dotenv and OpenAI are booby-trapped, no key set
    code = cli.main(
        ["score", str(score.run_dir), "--scores-dir", str(score.scores_dir), "--notes", str(score.notes)]
    )
    assert code == 0 and "score: reused" in capsys.readouterr().out


def test_missing_key_when_a_call_is_needed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    score = setup(tmp_path, [slot("RID", "C1", 1, REPLY)])
    loaded: list[bool] = []
    monkeypatch.setattr(cli, "load_dotenv", lambda **k: loaded.append(True))
    code = cli.main(
        ["score", str(score.run_dir), "--scores-dir", str(score.scores_dir), "--notes", str(score.notes)]
    )
    err = capsys.readouterr().err
    assert code == 2 and loaded == [True]
    assert "OPENAI_API_KEY is not set" in err and "No request was made." in err
    assert not score.scores_dir.exists()


def test_changed_reply_text_triggers_new_call(tmp_path: Path) -> None:
    score = setup(tmp_path, [slot("RID", "C1", 1, REPLY)])
    assert score(FakeJudge([judge()])) == 0
    other = make_run(tmp_path / "other", [slot("RID", "C1", 1, f"Okay. {REPLY}")])
    score2 = Scorer(tmp_path, other, score.notes)  # same scores dir, same slot key
    fake = FakeJudge([judge()])
    assert score2(fake) == 0 and len(fake.calls) == 1
    recs = score.records
    assert len(recs) == 2 and recs[0]["slot_key"] == recs[1]["slot_key"]
    assert recs[0]["text_sha256"] != recs[1]["text_sha256"]


def test_changed_judge_request_triggers_new_call(tmp_path: Path) -> None:
    score = setup(tmp_path, [slot("RID", "C1", 1, REPLY)])
    assert score(FakeJudge([judge()])) == 0
    write_notes(tmp_path, NOTES.replace("Moves on without asking.", "Moves on too early."))
    fake = FakeJudge([judge()])
    assert score(fake) == 0 and len(fake.calls) == 1
    recs = score.records
    assert recs[0]["judge_request_sha256"] != recs[1]["judge_request_sha256"]


@pytest.mark.parametrize(
    ("first", "status"),
    [
        ("not json at all", "needs_review"),
        (http_error(openai.RateLimitError, 429), "judge_failed"),
    ],
)
def test_needs_review_and_judge_failed_are_retried(
    tmp_path: Path, first: Any, status: str, capsys: pytest.CaptureFixture[str]
) -> None:
    score = setup(tmp_path, [slot("RID", "C1", 1, REPLY)])
    assert score(FakeJudge([first])) == 1
    out = capsys.readouterr().out
    assert f"Decision: {status.replace('_', ' ').upper()}" in out and "Scores: not judged" in out
    rec = score.records[0]
    assert rec["status"] == status and rec["decision"]["acceptable"] is None
    if status == "needs_review":
        assert rec["judge_output_text"] == "not json at all" and rec["validation_errors"]
    else:
        assert rec["error"]["status_code"] == 429 and rec["judge_response"] is None
    fake = FakeJudge([judge()])
    assert score(fake) == 0 and len(fake.calls) == 1
    assert [r["status"] for r in score.records] == [status, "scored"]
    assert score(None) == 0  # now reused


def test_first_of_several_matching_scored_records_is_used(tmp_path: Path) -> None:
    score = setup(tmp_path, [slot("RID", "C1", 1, REPLY)])
    assert score(FakeJudge([judge()])) == 0
    path = score.scores_dir / "RID.jsonl"
    second = dict(score.records[0], started_at="SECOND")
    with open(path, "a", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(second) + "\n")
    plan = scoring.plan_scoring(score.run_dir, score.scores_dir, score.notes, scoring.load_judge_prompt(JUDGE_PROMPT))
    assert plan.calls_needed == 0 and plan.slots[0].reused is not None
    assert plan.slots[0].reused["started_at"] != "SECOND"


# --- partial, failed, missing, duplicate slots ----------------------------------


def test_partial_failed_missing_and_empty_slots(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    score = setup(
        tmp_path,
        [
            slot("RID", "C1", 1, REPLY),
            slot("RID", "C1", 2, "Are your BL", status="incomplete"),
            slot("RID", "C1", 3, None, status="generation_failed", returned=None),
            # sample 4 missing
            slot("RID", "C1", 5, "  \n"),
        ],
        samples=5,
    )
    fake = FakeJudge([judge()])
    assert score(fake) == 0 and len(fake.calls) == 1
    captured = capsys.readouterr()
    out = captured.out
    assert "2 eligible replies (status ok): 0 reuse a valid score, 1 need a judge call; 1 of them empty" in out
    assert "C1 | requested gpt-x / reported none (no response received) | sample 3" in out
    assert "C1 | requested gpt-x / reported none (no saved record) | sample 4" in out
    assert "Reported model: gpt-x-2026\n" in out  # no 'unconfirmed' for the failed slot
    assert "Not scored: 1 incomplete, 1 generation failed, 1 missing." in out
    assert "reply was incomplete; not scored" in out
    assert "reply failed to generate; not scored" in out
    assert "no saved record for this slot; not scored" in out
    assert scoring.EMPTY_REPLY_REASON in out
    assert "Slots: 5 expected, 2 ok replies (1 empty), 1 incomplete, 1 generation failed, 1 missing" in out
    assert "Scores: 1 acceptable, 1 not acceptable" in out
    assert "Problems found" not in captured.err
    recs = score.records
    assert [r["sample_index"] for r in recs] == [1, 5]
    empty = recs[1]
    assert empty["status"] == "scored"
    assert empty["decision"] == {
        "acceptable": False, "scores": None, "total": None, "reasons": [scoring.EMPTY_REPLY_REASON],
    }
    for key in ("judgment", "judge_output_text", "judge_response", "judge_request_sha256", "judge_model"):
        assert empty[key] is None
    assert empty["score_key"].endswith("|scorer-1|judge-v1|none")
    assert score(None) == 0 and len(score.records) == 2  # the empty record is reused too


def test_ok_reply_without_reported_model_is_unconfirmed(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    score = setup(tmp_path, [slot("RID", "C1", 1, REPLY, returned=None)])
    assert score(FakeJudge([judge()])) == 0
    out = capsys.readouterr().out
    assert "C1 | requested gpt-x / reported served version unconfirmed | sample 1" in out
    assert "Reported model: served version unconfirmed" in out


def test_record_matching_no_expected_slot_exits_1(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    score = setup(
        tmp_path,
        [slot("RID", "C1", 1, REPLY), slot("RID", "C1", 1, REPLY, model="gpt-other")],
    )
    fake = FakeJudge([judge()])
    assert score(fake) == 1 and len(fake.calls) == 1
    err = capsys.readouterr().err
    assert "Problems found" in err
    assert "1 saved record matches no expected reply slot and was ignored." in err
    assert [r["status"] for r in score.records] == ["scored"]


def test_duplicate_slot_records_are_not_scored(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    score = setup(
        tmp_path,
        [slot("RID", "C1", 1, REPLY), slot("RID", "C1", 1, "Different text?"), slot("RID", "C1", 2, REPLY)],
        samples=2,
    )
    fake = FakeJudge([judge()])
    assert score(fake) == 1 and len(fake.calls) == 1
    captured = capsys.readouterr()
    assert "more than one saved record for this slot; not scored" in captured.out
    assert "1 reply slot has more than one saved record and was not scored." in captured.err
    assert [r["sample_index"] for r in score.records] == [2]


# --- judge errors ---------------------------------------------------------------


def test_fatal_judge_error_stops_scoring(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    score = setup(
        tmp_path,
        [slot("RID", "C1", 1, REPLY), slot("RID", "C1", 2, REPLY), slot("RID", "C1", 3, "")],
        samples=3,
    )
    fake = FakeJudge([http_error(openai.AuthenticationError, 401), judge()])
    assert score(fake) == 1 and len(fake.calls) == 1
    captured = capsys.readouterr()
    assert "Scoring stopped after a fatal judge error: AuthenticationError (HTTP 401)" in captured.err
    assert captured.out.count("not scored: scoring stopped after a fatal judge error") == 2
    assert "2 not scored (stopped)" in captured.out
    assert [r["status"] for r in score.records] == ["judge_failed"]


def test_recoverable_judge_error_continues(tmp_path: Path) -> None:
    score = setup(tmp_path, [slot("RID", "C1", 1, REPLY), slot("RID", "C1", 2, REPLY)], samples=2)
    fake = FakeJudge([http_error(openai.InternalServerError, 500), judge()])
    assert score(fake) == 1 and len(fake.calls) == 2
    assert [r["status"] for r in score.records] == ["judge_failed", "scored"]


def test_unclassified_judge_error_propagates(tmp_path: Path) -> None:
    score = setup(tmp_path, [slot("RID", "C1", 1, REPLY)])
    with pytest.raises(RuntimeError):
        score(FakeJudge([RuntimeError("bug")]))


def test_incomplete_judge_response_needs_review(tmp_path: Path) -> None:
    score = setup(tmp_path, [slot("RID", "C1", 1, REPLY)])
    assert score(FakeJudge([FakeJudgeResponse('{"next_action":', status="incomplete")])) == 1
    rec = score.records[0]
    assert rec["status"] == "needs_review" and rec["judge_output_text"] == '{"next_action":'
    assert rec["judge_response"]["status"] == "incomplete"


# --- criteria and input errors --------------------------------------------------


def test_case_without_notes_uses_general_rubric(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    score = setup(tmp_path, [slot("RID", "C9", 1, REPLY)], cases=("C9",))
    fake = FakeJudge([judge()])
    assert score(fake) == 0
    rec = score.records[0]
    assert rec["criteria_source"] == "general rubric" and rec["criteria"] is None
    assert fake.calls[0]["input"][0]["content"].startswith(
        "CASE CRITERIA\nNone for this case. Judge with the general rubric: the call "
        "brief and the conversation only.\n\n"
    )
    assert "criteria: general rubric" in capsys.readouterr().out


@pytest.mark.parametrize(
    ("change", "message"),
    [
        ("no_manifest", "no manifest.json; not a run directory"),
        ("no_notes", "case notes file not found"),
        ("bad_notes", "cannot read case notes"),
        ("notes_missing_field", "[C1] expected_action must be a non-empty string"),
        ("scores_in_run", "the scores directory is a run folder or inside one"),
        ("scores_is_other_run", "the scores directory is a run folder or inside one"),
        ("scores_inside_other_run", "the scores directory is a run folder or inside one"),
        ("scores_is_runs_dir", "the scores directory is a directory of runs"),
        ("scores_new_sibling_in_runs", "which is a directory of runs"),
        ("scores_nested_new_in_runs", "which is a directory of runs"),
        ("scores_existing_sibling_in_scratch_runs", "which is a directory of runs"),
        ("manifest_missing_field", "field samples_per_case is missing or not a positive integer"),
        ("turns_null", "field cases[0].turns is missing or not a list"),
        ("samples_string", "field samples_per_case is missing or not a positive integer"),
        ("manifest_array", "the manifest is not a JSON object"),
        ("slot_without_key", "slots.jsonl:2: slot record has no slot_key string"),
        ("bad_schema", "unsupported schema_version"),
    ],
)
def test_input_errors_exit_2_without_a_call(
    tmp_path: Path, change: str, message: str, capsys: pytest.CaptureFixture[str]
) -> None:
    score = setup(tmp_path, [slot("RID", "C1", 1, REPLY)])
    if change == "no_manifest":
        (score.run_dir / "manifest.json").unlink()
    elif change == "no_notes":
        score.notes.unlink()
    elif change == "bad_notes":
        score.notes.write_text("[C1\n", encoding="utf-8")
    elif change == "notes_missing_field":
        write_notes(tmp_path, NOTES.replace("expected_action", "expected"))
    elif change == "scores_in_run":
        score.scores_dir = score.run_dir / "scores"
    elif change in ("scores_is_other_run", "scores_inside_other_run"):
        other = make_run(tmp_path, [], run_id="OTHER")
        score.scores_dir = other if change == "scores_is_other_run" else other / "sub" / "scores"
    elif change == "scores_is_runs_dir":
        score.scores_dir = tmp_path / "runs"
    elif change == "scores_new_sibling_in_runs":
        score.scores_dir = tmp_path / "runs" / "newsib"
    elif change == "scores_nested_new_in_runs":
        score.scores_dir = tmp_path / "runs" / "a" / "b"
    elif change == "scores_existing_sibling_in_scratch_runs":
        make_run(tmp_path / "scratch", [], run_id="SCRATCHRUN")
        score.scores_dir = tmp_path / "scratch" / "runs" / "sib"
        score.scores_dir.mkdir()
    elif change in ("turns_null", "samples_string", "manifest_array"):
        manifest = json.loads((score.run_dir / "manifest.json").read_text(encoding="utf-8"))
        if change == "turns_null":
            manifest["cases"][0]["turns"] = None
        elif change == "samples_string":
            manifest["samples_per_case"] = "2"
        else:
            manifest = [manifest]
        (score.run_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    elif change == "manifest_missing_field":
        manifest = json.loads((score.run_dir / "manifest.json").read_text(encoding="utf-8"))
        del manifest["samples_per_case"]
        (score.run_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    elif change == "slot_without_key":
        with open(score.run_dir / "slots.jsonl", "a", encoding="utf-8", newline="\n") as fh:
            fh.write(json.dumps({"case_id": "C1", "status": "ok", "output_text": "x"}) + "\n")
    elif change == "bad_schema":
        manifest = json.loads((score.run_dir / "manifest.json").read_text(encoding="utf-8"))
        manifest["schema_version"] = 99
        (score.run_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    assert score(None) == 2
    assert message in capsys.readouterr().err
    assert score.factory_calls == 0
    assert not (tmp_path / "scores").exists() and not (score.run_dir / "scores").exists()
    assert not list((tmp_path / "runs").glob("*.jsonl"))
    assert not list((tmp_path / "runs").glob("*/*/*.jsonl"))
    assert not list(tmp_path.rglob("RID.jsonl"))


def test_default_scores_dir_at_repo_root_is_accepted() -> None:
    # The repo root holds runs/, which is not itself a run folder.
    scoring._check_scores_dir(REPO / "scores")
    scoring._check_scores_dir(Path("scores"))


def test_unreadable_folder_in_the_guard_is_an_input_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Test data: a permission error while checking an ancestor fails closed with a
    # clear input error, not a traceback.
    blocked = tmp_path / "manifest.json"
    real_stat = Path.stat

    def stat(self: Path, *args: Any, **kwargs: Any) -> Any:
        if self == blocked:
            raise PermissionError(13, "Permission denied", str(self))
        return real_stat(self, *args, **kwargs)

    monkeypatch.setattr(Path, "stat", stat)
    with pytest.raises(scoring.ScoringInputError, match="cannot read it to check"):
        scoring._check_scores_dir(tmp_path / "scores")


@pytest.mark.parametrize(
    "content",
    ['{"name": "an extension", "version": "1.0"}', "not json", '["a", "list"]'],
    ids=["other-json-object", "not-json", "json-array"],
)
def test_unrelated_manifest_json_does_not_block_scores_dir(tmp_path: Path, content: str) -> None:
    # Test data: another project's manifest.json is not a run manifest, whether it
    # sits beside the scores directory or in a folder above it.
    (tmp_path / "extension").mkdir()
    (tmp_path / "extension" / "manifest.json").write_text(content, encoding="utf-8")
    (tmp_path / "manifest.json").write_text(content, encoding="utf-8")
    scoring._check_scores_dir(tmp_path / "scores")
    scoring._check_scores_dir(tmp_path / "extension" / "scores")


@pytest.mark.parametrize(
    "raw",
    [
        "{\"status\": \"scored\"}\n".encode("utf-16"),  # saved as UTF-16
        b'{"status": "scored", "slot_key": "caf\xc3',  # truncated mid-character
    ],
    ids=["utf-16", "truncated"],
)
def test_score_file_with_invalid_utf8_exits_2(
    tmp_path: Path, raw: bytes, capsys: pytest.CaptureFixture[str]
) -> None:
    score = setup(tmp_path, [slot("RID", "C1", 1, REPLY)])
    score.scores_dir.mkdir()
    (score.scores_dir / "RID.jsonl").write_bytes(raw)
    assert score(None) == 2
    err = capsys.readouterr().err
    assert "RID.jsonl: score file is not valid UTF-8" in err and "No judge call was made." in err
    assert score.factory_calls == 0


@pytest.mark.parametrize(
    ("corrupt", "problem"),
    [
        (lambda r: r.update(decision=None), "decision is not an object"),
        (lambda r: r["decision"].pop("acceptable"), "decision.acceptable is not true or false"),
        (lambda r: r["decision"].update(total="8"), "decision.total is not an integer"),
        (lambda r: r.update(structural=None), "structural is malformed"),
        (lambda r: r["structural"].update(failures=[1]), "structural is malformed"),
        (lambda r: r["structural"]["diagnostics"].update(flags=[None]), "structural is malformed"),
    ],
    ids=[
        "decision-null", "no-acceptable", "total-string", "structural-null",
        "failures-non-string", "flags-non-string",
    ],
)
def test_corrupt_reusable_record_exits_2_without_rejudging(
    tmp_path: Path, corrupt: Any, problem: str, capsys: pytest.CaptureFixture[str]
) -> None:
    score = setup(tmp_path, [slot("RID", "C1", 1, REPLY)])
    assert score(FakeJudge([judge()])) == 0
    path = score.scores_dir / "RID.jsonl"
    record = score.records[0]
    corrupt(record)
    path.write_text(json.dumps(record) + "\n", encoding="utf-8", newline="\n")
    before = path.read_bytes()
    capsys.readouterr()
    score.factory_calls = 0
    assert score(None) == 2
    err = capsys.readouterr().err
    assert "RID.jsonl:1: the scored record for slot RID|C1|v1|gpt-x|1 can't be reused" in err
    assert problem in err and "The score file is corrupt" in err
    assert score.factory_calls == 0 and path.read_bytes() == before


def test_corrupt_later_record_stops_before_judging_earlier_slots(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # Slot 1 needs a judge call (needs_review last time); slot 2's reusable record is
    # corrupt. Planning must refuse before any call or append, not crash mid-run.
    score = setup(tmp_path, [slot("RID", "C1", 1, REPLY), slot("RID", "C1", 2, REPLY)], samples=2)
    assert score(FakeJudge(["not json", judge()])) == 1
    path = score.scores_dir / "RID.jsonl"
    records = score.records
    assert [r["status"] for r in records] == ["needs_review", "scored"]
    records[1]["structural"]["failures"] = [1]
    path.write_text("".join(json.dumps(r) + "\n" for r in records), encoding="utf-8", newline="\n")
    before = path.read_bytes()
    capsys.readouterr()
    score.factory_calls = 0
    assert score(FakeJudge([judge()])) == 2
    err = capsys.readouterr().err
    assert "RID.jsonl:2: the scored record for slot RID|C1|v1|gpt-x|2 can't be reused" in err
    assert score.factory_calls == 0 and path.read_bytes() == before
