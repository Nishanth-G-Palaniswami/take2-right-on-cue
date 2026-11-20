import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import httpx2
import openai
import pytest

from rightoncue.openai_responses import build_request
from rightoncue.runs import InputFile, create_run, read_slots, render_blind, run_slots
from rightoncue.transcript import Turn

CASE = b'{"role":"agent","utterance":"Hi"}\n{"role":"user","utterance":"Hello"}\n'


class FakeResponse:
    def __init__(self, text: str) -> None:
        self.output_text = text
        self.model = "gpt-returned-snapshot"
        self.usage = {"input_tokens": 5, "output_tokens": 3}
        self.status = "completed"
        self.incomplete_details: dict[str, Any] | None = None
        self.id = "resp_1"

    def model_dump(self, mode: str = "python") -> dict[str, Any]:
        return {
            "id": self.id,
            "model": self.model,
            "status": self.status,
            "usage": self.usage,
            "incomplete_details": self.incomplete_details,
            "output_text_hidden": self.output_text,
        }


class FakeClient:
    def __init__(self, outputs: list[Any]) -> None:
        self.outputs = list(outputs)
        self.calls: list[dict[str, Any]] = []
        self.responses = SimpleNamespace(create=self._create)
        self.max_retries = 2
        self.timeout = 60

    def _create(self, **kwargs: Any) -> FakeResponse:
        self.calls.append(kwargs)
        out = self.outputs.pop(0)
        if isinstance(out, Exception):
            raise out
        if isinstance(out, dict):  # {"text", "status", "details"}
            resp = FakeResponse(out["text"])
            resp.status = out["status"]
            resp.incomplete_details = out.get("details")
            return resp
        return FakeResponse(out)


def make(tmp_path: Path, samples: int = 2, cases: int = 2):
    files = [InputFile(f"cases/c{i}.jsonl", CASE) for i in range(cases)]
    return create_run(
        tmp_path, "RID", InputFile("prompts/v1.md", b"prompt"), files,
        "gpt-x", "none", samples, 2, "60",
    )


def http_error(cls: type, status: int) -> Exception:
    req = httpx2.Request("POST", "https://x")
    return cls("boom", response=httpx2.Response(status, request=req), body=None)


def test_build_request() -> None:
    req = build_request("P", [Turn(role="agent", utterance="a"), Turn(role="user", utterance="u")], "m", "none")
    assert set(req) == {"model", "instructions", "input", "reasoning"}
    assert req["input"] == [
        {"role": "assistant", "content": "a"},
        {"role": "user", "content": "u"},
    ]
    assert req["reasoning"] == {"effort": "none"}


def test_slots_count_identical_outputs_and_whitespace(tmp_path: Path) -> None:
    run_dir, manifest = make(tmp_path)
    assert (run_dir / "manifest.json").exists()
    client = FakeClient([" same \n"] * 4)
    run_slots(client, run_dir, manifest)
    slots = read_slots(run_dir)
    assert len(slots) == 4 and len(client.calls) == 4
    assert len({s["slot_key"] for s in slots}) == 4
    assert all(s["output_text"] == " same \n" for s in slots)
    assert [s["case_id"] for s in slots] == ["c0", "c0", "c1", "c1"]
    assert slots[0]["slot_key"] == "RID|c0|v1|gpt-x|1"


def test_resume_does_not_duplicate(tmp_path: Path) -> None:
    run_dir, manifest = make(tmp_path)
    client = FakeClient(["a"] * 4)
    run_slots(client, run_dir, manifest)
    again = run_slots(client, run_dir, manifest)
    assert again.attempted == 0 and again.skipped == 4
    assert len(read_slots(run_dir)) == 4 and len(client.calls) == 4


def test_recoverable_continues_fatal_aborts(tmp_path: Path) -> None:
    run_dir, manifest = make(tmp_path)
    client = FakeClient([http_error(openai.RateLimitError, 429), "ok", "ok", "ok"])
    res = run_slots(client, run_dir, manifest)
    assert res.failed == 1 and res.abort_message is None
    assert read_slots(run_dir)[0]["error"]["status_code"] == 429

    run_dir2, manifest2 = make(tmp_path / "b")
    client2 = FakeClient([http_error(openai.AuthenticationError, 401)])
    res2 = run_slots(client2, run_dir2, manifest2)
    assert res2.abort_message and len(read_slots(run_dir2)) == 1


def test_show_blind_and_stable(tmp_path: Path) -> None:
    # Changed: an empty reply is no longer shown as an option, and a second
    # render says the sheet was preserved instead of returning an identical text.
    run_dir, manifest = make(tmp_path, cases=1)
    run_slots(FakeClient(["first", "second"]), run_dir, manifest)
    one = render_blind(run_dir)
    two = render_blind(run_dir)
    assert one.text.replace("Created blind_sheet.md.", "") == two.text.replace(
        "Existing blind_sheet.md preserved; not rewritten.", ""
    )
    for forbidden in ("gpt-x", "gpt-returned", "RID", "resp_1", "sample", "|"):
        assert forbidden not in one.text
    assert "REPLY A" in one.text and "REPLY B" in one.text
    assert "first" in one.text and "Hello" in one.text
    assert "Accept A? (y/n):" in (run_dir / "blind_sheet.md").read_text(encoding="utf-8")
    assert json.loads((run_dir / "blind_key.json").read_text())["c0"]


def test_show_reports_failures(tmp_path: Path) -> None:
    run_dir, manifest = make(tmp_path, cases=1)
    run_slots(FakeClient([http_error(openai.RateLimitError, 429), "x"]), run_dir, manifest)
    # Changed wording: "replies", not "samples".
    assert "1 of 2 replies failed to generate" in render_blind(run_dir).text
