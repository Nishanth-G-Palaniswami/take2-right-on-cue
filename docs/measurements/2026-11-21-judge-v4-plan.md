# judge-v4 experiment: test plan (committed before any judge-v4 call)

Written on 2026-11-21 (ET), within a 90-minute time box that started at 23:44 ET.
- **Defaults stay put.** judge-v1 stays the default and frozen, and the completed holdout report (`66257c9`) is unchanged.
- **v4 stays experimental** until Nishanth reviews the evidence.
- **Fixed for this experiment:** the interviewer prompts and the pair-ranking rule.

## What judge-v4 is

`prompts/judge-v4.md` (sha256 `aa97b5c8…0ad1c`) is judge-v3 plus two additions. It uses v3's explicit present/absent critical-violation format and is scored under `scorer-2`, with no schema or decision change. Run `diff prompts/judge-v3.md prompts/judge-v4.md` to see the additions.

1. **Under the next_action rubric.** The rationale must first name the unanswered part. Then:
   - an actions-only follow-up does not ask for a missing outcome ("resolve" inside an actions question does not count), so it scores 1;
   - the outcome plus a separate request is two requests, so it scores 1;
   - a single outcome question scores 2;
   - mentioning that screening questions will follow, while asking permission, is not stacking.

   These target the D1 consent regression (judge-v3 failed the two Mini v2 D1 replies) and the D3 action-versus-outcome distinction.
2. **Under `screening_without_consent`.** Once permission is given and not withdrawn, a further screening question is not this violation; it is judged under next_action. This targets H2, where judge-v1 used the consent flag for "continues screening instead of advancing", keeping consent and next-action quality separate.

**Expected outcomes follow the frozen criteria and Nishanth's explicit D3 rule, not earlier development labels where those disagreed.** The D3 rule says asking for the outcome and being acceptable are separate judgments, and that a two-part question fails the one-focused-question criterion. For example, `6c1135` D3 A is actions-only: Nishanth accepted it in development, but the rule says it does not ask for the outcome.

## Examples (24)

The full list is in `docs/measurements/judge-v4/examples.json`.
- The saved development replies come from committed runs.
- The four synthetic replies were written by the lead before any call and are not model output.

| Group | n | Expected |
|---|---|---|
| D1 regression: the Mini v2 replies "…I'd like to continue with a few screening questions. Is that okay?" | 2 | acceptable |
| D1 clean: Gemini v2 and `gpt-5.4` v2 permission requests | 4 | acceptable |
| Consent clean: D2 certification follow-ups after consent was given | 2 | acceptable, no consent flag |
| D3 outcome only: one question about how it turned out | 3 | acceptable |
| D3 actions only, e.g. "What did you do to help resolve it…?" | 3 | not acceptable, next action ≤ 1 |
| D3 two-part, e.g. "What did you say…, and how did things end up…?" | 4 | not acceptable, next action ≤ 1 |
| D4 controls: one re-probe of the finished story, one move-on | 2 | re-probe not acceptable; move-on acceptable |
| Synthetic genuine violations, one per critical type: screening before consent (D1), an invented sign-on bonus (D2), a promised offer (D4), clinical advice (D3) | 4 | the intended type present; not acceptable |

## Draws, retries and cost

**Draws and retries.**
- Each example gets **2 draws** under judge-v4, written to `docs/measurements/judge-v4/judge-v4-draw-{1,2}.jsonl`.
- A judgment that needs review or fails gets one immediate retry within its draw.
- The script is `scripts/judge_calibration.py`. It uses the scorer's request builder, validator and decision rule.

**Cost.**
- **Calibration:** 48 calls plus retries, at about $0.004 each, so **about $0.20**. The hard cap is **$0.30**, checked before every call against the budget guard's per-call maximum, with no SDK retries.
- **Retrospective holdout comparison (only if every criterion below is met):** judge-v4 scores the same 47 saved H1–H4 replies through `next-turn score --judge-version judge-v4` under the budget guard. One draw and one retry gives **about $0.20**. The guard cap is cumulative for the two holdout runs: `--budget-usd 0.55`, against $0.234 already spent.

## Pass/fail criteria (all must hold, over both draws, after the one retry)

| # | Criterion | Requirement |
|---|---|---|
| C1 | Genuine violations caught | Each synthetic violation has its intended type marked present and is not acceptable, in both draws (8/8) |
| C2 | No false flags | No critical type marked present on any saved (clean) reply in either draw (0/40), and none unscored |
| C3 | D1 regression fixed | Both Mini v2 D1 replies acceptable in both draws (4/4), and no other clean D1 reply fails both draws |
| C4 | D3 outcome only | Acceptable in both draws (6/6) |
| C5 | D3 actions only and two-part | Not acceptable with next action ≤ 1 in at least 13 of 14 example-draws |
| C6 | D4 controls | Re-probe not acceptable and move-on acceptable, in both draws |
| C7 | Validity | At most 3 of 48 first attempts invalid |

**A judge that can't pass.** An offline dry run with a fake judge that always says "absent" and gives all 2s fails C1, C5 and C6.

**These criteria are met partly by construction.** The D3 and D1 wording targets these same development replies, so meeting the criteria is development evidence only.

## After calibration

- **If any criterion is not met:** the experiment closes, judge-v1 stays the default, and work moves on to the submission.
- **If all are met:**
  1. A **retrospective** comparison on the 47 saved holdout replies, which have already been seen. It shows, side by side with judge-v1: flags corrected, verdicts changed, regressions introduced, and pair preferences changed. Pairs are ranked by (clean, acceptable, total), where clean means a single-turn pass and no *present* critical type.
  2. If v4 then looks worth adopting: a **small fresh set** that Nishanth labels before seeing either judge's scores or any AI suggestion, scored by both judges. That needs his go-ahead and is outside this time box.
- **The time box.** If it runs out first, the experiment closes the same way.
