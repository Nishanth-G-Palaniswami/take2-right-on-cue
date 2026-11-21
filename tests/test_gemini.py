"""Gemini adapter and multi-model runs. Offline: fake clients and stubs only."""

import json
import shutil
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import httpx2
import openai
import pytest
from google import genai
from google.genai import errors, types
from test_run import CASE, FakeClient, http_error, openai_spec

from rightoncue import cli, gemini
from rightoncue.runs import (
    BlindKeyError,
    InputFile,
    ModelSpec,
    RunNotReadyError,
    create_run,
    manifest_models,
    read_slots,
    render_blind,
    run_slots,
)
from rightoncue.transcript import Turn

RUNS = Path(__file__).parent.parent / "runs"
GPT = "gpt-5.4-mini"
GEM = "gemini-3.5-flash"
MODEL_WORDS = ("gpt-", "gemini", "flash", "openai", "google")


def gresp(
    text: str | None = "reply",
    finish: str | None = "STOP",
    model_version: str | None = "gemini-3.6-flash",
    candidates: bool = True,
    block: str | None = None,
) -> types.GenerateContentResponse:
    """A real SDK response object, so .text and model_dump are the SDK's own."""
    data: dict[str, Any] = {
        "model_version": model_version,
        "response_id": "gem_1",
        "usage_metadata": {
            "prompt_token_count": 11,
            "candidates_token_count": 4,
            "thoughts_token_count": 6,
            "total_token_count": 21,
        },
    }
    if candidates:
        content = (
            {"role": "model", "parts": [{"text": text}]} if text is not None else None
        )
        data["candidates"] = [{"content": content, "finish_reason": finish, "index": 0}]
    if block is not None:
        data["prompt_feedback"] = {"block_reason": block}
    return types.GenerateContentResponse.model_validate(data)


class FakeGeminiClient:
    def __init__(self, outputs: list[Any]) -> None:
        self.outputs = list(outputs)
        self.calls: list[dict[str, Any]] = []
        self.models = SimpleNamespace(generate_content=self._generate)

    def _generate(self, *, model: str, contents: Any, config: Any) -> Any:
        self.calls.append({"model": model, "contents": contents, "config": config})
        out = self.outputs.pop(0)
        if isinstance(out, BaseException):
            raise out
        if isinstance(out, str):
            return gresp(out)
        return out


def gemini_spec(model: str = GEM, level: str = "MINIMAL") -> ModelSpec:
    return ModelSpec(model, "gemini", {"thinking_level": level}, gemini.client_settings())


def client_error(code: int) -> errors.APIError:
    body = {"error": {"code": code, "message": "boom", "status": "X"}}
    return (errors.ClientError if code < 500 else errors.ServerError)(code, body)


def make_gemini(tmp_path: Path, samples: int = 2, cases: int = 1):
    files = [InputFile(f"cases/c{i}.jsonl", CASE) for i in range(cases)]
    return create_run(
        tmp_path, "RID", InputFile("prompts/v1.md", b"prompt"), files,
        [gemini_spec()], samples,
    )


def make_multi(tmp_path: Path, samples: int = 2, case_ids: tuple[str, ...] = ("c0", "c1")):
    files = [InputFile(f"cases/{c}.jsonl", CASE) for c in case_ids]
    return create_run(
        tmp_path, "RID", InputFile("prompts/v1.md", b"prompt"), files,
        [openai_spec(GPT), gemini_spec(GEM)], samples,
    )


def snapshot(run_dir: Path) -> dict[str, bytes]:
    return {p.name: p.read_bytes() for p in sorted(run_dir.iterdir())}


def assert_no_model_words(text: str) -> None:
    low = text.lower()
    for word in MODEL_WORDS:
        assert word not in low, word


# ------------------------------------------------------------ request building


def test_gemini_build_request() -> None:
    turns = [
        Turn(role="agent", utterance="a1"),
        Turn(role="user", utterance="u1"),
        Turn(role="user", utterance="u2"),
    ]
    req = gemini.build_request("PROMPT", turns, GEM, "LOW")
    assert set(req) == {"model", "contents", "config"}
    assert req["model"] == GEM
    assert req["contents"] == [
        {"role": "model", "parts": [{"text": "a1"}]},
        {"role": "user", "parts": [{"text": "u1"}]},
        {"role": "user", "parts": [{"text": "u2"}]},
    ]
    assert req["config"] == {
        "system_instruction": "PROMPT",
        "thinking_config": {"thinking_level": "LOW"},
    }
    json.dumps(req)  # stored in the manifest
    # The SDK's own models accept exactly this shape (extra keys are forbidden).
    config = types.GenerateContentConfig.model_validate(req["config"])
    assert config.thinking_config.thinking_level is types.ThinkingLevel.LOW
    for content in req["contents"]:
        types.Content.model_validate(content)


def test_thinking_levels_exclude_unspecified() -> None:
    assert gemini.THINKING_LEVELS == ["MINIMAL", "LOW", "MEDIUM", "HIGH", "XHIGH"]


