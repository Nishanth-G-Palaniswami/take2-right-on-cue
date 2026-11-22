"""Prompt v3 experiment: generate v2 and v3 replies on the frozen conversations, then build the
blind review sheet. Pre-registered in docs/measurements/2026-11-22-prompt-v3-plan.md.

  uv run python scripts/prompt_v3_experiment.py generate      # safe to re-run: completed steps are skipped
  uv run python scripts/prompt_v3_experiment.py sheet         # once every step is complete

Runs are written to holdout-private/prompt-v3/runs (gitignored), because their files name the model
and the prompt. They are committed by hash with the sheet and revealed after the labels.
"""

from __future__ import annotations

import hashlib
import json
import random
import secrets
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
PUB = REPO / "docs/measurements/prompt-v3"
PRIV = REPO / "holdout-private/prompt-v3"
RUNS = PRIV / "runs"
LOG = PRIV / "generation_log.jsonl"
CASES = [f"F{i}" for i in range(1, 9)]
PROMPTS = ("v2", "v3")
OPENAI_MODELS = ("gpt-5.4", "gpt-5.4-mini")
GEMINI = "gemini-3.5-flash"
SAMPLES = 2


def steps() -> list[dict]:
    """The registered order: OpenAI v2, OpenAI v3, then Gemini one conversation at a time,
    alternating which prompt goes first, so a quota stop affects both prompts alike."""
    out = [{"step": f"openai-{p}", "prompt": p, "models": list(OPENAI_MODELS), "cases": CASES} for p in PROMPTS]
    for i, case in enumerate(CASES):
        for p in (PROMPTS if i % 2 == 0 else PROMPTS[::-1]):
            out.append({"step": f"gemini-{case}-{p}", "prompt": p, "models": [GEMINI], "cases": [case]})
    return out


def log() -> list[dict]:
    return [json.loads(x) for x in LOG.read_text(encoding="utf-8").splitlines() if x.strip()] if LOG.exists() else []


def slots(run_id: str) -> list[dict]:
    return [json.loads(x) for x in (RUNS / run_id / "slots.jsonl").read_text(encoding="utf-8").splitlines() if x.strip()]


def generate() -> int:
    RUNS.mkdir(parents=True, exist_ok=True)
    done = {e["step"] for e in log() if e["complete"]}
    for s in steps():
        if s["step"] in done:
            continue
        cmd = ["uv", "run", "--no-sync", "next-turn", "run", "--prompt", f"prompts/{s['prompt']}.md",
               *[a for c in s["cases"] for a in ("--case", f"docs/measurements/prompt-v3/cases/{c}.jsonl")],
               *[a for m in s["models"] for a in ("--model", m)],
               "--samples", str(SAMPLES), "--reasoning-effort", "none", "--runs-dir", str(RUNS)]
        if GEMINI in s["models"]:
            cmd += ["--gemini-thinking-level", "minimal"]
        res = subprocess.run(cmd, cwd=REPO, capture_output=True, text=True, encoding="utf-8")
        run_id = next((ln.split(":", 1)[1].strip() for ln in res.stdout.splitlines() if ln.startswith("run_id:")), None)
        if res.returncode != 0 or run_id is None:
            print(res.stdout[-2000:], res.stderr[-2000:])
            raise SystemExit(f"{s['step']}: the run command failed")
        statuses = [r["status"] for r in slots(run_id)]
        complete = len(statuses) == len(s["models"]) * len(s["cases"]) * SAMPLES and all(x == "ok" for x in statuses)
        entry = {**s, "run_id": run_id, "statuses": statuses, "complete": complete}
        with open(LOG, "a", encoding="utf-8", newline="\n") as fh:
            fh.write(json.dumps(entry) + "\n")
        print(f"{s['step']}: run {run_id}: {statuses}")
        if not complete:
            print("STOPPED at the first incomplete step; re-run after the cause is cleared (for a Gemini quota, after midnight Pacific)")
            return 2
    print("all steps complete")
    return 0


def sheet() -> int:
    if any((PUB / n).exists() for n in ("review_sheet.md", "commitment.json")):
        raise SystemExit("the sheet already exists; it is built once")
    entries = log()
    if {e["step"] for e in entries if e["complete"]} != {s["step"] for s in steps()}:
        raise SystemExit("not every step is complete")
    replies = []
    for e in entries:
        if not e["complete"]:
            continue  # an incomplete attempt stays in the log and the private files, not on the sheet
        man = json.loads((RUNS / e["run_id"] / "manifest.json").read_text(encoding="utf-8"))
        turns = {c["case_id"]: c["turns"] for c in man["cases"]}
        for r in slots(e["run_id"]):
            replies.append({"slot_key": r["slot_key"], "run_id": e["run_id"], "prompt": man["prompt"]["version"],
                            "model": r["requested_model"], "case": r["case_id"], "sample": r["sample_index"],
                            "text": r["output_text"], "turns": turns[r["case_id"]]})
    rng = random.SystemRandom()
    rng.shuffle(replies)
    key = {"salt": secrets.token_hex(16), "items": {}}
    lines = [
        "# Prompt v3 experiment: blind review sheet",
        "",
        "Label each reply as Riley's next turn: `y` if it is an acceptable next turn, `n` if not, by your own judgment.",
        "",
        "- Model and prompt are hidden. Several items share a conversation.",
        "- Please label every item before opening anything in `holdout-private/prompt-v3/` or seeing any score or suggested label.",
        "- A reason is optional. Note below whether you used an AI assistant.",
        "",
        "Used an AI assistant while labelling (yes/no):",
        "",
    ]
    for n, r in enumerate(replies, start=1):
        rid = f"R{n:02d}"
        key["items"][rid] = {k: r[k] for k in ("slot_key", "run_id", "prompt", "model", "case", "sample")}
        lines += ["---", "", f"## {rid}", "", "Conversation so far:", ""]
        for t in r["turns"]:
            lines += [f"> **{'Riley' if t['role'] == 'agent' else 'Applicant'}:** {t['utterance']}", ">"]
        lines.pop()
        lines += ["", "Riley's proposed next turn:", "", "> " + r["text"].replace("\n", "\n> "), "",
                  f"Accept {rid}? (y/n):", "", "Reason (optional):", ""]
    (PUB / "review_sheet.md").write_text("\n".join(lines), encoding="utf-8", newline="\n")
    (PRIV / "key.json").write_text(json.dumps(key, indent=1) + "\n", encoding="utf-8", newline="\n")
    sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
    private = sorted([PRIV / "key.json", LOG, *RUNS.rglob("*.json*")])
    commitment = {"private_files": {p.relative_to(PRIV).as_posix(): sha(p) for p in private},
                  "public_files": {"review_sheet.md": sha(PUB / "review_sheet.md")}}
    (PUB / "commitment.json").write_text(json.dumps(commitment, indent=1) + "\n", encoding="utf-8", newline="\n")
    print(f"sheet: {len(replies)} replies; commitment over {len(private)} private files")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd not in ("generate", "sheet"):
        raise SystemExit("usage: prompt_v3_experiment.py generate|sheet")
    raise SystemExit(generate() if cmd == "generate" else sheet())
