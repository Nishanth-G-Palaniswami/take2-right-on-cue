"""H2 criteria experiment: judge-v1 unchanged; only H2's case criteria change (old vs proposed).
Pre-registered in docs/measurements/2026-11-22-h2-criteria-plan.md.

  uv run --no-sync python scripts/h2_criteria_experiment.py sheet
  uv run --no-sync python scripts/h2_criteria_experiment.py estimate
  uv run --no-sync python scripts/h2_criteria_experiment.py run --set fresh --config new --cap-usd 0.50
  uv run --no-sync python scripts/h2_criteria_experiment.py report --write

Sets: `fresh` (new items, Nishanth's labels fixed before scoring), `known` (the judge-v5 sheet's
certification items and labels, already seen), `h2` (the six saved v3 H2 replies; requests built
by scoring.plan_scoring, the scorer's own path). Configs: `old` = H2's frozen criterion in
cases/notes.toml, `new` = docs/measurements/h2-criteria/notes-proposed.toml. Every run waits for
the fresh labels. One cap covers every results file; the client has max_retries=0; a judgment
that needs review or fails gets one immediate retry; output files are write-once.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import re
import secrets
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from rightoncue import scoring  # noqa: E402
from rightoncue.transcript import Turn  # noqa: E402

PUB = REPO / "docs/measurements/h2-criteria"
PRIV = REPO / "holdout-private/h2-criteria"
ITEMS, KEY, SHEET = PRIV / "items.json", PRIV / "key.json", PUB / "review_sheet.md"
SHEET_IN_GIT = "docs/measurements/h2-criteria/review_sheet.md"
RESULTS = PUB / "results"
NOTES_OLD, NOTES_NEW = REPO / "cases/notes.toml", PUB / "notes-proposed.toml"
V5 = REPO / "docs/measurements/judge-v5"
RUN_V3 = REPO / "docs/measurements/prompt-v3/regression/runs/20261123T004511Z-b08ea8"
SAVED_V3_SCORES = REPO / "docs/measurements/prompt-v3/regression/scores/20261123T004511Z-b08ea8.jsonl"
JUDGE = "judge-v1"
# new: the proposed H2 criterion; old: H2's frozen criterion; general: no case criteria, which is
# what the live path gives pasted transcripts and practice calls (a reference, unchanged here)
DRAWS = {"new": 2, "old": 1, "general": 1}
CONFIGS = ("new", "old", "general")
IN_NANO, OUT_NANO = 750, 4_500  # gpt-5.4-mini nano-USD per token (PRD rates)
PLANNING_NANO = 3_500_000  # $0.0035 per judge-v1 call (recorded mean $0.003468)
BOM, CRLF, LF = chr(0xFEFF), chr(13) + chr(10), chr(10)
ACCEPT_LINE = re.compile(r"^Accept (K\d\d)\? \(y/n\):[ \t]*(.*?)[ \t]*$", re.MULTILINE)
V5_ACCEPT_LINE = re.compile(r"^Accept (J\d\d)\? \(y/n\):[ \t]*(.*?)[ \t]*$", re.MULTILINE)

KINDS: dict[str, tuple[str, ...]] = {
    "explicit_plain": ("moves_on", "optional_question", "reasks_currency", "stacked_optional_behavioral"),
    "explicit_named": ("different_optional", "asks_named", "reasks_license"),
    "mixed_a": ("asks_currency", "moves_on_unconfirmed", "optional_instead"),
    "mixed_b": ("asks_currency", "moves_on_unconfirmed", "optional_instead"),
    "explicit_equiv_valid": ("optional_three_examples", "moves_on", "reasks_currency"),
    "explicit_equiv_renewed": ("optional_three_examples", "stacked_optional_behavioral", "reasks_currency"),
}
EXPLICIT = ("explicit_plain", "explicit_named", "explicit_equiv_valid", "explicit_equiv_renewed")
N_ITEMS = 19
# the judge-v5 sheet's certification conversations, by its kinds
V5_KINDS = {"confirmed": "explicit", "named_optional": "explicit", "currency_missing": "mixed"}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_once(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "x", encoding="utf-8", newline=LF) as fh:
        fh.write(text)


def criteria(config: str) -> scoring.Criteria | None:
    if config == "general":
        return None
    return scoring.load_criteria(NOTES_OLD if config == "old" else NOTES_NEW)["H2"]


# ------------------------------------------------------------------- the sheet


def load_items() -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]]]:
    data = json.loads(ITEMS.read_text(encoding="utf-8"))
    convs, items = data["conversations"], data["items"]
    if sorted(c["kind"] for c in convs.values()) != sorted(KINDS):
        raise SystemExit(f"expected one conversation of each kind {sorted(KINDS)}")
    for name, conv in convs.items():
        conv["turns_parsed"] = [Turn.model_validate(t) for t in conv["turns"]]
        got = sorted(i["intent"] for i in items if i["conversation"] == name)
        if got != sorted(KINDS[conv["kind"]]):
            raise SystemExit(f"conversation {name} ({conv['kind']}): intents {got}")
    if len(items) != N_ITEMS:
        raise SystemExit(f"expected {N_ITEMS} items, got {len(items)}")
    return convs, items


def sheet() -> int:
    if SHEET.exists() or KEY.exists():
        raise SystemExit("the sheet already exists; it is built once")
    convs, items = load_items()
    order = list(range(len(items)))
    random.SystemRandom().shuffle(order)
    key: dict[str, Any] = {"salt": secrets.token_hex(16), "items": {}}
    lines = [
        "# H2 criteria experiment: blind label sheet",
        "",
        "Label each reply as Riley's next turn: `y` if it is an acceptable next turn, `n` if not, by your own judgment.",
        "",
        "- Each item shows the conversation so far and one proposed reply. Several items share a conversation.",
        "- The items are new, written by a separate agent from your description of the rule. What each reply was written to do is sealed in `holdout-private/h2-criteria/` and committed by hash.",
        "- Please label every item before opening `holdout-private/h2-criteria/`, the plan's item table, or any score. Scoring refuses to start until every Accept line has y or n.",
        "- A reason is optional. Note below whether you used an AI assistant.",
        "",
        "Used an AI assistant while labelling (yes/no):",
        "",
    ]
    for n, idx in enumerate(order, start=1):
        rid = f"K{n:02d}"
        item = items[idx]
        key["items"][rid] = {"index": idx, "conversation": item["conversation"], "intent": item["intent"]}
        lines += ["---", "", f"## {rid}", "", "Conversation so far:", ""]
        for t in convs[item["conversation"]]["turns"]:
            lines += [f"> **{'Riley' if t['role'] == 'agent' else 'Applicant'}:** {t['utterance']}", ">"]
        lines.pop()
        lines += ["", "Riley's proposed next turn:", "", "> " + item["reply"].strip(), "",
                  f"Accept {rid}? (y/n):", "", "Reason (optional):", ""]
    write_once(SHEET, LF.join(lines))
    write_once(KEY, json.dumps(key, indent=1) + LF)
    commitment = {
        "private_files": {"items.json": sha(ITEMS), "key.json": sha(KEY)},
        "public_files": {"review_sheet.md": sha(SHEET)},
        "judge": JUDGE, "judge_prompt_sha256": scoring.JUDGE_PROMPTS[JUDGE][1],
        "notes_proposed_sha256": sha(NOTES_NEW), "notes_old_sha256": sha(NOTES_OLD),
    }
    write_once(PUB / "commitment.json", json.dumps(commitment, indent=1) + LF)
    print(f"sheet: {len(items)} items; commitment written")
    return 0


def sheet_text(path: Path = SHEET) -> str:
    return path.read_text(encoding="utf-8").lstrip(BOM).replace(CRLF, LF)


def shown(text: str) -> list[str]:
    return [line.rstrip() for line in text.split(LF) if line.startswith("## K") or line.startswith(">")]


def verify() -> None:
    c = json.loads((PUB / "commitment.json").read_text(encoding="utf-8"))
    for name, digest in c["private_files"].items():
        if sha(PRIV / name) != digest:
            raise SystemExit(f"{name} does not match the commitment")
    if sha(NOTES_NEW) != c["notes_proposed_sha256"] or sha(NOTES_OLD) != c["notes_old_sha256"]:
        raise SystemExit("a criteria file changed after the commitment")
    if sha(SHEET) == c["public_files"]["review_sheet.md"]:
        return
    first = subprocess.run(["git", "log", "--format=%H", "--diff-filter=A", "--", SHEET_IN_GIT],
                           cwd=REPO, capture_output=True, text=True, check=True).stdout.split()[-1]
    committed = subprocess.run(["git", "show", f"{first}:{SHEET_IN_GIT}"], cwd=REPO, capture_output=True, check=True).stdout
    if hashlib.sha256(committed).hexdigest() != c["public_files"]["review_sheet.md"]:
        raise SystemExit("the sheet in git does not match the commitment")
    if shown(committed.decode("utf-8")) != shown(sheet_text()):
        raise SystemExit("review_sheet.md changes an item heading, a conversation or a reply")


def labels() -> dict[str, str]:
    return {m.group(1): m.group(2).strip().lower() for m in ACCEPT_LINE.finditer(sheet_text())}


# ------------------------------------------------------------------------ jobs


@dataclass(frozen=True)
class Job:
    set: str
    item: str
    kind: str  # "explicit" or "mixed" (fresh/known); "h2" for the regression set
    draw: int
    turns: list[Turn]
    reply: str


def fresh_items() -> list[tuple[str, str, list[Turn], str]]:
    convs, items = load_items()
    key = json.loads(KEY.read_text(encoding="utf-8"))["items"]
    out = []
    for rid in sorted(key):
        item = items[key[rid]["index"]]
        conv = convs[item["conversation"]]
        out.append((rid, "explicit" if conv["kind"] in EXPLICIT else "mixed", conv["turns_parsed"], item["reply"]))
    return out


def known_items() -> list[tuple[str, str, list[Turn], str]]:
    data = json.loads((V5 / "revealed/items.json").read_text(encoding="utf-8"))
    key = json.loads((V5 / "revealed/key.json").read_text(encoding="utf-8"))["items"]
    out = []
    for rid in sorted(key):
        item = data["items"][key[rid]["index"]]
        kind = data["conversations"][item["conversation"]]["kind"]
        if kind in V5_KINDS:
            turns = [Turn.model_validate(t) for t in data["conversations"][item["conversation"]]["turns"]]
            out.append((rid, V5_KINDS[kind], turns, item["reply"]))
    return out


def known_labels() -> dict[str, str]:
    text = (V5 / "review_sheet.md").read_text(encoding="utf-8")
    return {m.group(1): m.group(2).strip().lower() for m in V5_ACCEPT_LINE.finditer(text)}


def h2_plan(config: str) -> list[Any]:
    """The six saved v3 H2 replies, planned by the scorer itself (scoring.plan_scoring)."""
    judge = scoring.load_judge_prompt(JUDGE)
    with tempfile.TemporaryDirectory() as tmp:
        plan = scoring.plan_scoring(RUN_V3, Path(tmp), NOTES_OLD if config == "old" else NOTES_NEW, judge,
                                    only_cases=frozenset({"H2"}))
    return [sp for sp in plan.slots if sp.state == "ok"]


def jobs_for(set_: str, config: str) -> list[Job]:
    jobs: list[Job] = []
    if config == "general" and set_ != "fresh":
        return []  # general rubric: fresh items only (known items: the judge-v5 run's judge-v1 records)
    if set_ == "h2":
        if config == "old":
            return []  # the saved judge-v1 records are the old baseline; no new call
        for sp in h2_plan(config):
            for draw in range(1, DRAWS[config] + 1):
                jobs.append(Job(set_, sp.slot_key, "h2", draw, sp.turns, sp.text))
        return jobs
    source = fresh_items() if set_ == "fresh" else known_items()
    for rid, kind, turns, reply in source:
        for draw in range(1, DRAWS[config] + 1):
            jobs.append(Job(set_, rid, kind, draw, turns, reply))
    return jobs


def request_for(job: Job, config: str, judge: scoring.JudgePrompt) -> dict[str, Any]:
    return scoring.build_judge_request(judge.text, job.turns, job.reply, criteria(config), scorer_version=judge.scorer_version)


def max_cost_nano(request: dict[str, Any]) -> int:
    canonical = json.dumps(request, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return len(canonical.encode("utf-8")) * IN_NANO + int(request["max_output_tokens"]) * OUT_NANO


def check_h2_requests_match_the_scorer() -> None:
    """The harness's H2 requests must be byte-identical to the scorer's own (plan_scoring)."""
    judge = scoring.load_judge_prompt(JUDGE)
    for config in ("old", "new"):
        planned = {sp.slot_key: sp.request_sha256 for sp in h2_plan(config)}
        for sp in h2_plan(config):
            job = Job("h2", sp.slot_key, "h2", 1, sp.turns, sp.text)
            if scoring.request_sha256(request_for(job, config, judge)) != planned[sp.slot_key]:
                raise SystemExit(f"{config}: harness request for {sp.slot_key} differs from the scorer's")


def estimate() -> int:
    check_h2_requests_match_the_scorer()
    judge = scoring.load_judge_prompt(JUDGE)
    total_n, worst = 0, 0
    for set_ in ("fresh", "known", "h2"):
        for config in CONFIGS:
            jobs = jobs_for(set_, config)
            if not jobs:
                print(f"{set_:6} {config}: 0 calls (saved judge-v1 records, or not applicable)")
                continue
            bounds = [max_cost_nano(request_for(j, config, judge)) for j in jobs]
            total_n += len(jobs)
            worst = max(worst, max(bounds))
            print(f"{set_:6} {config}: {len(jobs):3} first attempts; expected about ${len(jobs) * PLANNING_NANO * 1.2 / 1e9:.3f} with ~20% retries")
    print(f"total: {total_n} first attempts; expected about ${total_n * PLANNING_NANO * 1.2 / 1e9:.3f}; worst-case bound per call ${worst/1e9:.6f}")
    return 0


# ------------------------------------------------------------------------- run


def records(results: Path) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for p in sorted(results.glob("*.jsonl")):
        out += [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines() if x.strip()]
    return out


class _FakeClient:
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
        raise SystemExit("--dry-run needs --out-dir, so it never takes a write-once results file")
    verify()
    lab = labels()
    if len(lab) != N_ITEMS or any(v not in ("y", "n") for v in lab.values()):
        raise SystemExit("label every item on the sheet (y or n) before any set is scored")
    check_h2_requests_match_the_scorer()
    judge = scoring.load_judge_prompt(JUDGE)
    results = args.out_dir or RESULTS
    out_path = results / f"{args.set}-{args.config}.jsonl"
    if out_path.exists():
        raise SystemExit(f"{out_path} exists; each set and config is scored once")
    jobs = jobs_for(args.set, args.config)
    if not jobs:
        raise SystemExit("nothing to score: the old H2 baseline is the saved judge-v1 records")
    cap = round(args.cap_usd * 1e9)
    spent = sum(r["cost_nano"] for r in records(results))
    if args.dry_run:
        client: Any = _FakeClient()
    else:
        from dotenv import load_dotenv
        from openai import OpenAI

        load_dotenv(REPO / ".env", override=False)
        client = OpenAI(max_retries=0)
    calls = 0
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "x", encoding="utf-8", newline=LF) as fh:
        for job in jobs:
            request = request_for(job, args.config, judge)
            for attempt in (1, 2):
                bound = max_cost_nano(request)
                if spent + bound > cap:
                    print(f"STOPPED by the cap before {job.item} draw {job.draw} attempt {attempt}: "
                          f"spent ${spent/1e9:.6f}, call maximum ${bound/1e9:.6f}, cap ${cap/1e9:.2f}")
                    return 3
                rec: dict[str, Any] = {
                    "set": job.set, "config": args.config, "item": job.item, "kind": job.kind,
                    "draw": job.draw, "attempt": attempt, "judge_prompt_version": judge.version,
                    "judge_prompt_sha256": judge.sha256, "scorer_version": judge.scorer_version,
                    "judge_request_sha256": scoring.request_sha256(request), "dry_run": bool(args.dry_run),
                }
                calls += 1
                try:
                    resp = client.responses.create(**request)
                    dump = resp.model_dump(mode="json")
                    usage = dump.get("usage") or {}
                    tin, tout = usage.get("input_tokens"), usage.get("output_tokens")
                    cost = tin * IN_NANO + tout * OUT_NANO if isinstance(tin, int) and isinstance(tout, int) else bound
                    judgment, errors = scoring.validate_judge_output(
                        resp.status, resp.output_text, job.turns, job.reply, scorer_version=judge.scorer_version)
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
                fh.write(json.dumps(rec, ensure_ascii=False) + LF)
                fh.flush()
                if rec["status"] == "scored":
                    break
    print(f"{args.set} {args.config}: {calls} calls; experiment spend now ${spent/1e9:.6f} of ${cap/1e9:.2f}")
    return 0


# ---------------------------------------------------------------------- report


def finals(path: Path) -> dict[tuple[str, int], dict[str, Any]]:
    out: dict[tuple[str, int], dict[str, Any]] = {}
    if not path.exists():
        return out
    for line in path.read_text(encoding="utf-8").splitlines():
        r = json.loads(line)
        k = (r["item"], r["draw"])
        if r["status"] == "scored":
            out[k] = r
        else:
            out.setdefault(k, {"status": "unscored"})
    return out


def verdict(r: dict[str, Any] | None) -> str:
    if not r or r.get("status") != "scored":
        return "unscored"
    return "accepted" if r["decision"]["acceptable"] else "rejected"


def counts(vs: list[str]) -> dict[str, int]:
    return {k: vs.count(k) for k in ("accepted", "rejected", "unscored")}


def saved_h2_old() -> dict[tuple[str, int], dict[str, Any]]:
    """judge-v1's saved H2 verdicts (the old baseline): the first scored record per slot."""
    out: dict[tuple[str, int], dict[str, Any]] = {}
    for line in SAVED_V3_SCORES.read_text(encoding="utf-8").splitlines():
        r = json.loads(line)
        if r.get("case_id") == "H2" and r.get("judge_prompt_version") == JUDGE and r.get("status") == "scored":
            out.setdefault((r["slot_key"], 1), {"status": "scored", "decision": r["decision"],
                                                "listed": [c["type"] for c in r["judgment"]["critical_violations"]]})
    return out


