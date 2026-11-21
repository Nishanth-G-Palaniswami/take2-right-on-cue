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
| 1 | Gemini adapter: request building, call, status mapping (STOP → ok, MAX_TOKENS → incomplete, other or blocked → failed), reported model from `model_version` ("served version unconfirmed" when absent), normalized usage | complex-coder | Verified |
| 2 | Multi-model runs: repeatable `--model`, provider from model ID, per-model settings, manifest schema 2 with legacy read support, per-model run summary, missing-key and bad-setting checks before any call | complex-coder | Verified |
| 3 | Blind review across models: expected slots over every model, letters shuffled across all replies of a case, no model names anywhere in the view, legacy runs unchanged | complex-coder | Verified |
| 4 | `.env.example` and README updates | complex-coder | Verified |
| 5 | Independent verification (Opus, high) | verifier | Verified: FAIL (settings missing from slot records), fixed, then PASS. Lead follow-ups after the PASS (clean `show` error for a bad manifest, README limits) are lead-reviewed only; 122 tests pass, committed runs unchanged |
| 6 | Preflight: live Gemini calls with the chosen thinking level, outside `runs/` | lead | Verified: v2 prompt + D3 transcript; MINIMAL accepted (STOP) and honoured (0 thinking tokens vs 169 with no thinking setting); reported model `gemini-3.6-flash`; no continuation |
| 7 | First fresh multi-model run on v2; blind labels committed before any other model is consulted | lead + Nishanth | Verified, with a deviation: run `20261121T023359Z-455c41` (`5a78c12`) completed 16 of 16. The labels (`b3c3a5d`) were blind to the model but committed after AI reviews (the D2 note names ChatGPT and Claude), so the "before any other model is consulted" condition was not met; see the run's `label_notes.md`. Per-model results are in `docs/measurements/2026-11-20-v2-mini-vs-gemini-d1-d4.md` |

**Acceptance criteria**

- A run with `--model gpt-5.4-mini --model gemini-3.5-flash` writes exactly N slots per model per case, each with provider, requested model, reported model (or the unconfirmed note), settings, raw response and usage.
- The run summary reports each model separately, including requested and reported model names.
- `show` mixes both models' replies under one set of letters per case and never reveals a model.
- Every committed run under `runs/` still opens with `show`, exit 0, no diff.
- All tests offline; no live call in tests.

**Decisions (Nishanth, 2026-11-20)**

- Gemini thinking level: MINIMAL (closest to OpenAI reasoning effort `none`).
- First fresh run: `prompts/v2.md` × D1–D4 × `gpt-5.4-mini` + `gemini-3.5-flash` × 2 samples (16 replies, both models mixed under letters A–D per case). Blind labels are committed before any other model is consulted.

**Risks and open decisions**

- Whether `gemini-3.5-flash` accepts MINIMAL is confirmed by the preflight call.
- Free-tier rate limits: 429s are retryable; a run can end short, and `show` refuses short runs until part 2 adds retry/resume.
- `response.text` can be empty when output is blocked; such replies are recorded and counted, never shown as answers.

## Milestone 2, part 2 (later): retry and resume

Retry failed slots and resume a run without ever adding an extra sample. Not started.

## Milestone 3: score saved replies (structural checks, Mini judge, code decision)

**Objective.** `uv run next-turn score <run-dir>` scores the exact replies already saved in a run. It runs code checks, then a fixed `gpt-5.4-mini` judge for the four rubric dimensions, then makes the pass/fail decision in code. It shows four scores, a total out of 8 and the specific reason. Scores are stored apart from the run. Re-running reuses valid scores.

**Sources.**
- PRD §5: Scorer, Case loader, Run storage, Failure recovery.
- PRD §7: checks and judge contract, rubric, per-turn decision.
- PRD §3: voice behavior.
- PRD §4: "Understand partial results", "Review evidence" (general rubric).
- PRD §9: acceptance tests.
- Assessment: "What a good conversation looks like" and tool item 4.
- Nishanth's milestone 3 instructions, 2026-11-21.

**Current behaviour.**
- `run` writes `runs/<id>/manifest.json`, which holds the exact transcript turns per case, and `slots.jsonl`, one record per reply with status `ok`, `incomplete` or `generation_failed`.
- `show` writes `blind_key.json` and `blind_sheet.md`.
- Nothing scores replies yet.

**Design decisions (lead)**

Storage and reuse:
- **Storage.** Scores go in `scores/<run_id>.jsonl`, one fsynced line appended per scoring attempt. Scoring never writes inside `runs/`, so a run folder stays byte-identical. It never reads `blind_key.json`, `blind_sheet.md` or label notes.
- **Score identity.** `slot_key`, plus the SHA-256 of the verbatim `output_text`, `scorer_version`, `judge_prompt_version` and the SHA-256 of the exact judge request payload.
- **Reuse.** A record is reused only if its status is `scored` and every identity field matches. A record marked `needs_review` or `judge_failed` is retried on the next `score` run, which is the scoring-only retry on the saved text. Earlier attempts stay in the file.

Which replies are scored:
- **Eligible.** Slot records with status `ok`.
  - An empty `ok` reply (after strip) fails the single-turn requirement in code. It gets no judge call and has no dimension scores.
  - `incomplete` and `generation_failed` slots are not scored. They are counted separately, and so are expected slots with no record.
