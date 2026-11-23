# Prompt v3 (behavioral follow-up): results

**A separate experiment.**
- **v2 was the prompt used for the holdout.**
- **v3 is the final prompt.** After this experiment and the regression check, Nishanth chose GPT-5.4 with v3 as the final recommendation (2026-11-22), and "Run it yourself" now defaults to it.
- **The saved comparison.** It now opens on H3 with v3, from the regression check's retest on the original cases, and v2 is one click away.

 The published holdout results (31 of 47, 2 of 12), judge-v1, `cases/notes.toml` and the saved runs are unchanged. The plan was pre-registered in `docs/measurements/2026-11-22-prompt-v3-plan.md`.

**Sequence, by commit:**
1. `c0eda59`: wording, conversations, criteria and procedure frozen.
2. `5625433`: a fix to the generation script's exit handling.
3. `032930b`: the blind sheet.
4. `7a6e8fd` and `252feb2`: the ChatGPT labels and their provenance.
5. `21e7579`: reveal; all 40 private files match the commitment.
6. This commit: scoring and results.

## The ChatGPT labels, and how they deviate from the plan

The plan's primary measure was Nishanth's own blind labels. This experiment uses **ChatGPT labels** instead: `review_sheet_chatgpt.md`, 96 decisions, 67 `y` and 29 `n`.

> ChatGPT assigned all 96 labels using the transcripts and Nishanth’s summary of feedback from two students who discussed sample interviews.

- **The sheet's attribution line** was revised before the reveal, and no decision changed. `label_notes.md` quotes both versions and Nishanth's decision.
- **Blindness.** Model, prompt and score were not available to anyone until after the ChatGPT labels were fixed: they stayed in the gitignored private folder, and nothing was scored before the reveal.

These are ChatGPT labels, not an unaided human check. The development and holdout reviews have their own attribution (`holdout/review/label_notes.md`), which is unchanged.

## Generation and scoring

- **Generation.** All 96 replies were produced under the frozen script, models and settings:
  - gpt-5.4 and gpt-5.4-mini at reasoning effort `none`, and gemini-3.5-flash at thinking `MINIMAL`;
  - 2 samples, through `next-turn run`;
  - every slot `ok` and verified against the frozen prompt and conversation hashes.
- **The Gemini interruption.** Generation stopped once on Gemini's free-tier daily quota (F4/v2, sample 2), as the plan provides. It resumed after billing was added: the 9 remaining steps ran, and F4/v2 was rerun with both samples. The interrupted attempt stays in the generation log.
- **Scoring.** judge-v1 scored all 96 with the frozen criteria (`notes.toml`), and all 96 have a valid judgment.
  - Two replies needed the one registered retry (F3/v3/gpt-5.4 sample 2, F4/v2/gemini sample 2); both retries were valid.
  - A run of mine was cut off mid-scoring; it left 7 complete scores and no unaccounted call.
- **Spend.** $0.441581 under the scorer's $1.00 cap: $0.106712 for OpenAI generation and $0.334869 for judge-v1. Separately, the 18 Gemini replies generated after billing cost $0.014684 at Google's listed rate. Earlier Gemini replies were on the free tier.

## Results per model (primary: the ChatGPT labels)

| Model | Prompt | Accepted when the outcome was missing (of 6) | Accepted when the outcome was given (of 6) | Pair conversations accepted (of 12) | Both halves of a pair accepted (of 6) | Controls accepted (of 4) |
|---|---|---|---|---|---|---|
| gpt-5.4 | v2 | 2 | 3 | 5 | 2 | 4 |
| | **v3** | **5** | **6** | **11** | **5** | 4 |
| gpt-5.4-mini | v2 | 2 | 3 | 5 | 0 | 4 |
| | **v3** | **6** | **5** | **11** | **5** | 4 |
| gemini-3.5-flash | v2 | 0 | 6 | 6 | 0 | 3 |
| | v3 | 1 | 5 | 6 | 1 | 4 |
| **All three** | v2 | 4 | 12 | 16 | 2 | 11 |
| | **v3** | **12** | **16** | **28** | **11** | 12 |

**What the columns count: accepted replies, not behaviors.** R01 shows the difference. It is gpt-5.4 under v2 on F4, where the outcome was already given. It asked a further question about escalation ("What did you do to advocate for the patient after your initial pages weren’t acted on?"), and the ChatGPT labels accepted it. It counts as accepted when the outcome was given; it did not move on.

**The registered test is met.** Summed over the models, v3 has more accepted pair-conversation replies than v2 (28 vs 16), and no more than one fewer accepted control reply (12 vs 11).

**By model:**
- **gpt-5.4: v3 better.** Pair conversations 5 → 11, controls the same.
- **gpt-5.4-mini: v3 better.** Pair conversations 5 → 11, controls the same.
- **gemini-3.5-flash: no change on the pair conversations** (6 → 6). Controls went 3 → 4, which is within noise.

## Secondary: judge-v1 with the frozen criteria

