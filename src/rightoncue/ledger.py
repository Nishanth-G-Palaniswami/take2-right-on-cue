"""Spending ledger and guarded API clients for live runs (hosted, or local with a budget).

All money is integer nano-US-dollars (1 USD = 10**9 nano-USD).

The ledger is an append-only JSONL file. Before every paid call a `reserve` entry
holds the call's maximum cost; after the call a `settle` entry holds its actual cost
(or the maximum when usage is missing or the call raised). Spend is the sum of the
settled actual costs plus the maximum of every reservation that has no settle entry,
so a crash or kill between the two counts the maximum, never $0.

Concurrency: one process-wide `threading.Lock` serialises every read-check-append,
and the file is re-read under it on every reservation (no in-memory cache). This is
safe for one process with many threads (Streamlit sessions). It is NOT safe for
several processes writing the same file.
"""

from __future__ import annotations

import json
import os
import threading
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Literal

from . import budget, gemini, openai_responses

Kind = Literal["generation", "judge"]
Basis = Literal["usage", "maximum_no_usage", "maximum_raised"]
KINDS: tuple[str, ...] = ("generation", "judge")
BASES: tuple[str, ...] = ("usage", "maximum_no_usage", "maximum_raised")

# nano-USD per token == USD per 1M tokens: (input, output).
# OpenAI: budget.py's PRD rates, reused unchanged.
# Gemini: Google's pricing page (ai.google.dev/gemini-api/docs/pricing, read
# 2026-11-22) does not list gemini-3.5-flash. Every saved Gemini reply reports
# returned_model gemini-3.6-flash, whose paid tier is $0.75/M input and $3.75/M
# output through 2026-12-31 and $1.50/M and $7.50/M from 2027-01-01, output
# including thinking tokens. Reserve and settle both use the higher 2027 rates.
LEDGER_PRICES: dict[str, tuple[int, int]] = {
    "gpt-5.4": budget.OPENAI_PRICES["gpt-5.4"],
    "gpt-5.4-mini": budget.OPENAI_PRICES["gpt-5.4-mini"],
    "gemini-3.5-flash": (1_500, 7_500),
}

# One lock for every ledger in the process (module level: app.py re-executes on
# every Streamlit rerun, this module does not).
_LOCK = threading.Lock()


class LedgerError(RuntimeError):
    """The ledger can't be read or written, or a line is corrupt. Live runs stop."""


class BudgetExceeded(RuntimeError):
    """A call was refused before any request: spend plus its maximum exceeds the budget."""


class UnknownModelPrice(ValueError):
    """The ledger has no price for this model, so its cost has no bound."""


def prices_for(model: Any) -> tuple[int, int]:
    if isinstance(model, str) and model in LEDGER_PRICES:
        return LEDGER_PRICES[model]
    raise UnknownModelPrice(
        f"no ledger price for model {model!r}; priced: {', '.join(LEDGER_PRICES)}"
    )


