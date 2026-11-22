"""Google Gemini (google-genai SDK) request building, calling and response mapping.

The generation path sees only the prompt text and the transcript.
"""

from __future__ import annotations

from typing import Any, Literal

import httpx2
from google import genai
from google.genai import errors, types

from .transcript import Turn

PROVIDER = "gemini"
API_KEY_ENV = "GEMINI_API_KEY"

_ROLE_MAP = {"agent": "model", "user": "user"}

THINKING_LEVELS = [
    level.value
    for level in types.ThinkingLevel
    if level is not types.ThinkingLevel.THINKING_LEVEL_UNSPECIFIED
]

# SDK retry settings. `attempts` counts the first call too (3 = up to 2 retries,
# like the OpenAI client's max_retries=2). The SDK also retries its own transient
# transport errors (httpx2 TimeoutException and ConnectError) under these settings.
RETRY_OPTIONS: dict[str, Any] = {
    "attempts": 3,
    "initial_delay": 1.0,
    "max_delay": 60.0,
    "exp_base": 2.0,
    "jitter": 1.0,
    "http_status_codes": [429, 500, 502, 503, 504],
}
# For capped (budgeted) runs: exactly one attempt inside the SDK, so every billable
# request passes the spending guard. attempts must be explicit: the SDK turns
# attempts=None into its default of 5 (google.genai._api_client.retry_args).
NO_RETRY_OPTIONS: dict[str, Any] = {"attempts": 1}
# The SDK sets no timeout unless one is given; a stuck call would hang forever.
TIMEOUT_MS = 600_000

PARAMS_NOTE = (
    "Only model, contents, config.system_instruction and "
    "config.thinking_config.thinking_level are sent. Every other generation "
    "parameter (temperature, max_output_tokens, safety settings, ...) is left to "
    "the API defaults. The SDK's automatic continuation is left at its default "
    "(enabled), so one generate_content call can span several HTTP requests if the "
    "API answers with finish reason CONTINUATION."
)

PARAMS_NOTE_CAPPED = (
    "Only model, contents, config.system_instruction, "
    "config.thinking_config.thinking_level, config.max_output_tokens and "
    "config.automatic_continuation (false, applied by the SDK, not sent) are set. "
    "max_output_tokens caps the generated output (Google's thinking guide says "
    "thinking can exhaust it); a reply that reaches it ends with finish reason "
    "MAX_TOKENS. With automatic continuation off, one generate_content call is one "
    "HTTP request. Every other generation parameter is left to the API defaults."
)

FATAL_CODES = frozenset({400, 401, 403, 404})


def build_request(
    prompt_text: str,
    turns: list[Turn],
    model: str,
    thinking_level: str,
    max_output_tokens: int | None = None,
) -> dict[str, Any]:
    """The generate_content request. Without a cap it is exactly as before.

    With a cap, automatic continuation is turned off as well: each continuation
    hop is a separately billed request that the cap would not cover.
    """
    config: dict[str, Any] = {
        "system_instruction": prompt_text,
        "thinking_config": {"thinking_level": thinking_level},
    }
    if max_output_tokens is not None:
        config["max_output_tokens"] = max_output_tokens
        config["automatic_continuation"] = False
    return {
        "model": model,
        "contents": [
            {"role": _ROLE_MAP[t.role], "parts": [{"text": t.utterance}]} for t in turns
        ],
        "config": config,
    }


def client_settings(retry_options: dict[str, Any] | None = None) -> dict[str, Any]:
    """What the client is configured with, for the manifest (never the key)."""
    return {
        "api_key_env": API_KEY_ENV,
        "vertexai": False,
        "retry_options": dict(RETRY_OPTIONS if retry_options is None else retry_options),
        "timeout_ms": TIMEOUT_MS,
    }


def make_client(api_key: str, retry_options: dict[str, Any] | None = None) -> Any:
    options = RETRY_OPTIONS if retry_options is None else retry_options
    return genai.Client(
        api_key=api_key,
        vertexai=False,
        http_options=types.HttpOptions(
            timeout=TIMEOUT_MS,
            retry_options=types.HttpRetryOptions(**options),
        ),
    )


def generate(client: Any, request: dict[str, Any]) -> tuple[Any, dict[str, Any]]:
    """One generate_content call. Returns (response, response.model_dump(mode='json'))."""
    response = client.models.generate_content(
        model=request["model"],
        contents=request["contents"],
        config=types.GenerateContentConfig.model_validate(request["config"]),
    )
    return response, response.model_dump(mode="json")


def classify_error(exc: BaseException) -> Literal["fatal", "recoverable"] | None:
    """fatal: abort the run; recoverable: record and continue; None: propagate."""
    if isinstance(exc, errors.ClientError):
        if exc.code in FATAL_CODES:
            return "fatal"
        if exc.code == 429:
            return "recoverable"
        return None
    if isinstance(exc, errors.ServerError):
        return "recoverable"
    # The SDK sends through httpx2 and re-raises transport errors unwrapped
    # (connect, read, write, timeout, protocol).
    if isinstance(exc, httpx2.TransportError):
        return "recoverable"
    return None


def error_status_code(exc: BaseException) -> int | None:
    return exc.code if isinstance(exc, errors.APIError) else None


def normalize_usage(usage: dict[str, Any] | None) -> dict[str, Any] | None:
    if usage is None:
        return None
    return {
        "input_tokens": usage.get("prompt_token_count"),
        "output_tokens": usage.get("candidates_token_count"),
        "reasoning_tokens": usage.get("thoughts_token_count"),
    }


def slot_fields(response: Any, dump: dict[str, Any]) -> dict[str, Any]:
    """Map a returned response to slot record fields (status, text, model, ...)."""
    text = response.text
    candidates = response.candidates or []
    finish = candidates[0].finish_reason if candidates else None
    finish_value: str | None = finish.value if finish is not None else None
    error: dict[str, Any] | None = None
    incomplete: dict[str, Any] | None = None
    if not candidates:
        status = "generation_failed"
        feedback = response.prompt_feedback
        block = feedback.block_reason if feedback is not None else None
        error = {
            "type": "blocked",
            "message": "no candidates returned"
            + (f" (block reason {block.value!r})" if block is not None else ""),
            "status_code": None,
        }
    elif finish_value == types.FinishReason.STOP.value:
        status = "ok"
    elif finish_value == types.FinishReason.MAX_TOKENS.value:
        status = "incomplete"
        incomplete = {"reason": finish_value}
    else:
        status = "generation_failed"
        error = {
            "type": "finish_reason",
            "message": f"finish reason {finish_value!r}",
            "status_code": None,
        }
    reported = response.model_version or None
    usage = dump.get("usage_metadata")
    fields: dict[str, Any] = {
        "status": status,
        "output_text": text if text is not None else "",
        "returned_model": reported,
        "reported_model_note": None if reported else "served version unconfirmed",
        "response_id": response.response_id,
        "response_status": finish_value,
        "incomplete_details": incomplete,
        "usage": usage,
        "usage_normalized": normalize_usage(usage),
        "raw_response": dump,
    }
    if error is not None:
        fields["error"] = error
    return fields
