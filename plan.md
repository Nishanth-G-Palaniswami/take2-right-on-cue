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
- **Single-turn failures.** An empty completed reply, or a reply that contains both sides of the conversation (PRD §7, "multiple speaker blocks").
  - A *speaker label* is a role word in any case (Riley, Recruiter, Agent, Assistant, AI, Interviewer, Applicant, Candidate, User, Caller, Nurse, Interviewee) or a single capitalised word in any script (for example `José:`). It may be wrapped in `**`, `__` or `[ ]`, and is followed by `:`.
  - A label counts only at one of three positions:
    - (a) the start of the reply;
    - (b) the start of a line;
    - (c) directly after sentence-ending punctuation (`.`, `?` or `!`, optionally followed by a closing quote) and whitespace.
  - The reply fails if any of these holds:
    - R1: an applicant-side role word (applicant, candidate, user, caller, nurse, interviewee) is used as a label at position (a), (b) or (c). A mid-sentence "as a candidate:" doesn't count.
    - R2: two or more labels sit at positions (a) or (b).
    - R3: the reply starts with a label at position (a), and another label follows at position (b) or (c).
    - R4: a label starts any line other than the first non-empty line, at position (b).
  - A single label at the very start with nothing else is only the `markup` diagnostic flag, not a failure.
  - Each failure message names the rule that fired and quotes the label.
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
- **Exit codes.** 0 when everything scored validly. 1 when anything needs review, a judge call failed, scoring stopped, a slot has duplicate records, or a record matches no expected slot. 2 for input or configuration errors, including a scores directory inside a run folder or inside a directory that holds run folders (a run folder has a `manifest.json` that is a JSON object with `run_id` and `samples_per_case`), and a corrupt score file.

**Checklist**

