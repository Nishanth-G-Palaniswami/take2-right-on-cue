# Right on Cue

A next-turn evaluation tool for Take2's Forward Deployed Engineer take-home. Given a call prompt and a partial screening-call transcript, it asks a model for the recruiter's next line several times and saves every reply verbatim, so the replies can be compared and judged.

**For reviewers:**
- **Hosted app:** <https://rightoncue.nishanthgp.me>. It opens on the saved three-model comparison (holdout H3, prompt v2). "Run it yourself" needs the access code from Nishanth and defaults to the recommended setup, GPT-5.4 with prompt v3.
- **Report:** [`docs/report.md`](docs/report.md). It covers the method, the model comparison, both prompt iterations and the recommendation.
- **Video walkthrough:** _link to be added before submission._

Status: milestone 3. One or more models per run (OpenAI models such as `gpt-5.4-mini` through the Responses API, Google Gemini models such as `gemini-3.5-flash` through the `google-genai` SDK), raw generation, a blind review view for human preferences, and a scorer for saved replies (code checks, a fixed `gpt-5.4-mini` judge, and a pass/fail decision made in code). Failed generations can't be retried yet.

## Setup

Requires [uv](https://docs.astral.sh/uv/) and Python 3.12+.

```powershell
uv sync
Copy-Item .env.example .env   # then put your OpenAI and/or Gemini key in .env
```

## App

```powershell
uv sync
uv run streamlit run app.py
```

The app opens on `http://localhost:8501` (use `--server.port` to change it). It serves from the domain root and also works under `--server.baseUrlPath`.

**Without any key (the default, hosted-replay view).** It opens on the saved three-model comparison of holdout case H3 (prompt v2, sample 1). The case, prompt version (v1 or v2) and sample are kept in the URL, for example `?case=H3&prompt=v2&sample=1`. For each model it shows the verbatim reply, the raw judge-v1 verdict, the human reviewer's accept or reject label and, on demand, the four scores, the failed checks and the judge's reasoning. A generation that failed is shown as an operational failure, never as a reply. The "How it was evaluated" tab holds the method, the headline results with a plain-language explanation beside each, what I would change next, the experiment history and the committed documents. Everything is read from the committed `runs/`, `scores/` and `holdout/` files; nothing is written.

**With your own keys (the "Run it yourself" tab).** You can pick or paste a prompt and a transcript, choose models, samples (1 to 5), OpenAI reasoning effort and Gemini thinking level, generate replies, then score them with judge-v1. Put `OPENAI_API_KEY` and/or `GEMINI_API_KEY` in the environment or in `.env`; the app shows only whether each key is present. **Generation and scoring cost money.** The app shows the number of calls and asks for a confirmation checkbox before each. A model whose key is missing can't be generated.

In this plain local mode (no `RIGHTONCUE_BUDGET_USD`, no `RIGHTONCUE_DRY_RUN`), new runs are written to `runs/<run_id>/` and scores to `scores/<run_id>.jsonl`, exactly as the command line does. A pasted prompt or transcript is recorded as `pasted/prompt.md` or `pasted/transcript.jsonl`.

**Local mode with a spending cap.** Set `RIGHTONCUE_BUDGET_USD` locally and every generation and judge call goes through the spending ledger described below: replies are capped at 400 output tokens, clients make no hidden retries, and the projected maximum is shown before generating. Runs and scores then go to `<RIGHTONCUE_DATA_DIR>/runs/` and `<RIGHTONCUE_DATA_DIR>/scores/` (default: the git-ignored `data/`), never to the committed `runs/` and `scores/`. The same applies to a local dry run, which needs the budget too. Without a budget or dry run, local mode is exactly as above.

| Mode | Fresh runs | Scores | Ledger |
|---|---|---|---|
| Local, no budget, no dry run | `runs/` | `scores/` | none |
| Local with a budget | `<data>/runs/` | `<data>/scores/` | `<data>/ledger.jsonl` |
| Local dry run (needs a budget) | `<data>/runs/` | `<data>/scores/` | `<data>/ledger.dry-run.jsonl` |
| Hosted (live mode on) | `<data>/runs/` | `<data>/scores/` | `ledger.jsonl`, or `ledger.dry-run.jsonl` in dry run |

`<data>` is `RIGHTONCUE_DATA_DIR`. Locally it defaults to `data/`; hosted mode requires it.

**Hosted mode.** `RIGHTONCUE_HOSTED=1` serves the saved comparison to everyone. "Run it yourself" stays off (with a generic message; the reason goes to the server log) unless the host also sets the access code, the budget, the data directory and both keys. Then a reviewer enters the access code, starts from GPT-5.4 with `prompts/v3.md` (the recommended setup and the default; `v1.md` and `v2.md` stay selectable, and the saved comparison still opens on the v2 holdout run) and a case file (both editable in place), picks models and samples, and clicks "Generate and score". Fresh replies are scored by judge-v1. A reply whose judgment comes back invalid (`needs_review`, for example a quote that fails the unchanged quote check) or failed (`judge_failed`) gets one judge-only retry with the exact saved reply. A valid verdict, acceptable or not, is final. Both attempts stay in the score file. The maximum shown before Generate counts the retry, and the cap is checked before each call. If the retry also fails, the card reads "Needs review · no valid score". The replies are shown as side-by-side cards labelled "Fresh run: generated just now, not part of the saved evaluation", with the run ID. The saved comparison is labelled "Saved example". The settings are fixed on the hosted site: OpenAI reasoning effort `none` and Gemini thinking `MINIMAL` (the measured settings), and each reply is capped at 400 output tokens. A reply that reaches the cap is shown as an incomplete operational failure. Provider error text is never shown on the public page; only the error type and HTTP status are.

| Variable | Meaning |
|---|---|
| `RIGHTONCUE_HOSTED` | `1` hosted, `0` or unset local. Any other value is an error, and live mode stays off. |
| `RIGHTONCUE_ACCESS_CODE` | The code reviewers enter. Server-side only: never shown, logged or stored in a session, and compared in constant time. Failed attempts are counted process-wide: after 5 wrong codes, nobody can try for 60 seconds. |
| `RIGHTONCUE_BUDGET_USD` | The shared cap in USD across all reviewers' generation and judging, retries included (for example `5.00`). Required for hosted live runs; there is no default. Must be a positive number. |
| `RIGHTONCUE_DATA_DIR` | Where fresh runs (`runs/`), their scores (`scores/`) and the ledger live. Required in hosted mode; locally the default is the git-ignored `data/`. It may not be the repository or inside the committed `runs/` or `scores/`. |
| `RIGHTONCUE_MAX_SAMPLES` | Most samples per model in a hosted run, from 1 to 5. Default 2. |
| `OPENAI_API_KEY`, `GEMINI_API_KEY` | Both required for hosted live runs. Read from the server environment only. |
| `RIGHTONCUE_DRY_RUN` | `1` replaces every provider client with offline fakes: placeholder replies and schema-valid placeholder judge-v1 judgments, with no network and no key. A banner on every page says "Dry run: no API calls or charges. Replies are placeholders and are not scored." In the live tab the button reads "Simulate run", the paid-call acknowledgment is replaced by "No API calls or charges", the result is labelled "Simulated run", and each card reads "Simulated reply · Unscored". The placeholder judgments count toward the simulated spend but are never shown as verdicts or scores. The fakes go through the same guards with realistic token usage, so reservations and settlements are real amounts. They are written to `ledger.dry-run.jsonl`, never to the real ledger, and labelled "simulated". It needs `RIGHTONCUE_BUDGET_USD`. Never set it in the image or on the host. |
| `RIGHTONCUE_DRY_RUN_DELAY_S` | Test hook, honoured only in dry run: each fake call sleeps this many seconds (0–600), so a container can be killed in the middle of a call. |

**The cap has two layers.**
1. **The in-app ledger**, `<RIGHTONCUE_DATA_DIR>/ledger.jsonl`. This is an append-only JSONL file, fsynced on every line.
   - **Reservation.** Before every paid call, under a process-wide lock, the call's maximum cost is computed:
     - input: the UTF-8 byte length of the request's canonical JSON times the input price;
     - output: the 400-token cap (1500 for the judge) times the output price.

     A `reserve` entry is appended only if the spend so far plus that maximum is within the budget. Otherwise the call is refused before any request.
   - **Settlement.** After the call, a `settle` entry records the actual cost from the response's usage. It records the maximum when usage is missing or the call raised.
   - **Spend.** Spend is the settled costs plus the maximum of every reservation without a settle entry, so a crash or kill mid-call counts the maximum, never $0.
   - **Integrity.** A torn final line from a crash is ignored safely. Any other malformed line disables live runs with an explicit error.
   - **Prices.** OpenAI prices are the PRD rates in `budget.py`. `gemini-3.5-flash` is reserved and settled at $1.50/M input and $7.50/M output, Google's 2027 paid-tier rate for `gemini-3.6-flash`, the model every saved Gemini reply reports. Output includes thinking tokens. Any other model is refused.
   - **Up-front checks.** A run's projected maximum is shown before it starts, and the run is refused if the projection exceeds the remaining budget. One paid run runs at a time per process; a second reviewer is asked to try again shortly.
   - **One process only.** The lock is in-process, so do not point two app processes at the same ledger.
2. **Provider-side hard limit:** a dedicated OpenAI project with "Enforce a hard limit" on, as the backstop to the app's own accounting. The Gemini side's provider limit is not decided yet. `plan.md` assumes a key with no billing (free tier, $0), but the ledger prices Gemini as paid.

**The ledger persists only on persistent storage.** Point `RIGHTONCUE_DATA_DIR` at a persistent disk (on Render, a disk mounted at for example `/var/data`; disks need a paid instance). On ephemeral storage, such as a free instance, the ledger, and with it the spend so far, resets on every restart or deploy.

**No hidden retries.** Budgeted clients are built with `max_retries=0` (OpenAI) and one attempt (Gemini `HttpRetryOptions(attempts=1)`; `gemini.RETRY_OPTIONS` otherwise allows 3). Gemini's automatic continuation is turned off in capped requests, because each continuation hop is a separately billed request. The cap, the continuation setting and the retry settings are recorded in the run's manifest and requests. CLI runs and the saved runs are unchanged.

The theme and the minimal toolbar are in `.streamlit/config.toml`.

**Hosted replay in a container.** `docker build -t rightoncue:local .` then `docker run -p 127.0.0.1:3001:10000 -e PORT=10000 rightoncue:local` serves the no-key replay at `http://127.0.0.1:3001/` (the image sets `RIGHTONCUE_HOSTED=1` and excludes `.env` and `holdout-private/`). The deployment plan for `https://rightoncue.nishanthgp.me` is in `docs/hosting-plan.md`.

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

**Judge versions.** `--judge-version` picks the judge prompt: `judge-v1` (`prompts/judge.md`, the default and the frozen baseline), or `judge-v2a` or `judge-v2b` (`prompts/judge-v2a.md`, `prompts/judge-v2b.md`), which are candidate versions that were evaluated and not adopted (see `docs/measurements/2026-11-21-judge-diagnostic.md`), or `judge-v3` (`prompts/judge-v3.md`), a candidate scored under `scorer-2` that was evaluated and not adopted. judge-v1 stays the default and is frozen for the model comparison. `judge-v4` (`prompts/judge-v4.md`, `scorer-2`) is experimental and not adopted: judge-v3 plus targeted next-action and consent wording. It missed one pre-registered criterion, the D1 regression (`docs/measurements/2026-11-21-judge-v4-plan.md`). Its known limits and reporting rules are in `docs/judge-v1-known-limits.md`. Under `scorer-2` the judge gives exactly one critical-violation entry per type, each marked present true or false; only present entries count as violations, and a present entry needs evidence. `score` prints the version it used. Scores for different versions sit side by side in the same `scores/<run_id>.jsonl`, each record marked with its version. A score is never reused across versions, so the first run of a new version makes a judge call for every non-empty reply.

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
- `score` exits 0 when every eligible reply has a valid score. It exits 1 if any reply needs review, a judge call failed, a reply was stopped by the budget guard, a slot has duplicate records, a saved record matches no expected slot, or scoring stopped. It exits 2 for input or configuration errors, and then no call is made.

**Budget guard (optional).** `uv run next-turn score runs/<run_id> --budget-usd 0.40 --budget-run runs/<v2 run> --budget-run runs/<v1 run>`. Without `--budget-usd`, `score` behaves exactly as before.
- **Spend so far** is computed from recorded usage only, at fixed PRD rates in USD per million input/output tokens: `gpt-5.4` 2.50/15.00 and `gpt-5.4-mini` 0.75/4.50. It covers generation in every `--budget-run` (priced by the requested model) plus every judge call with a response in those runs' score files, across all judge versions, at Mini rates. Output tokens already include reasoning tokens, so reasoning is counted once.
- **Gemini generation is priced at $0**, because it is not billed by OpenAI.
- **Charges persist.** Every judge attempt made under a budget records `budget_charged_nano`: its actual usage cost, or its maximum when usage is missing (for example when the call raised). Spend so far uses that field when present, so a failed call keeps its maximum in later commands.
- **Write-ahead charges.** Before each budgeted judge call, `score` appends and fsyncs a `judge_pending` record with a fresh `attempt_id` and the call's maximum as its charge. After the call, the final record (`scored`, `needs_review` or `judge_failed`) carries the same `attempt_id` and the actual charge. An exception the scorer doesn't recognise still gets a final `judge_failed` record charged the maximum, then propagates. Spend counts one charge per `attempt_id`: the final record's, or the pending maximum if the process crashed or was killed before the final record was written. So a possibly billed attempt is never counted as free on restart.
- **Interrupted attempts.** A pending record is never reused and is not a score. A reply whose latest attempt has only a pending record needs a judge call on the next `score`; under the one-retry rule that call is its retry. `score` prints "Interrupted attempts: N", and the holdout compare tools report such a reply as "unscored (attempt interrupted)". Without `--budget-usd` no pending record is written.
- **Older records without that field** count their recorded usage. One whose call raised and returned no response has no usage and is counted at $0; `score` prints how many per run. A record with a response but no usage is refused (exit 2), naming the run.
- **No hidden retries.** Under a budget the judge client is built with `max_retries=0`, so the OpenAI SDK makes exactly one HTTP request per guarded call. A transient error (timeout, rate limit, 5xx) becomes `judge_failed`, and the one guarded rerun of `score` is its retry. Without `--budget-usd` the client keeps the SDK's default retries, as before.
- **The guard.** Before each judge call, retries included, it computes the call's maximum cost: the UTF-8 byte length of the canonical JSON of the exact request times the input price, plus `max_output_tokens` (1500) times the output price. This assumes every input token covers at least one byte of that text. If the spend so far plus that maximum would exceed the budget, no call is made: that reply and every remaining reply that needs a judge call is recorded as `budget_stopped`, with the numbers, and no further call is made in that command. After each call its actual usage cost is added, or its maximum if usage is missing.
- **`budget_stopped`** records are never reused, are reported as "unscored (budget)", and make `score` exit 1. Empty replies still need no call.
- **The runs must include the run being scored.** Money is kept in integer nano-dollars.
- **Generation has no cap.** `run` sends no output limit, so a generation call has no hard cost ceiling; the guard covers judge calls only.

## Holdout blind review

Offline tooling for the H1–H4 holdout (see `plan.md`, "Holdout evaluation"). No command calls an API. Every file is created once (write-once, LF, UTF-8 without BOM) and never rewritten; a command whose target exists refuses and changes nothing. No file is written inside a run folder or a directory of runs, and a `--json-out` report is refused inside `--scores-dir`. Before reveal, commands print only paths, counts and commitment hashes.

Order of use:

1. **Before generation:** `uv run next-turn pair-plan --case H1 --case H2 --case H3 --case H4 --model gpt-5.4 --model gpt-5.4-mini --model gemini-3.5-flash --prompt-version v2 --private-out <private plan> --commitment-out <commitment>`. It fixes the 12 v2 pairs (per case: M1 s1 vs M2 s1, M1 s2 vs M3 s1, M2 s2 vs M3 s2; each pairing's first model on the left in half the cases, drawn from OS randomness).
   - The private plan holds the salt and the mapping.
   - The commitment holds only the salted SHA-256, the formula, the models, the cases and the pair rule. Commit the commitment. The private plan may not sit in the same folder as the commitment.
2. **After both runs are generated:** `uv run next-turn review-sheet --run <v1 run> --run <v2 run> --out <dir> --private-key <private key>`. Both runs must have the same cases and transcripts. A failed or incomplete generation is an operational failure: it is left off the sheet and counted by kind, with no model. A missing slot (never attempted), a duplicate record for one slot, an unknown status, or a record matching no expected slot is refused.
   - `<dir>/review_sheet.md` shows every other reply (12 per case when nothing failed) under neutral IDs (`H1-01` …), with no model, run, prompt or sample. Each reply line starts with `> `; a completed reply with no text shows as a bare `(empty reply)` line and is labelled like any other. Identical words from different slots each get their own ID. Write `y` or `n` on each `Accept <ID>? (y/n):` line.
   - The private key maps each neutral ID to its run, slot, prompt version, model, sample and text SHA-256, lists the unavailable slots (run, slot, kind), and holds the salt. It is refused inside `--out`.
   - `<dir>/review_key_commitment.json` holds the salted hash (over the entries and the unavailable list), run IDs, case IDs, the reply count, the list of shown neutral IDs (`ids`) and the unavailable counts by kind, and no mapping.
3. **After the review labels are committed:** `uv run next-turn pair-sheet --plan-private <private plan> --commitment <commitment> --run <v2 run> --out <dir> --review-sheet <dir>/review_sheet.md --review-commitment <dir>/review_key_commitment.json`. It verifies the plan against its commitment and the published pair rule, and checks the run's prompt version, models and cases. It refuses unless the review sheet carries the review commitment's hash, the review commitment covers the run, the sheet's Accept IDs are exactly the commitment's `ids` (each once, none missing, none extra), and every value is exactly `y` or `n`. It also refuses an `--out` inside the folder that holds the private plan, or below it. A pair with a failed or incomplete reply is left off the sheet; the sheet and the output state only how many pairs cannot be shown (their IDs appear as gaps). Pairs with an empty reply are shown. A missing or duplicate slot is refused with counts only. `<dir>/pair_sheet.md` shows each pair's replies between `<<<<<<<< A >>>>>>>>` and `<<<<<<<< B >>>>>>>>` delimiters, with no model or sample, and a `Fingerprint:` line that ties the pair to the run's raw words. Write `A`, `B` or `tie` on the Choice line and a reason after `Reason:`; leave the delimiters and fingerprints unchanged.
4. **After the pair choices are committed (reveal):**
   - `uv run next-turn verify-commitment --private <private file> --commitment <commitment>` checks a plan or a key against its commitment (exit 0 verified, 1 not).
   - `uv run next-turn pair-compare --plan <private plan> --commitment <commitment> --run <v2 run> --pair-sheet <pair sheet> [--json-out <path>]` compares the human A/B/tie with the raw judge-v1 verdicts, ranked by (clean, acceptable, total, where an empty reply's total is -1). It reports evaluable pairs N of 12 and each missing pair's reasons: operational failure (reply unavailable), unscored (invalid or failed judgment), unscored (budget), unscored (attempt interrupted), unscored (no judge record), or human blank.
   - `uv run next-turn review-compare --key <private key> --commitment <review commitment> --sheet <review sheet> [--json-out <path>]` reports, per prompt and model and per case: shown replies, human accepted, judge acceptable, unscored with the reason, operational failures (not shown), evaluable replies (shown and scored) and agreement among the evaluable.

Both sheets carry their commitment hash, so the compare commands refuse a sheet made for a different plan or key. `pair-compare` also refuses a pair sheet whose fingerprints don't match the run's replies, or whose choices are all blank. It reports each pair's reason and how many chosen pairs have none. Both compare commands count a judge score only if it was made for the same words (the reply's text SHA-256), and treat a `budget_stopped` record as unscored for budget. Reply text is preserved exactly: because every reply line is prefixed with `> `, no reply line can pose as a delimiter, header or answer line, and fingerprints and SHA-256s are taken from the raw text.

**Do not open the private plan or the private review key, or the run folders, before the labels they would reveal are committed.** Write the private files to `holdout-private/` (git-ignored), never to the review directory you open, and commit them only at reveal.

## Layout

- `prompts/`: call prompts. `v1.md` is the starter prompt and is never edited. `v2.md` is the working prompt: v1 with one line changed (see `docs/measurements/2026-11-20-v2-d1-d4.md`).
- `prompts/judge.md`: the judge's instructions (`judge-v1`), pinned by SHA-256 in `src/rightoncue/scoring.py`.
- `docs/measurements/`: each prompt experiment, with counting rules committed before its replies were generated, then the results.
- `cases/dev/`: partial transcripts in JSON Lines, one `{"role": "agent"|"user", "utterance": ...}` per line, ending on a user turn.
- `cases/notes.toml`: the expected next move for each case, written before any replies were generated. The generator never reads it.
- `app.py`: the Streamlit app; `src/rightoncue/review.py` loads and joins runs, scores and the holdout human review for it.
- `runs/`: saved runs.
- `scores/`: judge scores, one `<run_id>.jsonl` per scored run, kept apart from the runs.
- `docs/time-log.md`: hours against the 4 to 6 hour timebox.

## Tests

```powershell
uv run pytest
```
