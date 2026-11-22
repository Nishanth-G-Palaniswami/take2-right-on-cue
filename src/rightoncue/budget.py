"""Budget guard for `score` (Nishanth's decision of 2026-11-21, option B).

All money is integer nano-US-dollars (1 USD = 10**9 nano-USD). The PRD rates in
USD per 1M tokens are exactly nano-USD per token, so every cost is an integer.

Spend so far is computed from recorded usage only:
- generation usage from every budget run's slots.jsonl, priced by the requested
  model (Gemini models are not OpenAI-billed and are priced at 0);
- judge usage from every judge record with a response in the budget runs' score
  files, across all judge versions, at the judge model's (Mini) rates.

A record whose API call raised (no response at all) has no recorded usage and is
counted at 0; the count of such calls is reported. A record WITH a response but
without usable usage is refused: the spend would be a guess.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from .runs import ManifestError, load_manifest, manifest_models, provider_for

NANO_PER_USD = 10**9
# USD per 1M tokens (PRD) == nano-USD per token: (input, output).
OPENAI_PRICES: dict[str, tuple[int, int]] = {
    "gpt-5.4": (2_500, 15_000),
    "gpt-5.4-mini": (750, 4_500),
}
JUDGE_PRICE_MODEL = "gpt-5.4-mini"  # the judge model (scoring.JUDGE_MODEL)
GEMINI_NOTE = "Gemini generation is priced at $0: it is not billed by OpenAI."
# On every judge attempt made under a budget: the nano-USD the guard charged for it
# (actual usage, or the call's maximum when usage is missing). Spend so far prefers it.
CHARGE_FIELD = "budget_charged_nano"
# Appended and fsynced before each budgeted judge call; its final record carries the
# same attempt_id. Spend counts one charge per attempt_id: the final's, or the
# pending maximum when no final record was written (a crash or kill).
PENDING_STATUS = "judge_pending"
ATTEMPT_FIELD = "attempt_id"


def interrupted_attempt_ids(records: Any) -> set[str]:
    """attempt_ids that have a pending record and no final record."""
    pending: set[str] = set()
    final: set[str] = set()
    for rec in records:
        attempt = rec.get(ATTEMPT_FIELD)
        if not isinstance(attempt, str):
            continue
        (pending if rec.get("status") == PENDING_STATUS else final).add(attempt)
    return pending - final


class BudgetInputError(ValueError):
    """The budget or the recorded spend can't be determined; nothing is called (exit 2)."""


def parse_usd(text: str) -> int:
    """A positive USD amount from its decimal string, in nano-USD (exact, no float)."""
    try:
        value = Decimal(text)
    except InvalidOperation:
        raise BudgetInputError(f"--budget-usd: {text!r} is not a number") from None
    if not value.is_finite() or value <= 0:
        raise BudgetInputError(f"--budget-usd: must be a positive amount, got {text!r}")
    nano = value * NANO_PER_USD
    if nano != nano.to_integral_value():
        raise BudgetInputError(f"--budget-usd: {text!r} has more precision than 1e-9 USD")
    return int(nano)


def fmt_usd(nano: int) -> str:
    """Display only: dollars with 6 decimals (exact values are kept in nano-USD)."""
    return f"${Decimal(nano) / NANO_PER_USD:.6f}"


def prices_for(model: str, provider: str) -> tuple[int, int]:
    if provider == "gemini":
        return (0, 0)
    if model in OPENAI_PRICES:
        return OPENAI_PRICES[model]
    raise BudgetInputError(
        f"no price is fixed for model {model!r}; the budget guard prices only "
        f"{', '.join(OPENAI_PRICES)} (and Gemini models at $0)"
    )


