import re
from pathlib import Path

from rightoncue.transcript import parse_transcript

DEV = Path(__file__).resolve().parents[1] / "cases" / "dev"


def test_d3_d4_pairing() -> None:
    d3 = parse_transcript((DEV / "D3.jsonl").read_text(encoding="utf-8"))
    d4 = parse_transcript((DEV / "D4.jsonl").read_text(encoding="utf-8"))
    assert len(d3) == len(d4)
    assert d3[:-1] == d4[:-1]
    a, b = d3[-1].utterance, d4[-1].utterance
    assert b.startswith(a)
    rest = b[len(a):].strip()
    assert rest and rest[-1] in ".!?"
    assert not re.search(r"[.!?]\s+[A-Z]", rest)