| Model | Prompt | Accepted when the outcome was missing (of 6) | Accepted when the outcome was given (of 6) | Pair conversations accepted (of 12) | Both halves of a pair accepted (of 6) | Controls accepted (of 4) |
|---|---|---|---|---|---|---|
| gpt-5.4 | v2 | 6 | 2 | 8 | 2 | 4 |
| | v3 | 6 | 5 | 11 | 5 | 4 |
| gpt-5.4-mini | v2 | 2 | 3 | 5 | 0 | 4 |
| | v3 | 6 | 5 | 11 | 5 | 4 |
| gemini-3.5-flash | v2 | 0 | 5 | 5 | 0 | 3 |
| | v3 | 5 | 5 | 10 | 4 | 4 |
| **All three** | v2 | 8 | 10 | 18 | 2 | 11 |
| | v3 | 17 | 15 | 32 | 14 | 12 |

judge-v1 agrees with the ChatGPT labels on **80 of 96** replies. It also finds v3 better for every model, including Gemini (5 → 10).

## Why the ChatGPT labels and the judge split, mostly on Gemini

Of the 16 disagreements, 11 are replies the ChatGPT labels reject and the judge accepts. Most of those ask the right outcome question but wrap it in an acknowledgment that **assumes a result the applicant never gave**, or stack two questions. The frozen judge criteria only check for a specific acknowledgment and one outcome question, so they don't catch this. Examples, with the ChatGPT labels' reasons:

- **R41**, Gemini, v3, advocacy: "What was the outcome for the patient after you got the resident to order the lactate and sepsis screen?" The reason given: it credits the applicant with an order they only requested.
- **R08**, gpt-5.4, v2, same conversation: "What happened after the sepsis screen and lactate were done?" The reason given: it turns a request into a completed workup.
- **R82**, gpt-5.4, v2, upset son: "You helped de-escalate him… What was the outcome after that conversation?" The reason given: it assumes the son calmed down.
- **R44**, Gemini, v3: "How did the son react to that offer, and how did the situation end up resolving?" The reason given: two questions, and it treats the offered call as already set up.

Reading Gemini's replies on the three outcome-missing conversations: under v3 it asked about the outcome in 5 of 6, and under v2 in 2 of 6, both stacked with a second question. judge-v1 accepted 5 of the v3 replies and none of the v2 ones. The ChatGPT labels rejected most of the v3 replies for the wording around the question.

The other 5 disagreements are replies the ChatGPT labels accept and the judge rejects. Four are on F4, the negative outcome.

## Per conversation (accepted of 2: ChatGPT labels / judge)

| | gpt-5.4 v2 | gpt-5.4 v3 | mini v2 | mini v3 | Gemini v2 | Gemini v3 |
|---|---|---|---|---|---|---|
| F1 outcome missing | 2/2 | 2/2 | 0/0 | 2/2 | 0/0 | 1/2 |
| F2 positive outcome given | 2/2 | 2/2 | 2/2 | 2/2 | 2/2 | 2/2 |
| F3 outcome missing | 0/2 | 1/2 | 2/2 | 2/2 | 0/0 | 0/2 |
| F4 negative outcome given | 1/0 | 2/1 | 0/0 | 1/1 | 2/1 | 1/1 |
| F5 outcome missing | 0/2 | 2/2 | 0/0 | 2/2 | 0/0 | 0/1 |
| F6 unresolved outcome given | 0/0 | 2/2 | 1/1 | 2/2 | 2/2 | 2/2 |
| F7 consent (control) | 2/2 | 2/2 | 2/2 | 2/2 | 2/2 | 2/2 |
| F8 applicant question (control) | 2/2 | 2/2 | 2/2 | 2/2 | 1/1 | 2/2 |

## Limits

- **ChatGPT labels.** An OpenAI model assigned the labels for replies from two OpenAI models and Gemini, using the transcripts and a summary of two students' feedback on sample interviews.
- **Small.** 8 conversations and 2 samples per cell. A per-model difference of one reply is noise.
- **Designed and analysed by the same session.** The freeze fixed the conversations, wording and criteria before any reply existed.
- **The original cases came later.** v3 removes v2's general "missing part" follow-up and keeps only the outcome rule. It was then run on D1–D4 and H1–H4 in a separate regression check (`docs/measurements/2026-11-22-prompt-v3-regression-results.md`).

## Recommendation

**The registered test is met. This experiment recommended a regression check before changing the default; that check followed.** It observed no regression for GPT-5.4. It observed regressions for Mini consistent with the wording change. The final recommendation is GPT-5.4 with v3.

- **For Gemini, the ChatGPT labels show no gain.** Its remaining failures are acknowledgments that assume the outcome, which neither prompt addresses.
- **Why the regression check:** v3 dropped v2's general instruction to follow up on any missing part of an answer.
- **A separate next step:** a v4 experiment could test one added instruction, "acknowledge only what the applicant said; don't assume how it turned out".
