"""H2 criteria, round 2: paired items (same reply, only the applicant's wording changes).
Pre-registered in docs/measurements/2026-11-22-h2-criteria-2-plan.md.

  uv run --no-sync python scripts/h2_criteria2_experiment.py sheet
  uv run --no-sync python scripts/h2_criteria2_experiment.py estimate
  uv run --no-sync python scripts/h2_criteria2_experiment.py run-all --cap-usd 0.65
  uv run --no-sync python scripts/h2_criteria2_experiment.py report --write

judge-v1 and Riley's prompt are unchanged. Configs: `new` = this round's H2 text
(docs/measurements/h2-criteria-2/notes-proposed.toml), `prev` = round 1's text. Sets: `fresh`
(30 paired items, Nishanth's own labels), `h2` (the six saved v3 H2 replies, requests built by
scoring.plan_scoring), `tobias` (the judge-v5 sheet's Tobias conversation, 3 items), `round1` (round
1's six Tobias-like items). The pre-registered readout is each judgment's next_action score (2 =
the move is allowed here); verdicts are reported beside it. `run-all` makes every pass in one
process, after the labels and under one cap; output files are write-once; the client has
max_retries=0; a judgment that needs review or fails gets one immediate retry.
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

PUB = REPO / "docs/measurements/h2-criteria-2"
PRIV = REPO / "holdout-private/h2-criteria-2"
FRAMES, KEY, SHEET = PRIV / "frames.json", PRIV / "key.json", PUB / "review_sheet.md"
SHEET_IN_GIT = "docs/measurements/h2-criteria-2/review_sheet.md"
RESULTS = PUB / "results"
NOTES_NEW = PUB / "notes-proposed.toml"
NOTES_PREV = REPO / "docs/measurements/h2-criteria/notes-proposed.toml"
NOTES_OLD = REPO / "cases/notes.toml"
R1 = REPO / "docs/measurements/h2-criteria"
V5 = REPO / "docs/measurements/judge-v5"
RUN_V3 = REPO / "docs/measurements/prompt-v3/regression/runs/20261123T004511Z-b08ea8"
SAVED_V3_SCORES = REPO / "docs/measurements/prompt-v3/regression/scores/20261123T004511Z-b08ea8.jsonl"
JUDGE = "judge-v1"
IN_NANO, OUT_NANO = 750, 4_500  # gpt-5.4-mini nano-USD per token (PRD rates)
PLANNING_NANO = 3_500_000  # $0.0035 per judge-v1 call
BOM, CRLF, LF = chr(0xFEFF), chr(13) + chr(10), chr(10)
ACCEPT = re.compile(r"^Accept (P\d\d)\? \(y/n\):[ \t]*(.*?)[ \t]*$", re.MULTILINE)
ACCEPT_ANY = re.compile(r"^Accept ([JK]\d\d)\? \(y/n\):[ \t]*(.*?)[ \t]*$", re.MULTILINE)

# frame -> (other version, reply keys); the design in the plan
DESIGN: dict[str, tuple[str, tuple[str, ...]]] = {
    "F1": ("U", ("move", "opt", "clarify_both")),
    "F2": ("U", ("move", "opt", "clarify_both")),
    "F3": ("U", ("move", "opt", "clarify_both")),
    "F4": ("P", ("move", "opt", "clarify_other")),
    "F5": ("P", ("move", "opt", "clarify_other")),
}
N_ITEMS = 30
PASSES = (("fresh", "new"), ("fresh", "prev"), ("h2", "new"), ("tobias", "new"), ("round1", "new"))
DRAWS = {"new": 2, "prev": 1}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_once(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "x", encoding="utf-8", newline=LF) as fh:
        fh.write(text)


def criteria(config: str) -> scoring.Criteria:
    return scoring.load_criteria(NOTES_NEW if config == "new" else NOTES_PREV)["H2"]


# --------------------------------------------------------------------- items


@dataclass(frozen=True)
class Item:
    frame: str
    version: str  # "C", "U" or "P"
    reply_key: str
    turns: list[Turn]
    reply: str


def build_items() -> list[Item]:
    """Every item as frame x version x reply. The shared turns and each reply are the same object
    for both versions of a frame, so only the applicant's last turn differs."""
    data = json.loads(FRAMES.read_text(encoding="utf-8"))["frames"]
    if sorted(data) != sorted(DESIGN):
        raise SystemExit(f"expected frames {sorted(DESIGN)}, got {sorted(data)}")
    items: list[Item] = []
    for name, (other, reply_keys) in DESIGN.items():
        f = data[name]
        if f.get("other_version") != other or sorted(f["versions"]) != sorted(("C", other)):
            raise SystemExit(f"{name}: versions must be C and {other}")
        if sorted(f["replies"]) != sorted(reply_keys):
            raise SystemExit(f"{name}: replies must be {sorted(reply_keys)}")
        shared = [Turn.model_validate(t) for t in f["shared_turns"]]
        if not shared or shared[-1].role != "agent":
            raise SystemExit(f"{name}: the shared turns must end with Riley's question")
        texts = {v: f["versions"][v].strip() for v in ("C", other)}
        if texts["C"] == texts[other]:
            raise SystemExit(f"{name}: the two versions are identical")
        for version in ("C", other):
            turns = [*shared, Turn(role="user", utterance=texts[version])]
            for key in reply_keys:
                items.append(Item(name, version, key, turns, f["replies"][key].strip()))
    # the paired property, checked: per frame and reply, identical reply and identical earlier turns
    for name, (other, reply_keys) in DESIGN.items():
        for key in reply_keys:
            pair = [i for i in items if i.frame == name and i.reply_key == key]
            assert len(pair) == 2 and pair[0].reply == pair[1].reply and pair[0].turns[:-1] == pair[1].turns[:-1]
    if len(items) != N_ITEMS:
        raise SystemExit(f"expected {N_ITEMS} items, got {len(items)}")
    return items


