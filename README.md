# Right on Cue

A next-turn evaluation tool for Take2's Forward Deployed Engineer take-home. Given a call prompt and a partial screening-call transcript, it asks a model for the recruiter's next line several times and saves every reply verbatim, so the replies can be compared and judged.

Status: milestone 3. One or more models per run (OpenAI models such as `gpt-5.4-mini` through the Responses API, Google Gemini models such as `gemini-3.5-flash` through the `google-genai` SDK), raw generation, a blind review view for human preferences, and a scorer for saved replies (code checks, a fixed `gpt-5.4-mini` judge, and a pass/fail decision made in code). Failed generations can't be retried yet.

## Setup

Requires [uv](https://docs.astral.sh/uv/) and Python 3.12+.

```powershell
uv sync
Copy-Item .env.example .env   # then put your OpenAI and/or Gemini key in .env
```

## Run one next-turn experiment

```powershell
uv run next-turn run --prompt prompts/v1.md --case cases/dev/D3.jsonl --case cases/dev/D4.jsonl --model gpt-5.4-mini --samples 2 --reasoning-effort none
uv run next-turn show runs/<run_id>
```

To compare models in one run, repeat `--model`:

```powershell
uv run next-turn run --prompt prompts/v2.md --case cases/dev/D3.jsonl --model gpt-5.4-mini --model gemini-3.5-flash --samples 2 --reasoning-effort none --gemini-thinking-level minimal
```

- The provider comes from the model ID: `gpt-...` is OpenAI, `gemini-...` is Gemini. Any other ID, or the same model twice, is an input error. After the prefix, an ID may contain only letters, digits, `.`, `-` and `_` (no spaces).
- Models × samples can be at most 26 per case, so every reply gets a blind letter A–Z.
- `--reasoning-effort` applies to OpenAI models (default `none`).
- `--gemini-thinking-level` applies to Gemini models: `minimal`, `low`, `medium`, `high` or `xhigh`. It is required whenever a Gemini model is selected; there is no default.
- `OPENAI_API_KEY` is needed only for OpenAI models and `GEMINI_API_KEY` only for Gemini models.
- Replies are generated case by case, then model by model in the order given, then sample by sample.

`run` validates every input and checks the needed keys before calling any API. It then makes one independent request per sample and writes `runs/<run_id>/`:

- `manifest.json`: the exact prompt text, transcripts, the request payload for every model and case, SHA-256 hashes, each model with its provider, settings and client retry settings, SDK versions and git commit.
- `slots.jsonl`: one line per reply, written as each reply arrives. It holds the provider, the model's settings (reasoning effort or thinking level), the requested model, the model the API reports (or "served version unconfirmed" when the API doesn't say), the verbatim output, token usage (raw and normalized to input, output and reasoning tokens), timings and the full raw response. Failed and incomplete responses are recorded too.

`run` ends with a summary for each model: the requested model, the model(s) the API reported, completed, incomplete and failed replies, a note if a completed reply had no text, and token totals. It exits nonzero if any reply failed or came back incomplete. An invalid key, model name or setting (HTTP 400, 401, 403 or 404) stops the whole run.

## Review replies blind

`show` opens a run for blind review. It refuses to start until every expected reply has been attempted: it prints a line such as `D3: 1 of 2 samples recorded`, writes nothing, and exits 2.

For each case the reviewer sees:

- Riley's previous turn (or a note that Riley hasn't spoken yet), then the applicant's last turn.
- The eligible replies under the letters A, B, ... in random order, with every model's replies for the case shuffled together. A reply is eligible only if the API completed it and it contains text. Incomplete, failed and empty replies are counted on separate lines and are not shown.
- A note when only one reply is eligible (no pairwise preference is possible) or when none is.

The view never shows model names, providers, sample numbers, scores or the expected-behaviour notes.

The first `show` freezes the letters in `blind_key.json`, tying each letter to a SHA-256 fingerprint of the exact words shown. It also creates `blind_sheet.md`, where you record a preference, the words that tipped it, a reason, and accept or reject for each reply. Later `show` calls never rewrite either file: the sheet stays byte for byte as you left it.

If the saved replies change after the freeze, the view flags it and exits 1. This covers a new eligible reply, or another record under a letter you already reviewed. The original words stay under their letter. If a letter's original words can't be found, nothing is shown under it.

Runs reviewed before fingerprints existed, such as `runs/20261120T225013Z-70fb30`, still open, with a note that their words can't be fingerprint-checked. A letter's words are shown only if every saved record for that reply has the same text. If that older review had already given a letter to an incomplete or empty reply, those words stay under the letter and are flagged.

If two `show` commands open a new run at the same moment, one of them stops with "run show again" and changes nothing. An empty or unreadable `blind_key.json` is reported, never overwritten.

## Score replies

```powershell
uv run next-turn score runs/<run_id>
```

`score` scores the exact replies already saved in a run. Only replies with status `ok` are eligible.

**Checked by code.**
- The single-turn requirement. A reply fails if it is empty, or if it contains both sides of the conversation. A speaker label is a role word or a single capitalised word followed by `:`, at the start of the reply, the start of a line, or right after a sentence ends. The reply fails in any of these cases (the failure names the rule):
  - R1: an applicant-side label such as `Applicant:` or `Nurse:`;
  - R2: two or more labels starting the reply or a line;
  - R3: a label at the start followed by any other label;
  - R4: a label starting any line after the first.

  A single label at the very start is flagged as `markup` only.
