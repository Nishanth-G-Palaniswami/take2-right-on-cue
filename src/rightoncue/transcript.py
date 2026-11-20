"""Partial phone-screen transcript parsing (JSONL, one turn per line)."""

from __future__ import annotations

import json
from typing import Literal

from pydantic import BaseModel


class Turn(BaseModel):
    role: Literal["agent", "user"]
    utterance: str


class TranscriptError(ValueError):
    def __init__(self, line: int, reason: str) -> None:
        super().__init__(f"line {line}: {reason}")
        self.line = line
        self.reason = reason


def parse_transcript(text: str) -> list[Turn]:
    text = text.lstrip("﻿")
    turns: list[Turn] = []
    last_line = 1
    for number, raw in enumerate(text.split("\n"), start=1):
        if not raw.strip():
            continue
        last_line = number
        try:
            obj = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise TranscriptError(number, f"invalid JSON ({exc.msg})") from exc
        if not isinstance(obj, dict):
            raise TranscriptError(number, "line is not a JSON object")
        if set(obj) != {"role", "utterance"}:
            raise TranscriptError(
                number,
                f"keys must be exactly 'role' and 'utterance', got {sorted(obj)}",
            )
        role = obj["role"]
        if role not in ("agent", "user"):
            raise TranscriptError(number, f"unknown role {role!r}")
        utterance = obj["utterance"]
        if not isinstance(utterance, str):
            raise TranscriptError(number, "utterance is not a string")
        if not utterance.strip():
            raise TranscriptError(number, "utterance is empty")
        turns.append(Turn(role=role, utterance=utterance))
    if not turns:
        raise TranscriptError(1, "transcript has no turns")
    if turns[-1].role != "user":
        raise TranscriptError(last_line, "last turn must be from 'user'")
    return turns