def sheet() -> int:
    if SHEET.exists() or KEY.exists():
        raise SystemExit("the sheet already exists; it is built once")
    items = build_items()
    order = list(range(len(items)))
    random.SystemRandom().shuffle(order)
    key: dict[str, Any] = {"salt": secrets.token_hex(16), "items": {}}
    lines = [
        "# H2 criteria, round 2: blind label sheet",
        "",
        "Label each reply as Riley's next turn: `y` if it is an acceptable next turn, `n` if not, by your own judgment.",
        "",
        "- **Labels: Nishanth's own, made blind and without an AI assistant** (decided before the sheet was built).",
        "- Each item shows the conversation so far and one proposed reply. Items come in pairs: the same reply after two versions of the applicant's last turn.",
        "- The items are new, written by a separate agent. Please label every item before opening `holdout-private/h2-criteria-2/`, the plan's design table, or any score. Scoring refuses to start until every Accept line has y or n.",
        "- A reason is optional.",
        "",
        "Used an AI assistant while labelling (yes/no):",
        "",
    ]
    for n, idx in enumerate(order, start=1):
        rid = f"P{n:02d}"
        it = items[idx]
        key["items"][rid] = {"index": idx, "frame": it.frame, "version": it.version, "reply_key": it.reply_key}
        lines += ["---", "", f"## {rid}", "", "Conversation so far:", ""]
        for t in it.turns:
            lines += [f"> **{'Riley' if t.role == 'agent' else 'Applicant'}:** {t.utterance}", ">"]
        lines.pop()
        lines += ["", "Riley's proposed next turn:", "", "> " + it.reply, "", f"Accept {rid}? (y/n):", "", "Reason (optional):", ""]
    write_once(SHEET, LF.join(lines))
    write_once(KEY, json.dumps(key, indent=1) + LF)
    commitment = {
        "private_files": {"frames.json": sha(FRAMES), "key.json": sha(KEY)},
        "public_files": {"review_sheet.md": sha(SHEET)},
        "judge": JUDGE, "judge_prompt_sha256": scoring.JUDGE_PROMPTS[JUDGE][1],
        "notes_new_sha256": sha(NOTES_NEW), "notes_prev_sha256": sha(NOTES_PREV), "notes_old_sha256": sha(NOTES_OLD),
        "script_sha256_when_the_sheet_was_built": sha(Path(__file__)),
    }
    write_once(PUB / "commitment.json", json.dumps(commitment, indent=1) + LF)
    print(f"sheet: {len(items)} items in {len(DESIGN)} frames; commitment written")
    return 0


