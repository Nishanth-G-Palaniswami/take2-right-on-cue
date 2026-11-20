# Right on Cue

A next-turn evaluation tool for Take2's Forward Deployed Engineer take-home. Given a call prompt and a partial screening-call transcript, it asks a model for the recruiter's next line several times and saves every reply verbatim, so the replies can be compared and judged.

Status: milestone 1.1. One model (`gpt-5.4-mini` through the OpenAI Responses API), raw generation, and a blind review view for human preferences. There is no scoring yet.

## Setup

Requires [uv](https://docs.astral.sh/uv/) and Python 3.12+.

```powershell
uv sync
Copy-Item .env.example .env   # then put your OpenAI key in .env
```

## Run one next-turn experiment

```powershell
uv run next-turn run --prompt prompts/v1.md --case cases/dev/D3.jsonl --case cases/dev/D4.jsonl --model gpt-5.4-mini --samples 2 --reasoning-effort none
uv run next-turn show runs/<run_id>
```

`run` validates every input before calling the API. It then makes one independent request per sample and writes `runs/<run_id>/`:

- `manifest.json`: the exact prompt text, transcripts, request payloads, SHA-256 hashes, model, settings, SDK version and git commit.
- `slots.jsonl`: one line per reply, written as each reply arrives. It holds the verbatim output, the model the API reports, token usage, timings and the full raw response. Failed and incomplete responses are recorded too.

`run` ends with a summary of completed, incomplete and failed replies, plus a note if a completed reply had no text. It exits nonzero if any reply failed or came back incomplete.

## Review replies blind

`show` opens a run for blind review. It refuses to start until every expected reply has been attempted: it prints a line such as `D3: 1 of 2 samples recorded`, writes nothing, and exits 2.

For each case the reviewer sees:

- Riley's previous turn (or a note that Riley hasn't spoken yet), then the applicant's last turn.
- The eligible replies under the letters A, B, ... in random order. A reply is eligible only if the API completed it and it contains text. Incomplete, failed and empty replies are counted on separate lines and are not shown.
- A note when only one reply is eligible (no pairwise preference is possible) or when none is.

The view never shows model names, sample numbers, scores or the expected-behaviour notes.

The first `show` freezes the letters in `blind_key.json`, tying each letter to a SHA-256 fingerprint of the exact words shown. It also creates `blind_sheet.md`, where you record a preference, the words that tipped it, a reason, and accept or reject for each reply. Later `show` calls never rewrite either file: the sheet stays byte for byte as you left it.

If the saved replies change after the freeze, the view flags it and exits 1. This covers a new eligible reply, or another record under a letter you already reviewed. The original words stay under their letter. If a letter's original words can't be found, nothing is shown under it.

Runs reviewed before fingerprints existed, such as `runs/20261120T225013Z-70fb30`, still open, with a note that their words can't be fingerprint-checked. A letter's words are shown only if every saved record for that reply has the same text. If that older review had already given a letter to an incomplete or empty reply, those words stay under the letter and are flagged.

If two `show` commands open a new run at the same moment, one of them stops with "run show again" and changes nothing. An empty or unreadable `blind_key.json` is reported, never overwritten.

## Layout

- `prompts/`: call prompts. `v1.md` is the starter prompt and is never edited.
- `cases/dev/`: partial transcripts in JSON Lines, one `{"role": "agent"|"user", "utterance": ...}` per line, ending on a user turn.
- `cases/notes.toml`: the expected next move for each case, written before any replies were generated. The generator never reads it.
- `runs/`: saved runs.
- `docs/time-log.md`: hours against the 4 to 6 hour timebox.

## Tests

```powershell
uv run pytest
```
