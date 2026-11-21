# Measurement: matched v1 vs v2, three models, D1–D4 (development)

**Did v2 narrow the gap?**
- On Nishanth's labels, the spread between the highest- and lowest-scoring model went from **4/8 under v1 to 1/8 under v2**. Total acceptance stayed **20/24 under both prompts**.
- That is an observation on these four development cases, not an attributed prompt effect:
  - most of the change sits on D3, where similar questions were labelled differently across runs;
  - there are two samples per model per case.
- Model ranking stays open.

## Matched set

There are 2 samples per model, prompt and case on D1–D4. Prompt and case files hash the same within each prompt version. Every run used reasoning effort `none` for OpenAI and thinking level `MINIMAL` for Gemini.

| Prompt | Model (reported as) | Run(s) | Labels committed | Labelling conditions |
|---|---|---|---|---|
| v1 | `gpt-5.4` (`gpt-5.4-2026-03-05`) | `20261121T202643Z-96f2fa` | `c10c6e5` | Model hidden (mixed with Gemini); Nishanth saw ChatGPT's suggestions before finalizing |
| v1 | `gpt-5.4-mini` (`gpt-5.4-mini-2026-03-17`) | `20261121T005440Z-0dbed1` (D1/D2), `20261121T000156Z-6c1135` (D3/D4) | `187a304`, `8191552` | Single-model runs. The `0dbed1` labels were committed "before any unblinding or feedback" (`187a304`), and the `6c1135` labels "before any scorer" (`8191552`). `6c1135` D4: a later tie correction (below) |
| v1 | `gemini-3.5-flash` (`gemini-3.6-flash`) | `20261121T202643Z-96f2fa` | `c10c6e5` | As for v1 `gpt-5.4` |
| v2 | `gpt-5.4` (`gpt-5.4-2026-03-05`) | `20261121T195552Z-6237ea` | `f13316a` | Not model-blind; Nishanth discussed his judgments with an AI assistant before committing |
| v2 | `gpt-5.4-mini` (`gpt-5.4-mini-2026-03-17`) | `20261121T023359Z-455c41` | `b3c3a5d` | Model hidden (mixed with Gemini); committed after AI reviews by ChatGPT and Claude |
| v2 | `gemini-3.5-flash` (`gemini-3.6-flash`) | `20261121T023359Z-455c41` | `b3c3a5d` | As for v2 Mini |

**Scoring.**
- Frozen judge-v1 under `docs/judge-v1-known-limits.md`: one draw per reply at temperature 1.0, and one retry per invalid or failed judgment.
- The `455c41` verdicts are from its draw 1.
- Raw verdicts are in `scores/<run_id>.jsonl`, unedited.

## Results by model and prompt

| Model | Prompt | Nishanth accepted | judge-v1 acceptable | Unscored | Judge agrees (of scored) | D3: outcome asked | D4: unnecessary follow-up |
|---|---|---|---|---|---|---|---|
| `gpt-5.4` | v1 | 4/8 | 3/8 | 1 | 7/7 | 2/2 | 2/2 |
| `gpt-5.4` | v2 | 7/8 | 5/8 | 0 | 6/8 | 2/2 | 1/2 |
| `gpt-5.4-mini` | v1 | 8/8 | 7/8 | 1 | 7/7 | 0/2 | 0/2 |
| `gpt-5.4-mini` | v2 | 6/8 | 8/8 | 0 | 6/8 | 0/2 | 0/2 |
| `gemini-3.5-flash` | v1 | 8/8 | 7/8 | 1 | 7/7 | 2/2 | 0/2 |
| `gemini-3.5-flash` | v2 | 7/8 | 8/8 | 0 | 7/8 | 2/2 | 0/2 |

**Where the label changes come from.** These are v1 → v2 on Nishanth's labels:

| Model | Change | D3 | D4 |
|---|---|---|---|
| `gpt-5.4` | +3 (4 → 7) | +2 | +1 |
| `gpt-5.4-mini` | −2 (8 → 6) | −2 | 0 |
| `gemini-3.5-flash` | −1 (8 → 7) | −1 | 0 |

- The spread narrowed because `gpt-5.4` rose while Mini and Gemini fell. Every change except one is on D3, where the counting rule shows no change for any model (next section).
- The exception is `gpt-5.4`'s +1 on D4, which matches a drop in unnecessary follow-ups.

**Per case.** Each cell shows sample 1, then sample 2. "unsc." means still invalid after the retry.