def sheet_text(path: Path = SHEET) -> str:
    return path.read_text(encoding="utf-8").lstrip(BOM).replace(CRLF, LF)


def shown(text: str) -> list[str]:
    return [line.rstrip() for line in text.split(LF) if line.startswith("## P") or line.startswith(">")]


def verify() -> None:
    c = json.loads((PUB / "commitment.json").read_text(encoding="utf-8"))
    for name, digest in c["private_files"].items():
        if sha(PRIV / name) != digest:
            raise SystemExit(f"{name} does not match the commitment")
    for path, field in ((NOTES_NEW, "notes_new_sha256"), (NOTES_PREV, "notes_prev_sha256"), (NOTES_OLD, "notes_old_sha256")):
        if sha(path) != c[field]:
            raise SystemExit(f"{path.name} changed after the commitment")
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
    return {m.group(1): m.group(2).strip().lower() for m in ACCEPT.finditer(sheet_text())}


def labels_from(path: Path) -> dict[str, str]:
    return {m.group(1): m.group(2).strip().lower() for m in ACCEPT_ANY.finditer(path.read_text(encoding="utf-8"))}


# ---------------------------------------------------------------------- jobs


@dataclass(frozen=True)
class Job:
    set: str
    item: str
    draw: int
    turns: list[Turn]
    reply: str


def fresh_jobs(config: str) -> list[Job]:
    items = build_items()
    key = json.loads(KEY.read_text(encoding="utf-8"))["items"]
    return [Job("fresh", rid, d, items[key[rid]["index"]].turns, items[key[rid]["index"]].reply)
            for rid in sorted(key) for d in range(1, DRAWS[config] + 1)]


def h2_plan(notes: Path) -> list[Any]:
    judge = scoring.load_judge_prompt(JUDGE)
    with tempfile.TemporaryDirectory() as tmp:
        plan = scoring.plan_scoring(RUN_V3, Path(tmp), notes, judge, only_cases=frozenset({"H2"}))
    return [sp for sp in plan.slots if sp.state == "ok"]


def tobias_items() -> list[tuple[str, list[Turn], str]]:
    data = json.loads((V5 / "revealed/items.json").read_text(encoding="utf-8"))
    key = json.loads((V5 / "revealed/key.json").read_text(encoding="utf-8"))["items"]
    out = []
    for rid in sorted(key):
        it = data["items"][key[rid]["index"]]
        conv = data["conversations"][it["conversation"]]
        if conv["kind"] == "currency_missing":  # Tobias
            out.append((rid, [Turn.model_validate(t) for t in conv["turns"]], it["reply"]))
    return out


def round1_items() -> list[tuple[str, list[Turn], str]]:
    data = json.loads((R1 / "revealed/items.json").read_text(encoding="utf-8"))
    key = json.loads((R1 / "revealed/key.json").read_text(encoding="utf-8"))["items"]
    out = []
    for rid in sorted(key):
        it = data["items"][key[rid]["index"]]
        conv = data["conversations"][it["conversation"]]
        if conv["kind"] in ("mixed_a", "mixed_b"):  # round 1's Tobias-like conversations
            out.append((rid, [Turn.model_validate(t) for t in conv["turns"]], it["reply"]))
    return out


def jobs_for(set_: str, config: str) -> list[Job]:
    if set_ == "fresh":
        return fresh_jobs(config)
    if config != "new":
        return []
    if set_ == "h2":
        return [Job("h2", sp.slot_key, d, sp.turns, sp.text) for sp in h2_plan(NOTES_NEW) for d in (1, 2)]
    source = tobias_items() if set_ == "tobias" else round1_items()
    return [Job(set_, rid, d, turns, reply) for rid, turns, reply in source for d in (1, 2)]


def request_for(job: Job, config: str, judge: scoring.JudgePrompt) -> dict[str, Any]:
    return scoring.build_judge_request(judge.text, job.turns, job.reply, criteria(config), scorer_version=judge.scorer_version)


