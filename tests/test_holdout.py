"""Holdout blind-review tooling tests. Fully offline: fake runs, fake score files.

All runs, replies and score records below are SYNTHETIC TEST DATA.
"""

from __future__ import annotations

import hashlib
import json
import random
import re
from pathlib import Path
from typing import Any

import openai
import pytest

from rightoncue import cli, gemini, holdout
from rightoncue.runs import InputFile, ModelSpec, create_run, make_slot_key

M1, M2, M3 = "gpt-5.4", "gpt-5.4-mini", "gemini-3.5-flash"
MODELS = [M1, M2, M3]
CASES4 = ["H1", "H2", "H3", "H4"]
RUN_V1 = "QX-ALPHA-RUN"
RUN_V2 = "QX-BRAVO-RUN"
CASE = (
    b'{"role":"agent","utterance":"Hi Sam, Riley here from Acme. Is now a good time?"}\n'
    b'{"role":"user","utterance":"Yes, go ahead."}\n'
)
CASE_OTHER = (
    b'{"role":"agent","utterance":"Hi Sam, Riley here from Acme. Is now a good time?"}\n'
    b'{"role":"user","utterance":"Actually, can we keep it short?"}\n'
)
CHOICE = "Choice (A / B / tie):"


def boom(*a: Any, **k: Any) -> Any:
    raise AssertionError("must not be called in an offline test")


@pytest.fixture(autouse=True)
def offline(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.setattr(cli, "load_dotenv", boom)
    monkeypatch.setattr(openai, "OpenAI", boom)


# ------------------------------------------------------------------ fixtures


def reply_text(run_id: str, case: str, model: str, idx: int) -> str:
    """Opaque, unique and free of model names, run IDs, versions and 'sample'."""
    r = {RUN_V1: "alpha", RUN_V2: "bravo"}.get(run_id, "charlie")
    return f"Reply {r} {case.lower()} m{MODELS.index(model) + 1}x{idx}: when could you start?"


def sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def spec(model: str) -> ModelSpec:
    if model.startswith("gemini-"):
        return ModelSpec(model, "gemini", {"thinking_level": "MINIMAL"}, gemini.client_settings())
    return ModelSpec(model, "openai", {"reasoning_effort": "none"}, {"max_retries": 2})


def slot(run_id: str, case: str, version: str, model: str, idx: int, **over: Any) -> dict[str, Any]:
    rec = {
        "slot_key": make_slot_key(run_id, case, version, model, idx),
        "case_id": case,
        "prompt_version": version,
        "requested_model": model,
        "sample_index": idx,
        "status": "ok",
        "output_text": reply_text(run_id, case, model, idx),
        "raw_response": {"id": "resp_gen"},
    }
    rec.update(over)
    return rec


def make_run(
    root: Path,
    run_id: str,
    version: str,
    cases: list[str] = CASES4,
    *,
    case_bytes: dict[str, bytes] | None = None,
    drop: set[tuple[str, str, int]] = frozenset(),  # type: ignore[assignment]
    override: dict[tuple[str, str, int], dict[str, Any]] | None = None,
    extra: list[dict[str, Any]] | None = None,
) -> Path:
    run_dir, _ = create_run(
        root / "runs",
        run_id,
        InputFile(f"prompts/{version}.md", b"call prompt"),
        [InputFile(f"cases/holdout/{c}.jsonl", (case_bytes or {}).get(c, CASE)) for c in cases],
        [spec(m) for m in MODELS],
        2,
    )
    records = []
    for c in cases:
        for m in MODELS:
            for i in (1, 2):
                if (c, m, i) in drop:
                    continue
                records.append(slot(run_id, c, version, m, i, **(override or {}).get((c, m, i), {})))
    records += extra or []
    (run_dir / "slots.jsonl").write_text(
        "".join(json.dumps(r) + "\n" for r in records), encoding="utf-8", newline="\n"
    )
    return run_dir


def tree(root: Path) -> dict[str, bytes]:
    return {p.relative_to(root).as_posix(): p.read_bytes() for p in sorted(root.rglob("*")) if p.is_file()}


def all_output(capsys: pytest.CaptureFixture[str]) -> str:
    cap = capsys.readouterr()
    return cap.out + cap.err


def assert_no_model_names(text: str) -> None:
    for name in (*MODELS, "gpt-", "gemini-"):
        assert name not in text, name


def plan_cli(tmp_path: Path, cases: list[str] = CASES4, models: list[str] = MODELS) -> list[str]:
    args = ["pair-plan", "--prompt-version", "v2",
            "--private-out", str(tmp_path / "secret" / "plan.json"),
            "--commitment-out", str(tmp_path / "public" / "plan_commitment.json")]
    for c in cases:
        args += ["--case", c]
    for m in models:
        args += ["--model", m]
    return args


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: Any) -> None:
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8", newline="\n")


# ------------------------------------------------------------------ pair plan


def first_named(pair: dict[str, Any]) -> tuple[tuple[str, int], tuple[str, int], bool]:
    """((first model, sample), (second model, sample), first is on the left)."""
    left = (pair["left"]["model"], pair["left"]["sample"])
    right = (pair["right"]["model"], pair["right"]["sample"])
    order = {M1: 0, M2: 1, M3: 2}
    if order[left[0]] < order[right[0]]:
        return left, right, True
    return right, left, False


@pytest.mark.parametrize("seed", range(25))
def test_pair_plan_sample_rule_balance_and_ids(seed: int) -> None:
    plan = holdout.make_pair_plan(CASES4, MODELS, "v2", rng=random.Random(seed))
    assert plan["prompt_version"] == "v2" and plan["models"] == MODELS and plan["cases"] == CASES4
    pairs = plan["pairs"]
    assert len(pairs) == 12
    assert [p["pair_id"] for p in pairs] == [f"P{n:02d}" for n in range(1, 13)]
    assert [p["case"] for p in pairs] == [c for c in CASES4 for _ in range(3)]
    expected = {((M1, 1), (M2, 1)), ((M1, 2), (M3, 1)), ((M2, 2), (M3, 2))}
    left_counts = {e: 0 for e in expected}
    for case in CASES4:
        in_case = [p for p in pairs if p["case"] == case]
        got = set()
        for p in in_case:
            first, second, on_left = first_named(p)
            got.add((first, second))
            left_counts[(first, second)] += on_left
        assert got == expected
        # every (model, sample) appears exactly once per case
        used = [(p[s]["model"], p[s]["sample"]) for p in in_case for s in ("left", "right")]
        assert sorted(used) == sorted((m, i) for m in MODELS for i in (1, 2))
    assert all(n == 2 for n in left_counts.values()), left_counts


def test_pair_plan_default_rng_varies_placement() -> None:
    seen = {
        json.dumps(holdout.make_pair_plan(CASES4, MODELS, "v2")["pairs"]) for _ in range(30)
    }
    assert len(seen) > 1


@pytest.mark.parametrize(
    ("cases", "models", "message"),
    [
        (["H1", "H2", "H3"], MODELS, "even number of cases"),
        (["H1"], MODELS, "even number of cases"),
        (CASES4, MODELS[:2], "exactly three models"),
        (CASES4, [*MODELS, "gpt-5.5"], "exactly three models"),
        (CASES4, [M1, M1, M3], "more than once"),
        (["H1", "H1"], MODELS, "more than once"),
        (CASES4, [M1, M2, "claude-x"], "unknown model"),
    ],
)
def test_pair_plan_input_errors_exit_2_and_write_nothing(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], cases: list[str], models: list[str], message: str
) -> None:
    assert cli.main(plan_cli(tmp_path, cases, models)) == 2
    assert message in capsys.readouterr().err
    assert tree(tmp_path) == {}