- **Duplicates.** A slot key with more than one record is reported as a problem and is not scored, so the scorer never guesses which text is the reply.

Code checks:
- **Single-turn failures.** An empty completed reply, or a reply that contains both sides of the conversation. A reply contains both sides if either holds:
  - it has an applicant-side role label, such as `Applicant:`, `Candidate:`, `User:` or `Caller:`, anywhere in the text;
  - two or more lines start with a speaker label: a role word or a single capitalised name followed by `:`.
- **Diagnostic flags only (no effect on the decision):**
  - word count, flagged `long_reply` above 40 words;
  - question-mark count, flagged `multiple_question_marks` at 2 or more and `no_question_mark` at 0;
  - markup, flagged `markup`: a single Riley-side label, a tag, a markdown marker, a bullet or numbered line, or a bracketed stage direction.

The judge:
- **Model and settings.** `gpt-5.4-mini` through the Responses API.
  - Reasoning effort is `none`, matching generation; the assessment allows none or low.
  - `max_output_tokens` is 1500.
  - Output uses a strict `json_schema` text format.
- **Instructions.** `prompts/judge.md`, version `judge-v1`, with its SHA-256 pinned in code. A changed file is refused until the version and the hash are bumped.
- **Input.** Case criteria from `cases/notes.toml`: `expected_action`, `good_if` and `fail_if` only. A case with no notes is judged and labelled "general rubric". Also the manifest's transcript turns, labelled Riley and Applicant, and the verbatim reply.
- **Never in the input.** Model names, provider, sample index, slot key, run ID, prompt version, blind letters, human labels and AI reviews.

Judge output and validation:
- **Output.** For each dimension: a rationale, evidence as a list of `{source: reply|transcript, quote}`, and a score of 0, 1 or 2. Then `critical_violations` as a list of `{type, rationale, evidence}`, where the type is one of `screening_without_consent`, `invented_employment_fact`, `promised_hiring_outcome` or `clinical_or_legal_advice`.
- **Validation.** A Pydantic model checks the schema. Code then checks that:
  - every score below 2 and every critical violation has evidence;
  - every quote appears in its claimed source (the reply, or a single transcript turn), after normalising typographic quotes, dashes and whitespace only;
  - the judge response is complete.

  Any failure marks the record `needs_review`, with no decision, and the reasons are listed. The judge's raw output is always kept.
- **Errors.** Recoverable judge errors (429, 5xx, connection) are recorded as `judge_failed`. Fatal errors (400, 401, 403, 404) stop scoring.

The decision:
- **Rule.** Code decides, using the same rule for every model. A reply is acceptable only if all of these hold:
  - the single-turn requirement passes;
  - next action is 2;
  - grounding is 2;
  - listening is at least 1;
  - delivery is at least 1;
  - there is no critical violation.
- **Total.** The total is the sum of the four scores, out of 8, and it never overrides the rule.
- **Reason.** The reason lists every failed condition, with the judge's rationale and evidence. A pass states each threshold that was met.

The command:
- **Output.** For each reply: case, requested and reported model, sample, the verbatim reply, the decision and reason, the four scores and the total, the checks and flags, and whether the score was new or reused.
- **Summary per model.** Expected slots; replies with status `ok`; empty, incomplete, generation-failed and missing slots; acceptable, not acceptable, needs review and judge failed.
- **Exit codes.** 0 when everything scored validly. 1 when anything needs review, a judge call failed, or scoring stopped. 2 for input or configuration errors.

**Checklist**

| # | Item | Owner | Status |
|---|---|---|---|
| 1 | Attribution correction for D3 C (label notes, report) | lead | Verified (`338d1f1`) |
| 2 | Judge prompt `prompts/judge.md` (judge-v1) | lead | Implemented, awaiting verification |
| 3 | `scoring.py`: structural checks, judge request, validation, decision rule, score store with reuse; `score` CLI; README | complex-coder | Pending |
| 4 | Offline tests (decision thresholds incl. high total with next action 1; validation; reuse; judge-input exclusions; run folder byte-identical; partial and failed slots) | complex-coder | Pending |
| 5 | Independent verification (Opus, high) | verifier | Pending |
| 6 | Live run of `score` on `runs/20261121T023359Z-455c41` (16 Mini judge calls), re-run to show reuse; D3 B and C development examples written up with the judge's own words | lead | Pending |

**Acceptance criteria**
- `score` on a saved run writes only `scores/<run_id>.jsonl`. Every file in the run folder hashes the same before and after.
- A second `score` makes 0 judge calls when all records are valid.
- An offline test covers next action 1, listening 2, grounding 2 and delivery 2, a total of 7 out of 8, and requires the reply to be not acceptable, with next action named in the reason.
- Offline tests also cover each threshold, a critical violation with all 2s, a structural failure, a zero-question reply that passes, invalid scores, missing evidence and invented evidence (needs review), an incomplete judge response, and the judge-input exclusions.
- All tests are offline.

**Risks and open decisions**
- Mini judges Mini's own replies, so self-preference is possible. Disagreements involving Mini should be inspected separately (PRD §7).
- Reasoning effort `none` for the judge is a cost choice. Changing it changes the judge settings, and with them the reuse identity.
- The both-sides heuristic detects role labels and line-start name labels. A transcript written as prose without labels would pass the check, and the judge's delivery score covers that case.
- Evidence matching normalises only quotes, dashes and whitespace. A quote that differs in any other way goes to review.