def max_cost_nano(request: dict[str, Any]) -> int:
    canonical = json.dumps(request, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return len(canonical.encode("utf-8")) * IN_NANO + int(request["max_output_tokens"]) * OUT_NANO


def check_h2_requests_match_the_scorer() -> None:
    judge = scoring.load_judge_prompt(JUDGE)
    planned = {sp.slot_key: sp.request_sha256 for sp in h2_plan(NOTES_NEW)}
    for job in jobs_for("h2", "new"):
        if scoring.request_sha256(request_for(job, "new", judge)) != planned[job.item]:
            raise SystemExit(f"the request for {job.item} differs from the scorer's own")


def estimate() -> int:
    check_h2_requests_match_the_scorer()
    judge = scoring.load_judge_prompt(JUDGE)
    total, worst = 0, 0
    for set_, config in PASSES:
        jobs = jobs_for(set_, config)
        bounds = [max_cost_nano(request_for(j, config, judge)) for j in jobs]
        total += len(jobs)
        worst = max(worst, max(bounds))
        print(f"{set_:7} {config}: {len(jobs):3} first attempts; expected about ${len(jobs) * PLANNING_NANO * 1.2 / 1e9:.3f} with ~20% retries")
    print(f"total: {total} first attempts; expected about ${total * PLANNING_NANO * 1.2 / 1e9:.3f}; worst-case bound per call ${worst/1e9:.6f}")
    return 0


# ----------------------------------------------------------------------- run


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


def run_all(args: argparse.Namespace) -> int:
    if args.dry_run and args.out_dir is None:
        raise SystemExit("--dry-run needs --out-dir, so it never takes a write-once results file")
    verify()
    lab = labels()
    if len(lab) != N_ITEMS or any(v not in ("y", "n") for v in lab.values()):
        raise SystemExit("label every item on the sheet (y or n) before anything is scored")
    check_h2_requests_match_the_scorer()
    if not args.dry_run:
        # the paid run uses exactly the committed script: refuse if it differs from git HEAD
        dirty = subprocess.run(["git", "status", "--porcelain", "--", "scripts/h2_criteria2_experiment.py"],
                               cwd=REPO, capture_output=True, text=True, check=True).stdout.strip()
        if dirty:
            raise SystemExit("commit scripts/h2_criteria2_experiment.py before the paid run")
    script_sha = sha(Path(__file__))
    judge = scoring.load_judge_prompt(JUDGE)
    results = args.out_dir or RESULTS
    for set_, config in PASSES:
        if (results / f"{set_}-{config}.jsonl").exists():
            raise SystemExit(f"{set_}-{config}.jsonl exists; every pass is scored once")
    cap = round(args.cap_usd * 1e9)
    spent = sum(r["cost_nano"] for r in records(results))
    if args.dry_run:
        client: Any = _FakeClient()
    else:
        from dotenv import load_dotenv
        from openai import OpenAI

        load_dotenv(REPO / ".env", override=False)
        client = OpenAI(max_retries=0)
    results.mkdir(parents=True, exist_ok=True)
    for set_, config in PASSES:
        calls = 0
        with open(results / f"{set_}-{config}.jsonl", "x", encoding="utf-8", newline=LF) as fh:
            for job in jobs_for(set_, config):
                request = request_for(job, config, judge)
                for attempt in (1, 2):
                    bound = max_cost_nano(request)
                    if spent + bound > cap:
                        print(f"STOPPED by the cap before {set_} {job.item} draw {job.draw} attempt {attempt}: "
                              f"spent ${spent/1e9:.6f}, call maximum ${bound/1e9:.6f}, cap ${cap/1e9:.2f}")
                        return 3
                    rec: dict[str, Any] = {
                        "set": set_, "config": config, "item": job.item, "draw": job.draw, "attempt": attempt,
                        "judge_prompt_version": judge.version, "judge_prompt_sha256": judge.sha256,
                        "scorer_version": judge.scorer_version,
                        "judge_request_sha256": scoring.request_sha256(request), "dry_run": bool(args.dry_run),
                        "script_sha256": script_sha,
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
                                       next_action=judgment.dimension("next_action").score,
                                       listed=[t for t, _, _ in scoring._violations(judgment)])
                    except Exception as exc:  # recorded and charged at its maximum, then retried once
                        rec.update(status="judge_failed", error=f"{type(exc).__name__}: {exc}", cost_nano=bound)
                    spent += rec["cost_nano"]
                    fh.write(json.dumps(rec, ensure_ascii=False) + LF)
                    fh.flush()
                    if rec["status"] == "scored":
                        break
        print(f"{set_} {config}: {calls} calls; spend now ${spent/1e9:.6f} of ${cap/1e9:.2f}", flush=True)
    print("ALL-DONE")
    return 0


# -------------------------------------------------------------------- report


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


def next_action(r: dict[str, Any] | None) -> int | None:
    if not r or r.get("status") != "scored":
        return None
    if "next_action" in r:
        return r["next_action"]
    return json.loads(r["output_text"])["next_action"]["score"]


def counts(vs: list[str]) -> dict[str, int]:
    return {k: vs.count(k) for k in ("accepted", "rejected", "unscored")}


def correct(label: str, na: int | None) -> bool | None:
    """The readout: next_action 2 where the label is y, below 2 where it is n; None if unscored."""
    if na is None:
        return None
    return (na == 2) == (label == "y")


def saved_old_h2() -> dict[tuple[str, int], dict[str, Any]]:
    out: dict[tuple[str, int], dict[str, Any]] = {}
    for line in SAVED_V3_SCORES.read_text(encoding="utf-8").splitlines():
        r = json.loads(line)
        if r.get("case_id") == "H2" and r.get("judge_prompt_version") == JUDGE and r.get("status") == "scored":
            out.setdefault((r["slot_key"], 1), {"status": "scored", "decision": r["decision"],
                                                "next_action": r["judgment"]["next_action"]["score"]})
    return out


def report(args: argparse.Namespace) -> int:
    verify()
    results = args.results_dir or RESULTS
    lab = labels() if args.labels is None else {m.group(1): m.group(2).strip().lower() for m in ACCEPT.finditer(sheet_text(args.labels))}
    if len(lab) != N_ITEMS or any(v not in ("y", "n") for v in lab.values()):
        raise SystemExit("the sheet needs y or n on every Accept line")
    key = json.loads(KEY.read_text(encoding="utf-8"))["items"]
    res = {(s, c): finals(results / f"{s}-{c}.jsonl") for s, c in PASSES}
    # baselines that need no new call
    res[("h2", "old")] = saved_old_h2()
    res[("h2", "prev")] = finals(R1 / "results/h2-new.jsonl")
    res[("round1", "prev")] = finals(R1 / "results/fresh-new.jsonl")
    res[("tobias", "prev")] = finals(R1 / "results/known-new.jsonl")
    tlab = labels_from(V5 / "review_sheet.md")
    rlab = labels_from(R1 / "review_sheet.md")
    tob_ids = [rid for rid, _, _ in tobias_items()]
    r1_ids = [rid for rid, _, _ in round1_items()]

    def judgments(config: str, version: str | None = None, label: str | None = None) -> list[tuple[str, int]]:
        ks = [(rid, d) for rid in sorted(key) for d in range(1, DRAWS[config] + 1)]
        return [k for k in ks if (version is None or key[k[0]]["version"] == version) and (label is None or lab[k[0]] == label)]

    def readout(config: str, ks: list[tuple[str, int]]) -> dict[str, int]:
        c = [correct(lab[i], next_action(res[("fresh", config)].get((i, d)))) for i, d in ks]
        return {"right": c.count(True), "wrong": c.count(False), "unscored": c.count(None)}

    def two_in_both(config: str, versions: tuple[str, ...]) -> list[str]:
        return sorted({i for (i, d) in judgments(config) if key[i]["version"] in versions and lab[i] == "n"
                       and all(next_action(res[("fresh", config)].get((i, dd))) == 2 for dd in (1, 2))})

    g = {
        "A1_C_y": readout("new", judgments("new", "C", "y")),
        "A2_U_n": readout("new", judgments("new", "U", "n")),
        "A3_UP_y": readout("new", judgments("new", "U", "y") + judgments("new", "P", "y")),
        "A4_P_n": readout("new", judgments("new", "P", "n")),
        "A5_C_n": readout("new", judgments("new", "C", "n")),
    }
    pairs = {}
    for rid in key:
        pairs.setdefault((key[rid]["frame"], key[rid]["reply_key"]), []).append(rid)
    pair_rows, pair_right = [], 0
    for (frame, rk), ids in sorted(pairs.items()):
        cells = {key[i]["version"]: [correct(lab[i], next_action(res[("fresh", "new")].get((i, d)))) for d in (1, 2)] for i in ids}
        ok = all(all(c is True for c in v) for v in cells.values())
        pair_right += ok
        pair_rows.append({"frame": frame, "reply": rk, "ids": {key[i]["version"]: i for i in ids},
                          "labels": {key[i]["version"]: lab[i] for i in ids},
                          "new_next_action": {key[i]["version"]: [next_action(res[("fresh", "new")].get((i, d))) for d in (1, 2)] for i in ids},
                          "prev_next_action": {key[i]["version"]: next_action(res[("fresh", "prev")].get((i, 1))) for i in ids},
                          "all_right": ok})
    n_up = lambda config: [k for k in judgments(config) if key[k[0]]["version"] in ("U", "P") and lab[k[0]] == "n"]  # noqa: E731
    share2 = lambda config: [sum(next_action(res[("fresh", config)].get(k)) == 2 for k in n_up(config)), len(n_up(config))]  # noqa: E731
    reg_ks = [("tobias", i, tlab[i]) for i in tob_ids] + [("round1", i, rlab[i]) for i in r1_ids]
    reg_c = [correct(lb, next_action(res[(s, "new")].get((i, d)))) for s, i, lb in reg_ks for d in (1, 2)]
    reg_both2 = sorted(i for s, i, lb in reg_ks if lb == "n" and all(next_action(res[(s, "new")].get((i, d))) == 2 for d in (1, 2)))
    h2_new = [verdict(res[("h2", "new")].get(k)) for k in sorted(res[("h2", "new")])]
    fresh_new_all = [verdict(res[("fresh", "new")].get(k)) for k in judgments("new")]
    s5, sp = share2("new"), share2("prev")
    crit = {
        "A1": g["A1_C_y"]["wrong"] <= 1,
        "A2": g["A2_U_n"]["wrong"] <= 1 and not two_in_both("new", ("U",)),
        "A3": g["A3_UP_y"]["wrong"] <= 1,
        "A4": g["A4_P_n"]["wrong"] <= 1 and not two_in_both("new", ("P",)),
        "A5": g["A5_C_n"]["wrong"] == 0,
        "A6": pair_right >= 12,
        # amended by Nishanth before scoring: a tie at zero passes; R2 then carries the attribution
        "A7": (s5[1] > 0 and sp[1] > 0 and (s5[0] / s5[1] < sp[0] / sp[1] or (s5[0] == 0 and sp[0] == 0))),
        "R1": h2_new.count("accepted") >= 10,
        "R2": reg_c.count(False) + reg_c.count(None) <= 2 and not reg_both2,
        "C1": fresh_new_all.count("unscored") <= len(fresh_new_all) * 0.15,
    }
    summary: dict[str, Any] = {"criteria": crit, "pass": all(crit.values()), "readout_new": g,
                               "pairs_all_right": [pair_right, len(pair_rows)],
                               "n_items_next_action_2": {"new": s5, "prev": sp},
                               "regression_readout": {"right": reg_c.count(True), "wrong": reg_c.count(False), "unscored": reg_c.count(None), "n_at_2_in_both_draws": reg_both2},
                               "pairs": pair_rows}
    verdicts = {}
    for name, (s, c) in {"fresh/new": ("fresh", "new"), "fresh/prev": ("fresh", "prev"), "h2/new": ("h2", "new"),
                         "h2/prev (round 1 records)": ("h2", "prev"), "h2/old (saved judge-v1 records)": ("h2", "old"),
                         "tobias/new": ("tobias", "new"), "round1/new": ("round1", "new")}.items():
        verdicts[name] = counts([verdict(r) for r in res[(s, c)].values()])
    verdicts["tobias/prev (round 1 records)"] = counts([verdict(r) for (i, d), r in res[("tobias", "prev")].items() if i in tob_ids])
    verdicts["round1/prev (round 1 records)"] = counts([verdict(r) for (i, d), r in res[("round1", "prev")].items() if i in r1_ids])
    summary["verdicts"] = verdicts
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
    r = sub.add_parser("run-all")
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
    return run_all(a)


if __name__ == "__main__":
    raise SystemExit(main())
