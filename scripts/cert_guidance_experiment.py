"""Certification-guidance experiment: score fixed replies under two criteria configurations.

Pre-registered in docs/measurements/2026-11-22-cert-guidance-plan.md. Both configurations use
judge-v1 unchanged (prompt, model, settings, scorer-1, decide()); they differ only in the case
criteria for conversations where the license and required certifications are confirmed.

  uv run python scripts/cert_guidance_experiment.py verify --dir <dir holding the three private files>
  uv run python scripts/cert_guidance_experiment.py run --config current --criteria-dir <dir> --cap-usd 0.60
  uv run python scripts/cert_guidance_experiment.py run --config candidate --criteria-dir <dir> --cap-usd 0.60
  uv run python scripts/cert_guidance_experiment.py report --key-dir <dir>

Cost control, as scripts/judge_calibration.py: before every call (retries included), the spend
recorded in the output directory (both configurations) plus the call's maximum cost must fit
within --cap-usd, or the script stops. The client is built with max_retries=0. A judgment that
needs review or fails is retried once, immediately. Output files are write-once.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any

from rightoncue import scoring
from rightoncue.transcript import Turn

REPO = Path(__file__).resolve().parents[1]
PUB = REPO / "docs/measurements/cert-guidance"
CONFIGS = ("current", "candidate")
PRIVATE = ("key.json", "criteria-current.toml", "criteria-candidate.toml")
JUDGE_VERSION = "judge-v1"
IN_NANO, OUT_NANO = 750, 4_500  # gpt-5.4-mini nano-USD per token (PRD rates)
ACCEPT_LINE = re.compile(r"^Accept (C\d\d)\? \(y/n\):[ \t]*(.*?)[ \t]*$", re.MULTILINE)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify(directory: Path) -> None:
    commitment = json.loads((PUB / "commitment.json").read_text(encoding="utf-8"))
    for name, digest in commitment["private_files"].items():
        if sha(directory / name) != digest:
            raise SystemExit(f"{name} in {directory} does not match the commitment")
    if sha(PUB / "examples.json") != commitment["public_files"]["examples.json"]:
        raise SystemExit("examples.json does not match the commitment")


def examples() -> tuple[dict[str, list[Turn]], list[dict[str, str]]]:
    ex = json.loads((PUB / "examples.json").read_text(encoding="utf-8"))
    convs = {k: [Turn.model_validate(t) for t in v] for k, v in ex["conversations"].items()}
    return convs, ex["items"]


def max_cost_nano(request: dict[str, Any]) -> int:
    canonical = json.dumps(request, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return len(canonical.encode("utf-8")) * IN_NANO + int(request["max_output_tokens"]) * OUT_NANO


def records(out_dir: Path, config: str | None = None) -> list[dict[str, Any]]:
    names = [f"{config}.jsonl"] if config else [f"{c}.jsonl" for c in CONFIGS]
    out: list[dict[str, Any]] = []
    for n in names:
        p = out_dir / n
        if p.exists():
            out += [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines() if x.strip()]
    return out


def run(args: argparse.Namespace) -> int:
    verify(args.criteria_dir)
    judge = scoring.load_judge_prompt(JUDGE_VERSION)
    criteria = scoring.load_criteria(args.criteria_dir / f"criteria-{args.config}.toml")
    convs, items = examples()
    out_path = args.out_dir / f"{args.config}.jsonl"
    if out_path.exists():
        raise SystemExit(f"{out_path} exists; each configuration is scored once")
    cap = round(args.cap_usd * 1e9)
    spent = sum(r["cost_nano"] for r in records(args.out_dir))
    if args.dry_run:
        client: Any = _FakeClient()
    else:
        from dotenv import load_dotenv
        from openai import OpenAI

        load_dotenv(REPO / ".env", override=False)
        client = OpenAI(max_retries=0)
    calls = 0
    args.out_dir.mkdir(parents=True, exist_ok=True)
    with open(out_path, "x", encoding="utf-8", newline="\n") as fh:
        for item in items:
            turns, reply = convs[item["conversation"]], item["reply"]
            request = scoring.build_judge_request(
                judge.text, turns, reply, criteria[item["conversation"]], scorer_version=judge.scorer_version
            )
            for attempt in (1, 2):
                bound = max_cost_nano(request)
                if spent + bound > cap:
                    print(f"STOPPED by cap before {item['id']} attempt {attempt}: spent {spent/1e9:.5f}, max {bound/1e9:.5f}")
                    return 3
                rec: dict[str, Any] = {
                    "id": item["id"], "config": args.config, "attempt": attempt,
                    "judge_prompt_version": judge.version, "judge_prompt_sha256": judge.sha256,
                    "judge_request_sha256": scoring.request_sha256(request),
                }
                calls += 1
                try:
                    resp = client.responses.create(**request)
                    dump = resp.model_dump(mode="json")
                    usage = dump.get("usage") or {}
                    tin, tout = usage.get("input_tokens"), usage.get("output_tokens")
                    cost = tin * IN_NANO + tout * OUT_NANO if isinstance(tin, int) and isinstance(tout, int) else bound
                    judgment, errors = scoring.validate_judge_output(
                        resp.status, resp.output_text, turns, reply, scorer_version=judge.scorer_version
                    )
                    rec.update(response_id=dump.get("id"), output_text=resp.output_text, usage=usage, cost_nano=cost)
                    if judgment is None:
                        rec.update(status="needs_review", validation_errors=errors)
                    else:
                        dec = scoring.decide(scoring.check_structure(reply), judgment)
                        rec.update(status="scored", decision=dec.to_dict())
                except Exception as exc:  # recorded and charged at its maximum, then retried once
                    rec.update(status="judge_failed", error=f"{type(exc).__name__}: {exc}", cost_nano=bound)
                spent += rec["cost_nano"]
                fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
                fh.flush()
                if rec["status"] == "scored":
                    break
    print(f"{args.config}: {calls} calls; experiment spend now ${spent/1e9:.6f} of ${cap/1e9:.2f}")
    return 0


def verdicts(out_dir: Path, config: str) -> dict[str, str]:
    """Final verdict per item: acceptable / not acceptable, or unscored after the retry."""
    final: dict[str, str] = {}
    for r in records(out_dir, config):
        if r["status"] == "scored":
            final[r["id"]] = "acceptable" if r["decision"]["acceptable"] else "not acceptable"
        else:
            final.setdefault(r["id"], "unscored")
    return final


def report(args: argparse.Namespace) -> int:
    verify(args.key_dir)
    key = json.loads((args.key_dir / "key.json").read_text(encoding="utf-8"))["items"]
    labels = {m.group(1): m.group(2) for m in ACCEPT_LINE.finditer(args.labels.read_text(encoding="utf-8"))}
    if sorted(labels) != sorted(key) or any(v not in ("y", "n") for v in labels.values()):
        raise SystemExit("the label sheet must have y or n for every item")
    v = {c: verdicts(args.out_dir, c) for c in CONFIGS}
    for c in CONFIGS:
        good_rej = sorted(i for i in key if labels[i] == "y" and v[c].get(i) == "not acceptable")
        bad_acc = sorted(i for i in key if labels[i] == "n" and v[c].get(i) == "acceptable")
        unscored = sorted(i for i in key if v[c].get(i, "unscored") == "unscored")
        print(f"{c}: good replies rejected {len(good_rej)} {good_rej}; bad replies accepted {len(bad_acc)} {bad_acc}; unscored {len(unscored)} {unscored}")
    changed = sorted(i for i in key if v["current"].get(i) != v["candidate"].get(i))
    for i in changed:
        part = "changed criteria" if key[i]["conversation"] in ("P", "Q", "R") else "identical criteria (noise)"
        print(f"changed {i} [{part}] label {labels[i]}: {v['current'].get(i)} -> {v['candidate'].get(i)}")
    spent = sum(r["cost_nano"] for r in records(args.out_dir))
    print(f"verdicts changed: {len(changed)}; calls {len(records(args.out_dir))}; spend ${spent/1e9:.6f}")
    return 0


class _FakeClient:
    """Offline stand-in for --dry-run: returns a valid scorer-1 judgment with all 2s."""

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


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    v = sub.add_parser("verify")
    v.add_argument("--dir", type=Path, required=True)
    r = sub.add_parser("run")
    r.add_argument("--config", choices=CONFIGS, required=True)
    r.add_argument("--criteria-dir", type=Path, required=True)
    r.add_argument("--cap-usd", type=float, required=True)
    r.add_argument("--dry-run", action="store_true")
    rep = sub.add_parser("report")
    rep.add_argument("--key-dir", type=Path, required=True)
    rep.add_argument("--labels", type=Path, default=PUB / "label_sheet.md")
    for s in (r, rep):
        s.add_argument("--out-dir", type=Path, default=PUB / "results")
    a = ap.parse_args()
    if a.cmd == "verify":
        verify(a.dir)
        print("all files match the commitment")
        return 0
    return run(a) if a.cmd == "run" else report(a)


if __name__ == "__main__":
    raise SystemExit(main())
