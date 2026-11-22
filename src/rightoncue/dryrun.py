"""Offline stand-ins for every provider client (RIGHTONCUE_DRY_RUN=1).

No network, no key. They answer like the real SDKs closely enough for the runner,
the scorer and the spending guard: canned replies marked as placeholders, valid
judge-v1 judgments, and realistic token usage so the guarded wrappers reserve and
settle nonzero amounts at the real prices (into a separate dry-run ledger). They
are wrapped by the same guards as the real clients.
"""

from __future__ import annotations

import itertools
import json
import time
from types import SimpleNamespace
from typing import Any

from google.genai import types

DRY_MODEL = "dry-run-placeholder"  # the reported model: marks every dry-run record
DRY_NOTE = "(Dry run placeholder: no model was called.)"
# Realistic usage, in tokens: (input, output).
OPENAI_GENERATION_USAGE = (850, 50)
GEMINI_GENERATION_USAGE = (850, 30)
JUDGE_USAGE = (1_700, 450)
_REPLIES = (
    "Thanks for walking me through that. What drew you to the Medical ICU role?",
    "That makes sense. Could you tell me a little about your most recent ICU unit?",
    "Got it, thank you. How many years have you worked as an ICU nurse?",
)
_RATIONALE = "Dry run placeholder: no model was called, so this score is not a judgment."


def placeholder_judgment() -> str:
    """A judge-v1 (scorer-1) judgment: every dimension 2, no violation, no evidence."""
    dim = {"rationale": _RATIONALE, "evidence": [], "score": 2}
    return json.dumps(
        {
            "next_action": dim,
            "listening_context": dim,
            "grounding_role": dim,
            "spoken_delivery": dim,
            "critical_violations": [],
        }
    )


class _OpenAIResponse:
    def __init__(self, text: str, usage: tuple[int, int], n: int) -> None:
        self.output_text = text
        self.status = "completed"
        self.model = DRY_MODEL
        self.id = f"dry_run_{n}"
        self._usage = usage

    def model_dump(self, mode: str = "python") -> dict[str, Any]:
        return {
            "id": self.id,
            "model": self.model,
            "status": self.status,
            "dry_run": True,
            "incomplete_details": None,
            "usage": {
                "input_tokens": self._usage[0],
                "output_tokens": self._usage[1],
                "output_tokens_details": {"reasoning_tokens": 0},
            },
        }


class DryRunOpenAI:
    """Answers generation requests with a canned reply and judge requests (they carry a
    json_schema text format) with a placeholder judgment."""

    max_retries = 0
    timeout = "dry-run"

    def __init__(self, delay_s: float = 0.0) -> None:
        self._delay_s = delay_s
        self._n = itertools.count(1)
        self.responses = SimpleNamespace(create=self._create)

    def _create(self, **request: Any) -> _OpenAIResponse:
        n = next(self._n)
        if self._delay_s:
            time.sleep(self._delay_s)
        if (request.get("text") or {}).get("format", {}).get("type") == "json_schema":
            return _OpenAIResponse(placeholder_judgment(), JUDGE_USAGE, n)
        reply = f"{DRY_NOTE} {_REPLIES[n % len(_REPLIES)]}"
        return _OpenAIResponse(reply, OPENAI_GENERATION_USAGE, n)


class DryRunGemini:
    """Answers generate_content with a real SDK response object holding a canned reply."""

    def __init__(self, delay_s: float = 0.0) -> None:
        self._delay_s = delay_s
        self._n = itertools.count(1)
        self.models = SimpleNamespace(generate_content=self._generate)

    def _generate(self, *, model: str, contents: Any, config: Any) -> types.GenerateContentResponse:
        n = next(self._n)
        if self._delay_s:
            time.sleep(self._delay_s)
        reply = f"{DRY_NOTE} {_REPLIES[(n + 1) % len(_REPLIES)]}"
        return types.GenerateContentResponse.model_validate(
            {
                "model_version": DRY_MODEL,
                "response_id": f"dry_run_gemini_{n}",
                "candidates": [
                    {"content": {"role": "model", "parts": [{"text": reply}]}, "finish_reason": "STOP", "index": 0}
                ],
                "usage_metadata": {
                    "prompt_token_count": GEMINI_GENERATION_USAGE[0],
                    "candidates_token_count": GEMINI_GENERATION_USAGE[1],
                    "total_token_count": sum(GEMINI_GENERATION_USAGE),
                },
            }
        )
