"""rightoncue.review: loading and joining. Offline; the committed runs are read only."""

import json
from pathlib import Path
from typing import Any

import pytest

from rightoncue import review, scoring
from rightoncue.runs import InputFile, ModelSpec, create_run, make_slot_key

REPO = Path(__file__).parent.parent
RUNS = REPO / "runs"
SCORES = REPO / "scores"
V2 = "20261122T024715Z-182705"
V1 = "20261122T024845Z-8babdd"
CASE = b'{"role":"agent","utterance":"Hi"}\n{"role":"user","utterance":"Hello"}\n'


@pytest.fixture(autouse=True)
def offline(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(REPO)  # judge prompt paths are relative to the repository root
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv(review.HOSTED_ENV, raising=False)

    def boom() -> Any:
        raise AssertionError("a real client must not be built in an offline test")

    monkeypatch.setattr(review, "CLIENT_FACTORIES", {"openai": boom, "gemini": boom})


def slot(run_id: str, idx: int, status: str = "ok", text: str | None = "A reply.", **kw: Any) -> dict[str, Any]:
    return {
        "slot_key": make_slot_key(run_id, "C1", "v1", "gpt-x", idx),
        "case_id": "C1",
        "requested_model": "gpt-x",
        "sample_index": idx,
        "status": status,
        "output_text": text,
        "returned_model": "gpt-x-2026" if status != "generation_failed" else None,
        "raw_response": None if status == "generation_failed" else {"id": "r"},
        **kw,
    }


def make_run(tmp_path: Path, slots: list[dict[str, Any]], samples: int = 4) -> Path:
    run_dir, _ = create_run(
        tmp_path / "runs", "RID", InputFile("prompts/v1.md", b"prompt"),
        [InputFile("cases/C1.jsonl", CASE)],
        [ModelSpec("gpt-x", "openai", {"reasoning_effort": "none"}, {})], samples,
    )
    (run_dir / "slots.jsonl").write_text(
        "".join(json.dumps(s) + "\n" for s in slots), encoding="utf-8", newline="\n"
    )
    return run_dir


# --------------------------------------------------------------- committed data


def test_list_scored_runs_only_runs_with_a_score_file() -> None:
    ids = review.list_scored_runs(RUNS, SCORES)
    assert V2 in ids and V1 in ids
    assert "draw-2" not in ids  # a folder, not a score file
    assert all((RUNS / i / "manifest.json").is_file() for i in ids)
    assert ids == sorted(ids, reverse=True)


def test_default_run_judge_versions_and_view() -> None:
    records = scoring.read_score_records(SCORES / f"{V2}.jsonl")
    assert review.judge_versions_in(records) == ["judge-v1"]
    view = review.load_run_view(RUNS / V2, SCORES / f"{V2}.jsonl", "judge-v1")
    assert view.prompt_version == "v2" and view.samples == 2
    assert [m.requested for m in view.models] == ["gpt-5.4", "gpt-5.4-mini", "gemini-3.5-flash"]
    assert view.case_ids == ["H1", "H2", "H3", "H4"]
    cards = view.all_cards()
    assert len(cards) == 24
    assert all(c.state == "reply" and c.decision in ("acceptable", "not acceptable") for c in cards)
    assert all(c.total is not None and c.scores for c in cards)
    assert all(m.reported for m in view.models)


def test_cards_equal_the_scorers_reused_records() -> None:
    judge = scoring.load_judge_prompt("judge-v1")
    plan = scoring.plan_scoring(RUNS / V2, SCORES, review.NOTES_PATH, judge)
    view = review.load_run_view(RUNS / V2, SCORES / f"{V2}.jsonl", "judge-v1")
    by_key = {c.slot_key: c for c in view.all_cards()}
    assert len(plan.slots) == len(by_key) == 24
    for sp in plan.slots:
        assert sp.reused is not None
        card = by_key[sp.slot_key]
        assert card.reply == sp.text
        assert card.total == sp.reused["decision"]["total"]
        assert (card.decision == "acceptable") == sp.reused["decision"]["acceptable"]


def scored_runs() -> list[tuple[str, str]]:
    out = []
    for rid in review.list_scored_runs(RUNS, SCORES):
        recs = scoring.read_score_records(SCORES / f"{rid}.jsonl")
        out += [(rid, v) for v in review.judge_versions_in(recs)]
    return out


@pytest.mark.parametrize("run_id,version", scored_runs())
def test_every_committed_run_and_judge_version_loads(run_id: str, version: str) -> None:
    view = review.load_run_view(RUNS / run_id, SCORES / f"{run_id}.jsonl", version)
    expected = len(view.case_ids) * len(view.models) * view.samples
    assert len(view.all_cards()) == expected
    for c in view.all_cards():
        assert (c.state == "reply") == (c.reply is not None)


def test_unknown_judge_version_is_an_error() -> None:
    with pytest.raises(ValueError, match="judge-v9"):
        review.load_run_view(RUNS / V2, SCORES / f"{V2}.jsonl", "judge-v9")


def test_holdout_join() -> None:
    h = review.load_holdout()
    assert h.run_by_prompt == {"v1": V1, "v2": V2}
    assert (h.headline.individual_agree, h.headline.individual_evaluable) == (31, 47)
    assert (h.headline.pair_exact, h.headline.pair_evaluable) == (2, 12)
    assert len(h.accept_by_slot) == 47 and len(h.pairs) == 12
    assert sum(len(v) for v in h.findings.values()) == 17
    p08 = next(p for p in h.pairs if p.pair_id == "P08")
    assert p08.case == "H3" and p08.preferred == ("gpt-5.4", 1)


def test_annotate_marks_labels_flags_and_the_failed_slot() -> None:
    h = review.load_holdout()
    v1 = review.load_run_view(RUNS / V1, SCORES / f"{V1}.jsonl", "judge-v1")
    v2 = review.load_run_view(RUNS / V2, SCORES / f"{V2}.jsonl", "judge-v1")
    for v in (v1, v2):
        review.annotate_holdout(v, h)
    failed = [c for c in v1.all_cards() if c.operational_failure]
    assert [(c.case_id, c.model, c.sample_index, c.state) for c in failed] == [
        ("H4", "gemini-3.5-flash", 2, "generation_failed")
    ]
    assert failed[0].reply is None and failed[0].human_accept is None
    replies = [c for c in v1.all_cards() + v2.all_cards() if c.state == "reply"]
    assert len(replies) == 47 and all(c.human_accept is not None for c in replies)
    flagged = [c for c in replies if c.violations]
    assert sum(len(c.critical_findings) for c in flagged) == 17
    assert all(len(c.critical_findings) == len(c.violations) for c in flagged)


def test_h3_v2_sample1_default_cards() -> None:
    h = review.load_holdout()
    v = review.load_run_view(RUNS / V2, SCORES / f"{V2}.jsonl", "judge-v1")
    review.annotate_holdout(v, h)
    h3 = next(c for c in v.cases if c.case_id == "H3")
    assert h3.previous_riley and "days" in h3.applicant_last
    assert [cards[0].model for cards in h3.cards.values()] == [m.requested for m in v.models]


def test_parse_review_sheet_rejects_blank_and_duplicate() -> None:
    assert review.parse_review_sheet("Accept H1-01? (y/n): y\nAccept H1-02? (y/n): n\n") == {
        "H1-01": True, "H1-02": False,
    }
    with pytest.raises(ValueError, match="expected y or n"):
        review.parse_review_sheet("Accept H1-01? (y/n): \n")
    with pytest.raises(ValueError, match="more than once"):
        review.parse_review_sheet("Accept H1-01? (y/n): y\nAccept H1-01? (y/n): y\n")


def test_read_doc_and_hosted(monkeypatch: pytest.MonkeyPatch) -> None:
    assert review.read_doc("docs/judge-v1-known-limits.md")
    assert review.read_doc("docs/no-such.md") is None
    assert review.hosted() is False
    monkeypatch.setenv(review.HOSTED_ENV, "1")
    assert review.hosted() is True


# ---------------------------------------------------------------------- fixtures


def test_operational_failures_are_never_replies(tmp_path: Path) -> None:
    rid = "RID"
    run_dir = make_run(
        tmp_path,
        [
            slot(rid, 1),
            slot(rid, 2, status="generation_failed", text=None, error={"type": "RateLimitError", "message": "slow down"}),
            slot(rid, 3, status="incomplete", text="partial words"),
            # sample 4: no record at all
        ],
    )
    view = review.load_run_view(run_dir, None, None)
    cards = view.cases[0].cards["gpt-x"]
    assert [c.state for c in cards] == ["reply", "generation_failed", "incomplete", "missing"]
    assert cards[0].decision == "unscored"
    assert all(c.reply is None for c in cards[1:])
    assert "slow down" in cards[1].note
    assert all(c.operational_failure for c in cards[1:])


def test_duplicate_slot_is_not_shown(tmp_path: Path) -> None:
    run_dir = make_run(tmp_path, [slot("RID", 1), slot("RID", 1, text="Other.")], samples=1)
    card = review.load_run_view(run_dir, None, None).cases[0].cards["gpt-x"][0]
    assert card.state == "duplicate" and card.reply is None


def sha(text: str) -> str:
    import hashlib

    return hashlib.sha256(text.encode()).hexdigest()


def record(key: str, text: str, status: str, version: str = "judge-v1", **kw: Any) -> dict[str, Any]:
    return {"slot_key": key, "text_sha256": sha(text), "judge_prompt_version": version, "status": status, **kw}


def test_pick_score_record_rules() -> None:
    key = "RID|C1|v1|gpt-x|1"
    pending = record(key, "A reply.", "judge_pending")
    review_needed = record(key, "A reply.", "needs_review", n=1)
    first = record(key, "A reply.", "scored", n=2)
    later = record(key, "A reply.", "scored", n=3)
    stale = record(key, "Old words.", "scored", n=4)
    other_version = record(key, "A reply.", "scored", version="judge-v3", n=5)
    pick = review.pick_score_record
    assert pick([pending], key, "A reply.", "judge-v1") is None
    assert pick([pending, review_needed], key, "A reply.", "judge-v1") is review_needed
    assert pick([review_needed, first, later], key, "A reply.", "judge-v1") is first
    assert pick([stale], key, "A reply.", "judge-v1") is None
    assert pick([other_version], key, "A reply.", "judge-v1") is None
    assert pick([other_version], key, "A reply.", "judge-v3") is other_version


def test_card_without_a_scored_record_shows_needs_review(tmp_path: Path) -> None:
    run_dir = make_run(tmp_path, [slot("RID", 1)], samples=1)
    scores = tmp_path / "scores" / "RID.jsonl"
    scores.parent.mkdir()
    key = "RID|C1|v1|gpt-x|1"
    row = record(key, "A reply.", "needs_review", decision={"acceptable": None, "scores": None, "total": None, "reasons": ["quote not found"]})
    scores.write_text(json.dumps(row) + "\n", encoding="utf-8")
    card = review.load_run_view(run_dir, scores, "judge-v1").cases[0].cards["gpt-x"][0]
    assert card.decision == "needs review" and card.reasons == ["quote not found"]
    assert card.scores is None and card.total is None


def test_violations_by_scorer_version() -> None:
    v1 = {"scorer_version": "scorer-1", "judgment": {"critical_violations": [{"type": "promised_hiring_outcome", "rationale": "No promise here."}]}}
    assert [v.type for v in review._violations(v1)] == ["promised_hiring_outcome"]
    entry = {"present": False, "rationale": "", "evidence": []}
    v2 = {"scorer_version": "scorer-2", "judgment": {"critical_violations": {"a": entry, "b": {**entry, "present": True, "rationale": "Yes."}}}}
    assert [v.type for v in review._violations(v2)] == ["b"]
    with pytest.raises(ValueError, match="unknown scorer version"):
        review._violations({"scorer_version": "scorer-9", "judgment": {"critical_violations": []}})


# ----------------------------------------------------------------- generate guards


def test_generate_guards_make_no_client(tmp_path: Path) -> None:
    prompt = review.pasted_prompt("Be Riley.")
    case = review.pasted_case(CASE.decode())
    assert prompt.path == "pasted/prompt.md" and case.path == "pasted/transcript.jsonl"
    with pytest.raises(ValueError, match="OPENAI_API_KEY is not set"):
        review.generate(prompt, case, ["gpt-5.4-mini"], 1, "none", "MINIMAL", runs_dir=tmp_path)
    with pytest.raises(ValueError, match="at least one model"):
        review.generate(prompt, case, [], 1, "none", "MINIMAL", runs_dir=tmp_path)
    with pytest.raises(ValueError, match="samples"):
        review.generate(prompt, case, ["gpt-5.4"], 6, "none", "MINIMAL", runs_dir=tmp_path)
    with pytest.raises(ValueError, match="transcript line 1"):
        review.generate(prompt, review.pasted_case("nope"), ["gpt-5.4"], 1, "none", "MINIMAL", runs_dir=tmp_path)
    with pytest.raises(ValueError, match="prompt is empty"):
        review.generate(review.pasted_prompt("  "), case, ["gpt-5.4"], 1, "none", "MINIMAL", runs_dir=tmp_path)
    assert list(tmp_path.iterdir()) == []


def test_blocked_models_and_call_count(monkeypatch: pytest.MonkeyPatch) -> None:
    assert review.blocked_models(["gpt-5.4", "gemini-3.5-flash"]) == {
        "gpt-5.4": "OPENAI_API_KEY is not set",
        "gemini-3.5-flash": "GEMINI_API_KEY is not set",
    }
    monkeypatch.setenv("OPENAI_API_KEY", "fake")
    assert list(review.blocked_models(["gpt-5.4", "gemini-3.5-flash"])) == ["gemini-3.5-flash"]
    assert review.generation_calls(["a", "b", "c"], 2) == 6
    assert review.transcript_error('{"role":"agent","utterance":"Hi"}') == "line 1: last turn must be from 'user'"
    assert review.transcript_error(CASE.decode()) is None
