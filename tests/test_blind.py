import hashlib
import json
import shutil
from pathlib import Path
from typing import Any

import openai
import pytest
from test_run import CASE, FakeClient, http_error, make, openai_spec

from rightoncue import cli
from rightoncue.runs import (
    BlindKeyError,
    RunNotReadyError,
    read_slots,
    render_blind,
    run_slots,
)

BASELINE = Path(__file__).parent.parent / "runs" / "20261120T225013Z-70fb30"
FORBIDDEN = (
    "gpt-", "RID", "resp_", "|", "slot_key", "sample_index", "text_sha256",
    "sample 1", "sample 2",
)


def snapshot(run_dir: Path) -> dict[str, bytes]:
    return {p.name: p.read_bytes() for p in sorted(run_dir.iterdir())}


def assert_blind(text: str) -> None:
    for word in FORBIDDEN:
        assert word not in text, word


def append_record(run_dir: Path, record: dict[str, Any]) -> None:
    with open(run_dir / "slots.jsonl", "ab") as fh:
        fh.write((json.dumps(record) + "\n").encode("utf-8"))


def key_of(run_dir: Path, label: str, case: str = "c0") -> str:
    entry = json.loads((run_dir / "blind_key.json").read_text())[case][label]
    return entry["slot_key"] if isinstance(entry, dict) else entry


def frozen_two(tmp_path: Path):
    run_dir, manifest = make(tmp_path, cases=1)
    run_slots({"openai": FakeClient(["alpha-text", "beta-text"])}, run_dir, manifest)
    return run_dir, manifest, render_blind(run_dir)


def test_sheet_bytes_preserved(tmp_path: Path) -> None:
    run_dir, _, first = frozen_two(tmp_path)
    assert first.sheet_status == "created"
    assert first.text.rstrip().endswith("Created blind_sheet.md.")
    sheet = run_dir / "blind_sheet.md"
    with open(sheet, "ab") as fh:
        fh.write("\nPreference: B — zebra-417 tipped it\n".encode("utf-8"))
    before = snapshot(run_dir)
    second = render_blind(run_dir)
    assert snapshot(run_dir) == before
    assert second.sheet_status == "preserved"
    assert "preserved" in second.text
    assert second.problems == []


def test_early_view_refused_then_complete(tmp_path: Path) -> None:
    run_dir, manifest = make(tmp_path, cases=1)
    with pytest.raises(RuntimeError, match="interrupted"):
        run_slots({"openai": FakeClient(["first", RuntimeError("interrupted")])}, run_dir, manifest)
    before = snapshot(run_dir)
    with pytest.raises(RunNotReadyError) as exc:
        render_blind(run_dir)
    assert "c0: 1 of 2 samples recorded" in exc.value.lines
    assert_blind(str(exc.value))
    assert snapshot(run_dir) == before
    assert not (run_dir / "blind_key.json").exists()
    assert not (run_dir / "blind_sheet.md").exists()

    # duplicate record of the same slot does not satisfy the count
    line = (run_dir / "slots.jsonl").read_bytes()
    with open(run_dir / "slots.jsonl", "ab") as fh:
        fh.write(line)
    before = snapshot(run_dir)
    with pytest.raises(RunNotReadyError) as exc:
        render_blind(run_dir)
    assert "c0: 1 of 2 samples recorded" in exc.value.lines
    assert snapshot(run_dir) == before

    client = FakeClient(["second"])
    result = run_slots({"openai": client}, run_dir, manifest)
    assert result.attempted == 1 and result.skipped == 1
    assert read_slots(run_dir)[-1]["sample_index"] == 2
    view = render_blind(run_dir).text
    assert "first" in view and "second" in view