| Case | Model | v1 labels | v1 judge | v2 labels | v2 judge |
|---|---|---|---|---|---|
| D1 | `gpt-5.4` | y, y | pass, pass | y, y | pass, pass |
| | Mini | y, y | pass, pass | y, y | pass, pass |
| | Gemini | y, y | unsc., pass | y, y | pass, pass |
| D2 | `gpt-5.4` | y, y | pass, unsc. | y, y | pass, pass |
| | Mini | y, y | unsc., pass | y, y | pass, pass |
| | Gemini | y, y | pass, pass | y, y | pass, pass |
| D3 | `gpt-5.4` | n, n | FAIL, FAIL | y, y | FAIL, FAIL |
| | Mini | y, y | pass, pass | n, n | pass, pass |
| | Gemini | y, y | pass, pass | y, n | pass, pass |
| D4 | `gpt-5.4` | n, n | FAIL, FAIL | y, n | pass, FAIL |
| | Mini | y, y | pass, pass | y, y | pass, pass |
| | Gemini | y, y | pass, pass | y, y | pass, pass |

## D3: same counting result under both prompts, labels differ on similar questions

Each model asked for the missing outcome equally often under v1 and v2: `gpt-5.4` 2/2 and 2/2, Mini 0/2 and 0/2, Gemini 2/2 and 2/2. The rule is from `docs/measurements/2026-11-20-v1-d3-d4-x5.md`: "yes" if the reply asks how the situation ended, whether as the whole question or part of one request.

Nishanth's original labels are preserved. Each reply below lists its run, letter and sample:

| Question type | Prompt, model, run, letter (sample) | Reply | Outcome asked | Label | judge-v1 |
|---|---|---|---|---|---|
| Two-part: what you said + how it ended | v1 `gpt-5.4` `96f2fa` C (1) | "What did you say to help calm him down, and how did things end up after that conversation?" | yes | **n** | FAIL 1121 5 |
| | v1 `gpt-5.4` `96f2fa` B (2) | "What did you say in that conversation, and how did things end up after that?" | yes | **n** | FAIL 1121 5 |
| | v2 `gpt-5.4` `6237ea` B (1) | "You helped bring everyone together when he was getting mixed messages. What did you say or do in that conversation, and how did things end up being resolved?" | yes | **y** | FAIL 1221 6 |
| | v2 `gpt-5.4` `6237ea` A (2) | "You involved your charge nurse and created a calmer space to talk, which makes sense. What did you say or do in that conversation, and how did it end up getting resolved?" | yes | **y** | FAIL 1121 5 |
| Actions only | v1 Mini `6c1135` A (1) | "What did you do next to help clear up the confusion and calm the situation?" | no | **y** | pass 8 |
| | v1 Mini `6c1135` B (2) | "What did you and the charge nurse do to resolve the confusion and help the brother calm down?" | no (borderline: actions toward a resolution) | **y** | pass 8 |
| | v2 Mini `455c41` B (1) | "What did you do to help resolve it once you brought the charge nurse in?" | no | **n** | pass 8 |
| | v2 Mini `455c41` D (2) | "That sounds like a tense situation, and bringing the charge nurse in was a good step. How did you resolve it for the brother and the patient?" | no | **n** | pass 8 |
| Outcome only | v1 Gemini `96f2fa` D (1) | "…What was the ultimate outcome for the patient's brother after that conversation?" | yes | y | pass 8 |
| | v1 Gemini `96f2fa` A (2) | "…What was the ultimate outcome for that family once you had that conversation?" | yes | y | pass 8 |
| | v2 Gemini `455c41` A (1) | "…How did the situation end up getting resolved with the patient's brother?" | yes | y | pass 8 |
| | v2 Gemini `455c41` C (2) | "…How did that conversation end up resolving his frustration?" | yes | n | pass 8 |

**Similar questions judged differently.**
1. **Two-part questions, rejected under v1 and accepted under v2.**
   - The v1 sheet's reason: "B and C each add a second request about what the applicant said". These were labelled with the model hidden, after seeing ChatGPT's suggestions.
   - The v2 sheet's reason: "I'd accept either reply because both ask how the conversation ended". These were labelled with the model known, after an AI discussion.
   - The visible wording difference is that the v2 replies open with an acknowledgment. Neither the wording nor the labelling conditions is established as the reason.
   - For context, outside the matched set, base `70fb30` D3-B ("What did you do after you brought the charge nurse in, and how did the situation end?") was also accepted.