| # | Item | Owner | Status |
|---|---|---|---|
| 1 | Attribution correction for D3 C (label notes, report) | lead | Verified (`338d1f1`) |
| 2 | Judge prompt `prompts/judge.md` (judge-v1) | lead | Verified (`db3623d`; hash pinned and checked by every verifier pass) |
| 3 | `scoring.py`: structural checks, judge request, validation, decision rule, score store with reuse; `score` CLI; README | complex-coder | Verified |
| 4 | Offline tests (decision thresholds incl. high total with next action 1; validation; reuse; judge-input exclusions; run folder byte-identical; partial and failed slots) | complex-coder | Verified (236 tests pass) |
| 5 | Independent verification (Opus, high) | verifier | First pass: PASS with 6 non-blocking findings. Four were fixed (single-turn rule R1–R4, scores-dir guard, clean exit 2 for corrupt input, exit 1 for unmatched records). Two were left as designed (409 and 422 propagate as in `run`; `--scores-dir`/`--notes` kept as documented options). Second pass: FAIL (`--scores-dir runs/<new>` accepted); fixed, with corrupt reused records, manifest field types and non-ASCII labels. The lead narrowed run-folder detection to real run manifests. Third pass: PASS; its two minor follow-ups (a permission error in the guard becomes an input error; two more false negatives listed under risks) were made by the lead with a test |
| 6 | Live run of `score` on `runs/20261121T023359Z-455c41` (16 Mini judge calls), re-run to show reuse; D3 B and C development examples written up with the judge's own words | lead | Verified. 18 calls: 16, then 2 retries of `needs_review`, then 0. Run folder byte-identical. All 16 replies 8/8 acceptable; the scorer disagrees with Nishanth's labels on D3 B, C and D. See `docs/measurements/2026-11-21-judge-v1-dev-run.md` |
| 7 | Diagnostic pass (Nishanth, 2026-11-21): trace D3-A and D3-C end to end; test the smallest justified judge-prompt change on the 20 development replies with two draws | lead | Verified. No pipeline bug: all 22 judge-v1 records match their raw responses. Arms `judge-v2a` and `judge-v2b` (`844e719`) caught 0 of 3 D3 rejections and added false failures, so neither is adopted and judge-v1 stays the default. A defect was found in the critical-violation list: the judge lists types with rationales that deny them. It is reported with options, not fixed. 113 calls. See `docs/measurements/2026-11-21-judge-diagnostic.md` |
| 8 | Judge version registry and `--judge-version` (judge-v1 default) | complex-coder | Verified (`16e2f2a`, verifier PASS; 240 tests) |
| 9 | `judge-v3` (`prompts/judge-v3.md`: judge-v1 plus a present/absent verdict for each critical type and a no-speaker-label quote rule) scored under `scorer-2` (only present entries count; a present entry needs evidence). judge-v1, v2a and v2b stay on `scorer-1` and keep being reused. D3 recorded as a known limitation (diagnostic doc, section 6) | lead (prompt, docs) + complex-coder (code, tests) | Verified (verifier on Opus: PASS, no blocking findings, 12 of 13 mutants caught; 267 tests; judge-v1 and judge-v2a plan 0 calls against the committed scores) |
| 10 | Pre-registration of the judge-v3 development draws (diagnostic doc, section 7) | lead | Verified (reviewed by Nishanth; his clarifications are in section 8) |
| 11 | Live judge-v3 draws on the 20 development replies | lead | Verified, complete. 41 calls (1 preflight + 40 first attempts); no retry made a call; estimated $0.18506. Criteria 1, 2 and 4 met; criterion 3 not met on D1-C, so judge-v3 is not adopted (Nishanth). Diagnostic doc, section 9 |
| 12 | Freeze judge-v1 for the model comparison and document its known limits and reporting rules (`docs/judge-v1-known-limits.md`) before holdout work | lead | Verified (lead). The freeze, the retry rule (one retry) and the reporting rules were clarified by Nishanth on 2026-11-21, before the `gpt-5.4` development run |

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
- A reply in which a later line starts with a single capitalised word and a colon (for example `Note:`) is treated as a new speaker block and fails R4. That false positive is accepted, because a spoken reply shouldn't contain labelled lines.
- A reply that starts with its own label and later has an inline single-word label after a sentence end fails R3, for example `"Riley: Great. Question: are both current?"`. That false positive is accepted.
- The single-turn rule misses these labels: one after a sentence end when the reply doesn't start with a label (`"Are they current? Sam: Yes, both."`), two-word names (`"Sam Lee:"`), parenthesised labels (`"Applicant (Sam):"`), single-asterisk wrapping (`"*Sam*:"`), bullet or quote prefixes (`"- Sam:"`, `"> Sam:"`), a label with no space after the punctuation or after a `…` ellipsis character (three dots `...` are caught), a name written with a combining accent mark rather than a precomposed letter, and a name in a script without letter case (`"李:"`). The judge's delivery score ("exposes tool or role markup") is the backstop for these.
- Evidence matching normalises only quotes, dashes and whitespace. A quote that differs in any other way goes to review.

## Model comparison, development run: `gpt-5.4` on v2

**Objective.** Generate 8 `gpt-5.4` replies on the same inputs as run `20261121T023359Z-455c41`: `prompts/v2.md`, D1–D4, 2 samples, reasoning effort `none`. They can then be compared on v2 with the Mini and Gemini replies already in that run.

**Decisions (Nishanth, 2026-11-21).**
- **Scope.**
  - The run generates `gpt-5.4` only.
  - The Mini and Gemini results from `455c41` are reused, not regenerated.
- **Labels.**
  - Nishanth labels the 8 new replies before seeing any judge score.
  - The labels are not model-blind: he knew all eight came from `gpt-5.4`, and this is disclosed with the results.
- **Preflight.**
  - One `gpt-5.4` call checks that the API accepts reasoning effort `none`. Its reply is excluded from the eight samples.
  - If the API rejects the setting, the work stops and the error goes to Nishanth, before any switch to `low` or any other run.
- **Scoring.**
  - Scoring happens only after Nishanth commits his labels, with the frozen judge-v1.
  - Each `needs_review` or `judge_failed` judgment gets one retry. Every scored verdict is preserved, and anything still unscored after its retry is reported.
  - The reporting rules are in `docs/judge-v1-known-limits.md`.
- **Branch.** The run is made from the local `judge-v3` branch, with a clean tree, so the manifest records the commit actually used. `main` and the remote are left alone.
- **Holdouts.** H1–H4 stay sealed.
- **Prompt comparison.**
  - The final comparison covers v1 and v2 for all three models, with matched cases and sample counts, reusing existing runs where they match.
  - This v2-only run shows how the models compare on v2. Whether the prompt change narrowed the gaps between models can't be concluded until the matched v1 results exist.

