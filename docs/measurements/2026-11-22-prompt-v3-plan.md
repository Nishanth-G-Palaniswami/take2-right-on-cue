# Prompt v3: a behavioral follow-up experiment (pre-registered 2026-11-22)

**Status: frozen before any generation.** This is a separate experiment.
- Riley's app default stays **v2** pending the comparison.
- The published holdout results (31 of 47, 2 of 12), the judge (judge-v1), `cases/notes.toml` and the saved runs are unchanged.

## The one change

`prompts/v3.md` is `prompts/v2.md` with line 25, the behavioral follow-up instruction, replaced. Nothing else differs (`git diff --no-index prompts/v2.md prompts/v3.md`).

- **v2:** "If part of your question is still unanswered, use what the applicant just said to ask one short follow-up about the missing part. Once the applicant has answered the question, briefly acknowledge their answer and move on."
- **v3:** "If the applicant has explained what they did but left out what happened afterward, ask one question about the outcome. If they have already described the result, including a negative or unresolved result, briefly acknowledge it and move on."

The app's prompt choices stay v1 and v2 (`review.PROMPT_CHOICES`). v3 is used only by this experiment.

## Fresh test conversations

These are in `docs/measurements/prompt-v3/cases/`, written for this experiment, and no reply has been generated on them.

**Three pairs.** In each pair, the second conversation is the first plus **one added sentence** that gives the outcome, so the right next turn flips:

| Pair | Question asked | Without the sentence | With the sentence |
|---|---|---|---|
| F1 / F2 | upset patient or family member | ask about the outcome | positive outcome: acknowledge, move on to the advocacy question |
| F3 / F4 | advocacy | ask about the outcome | negative outcome (septic shock, ICU transfer): acknowledge, move on to the applicant's questions |
| F5 / F6 | upset patient or family member | ask about the outcome | unresolved outcome (a complaint, no resolution): acknowledge, move on to the advocacy question |

**Two controls:**
- **F7, consent:** availability is not consent, so the right turn is the disclosure plus a permission question.
- **F8, an applicant question:** orientation for someone new to the ICU, answered from the known facts.

**Judge criteria** for all eight are frozen in `docs/measurements/prompt-v3/notes.toml`. They follow the frozen D3/D4 (outcome missing or given) and D1 (consent) patterns. They are used only for the secondary judge-v1 scores.

## Generation (same models, settings and sample counts as the holdout)

- **Models and settings:**
  - gpt-5.4 and gpt-5.4-mini, with reasoning effort `none`;
  - gemini-3.5-flash, with thinking `MINIMAL`;
  - 2 samples per model per conversation, through the production CLI (`next-turn run`).
- **Volume:** 8 conversations × 3 models × 2 samples × 2 prompts = **96 replies**.
- **Order, fixed in `scripts/prompt_v3_experiment.py`:**
  1. OpenAI models, v2 then v3.
  2. Gemini one conversation at a time, alternating which prompt goes first.

  Gemini runs on a key that may be on the free tier, which has a daily request limit. Generation stops at the first incomplete step.
- **After a quota stop:** the missing Gemini steps are completed after the daily reset (midnight Pacific), with identical settings and the same order. Each completion is disclosed in the generation log.
- **Operational failures:** failed or incomplete generations are counted by kind and never shown as replies. In the comparison, a slot that failed under one prompt is excluded from both prompts for that model, conversation and sample, so neither prompt gains from a failure.
- **Blindness:** runs go to `holdout-private/prompt-v3/runs/` (gitignored), because their files name the model and prompt. The shuffled sheet, `docs/measurements/prompt-v3/review_sheet.md`, shows only conversations and replies under neutral IDs. The key and every run file are committed by SHA-256 in `docs/measurements/prompt-v3/commitment.json`.
- **Expected generation cost:** about $0.13 (64 OpenAI replies). Gemini is free on the free tier, or about $0.03 at paid rates.

## Labels

- **Who labels:** Nishanth labels every reply on the sheet, `y` or `n`, before seeing models, prompts, scores or suggested labels. The sheet records whether an AI assistant was used.
- **Ground truth:** his labels are the primary measure.
- **Order:** the labels are committed before the reveal.

## Success criteria (fixed now)

For each model and prompt, using Nishanth's labels:
1. **Pair-case replies accepted:** out of 12 (6 conversations × 2 samples), shown separately for:
   - the three outcome-missing conversations (F1, F3, F5);
   - the three outcome-given conversations (F2, F4, F6).
2. **Pair units right:** out of 6 (3 pairs × 2 samples). Both halves of the same sample must be accepted.
3. **Control replies accepted:** out of 4 (F7, F8 × 2 samples).

**v3 is supported** if both of these hold:
- summed over the three models, v3 has more accepted pair-case replies than v2;
- summed over the three models, v3 has no more than one fewer accepted control reply than v2.

**For each model,** the direction is reported as better, the same or worse on pair-case replies, with the control change beside it. With 2 samples per cell, a per-model difference of one reply is within noise.

**Secondary measure:** judge-v1, with the frozen criteria above, scores all 96 replies after the labels are committed. It is reported beside the labels, per model, with the registered one judge-only retry. Its agreement with the labels is reported, not used to decide.

**No adoption decision in this experiment.** v2 stays the default until Nishanth reviews the outcome.

## Scoring (after the labels are committed)

1. Copy `holdout-private/prompt-v3/` to `docs/measurements/prompt-v3/revealed/` and verify it against `commitment.json`.
2. Score every run with `next-turn score <run> --notes docs/measurements/prompt-v3/notes.toml --scores-dir docs/measurements/prompt-v3/scores --budget-usd 1.00`, listing every experiment run with `--budget-run`.
3. The expected scoring cost is about $0.35–0.40.

## Limits

- **Small:** 8 conversations and 2 samples per cell. Per-model differences are directional.
- **The conversations were designed by the session that will analyse them.** The freeze fixes them before any reply exists.
- **One reviewer.** The labels may be AI-assisted; the sheet records it.
