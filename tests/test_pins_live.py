"""Pins written BEFORE the hosted-live change, against dc8b1dd.

They keep two things byte for byte: the runner's requests and manifests when no
output cap is given (the CLI and the saved runs), and the hosted-off / local live
behaviour of the app. Offline: fake clients only.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

import pytest
from streamlit.testing.v1 import AppTest
from test_gemini import gemini_spec
from test_run import openai_spec

from rightoncue import review
from rightoncue.runs import InputFile, _build_request, create_run, manifest_models
from rightoncue.transcript import Turn

REPO = Path(__file__).parent.parent
APP = str(REPO / "app.py")
LIVE_ENV = (
    "RIGHTONCUE_HOSTED",
    "RIGHTONCUE_ACCESS_CODE",
    "RIGHTONCUE_BUDGET_USD",
    "RIGHTONCUE_DATA_DIR",
    "RIGHTONCUE_MAX_SAMPLES",
    "RIGHTONCUE_DRY_RUN",
    "RIGHTONCUE_DRY_RUN_DELAY_S",
)
CASE = b'{"role":"agent","utterance":"Hi \\u00e9"}\n{"role":"user","utterance":"Hello"}\n'
# sha256 of the masked manifest below, computed on dc8b1dd before any change.
MANIFEST_PIN = "72315158d26142333194c013539400a08c33458a325cee45f085b90dfb575b61"


def masked_manifest(run_dir: Path) -> str:
    text = (run_dir / "manifest.json").read_text(encoding="utf-8")
    for key in ("created_at", "openai_sdk_version", "google_genai_sdk_version", "python_version"):
        text = re.sub(rf'"{key}": "[^"]*"', f'"{key}": "<X>"', text)
    return re.sub(r'"git": \{[^}]*\}', '"git": "<X>"', text)


def test_uncapped_manifest_and_requests_are_byte_identical(tmp_path: Path) -> None:
    run_dir, _ = create_run(
        tmp_path, "RID", InputFile("prompts/v1.md", "Be Riley. \u00e9".encode()),
        [InputFile("cases/c0.jsonl", CASE)],
        [openai_spec("gpt-5.4"), gemini_spec("gemini-3.5-flash")], 2,
    )
    digest = hashlib.sha256(masked_manifest(run_dir).encode("utf-8")).hexdigest()
    assert digest == MANIFEST_PIN, digest


def committed_manifests() -> list[Path]:
    return sorted((REPO / "runs").glob("*/manifest.json"))


@pytest.mark.parametrize("path", committed_manifests(), ids=lambda p: p.parent.name)
def test_committed_requests_rebuild_byte_for_byte(path: Path) -> None:
    """Every saved schema-2 run's recorded requests equal what the runner builds now."""
    manifest = json.loads(path.read_text(encoding="utf-8"))
    if manifest.get("schema_version") is None:
        pytest.skip("legacy manifest: one request per case, built by older code")
    from rightoncue.runs import ModelSpec

    for case in manifest["cases"]:
        turns = [Turn.model_validate(t) for t in case["turns"]]
        for m in manifest_models(manifest):
            spec = ModelSpec(m["model"], m["provider"], m["settings"], m["client"])
            rebuilt = _build_request(spec, manifest["prompt"]["text"], turns)
            recorded = case["requests"][m["model"]]
            assert json.dumps(rebuilt, sort_keys=False) == json.dumps(recorded, sort_keys=False)


# ------------------------------------------------------------------ the app


@pytest.fixture
def offline(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(REPO)
    for name in LIVE_ENV + ("OPENAI_API_KEY", "GEMINI_API_KEY"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(review, "load_env", lambda: None)

    def boom() -> Any:
        raise AssertionError("a real client must not be built in an offline test")

    monkeypatch.setattr(review, "CLIENT_FACTORIES", {"openai": boom, "gemini": boom})


HOSTED_OFF = (
    "Live evaluation is not available in this hosted replay. Run the app locally "
    "with your own API keys to generate and score new replies: `uv sync`, then "
    "`uv run streamlit run app.py`."
)


@pytest.mark.usefixtures("offline")
def test_pin_hosted_without_access_code_has_live_off(monkeypatch: pytest.MonkeyPatch) -> None:
    """Hosted with keys present but no access code: the replay message, no form."""
    monkeypatch.setenv("RIGHTONCUE_HOSTED", "1")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-pin-secret")
    monkeypatch.setenv("GEMINI_API_KEY", "gm-pin-secret")
    at = AppTest.from_file(APP, default_timeout=60).run()
    assert not at.exception
    assert [i.value for i in at.info if "hosted replay" in i.value] == [HOSTED_OFF]
    assert not at.multiselect and not at.text_input and not at.checkbox
    assert not [b for b in at.button if (b.key or "").startswith(("live_", "hl_"))]
    captions = " ".join(c.value for c in at.caption)
    assert "OPENAI_API_KEY" not in captions and "sk-pin-secret" not in captions


@pytest.mark.usefixtures("offline")
def test_pin_local_live_form_as_now() -> None:
    """Local mode, no budget: the same widgets, texts and limits as dc8b1dd."""
    at = AppTest.from_file(APP, default_timeout=60).run()
    assert not at.exception
    assert at.number_input(key="live_samples").max == review.MAX_SAMPLES == 5
    assert at.multiselect(key="live_models").options == list(review.MODEL_CHOICES)
    assert any(
        i.value.startswith("Generating makes 2 paid call(s) to the selected models (no output cap).")
        for i in at.info
    )
    assert "Generation and scoring are paid API calls billed to your keys." in [c.value for c in at.caption]
    assert at.selectbox(key="live_effort").options == ["none", "low"]
    assert [w.key for w in at.radio] == ["sel_case", "sel_prompt", "sel_sample", "live_prompt_src", "live_case_src"]
    assert not at.text_input  # no access code field locally