def test_generate_makes_one_call() -> None:
    req = gemini.build_request("P", [Turn(role="user", utterance="u")], GEM, "HIGH")
    client = FakeGeminiClient(["hello"])
    response, dump = gemini.generate(client, req)
    assert len(client.calls) == 1
    call = client.calls[0]
    assert call["model"] == GEM and call["contents"] == req["contents"]
    assert isinstance(call["config"], types.GenerateContentConfig)
    assert call["config"].system_instruction == "P"
    assert dump == response.model_dump(mode="json")


def test_make_client_uses_gemini_key_only(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, Any] = {}

    def fake_client(**kwargs: Any) -> str:
        seen.update(kwargs)
        return "client"

    monkeypatch.setattr(genai, "Client", fake_client)
    assert gemini.make_client("k-123") == "client"
    assert seen["api_key"] == "k-123" and seen["vertexai"] is False
    options = seen["http_options"]
    assert options.timeout == gemini.TIMEOUT_MS
    assert options.retry_options.attempts == 3
    assert options.retry_options.http_status_codes == [429, 500, 502, 503, 504]
    assert gemini.client_settings()["retry_options"] == gemini.RETRY_OPTIONS
    assert "k-123" not in json.dumps(gemini.client_settings())


# ------------------------------------------------------------ slot mapping


def test_stop_is_ok_and_text_verbatim(tmp_path: Path) -> None:
    run_dir, manifest = make_gemini(tmp_path)
    result = run_slots({"gemini": FakeGeminiClient([" same \n", "two"])}, run_dir, manifest)
    assert result.attempted == 2 and result.failed == 0
    rec = read_slots(run_dir)[0]
    assert rec["status"] == "ok" and rec["output_text"] == " same \n"
    assert rec["provider"] == "gemini" and rec["requested_model"] == GEM
    assert rec["returned_model"] == "gemini-3.6-flash"
    assert rec["reported_model_note"] is None
    assert rec["response_status"] == "STOP" and rec["response_id"] == "gem_1"
    assert rec["usage"]["prompt_token_count"] == 11
    assert rec["usage_normalized"] == {
        "input_tokens": 11, "output_tokens": 4, "reasoning_tokens": 6
    }
    assert rec["raw_response"]["model_version"] == "gemini-3.6-flash"
    assert rec["slot_key"] == f"RID|c0|v1|{GEM}|1"


def test_max_tokens_is_incomplete(tmp_path: Path) -> None:
    run_dir, manifest = make_gemini(tmp_path)
    client = FakeGeminiClient(["ok", gresp("cut off", finish="MAX_TOKENS")])
    result = run_slots({"gemini": client}, run_dir, manifest)
    assert result.incomplete == 1 and result.failed == 0
    rec = read_slots(run_dir)[1]
    assert rec["status"] == "incomplete" and rec["output_text"] == "cut off"
    assert rec["incomplete_details"] == {"reason": "MAX_TOKENS"}
    assert "error" not in rec


@pytest.mark.parametrize("finish", ["SAFETY", "RECITATION", "CONTINUATION", None])
def test_other_finish_reason_is_failed_with_raw_kept(tmp_path: Path, finish: str | None) -> None:
    run_dir, manifest = make_gemini(tmp_path)
    client = FakeGeminiClient(["ok", gresp("partial", finish=finish)])
    result = run_slots({"gemini": client}, run_dir, manifest)
    assert result.failed == 1 and result.abort_message is None
    rec = read_slots(run_dir)[1]
    assert rec["status"] == "generation_failed"
    assert rec["error"] == {
        "type": "finish_reason", "message": f"finish reason {finish!r}", "status_code": None
    }
    assert rec["output_text"] == "partial" and rec["raw_response"] is not None
    assert rec["usage_normalized"]["input_tokens"] == 11
    assert rec["returned_model"] == "gemini-3.6-flash"


def test_no_candidates_is_blocked(tmp_path: Path) -> None:
    run_dir, manifest = make_gemini(tmp_path)
    blocked = gresp(candidates=False, block="SAFETY")
    result = run_slots({"gemini": FakeGeminiClient(["ok", blocked])}, run_dir, manifest)
    assert result.failed == 1
    rec = read_slots(run_dir)[1]
    assert rec["status"] == "generation_failed" and rec["output_text"] == ""
    assert rec["error"]["type"] == "blocked" and rec["error"]["status_code"] is None
    assert "SAFETY" in rec["error"]["message"]
    assert rec["raw_response"]["prompt_feedback"]["block_reason"] == "SAFETY"
    assert rec["response_status"] is None and rec["usage"] is not None


@pytest.mark.parametrize("version", [None, ""])
def test_missing_model_version_is_unconfirmed(tmp_path: Path, version: str | None) -> None:
    run_dir, manifest = make_gemini(tmp_path)
    client = FakeGeminiClient([gresp("a", model_version=version), "b"])
    run_slots({"gemini": client}, run_dir, manifest)
    rec = read_slots(run_dir)[0]
    assert rec["returned_model"] is None
    assert rec["reported_model_note"] == "served version unconfirmed"