**Checklist**

| # | Item | Owner | Status |
|---|---|---|---|
| 1 | Freeze clarification and these decisions (`docs/judge-v1-known-limits.md`, this section) | lead | Verified (lead) |
| 2 | Preflight: one `gpt-5.4` call with reasoning effort `none`, kept outside `runs/` | lead | Verified. Accepted: status completed, effort `none` echoed back, 0 reasoning tokens, reported model `gpt-5.4-2026-03-05`, 797 input and 35 output tokens, about $0.00252. Its reply is excluded and wasn't viewed |
| 3 | Run: v2 × D1–D4 × `gpt-5.4` × 2, then commit the run with its blind key and sheet | lead | Verified. Run `20261121T195552Z-6237ea`: 8 of 8 completed, reported model `gpt-5.4-2026-03-05`, 7,728 input and 251 output tokens, 0 reasoning, about $0.02309. The manifest records `26cd5d4` with a clean tree. The prompt and case files hash the same as in `455c41` |
| 4 | Labels for the 8 replies, committed before any scoring | Nishanth | Verified. Entered by Nishanth and committed in `f13316a` by the coding session, after he reported finishing and before any scoring. Only the answer fields changed. Not model-blind (disclosed) |
| 5 | Score with judge-v1 (one retry), then report next to `455c41` | lead | Verified. 8 judge calls, all valid on the first attempt, so no retry was needed and none is unscored. 5 acceptable, 3 not acceptable. D4-B's 4 critical entries all deny a violation in their own rationale (known limit 1). Nishanth reviewed them and found all four absent (`runs/20261121T195552Z-6237ea/critical_review.md`); the raw verdict is kept. Report: `docs/measurements/2026-11-21-gpt54-v2-dev.md` |
| 6 | Final comparison: v1 and v2 × three models, with matched cases and sample counts | lead + Nishanth | In progress. The development matched set (D1–D4) is reported in `docs/measurements/2026-11-21-v1-v2-matched-dev.md`. The holdouts (H1–H4) are not started |
| 7 | v1 matched set (Nishanth, 2026-11-21). Mini v1 reuses `0dbed1` for D1/D2 and `6c1135` for D3/D4: their original labels were recorded before any scoring. The report notes `6c1135`'s later D4 tie correction. `70fb30` is not used, because it was the material for the judge investigation | Nishanth | Verified (decision) |
| 8 | Run: v1 × D1–D4 × `gpt-5.4` + `gemini-3.5-flash` × 2 = 16 replies, one combined run, no preflight. Blind sheet with the model-to-letter mapping hidden | lead | Verified. Run `20261121T202643Z-96f2fa`: 16 of 16 completed. `gpt-5.4` reported as `gpt-5.4-2026-03-05`: 7,560 input and 215 output tokens, 0 reasoning, about $0.02213. `gemini-3.5-flash` reported as `gemini-3.6-flash`. The manifest records `8ef9391` with a clean tree, and the v1 prompt hashes the same as in `0dbed1` and `6c1135`. The blank sheet is created; the key wasn't opened |
| 9 | Labels for the 16 replies, committed before any scoring | Nishanth | Verified. Committed in `c10c6e5`, answer fields only. The model was hidden; Nishanth saw ChatGPT's suggestions before finalizing (`runs/20261121T202643Z-96f2fa/label_notes.md`, `65adf94`) |
| 10 | Score the new run, `0dbed1` and `6c1135` with frozen judge-v1 (one retry rule) | lead | Verified. 30 judge calls: 24 first attempts, of which 6 were `needs_review` and 0 `judge_failed`, plus 6 retries. About $0.10161. After the retry, 3 are still unscored, all because of a speaker-label quote, and are reported as operational failures: `96f2fa` D1 Gemini sample 1, `96f2fa` D2 `gpt-5.4` sample 2, and `0dbed1` D2 Mini sample 1 |

judge-v4 is deferred until the assessment comparison is complete (Nishanth, 2026-11-21).

## Holdout evaluation (H1–H4)

**Objective.** Evaluate the frozen setup on four fresh holdout cases. Nishanth's labels are recorded before he sees model identities, judge verdicts or AI suggestions.