- Diagnostic flags that never change the decision: `long_reply` (over 40 words), `multiple_question_marks`, `no_question_mark`, and `markup`.

**Scored by the judge.** A fixed `gpt-5.4-mini` judge (reasoning effort `none`, strict JSON output) scores next action, listening, grounding and delivery from 0 to 2, and lists critical violations.
- By default its instructions are `prompts/judge.md` (`judge-v1`). Each judge prompt version's file SHA-256 is pinned in code. A changed file is refused; changed text needs a new version.
- It receives only three things:
  - the case's `expected_action`, `good_if` and `fail_if` from `cases/notes.toml`, or a "general rubric" note for a case with no notes;
  - the transcript, labelled Riley and Applicant;
  - the reply.
- It never sees model names, the run, the sample or the prompt version.
- Every quote the judge gives must appear in the reply or in a single transcript turn. Only typographic quotes, dashes and whitespace are normalised before matching.
- Otherwise the reply is marked `needs review` and gets no decision.

**Judge versions.** `--judge-version` picks the judge prompt: `judge-v1` (`prompts/judge.md`, the default and the frozen baseline), or `judge-v2a` or `judge-v2b` (`prompts/judge-v2a.md`, `prompts/judge-v2b.md`), which are candidate versions that were evaluated and not adopted (see `docs/measurements/2026-11-21-judge-diagnostic.md`), or `judge-v3` (`prompts/judge-v3.md`), a candidate scored under `scorer-2` that is not adopted. judge-v1 stays the default. Under `scorer-2` the judge gives exactly one critical-violation entry per type, each marked present true or false; only present entries count as violations, and a present entry needs evidence. `score` prints the version it used. Scores for different versions sit side by side in the same `scores/<run_id>.jsonl`, each record marked with its version. A score is never reused across versions, so the first run of a new version makes a judge call for every non-empty reply.

**Decision rule.** Code decides, with the same rule for every model. A reply is acceptable only if all of these hold:
- the single-turn check passes;
- next action is 2;
- grounding is 2;
- listening is at least 1;
- delivery is at least 1;
- there is no critical violation.

The total out of 8 is shown but never overrides the rule. An empty completed reply gets no judge call and is not acceptable.

**Storage.** Scores go to `scores/<run_id>.jsonl` (`--scores-dir` to change it), one line per scoring attempt.
- Each line holds the judge's verbatim output and the full judge response.
- Nothing inside `runs/` is written. A `--scores-dir` inside a run folder or inside a directory that holds run folders (such as `runs/` or `runs/new`) is refused. A run folder is one whose `manifest.json` is a JSON object with `run_id` and `samples_per_case`, so another project's `manifest.json` doesn't count.
- The blind key, the blind sheet and label notes are never read.

**Reuse and retry.** A score is reused when the slot, the SHA-256 of the reply text, the scorer version, the judge prompt version and the SHA-256 of the exact judge request all match.
- A second `score` therefore makes no judge calls.
- Replies marked `needs review` or `judge failed` are judged again on the next `score`, and earlier lines are kept.
- Incomplete, failed, missing and empty replies are counted separately.
- A slot with more than one saved record is reported and not scored.

**Output.** For each reply, `score` prints:
- the case, the requested and reported model, the sample and the verbatim reply;
- the decision with its reasons;
- the four scores and the total;
- the judge's rationale and evidence, the checks, and whether the score was new or reused.

It ends with a summary per model and the judge calls and tokens used.

**Score after blind review.** The output names models and shows scores, so record and commit your blind labels for a run before you score it.

**API key and exit codes.**
- `OPENAI_API_KEY` is needed only when at least one judge call is needed. A fully reused run needs no key.
- An invalid key, model or request (HTTP 400, 401, 403 or 404) stops scoring.
- `score` exits 0 when every eligible reply has a valid score. It exits 1 if any reply needs review, a judge call failed, a slot has duplicate records, a saved record matches no expected slot, or scoring stopped. It exits 2 for input or configuration errors, and then no call is made.

## Layout

- `prompts/`: call prompts. `v1.md` is the starter prompt and is never edited. `v2.md` is the working prompt: v1 with one line changed (see `docs/measurements/2026-11-20-v2-d1-d4.md`).
- `prompts/judge.md`: the judge's instructions (`judge-v1`), pinned by SHA-256 in `src/rightoncue/scoring.py`.
- `docs/measurements/`: each prompt experiment, with counting rules committed before its replies were generated, then the results.
- `cases/dev/`: partial transcripts in JSON Lines, one `{"role": "agent"|"user", "utterance": ...}` per line, ending on a user turn.
- `cases/notes.toml`: the expected next move for each case, written before any replies were generated. The generator never reads it.
- `runs/`: saved runs.
- `scores/`: judge scores, one `<run_id>.jsonl` per scored run, kept apart from the runs.
- `docs/time-log.md`: hours against the 4 to 6 hour timebox.

## Tests

```powershell
uv run pytest
```