def test_text_none_becomes_empty_string(tmp_path: Path) -> None:
    run_dir, manifest = make_gemini(tmp_path)
    result = run_slots({"gemini": FakeGeminiClient([gresp(None), "b"])}, run_dir, manifest)
    rec = read_slots(run_dir)[0]
    assert rec["status"] == "ok" and rec["output_text"] == ""
    assert result.empty == 1


# ------------------------------------------------------------ error mapping


@pytest.mark.parametrize("code", [400, 401, 403, 404])
def test_client_error_aborts(tmp_path: Path, code: int) -> None:
    run_dir, manifest = make_gemini(tmp_path, cases=2)
    client = FakeGeminiClient([client_error(code), "never"])
    result = run_slots({"gemini": client}, run_dir, manifest)
    assert result.abort_message and GEM in result.abort_message
    assert len(read_slots(run_dir)) == 1 and len(client.calls) == 1
    rec = read_slots(run_dir)[0]
    assert rec["status"] == "generation_failed" and rec["raw_response"] is None
    assert rec["error"]["type"] == "ClientError" and rec["error"]["status_code"] == code


@pytest.mark.parametrize(
    "exc",
    [
        client_error(429),
        client_error(500),
        client_error(503),
        httpx2.ConnectError("refused"),
        httpx2.ReadTimeout("slow"),
        httpx2.ReadError("reset"),
    ],
    ids=["429", "500", "503", "connect", "timeout", "read"],
)
def test_recoverable_errors_continue(tmp_path: Path, exc: Exception) -> None:
    run_dir, manifest = make_gemini(tmp_path)
    client = FakeGeminiClient([exc, "fine"])
    result = run_slots({"gemini": client}, run_dir, manifest)
    assert result.failed == 1 and result.abort_message is None
    slots = read_slots(run_dir)
    assert [s["status"] for s in slots] == ["generation_failed", "ok"]
    expected_code = exc.code if isinstance(exc, errors.APIError) else None
    assert slots[0]["error"]["status_code"] == expected_code
    assert slots[0]["error"]["type"] == type(exc).__name__


@pytest.mark.parametrize("exc", [client_error(408), RuntimeError("unexpected")])
def test_other_errors_propagate(tmp_path: Path, exc: Exception) -> None:
    run_dir, manifest = make_gemini(tmp_path)
    with pytest.raises(type(exc)):
        run_slots({"gemini": FakeGeminiClient([exc])}, run_dir, manifest)
    assert read_slots(run_dir) == []


# ------------------------------------------------------------ multi-model runs


def test_multi_model_run_order_keys_manifest(tmp_path: Path) -> None:
    run_dir, manifest = make_multi(tmp_path)
    oa = FakeClient(["o1", "o2", "o3", "o4"])
    gm = FakeGeminiClient(["g1", "g2", "g3", "g4"])
    result = run_slots({"openai": oa, "gemini": gm}, run_dir, manifest)
    assert result.attempted == 8 and result.failed == 0
    slots = read_slots(run_dir)
    order = [(s["case_id"], s["requested_model"], s["sample_index"]) for s in slots]
    assert order == [
        (c, m, i) for c in ("c0", "c1") for m in (GPT, GEM) for i in (1, 2)
    ]
    assert len({s["slot_key"] for s in slots}) == 8
    assert slots[0]["slot_key"] == f"RID|c0|v1|{GPT}|1"
    assert slots[2]["slot_key"] == f"RID|c0|v1|{GEM}|1"
    assert [s["provider"] for s in slots[:4]] == ["openai"] * 2 + ["gemini"] * 2
    for model in (GPT, GEM):
        for case in ("c0", "c1"):
            assert sum(
                1 for s in slots if s["requested_model"] == model and s["case_id"] == case
            ) == 2
    assert len(oa.calls) == 4 and len(gm.calls) == 4

    on_disk = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    assert on_disk == manifest
    assert on_disk["schema_version"] == 2
    assert "model" not in on_disk and "reasoning_effort" not in on_disk
    assert on_disk["models"] == [
        {
            "model": GPT, "provider": "openai",
            "settings": {"reasoning_effort": "none"},
            "client": {"max_retries": 2, "timeout": "60"},
        },
        {
            "model": GEM, "provider": "gemini",
            "settings": {"thinking_level": "MINIMAL"},
            "client": gemini.client_settings(),
        },
    ]
    assert on_disk["google_genai_sdk_version"] == genai.__version__
    assert on_disk["openai_sdk_version"] == openai.__version__
    assert set(on_disk["generation_params_note"]) == {"openai", "gemini"}
    assert on_disk["samples_per_case"] == 2 and on_disk["prompt"]["text"] == "prompt"
    for case in on_disk["cases"]:
        assert set(case) == {"case_id", "path", "sha256", "raw_text", "turns", "requests"}
        assert set(case["requests"]) == {GPT, GEM}
        assert case["requests"][GPT]["reasoning"] == {"effort": "none"}
        assert case["requests"][GEM]["config"]["thinking_config"] == {
            "thinking_level": "MINIMAL"
        }
    # what was sent is exactly what the manifest says
    assert oa.calls[0] == on_disk["cases"][0]["requests"][GPT]
    assert gm.calls[0]["contents"] == on_disk["cases"][0]["requests"][GEM]["contents"]

    by_provider = {s["provider"]: s["usage_normalized"] for s in slots}
    assert by_provider["openai"] == {
        "input_tokens": 5, "output_tokens": 3, "reasoning_tokens": None
    }
    assert by_provider["gemini"] == {
        "input_tokens": 11, "output_tokens": 4, "reasoning_tokens": 6
    }


