"""judge-v5 fresh check and known regressions. Pre-registered in
docs/measurements/2026-11-22-judge-v5-plan.md.

  uv run --no-sync python scripts/judge_v5_experiment.py sheet
  uv run --no-sync python scripts/judge_v5_experiment.py estimate
  uv run --no-sync python scripts/judge_v5_experiment.py run --stage fresh --judge judge-v5 --cap-usd 0.75
  uv run --no-sync python scripts/judge_v5_experiment.py run --stage regression --judge judge-v5 --cap-usd 0.75
  uv run --no-sync python scripts/judge_v5_experiment.py report --write

`sheet` builds the blind sheet once from holdout-private/judge-v5/items.json (written by a separate
item author). `run` refuses the fresh stage until every Accept line on the sheet has y or n.

Cost control, as scripts/cert_guidance_experiment.py: before every call (retries included), the
spend recorded in docs/measurements/judge-v5/results/ plus the call's maximum cost must fit
within --cap-usd, or the script stops. The client is built with max_retries=0. A judgment that
needs review or fails is retried once, immediately. Output files are write-once.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import re
import secrets
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from rightoncue import scoring  # noqa: E402
from rightoncue.transcript import Turn  # noqa: E402

PUB = REPO / "docs/measurements/judge-v5"
PRIV = REPO / "holdout-private/judge-v5"
ITEMS, KEY, SHEET = PRIV / "items.json", PRIV / "key.json", PUB / "review_sheet.md"
SHEET_IN_GIT = "docs/measurements/judge-v5/review_sheet.md"  # the committed sheet, for verify()
RESULTS = PUB / "results"
JUDGES = ("judge-v5", "judge-v1")
DRAWS = {"judge-v5": 2, "judge-v1": 1}
IN_NANO, OUT_NANO = 750, 4_500  # gpt-5.4-mini nano-USD per token (PRD rates)
PLANNING_NANO = 4_000_000  # $0.004 per call, the plan's planning figure
BOM, CRLF, LF = "\ufeff", "\r\n", "\n"
ACCEPT_LINE = re.compile(r"^Accept (J\d\d)\? \(y/n\):[ \t]*(.*?)[ \t]*$", re.MULTILINE)

# conversation kind -> the reply intents the author writes for it (the plan's table)
KINDS: dict[str, tuple[str, ...]] = {
    "confirmed": ("moves_on", "optional_question", "reasks_confirmed", "stacked_optional_behavioral"),
    "currency_missing": ("asks_currency", "optional_instead", "moves_on_unconfirmed"),
    "named_optional": ("asks_named", "different_optional"),
    "availability_only": ("disclose_permission", "disclose_permission_mentions_screening", "asks_license"),
    "premature_screening": ("recovery_pause", "continues_screening", "permission_plus_cert"),
    "withdrawal": ("stops", "screens_after_withdrawal"),
    "excerpt": ("appropriate_next",),
}
CERT_KINDS = ("confirmed", "currency_missing", "named_optional")
CONSENT_VIOLATION_INTENTS = ("asks_license", "continues_screening", "permission_plus_cert", "screens_after_withdrawal")
# One-move criteria for the certification path: H2's frozen text for the confirmed conversations,
# D2's made generic (no case-specific detail) for the currency conversation.
D2_GENERIC: scoring.Criteria = {
    "expected_action": "Acknowledge the certifications given and ask, in one focused question, whether the required BLS and ACLS are current.",
    "good_if": ["Acknowledges what the applicant listed.", "Asks once whether BLS and ACLS are current."],
    "fail_if": [
        "Moves on to the behavioral questions without confirming that BLS and ACLS are current.",
        "Asks again which certifications the applicant holds.",
        "Stacks the currency question with a separate request.",
    ],
}
REGRESSION_RUNS = {
    "D1": (REPO / "runs/20261121T023359Z-455c41", ("D1",), 2),
    "v3": (REPO / "docs/measurements/prompt-v3/regression/runs/20261123T004511Z-b08ea8", ("H1", "H2"), 1),
}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_once(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "x", encoding="utf-8", newline="\n") as fh:
        fh.write(text)


# ----------------------------------------------------------------------- items


def load_items() -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]]]:
    data = json.loads(ITEMS.read_text(encoding="utf-8"))
    convs, items = data["conversations"], data["items"]
    kinds = sorted(c["kind"] for c in convs.values())
    if kinds != sorted(KINDS):
        raise SystemExit(f"expected one conversation of each kind {sorted(KINDS)}, got {kinds}")
    for name, conv in convs.items():
        conv["turns_parsed"] = [Turn.model_validate(t) for t in conv["turns"]]
        want = sorted(KINDS[conv["kind"]])
        got = sorted(i["intent"] for i in items if i["conversation"] == name)
        if got != want:
            raise SystemExit(f"conversation {name} ({conv['kind']}): intents {got}, expected {want}")
    if len(items) != 18:
        raise SystemExit(f"expected 18 items, got {len(items)}")
    return convs, items


def sheet() -> int:
    if SHEET.exists() or KEY.exists():
        raise SystemExit("the sheet already exists; it is built once")
    convs, items = load_items()
    order = list(range(len(items)))
    random.SystemRandom().shuffle(order)
    key: dict[str, Any] = {"salt": secrets.token_hex(16), "items": {}}
    lines = [
        "# judge-v5 fresh check: blind label sheet",
        "",
        "Label each reply as Riley's next turn: `y` if it is an acceptable next turn, `n` if not, by your own judgment of a good recruiter turn.",
        "",
        "- Each item shows the conversation so far and one proposed reply. Several items share a conversation, and one conversation starts partway through a call.",
        "- These items are new. They were written by a separate agent that did not see the judge-v5 prompt; the author's intent for each item is sealed in `holdout-private/judge-v5/` and committed by hash.",
        "- Please label every item before opening `holdout-private/judge-v5/` or seeing any score. Scoring refuses to start until every Accept line has y or n.",
        "- A reason is optional. Note below whether you used an AI assistant.",
        "",
        "Used an AI assistant while labelling (yes/no):",
        "",
    ]
    for n, idx in enumerate(order, start=1):
        rid = f"J{n:02d}"
        item = items[idx]
        key["items"][rid] = {"index": idx, "conversation": item["conversation"], "intent": item["intent"]}
        lines += ["---", "", f"## {rid}", "", "Conversation so far:", ""]
        for t in convs[item["conversation"]]["turns"]:
            lines += [f"> **{'Riley' if t['role'] == 'agent' else 'Applicant'}:** {t['utterance']}", ">"]
        lines.pop()
        lines += ["", "Riley's proposed next turn:", "", "> " + item["reply"].strip(), "",
                  f"Accept {rid}? (y/n):", "", "Reason (optional):", ""]
    write_once(SHEET, "\n".join(lines))
    write_once(KEY, json.dumps(key, indent=1) + "\n")
    commitment = {
        "private_files": {"items.json": sha(ITEMS), "key.json": sha(KEY)},
        "public_files": {"review_sheet.md": sha(SHEET)},
        "judge_v5_prompt_sha256": scoring.JUDGE_PROMPTS["judge-v5"][1],
    }
    write_once(PUB / "commitment.json", json.dumps(commitment, indent=1) + "\n")
    print(f"sheet: {len(items)} items; commitment written")
    return 0


def verify() -> None:
    c = json.loads((PUB / "commitment.json").read_text(encoding="utf-8"))
    for name, digest in c["private_files"].items():
        if sha(PRIV / name) != digest:
            raise SystemExit(f"{name} does not match the commitment")
    if sha(SHEET) == c["public_files"]["review_sheet.md"]:
        return
    # A labelled sheet may differ in its labels, reasons, line endings or a BOM, never in what
    # was shown: every item heading and every quoted conversation or reply line must match the
    # sheet as committed (found in git by the hash in the commitment).
    import subprocess

    first = subprocess.run(
        ["git", "log", "--format=%H", "--diff-filter=A", "--", SHEET_IN_GIT],
        cwd=REPO, capture_output=True, text=True, check=True,
    ).stdout.split()[-1]
    committed = subprocess.run(
        ["git", "show", f"{first}:{SHEET_IN_GIT}"],
        cwd=REPO, capture_output=True, check=True,
    ).stdout
    if hashlib.sha256(committed).hexdigest() != c["public_files"]["review_sheet.md"]:
        raise SystemExit("the sheet in git does not match the commitment")
    if shown(committed.decode("utf-8")) != shown(sheet_text()):
        raise SystemExit("review_sheet.md changes an item heading, a conversation or a reply")


def sheet_text() -> str:
    """The sheet as the labeller saved it: a BOM and CRLF line endings are tolerated."""
    return SHEET.read_text(encoding="utf-8").lstrip(BOM).replace(CRLF, LF)


def shown(text: str) -> list[str]:
    """What the labeller was shown: item headings and quoted lines, in order."""
    return [line.rstrip() for line in text.split("\n") if line.startswith("## J") or line.startswith(">")]


def labels() -> dict[str, str]:
    return {m.group(1): m.group(2).strip().lower() for m in ACCEPT_LINE.finditer(sheet_text())}


# ---------------------------------------------------------------------- jobs


@dataclass(frozen=True)
class Job:
    stage: str
    item: str  # J-id, maya-live, or a slot key
    path: str  # "criteria" or "general"
    draw: int
    turns: list[Turn]
    reply: str
    criteria: scoring.Criteria | None


def fresh_jobs(judge: str) -> list[Job]:
    verify()
    convs, items = load_items()
    key = json.loads(KEY.read_text(encoding="utf-8"))["items"]
    h2 = scoring.load_criteria(REPO / "cases/notes.toml")["H2"]
    jobs: list[Job] = []
    for rid in sorted(key):
        item = items[key[rid]["index"]]
        conv = convs[item["conversation"]]
        paths: list[tuple[str, scoring.Criteria | None]] = [("general", None)]
        if conv["kind"] in CERT_KINDS:
            paths.insert(0, ("criteria", D2_GENERIC if conv["kind"] == "currency_missing" else h2))
        for path, crit in paths:
            for draw in range(1, DRAWS[judge] + 1):
                jobs.append(Job("fresh", rid, path, draw, conv["turns_parsed"], item["reply"], crit))
    return jobs


def regression_jobs(judge: str) -> list[Job]:
    jobs: list[Job] = []
    maya = json.loads((PUB / "regression/maya-live.json").read_text(encoding="utf-8"))
    turns = [Turn.model_validate(t) for t in maya["turns"]]
    for draw in range(1, DRAWS[judge] + 1):
        jobs.append(Job("regression", "maya-live", "general", draw, turns, maya["reply"], None))
    if judge != "judge-v5":
        return jobs  # judge-v1 re-checks only the reported Maya verdict
    notes = scoring.load_criteria(REPO / "cases/notes.toml")
    for run_dir, cases, draws in REGRESSION_RUNS.values():
        manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
        case_turns = {c["case_id"]: [Turn.model_validate(t) for t in c["turns"]] for c in manifest["cases"]}
        for line in (run_dir / "slots.jsonl").read_text(encoding="utf-8").splitlines():
            s = json.loads(line)
            if s["case_id"] in cases and s["status"] == "ok":
                for draw in range(1, draws + 1):
                    jobs.append(Job("regression", s["slot_key"], "criteria", draw, case_turns[s["case_id"]],
                                    s["output_text"], notes[s["case_id"]]))
    return jobs


def jobs_for(stage: str, judge: str) -> list[Job]:
    return fresh_jobs(judge) if stage == "fresh" else regression_jobs(judge)


def request_for(job: Job, judge: scoring.JudgePrompt) -> dict[str, Any]:
    return scoring.build_judge_request(judge.text, job.turns, job.reply, job.criteria, scorer_version=judge.scorer_version)


def max_cost_nano(request: dict[str, Any]) -> int:
    canonical = json.dumps(request, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return len(canonical.encode("utf-8")) * IN_NANO + int(request["max_output_tokens"]) * OUT_NANO


def estimate() -> int:
    total_n, total_max = 0, 0
    for stage in ("fresh", "regression"):
        for name in JUDGES:
            judge = scoring.load_judge_prompt(name)
            jobs = jobs_for(stage, name)
            bounds = [max_cost_nano(request_for(j, judge)) for j in jobs]
            total_n += len(jobs)
            total_max += sum(bounds)
            print(f"{stage:10} {name}: {len(jobs):3} first attempts; worst-case bound per call up to "
                  f"${max(bounds)/1e9:.6f}; expected about ${len(jobs) * PLANNING_NANO * 1.15 / 1e9:.3f} with ~15% retries")
    print(f"total: {total_n} first attempts; expected about ${total_n * PLANNING_NANO * 1.15 / 1e9:.3f}; "
          f"worst case if every call hit its bound ${total_max/1e9:.3f} (the run cap stops well before that)")
    return 0


# ------------------------------------------------------------------------ run


def records() -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for p in sorted(RESULTS.glob("*.jsonl")):
        out += [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines() if x.strip()]
    return out


class _FakeClient:
    """Offline stand-in for --dry-run: a valid judgment with all 2s and no violation."""

    class responses:  # noqa: N801
        @staticmethod
        def create(**request: Any) -> Any:
            dim = {"rationale": "dry run", "evidence": [], "score": 2}
            body = json.dumps({**{d: dim for d in scoring.DIMENSIONS}, "critical_violations": []})

            class R:
                status, output_text, id = "completed", body, "dry"

                @staticmethod
                def model_dump(mode: str = "json") -> dict[str, Any]:
                    return {"id": "dry", "usage": {"input_tokens": 0, "output_tokens": 0}}

            return R()


def run(args: argparse.Namespace) -> int:
    if args.dry_run and args.out_dir is None:
        raise SystemExit("--dry-run needs --out-dir, so it never takes the write-once results file")
    # every stage waits for the labels, so no score exists before the sheet is complete
    verify()
    lab = labels()
    if len(lab) != 18 or any(v not in ("y", "n") for v in lab.values()):
        raise SystemExit("label every item on the sheet (y or n) before any stage is scored")
    judge = scoring.load_judge_prompt(args.judge)
    out_path = (args.out_dir or RESULTS) / f"{args.stage}-{args.judge}.jsonl"
    if out_path.exists():
        raise SystemExit(f"{out_path} exists; each stage is scored once per judge")
    cap = round(args.cap_usd * 1e9)
    spent = sum(r["cost_nano"] for r in records())
    if args.dry_run:
        client: Any = _FakeClient()
    else:
        from dotenv import load_dotenv
        from openai import OpenAI

        load_dotenv(REPO / ".env", override=False)
        client = OpenAI(max_retries=0)
    calls = 0
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "x", encoding="utf-8", newline="\n") as fh:
        for job in jobs_for(args.stage, args.judge):
            request = request_for(job, judge)
            for attempt in (1, 2):
                bound = max_cost_nano(request)
                if spent + bound > cap:
                    print(f"STOPPED by the cap before {job.item} {job.path} draw {job.draw} attempt {attempt}: "
                          f"spent ${spent/1e9:.6f}, call maximum ${bound/1e9:.6f}, cap ${cap/1e9:.2f}")
                    return 3
                rec: dict[str, Any] = {
                    "stage": job.stage, "item": job.item, "path": job.path, "draw": job.draw, "attempt": attempt,
                    "judge_prompt_version": judge.version, "judge_prompt_sha256": judge.sha256,
                    "scorer_version": judge.scorer_version, "judge_request_sha256": scoring.request_sha256(request),
                    "dry_run": bool(args.dry_run),
                }
                calls += 1
                try:
                    resp = client.responses.create(**request)
                    dump = resp.model_dump(mode="json")
                    usage = dump.get("usage") or {}
                    tin, tout = usage.get("input_tokens"), usage.get("output_tokens")
                    cost = tin * IN_NANO + tout * OUT_NANO if isinstance(tin, int) and isinstance(tout, int) else bound
                    judgment, errors = scoring.validate_judge_output(
                        resp.status, resp.output_text, job.turns, job.reply, scorer_version=judge.scorer_version
                    )
                    rec.update(response_id=dump.get("id"), output_text=resp.output_text, usage=usage, cost_nano=cost)
                    if judgment is None:
                        rec.update(status="needs_review", validation_errors=errors)
                    else:
                        dec = scoring.decide(scoring.check_structure(job.reply), judgment)
                        rec.update(status="scored", decision=dec.to_dict(),
                                   listed=[t for t, _, _ in scoring._violations(judgment)])
                except Exception as exc:  # recorded and charged at its maximum, then retried once
                    rec.update(status="judge_failed", error=f"{type(exc).__name__}: {exc}", cost_nano=bound)
                spent += rec["cost_nano"]
                fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
                fh.flush()
                if rec["status"] == "scored":
                    break
    print(f"{args.stage} {args.judge}: {calls} calls; experiment spend now ${spent/1e9:.6f} of ${cap/1e9:.2f}")
    return 0


# --------------------------------------------------------------------- report

SWC = "screening_without_consent"


def finals(path: Path) -> dict[tuple[str, str, int], dict[str, Any]]:
    """(item, path, draw) -> the scored record, or {"status": "unscored"} after the retry."""
    out: dict[tuple[str, str, int], dict[str, Any]] = {}
    if not path.exists():
        return out
    for line in path.read_text(encoding="utf-8").splitlines():
        r = json.loads(line)
        k = (r["item"], r["path"], r["draw"])
        if r["status"] == "scored":
            out[k] = r
        else:
            out.setdefault(k, {"status": "unscored"})
    return out


def verdict(r: dict[str, Any] | None) -> str:
    if not r or r.get("status") != "scored":
        return "unscored"
    return "acceptable" if r["decision"]["acceptable"] else "not acceptable"


def lists_swc(r: dict[str, Any] | None) -> bool:
    return bool(r and r.get("status") == "scored" and SWC in r.get("listed", []))


def report(args: argparse.Namespace) -> int:
    verify()
    results = args.results_dir or RESULTS
    lab = labels() if args.labels is None else {
        m.group(1): m.group(2).strip().lower()
        for m in ACCEPT_LINE.finditer(args.labels.read_text(encoding="utf-8").lstrip(BOM).replace(CRLF, LF))}
    if len(lab) != 18 or any(v not in ("y", "n") for v in lab.values()):
        raise SystemExit("the sheet needs y or n on every Accept line")
    convs, items = load_items()
    key = json.loads(KEY.read_text(encoding="utf-8"))["items"]
    kind = {rid: convs[k["conversation"]]["kind"] for rid, k in key.items()}
    intent = {rid: k["intent"] for rid, k in key.items()}
    v5, v1 = finals(results / "fresh-judge-v5.jsonl"), finals(results / "fresh-judge-v1.jsonl")
    reg5, reg1 = finals(results / "regression-judge-v5.jsonl"), finals(results / "regression-judge-v1.jsonl")
    want = {(j.item, j.path, j.draw) for j in fresh_jobs("judge-v5")}
    want1 = {(j.item, j.path, j.draw) for j in fresh_jobs("judge-v1")}
    agree = lambda rid, r: verdict(r) == ("acceptable" if lab[rid] == "y" else "not acceptable")  # noqa: E731

    # P1: no false acceptances
    n_keys = [k for k in want if lab[k[0]] == "n"]
    n_acc = [k for k in n_keys if verdict(v5.get(k)) == "acceptable"]
    both = sorted({(i, p) for i, p, _ in n_acc if all(verdict(v5.get((i, p, d))) == "acceptable" for d in (1, 2))})
    p1 = len(n_acc) <= 1 and not both
    # P2: the certification fix, per criteria path
    p2_rates = {}
    for path in ("criteria", "general"):
        ks = [k for k in want if k[1] == path and kind[k[0]] in CERT_KINDS and lab[k[0]] == "y"]
        scored = [k for k in ks if verdict(v5.get(k)) != "unscored"]
        acc = [k for k in scored if verdict(v5.get(k)) == "acceptable"]
        p2_rates[path] = (len(acc), len(scored))
    p2 = all(s > 0 and a / s >= 0.9 for a, s in p2_rates.values())
    # P3: consent
    consent_y = [k for k in want if kind[k[0]] not in CERT_KINDS and lab[k[0]] == "y"]
    y_flagged = sorted(k for k in consent_y if lists_swc(v5.get(k)))
    viol_n = [k for k in want if intent[k[0]] in CONSENT_VIOLATION_INTENTS and lab[k[0]] == "n"
              and verdict(v5.get(k)) != "unscored"]
    viol_missed = sorted(k for k in viol_n if not lists_swc(v5.get(k)))
    p3 = not y_flagged and len(viol_missed) <= 1
    # P4: overall agreement (unscored counts as disagreement)
    a5 = sum(agree(k[0], v5.get(k)) for k in want)
    a1 = sum(agree(k[0], v1.get(k)) for k in want1)
    p4 = a5 / len(want) >= 0.85 and a5 / len(want) >= a1 / len(want1)
    # P5: unscored and self-contradictions
    unscored5 = sorted(k for k in want if verdict(v5.get(k)) == "unscored")
    contradictions = 0
    for name in ("fresh-judge-v5.jsonl", "regression-judge-v5.jsonl"):
        p = results / name
        if p.exists():
            for line in p.read_text(encoding="utf-8").splitlines():
                r = json.loads(line)
                contradictions += any("contradicts itself" in e for e in r.get("validation_errors", []))
    p5 = len(unscored5) <= 2
    # P6: known regressions
    def reg(prefix: str) -> list[dict[str, Any] | None]:
        return [r for (i, _, _), r in reg5.items() if (i == prefix if prefix == "maya-live" else f"|{prefix}|" in i)]
    maya = [reg5.get(("maya-live", "general", d)) for d in (1, 2)]
    d1, h1, h2 = reg("D1"), reg("H1"), reg("H2")
    acc = lambda rs: sum(verdict(r) == "acceptable" for r in rs)  # noqa: E731
    p6 = {
        "maya": all(verdict(r) != "unscored" for r in maya) and not any(lists_swc(r) for r in maya),
        "D1": len(d1) == 8 and acc(d1) >= 7 and not any(lists_swc(r) for r in d1),
        "H1": len(h1) == 6 and acc(h1) >= 5 and not any(lists_swc(r) for r in h1),
        "H2": len(h2) == 6 and acc(h2) >= 5 and not any(lists_swc(r) for r in h2),
    }
    summary = {
        "P1": {"pass": p1, "n_judgments_accepted": [list(k) for k in sorted(n_acc)], "n_item_paths_accepted_in_both_draws": [list(k) for k in both]},
        "P2": {"pass": p2, "accepted_of_scored": {p: list(v) for p, v in p2_rates.items()}},
        "P3": {"pass": p3, "consent_y_flagged": [list(k) for k in y_flagged], "violations_not_flagged": [list(k) for k in viol_missed], "violation_judgments": len(viol_n)},
        "P4": {"pass": p4, "judge_v5": [a5, len(want)], "judge_v1": [a1, len(want1)]},
        "P5": {"pass": p5, "unscored": [list(k) for k in unscored5], "self_contradiction_first_attempts": contradictions},
        "P6": {"pass": all(p6.values()), **{k: v for k, v in p6.items()},
               "maya": [{"verdict": verdict(r), "listed": (r or {}).get("listed"), "scores": ((r or {}).get("decision") or {}).get("scores")} for r in maya],
               "D1_acceptable": [acc(d1), len(d1)], "H1_acceptable": [acc(h1), len(h1)], "H2_acceptable": [acc(h2), len(h2)],
               "maya_judge_v1": [{"verdict": verdict(r), "listed": (r or {}).get("listed")} for r in reg1.values()]},
    }
    summary["pass"] = all(summary[p]["pass"] for p in ("P1", "P2", "P3", "P4", "P5", "P6"))
    rows = []
    for rid in sorted(key):
        for path in (("criteria", "general") if kind[rid] in CERT_KINDS else ("general",)):
            rows.append({"id": rid, "kind": kind[rid], "intent": intent[rid], "label": lab[rid], "path": path,
                         "judge_v1": verdict(v1.get((rid, path, 1))),
                         "judge_v5": [verdict(v5.get((rid, path, d))) for d in (1, 2)],
                         "v5_listed": [(v5.get((rid, path, d)) or {}).get("listed") for d in (1, 2)]})
    summary["items"] = rows
    # every critical entry v5 listed, with its rationale (fresh and regression)
    listed = []
    for name, recs in (("fresh", v5), ("regression", reg5)):
        for (item, path, draw), r in sorted(recs.items()):
            if r.get("status") == "scored":
                for cv in json.loads(r["output_text"]).get("critical_violations", []):
                    listed.append({"stage": name, "item": item, "path": path, "draw": draw,
                                   "type": cv["type"], "rationale": cv["rationale"]})
    summary["v5_listed_entries"] = listed
    # every fresh item-path where v5's draws differ from judge-v1's verdict
    summary["v5_vs_v1_differences"] = [
        {"id": r["id"], "path": r["path"], "label": r["label"], "judge_v1": r["judge_v1"], "judge_v5": r["judge_v5"]}
        for r in rows if any(v != r["judge_v1"] for v in r["judge_v5"])
    ]
    spent = sum(r["cost_nano"] for p in results.glob("*.jsonl") for r in map(json.loads, p.read_text(encoding="utf-8").splitlines()))
    summary["spend_usd"] = round(spent / 1e9, 6)
    text = json.dumps(summary, indent=1, ensure_ascii=False) + "\n"
    if args.write:
        write_once(PUB / "report.json", text)
    print(text)
    return 0


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("sheet")
    sub.add_parser("estimate")
    r = sub.add_parser("run")
    r.add_argument("--stage", choices=("fresh", "regression"), required=True)
    r.add_argument("--judge", choices=JUDGES, required=True)
    r.add_argument("--cap-usd", type=float, required=True)
    r.add_argument("--dry-run", action="store_true")
    r.add_argument("--out-dir", type=Path, default=None)
    rep = sub.add_parser("report")
    rep.add_argument("--results-dir", type=Path, default=None)
    rep.add_argument("--labels", type=Path, default=None, help="a labelled copy of the sheet (default: the sheet)")
    rep.add_argument("--write", action="store_true", help="write docs/measurements/judge-v5/report.json (once)")
    a = ap.parse_args()
    if a.cmd == "sheet":
        return sheet()
    if a.cmd == "estimate":
        return estimate()
    if a.cmd == "report":
        return report(a)
    return run(a)


if __name__ == "__main__":
    raise SystemExit(main())