def test_cli_show_refuses_incomplete(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    run_dir, manifest = make(tmp_path, cases=1)
    with pytest.raises(RuntimeError):
        run_slots({"openai": FakeClient(["first", RuntimeError("interrupted")])}, run_dir, manifest)
    before = snapshot(run_dir)
    assert cli.main(["show", str(run_dir)]) == 2
    err = capsys.readouterr().err
    assert "c0: 1 of 2 samples recorded" in err and "Nothing was written." in err
    assert snapshot(run_dir) == before


def test_incomplete_reply(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    run_dir, manifest = make(tmp_path, cases=1)
    inc = {"text": "cut off", "status": "incomplete", "details": {"reason": "max_output_tokens"}}
    result = run_slots({"openai": FakeClient(["good", inc])}, run_dir, manifest)
    assert result.incomplete == 1 and result.failed == 0
    rec = read_slots(run_dir)[1]
    assert rec["status"] == "incomplete"
    assert rec["output_text"] == "cut off" and rec["raw_response"]["status"] == "incomplete"
    assert rec["incomplete_details"] == {"reason": "max_output_tokens"}

    review = render_blind(run_dir)
    assert "good" in review.text and "cut off" not in review.text
    assert "1 of 2 replies was incomplete and is not shown." in review.text
    assert "Only one eligible reply" in review.text
    sheet = (run_dir / "blind_sheet.md").read_text(encoding="utf-8")
    assert "Preference" not in sheet and "Accept B" not in sheet
    assert "Accept A? (y/n):" in sheet
    assert_blind(review.text)


def test_cli_run_exit_codes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def boom(*a: Any, **k: Any) -> Any:
        raise AssertionError("must not be called")

    monkeypatch.setattr(cli, "load_dotenv", boom)
    monkeypatch.setattr(openai, "OpenAI", boom)
    prompt = tmp_path / "v1.md"
    prompt.write_text("prompt", encoding="utf-8")
    case = tmp_path / "c0.jsonl"
    case.write_bytes(CASE)

    def run(outputs: list[Any]) -> int:
        args = [
            "run", "--prompt", str(prompt), "--case", str(case),
            "--samples", "2", "--runs-dir", str(tmp_path / "runs"),
        ]
        return cli.main(args, client_factories={"openai": lambda: FakeClient(outputs)})

    inc = {"text": "cut", "status": "incomplete", "details": {"reason": "max_output_tokens"}}
    assert run(["a", inc]) == 1
    out = capsys.readouterr().out
    assert "Summary: 2 of 2 slots attempted: 1 completed, 1 incomplete, 0 failed" in out
    assert "max_output_tokens" in out

    assert run(["a", "b"]) == 0
    assert "2 completed, 0 incomplete, 0 failed" in capsys.readouterr().out

    assert run(["a", ""]) == 0
    out = capsys.readouterr().out
    assert "had no text" in out and "2 completed" in out

    assert run(["a", http_error(openai.RateLimitError, 429)]) == 1
    assert "Summary: 2 of 2 slots attempted: 1 completed, 0 incomplete, 1 failed" in (
        capsys.readouterr().out
    )


def test_other_status_is_generation_failed(tmp_path: Path) -> None:
    run_dir, manifest = make(tmp_path, cases=1)
    bad = {"text": "partial", "status": "failed"}
    result = run_slots({"openai": FakeClient(["ok", bad])}, run_dir, manifest)
    assert result.failed == 1
    rec = read_slots(run_dir)[1]
    assert rec["status"] == "generation_failed"
    assert rec["error"] == {
        "type": "response_status", "message": "response status 'failed'", "status_code": None
    }
    assert rec["raw_response"] is not None and rec["output_text"] == "partial"
    assert rec["returned_model"] == "gpt-returned-snapshot"


def test_empty_completed_not_eligible(tmp_path: Path) -> None:
    run_dir, manifest = make(tmp_path, cases=1)
    result = run_slots({"openai": FakeClient(["ok", "  "])}, run_dir, manifest)
    assert result.empty == 1 and result.failed == 0
    text = render_blind(run_dir).text
    assert "1 of 2 replies returned no text and is not shown." in text
    assert "REPLY B" not in text


def test_zero_eligible(tmp_path: Path) -> None:
    run_dir, manifest = make(tmp_path, cases=1)
    err = http_error(openai.RateLimitError, 429)
    run_slots({"openai": FakeClient([err, http_error(openai.RateLimitError, 429)])}, run_dir, manifest)
    review = render_blind(run_dir)
    assert "No eligible replies" in review.text
    assert "2 of 2 replies failed to generate" in review.text
    sheet = (run_dir / "blind_sheet.md").read_text(encoding="utf-8")
    assert "Preference" not in sheet and "Accept" not in sheet
    assert json.loads((run_dir / "blind_key.json").read_text()) == {"c0": {}}


def test_later_eligible_reply_not_added(tmp_path: Path) -> None:
    run_dir, manifest = make(tmp_path, cases=1)
    run_slots({"openai": FakeClient(["only-one", http_error(openai.RateLimitError, 429)])}, run_dir, manifest)
    first = render_blind(run_dir)
    assert "REPLY A" in first.text and "REPLY B" not in first.text
    failed = read_slots(run_dir)[1]
    append_record(run_dir, {**failed, "status": "ok", "output_text": "late-text", "error": None})
    before = snapshot(run_dir)
    second = render_blind(run_dir)
    assert "only-one" in second.text and "late-text" not in second.text
    assert "recorded after this review was frozen" in second.text
    assert second.problems
    assert snapshot(run_dir) == before
    key = json.loads((run_dir / "blind_key.json").read_text())
    assert list(key["c0"]) == ["A"]


def test_later_different_text_under_frozen_slot(tmp_path: Path) -> None:
    run_dir, _, first = frozen_two(tmp_path)
    key_a = key_of(run_dir, "A")
    original = next(r["output_text"] for r in read_slots(run_dir) if r["slot_key"] == key_a)
    rec = next(r for r in read_slots(run_dir) if r["slot_key"] == key_a)
    append_record(run_dir, {**rec, "output_text": "replacement-words"})
    before = snapshot(run_dir)
    second = render_blind(run_dir)
    a_block = second.text.split("REPLY A >>>>>>>>")[1].split("END REPLY A")[0]
    assert original in a_block
    assert "replacement-words" not in second.text
    assert any(p.startswith("c0: Reply A:") for p in second.problems)
    assert snapshot(run_dir) == before
    assert_blind(second.text)


def test_tampered_text_is_unverifiable(tmp_path: Path) -> None:
    run_dir, _, first = frozen_two(tmp_path)
    key_a = key_of(run_dir, "A")
    recs = read_slots(run_dir)
    original = next(r["output_text"] for r in recs if r["slot_key"] == key_a)
    for r in recs:
        if r["slot_key"] == key_a:
            r["output_text"] = "mutated-zzz"
    (run_dir / "slots.jsonl").write_text(
        "".join(json.dumps(r) + "\n" for r in recs), encoding="utf-8"
    )
    before = snapshot(run_dir)
    review = render_blind(run_dir)
    assert original not in review.text and "mutated-zzz" not in review.text
    assert "Reply A" in review.text and "can't be found or verified" in review.text
    assert review.problems
    assert snapshot(run_dir) == before
    assert_blind(review.text)


def test_legacy_key_with_existing_sheet(tmp_path: Path) -> None:
    run_dir, _, _ = frozen_two(tmp_path)
    key = json.loads((run_dir / "blind_key.json").read_text())
    legacy = {"c0": {lb: e["slot_key"] for lb, e in key["c0"].items()}}
    (run_dir / "blind_key.json").write_text(json.dumps(legacy, indent=2), encoding="utf-8")
    before = snapshot(run_dir)
    review = render_blind(run_dir)
    assert "saved before text fingerprints" in review.text
    assert review.text.count("saved before text fingerprints") == 1
    assert "alpha-text" in review.text and "beta-text" in review.text
    assert review.problems == []
    assert snapshot(run_dir) == before


def test_legacy_conflicting_text_unverifiable(tmp_path: Path) -> None:
    run_dir, _, _ = frozen_two(tmp_path)
    key = json.loads((run_dir / "blind_key.json").read_text())
    legacy = {"c0": {lb: e["slot_key"] for lb, e in key["c0"].items()}}
    (run_dir / "blind_key.json").write_text(json.dumps(legacy), encoding="utf-8")
    rec = read_slots(run_dir)[0]
    append_record(run_dir, {**rec, "output_text": "different"})
    before = snapshot(run_dir)
    review = render_blind(run_dir)
    assert "different" not in review.text
    assert review.problems
    assert snapshot(run_dir) == before


def test_sheet_without_mapping_is_an_error(tmp_path: Path) -> None:
    run_dir, manifest = make(tmp_path, cases=1)
    run_slots({"openai": FakeClient(["a", "b"])}, run_dir, manifest)
    (run_dir / "blind_sheet.md").write_text("typed", encoding="utf-8")
    before = snapshot(run_dir)
    with pytest.raises(BlindKeyError):
        render_blind(run_dir)
    assert snapshot(run_dir) == before


def test_user_only_transcript(tmp_path: Path) -> None:
    from rightoncue.runs import InputFile, create_run

    only = InputFile("cases/solo.jsonl", b'{"role":"user","utterance":"Yeah, now is fine."}\n')
    run_dir, manifest = create_run(
        tmp_path, "RID", InputFile("prompts/v1.md", b"p"), [only], [openai_spec()], 2
    )
    run_slots({"openai": FakeClient(["x", "y"])}, run_dir, manifest)
    text = render_blind(run_dir).text
    assert "(Riley hasn't spoken yet" in text and "Yeah, now is fine." in text


def test_previous_turn_and_skipped_turns(tmp_path: Path) -> None:
    run_dir, manifest = make(tmp_path, cases=1)
    run_slots({"openai": FakeClient(["x", "y"])}, run_dir, manifest)
    text = render_blind(run_dir).text
    assert "Riley's previous turn:\nHi\nApplicant's last turn:\nHello" in text

    from rightoncue.runs import InputFile, create_run

    raw = (
        b'{"role":"agent","utterance":"Is now ok?"}\n'
        b'{"role":"user","utterance":"umm"}\n{"role":"user","utterance":"yes"}\n'
    )
    run2, m2 = create_run(
        tmp_path / "b", "RID", InputFile("prompts/v1.md", b"p"),
        [InputFile("cases/multi.jsonl", raw)], [openai_spec()], 2,
    )
    run_slots({"openai": FakeClient(["x", "y"])}, run2, m2)
    text2 = render_blind(run2).text
    assert "Is now ok?" in text2
    assert "(1 earlier applicant turn after Riley's last turn is not shown.)" in text2


def test_blindness_across_paths(tmp_path: Path) -> None:
    texts: list[str] = []
    # normal, incomplete, failed, zero eligible, later-eligible, unverifiable, refusal
    d1, m1 = make(tmp_path / "1", cases=1)
    inc = {"text": "cut", "status": "incomplete", "details": {"reason": "max_output_tokens"}}
    run_slots({"openai": FakeClient(["good", inc])}, d1, m1)
    r = render_blind(d1)
    texts += [r.text, *r.problems, (d1 / "blind_sheet.md").read_text(encoding="utf-8")]

    d2, m2 = make(tmp_path / "2", cases=1)
    run_slots({"openai": FakeClient([http_error(openai.RateLimitError, 429)] * 2)}, d2, m2)
    r = render_blind(d2)
    texts += [r.text, *r.problems]

    d3, m3 = make(tmp_path / "3", cases=1)
    run_slots({"openai": FakeClient(["a", http_error(openai.RateLimitError, 429)])}, d3, m3)
    render_blind(d3)
    failed = read_slots(d3)[1]
    append_record(d3, {**failed, "status": "ok", "output_text": "late"})
    r = render_blind(d3)
    texts += [r.text, *r.problems]

    d4, m4, _ = frozen_two(tmp_path / "4")
    key_a = key_of(d4, "A")
    recs = read_slots(d4)
    for rec in recs:
        if rec["slot_key"] == key_a:
            rec["output_text"] = "mutated"
    (d4 / "slots.jsonl").write_text("".join(json.dumps(x) + "\n" for x in recs), encoding="utf-8")
    r = render_blind(d4)
    texts += [r.text, *r.problems]

    d5, m5 = make(tmp_path / "5", cases=1)
    with pytest.raises(RuntimeError):
        run_slots({"openai": FakeClient(["a", RuntimeError("interrupted")])}, d5, m5)
    with pytest.raises(RunNotReadyError) as exc:
        render_blind(d5)
    texts.append(str(exc.value))

    for t in texts:
        assert_blind(t)


def test_baseline_compat(tmp_path: Path) -> None:
    run_dir = tmp_path / "baseline"
    shutil.copytree(BASELINE, run_dir)
    before = snapshot(run_dir)
    review = render_blind(run_dir)
    assert review.problems == []
    assert review.sheet_status == "preserved"
    assert "saved before text fingerprints" in review.text
    assert "Riley's previous turn" in review.text
    assert snapshot(run_dir) == before


def test_later_non_ok_record_under_frozen_slot_is_flagged(tmp_path: Path) -> None:
    run_dir, _, _ = frozen_two(tmp_path)
    key_a = key_of(run_dir, "A")
    rec = next(r for r in read_slots(run_dir) if r["slot_key"] == key_a)
    original = rec["output_text"]
    append_record(run_dir, {**rec, "status": "incomplete", "output_text": "partial-zzz"})
    before = snapshot(run_dir)
    review = render_blind(run_dir)
    a_block = review.text.split("REPLY A >>>>>>>>")[1].split("END REPLY A")[0]
    assert original in a_block and "partial-zzz" not in review.text
    assert any(p.startswith("c0: Reply A:") for p in review.problems)
    assert snapshot(run_dir) == before
    assert_blind(review.text)


def test_single_reply_sheet_uses_shown_letter() -> None:
    from rightoncue.runs import _sheet_fields

    fields = _sheet_fields(["B"])
    assert "Accept B? (y/n):" in fields and not any("Accept A" in f for f in fields)
    assert not any(f.startswith("Preference") for f in fields)


def to_legacy(run_dir: Path) -> None:
    key = json.loads((run_dir / "blind_key.json").read_text())
    legacy = {c: {lb: e["slot_key"] for lb, e in m.items()} for c, m in key.items()}
    (run_dir / "blind_key.json").write_text(json.dumps(legacy, indent=2), encoding="utf-8")


def test_partial_run_in_two_case_run_freezes_nothing(tmp_path: Path) -> None:
    run_dir, manifest = make(tmp_path, cases=2)
    with pytest.raises(RuntimeError):
        run_slots({"openai": FakeClient(["a", "b", "c", RuntimeError("interrupted")])}, run_dir, manifest)
    before = snapshot(run_dir)
    with pytest.raises(RunNotReadyError) as exc:
        render_blind(run_dir)
    assert exc.value.lines == ["c1: 1 of 2 samples recorded"]
    assert snapshot(run_dir) == before


def test_key_and_sheet_agree(tmp_path: Path) -> None:
    run_dir, manifest = make(tmp_path, cases=2)
    run_slots({"openai": FakeClient(["a1", "a2", "b1", "b2"])}, run_dir, manifest)
    render_blind(run_dir)
    key = json.loads((run_dir / "blind_key.json").read_text())
    sheet = (run_dir / "blind_sheet.md").read_text(encoding="utf-8")
    for case, mapping in key.items():
        block = sheet.split(f"=== CASE {case} ===")[1].split("=== CASE")[0]
        assert mapping
        for label, entry in mapping.items():
            body = block.split(f"<<<<<<<< REPLY {label} >>>>>>>>\n")[1].split(
                f"\n<<<<<<<< END REPLY {label}"
            )[0]
            assert hashlib.sha256(body.encode("utf-8")).hexdigest() == entry["text_sha256"]


def test_key_race_is_refused(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import rightoncue.runs as runs_mod

    run_dir, manifest = make(tmp_path, cases=1)
    run_slots({"openai": FakeClient(["alpha-text", "beta-text"])}, run_dir, manifest)
    winner = '{"c0": {"A": "other"}}\n'
    real = runs_mod.json.dumps

    def racing_dumps(obj: Any, *a: Any, **k: Any) -> str:
        # called while building the key to write: another show wins just now
        if isinstance(obj, dict) and "c0" in obj and not (run_dir / "blind_key.json").exists():
            (run_dir / "blind_key.json").write_text(winner, encoding="utf-8")
        return real(obj, *a, **k)

    monkeypatch.setattr(runs_mod.json, "dumps", racing_dumps)
    with pytest.raises(BlindKeyError, match="run show again"):
        render_blind(run_dir)
    monkeypatch.undo()
    assert (run_dir / "blind_key.json").read_text(encoding="utf-8") == winner
    assert not (run_dir / "blind_sheet.md").exists()


def test_following_render_uses_existing_key(tmp_path: Path) -> None:
    run_dir, manifest, first = frozen_two(tmp_path)
    key_bytes = (run_dir / "blind_key.json").read_bytes()
    (run_dir / "blind_sheet.md").unlink()  # crash between key and sheet
    again = render_blind(run_dir)
    assert again.sheet_status == "created" and again.problems == []
    assert (run_dir / "blind_key.json").read_bytes() == key_bytes
    a1 = first.text.split("REPLY A >>>>>>>>")[1].split("END REPLY A")[0]
    a2 = again.text.split("REPLY A >>>>>>>>")[1].split("END REPLY A")[0]
    assert a1 == a2


def test_key_missing_a_case_is_refused(tmp_path: Path) -> None:
    run_dir, manifest = make(tmp_path, cases=2)
    run_slots({"openai": FakeClient(["a", "b", "c", "d"])}, run_dir, manifest)
    render_blind(run_dir)
    key = json.loads((run_dir / "blind_key.json").read_text())
    del key["c1"]
    (run_dir / "blind_key.json").write_text(json.dumps(key), encoding="utf-8")
    (run_dir / "blind_sheet.md").unlink()
    before = snapshot(run_dir)
    with pytest.raises(BlindKeyError):
        render_blind(run_dir)
    assert snapshot(run_dir) == before


def test_cli_show_reopen_and_flagged(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    run_dir, manifest, _ = frozen_two(tmp_path)
    assert cli.main(["show", str(run_dir)]) == 0
    assert "Existing blind_sheet.md preserved; not rewritten." in capsys.readouterr().out
    rec = read_slots(run_dir)[0]
    append_record(run_dir, {**rec, "output_text": "replacement-words"})
    before = snapshot(run_dir)
    assert cli.main(["show", str(run_dir)]) == 1
    captured = capsys.readouterr()
    assert "c0: Reply " in captured.err
    assert snapshot(run_dir) == before


def test_legacy_single_incomplete_record(tmp_path: Path) -> None:
    run_dir, manifest = make(tmp_path, cases=1)
    run_slots({"openai": FakeClient(["good", "other"])}, run_dir, manifest)
    render_blind(run_dir)
    to_legacy(run_dir)
    key_a = key_of(run_dir, "A")
    recs = read_slots(run_dir)
    for r in recs:
        if r["slot_key"] == key_a:
            r["status"] = "incomplete"
    (run_dir / "slots.jsonl").write_text(
        "".join(json.dumps(r) + "\n" for r in recs), encoding="utf-8"
    )
    shown = next(r["output_text"] for r in recs if r["slot_key"] == key_a)
    before = snapshot(run_dir)
    review = render_blind(run_dir)
    assert shown in review.text
    assert any("Reply A: this older review included a reply that was incomplete" in p
               for p in review.problems)
    assert snapshot(run_dir) == before


def test_legacy_ok_then_incomplete_is_unverifiable(tmp_path: Path) -> None:
    run_dir, manifest = make(tmp_path, cases=1)
    run_slots({"openai": FakeClient(["good", "other"])}, run_dir, manifest)
    render_blind(run_dir)
    to_legacy(run_dir)
    key_a = key_of(run_dir, "A")
    rec = next(r for r in read_slots(run_dir) if r["slot_key"] == key_a)
    append_record(run_dir, {**rec, "status": "incomplete", "output_text": "partial-zzz"})
    before = snapshot(run_dir)
    review = render_blind(run_dir)
    assert "REPLY A >>>" not in review.text
    assert "partial-zzz" not in review.text
    assert "originally reviewed words" not in review.text
    assert any("can't be verified" in p for p in review.problems)
    assert snapshot(run_dir) == before


def test_sheet_race_is_refused(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import rightoncue.runs as runs_mod

    run_dir, manifest = make(tmp_path, cases=1)
    run_slots({"openai": FakeClient(["alpha-text", "beta-text"])}, run_dir, manifest)
    sheet = run_dir / "blind_sheet.md"
    other = "sheet written by another show\n"
    real = runs_mod._create_exclusive

    def racing_create(path: Path, content: str) -> None:
        if path == sheet and not sheet.exists():
            sheet.write_text(other, encoding="utf-8")  # another show wins just now
        real(path, content)

    monkeypatch.setattr(runs_mod, "_create_exclusive", racing_create)
    with pytest.raises(BlindKeyError, match="run show again"):
        render_blind(run_dir)
    monkeypatch.undo()
    assert sheet.read_text(encoding="utf-8") == other
    assert (run_dir / "blind_key.json").exists()
    before = snapshot(run_dir)
    again = render_blind(run_dir)
    assert again.sheet_status == "preserved" and again.problems == []
    assert snapshot(run_dir) == before


@pytest.mark.parametrize("content", ["", '{"c0": {"A"', "[]"])
def test_unreadable_key_is_reported_not_rewritten(tmp_path: Path, content: str) -> None:
    run_dir, manifest = make(tmp_path, cases=1)
    run_slots({"openai": FakeClient(["alpha-text", "beta-text"])}, run_dir, manifest)
    (run_dir / "blind_key.json").write_text(content, encoding="utf-8")
    before = snapshot(run_dir)
    with pytest.raises(BlindKeyError, match="empty or unreadable") as info:
        render_blind(run_dir)
    assert snapshot(run_dir) == before
    assert_blind(str(info.value))