def test_openai_usage_normalized_reasoning() -> None:
    from rightoncue.openai_responses import normalize_usage

    usage = {"input_tokens": 7, "output_tokens": 9, "output_tokens_details": {"reasoning_tokens": 2}}
    assert normalize_usage(usage) == {"input_tokens": 7, "output_tokens": 9, "reasoning_tokens": 2}
    assert normalize_usage(None) is None


def test_fatal_on_one_model_aborts_whole_run(tmp_path: Path) -> None:
    run_dir, manifest = make_multi(tmp_path)
    oa = FakeClient(["o1", "o2", "o3", "o4"])
    gm = FakeGeminiClient([client_error(403)])
    result = run_slots({"openai": oa, "gemini": gm}, run_dir, manifest)
    assert result.abort_message and GEM in result.abort_message
    assert result.attempted == 3 and len(oa.calls) == 2  # c1 never started


def test_create_run_rejects_bad_models(tmp_path: Path) -> None:
    files = [InputFile("cases/c0.jsonl", CASE)]
    prompt = InputFile("prompts/v1.md", b"p")
    with pytest.raises(ValueError, match="duplicate"):
        create_run(tmp_path, "R1", prompt, files, [openai_spec(GPT), openai_spec(GPT)], 1)
    with pytest.raises(ValueError, match="unknown model"):
        create_run(tmp_path, "R2", prompt, files, [openai_spec("claude-x")], 1)
    assert not any(tmp_path.iterdir())


def test_missing_client_for_provider(tmp_path: Path) -> None:
    run_dir, manifest = make_multi(tmp_path)
    with pytest.raises(ValueError, match="gemini"):
        run_slots({"openai": FakeClient([])}, run_dir, manifest)
    assert read_slots(run_dir) == []


def test_unknown_schema_version_is_an_error() -> None:
    with pytest.raises(ValueError, match="schema_version"):
        manifest_models({"schema_version": 3})


# ------------------------------------------------------------ CLI


def write_inputs(tmp_path: Path) -> tuple[Path, Path]:
    tmp_path.mkdir(parents=True, exist_ok=True)
    prompt = tmp_path / "v1.md"
    prompt.write_text("prompt", encoding="utf-8")
    case = tmp_path / "D3.jsonl"
    case.write_bytes(CASE)
    return prompt, case


def no_network(monkeypatch: pytest.MonkeyPatch, dotenv: Any = None) -> None:
    def boom(*a: Any, **k: Any) -> Any:
        raise AssertionError("must not be called")

    monkeypatch.setattr(cli, "load_dotenv", dotenv or boom)
    monkeypatch.setattr(openai, "OpenAI", boom)
    monkeypatch.setattr(genai, "Client", boom)
    monkeypatch.setattr(gemini, "make_client", boom)


def base_args(tmp_path: Path, *extra: str) -> list[str]:
    prompt, case = write_inputs(tmp_path)
    return [
        "run", "--prompt", str(prompt), "--case", str(case),
        "--samples", "2", "--runs-dir", str(tmp_path / "runs"), *extra,
    ]


@pytest.mark.parametrize(
    "extra, message",
    [
        (["--model", GEM], "--gemini-thinking-level: required"),
        (["--model", GPT, "--model", GEM], "--gemini-thinking-level: required"),
        (["--model", "claude-3"], "unknown model 'claude-3'"),
        (["--model", GPT, "--model", GPT], "duplicate model"),
        (["--model", GPT, "--gemini-thinking-level", "low"], "only applies to Gemini"),
        (["--model", "gpt-5.4-mini "], "invalid model ID 'gpt-5.4-mini '"),
        (["--model", "gpt-"], "invalid model ID 'gpt-'"),
        (["--model", "gemini-", "--gemini-thinking-level", "low"], "invalid model ID 'gemini-'"),
        (["--model", "gemini-3.5 flash", "--gemini-thinking-level", "low"], "invalid model ID"),
        (["--model", "gpt-x/y"], "invalid model ID"),
        (
            [a for i in range(6) for a in ("--model", f"gpt-m{i}")] + ["--samples", "5"],
            "30 replies per case",
        ),
    ],
)
def test_cli_input_errors_exit_2_before_anything(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    extra: list[str],
    message: str,
) -> None:
    no_network(monkeypatch)
    assert cli.main(base_args(tmp_path, *extra)) == 2
    assert message in capsys.readouterr().err
    assert not (tmp_path / "runs").exists()