def saved_known_general() -> dict[tuple[str, int], dict[str, Any]]:
    """judge-v1 under the general rubric on the known items: the judge-v5 run's reference records."""
    out: dict[tuple[str, int], dict[str, Any]] = {}
    for line in (V5 / "results/fresh-judge-v1.jsonl").read_text(encoding="utf-8").splitlines():
        r = json.loads(line)
        if r["path"] != "general":
            continue
        if r["status"] == "scored":
            out[(r["item"], r["draw"])] = r
        else:
            out.setdefault((r["item"], r["draw"]), {"status": "unscored"})
    return out


def report(args: argparse.Namespace) -> int:
    verify()
    results = args.results_dir or RESULTS
    lab = labels() if args.labels is None else {
        m.group(1): m.group(2).strip().lower() for m in ACCEPT_LINE.finditer(sheet_text(args.labels))}
    if len(lab) != N_ITEMS or any(v not in ("y", "n") for v in lab.values()):
        raise SystemExit("the sheet needs y or n on every Accept line")
    klab = known_labels()
    res = {(s, c): finals(results / f"{s}-{c}.jsonl") for s in ("fresh", "known", "h2") for c in CONFIGS}
    res[("h2", "old")] = saved_h2_old()
    res[("known", "general")] = saved_known_general()
    kinds = {rid: kind for rid, kind, _, _ in fresh_items()}
    kkinds = {rid: kind for rid, kind, _, _ in known_items()}
    want = lambda s, c: [(j.item, j.draw) for j in jobs_for(s, c)]  # noqa: E731

    def keys(set_: str, config: str) -> list[tuple[str, int]]:
        if (set_, config) == ("known", "general"):
            return [(i, 1) for i, _, _, _ in known_items()]
        return want(set_, config)

    def group(set_: str, config: str, kind: str | None, label: str | None) -> list[str]:
        L, K = (lab, kinds) if set_ == "fresh" else (klab, kkinds)
        return [verdict(res[(set_, config)].get(k)) for k in keys(set_, config)
                if (kind is None or K[k[0]] == kind) and (label is None or L[k[0]] == label)]

    def agree(set_: str, config: str) -> list[int]:
        L = lab if set_ == "fresh" else klab
        ks = keys(set_, config)
        good = sum(verdict(res[(set_, config)].get(k)) == ("accepted" if L[k[0]] == "y" else "rejected") for k in ks)
        return [good, len(ks)]

    new_fresh = res[("fresh", "new")]
    both_accepted = sorted({i for (i, d) in want("fresh", "new") if kinds[i] == "mixed" and lab[i] == "n"
                            and all(verdict(new_fresh.get((i, dd))) == "accepted" for dd in (1, 2))})
    g = {
        "H1_explicit_y": counts(group("fresh", "new", "explicit", "y")),
        "H2_mixed_n": counts(group("fresh", "new", "mixed", "n")),
        "H3_mixed_y": counts(group("fresh", "new", "mixed", "y")),
        "H4_explicit_n": counts(group("fresh", "new", "explicit", "n")),
        "H5_h2_regression": counts([verdict(res[("h2", "new")].get(k)) for k in want("h2", "new")]),
    }
    new_all = [verdict(new_fresh.get(k)) for k in want("fresh", "new")]
    crit = {
        "H1": g["H1_explicit_y"]["rejected"] <= 1,
        "H2": g["H2_mixed_n"]["accepted"] <= 1 and not both_accepted,
        "H3": g["H3_mixed_y"]["rejected"] <= 1,
        "H4": g["H4_explicit_n"]["accepted"] == 0,
        "H5": g["H5_h2_regression"]["accepted"] >= 10,
        "H6": new_all.count("unscored") <= len(new_all) * 0.15,
    }
    summary: dict[str, Any] = {"criteria": crit, "pass": all(crit.values()), "groups_new": g,
                               "mixed_n_accepted_in_both_draws": both_accepted}
    table = {}
    for set_ in ("fresh", "known", "h2"):
        for config in ("old", "new", "general"):
            if set_ == "h2" and config == "old":
                vs = [verdict(r) for r in res[("h2", "old")].values()]
                table[f"{set_}/{config} (saved judge-v1 records)"] = counts(vs)
                continue
            if set_ == "h2" and config == "general":
                continue
            ks = keys(set_, config)
            row: dict[str, Any] = counts([verdict(res[(set_, config)].get(k)) for k in ks])
            if set_ != "h2":
                row["agreement_with_labels"] = agree(set_, config)
                for kind in ("explicit", "mixed"):
                    for label in ("y", "n"):
                        row[f"{kind}_{label}"] = counts(group(set_, config, kind, label))
            table[f"{set_}/{config}"] = row
    summary["counts"] = table
    rows = []
    for set_, L, K in (("fresh", lab, kinds), ("known", klab, kkinds)):
        for rid in sorted(K):
            rows.append({"set": set_, "id": rid, "kind": K[rid], "label": L[rid],
                         "old": verdict(res[(set_, "old")].get((rid, 1))),
                         "general": verdict(res[(set_, "general")].get((rid, 1))),
                         "new": [verdict(res[(set_, "new")].get((rid, d))) for d in (1, 2)],
                         "new_listed": [(res[(set_, "new")].get((rid, d)) or {}).get("listed") for d in (1, 2)]})
    for sk in sorted({k[0] for k in want("h2", "new")}):
        rows.append({"set": "h2", "id": sk, "old": verdict(res[("h2", "old")].get((sk, 1))),
                     "new": [verdict(res[("h2", "new")].get((sk, d))) for d in (1, 2)],
                     "new_listed": [(res[("h2", "new")].get((sk, d)) or {}).get("listed") for d in (1, 2)]})
    summary["items"] = rows
    spent = sum(r["cost_nano"] for r in records(results))
    summary["spend_usd"] = round(spent / 1e9, 6)
    text = json.dumps(summary, indent=1, ensure_ascii=False) + LF
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
    r.add_argument("--set", choices=("fresh", "known", "h2"), required=True)
    r.add_argument("--config", choices=CONFIGS, required=True)
    r.add_argument("--cap-usd", type=float, required=True)
    r.add_argument("--dry-run", action="store_true")
    r.add_argument("--out-dir", type=Path, default=None)
    rep = sub.add_parser("report")
    rep.add_argument("--results-dir", type=Path, default=None)
    rep.add_argument("--labels", type=Path, default=None)
    rep.add_argument("--write", action="store_true")
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
