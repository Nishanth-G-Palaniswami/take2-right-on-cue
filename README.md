# Right on Cue

A next-turn evaluation tool for Take2's Forward Deployed Engineer take-home. Given a call prompt and a partial screening-call transcript, it asks a model for the recruiter's next line several times and saves every reply verbatim, so the replies can be compared and judged.

Status: milestone 1. One model (`gpt-5.4-mini` through the OpenAI Responses API), raw generation, and a blind A/B view for human preferences. There is no scoring yet.

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
- `slots.jsonl`: one line per reply, written as each reply arrives. It holds the verbatim output, the model the API reports, token usage, timings and the full raw response.

`show` prints the applicant's last line and the replies for each case as A, B, ... in a random order, with no model or sample information. It also writes `blind_sheet.md` for recording a preference and the reason. The label mapping lives in `blind_key.json`.

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