def canonical_bytes(request: dict[str, Any]) -> int:
    """UTF-8 length of the request's canonical JSON, as budget.max_call_cost counts it."""
    text = json.dumps(request, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return len(text.encode("utf-8"))


def max_call_cost(request: dict[str, Any], model: str, max_output_tokens: Any) -> int:
    """Upper bound on one call's cost before it is made.

    Input: the canonical JSON byte length of the exact request times the input price
    (budget.py's assumption: every input token covers at least one byte of that text).
    Output: the request's output cap times the output price. For OpenAI the cap
    includes reasoning tokens. For Gemini, Google's thinking guide
    (aistudio.google.com/docs/thinking, read 2026-11-22) says thinking can "exhaust
    `max_output_tokens`", i.e. thinking draws on the cap; it does not say so
    model by model, so hosted runs also fix thinking to MINIMAL. Settlement counts
    thinking tokens as output either way.
    """
    price_in, price_out = prices_for(model)
    if type(max_output_tokens) is not int or max_output_tokens <= 0:
        raise BudgetExceeded(
            f"a {model} request has no positive max_output_tokens, so its cost has no "
            "bound; no request was made"
        )
    return canonical_bytes(request) * price_in + max_output_tokens * price_out


def _now() -> str:
    return datetime.now(UTC).isoformat()


@dataclass(frozen=True)
class LedgerState:
    spent_nano: int
    open_reservations: int
    settled: int


def _check_entry(entry: Any, where: str) -> dict[str, Any]:
    if not isinstance(entry, dict):
        raise LedgerError(f"{where}: entry is not a JSON object")
    kind = entry.get("type")
    if not isinstance(entry.get("id"), str) or not entry["id"]:
        raise LedgerError(f"{where}: entry has no id")
    if entry.get("kind") not in KINDS or not isinstance(entry.get("model"), str):
        raise LedgerError(f"{where}: entry has an invalid kind or model")
    field = {"reserve": "max_nano", "settle": "actual_nano"}.get(kind)  # type: ignore[arg-type]
    if field is None:
        raise LedgerError(f"{where}: unknown entry type {kind!r}")
    amount = entry.get(field)
    if type(amount) is not int or amount < 0:
        raise LedgerError(f"{where}: {field} must be a non-negative integer")
    if kind == "settle" and entry.get("basis") not in BASES:
        raise LedgerError(f"{where}: settle entry has an invalid basis")
    return entry


class Ledger:
    """One ledger file and its limit. Stateless: every method re-reads the file."""

    def __init__(self, path: Path, limit_nano: int) -> None:
        if type(limit_nano) is not int or limit_nano <= 0:
            raise ValueError(f"the budget must be a positive number of nano-USD, got {limit_nano!r}")
        self.path = path
        self.limit_nano = limit_nano

    # ---------------------------------------------------------------- reading

    def _read_locked(self) -> tuple[list[dict[str, Any]], bool]:
        """(valid entries, whether a torn final line was found and ignored).

        A final line without a newline that is not valid JSON is a torn write:
        - a torn reserve: the call never started (calls start only after the
          reserve's fsync returns), so ignoring it is exact;
        - a torn settle: its reservation stays open and counts at its maximum.
        Any other malformed line is corruption and raises.
        """
        try:
            data = self.path.read_bytes()
        except FileNotFoundError:
            return [], False
        except OSError as exc:
            raise LedgerError(f"{self.path.as_posix()}: cannot read the ledger ({exc})") from exc
        lines = data.split(b"\n")
        tail = lines.pop()  # b"" when the file ends with a newline
        entries: list[dict[str, Any]] = []
        for number, raw in enumerate(lines, start=1):
            where = f"{self.path.as_posix()}:{number}"
            try:
                obj = json.loads(raw.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                raise LedgerError(f"{where}: corrupt ledger line") from None
            entries.append(_check_entry(obj, where))
        torn = False
        if tail:
            where = f"{self.path.as_posix()}:{len(lines) + 1}"
            try:
                obj = json.loads(tail.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                torn = True
            else:  # a complete entry whose newline was not written: count it
                entries.append(_check_entry(obj, where))
        return entries, torn

    @staticmethod
    def _state(entries: list[dict[str, Any]], path: Path) -> LedgerState:
        reserved: dict[str, int] = {}
        settled: dict[str, int] = {}
        for e in entries:
            rid = e["id"]
            if e["type"] == "reserve":
                if rid in reserved:
                    raise LedgerError(f"{path.as_posix()}: reservation {rid} appears twice")
                reserved[rid] = e["max_nano"]
            else:
                if rid not in reserved:
                    raise LedgerError(f"{path.as_posix()}: settle {rid} has no earlier reservation")
                if rid in settled:
                    raise LedgerError(f"{path.as_posix()}: reservation {rid} is settled twice")
                settled[rid] = e["actual_nano"]
        open_max = sum(m for rid, m in reserved.items() if rid not in settled)
        return LedgerState(
            spent_nano=sum(settled.values()) + open_max,
            open_reservations=len(reserved) - len(settled),
            settled=len(settled),
        )

    def state(self) -> LedgerState:
        with _LOCK:
            entries, _ = self._read_locked()
            return self._state(entries, self.path)

    def spend(self) -> int:
        return self.state().spent_nano

    def remaining(self) -> int:
        return self.limit_nano - self.spend()

    # ---------------------------------------------------------------- writing

    def ensure_writable(self) -> None:
        """Create the directory and the file if needed (fsynced), and prove it opens for append."""
        with _LOCK:
            self._open_for_append_locked().close()

    def _open_for_append_locked(self) -> Any:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            created = not self.path.exists()
            fh = open(self.path, "ab")
        except OSError as exc:
            raise LedgerError(f"{self.path.as_posix()}: cannot open the ledger for writing ({exc})") from exc
        if created:
            try:
                fh.flush()
                os.fsync(fh.fileno())
                _fsync_dir(self.path.parent)
            except OSError as exc:
                fh.close()
                raise LedgerError(f"{self.path.as_posix()}: cannot fsync the new ledger ({exc})") from exc
        return fh

    def _append_locked(self, entry: dict[str, Any]) -> None:
        line = (json.dumps(entry, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")
        fh = self._open_for_append_locked()
        try:
            size = fh.seek(0, os.SEEK_END)
            if size:
                with open(self.path, "rb") as rf:
                    rf.seek(size - 1)
                    last = rf.read(1)
                if last != b"\n":
                    _, torn = self._read_locked()
                    if torn:  # drop the torn tail so the next line starts clean
                        data = self.path.read_bytes()
                        fh.truncate(data.rfind(b"\n") + 1)
                    else:  # a complete final entry without its newline
                        fh.write(b"\n")
            fh.write(line)
            fh.flush()
            os.fsync(fh.fileno())
        except OSError as exc:
            raise LedgerError(f"{self.path.as_posix()}: cannot append to the ledger ({exc})") from exc
        finally:
            fh.close()

    def reserve(self, kind: Kind, model: str, max_nano: int) -> str:
        """Append a reservation if spend + max_nano <= the budget; else BudgetExceeded."""
        if kind not in KINDS:
            raise ValueError(f"unknown call kind {kind!r}")
        if type(max_nano) is not int or max_nano < 0:
            raise ValueError(f"max_nano must be a non-negative integer, got {max_nano!r}")
        with _LOCK:
            entries, _ = self._read_locked()
            spent = self._state(entries, self.path).spent_nano
            if spent + max_nano > self.limit_nano:
                raise BudgetExceeded(
                    f"budget reached: spend so far {budget.fmt_usd(spent)} plus this "
                    f"{model} {kind} call's maximum {budget.fmt_usd(max_nano)} would exceed "
                    f"the budget of {budget.fmt_usd(self.limit_nano)}; no request was made"
                )
            rid = uuid.uuid4().hex
            self._append_locked(
                {
                    "type": "reserve",
                    "id": rid,
                    "at": _now(),
                    "kind": kind,
                    "model": model,
                    "max_nano": max_nano,
                    "spend_before_nano": spent,
                    "budget_nano": self.limit_nano,
                }
            )
            return rid

    def settle(
        self, rid: str, kind: Kind, model: str, actual_nano: int, basis: Basis,
        error: str | None = None,
    ) -> None:
        if type(actual_nano) is not int or actual_nano < 0:
            raise ValueError(f"actual_nano must be a non-negative integer, got {actual_nano!r}")
        if basis not in BASES:
            raise ValueError(f"unknown settle basis {basis!r}")
        entry: dict[str, Any] = {
            "type": "settle",
            "id": rid,
            "at": _now(),
            "kind": kind,
            "model": model,
            "actual_nano": actual_nano,
            "basis": basis,
        }
        if error is not None:
            entry["error"] = error
        with _LOCK:
            self._append_locked(entry)


def _fsync_dir(directory: Path) -> None:
    """fsync a directory so a new file's entry survives a crash. POSIX only: Windows
    can't open a directory for fsync (the container target is Linux)."""
    if os.name != "posix":
        return
    fd = os.open(directory, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


# ------------------------------------------------------------ actual cost from usage


def openai_actual_cost(response: Any, model: str) -> int | None:
    """Actual cost from the response usage, the scorer's own path; None if missing."""
    dump = response.model_dump(mode="json")
    usage = openai_responses.normalize_usage(dump.get("usage") if isinstance(dump, dict) else None)
    return budget.usage_cost(usage, prices_for(model))


def gemini_actual_cost(response: Any, model: str) -> int | None:
    """Input = prompt_token_count; output = candidates_token_count + thoughts_token_count
    (thoughts None -> 0). None when the input or candidates count is missing."""
    dump = response.model_dump(mode="json")
    usage = dump.get("usage_metadata") if isinstance(dump, dict) else None
    if not isinstance(usage, dict):
        return None
    tokens_in = usage.get("prompt_token_count")
    tokens_out = usage.get("candidates_token_count")
    thoughts = usage.get("thoughts_token_count")
    if thoughts is None:
        thoughts = 0
    if type(tokens_in) is not int or type(tokens_out) is not int or type(thoughts) is not int:
        return None
    price_in, price_out = prices_for(model)
    return tokens_in * price_in + (tokens_out + thoughts) * price_out


def _guarded_call(
    ledger: Ledger,
    kind: Kind,
    model: str,
    max_nano: int,
    call: Callable[[], Any],
    actual: Callable[[Any], int | None],
) -> Any:
    """Reserve under the lock, call outside it, then settle.

    - Reservation refused: BudgetExceeded before any request.
    - The call raised (any BaseException): settle at the maximum, then re-raise.
    - Usage missing: settle at the maximum. Reading usage raised: settle at the
      maximum, then re-raise.
    - A kill between reserve and settle leaves the reservation open (its maximum).
    """
    rid = ledger.reserve(kind, model, max_nano)
    try:
        response = call()
    except BaseException as exc:
        ledger.settle(rid, kind, model, max_nano, "maximum_raised", type(exc).__name__)
        raise
    try:
        cost = actual(response)
    except Exception as exc:
        ledger.settle(rid, kind, model, max_nano, "maximum_no_usage", type(exc).__name__)
        raise
    if cost is None:
        ledger.settle(rid, kind, model, max_nano, "maximum_no_usage")
    else:
        ledger.settle(rid, kind, model, cost, "usage")
    return response


class GuardedOpenAI:
    """An OpenAI client whose `responses.create` goes through the ledger.

    Used for generation (kind "generation") and the judge (kind "judge"). The inner
    client must make exactly one HTTP request per call: max_retries must be 0.
    """

    def __init__(self, inner: Any, ledger: Ledger, kind: Kind) -> None:
        if getattr(inner, "max_retries", None) != 0:
            raise ValueError(
                "a guarded OpenAI client must be built with max_retries=0: SDK retries "
                "would be billed outside the spending guard"
            )
        if kind not in KINDS:
            raise ValueError(f"unknown call kind {kind!r}")
        self._inner = inner
        self._ledger = ledger
        self._kind: Kind = kind
        # openai_responses.client_settings reads these for the manifest.
        self.max_retries = inner.max_retries
        self.timeout = inner.timeout
        self.responses = SimpleNamespace(create=self._create)

    def _create(self, **request: Any) -> Any:
        model = request.get("model")
        max_nano = max_call_cost(request, model, request.get("max_output_tokens"))  # type: ignore[arg-type]
        return _guarded_call(
            self._ledger, self._kind, model, max_nano,  # type: ignore[arg-type]
            lambda: self._inner.responses.create(**request),
            lambda r: openai_actual_cost(r, model),  # type: ignore[arg-type]
        )


class GuardedGemini:
    """A google-genai client whose `models.generate_content` goes through the ledger.

    The inner client must be built with gemini.NO_RETRY_OPTIONS (checked where it is
    built: the wrapper can't see the SDK's retry settings). Automatic continuation
    must be off in the request: each continuation hop is a separate billed request.
    """

    def __init__(self, inner: Any, ledger: Ledger) -> None:
        self._inner = inner
        self._ledger = ledger
        self.models = SimpleNamespace(generate_content=self._generate)

    def _generate(self, *, model: str, contents: Any, config: Any) -> Any:
        cfg = config.model_dump(mode="json", exclude_none=True) if hasattr(config, "model_dump") else dict(config)
        if cfg.get("automatic_continuation") is not False:
            raise BudgetExceeded(
                f"a {model} request leaves automatic continuation on, so its cost has no "
                "bound; no request was made"
            )
        request = {"model": model, "contents": contents, "config": cfg}
        max_nano = max_call_cost(request, model, cfg.get("max_output_tokens"))
        return _guarded_call(
            self._ledger, "generation", model, max_nano,
            lambda: self._inner.models.generate_content(model=model, contents=contents, config=config),
            lambda r: gemini_actual_cost(r, model),
        )


def guard_clients(
    generation: dict[str, Any], judge: Any, ledger: Ledger
) -> tuple[dict[str, Any], GuardedOpenAI]:
    """Wrap every paid client: generation clients by provider, and the judge."""
    out: dict[str, Any] = {}
    for provider, inner in generation.items():
        if provider == openai_responses.PROVIDER:
            out[provider] = GuardedOpenAI(inner, ledger, "generation")
        elif provider == gemini.PROVIDER:
            out[provider] = GuardedGemini(inner, ledger)
        else:
            raise ValueError(f"no guard for provider {provider!r}")
    return out, GuardedOpenAI(judge, ledger, "judge")