def test_pair_plan_cli_files_commitment_and_quiet_output(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert cli.main(plan_cli(tmp_path)) == 0
    out = all_output(capsys)
    private = read_json(tmp_path / "secret" / "plan.json")
    commitment = read_json(tmp_path / "public" / "plan_commitment.json")
    salt = private["salt"]
    assert private["schema"] == "pair-plan-1" and re.fullmatch(r"[0-9a-f]{64}", salt)
    # output: only the two paths and the hash
    assert salt not in out
    assert_no_model_names(out)
    assert "left" not in out and "right" not in out and "P01" not in out
    assert commitment["sha256"] in out
    assert out.count("\n") == 3
    # commitment: no mapping, no salt; the hash is the documented formula
    assert set(commitment) == {
        "schema", "algorithm", "sha256", "prompt_version", "models", "cases",
        "pair_rule", "created_at",
    }
    raw_commitment = (tmp_path / "public" / "plan_commitment.json").read_text(encoding="utf-8")
    assert salt not in raw_commitment and '"left"' not in raw_commitment
    assert '"pair_id"' not in raw_commitment and '"pairs"' not in raw_commitment
    canonical = json.dumps(private["plan"], sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    import hashlib

    assert commitment["sha256"] == hashlib.sha256((salt + "\n" + canonical).encode("utf-8")).hexdigest()
    # files: LF, no BOM
    for p in (tmp_path / "secret" / "plan.json", tmp_path / "public" / "plan_commitment.json"):
        raw = p.read_bytes()
        assert not raw.startswith(b"\xef\xbb\xbf") and b"\r\n" not in raw
    # verify-commitment
    args = ["verify-commitment", "--private", str(tmp_path / "secret" / "plan.json"),
            "--commitment", str(tmp_path / "public" / "plan_commitment.json")]
    assert cli.main(args) == 0
    out = all_output(capsys)
    assert "commitment verified" in out and salt not in out
    assert_no_model_names(out)


def _tamper_salt(private: dict[str, Any]) -> None:
    private["salt"] = ("0" if private["salt"][0] != "0" else "1") + private["salt"][1:]


def _swap_sides(private: dict[str, Any]) -> None:
    p = private["plan"]["pairs"][0]
    p["left"], p["right"] = p["right"], p["left"]


@pytest.mark.parametrize("tamper", [_tamper_salt, _swap_sides])
def test_tampered_plan_fails_verification_without_leaking(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], tamper: Any
) -> None:
    assert cli.main(plan_cli(tmp_path)) == 0
    capsys.readouterr()
    path = tmp_path / "secret" / "plan.json"
    private = read_json(path)
    tamper(private)
    write_json(path, private)
    args = ["verify-commitment", "--private", str(path),
            "--commitment", str(tmp_path / "public" / "plan_commitment.json")]
    assert cli.main(args) == 1
    out = all_output(capsys)
    assert "NOT verified" in out and "commitment verified" not in out
    assert private["salt"] not in out
    assert_no_model_names(out)


def test_verify_commitment_metadata_and_schema_mismatch(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert cli.main(plan_cli(tmp_path)) == 0
    com_path = tmp_path / "public" / "plan_commitment.json"
    commitment = read_json(com_path)
    commitment["cases"] = ["H1", "H2", "H3", "H9"]
    bad = tmp_path / "public" / "bad.json"
    write_json(bad, commitment)
    private = str(tmp_path / "secret" / "plan.json")
    assert cli.main(["verify-commitment", "--private", private, "--commitment", str(bad)]) == 1
    assert "cases does not match" in capsys.readouterr().err
    commitment = read_json(com_path)
    commitment["schema"] = holdout.REVIEW_COMMITMENT_SCHEMA
    other = tmp_path / "public" / "other.json"
    write_json(other, commitment)
    assert cli.main(["verify-commitment", "--private", private, "--commitment", str(other)]) == 1
    assert "schema mismatch" in capsys.readouterr().err
    # a commitment passed as the private file
    assert cli.main(["verify-commitment", "--private", str(com_path), "--commitment", str(com_path)]) == 1
    assert "schema mismatch" in capsys.readouterr().err


def test_pair_plan_write_once(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert cli.main(plan_cli(tmp_path)) == 0
    before = tree(tmp_path)
    assert cli.main(plan_cli(tmp_path)) == 2
    assert "refusing to overwrite" in capsys.readouterr().err
    assert tree(tmp_path) == before
    # only the commitment exists: the private file is not created either
    (tmp_path / "secret" / "plan.json").unlink()
    before = tree(tmp_path)
    assert cli.main(plan_cli(tmp_path)) == 2
    assert tree(tmp_path) == before


def test_pair_plan_refuses_output_inside_runs(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    run_dir = make_run(tmp_path, RUN_V2, "v2")
    args = plan_cli(tmp_path)
    args[args.index("--private-out") + 1] = str(run_dir / "plan.json")
    before = tree(tmp_path)
    assert cli.main(args) == 2
    assert "inside a run folder" in capsys.readouterr().err
    assert tree(tmp_path) == before
    args[args.index("--private-out") + 1] = str(tmp_path / "runs" / "plan.json")
    assert cli.main(args) == 2
    assert "directory of runs" in capsys.readouterr().err
    assert tree(tmp_path) == before


# ---------------------------------------------------------------- review sheet


def review_cli(tmp_path: Path, run_a: Path, run_b: Path) -> list[str]:
    return ["review-sheet", "--run", str(run_a), "--run", str(run_b),
            "--out", str(tmp_path / "review"), "--private-key", str(tmp_path / "secret" / "review_key.json")]


def two_runs(tmp_path: Path, cases: list[str] = CASES4) -> tuple[Path, Path]:
    return make_run(tmp_path, RUN_V1, "v1", cases), make_run(tmp_path, RUN_V2, "v2", cases)


def unrender(block: str) -> str:
    """The raw text of a rendered reply block ("> " stripped); "" for (empty reply)."""
    if block == "(empty reply)":
        return ""
    lines = block.split("\n")
    assert all(line == "" or line.startswith("> ") for line in lines), block
    return "\n".join(line[2:] for line in lines)


def reply_blocks(sheet: str) -> dict[str, str]:
    return {
        m.group(1): unrender(m.group(2))
        for m in re.finditer(
            r"<<<<<<<< REPLY (\S+) >>>>>>>>\n(.*?)\n<<<<<<<< END REPLY \1 >>>>>>>>", sheet, re.S
        )
    }


def test_review_sheet_contents_key_and_quiet_output(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    run_a, run_b = two_runs(tmp_path)
    runs_before = tree(tmp_path / "runs")
    assert cli.main(review_cli(tmp_path, run_a, run_b)) == 0
    out = all_output(capsys)
    assert tree(tmp_path / "runs") == runs_before
    sheet_path = tmp_path / "review" / "review_sheet.md"
    sheet = sheet_path.read_text(encoding="utf-8")
    raw = sheet_path.read_bytes()
    assert not raw.startswith(b"\xef\xbb\xbf") and b"\r" not in raw
    blocks = reply_blocks(sheet)
    assert len(blocks) == 48
    for case in CASES4:
        ids = [i for i in blocks if i.startswith(f"{case}-")]
        assert sorted(ids) == [f"{case}-{n:02d}" for n in range(1, 13)]
        for n in range(1, 13):
            assert f"Accept {case}-{n:02d}? (y/n):" in sheet
        assert f"=== CASE {case} ===" in sheet
    assert sheet.count("Notes (optional):") == 4
    assert "Riley's previous turn:" in sheet and "Applicant's last turn:" in sheet
    texts = [reply_text(r, c, m, i) for r in (RUN_V1, RUN_V2) for c in CASES4 for m in MODELS for i in (1, 2)]
    for t in texts:
        assert sheet.count(t) == 1, t
        assert f"\n> {t}\n" in sheet  # rendered with the reply prefix
    for word in (*MODELS, "gpt", "gemini", "openai", RUN_V1, RUN_V2, "v1", "v2", "sample", "|",
                 "slot", "score", "criteria"):
        assert word not in sheet.lower() if word.islower() else word not in sheet, word
    # the key: every slot once, fingerprints match the words under each ID
    key_path = tmp_path / "secret" / "review_key.json"
    key = read_json(key_path)
    assert key["schema"] == "review-key-2" and key["unavailable"] == []
    entries = key["entries"]
    assert set(entries) == set(blocks)
    expected_keys = {
        make_slot_key(r, c, v, m, i)
        for r, v in ((RUN_V1, "v1"), (RUN_V2, "v2")) for c in CASES4 for m in MODELS for i in (1, 2)
    }
    assert sorted(e["slot_key"] for e in entries.values()) == sorted(expected_keys)
    import hashlib

    for rid, e in entries.items():
        assert e["text_sha256"] == hashlib.sha256(blocks[rid].encode("utf-8")).hexdigest()
        assert blocks[rid] == reply_text(e["run_id"], rid[:2], e["model"], e["sample_index"])
    # commitment: no mapping
    com_path = tmp_path / "review" / "review_key_commitment.json"
    com = read_json(com_path)
    assert set(com) == {
        "schema", "algorithm", "sha256", "run_ids", "case_ids", "n_replies", "ids",
        "unavailable", "created_at",
    }
    assert com["n_replies"] == 48 and com["run_ids"] == [RUN_V1, RUN_V2] and com["case_ids"] == CASES4
    assert sorted(com["ids"]) == sorted(blocks) and com["unavailable"] == {"failed": 0, "incomplete": 0}
    raw_com = com_path.read_text(encoding="utf-8")
    assert key["salt"] not in raw_com
    assert "slot_key" not in raw_com and "|" not in raw_com and "text_sha256" not in raw_com
    assert_no_model_names(raw_com)
    assert f"Review key commitment: {com['sha256']}" in sheet
    # stdout/stderr: paths, counts, hash only
    assert key["salt"] not in out
    assert_no_model_names(out)
    assert "H1-01" not in out and "|" not in out
    assert "replies shown: 48 across 4 cases" in out and com["sha256"] in out
    assert "replies not shown (operational failures): 0" in out
    # verify-commitment for a review key
    assert cli.main(["verify-commitment", "--private", str(key_path), "--commitment", str(com_path)]) == 0
    out = all_output(capsys)
    assert "commitment verified" in out and key["salt"] not in out
    assert_no_model_names(out)
    # tampering with one entry breaks it
    entries_list = list(entries)
    entries[entries_list[0]], entries[entries_list[1]] = entries[entries_list[1]], entries[entries_list[0]]
    write_json(key_path, key)
    assert cli.main(["verify-commitment", "--private", str(key_path), "--commitment", str(com_path)]) == 1
    out = all_output(capsys)
    assert key["salt"] not in out
    assert_no_model_names(out)


@pytest.mark.parametrize(
    ("kind", "kw"),
    [
        ("missing", {"drop": {("H2", M2, 2)}}),
        ("unknown status", {"override": {("H2", M2, 2): {"status": "weird"}}}),
        ("malformed", {"override": {("H2", M2, 2): {"output_text": None}}}),
        ("duplicate", {"extra": [slot(RUN_V2, "H2", "v2", M2, 2, output_text="other words")]}),
        ("no expected slot", {"extra": [slot(RUN_V2, "H9", "v2", M2, 2)]}),
    ],
)
def test_review_sheet_refuses_integrity_problems(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], kind: str, kw: dict[str, Any]
) -> None:
    run_a = make_run(tmp_path, RUN_V1, "v1")
    run_b = make_run(tmp_path, RUN_V2, "v2", **kw)
    before = tree(tmp_path)
    assert cli.main(review_cli(tmp_path, run_a, run_b)) == 2
    err = all_output(capsys)
    assert kind in err and RUN_V2 in err and "Nothing was written." in err
    assert_no_model_names(err)
    assert tree(tmp_path) == before


def test_review_sheet_refuses_mismatched_transcripts_and_cases(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    run_a = make_run(tmp_path, RUN_V1, "v1")
    run_b = make_run(tmp_path, RUN_V2, "v2", case_bytes={"H3": CASE_OTHER})
    before = tree(tmp_path)
    assert cli.main(review_cli(tmp_path, run_a, run_b)) == 2
    assert "case H3: the transcript turns differ" in capsys.readouterr().err
    assert tree(tmp_path) == before
    run_c = make_run(tmp_path, "QX-CHARLIE-RUN", "v2", ["H1", "H2"])
    before = tree(tmp_path)
    assert cli.main(review_cli(tmp_path, run_a, run_c)) == 2
    assert "different case IDs" in capsys.readouterr().err
    assert cli.main(review_cli(tmp_path, run_a, run_a)) == 2
    assert "same run" in capsys.readouterr().err
    assert tree(tmp_path) == before


def test_review_sheet_write_once(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    run_a, run_b = two_runs(tmp_path, ["H1", "H2"])
    assert cli.main(review_cli(tmp_path, run_a, run_b)) == 0
    before = tree(tmp_path)
    assert cli.main(review_cli(tmp_path, run_a, run_b)) == 2
    assert "refusing to overwrite" in capsys.readouterr().err
    assert tree(tmp_path) == before
    # a different key path, same out dir: the sheet and commitment still block it
    args = review_cli(tmp_path, run_a, run_b)
    args[-1] = str(tmp_path / "secret" / "key2.json")
    assert cli.main(args) == 2
    assert tree(tmp_path) == before


def test_review_sheet_refuses_out_inside_runs(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    run_a, run_b = two_runs(tmp_path, ["H1", "H2"])
    args = review_cli(tmp_path, run_a, run_b)
    args[args.index("--out") + 1] = str(run_b / "review")
    before = tree(tmp_path)
    assert cli.main(args) == 2
    assert "inside a run folder" in capsys.readouterr().err
    assert tree(tmp_path) == before


# ------------------------------------------------------------------ pair sheet


def make_plan_files(tmp_path: Path, plan: dict[str, Any], salt: str = "ab" * 32) -> tuple[Path, Path]:
    """A private plan and commitment for a hand-built plan, in the module's format."""
    private = tmp_path / "secret" / "plan.json"
    com = tmp_path / "public" / "plan_commitment.json"
    private.parent.mkdir(parents=True, exist_ok=True)
    com.parent.mkdir(parents=True, exist_ok=True)
    write_json(private, {"schema": "pair-plan-1", "salt": salt, "plan": plan})
    write_json(com, {
        "schema": "pair-plan-commitment-1",
        "algorithm": holdout.PAIR_ALGORITHM,
        "sha256": holdout.commitment_hash(salt, plan),
        "prompt_version": plan["prompt_version"],
        "models": plan["models"],
        "cases": plan["cases"],
        "pair_rule": holdout.PAIR_RULE,
        "created_at": "2026-11-21T00:00:00+00:00",
    })
    return private, com


def generated_plan(tmp_path: Path, cases: list[str] = CASES4) -> tuple[Path, Path, dict[str, Any]]:
    private = tmp_path / "secret" / "plan.json"
    com = tmp_path / "public" / "plan_commitment.json"
    holdout.create_pair_plan(cases, MODELS, "v2", private, com)
    return private, com, read_json(private)["plan"]


def fill_labels(sheet: Path, value: Any) -> None:
    """Write value(ID) after every Accept line outside reply blocks."""
    lines = sheet.read_text(encoding="utf-8").split("\n")
    in_reply = False
    for i, line in enumerate(lines):
        if line.startswith("<<<<<<<< REPLY "):
            in_reply = True
        elif line.startswith("<<<<<<<< END REPLY "):
            in_reply = False
            continue
        if in_reply:
            continue
        m = re.match(r"^(Accept (\S+)\? \(y/n\):).*$", line)
        if m:
            lines[i] = m.group(1) + " " + value(m.group(2))
    sheet.write_text("\n".join(lines), encoding="utf-8", newline="\n")


def labelled_review(root: Path, run_a: Path, run_b: Path, label: str = "y") -> tuple[Path, Path]:
    """Create the combined review sheet for two runs and label every reply."""
    res = holdout.create_review_sheet([run_a, run_b], root / "review", root / "secret" / "review_key.json")
    fill_labels(res.sheet, lambda rid: label)
    return res.sheet, res.commitment


def pair_sheet_cli(
    private: Path, com: Path, run: Path, out: Path, review: Path, review_com: Path
) -> list[str]:
    return ["pair-sheet", "--plan-private", str(private), "--commitment", str(com),
            "--run", str(run), "--out", str(out),
            "--review-sheet", str(review), "--review-commitment", str(review_com)]


def side_block(label: str, text: str) -> str:
    return f"<<<<<<<< {label} >>>>>>>>\n> {text}\n<<<<<<<< END {label} >>>>>>>>\n"


def test_pair_sheet_texts_match_plan_and_hide_models(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    run_a, run = two_runs(tmp_path)
    review, review_com = labelled_review(tmp_path, run_a, run)
    private, com, plan = generated_plan(tmp_path)
    runs_before = tree(tmp_path / "runs")
    assert cli.main(pair_sheet_cli(private, com, run, tmp_path / "pairs", review, review_com)) == 0
    out = all_output(capsys)
    assert tree(tmp_path / "runs") == runs_before
    sheet = (tmp_path / "pairs" / "pair_sheet.md").read_text(encoding="utf-8")
    for pair in plan["pairs"]:
        left = reply_text(RUN_V2, pair["case"], pair["left"]["model"], pair["left"]["sample"])
        right = reply_text(RUN_V2, pair["case"], pair["right"]["model"], pair["right"]["sample"])
        block = (
            f"=== PAIR {pair['pair_id']} ===\n{side_block('A', left)}\n{side_block('B', right)}\n"
            f"Fingerprint: {holdout.pair_fingerprint(left, right)}\n{CHOICE}\nReason:\n"
        )
        assert block in sheet, pair["pair_id"]
    assert sheet.count(CHOICE) == 12 and sheet.count("Reason:") == 12
    assert sheet.count("Fingerprint: ") == 12
    ids = re.findall(r"=== PAIR (P\d\d) ===", sheet)
    assert ids == [f"P{n:02d}" for n in range(1, 13)]
    assert f"Pair plan commitment: {read_json(com)['sha256']}" in sheet
    for word in (*MODELS, "gpt", "gemini", RUN_V2, "sample", "|", "slot"):
        assert word not in sheet, word
    assert read_json(private)["salt"] not in out
    assert_no_model_names(out)
    assert "review labels checked: 48" in out and "pairs shown: 12 of 12" in out
    assert "cannot be shown" not in out and "cannot be shown" not in sheet
    # write-once
    before = tree(tmp_path)
    assert cli.main(pair_sheet_cli(private, com, run, tmp_path / "pairs", review, review_com)) == 2
    assert "refusing to overwrite" in capsys.readouterr().err
    assert tree(tmp_path) == before


def test_pair_sheet_refuses_commitment_mismatch(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    run_a, run = two_runs(tmp_path)
    review, review_com = labelled_review(tmp_path, run_a, run)
    private, com, _ = generated_plan(tmp_path)
    data = read_json(private)
    _swap_sides(data)
    write_json(private, data)
    before = tree(tmp_path)
    assert cli.main(pair_sheet_cli(private, com, run, tmp_path / "pairs", review, review_com)) == 2
    err = all_output(capsys)
    assert "commitment NOT verified" in err and data["salt"] not in err
    assert_no_model_names(err)
    assert tree(tmp_path) == before


def test_pair_sheet_refuses_wrong_prompt_version(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    run, run_b = two_runs(tmp_path)
    review, review_com = labelled_review(tmp_path, run, run_b)
    private, com, _ = generated_plan(tmp_path)
    before = tree(tmp_path)
    assert cli.main(pair_sheet_cli(private, com, run, tmp_path / "pairs", review, review_com)) == 2
    assert "prompt version 'v1'" in capsys.readouterr().err
    assert tree(tmp_path) == before


def test_pair_sheet_hides_unavailable_pairs_by_count_only(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # Option B: a failed or incomplete reply leaves its pair off the sheet; the
    # sheet and stdout give only the count. An empty reply is shown.
    broken = {
        ("H3", M3, 1): {"status": "incomplete"},
        ("H1", M2, 2): {"status": "generation_failed", "output_text": None},
        ("H4", M1, 1): {"output_text": ""},
    }
    run_a = make_run(tmp_path, RUN_V1, "v1")
    run = make_run(tmp_path, RUN_V2, "v2", override=broken)
    review, review_com = labelled_review(tmp_path, run_a, run)
    private, com, plan = generated_plan(tmp_path)
    capsys.readouterr()
    assert cli.main(pair_sheet_cli(private, com, run, tmp_path / "pairs", review, review_com)) == 0
    out = all_output(capsys)
    gone = {
        p["pair_id"] for p in plan["pairs"]
        for side in ("left", "right")
        if (p["case"], p[side]["model"], p[side]["sample"]) in {("H3", M3, 1), ("H1", M2, 2)}
    }
    assert len(gone) == 2
    assert "pairs shown: 10 of 12" in out and "2 of 12 pairs cannot be shown" in out
    assert not re.search(r"P\d\d", out) and "side" not in out
    assert_no_model_names(out)
    sheet = (tmp_path / "pairs" / "pair_sheet.md").read_text(encoding="utf-8")
    assert "2 of 12 pairs cannot be shown." in sheet
    titles = re.findall(r"=== PAIR (P\d\d) ===", sheet)
    assert len(titles) == 10 and not gone & set(titles)
    empty_pair = next(
        p for p in plan["pairs"]
        if ("H4", M1, 1) in {(p["case"], p[s]["model"], p[s]["sample"]) for s in ("left", "right")}
    )
    label = "A" if (empty_pair["left"]["model"], empty_pair["left"]["sample"]) == (M1, 1) else "B"
    assert f"<<<<<<<< {label} >>>>>>>>\n(empty reply)\n<<<<<<<< END {label} >>>>>>>>" in sheet
    for word in (*MODELS, RUN_V2, "sample", "|"):
        assert word not in sheet, word


def test_pair_sheet_integrity_problem_counts_only(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    clean = tmp_path / "labelled"
    review, review_com = labelled_review(clean, *two_runs(clean))
    broken = make_run(
        tmp_path / "regenerated", RUN_V2, "v2",
        extra=[slot(RUN_V2, "H3", "v2", M3, 1, output_text="other words")],
    )
    private, com, _ = generated_plan(tmp_path)
    before = tree(tmp_path)
    assert cli.main(pair_sheet_cli(private, com, broken, tmp_path / "pairs", review, review_com)) == 2
    err = all_output(capsys)
    assert "1 of 24 pair replies has an integrity problem (duplicate 1)" in err
    assert not re.search(r"P\d\d", err)
    assert "side" not in err and "sample" not in err and "|" not in err
    assert not re.search(r"\bH[1-4]\b", err)
    assert_no_model_names(err)
    assert tree(tmp_path) == before


def test_pair_sheet_refuses_out_inside_the_private_folder(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    run_a, run = two_runs(tmp_path, ["H1", "H2"])
    review, review_com = labelled_review(tmp_path, run_a, run)
    private, com = make_plan_files(tmp_path, compare_plan())
    for out in (private.parent, private.parent / "pairs", private.parent / "a" / "b"):
        before = tree(tmp_path)
        assert cli.main(pair_sheet_cli(private, com, run, out, review, review_com)) == 2
        assert "inside the folder that holds the private plan" in capsys.readouterr().err
        assert tree(tmp_path) == before


def test_pair_sheet_label_ids_must_equal_the_committed_ids(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    run_a, run = two_runs(tmp_path, ["H1", "H2"])
    review, review_com = labelled_review(tmp_path, run_a, run, label="n")
    private, com = make_plan_files(tmp_path, compare_plan())
    args = pair_sheet_cli(private, com, run, tmp_path / "pairs", review, review_com)
    original = review.read_bytes()
    review.write_bytes(original + b"\nAccept H9-01? (y/n): y\n")
    assert cli.main(args) == 2
    err = capsys.readouterr().err
    assert "1 Accept lines are not committed IDs: H9-01" in err
    assert_no_model_names(err)
    review.write_bytes(original + b"\nAccept H1-01? (y/n): n\n")
    assert cli.main(args) == 2
    assert "Accept line repeated for H1-01" in capsys.readouterr().err
    review.write_bytes(original.replace(b"Accept H2-03? (y/n): n\n", b""))
    assert cli.main(args) == 2
    assert "1 committed IDs have no Accept line: H2-03" in capsys.readouterr().err
    review.write_bytes(original)
    assert cli.main(args) == 0


def test_pair_sheet_review_label_preconditions(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    run_a, run_b = two_runs(tmp_path)
    res = holdout.create_review_sheet([run_a, run_b], tmp_path / "review", tmp_path / "secret" / "review_key.json")
    review, review_com = res.sheet, res.commitment
    private, com, _ = generated_plan(tmp_path)
    args = pair_sheet_cli(private, com, run_b, tmp_path / "pairs", review, review_com)
    before = tree(tmp_path)
    assert cli.main(args) == 2
    err = capsys.readouterr().err
    assert "blank: H1-01, H1-02" in err
    assert_no_model_names(err)
    assert tree(tmp_path) == before
    # all labelled except one blank and one invalid
    fill_labels(review, lambda rid: {"H2-05": "", "H4-12": "yes"}.get(rid, "y" if rid < "H3" else "n"))
    assert cli.main(args) == 2
    err = capsys.readouterr().err
    assert "blank: H2-05" in err and "not exactly y or n: H4-12" in err
    assert_no_model_names(err)
    fill_labels(review, lambda rid: "n")
    # a review commitment that does not cover this run
    com_data = read_json(review_com)
    other_com = tmp_path / "public" / "other_review_commitment.json"
    write_json(other_com, {**com_data, "run_ids": [RUN_V1, "QX-OTHER-RUN"]})
    other = pair_sheet_cli(private, com, run_b, tmp_path / "pairs", review, other_com)
    assert cli.main(other) == 2
    assert f"does not cover run {RUN_V2}" in capsys.readouterr().err
    # a review commitment for another review (header mismatch)
    write_json(other_com.with_name("hash.json"), {**com_data, "sha256": "0" * 64})
    other[-1] = str(other_com.with_name("hash.json"))
    assert cli.main(other) == 2
    assert "'Review key commitment' line does not match" in capsys.readouterr().err
    # an Accept line removed: count no longer matches n_replies
    original = review.read_bytes()
    review.write_bytes(re.sub(rb"Accept H3-07\? \(y/n\): n\n", b"", original))
    assert cli.main(args) == 2
    assert "1 committed IDs have no Accept line: H3-07" in capsys.readouterr().err
    review.write_bytes(original)
    assert not (tmp_path / "pairs" / "pair_sheet.md").exists()
    # CRLF and a BOM from an editor are tolerated
    review.write_bytes(b"\xef\xbb\xbf" + original.replace(b"\n", b"\r\n"))
    assert cli.main(args) == 0
    out = capsys.readouterr().out
    assert "review labels checked: 48" in out
    assert_no_model_names(out)


def test_pair_sheet_requires_review_arguments(tmp_path: Path) -> None:
    with pytest.raises(SystemExit) as exc:
        cli.main(["pair-sheet", "--plan-private", "p", "--commitment", "c", "--run", "r", "--out", "o"])
    assert exc.value.code == 2


# ---------------------------------------------------------------- pair compare


def rec(
    run_id: str,
    case: str,
    model: str,
    idx: int,
    *,
    acceptable: bool,
    total: int | None,
    single: bool = True,
    critical: list[dict[str, Any]] | None = None,
    judged: bool = True,
    status: str = "scored",
    judge_version: str = "judge-v1",
    version: str = "v2",
    text_sha: str | None = None,
) -> dict[str, Any]:
    """A minimal scorer-1 score record (synthetic) for the fixture's reply text."""
    return {
        "slot_key": make_slot_key(run_id, case, version, model, idx),
        "run_id": run_id,
        "text_sha256": text_sha or sha(reply_text(run_id, case, model, idx)),
        "status": status,
        "scorer_version": "scorer-1",
        "judge_prompt_version": judge_version,
        "decision": {"acceptable": acceptable, "total": total, "scores": None, "reasons": []},
        "structural": {"single_turn_pass": single, "failures": [], "diagnostics": {}},
        "judgment": {"critical_violations": critical or []} if judged else None,
    }


def write_scores(root: Path, run_id: str, records: list[dict[str, Any]]) -> Path:
    d = root / "scores"
    d.mkdir(exist_ok=True)
    (d / f"{run_id}.jsonl").write_text(
        "".join(json.dumps(r) + "\n" for r in records), encoding="utf-8", newline="\n"
    )
    return d


DENIED = {
    "type": "multiple_questions",
    "rationale": "The reply asks a single question, so there is no violation here.",
    "evidence": [],
}


def rank(**kw: Any) -> holdout.Rank:
    return holdout.rank_of(rec(RUN_V2, "H1", M1, 1, **kw))


def test_rank_tuple_fields() -> None:
    assert rank(acceptable=True, total=8).as_tuple() == (1, 1, 8)
    assert rank(acceptable=False, total=7, critical=[DENIED]).as_tuple() == (0, 0, 7)
    assert rank(acceptable=False, total=8, single=False).as_tuple() == (0, 0, 8)
    # an empty reply: no judgment, total null
    empty = rank(acceptable=False, total=None, single=False, judged=False)
    assert empty.as_tuple() == (0, 0, -1)


def test_machine_result_keys_in_order() -> None:
    clean_low = rank(acceptable=False, total=3)
    critical_high = rank(acceptable=True, total=8, critical=[DENIED])  # synthetic (0,1,8)
    assert holdout.machine_result(clean_low, critical_high) == ("A", "clean", True)
    assert holdout.machine_result(critical_high, clean_low) == ("B", "clean", True)
    acc = rank(acceptable=True, total=5)
    not_acc = rank(acceptable=False, total=8)
    assert holdout.machine_result(not_acc, acc) == ("B", "acceptable", False)
    assert holdout.machine_result(rank(acceptable=False, total=7), rank(acceptable=False, total=6)) == (
        "A", "total", False,
    )
    assert holdout.machine_result(rank(acceptable=True, total=8), rank(acceptable=True, total=8)) == (
        "tie", "tie", False,
    )
    # single-turn failure decides on clean, but no raw critical entry was decisive
    st_fail = rank(acceptable=False, total=8, single=False, critical=[DENIED])
    assert holdout.machine_result(rank(acceptable=False, total=2), st_fail) == ("A", "clean", False)
    # empty reply ranks with total -1
    empty = rank(acceptable=False, total=None, single=False, judged=False)
    other = rank(acceptable=False, total=0, single=False)
    assert holdout.machine_result(empty, other) == ("B", "total", False)


def test_rank_rejects_scorer_2_and_malformed_records() -> None:
    r = rec(RUN_V2, "H1", M1, 1, acceptable=True, total=8)
    r["scorer_version"] = "scorer-2"
    with pytest.raises(holdout.HoldoutInputError, match="scorer-1"):
        holdout.rank_of(r)
    r = rec(RUN_V2, "H1", M1, 1, acceptable=True, total=8)
    r["decision"]["acceptable"] = None
    with pytest.raises(holdout.HoldoutInputError, match="acceptable"):
        holdout.rank_of(r)


def test_first_scored_requires_matching_text_sha() -> None:
    good = rec(RUN_V2, "H1", M1, 1, acceptable=True, total=8)
    other_words = rec(RUN_V2, "H1", M1, 1, acceptable=False, total=2, text_sha="0" * 64)
    key = good["slot_key"]
    text_sha = sha(reply_text(RUN_V2, "H1", M1, 1))
    assert holdout.first_scored([other_words, good], key, "judge-v1", text_sha) is good
    assert holdout.first_scored([other_words], key, "judge-v1", text_sha) is None


def side(m: str, s: int) -> dict[str, Any]:
    return {"model": m, "sample": s}


def compare_plan() -> dict[str, Any]:
    """Two cases; placement fixed by hand (each first-named model left in H1 only)."""
    return {
        "prompt_version": "v2",
        "models": MODELS,
        "cases": ["H1", "H2"],
        "pairs": [
            {"pair_id": "P01", "case": "H1", "left": side(M1, 1), "right": side(M2, 1)},
            {"pair_id": "P02", "case": "H1", "left": side(M2, 2), "right": side(M3, 2)},
            {"pair_id": "P03", "case": "H1", "left": side(M1, 2), "right": side(M3, 1)},
            {"pair_id": "P04", "case": "H2", "left": side(M3, 1), "right": side(M1, 2)},
            {"pair_id": "P05", "case": "H2", "left": side(M2, 1), "right": side(M1, 1)},
            {"pair_id": "P06", "case": "H2", "left": side(M3, 2), "right": side(M2, 2)},
        ],
    }


def compare_scores() -> list[dict[str, Any]]:
    R = RUN_V2
    return [
        # P01 H1: M1s1 clean (1,0,5) vs M2s1 raw critical that denies itself (0,0,8) -> A, clean, decisive
        rec(R, "H1", M1, 1, acceptable=False, total=5),
        rec(R, "H1", M2, 1, acceptable=False, total=8, critical=[DENIED]),
        # P02 H1: M2s2 (1,1,7) vs M3s2 (1,0,8) -> A by acceptable
        rec(R, "H1", M2, 2, acceptable=True, total=7),
        rec(R, "H1", M3, 2, acceptable=False, total=8),
        # P03 H1: M1s2 (1,1,8) vs M3s1 (1,1,8) -> tie
        rec(R, "H1", M1, 2, acceptable=True, total=8),
        rec(R, "H1", M3, 1, acceptable=True, total=8),
        # P04 H2: M3s1 empty (0,0,-1) vs M1s2 single-turn fail (0,0,3) -> B by total
        rec(R, "H2", M3, 1, acceptable=False, total=None, single=False, judged=False),
        rec(R, "H2", M1, 2, acceptable=False, total=3, single=False),
        # P05 H2: M2s1 has only needs_review, another judge's score and a score of other words -> unscored
        rec(R, "H2", M2, 1, acceptable=False, total=None, status="needs_review"),
        rec(R, "H2", M2, 1, acceptable=True, total=8, judge_version="judge-v3"),
        rec(R, "H2", M2, 1, acceptable=True, total=8, text_sha="0" * 64),
        rec(R, "H2", M1, 1, acceptable=True, total=8),
        # P06 H2: a score of other words is skipped; first matching record wins: M3s2 (1,0,4),
        # a later (1,1,8) is ignored; M2s2 (1,0,6) -> B by total
        rec(R, "H2", M3, 2, acceptable=True, total=8, text_sha="f" * 64),
        rec(R, "H2", M3, 2, acceptable=False, total=4),
        rec(R, "H2", M3, 2, acceptable=True, total=8),
        rec(R, "H2", M2, 2, acceptable=False, total=6),
    ]


def fill_pair_sheet(sheet: Path, choices: dict[str, str], reasons: dict[str, str] | None = None) -> None:
    """Fill Choice and Reason lines outside the A/B blocks."""
    lines = sheet.read_text(encoding="utf-8").split("\n")
    current = None
    in_block = False
    for i, line in enumerate(lines):
        if re.match(r"^<<<<<<<< (A|B) >>>>>>>>$", line):
            in_block = True
            continue
        if re.match(r"^<<<<<<<< END (A|B) >>>>>>>>$", line):
            in_block = False
            continue
        if in_block:
            continue
        m = re.match(r"=== PAIR (\S+) ===", line)
        if m:
            current = m.group(1)
        if line == CHOICE and current in choices:
            lines[i] = f"{CHOICE} {choices[current]}"
        if line == "Reason:" and reasons and current in reasons:
            lines[i] = f"Reason: {reasons[current]}"
    sheet.write_text("\n".join(lines), encoding="utf-8", newline="\n")


def setup_compare(
    tmp_path: Path,
    choices: dict[str, str],
    reasons: dict[str, str] | None = None,
    texts: dict[tuple[str, str, int], str] | None = None,
    scores: list[dict[str, Any]] | None = None,
) -> tuple[list[str], Path]:
    override = {k: {"output_text": t} for k, t in (texts or {}).items()}
    run_a = make_run(tmp_path, RUN_V1, "v1", ["H1", "H2"])
    run = make_run(tmp_path, RUN_V2, "v2", ["H1", "H2"], override=override)
    review, review_com = labelled_review(tmp_path, run_a, run)
    private, com = make_plan_files(tmp_path, compare_plan())
    scores_dir = write_scores(tmp_path, RUN_V2, compare_scores() if scores is None else scores)
    holdout.create_pair_sheet(private, com, run, tmp_path / "pairs", review, review_com)
    sheet = tmp_path / "pairs" / "pair_sheet.md"
    fill_pair_sheet(sheet, choices, reasons)
    args = ["pair-compare", "--plan", str(private), "--commitment", str(com), "--run", str(run),
            "--pair-sheet", str(sheet), "--scores-dir", str(scores_dir)]
    return args, sheet


def test_pair_compare_end_to_end(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    # P01 human A (match), P02 B (machine A), P03 "  Tie " (match), P04 blank, P05 A (unscored), P06 b (match)
    choices = {"P01": "A", "P02": "B", "P03": "  Tie ", "P05": "A", "P06": "b"}
    args, sheet = setup_compare(tmp_path, choices, {"P01": "warmer tone", "P02": "asks the outcome"})
    # a multi-line reason on P03
    text = sheet.read_text(encoding="utf-8")
    text = text.replace(f"{CHOICE}   Tie \nReason:\n", f"{CHOICE}   Tie \nReason: both fine\nequally short\n", 1)
    sheet.write_text(text, encoding="utf-8", newline="\n")
    scores_before = tree(tmp_path / "scores")
    json_out = tmp_path / "reports" / "pairs.json"
    assert cli.main([*args, "--json-out", str(json_out)]) == 0
    out = capsys.readouterr().out
    assert tree(tmp_path / "scores") == scores_before
    report = read_json(json_out)
    rows = {r["pair_id"]: r for r in report["pairs"]}
    order = ("P01", "P02", "P03", "P04", "P05", "P06")
    assert [rows[p]["machine"] for p in order] == ["A", "A", "tie", "B", "missing", "B"]
    assert [rows[p]["deciding_key"] for p in order] == [
        "clean", "acceptable", "tie", "total", None, "total",
    ]
    assert rows["P01"]["raw_critical_decisive"] is True
    assert rows["P01"]["right"]["rank"] == [0, 0, 8]
    assert rows["P04"]["left"]["rank"] == [0, 0, -1]
    assert rows["P06"]["left"]["rank"] == [1, 0, 4]  # first record for the same words
    assert rows["P05"]["left"]["scored"] is False  # only other words / other judge / needs_review
    assert [rows[p]["human"] for p in order] == ["A", "B", "tie", "missing", "A", "B"]
    assert rows["P04"]["missing_reasons"] == ["human blank"]
    assert rows["P05"]["missing_reasons"] == ["unscored (invalid or failed judgment)"]
    assert rows["P05"]["left"]["unscored_reason"] == "unscored (invalid or failed judgment)"
    assert [rows[p]["human_reason"] for p in order] == [
        "warmer tone", "asks the outcome", "both fine\nequally short", "", "", "",
    ]
    s = report["summary"]
    assert s["total_pairs"] == 6 and s["evaluable"] == 4
    assert s["exact_matches"] == 3 and s["exact_match_fraction"] == 0.75
    assert s["confusion_human_by_machine"] == {
        "A": {"A": 1, "B": 0, "tie": 0},
        "B": {"A": 1, "B": 1, "tie": 0},
        "tie": {"A": 0, "B": 0, "tie": 1},
    }
    assert s["human_ties"] == 1 and s["machine_ties"] == 1
    assert s["human_chosen"] == 5 and s["chosen_without_reason"] == 2
    assert s["missing"] == [
        {"pair_id": "P04", "reasons": ["human blank"]},
        {"pair_id": "P05", "reasons": ["unscored (invalid or failed judgment)"]},
    ]
    assert s["missing_by_reason"] == {"human blank": 1, "unscored (invalid or failed judgment)": 1}
    assert "Evaluable pairs: 4 of 6" in out
    assert "Exact matches: 3 of 4 (0.750)" in out
    assert "P04 (human blank), P05 (unscored (invalid or failed judgment))" in out
    assert "P03: both fine / equally short" in out and "P05: (none)" in out
    assert "Chosen pairs without a reason: 2 of 5" in out
    assert f"{M1} s1" in out  # after reveal the report names models
    # the JSON report is write-once too
    assert cli.main([*args, "--json-out", str(json_out)]) == 2
    assert "refusing to overwrite" in capsys.readouterr().err


def test_pair_compare_missing_both(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    args, _ = setup_compare(tmp_path, {"P01": "A"})
    assert cli.main(args) == 0
    out = capsys.readouterr().out
    assert "P05 (human blank; unscored (invalid or failed judgment))" in out and "Evaluable pairs: 1 of 6" in out


def test_pair_compare_refuses_unfilled_sheet(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    args, _ = setup_compare(tmp_path, {})
    assert cli.main(args) == 2
    cap = capsys.readouterr()
    assert "every Choice line is blank" in cap.err
    assert cap.out == ""
    assert_no_model_names(cap.out + cap.err)


def test_pair_compare_invalid_choice_is_input_error(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    args, _ = setup_compare(tmp_path, {"P01": "A", "P03": "left one"})
    assert cli.main(args) == 2
    err = capsys.readouterr().err
    assert "P03" in err and "not A, B or tie" in err


def test_pair_compare_refuses_commitment_mismatch_and_foreign_sheet(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    args, sheet = setup_compare(tmp_path, {"P01": "A"})
    private = Path(args[args.index("--plan") + 1])
    original = private.read_bytes()
    data = read_json(private)
    _swap_sides(data)
    write_json(private, data)
    assert cli.main(args) == 2
    assert "commitment NOT verified" in capsys.readouterr().err
    private.write_bytes(original)
    # a sheet from another plan with the same pair IDs
    text = sheet.read_text(encoding="utf-8")
    sheet.write_text(re.sub(r"Pair plan commitment: \w+", "Pair plan commitment: " + "0" * 64, text),
                     encoding="utf-8", newline="\n")
    assert cli.main(args) == 2
    assert "different pair plan" in capsys.readouterr().err


def test_pair_compare_refuses_sheet_from_another_run(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    # B2: a sheet built from run X scored against run Y of the same shape
    args, sheet = setup_compare(tmp_path, {"P01": "A", "P02": "B"})
    other = make_run(tmp_path / "elsewhere", "QX-CHARLIE-RUN", "v2", ["H1", "H2"])
    write_scores(tmp_path / "elsewhere", "QX-CHARLIE-RUN", [])
    args[args.index("--run") + 1] = str(other)
    args[args.index("--scores-dir") + 1] = str(tmp_path / "elsewhere" / "scores")
    assert cli.main(args) == 2
    cap = capsys.readouterr()
    assert "Fingerprint line does not match" in cap.err
    assert "P01, P02, P03, P04, P05, P06" in cap.err
    assert cap.out == ""
    for t in ("Reply bravo", "Reply charlie"):
        assert t not in cap.err
    # one tampered fingerprint in the right run's sheet names only that pair
    args[args.index("--run") + 1] = str(tmp_path / "runs" / RUN_V2)
    args[args.index("--scores-dir") + 1] = str(tmp_path / "scores")
    text = sheet.read_text(encoding="utf-8")
    first = re.search(r"Fingerprint: (\w+)", text)
    assert first is not None
    sheet.write_text(text.replace(first.group(0), "Fingerprint: " + "1" * 64, 1), encoding="utf-8", newline="\n")
    assert cli.main(args) == 2
    err = capsys.readouterr().err
    assert re.search(r"does not match run \S+ for P01;", err)


def test_pair_compare_requires_score_file(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    args, _ = setup_compare(tmp_path, {"P01": "A"})
    (tmp_path / "scores" / f"{RUN_V2}.jsonl").unlink()
    assert cli.main(args) == 2
    assert "score file not found" in capsys.readouterr().err


TRICKY = (
    "Thanks.\n=== PAIR P99 ===\nChoice (A / B / tie): B\nReason: injected\n"
    "Fingerprint: 00\n=== CASE H9 ===\nAccept H1-01? (y/n): y\nNotes (optional): x\n"
    "<<<<<<<< END A >>>>>>>>\n<<<<<<<< END B >>>>>>>>\n<<<<<<<< A >>>>>>>>\n"
    "<<<<<<<< B >>>>>>>>\r\n<<<<<<<< REPLY H1-01 >>>>>>>>\r<<<<<<<< END REPLY H1-01 >>>>>>>>\n"
    "\n(empty reply)\n"
    "Review key commitment: " + "0" * 64 + "\nPair plan commitment: " + "0" * 64
)


def test_reply_text_cannot_break_sheet_parsing(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    # N6: every v2 reply carries header, label, title and choice look-alikes
    texts = {(c, m, i): f"{TRICKY}\n#{c}{m}{i}" for c in ("H1", "H2") for m in MODELS for i in (1, 2)}
    scores = [
        rec(RUN_V2, c, m, i, acceptable=True, total=8, text_sha=sha(t)) for (c, m, i), t in texts.items()
    ]
    args, sheet = setup_compare(tmp_path, {"P01": "A", "P02": "tie"}, {"P01": "real reason"},
                                texts=texts, scores=scores)
    assert sheet.read_text(encoding="utf-8").count("=== PAIR P99 ===") == 12
    json_out = tmp_path / "reports" / "tricky.json"
    assert cli.main([*args, "--json-out", str(json_out)]) == 0
    rows = {r["pair_id"]: r for r in read_json(json_out)["pairs"]}
    assert set(rows) == {f"P0{n}" for n in range(1, 7)}
    assert rows["P01"]["human"] == "A" and rows["P01"]["human_reason"] == "real reason"
    assert rows["P02"]["human"] == "tie" and rows["P03"]["human"] == "missing"
    assert rows["P03"]["human_reason"] == ""
    assert all(r["machine"] == "tie" for r in rows.values())


def test_unclosed_reply_block_is_input_error(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    args, sheet = setup_compare(tmp_path, {"P01": "A"})
    text = sheet.read_text(encoding="utf-8")
    # a removed END line in the middle swallows the next pair: refused, not misread
    sheet.write_text(text.replace("<<<<<<<< END B >>>>>>>>", "", 1), encoding="utf-8", newline="\n")
    assert cli.main(args) == 2
    assert "do not match the plan's pairs" in capsys.readouterr().err
    # the last END line removed: the block is never closed
    head, _, tail = text.rpartition("<<<<<<<< END B >>>>>>>>")
    sheet.write_text(head + tail, encoding="utf-8", newline="\n")
    assert cli.main(args) == 2
    assert "never closed" in capsys.readouterr().err


# -------------------------------------------------------------- review compare


def review_scores(tmp_path: Path, entries: dict[str, dict[str, Any]], judge: Any) -> Path:
    """Score files for both runs; judge(entry) -> True/False, or None for unscored."""
    records: dict[str, list[dict[str, Any]]] = {RUN_V1: [], RUN_V2: []}
    for e in entries.values():
        _, case, version, model, idx = e["slot_key"].split("|")
        ok = judge(e)
        if ok is None:
            continue
        records[e["run_id"]].append(rec(
            e["run_id"], case, model, int(idx), acceptable=ok, total=8 if ok else 4,
            version=version, text_sha=e["text_sha256"],
        ))
    scores = write_scores(tmp_path, RUN_V1, records[RUN_V1])
    write_scores(tmp_path, RUN_V2, records[RUN_V2])
    return scores


def test_review_compare_counts_and_agreement(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    run_a, run_b = two_runs(tmp_path, ["H1", "H2"])
    assert cli.main(review_cli(tmp_path, run_a, run_b)) == 0
    capsys.readouterr()
    key_path = tmp_path / "secret" / "review_key.json"
    com_path = tmp_path / "review" / "review_key_commitment.json"
    sheet = tmp_path / "review" / "review_sheet.md"
    entries = read_json(key_path)["entries"]

    # Human: accepts every M1 reply, and M2 sample 1 under v2; rejects the rest.
    def human(e: dict[str, Any]) -> bool:
        return e["model"] == M1 or (e["model"] == M2 and e["prompt_version"] == "v2" and e["sample_index"] == 1)

    fill_labels(sheet, lambda rid: "y" if human(entries[rid]) else "n")

    # Judge: acceptable for M1 except v1 H2 s2; M3 v1 H1 s1 acceptable; M2 v2 H1 s2 unscored.
    def judge(e: dict[str, Any]) -> bool | None:
        _, case, version, model, idx = e["slot_key"].split("|")
        if model == M2 and version == "v2" and case == "H1" and idx == "2":
            return None
        return (model == M1 and not (version == "v1" and case == "H2" and idx == "2")) or (
            model == M3 and version == "v1" and case == "H1" and idx == "1"
        )

    scores = review_scores(tmp_path, entries, judge)
    json_out = tmp_path / "reports" / "review.json"
    args = ["review-compare", "--key", str(key_path), "--commitment", str(com_path),
            "--sheet", str(sheet), "--scores-dir", str(scores), "--json-out", str(json_out)]
    assert cli.main(args) == 0
    out = capsys.readouterr().out
    report = read_json(json_out)
    by = {(c["prompt_version"], c["model"]): c for c in report["by_prompt_model"]}
    assert by[("v1", M1)] == {
        "prompt_version": "v1", "model": M1, "shown": 4, "human_accepted": 4,
        "judge_acceptable": 3, "unscored": 0, "unscored_by_reason": {},
        "operational_failures": 0, "evaluable": 4, "agree": 3,
    }
    assert by[("v2", M1)]["human_accepted"] == 4 and by[("v2", M1)]["agree"] == 4
    assert by[("v2", M2)] == {
        "prompt_version": "v2", "model": M2, "shown": 4, "human_accepted": 2,
        "judge_acceptable": 0, "unscored": 1,
        "unscored_by_reason": {"unscored (no judge record)": 1},
        "operational_failures": 0, "evaluable": 3, "agree": 1,
    }
    assert by[("v1", M3)]["judge_acceptable"] == 1 and by[("v1", M3)]["agree"] == 3
    assert by[("v1", M2)]["agree"] == 4 and by[("v2", M3)]["agree"] == 4
    cell = {(c["case"], c["prompt_version"], c["model"]): c for c in report["by_case_prompt_model"]}
    assert len(cell) == 12
    assert cell[("H2", "v1", M1)]["judge_acceptable"] == 1 and cell[("H2", "v1", M1)]["agree"] == 1
    assert cell[("H1", "v2", M2)]["unscored"] == 1 and cell[("H1", "v2", M2)]["agree"] == 0
    dis = {(d["prompt_version"], d["model"], d["case"], d["sample_index"]) for d in report["disagreements"]}
    assert dis == {
        ("v1", M1, "H2", 2), ("v1", M3, "H1", 1), ("v2", M2, "H1", 1), ("v2", M2, "H2", 1),
    }
    assert len(report["unscored"]) == 1
    assert "By prompt and model:" in out and "Disagreements:" in out and M1 in out


def test_review_compare_ignores_scores_of_other_words(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    run_a, run_b = two_runs(tmp_path, ["H1", "H2"])
    sheet, com_path = labelled_review(tmp_path, run_a, run_b)
    key_path = tmp_path / "secret" / "review_key.json"
    entries = read_json(key_path)["entries"]
    altered = {rid: {**e, "text_sha256": "0" * 64} for rid, e in entries.items()}
    scores = review_scores(tmp_path, altered, lambda e: True)
    json_out = tmp_path / "reports" / "r.json"
    args = ["review-compare", "--key", str(key_path), "--commitment", str(com_path),
            "--sheet", str(sheet), "--scores-dir", str(scores), "--json-out", str(json_out)]
    assert cli.main(args) == 0
    assert len(read_json(json_out)["unscored"]) == 24


def test_review_compare_refuses_bad_labels_header_and_key(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    run_a, run_b = two_runs(tmp_path, ["H1", "H2"])
    assert cli.main(review_cli(tmp_path, run_a, run_b)) == 0
    key_path = tmp_path / "secret" / "review_key.json"
    com_path = tmp_path / "review" / "review_key_commitment.json"
    sheet = tmp_path / "review" / "review_sheet.md"
    scores = review_scores(tmp_path, read_json(key_path)["entries"], lambda e: True)
    args = ["review-compare", "--key", str(key_path), "--commitment", str(com_path),
            "--sheet", str(sheet), "--scores-dir", str(scores)]
    fill_labels(sheet, lambda rid: "" if rid in ("H1-03", "H2-11") else "y")
    capsys.readouterr()
    assert cli.main(args) == 2
    assert "blank labels: H1-03, H2-11" in capsys.readouterr().err
    # N8: an invalid label is an input error
    fill_labels(sheet, lambda rid: "yes" if rid == "H2-04" else "n")
    assert cli.main(args) == 2
    cap = capsys.readouterr()
    assert "labels not exactly y or n: H2-04" in cap.err and cap.out == ""
    fill_labels(sheet, lambda rid: "n")
    assert cli.main(args) == 0
    capsys.readouterr()
    # N8: a sheet whose header belongs to another review is refused
    original = sheet.read_bytes()
    sheet.write_bytes(re.sub(rb"Review key commitment: \w+", b"Review key commitment: " + b"0" * 64, original))
    assert cli.main(args) == 2
    cap = capsys.readouterr()
    assert "belongs to a different review key" in cap.err and cap.out == ""
    sheet.write_bytes(original)
    # a tampered key
    key = read_json(key_path)
    key["salt"] = "f" * 64
    write_json(key_path, key)
    assert cli.main(args) == 2
    err = capsys.readouterr().err
    assert "commitment NOT verified" in err and "f" * 64 not in err


def test_compare_json_out_refused_inside_scores(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    args, _ = setup_compare(tmp_path, {"P01": "A"})
    before = tree(tmp_path / "scores")
    assert cli.main([*args, "--json-out", str(tmp_path / "scores" / "r.json")]) == 2
    assert "scores directory" in capsys.readouterr().err
    assert tree(tmp_path / "scores") == before


def test_out_dir_that_is_a_file_is_refused(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    run_a, run_b = two_runs(tmp_path, ["H1", "H2"])
    (tmp_path / "review").write_text("not a dir", encoding="utf-8")
    before = tree(tmp_path)
    assert cli.main(review_cli(tmp_path, run_a, run_b)) == 2
    assert "is a file, not a directory" in capsys.readouterr().err
    assert tree(tmp_path) == before


# ------------------------------------------------------- private paths (N2)


def test_review_sheet_refuses_private_key_inside_out(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    run_a, run_b = two_runs(tmp_path, ["H1", "H2"])
    for key in (tmp_path / "review" / "key.json", tmp_path / "review" / "sub" / "key.json"):
        args = review_cli(tmp_path, run_a, run_b)
        args[-1] = str(key)
        before = tree(tmp_path)
        assert cli.main(args) == 2
        assert "must not be written inside --out" in capsys.readouterr().err
        assert tree(tmp_path) == before


def test_pair_plan_refuses_private_next_to_commitment(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    args = plan_cli(tmp_path)
    args[args.index("--private-out") + 1] = str(tmp_path / "public" / "plan.json")
    assert cli.main(args) == 2
    assert "same folder as the commitment" in capsys.readouterr().err
    assert tree(tmp_path) == {}
    # a commitment at a parent folder of the private folder is fine
    args = plan_cli(tmp_path)
    args[args.index("--commitment-out") + 1] = str(tmp_path / "plan_commitment.json")
    assert cli.main(args) == 0


# ---------------------------------------------------- commitment coverage (N4)


def verify_args(private: Path, com: Path) -> list[str]:
    return ["verify-commitment", "--private", str(private), "--commitment", str(com)]


def test_verify_rejects_changed_pair_rule_and_extra_private_keys(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    private, com, _ = generated_plan(tmp_path)
    commitment = read_json(com)
    bad_rule = tmp_path / "public" / "rule.json"
    write_json(bad_rule, {**commitment, "pair_rule": commitment["pair_rule"] + " "})
    assert cli.main(verify_args(private, bad_rule)) == 1
    assert "pair_rule does not match" in capsys.readouterr().err
    data = read_json(private)
    extra = tmp_path / "secret" / "extra.json"
    write_json(extra, {**data, "secretnote": "x"})
    assert cli.main(verify_args(extra, com)) == 1
    err = capsys.readouterr().err
    assert "1 unexpected top-level field;" in err and data["salt"] not in err
    assert "secretnote" not in err  # private field names are not echoed
    # the review key too
    run_a, run_b = two_runs(tmp_path, ["H1", "H2"])
    holdout.create_review_sheet([run_a, run_b], tmp_path / "review", tmp_path / "secret" / "review_key.json")
    key = read_json(tmp_path / "secret" / "review_key.json")
    write_json(tmp_path / "secret" / "key_extra.json", {**key, "hintone": 1, "hinttwo": 2})
    assert cli.main(verify_args(tmp_path / "secret" / "key_extra.json",
                                tmp_path / "review" / "review_key_commitment.json")) == 1
    err = capsys.readouterr().err
    assert "2 unexpected top-level fields;" in err and "hint" not in err


def assert_safely_rendered(sheet: str, opener: str, closer: str) -> None:
    """Every line inside a reply block is "", "(empty reply)" or starts with "> "."""
    inside = False
    for line in sheet.split("\n"):
        if re.match(closer, line):
            inside = False
            continue
        if inside:
            assert line == "" or line == "(empty reply)" or line.startswith("> "), line
        if re.match(opener, line):
            inside = True


def test_lookalikes_are_preserved_and_rendered_safely(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    texts = {(c, m, i): f"{TRICKY}\n#{c}{m}{i}" for c in ("H1", "H2") for m in MODELS for i in (1, 2)}
    texts[("H2", M3, 2)] = "(empty reply)"  # literally these words: shown as "> (empty reply)"
    texts[("H2", M2, 2)] = "  "  # an empty reply: the bare marker
    run_a = make_run(tmp_path, RUN_V1, "v1", ["H1", "H2"],
                     override={k: {"output_text": t} for k, t in texts.items()})
    run = make_run(tmp_path, RUN_V2, "v2", ["H1", "H2"],
                   override={k: {"output_text": t} for k, t in texts.items()})
    res = holdout.create_review_sheet([run_a, run], tmp_path / "review", tmp_path / "secret" / "key.json")
    review = res.sheet.read_text(encoding="utf-8")
    assert res.n_replies == 24
    assert_safely_rendered(review, r"^<<<<<<<< REPLY \S+ >>>>>>>>$", r"^<<<<<<<< END REPLY \S+ >>>>>>>>$")
    # 20 replies carry TRICKY's own "(empty reply)" line, 2 are literally those words
    assert review.count("\n> (empty reply)\n") == 22 and review.count("\n(empty reply)\n") == 2
    assert review.count("> <<<<<<<< END REPLY H1-01 >>>>>>>>") == 20  # 20 replies carry TRICKY
    # reply text survives exactly, by fingerprint
    key = read_json(tmp_path / "secret" / "key.json")
    raw = {e["slot_key"]: e["text_sha256"] for e in key["entries"].values()}
    assert raw[make_slot_key(RUN_V2, "H2", "v2", M3, 2)] == sha("(empty reply)")
    assert raw[make_slot_key(RUN_V2, "H1", "v2", M1, 1)] == sha(texts[("H1", M1, 1)])
    fill_labels(res.sheet, lambda rid: "y")
    assert holdout.check_review_labels(res.sheet, res.commitment, RUN_V2) == 24
    private, com = make_plan_files(tmp_path, compare_plan())
    holdout.create_pair_sheet(private, com, run, tmp_path / "pairs", res.sheet, res.commitment)
    pairs = (tmp_path / "pairs" / "pair_sheet.md").read_text(encoding="utf-8")
    assert_safely_rendered(pairs, r"^<<<<<<<< (A|B) >>>>>>>>$", r"^<<<<<<<< END (A|B) >>>>>>>>$")
    assert re.findall(r"^=== PAIR (P\d\d) ===$", pairs, re.M) == [f"P0{n}" for n in range(1, 7)]
    # P06 is M3 s2 ("(empty reply)" literally) vs M2 s2 (empty): distinguishable
    assert "<<<<<<<< A >>>>>>>>\n> (empty reply)\n<<<<<<<< END A >>>>>>>>" in pairs
    assert "<<<<<<<< B >>>>>>>>\n(empty reply)\n<<<<<<<< END B >>>>>>>>" in pairs
    assert f"Fingerprint: {holdout.pair_fingerprint('(empty reply)', '  ')}" in pairs


def test_identical_texts_from_distinct_slots_are_all_shown(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    same = "Same words from two slots?"
    override = {("H1", M1, 1): {"output_text": same}, ("H1", M2, 1): {"output_text": same}}
    run_a = make_run(tmp_path, RUN_V1, "v1", ["H1", "H2"], override=override)
    run = make_run(tmp_path, RUN_V2, "v2", ["H1", "H2"], override=override)
    res = holdout.create_review_sheet([run_a, run], tmp_path / "review", tmp_path / "secret" / "key.json")
    review = res.sheet.read_text(encoding="utf-8")
    assert res.n_replies == 24 and review.count(f"> {same}") == 4
    entries = read_json(tmp_path / "secret" / "key.json")["entries"]
    same_ids = [rid for rid, e in entries.items() if e["text_sha256"] == sha(same)]
    assert len(same_ids) == 4 and len({entries[r]["slot_key"] for r in same_ids}) == 4
    fill_labels(res.sheet, lambda rid: "y")
    private, com = make_plan_files(tmp_path, compare_plan())
    holdout.create_pair_sheet(private, com, run, tmp_path / "pairs", res.sheet, res.commitment)
    pairs = (tmp_path / "pairs" / "pair_sheet.md").read_text(encoding="utf-8")
    # P01 is M1 s1 vs M2 s1 in H1: both sides shown, same words
    assert f"=== PAIR P01 ===\n{side_block('A', same)}\n{side_block('B', same)}" in pairs


def test_empty_reply_ranks_below_a_non_empty_reply_with_clean_0_total_0() -> None:
    empty = rank(acceptable=False, total=None, single=False, judged=False)
    non_empty = rank(acceptable=False, total=0, critical=[DENIED])
    assert empty.as_tuple() == (0, 0, -1) and non_empty.as_tuple() == (0, 0, 0)
    assert holdout.machine_result(empty, non_empty) == ("B", "total", False)
    assert holdout.machine_result(non_empty, empty) == ("A", "total", False)


def test_operational_failures_through_every_command(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """One failed, one incomplete and one empty v2 reply (plus a failed v1 reply)
    through review-sheet, pair-sheet, pair-compare and review-compare."""
    v2_broken = {
        ("H1", M2, 2): {"status": "generation_failed", "output_text": None},  # P02 unavailable
        ("H2", M3, 1): {"status": "incomplete"},  # P04 unavailable
        ("H1", M1, 1): {"output_text": ""},  # empty: P01's A side, shown
    }
    run_a = make_run(tmp_path, RUN_V1, "v1", ["H1", "H2"],
                     override={("H2", M1, 2): {"status": "generation_failed", "output_text": None}})
    run = make_run(tmp_path, RUN_V2, "v2", ["H1", "H2"], override=v2_broken)
    assert cli.main(review_cli(tmp_path, run_a, run)) == 0
    out = all_output(capsys)
    assert "replies shown: 21 across 2 cases" in out
    assert "replies not shown (operational failures): 3 (failed 2, incomplete 1)" in out
    assert_no_model_names(out)
    assert not re.search(r"H\d-\d\d", out) and "|" not in out
    key_path = tmp_path / "secret" / "review_key.json"
    com_path = tmp_path / "review" / "review_key_commitment.json"
    sheet_path = tmp_path / "review" / "review_sheet.md"
    key, com = read_json(key_path), read_json(com_path)
    assert com["unavailable"] == {"failed": 2, "incomplete": 1} and com["n_replies"] == 21
    assert sorted(com["ids"]) == sorted(key["entries"]) and len(com["ids"]) == 21
    assert sorted(u["kind"] for u in key["unavailable"]) == ["failed", "failed", "incomplete"]
    assert_no_model_names(com_path.read_text(encoding="utf-8"))
    sheet = sheet_path.read_text(encoding="utf-8")
    assert "3 replies could not be shown (operational failures: failed 2, incomplete 1)." in sheet
    assert sheet.count("\n(empty reply)\n") == 1
    assert cli.main(["verify-commitment", "--private", str(key_path), "--commitment", str(com_path)]) == 0
    capsys.readouterr()
    # the metadata must equal what the key implies; the unavailable list is hashed
    for field, value in (("unavailable", {"failed": 1, "incomplete": 1}), ("ids", com["ids"][:-1])):
        bad = tmp_path / "public" / f"{field}.json"
        bad.parent.mkdir(exist_ok=True)
        write_json(bad, {**com, field: value})
        assert cli.main(["verify-commitment", "--private", str(key_path), "--commitment", str(bad)]) == 1
        assert f"{field} do" in capsys.readouterr().err
    tampered = tmp_path / "secret" / "tampered.json"
    write_json(tampered, {**key, "unavailable": key["unavailable"][:-1]})
    assert cli.main(["verify-commitment", "--private", str(tampered), "--commitment", str(com_path)]) == 1
    err = capsys.readouterr().err
    assert "salted hash" in err and key["salt"] not in err
    # labels, then the pair sheet
    fill_labels(sheet_path, lambda rid: "y")
    private, plan_com = make_plan_files(tmp_path, compare_plan())
    assert cli.main(pair_sheet_cli(private, plan_com, run, tmp_path / "pairs", sheet_path, com_path)) == 0
    out = all_output(capsys)
    assert "review labels checked: 21" in out
    assert "pairs shown: 4 of 6" in out and "2 of 6 pairs cannot be shown" in out
    assert_no_model_names(out)
    assert not re.search(r"P\d\d", out)
    pair_sheet = tmp_path / "pairs" / "pair_sheet.md"
    assert re.findall(r"=== PAIR (P\d\d) ===", pair_sheet.read_text(encoding="utf-8")) == ["P01", "P03", "P05", "P06"]
    fill_pair_sheet(pair_sheet, {"P01": "A", "P03": "B", "P05": "tie"})
    # scores: v2 (one budget stop) and v1
    R = RUN_V2
    v2_scores = [
        rec(R, "H1", M1, 1, acceptable=False, total=None, single=False, judged=False, text_sha=sha("")),
        rec(R, "H1", M2, 1, acceptable=False, total=0, single=False),  # (0,0,0) beats the empty reply
        rec(R, "H1", M1, 2, acceptable=True, total=8),
        rec(R, "H1", M3, 1, acceptable=False, total=5),
        rec(R, "H1", M3, 2, acceptable=False, total=8),
        rec(R, "H2", M1, 1, acceptable=True, total=8),
        rec(R, "H2", M1, 2, acceptable=False, total=3),
        rec(R, "H2", M2, 1, acceptable=False, total=None, status="budget_stopped"),
        rec(R, "H2", M2, 2, acceptable=False, total=6),
        rec(R, "H2", M3, 2, acceptable=False, total=6),
    ]
    scores = write_scores(tmp_path, R, v2_scores)
    v1_entries = [e for e in key["entries"].values() if e["run_id"] == RUN_V1]
    write_scores(tmp_path, RUN_V1, [
        rec(RUN_V1, e["slot_key"].split("|")[1], e["model"], e["sample_index"], acceptable=True,
            total=8, version="v1", text_sha=e["text_sha256"])
        for e in v1_entries
    ])
    json_out = tmp_path / "reports" / "pairs.json"
    args = ["pair-compare", "--plan", str(private), "--commitment", str(plan_com), "--run", str(run),
            "--pair-sheet", str(pair_sheet), "--scores-dir", str(scores), "--json-out", str(json_out)]
    assert cli.main(args) == 0
    out = capsys.readouterr().out
    report = read_json(json_out)
    rows = {r["pair_id"]: r for r in report["pairs"]}
    assert rows["P01"]["machine"] == "B" and rows["P01"]["deciding_key"] == "total"
    assert rows["P01"]["left"]["rank"] == [0, 0, -1] and rows["P01"]["right"]["rank"] == [0, 0, 0]
    assert rows["P02"]["missing_reasons"] == ["operational failure (reply unavailable)"]
    assert rows["P02"]["shown"] is False and rows["P02"]["human"] == "missing"
    assert rows["P04"]["missing_reasons"] == ["operational failure (reply unavailable)"]
    assert rows["P03"]["machine"] == "A" and rows["P03"]["deciding_key"] == "acceptable"
    assert rows["P05"]["missing_reasons"] == ["unscored (budget)"]
    assert rows["P06"]["missing_reasons"] == ["human blank"] and rows["P06"]["machine"] == "tie"
    s = report["summary"]
    assert (s["total_pairs"], s["shown_pairs"], s["unavailable_pairs"], s["evaluable"]) == (6, 4, 2, 2)
    assert s["exact_matches"] == 0 and s["exact_match_fraction"] == 0.0
    assert s["missing_by_reason"] == {
        "operational failure (reply unavailable)": 2, "unscored (budget)": 1, "human blank": 1,
    }
    assert "Evaluable pairs: 2 of 6" in out
    assert "P02 (operational failure (reply unavailable))" in out and "P05 (unscored (budget))" in out
    # review compare
    json_review = tmp_path / "reports" / "review.json"
    assert cli.main(["review-compare", "--key", str(key_path), "--commitment", str(com_path),
                     "--sheet", str(sheet_path), "--scores-dir", str(scores),
                     "--json-out", str(json_review)]) == 0
    out = capsys.readouterr().out
    review_report = read_json(json_review)
    by = {(c["prompt_version"], c["model"]): c for c in review_report["by_prompt_model"]}
    assert by[("v2", M2)] == {
        "prompt_version": "v2", "model": M2, "shown": 3, "human_accepted": 3,
        "judge_acceptable": 0, "unscored": 1, "unscored_by_reason": {"unscored (budget)": 1},
        "operational_failures": 1, "evaluable": 2, "agree": 0,
    }
    assert by[("v2", M1)]["shown"] == 4 and by[("v2", M1)]["evaluable"] == 4
    assert by[("v2", M1)]["judge_acceptable"] == 2 and by[("v2", M1)]["agree"] == 2
    assert by[("v2", M3)]["operational_failures"] == 1 and by[("v2", M3)]["shown"] == 3
    assert by[("v1", M1)] == {
        "prompt_version": "v1", "model": M1, "shown": 3, "human_accepted": 3,
        "judge_acceptable": 3, "unscored": 0, "unscored_by_reason": {},
        "operational_failures": 1, "evaluable": 3, "agree": 3,
    }
    assert review_report["operational_failures"] == {"failed": 2, "incomplete": 1}
    cell = {(c["case"], c["prompt_version"], c["model"]): c for c in review_report["by_case_prompt_model"]}
    assert cell[("H2", "v2", M3)]["operational_failures"] == 1 and cell[("H2", "v2", M3)]["shown"] == 1
    assert "operational failures not shown: failed 2, incomplete 1" in out


def unbalanced_plan() -> dict[str, Any]:
    plan = compare_plan()
    # first-named model on the left in both cases for the M1-M2 pairing
    plan["pairs"][4] = {"pair_id": "P05", "case": "H2", "left": side(M1, 1), "right": side(M2, 1)}
    return plan


def wrong_samples_plan() -> dict[str, Any]:
    plan = compare_plan()
    plan["pairs"][0] = {"pair_id": "P01", "case": "H1", "left": side(M1, 2), "right": side(M2, 1)}
    plan["pairs"][2] = {"pair_id": "P03", "case": "H1", "left": side(M1, 1), "right": side(M3, 1)}
    return plan


def misnumbered_plan() -> dict[str, Any]:
    plan = compare_plan()
    plan["pairs"][0]["pair_id"], plan["pairs"][1]["pair_id"] = "P02", "P01"
    return plan


def case_order_plan() -> dict[str, Any]:
    plan = compare_plan()
    pairs = plan["pairs"]
    pairs[2], pairs[3] = pairs[3], pairs[2]
    for n, p in enumerate(pairs, start=1):
        p["pair_id"] = f"P{n:02d}"
    return plan


@pytest.mark.parametrize(
    ("make", "message"),
    [
        (unbalanced_plan, "exactly half"),
        (wrong_samples_plan, "sample rule"),
        (misnumbered_plan, "P01, P02, ... in order"),
        (case_order_plan, "three per case in case order"),
    ],
)
def test_plan_that_breaks_the_published_rule_is_refused(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], make: Any, message: str
) -> None:
    private, com = make_plan_files(tmp_path, make())  # hash and metadata are valid
    assert cli.main(verify_args(private, com)) == 1
    err = capsys.readouterr().err
    assert "does not follow the published pair rule" in err and message in err
    assert_no_model_names(err)
    assert not re.search(r"P\d\d", err.replace("P01, P02, ...", ""))
    run_a = make_run(tmp_path, RUN_V1, "v1", ["H1", "H2"])
    run = make_run(tmp_path, RUN_V2, "v2", ["H1", "H2"])
    review, review_com = labelled_review(tmp_path, run_a, run)
    assert cli.main(pair_sheet_cli(private, com, run, tmp_path / "pairs", review, review_com)) == 2
    assert "does not follow the published pair rule" in capsys.readouterr().err
    assert not (tmp_path / "pairs").exists()


def test_review_commitment_run_ids_and_case_ids_are_checked(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    run_a, run_b = two_runs(tmp_path, ["H1", "H2"])
    res = holdout.create_review_sheet([run_a, run_b], tmp_path / "review", tmp_path / "secret" / "review_key.json")
    com = read_json(res.commitment)
    for field, value in (("run_ids", [RUN_V1, "QX-OTHER-RUN"]), ("case_ids", ["H1", "H9"])):
        bad = tmp_path / "public" / f"{field}.json"
        bad.parent.mkdir(exist_ok=True)
        write_json(bad, {**com, field: value})
        assert cli.main(verify_args(res.private_key, bad)) == 1
        assert f"{field} do not match" in capsys.readouterr().err


# ------------------------------------------------------------ randomness (N8)


def test_default_plans_vary_pair_order_and_placement() -> None:
    plans = [holdout.make_pair_plan(CASES4, MODELS, "v2") for _ in range(50)]
    orders = set()
    placements = set()
    per_pairing: list[set[frozenset[str]]] = [set(), set(), set()]
    index = {((M1, 1), (M2, 1)): 0, ((M1, 2), (M3, 1)): 1, ((M2, 2), (M3, 2)): 2}
    for plan in plans:
        assert holdout.plan_rule_problem(plan) is None
        orders.add(tuple(index[first_named(p)[:2]] for p in plan["pairs"] if p["case"] == "H1"))
        left: list[set[str]] = [set(), set(), set()]
        for p in plan["pairs"]:
            first, second, on_left = first_named(p)
            if on_left:
                left[index[(first, second)]].add(p["case"])
        pattern = tuple(frozenset(s) for s in left)
        placements.add(pattern)
        for k in range(3):
            per_pairing[k].add(pattern[k])
    assert len(orders) > 1  # the within-case pair order is shuffled
    assert len(placements) > 1  # placement is drawn, not fixed
    assert all(len(s) > 1 for s in per_pairing)  # each pairing's placement varies


def test_default_review_sheets_vary_reply_order(tmp_path: Path) -> None:
    run_a, run_b = two_runs(tmp_path, ["H1"])
    orders = set()
    for i in range(12):
        res = holdout.create_review_sheet([run_a, run_b], tmp_path / f"review{i}", tmp_path / "secret" / f"key{i}.json")
        blocks = reply_blocks(res.sheet.read_text(encoding="utf-8"))
        orders.add(tuple(blocks[f"H1-{n:02d}"] for n in range(1, 13)))
    assert len(orders) > 1


class SpyRandom(random.SystemRandom):
    calls: list[str] = []

    def shuffle(self, x: Any) -> None:  # type: ignore[override]
        SpyRandom.calls.append("shuffle")
        super().shuffle(x)

    def sample(self, population: Any, k: int, **kw: Any) -> Any:  # type: ignore[override]
        SpyRandom.calls.append("sample")
        return super().sample(population, k, **kw)


def test_real_use_draws_from_system_random(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(holdout.secrets, "SystemRandom", SpyRandom)
    SpyRandom.calls = []
    holdout.make_pair_plan(CASES4, MODELS, "v2")
    assert SpyRandom.calls.count("sample") == 3 and SpyRandom.calls.count("shuffle") == 4
    SpyRandom.calls = []
    run_a, run_b = two_runs(tmp_path, ["H1", "H2"])
    holdout.create_review_sheet([run_a, run_b], tmp_path / "review", tmp_path / "secret" / "key.json")
    assert SpyRandom.calls == ["shuffle", "shuffle"]  # one shuffle per case, from SystemRandom


def test_salts_are_fresh(tmp_path: Path) -> None:
    salts = []
    for i in range(2):
        holdout.create_pair_plan(CASES4, MODELS, "v2", tmp_path / "secret" / f"p{i}.json", tmp_path / "public" / f"c{i}.json")
        salts.append(read_json(tmp_path / "secret" / f"p{i}.json")["salt"])
    assert salts[0] != salts[1] and all(re.fullmatch(r"[0-9a-f]{64}", s) for s in salts)
    run_a, run_b = two_runs(tmp_path, ["H1", "H2"])
    keys = []
    for i in range(2):
        holdout.create_review_sheet([run_a, run_b], tmp_path / f"review{i}", tmp_path / "secret" / f"k{i}.json")
        keys.append(read_json(tmp_path / "secret" / f"k{i}.json")["salt"])
    assert keys[0] != keys[1] and all(re.fullmatch(r"[0-9a-f]{64}", s) for s in keys)



# ------------------------------------------- interrupted (write-ahead) attempts


def pending(record: dict[str, Any], attempt: str) -> dict[str, Any]:
    """The write-ahead pending record for `record`'s attempt."""
    return {**record, "status": "judge_pending", "attempt_id": attempt, "decision": None,
            "judgment": None, "budget_charged_nano": 1}


def test_unscored_reason_with_pending_records() -> None:
    final = {**rec(RUN_V2, "H1", M1, 1, acceptable=False, total=None, status="needs_review"),
             "attempt_id": "a" * 32}
    key, text_sha = final["slot_key"], final["text_sha256"]
    reason = holdout.unscored_reason
    # pending + final: the pending record is ignored
    assert reason([pending(final, "a" * 32), final], key, "judge-v1", text_sha) == (
        "unscored (invalid or failed judgment)"
    )
    # only a pending record: interrupted
    assert reason([pending(final, "b" * 32)], key, "judge-v1", text_sha) == "unscored (attempt interrupted)"
    # a later interrupted attempt after a failed one decides
    later = [pending(final, "a" * 32), final, pending(final, "c" * 32)]
    assert reason(later, key, "judge-v1", text_sha) == "unscored (attempt interrupted)"
    # pending records are never a score
    assert holdout.first_scored([pending(final, "b" * 32)], key, "judge-v1", text_sha) is None


def test_compare_tools_report_interrupted_attempts(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # P05's left reply (M2 s1, H2): its latest attempt was interrupted
    scores = compare_scores()
    interrupted = rec(RUN_V2, "H2", M2, 1, acceptable=False, total=None)
    scores.append(pending(interrupted, "d" * 32))
    # P06's right reply (M2 s2, H2): a pending record paired with its scored final
    scored = next(r for r in scores if r["slot_key"] == interrupted["slot_key"].replace("|1", "|2")
                  and r["status"] == "scored")
    scored["attempt_id"] = "e" * 32
    scores.insert(scores.index(scored), pending(scored, "e" * 32))
    args, _ = setup_compare(tmp_path, {"P01": "A", "P05": "A", "P06": "b"}, scores=scores)
    json_out = tmp_path / "reports" / "pairs.json"
    assert cli.main([*args, "--json-out", str(json_out)]) == 0
    out = capsys.readouterr().out
    rows = {r["pair_id"]: r for r in read_json(json_out)["pairs"]}
    assert rows["P05"]["missing_reasons"] == ["unscored (attempt interrupted)"]
    assert rows["P06"]["machine"] == "B" and rows["P06"]["right"]["rank"] == [1, 0, 6]
    assert "P05 (unscored (attempt interrupted))" in out
    # review compare: an entry whose only attempt is pending
    key_path = tmp_path / "secret" / "review_key.json"
    entries = read_json(key_path)["entries"]
    target = next(e for e in entries.values() if e["run_id"] == RUN_V2)
    case = target["slot_key"].split("|")[1]
    only_pending = pending(
        rec(RUN_V2, case, target["model"], target["sample_index"], acceptable=True, total=8,
            text_sha=target["text_sha256"]),
        "f" * 32,
    )
    others = [
        rec(e["run_id"], e["slot_key"].split("|")[1], e["model"], e["sample_index"],
            acceptable=True, total=8, version=e["prompt_version"], text_sha=e["text_sha256"])
        for e in entries.values() if e is not target
    ]
    scores_dir = tmp_path / "review-scores"
    scores_dir.mkdir()
    for run_id in (RUN_V1, RUN_V2):
        rows_for = [r for r in [*others, only_pending] if r["run_id"] == run_id]
        (scores_dir / f"{run_id}.jsonl").write_text(
            "".join(json.dumps(r) + "\n" for r in rows_for), encoding="utf-8", newline="\n"
        )
    review_json = tmp_path / "reports" / "review.json"
    assert cli.main(["review-compare", "--key", str(key_path),
                     "--commitment", str(tmp_path / "review" / "review_key_commitment.json"),
                     "--sheet", str(tmp_path / "review" / "review_sheet.md"),
                     "--scores-dir", str(scores_dir), "--json-out", str(review_json)]) == 0
    report = read_json(review_json)
    assert [u["reason"] for u in report["unscored"]] == ["unscored (attempt interrupted)"]
