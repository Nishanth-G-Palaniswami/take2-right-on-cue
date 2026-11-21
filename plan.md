# Plan

## Milestone 2, part 1: Gemini and multi-model runs

**Objective.** Run the same prompt and cases against `gpt-5.4-mini` and `gemini-3.5-flash` in one run, record the requested and the reported model for every reply, report each model's results separately, and keep the blind review working across models. Full `gpt-5.4` is reserved for the planned final comparison. v3 (phrasing) is deferred.

**Current behaviour.** `next-turn run` supports one OpenAI model per run (`manifest.model` is a string; one request per case). Each slot already stores `requested_model` and `returned_model` (the model the API reports, e.g. `gpt-5.4-mini-2026-03-17`). `show` assumes one model per run.

**Dependencies and assumptions**

- Official `google-genai` SDK (3.6.1 checked): `client.models.generate_content(model, contents, config)`, `config.system_instruction`, `config.thinking_config.thinking_level` (MINIMAL/LOW/MEDIUM/HIGH/XHIGH), response `model_version`, `usage_metadata`, `candidates[0].finish_reason`; errors `ClientError` (4xx) and `ServerError` (5xx) with `.code`.
- `GEMINI_API_KEY` in `.env` (present). Nishanth's own access check: requested `gemini-3.5-flash`, API reported `gemini-3.6-flash`, OK.
- The Gemini thinking level is an experimental setting Nishanth chooses; it is recorded in the manifest. Whether the model accepts it is confirmed by a preflight call before the first real run.
- Existing runs stay readable and byte-identical under `show`.

**Checklist**

| # | Item | Owner | Status |
|---|---|---|---|
| 1 | Gemini adapter: request building, call, status mapping (STOP → ok, MAX_TOKENS → incomplete, other or blocked → failed), reported model from `model_version` ("served version unconfirmed" when absent), normalized usage | complex-coder | Pending |
| 2 | Multi-model runs: repeatable `--model`, provider from model ID, per-model settings, manifest schema 2 with legacy read support, per-model run summary, missing-key and bad-setting checks before any call | complex-coder | Pending |
| 3 | Blind review across models: expected slots over every model, letters shuffled across all replies of a case, no model names anywhere in the view, legacy runs unchanged | complex-coder | Pending |
| 4 | `.env.example` and README updates | complex-coder | Pending |
| 5 | Independent verification (Opus, high) | verifier | Pending |
| 6 | Preflight: one tiny live Gemini call with the chosen thinking level, outside `runs/` | lead | Pending |
| 7 | First fresh multi-model run on v2; blind labels committed before any other model is consulted | lead + Nishanth | Pending |

**Acceptance criteria**

- A run with `--model gpt-5.4-mini --model gemini-3.5-flash` writes exactly N slots per model per case, each with provider, requested model, reported model (or the unconfirmed note), settings, raw response and usage.
- The run summary reports each model separately, including requested and reported model names.
- `show` mixes both models' replies under one set of letters per case and never reveals a model.
- Every committed run under `runs/` still opens with `show`, exit 0, no diff.
- All tests offline; no live call in tests.

**Risks and open decisions**

- Gemini thinking level (decision for Nishanth).
- Free-tier rate limits: 429s are retryable; a run can end short, and `show` refuses short runs until part 2 adds retry/resume.
- `response.text` can be empty when output is blocked; such replies are recorded and counted, never shown as answers.

## Milestone 2, part 2 (later): retry and resume

Retry failed slots and resume a run without ever adding an extra sample. Not started.