def test_cli_invalid_thinking_level_rejected(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    no_network(monkeypatch)
    with pytest.raises(SystemExit) as exc:
        cli.main(base_args(tmp_path, "--model", GEM, "--gemini-thinking-level", "thinking_level_unspecified"))
    assert exc.value.code == 2
    assert not (tmp_path / "runs").exists()


@pytest.mark.parametrize(
    "models, unset, expected",
    [
        ([GEM], ["GEMINI_API_KEY"], "GEMINI_API_KEY is not set"),
        ([GPT, GEM], ["GEMINI_API_KEY"], "GEMINI_API_KEY is not set"),
        ([GPT, GEM], ["OPENAI_API_KEY"], "OPENAI_API_KEY is not set"),
        ([GPT], ["OPENAI_API_KEY"], "OPENAI_API_KEY is not set"),
    ],
)
def test_cli_missing_key_exit_2_no_network(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    models: list[str],
    unset: list[str],
    expected: str,
) -> None:
    loaded: list[bool] = []
    no_network(monkeypatch, dotenv=lambda **k: loaded.append(True))  # never reads .env
    for env in ("OPENAI_API_KEY", "GEMINI_API_KEY"):
        monkeypatch.setenv(env, "dummy-not-a-key")
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    for env in unset:
        monkeypatch.delenv(env)
    extra = [a for m in models for a in ("--model", m)]
    if GEM in models:
        extra += ["--gemini-thinking-level", "minimal"]
    assert cli.main(base_args(tmp_path, *extra)) == 2
    err = capsys.readouterr().err
    assert expected in err and "No request was made." in err
    assert loaded == [True]
    assert not (tmp_path / "runs").exists()


def test_cli_gemini_only_needs_no_openai_key(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    built: list[str] = []
    no_network(monkeypatch, dotenv=lambda **k: None)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("GOOGLE_API_KEY", "other-key-must-not-be-used")
    monkeypatch.setenv("GEMINI_API_KEY", "dummy-gemini-key")

    def fake_make_client(api_key: str) -> FakeGeminiClient:
        built.append(api_key)
        return FakeGeminiClient(["a", "b"])

    monkeypatch.setattr(gemini, "make_client", fake_make_client)
    code = cli.main(base_args(tmp_path, "--model", GEM, "--gemini-thinking-level", "Minimal"))
    assert code == 0
    assert built == ["dummy-gemini-key"]
    out = capsys.readouterr().out
    assert "dummy-gemini-key" not in out
    run_dir = next((tmp_path / "runs").iterdir())
    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    assert [m["model"] for m in manifest["models"]] == [GEM]
    assert manifest["models"][0]["settings"] == {"thinking_level": "MINIMAL"}
    assert "dummy-gemini-key" not in (run_dir / "manifest.json").read_text(encoding="utf-8")


def test_cli_default_model_unchanged(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    no_network(monkeypatch)
    code = cli.main(base_args(tmp_path), client_factories={"openai": lambda: FakeClient(["a", "b"])})
    assert code == 0
    run_dir = next((tmp_path / "runs").iterdir())
    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    assert [m["model"] for m in manifest["models"]] == [GPT]


def run_cli_multi(tmp_path: Path, oa_out: list[Any], gm_out: list[Any]) -> int:
    args = base_args(
        tmp_path, "--model", GPT, "--model", GEM, "--gemini-thinking-level", "low"
    )
    return cli.main(
        args,
        client_factories={
            "openai": lambda: FakeClient(oa_out),
            "gemini": lambda: FakeGeminiClient(gm_out),
        },
    )


def test_cli_per_model_summary(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    no_network(monkeypatch)
    assert run_cli_multi(tmp_path, ["o1", "o2"], ["g1", gresp("g2", model_version=None)]) == 0
    out = capsys.readouterr().out
    assert f"Model {GPT} (openai):" in out and f"Model {GEM} (gemini):" in out
    gpt_block = out.split(f"Model {GPT} (openai):")[1].split("Model ")[0]
    gem_block = out.split(f"Model {GEM} (gemini):")[1]
    assert f"Requested model: {GPT}" in gpt_block
    assert "Reported model: gpt-returned-snapshot" in gpt_block
    assert "Summary: 2 of 2 slots attempted: 2 completed, 0 incomplete, 0 failed" in gpt_block
    assert "Tokens: input=10 output=6 reasoning=n/a" in gpt_block
    assert f"Requested model: {GEM}" in gem_block
    assert "Reported model: gemini-3.6-flash, served version unconfirmed" in gem_block
    assert "Summary: 2 of 2 slots attempted: 2 completed, 0 incomplete, 0 failed" in gem_block
    assert "Tokens: input=22 output=8 reasoning=12" in gem_block
    for reply in ("o1", "o2", "g1", "g2"):
        assert f": {reply}" not in out and f"\n{reply}\n" not in out
    progress = [line for line in out.splitlines() if line.startswith("  D3 ")]
    assert [line.split(":")[0] for line in progress] == [
        f"  D3 {GPT} sample 1", f"  D3 {GPT} sample 2",
        f"  D3 {GEM} sample 1", f"  D3 {GEM} sample 2",
    ]


def test_cli_exit_codes_one_model_bad(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    no_network(monkeypatch)
    assert run_cli_multi(tmp_path / "a", ["o1", "o2"], ["g1", gresp("cut", finish="MAX_TOKENS")]) == 1
    out = capsys.readouterr().out
    gem_block = out.split(f"Model {GEM} (gemini):")[1]
    assert "1 completed, 1 incomplete, 0 failed" in gem_block
    assert "(reason: MAX_TOKENS)" in out

    assert run_cli_multi(tmp_path / "b", ["o1", "o2"], ["g1", client_error(503)]) == 1
    gem_block = capsys.readouterr().out.split(f"Model {GEM} (gemini):")[1]
    assert "1 completed, 0 incomplete, 1 failed" in gem_block

    assert run_cli_multi(tmp_path / "c", ["o1", http_error(openai.RateLimitError, 429)], ["g1", "g2"]) == 1
    out = capsys.readouterr().out
    assert "1 completed, 0 incomplete, 1 failed" in out.split(f"Model {GPT} (openai):")[1].split("Model ")[0]

    assert run_cli_multi(tmp_path / "d", ["o1", "o2"], [client_error(401)]) == 1
    captured = capsys.readouterr()
    gem_block = captured.out.split(f"Model {GEM} (gemini):")[1]
    assert "Summary: 1 of 2 slots attempted: 0 completed, 0 incomplete, 1 failed" in gem_block
    assert "Reported model: none (no response received)" in gem_block
    assert "aborting all remaining slots" in captured.err

    assert run_cli_multi(tmp_path / "e", ["o1", "o2"], ["g1", "g2"]) == 0


# ------------------------------------------------------------ blind review


def test_blind_two_models_four_letters(tmp_path: Path) -> None:
    run_dir, manifest = make_multi(tmp_path, case_ids=("D3", "D4"))
    oa = FakeClient(["reply-o1", "reply-o2", "reply-o3", "reply-o4"])
    gm = FakeGeminiClient(["reply-g1", "reply-g2", "reply-g3", "reply-g4"])
    run_slots({"openai": oa, "gemini": gm}, run_dir, manifest)
    review = render_blind(run_dir)
    assert review.problems == []
    key = json.loads((run_dir / "blind_key.json").read_text(encoding="utf-8"))
    for case in ("D3", "D4"):
        assert list(key[case]) == ["A", "B", "C", "D"]
        models = {entry["slot_key"].split("|")[3] for entry in key[case].values()}
        assert models == {GPT, GEM}
    for i in range(1, 5):
        assert f"reply-o{i}" in review.text and f"reply-g{i}" in review.text
    sheet = (run_dir / "blind_sheet.md").read_text(encoding="utf-8")
    assert "Preference (A / B / C / D / tie):" in sheet
    for text in (review.text, sheet):
        assert_no_model_words(text)
        for word in ("RID", "|", "slot_key", "sample", "gem_1", "resp_1"):
            assert word not in text, word


def test_blind_letters_mix_models_across_shuffles(tmp_path: Path) -> None:
    # Over many fresh reviews, model order under the letters is not fixed.
    firsts: set[str] = set()
    for n in range(30):
        run_dir, manifest = make_multi(tmp_path / str(n), samples=1, case_ids=("D3",))
        run_slots({"openai": FakeClient(["x"]), "gemini": FakeGeminiClient(["y"])}, run_dir, manifest)
        render_blind(run_dir)
        key = json.loads((run_dir / "blind_key.json").read_text(encoding="utf-8"))
        firsts.add(key["D3"]["A"]["slot_key"].split("|")[3])
    assert firsts == {GPT, GEM}


def test_blind_readiness_blocks_on_one_models_missing_slot(tmp_path: Path) -> None:
    run_dir, manifest = make_multi(tmp_path, case_ids=("D3",))
    with pytest.raises(RuntimeError, match="interrupted"):
        run_slots(
            {"openai": FakeClient(["o1", "o2"]),
             "gemini": FakeGeminiClient(["g1", RuntimeError("interrupted")])},
            run_dir, manifest,
        )
    before = snapshot(run_dir)
    with pytest.raises(RunNotReadyError) as exc:
        render_blind(run_dir)
    assert exc.value.lines == ["D3: 3 of 4 samples recorded"]
    assert_no_model_words(str(exc.value))
    assert snapshot(run_dir) == before
    assert not (run_dir / "blind_key.json").exists()


def test_blind_problems_and_errors_have_no_model_names(tmp_path: Path) -> None:
    texts: list[str] = []
    # failed + incomplete + empty replies across both models
    d1, m1 = make_multi(tmp_path / "1", case_ids=("D3",))
    inc = {"text": "cut", "status": "incomplete", "details": {"reason": "max_output_tokens"}}
    run_slots(
        {"openai": FakeClient(["good-1", inc]),
         "gemini": FakeGeminiClient([gresp("unsafe", finish="SAFETY"), gresp(None)])},
        d1, m1,
    )
    r = render_blind(d1)
    assert "1 of 4 replies was incomplete" in r.text
    assert "1 of 4 replies failed to generate" in r.text
    assert "1 of 4 replies returned no text" in r.text
    assert "Only one eligible reply" in r.text and "unsafe" not in r.text
    texts += [r.text, *r.problems, (d1 / "blind_sheet.md").read_text(encoding="utf-8")]

    # a later record under a frozen slot, and a late eligible reply
    d2, m2 = make_multi(tmp_path / "2", case_ids=("D3",))
    run_slots(
        {"openai": FakeClient(["o1", "o2"]),
         "gemini": FakeGeminiClient(["g1", client_error(429)])},
        d2, m2,
    )
    render_blind(d2)
    recs = read_slots(d2)
    with open(d2 / "slots.jsonl", "ab") as fh:
        for rec in (
            {**recs[3], "status": "ok", "output_text": "late-g2", "error": None},
            {**recs[2], "output_text": "replacement-words"},
        ):
            fh.write((json.dumps(rec) + "\n").encode("utf-8"))
    r = render_blind(d2)
    assert r.problems and "late-g2" not in r.text and "replacement-words" not in r.text
    texts += [r.text, *r.problems]

    # sheet without key
    d3, m3 = make_multi(tmp_path / "3", case_ids=("D3",))
    run_slots({"openai": FakeClient(["a", "b"]), "gemini": FakeGeminiClient(["c", "d"])}, d3, m3)
    (d3 / "blind_sheet.md").write_text("typed", encoding="utf-8")
    with pytest.raises(BlindKeyError) as info:
        render_blind(d3)
    texts.append(str(info.value))

    for t in texts:
        assert_no_model_words(t)


# ------------------------------------------------------------ legacy runs


class Raising:
    def __getattr__(self, name: str) -> Any:
        raise AssertionError("must not be called")


def check_runs_root(root: Path, work: Path) -> tuple[int, int]:
    """Copy every run under root; each must open (exit 0) without changing any
    existing file. Returns (directories checked, legacy manifests among them)."""
    dirs = sorted(p for p in root.iterdir() if p.is_dir())
    legacy = 0
    for src in dirs:
        run_dir = work / src.name
        shutil.copytree(src, run_dir)
        before = snapshot(run_dir)
        assert before == snapshot(src)
        review = render_blind(run_dir)
        assert review.problems == [], src.name
        assert cli.main(["show", str(run_dir)]) == 0, src.name
        after = snapshot(run_dir)
        assert {name: after[name] for name in before} == before, src.name
        if "blind_sheet.md" in before:  # reviewed: nothing at all is written
            assert after == before, src.name
        manifest = json.loads(before["manifest.json"].decode("utf-8"))
        if "schema_version" not in manifest:
            legacy += 1
            models = manifest_models(manifest)
            assert len(models) == 1 and models[0]["provider"] == "openai"
    return len(dirs), legacy


def check_resume_skips(root: Path, work: Path) -> int:
    """run_slots on a copy of every complete run attempts nothing."""
    dirs = sorted(p for p in root.iterdir() if p.is_dir())
    for src in dirs:
        run_dir = work / src.name
        shutil.copytree(src, run_dir)
        before = snapshot(run_dir)
        manifest = json.loads(before["manifest.json"].decode("utf-8"))
        clients = {"openai": Raising(), "gemini": Raising()}
        result = run_slots(clients, run_dir, manifest)
        expected = (
            len(manifest["cases"]) * len(manifest_models(manifest))
            * manifest["samples_per_case"]
        )
        assert result.attempted == 0 and result.skipped == expected, src.name
        assert snapshot(run_dir) == before
    return len(dirs)


def test_every_committed_run_still_opens_unchanged(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    checked, legacy = check_runs_root(RUNS, tmp_path)
    capsys.readouterr()
    assert legacy >= 6 and checked >= legacy


def test_run_slots_on_committed_runs_skips_everything(tmp_path: Path) -> None:
    assert check_resume_skips(RUNS, tmp_path) >= 6


def test_run_checks_also_cover_a_two_model_run(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = tmp_path / "root"
    run_dir, manifest = make_multi(root, case_ids=("D3", "D4"))
    run_slots(
        {"openai": FakeClient(["o1", "o2", "o3", "o4"]),
         "gemini": FakeGeminiClient(["g1", "g2", "g3", "g4"])},
        run_dir, manifest,
    )
    assert check_runs_root(root, tmp_path / "a") == (1, 0)
    capsys.readouterr()
    render_blind(run_dir)  # a reviewed two-model run: nothing is written at all
    assert check_runs_root(root, tmp_path / "b") == (1, 0)
    capsys.readouterr()
    assert check_resume_skips(root, tmp_path / "c") == 1


# ------------------------------------------------------------ verifier follow-ups


def test_settings_in_every_slot_record(tmp_path: Path) -> None:
    run_dir, manifest = make_multi(tmp_path)
    oa = FakeClient(["o1", http_error(openai.RateLimitError, 429), "o3", "o4"])
    gm = FakeGeminiClient(["g1", client_error(503), gresp("g3", finish="SAFETY"), "g4"])
    run_slots({"openai": oa, "gemini": gm}, run_dir, manifest)
    slots = read_slots(run_dir)
    assert len(slots) == 8
    statuses = {s["status"] for s in slots}
    assert statuses == {"ok", "generation_failed"}  # success and failure paths
    for s in slots:
        if s["provider"] == "openai":
            assert s["settings"] == {"reasoning_effort": "none"}
        else:
            assert s["settings"] == {"thinking_level": "MINIMAL"}
    # legacy records carry no settings and are still read everywhere
    first_legacy = next(p for p in sorted(RUNS.iterdir()) if p.is_dir())
    assert "settings" not in read_slots(first_legacy)[0]


@pytest.mark.parametrize("level", gemini.THINKING_LEVELS)
def test_thinking_level_reaches_the_call(level: str) -> None:
    req = gemini.build_request("P", [Turn(role="user", utterance="u")], GEM, level)
    client = FakeGeminiClient(["x"])
    gemini.generate(client, req)
    config = client.calls[0]["config"]
    assert config.thinking_config is not None
    assert config.thinking_config.thinking_level == types.ThinkingLevel(level)


def test_settings_reach_both_providers_through_cli(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    no_network(monkeypatch)
    oa = FakeClient(["o1", "o2"])
    gm = FakeGeminiClient(["g1", "g2"])
    args = base_args(
        tmp_path, "--model", GPT, "--model", GEM,
        "--reasoning-effort", "low", "--gemini-thinking-level", "high",
    )
    assert cli.main(args, client_factories={"openai": lambda: oa, "gemini": lambda: gm}) == 0
    assert [c["reasoning"] for c in oa.calls] == [{"effort": "low"}] * 2
    assert [c["config"].thinking_config.thinking_level for c in gm.calls] == [
        types.ThinkingLevel.HIGH
    ] * 2


def test_cli_26_replies_per_case_is_allowed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    no_network(monkeypatch)
    models = [a for i in range(13) for a in ("--model", f"gpt-m{i}")]
    code = cli.main(
        base_args(tmp_path, *models),
        client_factories={"openai": lambda: FakeClient([f"r{i}" for i in range(26)])},
    )
    assert code == 0
    run_dir = next((tmp_path / "runs").iterdir())
    capsys.readouterr()
    review = render_blind(run_dir)
    key = json.loads((run_dir / "blind_key.json").read_text(encoding="utf-8"))
    assert list(key["D3"]) == [chr(ord("A") + i) for i in range(26)]
    assert review.problems == []


def test_create_run_rejects_more_than_26_replies(tmp_path: Path) -> None:
    specs = [openai_spec(f"gpt-m{i}") for i in range(6)]
    with pytest.raises(ValueError, match="at most 26"):
        create_run(
            tmp_path, "R", InputFile("prompts/v1.md", b"p"),
            [InputFile("cases/c0.jsonl", CASE)], specs, 5,
        )
    assert not any(tmp_path.iterdir())


def test_render_blind_refuses_more_than_26_replies(tmp_path: Path) -> None:
    run_dir, manifest = make_multi(tmp_path, samples=1, case_ids=("D3",))
    run_slots({"openai": FakeClient(["a"]), "gemini": FakeGeminiClient(["b"])}, run_dir, manifest)
    edited = {**manifest, "samples_per_case": 14}  # 2 models x 14 = 28
    (run_dir / "manifest.json").write_text(json.dumps(edited), encoding="utf-8")
    before = snapshot(run_dir)
    with pytest.raises(BlindKeyError, match="at most 26") as info:
        render_blind(run_dir)
    assert_no_model_words(str(info.value))
    assert snapshot(run_dir) == before


def test_duplicate_model_in_manifest_is_refused(tmp_path: Path) -> None:
    run_dir, manifest = make_multi(tmp_path, samples=1, case_ids=("D3",))
    run_slots({"openai": FakeClient(["a"]), "gemini": FakeGeminiClient(["b"])}, run_dir, manifest)
    edited = {**manifest, "models": [manifest["models"][1], manifest["models"][1]]}
    with pytest.raises(ValueError, match="same model more than once") as info:
        manifest_models(edited)
    assert_no_model_words(str(info.value))
    (run_dir / "manifest.json").write_text(json.dumps(edited), encoding="utf-8")
    before = snapshot(run_dir)
    with pytest.raises(ValueError, match="same model more than once"):
        render_blind(run_dir)
    with pytest.raises(ValueError, match="same model more than once"):
        run_slots({"openai": Raising(), "gemini": Raising()}, run_dir, edited)
    assert snapshot(run_dir) == before


def test_cli_show_reports_bad_manifest_cleanly(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    run_dir, manifest = make_multi(tmp_path, samples=1, case_ids=("D3",))
    run_slots({"openai": FakeClient(["a"]), "gemini": FakeGeminiClient(["b"])}, run_dir, manifest)
    edited = {**manifest, "models": [manifest["models"][1], manifest["models"][1]]}
    (run_dir / "manifest.json").write_text(json.dumps(edited), encoding="utf-8")
    before = snapshot(run_dir)
    assert cli.main(["show", str(run_dir)]) == 2
    err = capsys.readouterr().err
    assert "same model more than once" in err and "Nothing was written." in err
    assert "Traceback" not in err
    assert_no_model_words(err)
    assert snapshot(run_dir) == before


def test_label_beyond_z_is_an_error() -> None:
    from rightoncue.runs import _label

    assert _label(25) == "Z"
    with pytest.raises(ValueError):
        _label(26)