2. **Action-only questions, accepted under v1 and rejected under v2.** Compare the near-identical "What did you and the charge nurse do to resolve the confusion…" (v1, accepted) with "What did you do to help resolve it once you brought the charge nurse in?" (v2, rejected).
   - The v1 labels were made in a single-model run, before any feedback.
   - The v2 labels were made after AI reviews.

judge-v1 treats each pattern the same way in both runs: it fails the two-part questions and passes the action-only questions. On D3 it therefore agrees with the v1 labels and disagrees with the v2 labels. This is known limit 2.

## D4: unnecessary follow-ups on the completed story

"Asked again" is defined as an unnecessary follow-up on the completed story: the applicant has already given the outcome ("he told me he finally knew what to expect").

| Prompt, model, run, letter (sample) | Reply | Unnecessary follow-up | Label | judge-v1 |
|---|---|---|---|---|
| v1 `gpt-5.4` `96f2fa` A (1) | "Thanks, that helps. What did you personally say or do in that conversation to de-escalate things before it got resolved?" | yes, about actions | n | FAIL 0111 3, 1 false critical flag |
| v1 `gpt-5.4` `96f2fa` B (2) | "Thanks, that helps. What did you say or do in the moment to calm him down before you brought in the charge nurse?" | yes, about actions | n | FAIL 0111 3, 1 false critical flag |
| v2 `gpt-5.4` `6237ea` A (1) | Acknowledges, then gives the advocacy question | no | y | pass 8 |
| v2 `gpt-5.4` `6237ea` B (2) | "…What was the result after that?" | yes, repeats the outcome question | n | FAIL 0121 4, 4 false critical flags |

- **Summary.** Unnecessary follow-ups went from 2/2 to 1/2 for `gpt-5.4`, and stayed at 0/2 for Mini and Gemini. Every Mini and Gemini D4 reply, under both prompts, acknowledges and moves on to the advocacy question.
- **Labels and judge.** Nishanth and judge-v1 reject all three follow-ups.
- **The critical flags.** Every critical flag on them is a false positive by Nishanth's review: `runs/20261121T202643Z-96f2fa/critical_review.md` and `runs/20261121T195552Z-6237ea/critical_review.md`. Each judge rationale also denies the violation (known limit 1).
- **Raw verdicts** are unchanged.

## Judge agreement

- **v1:** 21/21 scored replies agree with Nishanth's labels. Three replies are unscored after their retry, all because the judge quoted a transcript turn with its "Applicant:" label (known limit 3). They are operational failures, not rejections:
  - `96f2fa` D1 Gemini sample 1;
  - `96f2fa` D2 `gpt-5.4` sample 2;
  - `0dbed1` D2 Mini sample 1.
- **v2:** 19/24. All five disagreements are on D3:
  - the judge rejected both `gpt-5.4` replies Nishanth accepted;
  - it passed both Mini replies and one Gemini reply that he rejected.
- **The `6c1135` D4 correction.** After unblinding, Nishanth changed his preference from B to a tie (`runs/20261121T000156Z-6c1135/label_corrections.md`). Both acceptance labels (y, y) stayed intact, so the counts above are unaffected.

## Limits

- **Sample size.** Four development cases and two samples per model per case. Replies within a case are related.
- **Judge draws.** One draw per reply at temperature 1.0.
- **Labelling conditions** differ across runs (table above). Every set except the two reused Mini runs is recorded as AI-informed. No AI assistance is recorded for those two.
- **The judge.** It is a Mini model, so effects from judging its own family are possible. The D3 disagreements are a known judge limit.
- **Development only.** These are development cases. Holdout results, under a frozen setup, are still to come.

## Cost

These are estimates from recorded tokens at the PRD rates (`gpt-5.4` $2.50/$15 and Mini $0.75/$4.50 per million input/output tokens), not read from the usage page. They cover the calls made for this matched set on 2026-11-21. The earlier runs it reuses are not included.

| Step | Calls | Estimate |
|---|---|---|
| `gpt-5.4` preflight | 1 | $0.00252 |
| v2 `gpt-5.4` generation (`6237ea`) | 8 | $0.02309 |
| v2 `gpt-5.4` scoring | 8 | $0.02797 |
| v1 `gpt-5.4` generation (`96f2fa`); Gemini adds no OpenAI cost | 8 | $0.02213 |
| v1 scoring (`96f2fa`, `0dbed1`, `6c1135`), including 6 retries | 30 | $0.10161 |
| **Total** | **55** | **$0.17732** |
