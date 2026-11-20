import json

import pytest

from rightoncue.transcript import TranscriptError, parse_transcript


def line(role: str, text: str) -> str:
    return json.dumps({"role": role, "utterance": text})


GOOD = line("agent", "Hi there") + "\n" + line("user", "Hello")


def err(text: str) -> TranscriptError:
    with pytest.raises(TranscriptError) as info:
        parse_transcript(text)
    return info.value


def test_valid_and_verbatim() -> None:
    turns = parse_transcript("﻿" + line("agent", " Hi ") + "\n\n" + line("user", " yo \n"))
    assert [t.utterance for t in turns] == [" Hi ", " yo \n"]


def test_consecutive_agent_turns_accepted() -> None:
    text = "\n".join([line("agent", "a"), line("agent", "b"), line("user", "c")])
    assert len(parse_transcript(text)) == 3


@pytest.mark.parametrize(
    "bad,lineno",
    [
        ("{nope", 2),
        ("[1]", 2),
        ('{"role":"user"}', 2),
        ('{"role":"user","utterance":"x","extra":1}', 2),
        ('{"role":"bot","utterance":"x"}', 2),
        ('{"role":"user","utterance":5}', 2),
        ('{"role":"user","utterance":"  "}', 2),
    ],
)
def test_line_errors_report_line_number(bad: str, lineno: int) -> None:
    e = err(line("agent", "a") + "\n\n" + bad + "\n" + line("user", "b"))
    assert e.line == lineno + 1  # blank line counted
    assert f"line {e.line}" in str(e)


def test_no_turns() -> None:
    assert "no turns" in str(err("\n\n"))


def test_last_turn_must_be_user() -> None:
    e = err(GOOD + "\n" + line("agent", "z"))
    assert e.line == 3
