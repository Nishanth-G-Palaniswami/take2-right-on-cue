"""judge-v4 calibration: score fixed examples with a judge version and check criteria.

Uses the scorer's own request builder, validator and decision rule (rightoncue.scoring).
Nothing in runs/ or scores/ is written. Examples come from
docs/measurements/judge-v4/examples.json; turns come from cases/dev/<case>.jsonl
(identical to the files the saved runs used); criteria come from cases/notes.toml.

  uv run python scripts/judge_calibration.py run --judge-version judge-v4 --draw 1 --cap-usd 0.30
  uv run python scripts/judge_calibration.py evaluate --judge-version judge-v4

Cost control: before every call (retries included), the spend already recorded in the
output directory plus the call's maximum cost (request UTF-8 bytes x input price +
max_output_tokens x output price, the budget guard's bound) must fit within --cap-usd,
or the script stops. The client is built with max_retries=0, so no hidden SDK retries.
A judgment that needs review or fails is retried once, immediately, within its draw.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

from rightoncue import scoring
from rightoncue.transcript import parse_transcript

REPO = Path(__file__).resolve().parents[1]
EXAMPLES = REPO / "docs/measurements/judge-v4/examples.json"
OUT = REPO / "docs/measurements/judge-v4"
OUT_DIR = OUT
IN_NANO, OUT_NANO = 750, 4_500  # gpt-5.4-mini nano-USD per token (PRD rates)


def load_examples() -> list[dict[str, Any]]:
    examples = json.loads(EXAMPLES.read_text(encoding="utf-8"))
    for e in examples:
        if e["source"] == "saved":
            run = e["slot_key"].split("|")[0]
            texts = [
                json.loads(line)["output_text"]
                for line in (REPO / "runs" / run / "slots.jsonl").read_text(encoding="utf-8").split("\n")
                if line.strip() and json.loads(line)["slot_key"] == e["slot_key"]
            ]
            if len(texts) != 1:
                raise SystemExit(f"{e['id']}: expected exactly one saved record, found {len(texts)}")
            e["text"] = texts[0]
    return examples


def max_cost_nano(request: dict[str, Any]) -> int:
    canonical = json.dumps(request, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return len(canonical.encode("utf-8")) * IN_NANO + int(request["max_output_tokens"]) * OUT_NANO


def records(judge_version: str) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for p in sorted(OUT_DIR.glob(f"{judge_version}-draw-*.jsonl")):
        out += [json.loads(x) for x in p.read_text(encoding="utf-8").split("\n") if x.strip()]
    return out


def run(args: argparse.Namespace) -> int:
    judge = scoring.load_judge_prompt(args.judge_version)
    criteria = scoring.load_criteria(REPO / "cases/notes.toml")
    examples = load_examples()
    out_path = OUT_DIR / f"{args.judge_version}-draw-{args.draw}.jsonl"
    if out_path.exists():
        raise SystemExit(f"{out_path.name} exists; draws are write-once")
    cap = round(args.cap_usd * 1e9)
    spent = sum(r["cost_nano"] for r in records(args.judge_version))
    if args.dry_run:
        client: Any = _FakeClient()
    else:
        from dotenv import load_dotenv
        from openai import OpenAI

        load_dotenv(REPO / ".env", override=False)
        client = OpenAI(max_retries=0)
    calls = 0
    with open(out_path, "x", encoding="utf-8", newline="\n") as fh:
        for e in examples:
            turns = parse_transcript((REPO / f"cases/dev/{e['case']}.jsonl").read_text(encoding="utf-8"))
            request = scoring.build_judge_request(
                judge.text, turns, e["text"], criteria.get(e["case"]), scorer_version=judge.scorer_version
            )
            for attempt in (1, 2):
                bound = max_cost_nano(request)
                if spent + bound > cap:
                    print(f"STOPPED by cap before {e['id']} attempt {attempt}: spent {spent/1e9:.5f}, max {bound/1e9:.5f}, cap {cap/1e9:.2f}")
                    return 3
                rec: dict[str, Any] = {"example_id": e["id"], "draw": args.draw, "attempt": attempt,
                                       "judge_prompt_version": judge.version, "judge_prompt_sha256": judge.sha256,
                                       "judge_request_sha256": scoring.request_sha256(request)}
                calls += 1
                try:
                    resp = client.responses.create(**request)
                    dump = resp.model_dump(mode="json")
                    usage = (dump.get("usage") or {})
                    tin, tout = usage.get("input_tokens"), usage.get("output_tokens")
                    cost = tin * IN_NANO + tout * OUT_NANO if isinstance(tin, int) and isinstance(tout, int) else bound
                    judgment, errors = scoring.validate_judge_output(
                        resp.status, resp.output_text, turns, e["text"], scorer_version=judge.scorer_version
                    )
                    rec.update(response_id=dump.get("id"), output_text=resp.output_text, usage=usage, cost_nano=cost)
                    if judgment is None:
                        rec.update(status="needs_review", validation_errors=errors)
                    else:
                        dec = scoring.decide(scoring.check_structure(e["text"]), judgment)
                        rec.update(status="scored", judgment=judgment.model_dump(mode="json"), decision=dec.to_dict())
                except Exception as exc:  # recorded and charged at its maximum, then retried once
                    rec.update(status="judge_failed", error=f"{type(exc).__name__}: {exc}", cost_nano=bound)
                spent += rec["cost_nano"]
                fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
                fh.flush()
                if rec["status"] == "scored":
                    break
    print(f"draw {args.draw}: {calls} calls; calibration spend now ${spent/1e9:.5f} of ${cap/1e9:.2f}")
    return 0


def final_by_example(recs: list[dict[str, Any]]) -> dict[tuple[int, str], dict[str, Any]]:
    out: dict[tuple[int, str], dict[str, Any]] = {}
    for r in recs:
        out[(r["draw"], r["example_id"])] = r  # last attempt per example per draw
    return out


def evaluate(args: argparse.Namespace) -> int:
    examples = {e["id"]: e for e in json.loads(EXAMPLES.read_text(encoding="utf-8"))}
    recs = records(args.judge_version)
    final = final_by_example(recs)
    draws = sorted({d for d, _ in final})
    first_attempts = [r for r in recs if r["attempt"] == 1]
    invalid_first = sum(r["status"] != "scored" for r in first_attempts)

    def verdict(r: dict[str, Any] | None) -> dict[str, Any]:
        if r is None or r["status"] != "scored":
            return {"scored": False}
        present = [t for t, v in r["judgment"]["critical_violations"].items() if v["present"]]
        return {"scored": True, "acceptable": r["decision"]["acceptable"],
                "na": r["judgment"]["next_action"]["score"], "present": present,
                "scores": "".join(str(r["decision"]["scores"][d]) for d in scoring.DIMENSIONS)}

    by_group: dict[str, list[tuple[str, list[dict[str, Any]]]]] = defaultdict(list)
    for eid, e in examples.items():
        vs = [verdict(final.get((d, eid))) for d in draws]
        by_group[e["group"]].append((eid, vs))
        print(f"{e['group']:18} {eid:24} " + " | ".join(
            (f"{'PASS' if v['acceptable'] else 'FAIL'} {v['scores']}" + (f" present={v['present']}" if v['present'] else ""))
            if v["scored"] else "UNSCORED" for v in vs))

    def ok_all(group: str, pred: Any) -> tuple[int, int]:
        cells = [v for _, vs in by_group[group] for v in vs]
        return sum(1 for v in cells if v["scored"] and pred(v)), len(cells)

    res = {}
    # C1 genuine violations: intended type present and not acceptable, every draw
    c1 = [(v["scored"] and (examples[eid]["expect"].split(":")[1] in v["present"]) and not v["acceptable"])
          for eid, vs in by_group["genuine_violation"] for v in vs]
    res["C1 genuine violations caught (type present, not acceptable)"] = (sum(c1), len(c1), sum(c1) == len(c1))
    # C2 no present entry on any saved (clean) example
    clean = [v for g, items in by_group.items() if g != "genuine_violation" for _, vs in items for v in vs]
    c2_bad = sum(1 for v in clean if v["scored"] and v["present"])
    c2_unscored = sum(1 for v in clean if not v["scored"])
    res["C2 false critical flags on clean saved replies"] = (c2_bad, len(clean), c2_bad == 0 and c2_unscored == 0)
    # C3 D1 regression acceptable in every draw; no other clean D1 reply fails in every draw
    k, n = ok_all("d1_regression", lambda v: v["acceptable"])
    d1_fail_all = sum(1 for _, vs in by_group["d1_clean"] if all(v["scored"] and not v["acceptable"] for v in vs))
    res["C3 D1 regression replies acceptable (and no clean D1 reply fails every draw)"] = (k, n, k == n and d1_fail_all == 0)
    # C4 outcome-only acceptable every draw
    k, n = ok_all("d3_outcome_only", lambda v: v["acceptable"])
    res["C4 D3 outcome-only acceptable"] = (k, n, k == n)
    # C5 action-only and two-part: not acceptable with next action <= 1, at least 13 of 14
    k1, n1 = ok_all("d3_action_only", lambda v: (not v["acceptable"]) and v["na"] <= 1)
    k2, n2 = ok_all("d3_two_part", lambda v: (not v["acceptable"]) and v["na"] <= 1)
    res["C5 D3 action-only + two-part rejected with next action <= 1"] = (k1 + k2, n1 + n2, k1 + k2 >= (n1 + n2) - 1)
    # C6 D4 controls
    rep = [v for eid, vs in by_group["d4_control"] if eid.endswith("reprobe") for v in vs]
    mov = [v for eid, vs in by_group["d4_control"] if eid.endswith("moveon") for v in vs]
    c6 = all(v["scored"] and not v["acceptable"] for v in rep) and all(v["scored"] and v["acceptable"] for v in mov)
    res["C6 D4 controls (re-probe fails, move-on passes)"] = (sum(v["scored"] and not v["acceptable"] for v in rep) + sum(v["scored"] and v["acceptable"] for v in mov), len(rep) + len(mov), c6)
    # C7 validity
    res["C7 invalid first attempts (at most 3)"] = (invalid_first, len(first_attempts), invalid_first <= 3)
    print()
    for name, (k, n, ok) in res.items():
        print(f"{'MET    ' if ok else 'NOT MET'} {name}: {k}/{n}")
    spent = sum(r["cost_nano"] for r in recs)
    print(f"\nall criteria met: {all(ok for _, _, ok in res.values())}; draws {draws}; calls {len(recs)}; spend ${spent/1e9:.5f}")
    return 0


class _FakeClient:
    """Offline stand-in for --dry-run: returns a valid scorer-2 judgment with all 2s."""

    class responses:  # noqa: N801
        @staticmethod
        def create(**request: Any) -> Any:
            dim = {"rationale": "dry run", "evidence": [], "score": 2}
            crit = {t: {"rationale": "dry run", "evidence": [], "present": False} for t in scoring.CRITICAL_TYPES}
            body = json.dumps({**{d: dim for d in scoring.DIMENSIONS}, "critical_violations": crit})

            class R:
                status, output_text, id = "completed", body, "dry"

                @staticmethod
                def model_dump(mode: str = "json") -> dict[str, Any]:
                    return {"id": "dry", "usage": {"input_tokens": 0, "output_tokens": 0}}

            return R()


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("--judge-version", required=True)
    r.add_argument("--draw", type=int, required=True)
    r.add_argument("--cap-usd", type=float, required=True)
    r.add_argument("--dry-run", action="store_true")
    ev = sub.add_parser("evaluate")
    ev.add_argument("--judge-version", required=True)
    for s in (r, ev):
        s.add_argument("--out-dir", type=Path, default=OUT)
    a = ap.parse_args()
    global OUT_DIR
    OUT_DIR = a.out_dir
    return run(a) if a.cmd == "run" else evaluate(a)


if __name__ == "__main__":
    raise SystemExit(main())