**Decisions (Nishanth, 2026-11-21).**
1. **The frozen setup.**
   - Interviewer prompt v2 is frozen as final, and v1 is the baseline.
   - judge-v1 stays frozen (`scorer-1`, effort `none`); Gemini runs at `MINIMAL`.
   - judge-v4 is deferred.
2. **Authorship.** Nishanth writes the four transcripts (`cases/holdout/H1–H4.jsonl`) and their criteria (`cases/notes.toml`, `split = "holdout"`). The lead checks only that the transcripts parse, the scorer loads the notes, and the offline tests pass.
3. **Scope.**
   - Two samples per model, per prompt, per case: all three models on H1–H4 under v1 and v2, giving 48 replies.
   - From the v2 run, 12 pairs selected in advance: one per model pairing per case.
4. **Labelling order.**
   1. **The combined review sheet.** It shows all 12 replies per case, shuffled under neutral IDs, with prompt, model, sample number and run ID hidden. Nishanth commits all 48 accept/reject labels first.
   2. **The pair sheet.** Only then is it shown. It hides the models, but Nishanth knows its prompt is v2. He commits his 12 A/B/tie choices and reasons before any score, identity or AI suggestion.
5. **The pairs.** In every case:
   - **Sample assignment:**
     - `gpt-5.4` s1 vs Mini s1;
     - `gpt-5.4` s2 vs Gemini s1;
     - Mini s2 vs Gemini s2.
   - **Placement:** balanced left/right, with each model on the left in 2 of the 4 cases per pairing, drawn from fresh OS randomness.
   - **Commitment:** a salted SHA-256 of the mapping is committed before generation and verified when the mapping is revealed.
   - **Automated A/B/tie:** from the raw judge-v1 verdicts. Exact matches are reported as a fraction of evaluable pairs, with the number of the 12 that were evaluable.
6. **Counting observations.**
   - Separate yes/no fields wherever a case asks two things, kept apart from the overall accept/reject label.
   - The one-focused-question rule applies wherever a case calls for a follow-up.
   - The fields are fixed in the pre-registration, after the cases are written.

**Checklist**

| # | Item | Owner | Status |
|---|---|---|---|
| 1 | Blank case template for Nishanth | lead | Verified (sent 2026-11-21) |
| 2 | Offline holdout tooling: pair plan with salted commitment, combined review sheet, pair sheet, commitment verification, automated A/B/tie and agreement, all tested with fixtures | complex-coder | Verified. Six commands in `src/rightoncue/holdout.py`; 353 tests |
| 3 | Independent verification of item 2 | verifier | Verified. The first Opus pass FAILED: B1, a pre-reveal error that leaked a pair's side by inference; B2, a pair sheet not tied to its run; N1–N8. All were fixed. The second pass gave PASS: 28 mutations, all relevant ones killed. Open, non-blocking: N-new-1 (label IDs not matched to the committed neutral IDs) and N-new-2 (`pair-sheet --out` allowed in the private folder), to be fixed with D1. Owner decision pending, D1: how empty or failed replies are handled (currently refused). The delimiter look-alike refusal is decided with it |
| 4 | H1–H4 transcripts and criteria | Nishanth | Verified. Committed in `b6166cf`: all four parse, the notes load, and D1–D4 are unchanged |
| 5 | Format checks (parse, notes load, offline suite), pre-registration and pair-plan commitment, committed before generation | lead | Verified. 353 tests pass. Pre-registration in `docs/measurements/2026-11-21-holdout-preregistration.md`; pair-plan commitment `holdout/pair_plan_commitment.json` (sha256 `42e945ab…ec19`, verified). Still open before the go-ahead: D1, the cost-cap option, and fixes N-new-1 and N-new-2 |
| 6 | Generation, v2 and v1 runs (only on Nishanth's go-ahead) | lead | Pending |
| 7 | Labels: 48 individual, then 12 pairs | Nishanth | Pending |
| 8 | Scoring, reveal and verification, report | lead | Pending |

**Risks.**
- **Blinding depends on discipline.** The committed run folders (`slots.jsonl`) and the private mapping files hold the identities, so they must not be opened before the labels are committed.
- **The cost cap holds only between commands.** Generation sends no output cap, so a single generation call has no hard ceiling.
