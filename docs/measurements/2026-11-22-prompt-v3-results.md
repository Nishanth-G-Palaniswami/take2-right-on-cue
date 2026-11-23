# Prompt v3 (behavioral follow-up): results

**A separate experiment.** Riley's app default stays **v2** until Nishanth decides. The published holdout results (31 of 47, 2 of 12), judge-v1, `cases/notes.toml` and the saved runs are unchanged. The plan was pre-registered in `docs/measurements/2026-11-22-prompt-v3-plan.md`.

**Sequence, by commit:**
1. `c0eda59`: wording, conversations, criteria and procedure frozen.
2. `5625433`: a fix to the generation script's exit handling.
3. `032930b`: the blind sheet.
4. `7a6e8fd` and `252feb2`: the labels and their provenance.
5. `21e7579`: reveal; all 40 private files match the commitment.
6. This commit: scoring and results.

## The labels used, and how they deviate from the plan

The plan's primary measure was Nishanth's own blind labels. The labels used are in `review_sheet_chatgpt.md`, with 96 decisions: 67 `y` and 29 `n`.
- **Where they come from.** Two medical students said on a call which replies looked right or wrong, and ChatGPT turned the call transcript into the per-item decisions and reasons.
- **What the sheet says.** Its attribution line was revised before the reveal and now says the decisions "were generated after reviewing the conversation between the students and the owner of the project". The first version called them "AI-generated judgments". No decision changed.
- **What isn't recorded.** Whether the students judged every reply individually.
- **Blindness.** Model, prompt and score were not available to anyone until after the labels were fixed: they stayed in the gitignored private folder, and nothing was scored before the reveal.

`label_notes.md` quotes Nishanth's decision. These labels are AI-mediated, not an unaided human check.

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

## Results per model (primary: the labels used)

| Model | Prompt | Outcome missing, asks (of 6) | Outcome given, moves on (of 6) | Pair conversations (of 12) | Both halves of a pair right (of 6) | Controls (of 4) |
|---|---|---|---|---|---|---|
| gpt-5.4 | v2 | 2 | 3 | 5 | 2 | 4 |
| | **v3** | **5** | **6** | **11** | **5** | 4 |
| gpt-5.4-mini | v2 | 2 | 3 | 5 | 0 | 4 |
| | **v3** | **6** | **5** | **11** | **5** | 4 |
| gemini-3.5-flash | v2 | 0 | 6 | 6 | 0 | 3 |
| | v3 | 1 | 5 | 6 | 1 | 4 |
| **All three** | v2 | 4 | 12 | 16 | 2 | 11 |
| | **v3** | **12** | **16** | **28** | **11** | 12 |

**The registered test is met.** Summed over the models, v3 has more accepted pair-conversation replies than v2 (28 vs 16), and no more than one fewer accepted control reply (12 vs 11).

**By model:**
- **gpt-5.4: v3 better.** Pair conversations 5 → 11, controls the same.
- **gpt-5.4-mini: v3 better.** Pair conversations 5 → 11, controls the same.
- **gemini-3.5-flash: no change on the pair conversations** (6 → 6). Controls went 3 → 4, which is within noise.

## Secondary: judge-v1 with the frozen criteria

| Model | Prompt | Outcome missing (of 6) | Outcome given (of 6) | Pair conversations (of 12) | Both halves right (of 6) | Controls (of 4) |
|---|---|---|---|---|---|---|
| gpt-5.4 | v2 | 6 | 2 | 8 | 2 | 4 |
| | v3 | 6 | 5 | 11 | 5 | 4 |
| gpt-5.4-mini | v2 | 2 | 3 | 5 | 0 | 4 |
| | v3 | 6 | 5 | 11 | 5 | 4 |
| gemini-3.5-flash | v2 | 0 | 5 | 5 | 0 | 3 |
| | v3 | 5 | 5 | 10 | 4 | 4 |
| **All three** | v2 | 8 | 10 | 18 | 2 | 11 |
| | v3 | 17 | 15 | 32 | 14 | 12 |

judge-v1 agrees with the labels on **80 of 96** replies. It also finds v3 better for every model, including Gemini (5 → 10).

## Why the labels and the judge split, mostly on Gemini

Of the 16 disagreements, 11 are replies the labels reject and the judge accepts. Most of those ask the right outcome question but wrap it in an acknowledgment that **assumes a result the applicant never gave**, or stack two questions. The frozen judge criteria only check for a specific acknowledgment and one outcome question, so they don't catch this. Examples, with the labels' reasons:

- **R41**, Gemini, v3, advocacy: "What was the outcome for the patient after you got the resident to order the lactate and sepsis screen?" The reason given: it credits the applicant with an order they only requested.
- **R08**, gpt-5.4, v2, same conversation: "What happened after the sepsis screen and lactate were done?" The reason given: it turns a request into a completed workup.
- **R82**, gpt-5.4, v2, upset son: "You helped de-escalate him… What was the outcome after that conversation?" The reason given: it assumes the son calmed down.
- **R44**, Gemini, v3: "How did the son react to that offer, and how did the situation end up resolving?" The reason given: two questions, and it treats the offered call as already set up.

So for Gemini, v3 fixed the move itself: the judge sees it asking about the outcome 5 times in 6, against 0 in 6 under v2. The labels still reject most of those replies for the wording around the question.

The other 5 disagreements are replies the labels accept and the judge rejects. Four are on F4, the negative outcome.

## Per conversation (accepted of 2: labels / judge)

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

- **AI-mediated labels.** An OpenAI model encoded the labels for replies from two OpenAI models and Gemini. The students' judgments reached the sheet through a call transcript.
- **Small.** 8 conversations and 2 samples per cell. A per-model difference of one reply is noise.
- **Designed and analysed by the same session.** The freeze fixed the conversations, wording and criteria before any reply existed.
- **v3 is untested on the original cases.** v3 removes v2's general "missing part" follow-up and keeps only the outcome rule. v3 has not been run on D1–D4 or H1–H4.

## Recommendation

**v3 is better than v2 for gpt-5.4 and gpt-5.4-mini on both measures, and the registered test is met. Run one regression check of v3 on the original eight cases (D1–D4, H1–H4) before making it the app default.**

- **For Gemini, the labels show no gain.** Its remaining failures are acknowledgments that assume the outcome, which neither prompt addresses.
- **Why the regression check:** v3 dropped v2's general instruction to follow up on any missing part of an answer.
- **A separate next step:** a v4 experiment could test one added instruction, "acknowledge only what the applicant said; don't assume how it turned out".
