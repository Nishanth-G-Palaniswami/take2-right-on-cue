"""OpenAI Responses API request building and calling.

The generation path sees only the prompt text and the transcript.
"""

from __future__ import annotations

from typing import Any

from .transcript import Turn

_ROLE_MAP = {"agent": "assistant", "user": "user"}


def build_request(
    prompt_text: str, turns: list[Turn], model: str, reasoning_effort: str
) -> dict[str, Any]:
    return {
        "model": model,
        "instructions": prompt_text,
        "input": [
            {"role": _ROLE_MAP[t.role], "content": t.utterance} for t in turns
        ],
        "reasoning": {"effort": reasoning_effort},
    }


def generate(client: Any, request: dict[str, Any]) -> tuple[Any, dict[str, Any]]:
    """One independent call. Returns (response, response.model_dump(mode='json'))."""
    response = client.responses.create(**request)
    return response, response.model_dump(mode="json")