def usage_cost(usage: Any, prices: tuple[int, int]) -> int | None:
    """Cost of normalized usage, or None if input or output tokens are missing.

    OpenAI output_tokens already include reasoning tokens
    (output_tokens_details.reasoning_tokens is a part of them), so reasoning is
    counted as output exactly once by pricing output_tokens alone.
    """
    if not isinstance(usage, dict):
        return None
    tokens_in, tokens_out = usage.get("input_tokens"), usage.get("output_tokens")
    if type(tokens_in) is not int or type(tokens_out) is not int:
        return None
    return tokens_in * prices[0] + tokens_out * prices[1]


def max_call_cost(request: dict[str, Any]) -> int:
    """Upper bound on one judge call's cost, before it is made.

    Input: the UTF-8 byte length of the canonical JSON of the exact request
    (instructions, input, schema and settings). Assumption: every input token
    covers at least one byte of that text, and the JSON syntax bytes (quotes,
    keys, braces) far outnumber the few per-message framing tokens the API adds,
    so the byte count bounds the input tokens. Output: max_output_tokens.
    """
    canonical = json.dumps(request, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    max_out = request.get("max_output_tokens")
    if type(max_out) is not int or max_out <= 0:
        raise BudgetInputError(
            "a judge request has no positive max_output_tokens, so its cost has no bound"
        )
    price_in, price_out = OPENAI_PRICES[JUDGE_PRICE_MODEL]
    return len(canonical.encode("utf-8")) * price_in + max_out * price_out


@dataclass
class Spend:
    generation: int = 0
    judge: int = 0
    gemini_replies: int = 0
    no_response: dict[str, int] = field(default_factory=dict)  # run_id -> calls at $0

    @property
    def total(self) -> int:
        return self.generation + self.judge


def _jsonl(path: Path, what: str) -> list[dict[str, Any]]:
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise BudgetInputError(f"{path.as_posix()}: cannot read {what} ({exc})") from None
    out: list[dict[str, Any]] = []
    for number, line in enumerate(text.split("\n"), start=1):
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            raise BudgetInputError(f"{path.as_posix()}:{number}: unreadable {what} record") from None
        if not isinstance(record, dict):
            raise BudgetInputError(f"{path.as_posix()}:{number}: {what} record is not an object")
        out.append(record)
    return out


def spend_so_far(run_dirs: list[Path], scores_dir: Path) -> Spend:
    """Recorded spend of the budget runs: generation plus every judge call."""
    spend = Spend()
    judge_prices = OPENAI_PRICES[JUDGE_PRICE_MODEL]
    for run_dir in run_dirs:
        try:
            manifest = load_manifest(run_dir)
            providers = {m["model"]: m["provider"] for m in manifest_models(manifest)}
        except (OSError, ValueError, KeyError, ManifestError) as exc:
            raise BudgetInputError(f"{run_dir.as_posix()}: cannot read the run manifest ({exc})") from None
        run_id = manifest.get("run_id")
        if not isinstance(run_id, str):
            raise BudgetInputError(f"{run_dir.as_posix()}/manifest.json: run_id is not a string")
        slots = run_dir / "slots.jsonl"
        for rec in _jsonl(slots, "slots.jsonl") if slots.exists() else []:
            model = rec.get("requested_model")
            if not isinstance(model, str):
                raise BudgetInputError(f"run {run_id}: a slot record has no requested_model")
            try:
                provider = rec.get("provider") or providers.get(model) or provider_for(model)
            except ValueError as exc:
                raise BudgetInputError(f"run {run_id}: {exc}") from None
            prices = prices_for(model, provider)
            if prices == (0, 0):
                spend.gemini_replies += 1
                continue
            if rec.get("raw_response") is None:  # the call raised: no response, no usage
                spend.no_response[run_id] = spend.no_response.get(run_id, 0) + 1
                continue
            cost = usage_cost(rec.get("usage_normalized"), prices)
            if cost is None:
                raise BudgetInputError(
                    f"run {run_id}: generation record {rec.get('slot_key')} has a response "
                    "but no recorded input and output tokens, so the spend can't be computed"
                )
            spend.generation += cost
        score_path = scores_dir / f"{run_id}.jsonl"
        records = _jsonl(score_path, "score file") if score_path.exists() else []
        spend.judge += _attempt_charges(records, run_id, score_path)
        for rec in records:
            if ATTEMPT_FIELD in rec:  # counted once per attempt above
                continue
            if CHARGE_FIELD in rec:  # charged by the guard when the call was made
                charged = rec[CHARGE_FIELD]
                if type(charged) is not int or charged < 0:
                    raise BudgetInputError(
                        f"run {run_id}: judge record {rec.get('slot_key')} in "
                        f"{score_path.as_posix()} has an invalid {CHARGE_FIELD}"
                    )
                spend.judge += charged
                continue
            if rec.get("judge_model") is None:  # no judge call (empty reply, budget stop)
                continue
            response = rec.get("judge_response")
            if response is None:  # the judge call raised: no response, no usage
                spend.no_response[run_id] = spend.no_response.get(run_id, 0) + 1
                continue
            cost = usage_cost(
                response.get("usage_normalized") if isinstance(response, dict) else None,
                judge_prices,
            )
            if cost is None:
                raise BudgetInputError(
                    f"run {run_id}: judge record {rec.get('slot_key')} in "
                    f"{score_path.as_posix()} has a response but no recorded input and "
                    "output tokens, so the spend can't be computed"
                )
            spend.judge += cost
    return spend


def _charge_of(rec: dict[str, Any], run_id: str, score_path: Path) -> int:
    charged = rec.get(CHARGE_FIELD)
    if type(charged) is not int or charged < 0:
        raise BudgetInputError(
            f"run {run_id}: judge record {rec.get('slot_key')} in {score_path.as_posix()} "
            f"has a missing or invalid {CHARGE_FIELD}"
        )
    return charged


def _attempt_charges(records: list[dict[str, Any]], run_id: str, score_path: Path) -> int:
    """One charge per attempt_id: its final record's, else its pending maximum."""
    by_attempt: dict[str, dict[str, list[dict[str, Any]]]] = {}
    for rec in records:
        attempt = rec.get(ATTEMPT_FIELD)
        if attempt is None:
            continue
        if not isinstance(attempt, str):
            raise BudgetInputError(f"run {run_id}: a score record has an invalid {ATTEMPT_FIELD}")
        kind = "pending" if rec.get("status") == PENDING_STATUS else "final"
        by_attempt.setdefault(attempt, {"pending": [], "final": []})[kind].append(rec)
    total = 0
    for attempt, group in by_attempt.items():
        if len(group["pending"]) > 1 or len(group["final"]) > 1:
            raise BudgetInputError(
                f"run {run_id}: attempt {attempt} has more than one pending or final "
                f"record in {score_path.as_posix()}"
            )
        chosen = group["final"][0] if group["final"] else group["pending"][0]
        total += _charge_of(chosen, run_id, score_path)
    return total


@dataclass
class Budget:
    """The guard's state during one `score` command."""

    limit: int
    spent: int
    stopped: bool = False
    spent_this_command: int = 0

    def allows(self, max_cost: int) -> bool:
        """Stop only when spend + maximum is strictly greater than the budget."""
        return not self.stopped and self.spent + max_cost <= self.limit

    def charge(self, record: dict[str, Any], max_cost: int) -> int:
        """Add a finished call's actual usage cost, or its maximum if usage is missing.

        Returns the charge, which the caller records on the attempt record as
        CHARGE_FIELD so later commands count the same amount.
        """
        response = record.get("judge_response")
        usage = response.get("usage_normalized") if isinstance(response, dict) else None
        cost = usage_cost(usage, OPENAI_PRICES[JUDGE_PRICE_MODEL])
        cost = max_cost if cost is None else cost
        self.spent += cost
        self.spent_this_command += cost
        return cost
