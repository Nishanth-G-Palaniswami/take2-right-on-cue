# Right on Cue

A next-turn evaluation tool for Take2's Forward Deployed Engineer take-home. Given a call prompt and a partial screening-call transcript, it asks a model for the recruiter's next line several times and saves every reply verbatim, so the replies can be compared and judged.

Status: milestone 2, part 1. One or more models per run (OpenAI models such as `gpt-5.4-mini` through the Responses API, Google Gemini models such as `gemini-3.5-flash` through the `google-genai` SDK), raw generation, and a blind review view for human preferences. There is no scoring yet, and failed replies can't be retried yet.

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

## Layout

- `prompts/`: call prompts. `v1.md` is the starter prompt and is never edited. `v2.md` is the working prompt: v1 with one line changed (see `docs/measurements/2026-11-20-v2-d1-d4.md`).
- `docs/measurements/`: each prompt experiment, with counting rules committed before its replies were generated, then the results.
- `cases/dev/`: partial transcripts in JSON Lines, one `{"role": "agent"|"user", "utterance": ...}` per line, ending on a user turn.
- `cases/notes.toml`: the expected next move for each case, written before any replies were generated. The generator never reads it.
- `runs/`: saved runs.
- `docs/time-log.md`: hours against the 4 to 6 hour timebox.

## Tests

```powershell
uv run pytest
```
