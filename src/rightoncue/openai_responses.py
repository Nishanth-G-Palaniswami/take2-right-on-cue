"""OpenAI Responses API request building, calling and response mapping.

The generation path sees only the prompt text and the transcript.
"""

from __future__ import annotations

from typing import Any, Literal

import openai

from .transcript import Turn

PROVIDER = "openai"
API_KEY_ENV = "OPENAI_API_KEY"

_ROLE_MAP = {"agent": "assistant", "user": "user"}

FATAL_ERRORS = (
    openai.AuthenticationError,
    openai.PermissionDeniedError,
    openai.BadRequestError,
    openai.NotFoundError,
)
RECOVERABLE_ERRORS = (
    openai.RateLimitError,
    openai.APIConnectionError,  # parent of APITimeoutError
    openai.InternalServerError,
)

PARAMS_NOTE = (
    "Only model, instructions, input and reasoning.effort are sent. Every other "
    "generation parameter (temperature, max_output_tokens, store, ...) is left to "
    "the API defaults."
)


PARAMS_NOTE_CAPPED = (
    "Only model, instructions, input, reasoning.effort and max_output_tokens are "
    "sent. max_output_tokens caps the reply including reasoning tokens; a reply "
    "that reaches it comes back with status incomplete. Every other generation "
    "parameter (temperature, store, ...) is left to the API defaults."
)


def build_request(
    prompt_text: str,
    turns: list[Turn],
    model: str,
    reasoning_effort: str,
    max_output_tokens: int | None = None,
) -> dict[str, Any]:
    """The Responses API request. Without a cap it is exactly as before."""
    request: dict[str, Any] = {
        "model": model,
        "instructions": prompt_text,
        "input": [
            {"role": _ROLE_MAP[t.role], "content": t.utterance} for t in turns
        ],
        "reasoning": {"effort": reasoning_effort},
    }
    if max_output_tokens is not None:
        request["max_output_tokens"] = max_output_tokens
    return request


def client_settings(client: Any) -> dict[str, Any]:
    return {"max_retries": client.max_retries, "timeout": str(client.timeout)}


def generate(client: Any, request: dict[str, Any]) -> tuple[Any, dict[str, Any]]:
    """One independent call. Returns (response, response.model_dump(mode='json'))."""
    response = client.responses.create(**request)
    return response, response.model_dump(mode="json")


def classify_error(exc: BaseException) -> Literal["fatal", "recoverable"] | None:
    """fatal: abort the run; recoverable: record and continue; None: propagate."""
    if isinstance(exc, FATAL_ERRORS):
        return "fatal"
    if isinstance(exc, RECOVERABLE_ERRORS):
        return "recoverable"
    return None


def error_status_code(exc: BaseException) -> int | None:
    return getattr(exc, "status_code", None)


def normalize_usage(usage: dict[str, Any] | None) -> dict[str, Any] | None:
    if usage is None:
        return None
    return {
        "input_tokens": usage.get("input_tokens"),
        "output_tokens": usage.get("output_tokens"),
        "reasoning_tokens": (usage.get("output_tokens_details") or {}).get(
            "reasoning_tokens"
        ),
    }


def slot_fields(response: Any, dump: dict[str, Any]) -> dict[str, Any]:
    """Map a returned response to slot record fields (status, text, model, ...)."""
    if response.status == "completed":
        status = "ok"
    elif response.status == "incomplete":
        status = "incomplete"
    else:
        status = "generation_failed"
    usage = dump.get("usage")
    reported = response.model or None
    fields: dict[str, Any] = {
        "status": status,
        "output_text": response.output_text,
        "returned_model": reported,
        "reported_model_note": None if reported else "served version unconfirmed",
        "response_id": response.id,
        "response_status": response.status,
        "incomplete_details": dump.get("incomplete_details"),
        "usage": usage,
        "usage_normalized": normalize_usage(usage),
        "raw_response": dump,
    }
    if status == "generation_failed":
        fields["error"] = {
            "type": "response_status",
            "message": f"response status {response.status!r}",
            "status_code": None,
        }
    return fields
