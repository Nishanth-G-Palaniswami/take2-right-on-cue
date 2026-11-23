"""Blind review sheet for the 24 prompt-v3 replies on the original holdout cases H1-H4.

The replies come from run 20261123T004511Z-b08ea8 (the v3 retest, judge-v1 scored). The sheet
shows each case's full transcript and the six replies to it in a shuffled order, under neutral
IDs, with no model name, judge score or suggested label. The ID -> reply mapping is written to
holdout-private/v3-retest-review/review_key.json (gitignored) and committed by salted SHA-256,
the same scheme as holdout/review/review_key_commitment.json.

    uv run --no-sync python scripts/v3_retest_review.py sheet

The sheet is built once; running it again refuses to overwrite.
"""

from __future__ import annotations

import hashlib
import json
import random
import secrets
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from rightoncue import review  # noqa: E402

PUB = REPO / "docs" / "measurements" / "v3-retest-review"
PRIV = REPO / "holdout-private" / "v3-retest-review"
ALGORITHM = (
    'sha256((salt + "\\n" + canonical_json({"entries": entries})).encode("utf-8")).hexdigest(), '
    "where canonical_json(obj) = json.dumps(obj, sort_keys=True, ensure_ascii=False, "
    'separators=(",", ":"))'
)


def canonical(obj: object) -> str:
    return json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def sheet() -> int:
    if (PUB / "review_sheet.md").exists() or (PRIV / "review_key.json").exists():
        raise SystemExit("the sheet already exists; it is built once")
    run_dir, scores_path = review.saved_runs(review.load_holdout())["v3"]
    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    turns = {c["case_id"]: c["turns"] for c in manifest["cases"]}
    slots = [json.loads(x) for x in (run_dir / "slots.jsonl").read_text(encoding="utf-8").splitlines()]
    slots = [s for s in slots if s["case_id"] in review.HOLDOUT_CASES]
    if len(slots) != 24 or any(s["status"] != "ok" or not (s["output_text"] or "").strip() for s in slots):
        raise SystemExit("expected 24 completed replies on H1-H4")

    rng = random.SystemRandom()
    entries: list[dict] = []
    lines = [
        "# Prompt v3 on the original holdout cases: blind review sheet",
        "",
        "These are the 24 replies that prompt v3 produced on H1–H4 (three models, two samples each).",
        "Label each reply as Riley's next turn by your own judgment: write `y` (accept) or `n` (reject)",
        "after the colon on its Accept line. A reason is optional.",
        "",
        "- **Hidden here:** the model, the judge-v1 scores and any suggested label. Replies to each case are shuffled.",
        "- **Blindness depends on the order you do things.** The same replies, with model names and",
        "  judge-v1 verdicts, are already in the repo (`docs/measurements/prompt-v3/regression/`) and in",
        "  the app's saved comparison (prompt v3). Please label every item before opening those, the",
        "  v3 regression results, or `holdout-private/v3-retest-review/`.",
        "- **Planned comparison.** Individual agreement, defined as for the original 31 of 47: judge-v1's",
        "  acceptable / not acceptable against your y / n, over replies with a judge verdict.",
        "",
        "Used an AI assistant while labelling (yes/no):",
        "",
    ]
    for case_id in review.HOLDOUT_CASES:
        case_slots = [s for s in slots if s["case_id"] == case_id]
        rng.shuffle(case_slots)
        lines += ["---", "", f"## Case {case_id}", "", "Conversation so far:", ""]
        for t in turns[case_id]:
            lines += [f"> **{'Riley' if t['role'] == 'agent' else 'Applicant'}:** {t['utterance']}", ">"]
        lines.pop()
        lines.append("")
        for n, s in enumerate(case_slots, start=1):
            rid = f"V3-{case_id}-{n:02d}"
            entries.append({"neutral_id": rid, "slot_key": s["slot_key"], "case_id": case_id,
                            "requested_model": s["requested_model"], "sample_index": s["sample_index"]})
            lines += [f"### {rid}", "", "Riley's proposed next turn:", "",
                      "> " + s["output_text"].strip().replace("\n", "\n> "), "",
                      f"Accept {rid}? (y/n):", "", "Reason (optional):", ""]

    salt = secrets.token_hex(16)
    digest = hashlib.sha256((salt + "\n" + canonical({"entries": entries})).encode("utf-8")).hexdigest()
    PUB.mkdir(parents=True, exist_ok=True)
    PRIV.mkdir(parents=True, exist_ok=True)
    (PRIV / "review_key.json").write_text(
        json.dumps({"salt": salt, "entries": entries}, indent=1, ensure_ascii=False) + "\n",
        encoding="utf-8", newline="\n",
    )
    (PUB / "review_sheet.md").write_text("\n".join(lines), encoding="utf-8", newline="\n")
    sheet_sha = hashlib.sha256((PUB / "review_sheet.md").read_bytes()).hexdigest()
    commitment = {
        "schema": "v3-retest-review-key-commitment-1",
        "algorithm": ALGORITHM,
        "sha256": digest,
        "run_id": run_dir.name,
        "scores_file_sha256": hashlib.sha256(scores_path.read_bytes()).hexdigest(),
        "case_ids": list(review.HOLDOUT_CASES),
        "replies": len(entries),
        "review_sheet_sha256": sheet_sha,
    }
    (PUB / "review_key_commitment.json").write_text(
        json.dumps(commitment, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    print(f"sheet: {len(entries)} replies; key commitment {digest}")
    return 0


def main(argv: list[str]) -> int:
    if argv[1:] == ["sheet"]:
        return sheet()
    raise SystemExit("usage: v3_retest_review.py sheet")


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
