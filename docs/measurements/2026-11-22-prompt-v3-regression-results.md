# Prompt v3 regression check: results

**A separate check.** The plan was pre-registered in `docs/measurements/2026-11-22-prompt-v3-regression-plan.md` (`d2520cb`) before generation. v2 was the prompt used for the holdout. Nishanth later chose GPT-5.4 with v3 as the final recommendation, and "Run it yourself" now defaults to it. The saved comparison still opens on the v2 holdout run, and the published results, judge-v1 and the saved runs are unchanged.

**What was run.**
- **The replies.** v3 on D1–D4 and H1–H4, with gpt-5.4, gpt-5.4-mini and gemini-3.5-flash, 2 samples each, at the saved v2 settings: run `20261123T004511Z-b08ea8`. Plus the targeted case T1 under v2 and v3: runs `…b68051` and `…25803f`.
- **The scoring.** judge-v1, with `cases/notes.toml` for the original cases (the criteria the saved v2 replies were scored with) and the frozen T1 criterion. Each invalid judgment got the one retry.
- **The baseline.** The saved v2 replies keep their saved judge-v1 verdicts.
- **Spend.** $0.307799: OpenAI generation $0.071986, Gemini generation $0.016870 at Google's listed paid rate, judge-v1 $0.218943. The scorer's $1.00 cap was not reached.

## Original cases: judge-v1 acceptable (of 2), saved v2 → v3

| Case | gpt-5.4 | gpt-5.4-mini | gemini-3.5-flash |
|---|---|---|---|
| D1 consent | 2 → 1 + 1 unscored | 2 → 1 + 1 unscored | 2 → 2 |
| D2 certification currency | 2 → 1 + 1 unscored | 2 → 2 | 2 → 2 |
| D3 outcome missing | **0 → 2** | 2 → 2 | 2 → 2 |
| D4 outcome given | 1 → 2 | **2 → 1** | 2 → 2 |
| H1 withdrawal | 2 → 2 | 2 → 2 | 2 → 2 |
| H2 certifications volunteered | 0 → 0 | 0 → 0 | 0 → 0 |
| H3 day-shift guarantee | **0 → 2** | 0 → 1 | **2 → 1** |
| H4 close | 2 → 2 | 2 → 2 | 2 → 2 |
| **Accepted / rejected / unscored, of 16** | **9 / 7 / 0 → 12 / 2 / 2** | 12 / 4 / 0 → 11 / 4 / 1 | 14 / 2 / 0 → 13 / 3 / 0 |

**What the table includes:**
- **Unscored.** Three v3 judgments are unscored after their retry: gpt-5.4 D1 s2, Mini D1 s1 and gpt-5.4 D2 s1. Each time, the judge quoted a turn with its "Applicant:" label (known limit 3). These are not reply failures.
- **H2.** Every reply, under both prompts, asks about optional certifications, which H2's frozen criterion rejects. This is the known criterion issue, unchanged.

## The targeted case T1: outcome given, the applicant's own action missing

| Model | v2 asks what they did | v3 asks what they did | judge-v1 acceptable, v2 → v3 |
|---|---|---|---|
| gpt-5.4 | 2 of 2 | 2 of 2 | 2 → 2 |
| gpt-5.4-mini | 2 of 2 | **0 of 2** | 2 → **0** |
| gemini-3.5-flash | 2 of 2 | 2 of 2 | 2 → 1 |

- **Mini, v3.** It moves on without asking what the applicant did: "Thanks, that sounds like you helped de-escalate things and ended on a positive note. Describe a time you advocated for a patient whose needs weren't immediately recognized." Under v2, Mini asked "What did you do in the moment to help calm her and address her concerns?"
- **Gemini, v3, sample 2.** It does ask about the applicant's steps. The judge took a point off next action for combining "steps and resolution in one question".

## Regressions

**Observed regressions consistent with the wording change** (on the pre-registered follow-up moments and T1). The plan called these "attributed to the change". With two samples, this report describes them as observed regressions consistent with it. All three are on **gpt-5.4-mini**:
- **T1, both samples:** it moves on past an answer that lacks the applicant's own action. This is consistent with the main risk of dropping v2's general follow-up rule.
- **D4, sample 2:** it re-asks a given outcome: "That makes sense, and it sounds like bringing the charge nurse in helped settle the inconsistency. What was the outcome after that conversation?" Under v2, the same sample moved on correctly. This is consistent with v3's outcome rule being over-applied.

**Other differences:**
- **Gemini on H3, sample 1** (2 → 1): grounding 1 for an invented process detail ("handled directly by the hiring team during the offer process"). That is not the follow-up instruction.
- **The three unscored judgments:** judge-v1's quote check, not the replies.

**We observed no regression for GPT-5.4 in this check.** Its acceptances rose on D3, D4 and H3, and it asked for the applicant's own action on T1 under both prompts. With two samples, we can't establish what caused every difference.

## An improvement the judge credits, which the reviewer's dev label did not require

- **gpt-5.4 on D3, sample 1, v2:** "What did you say or do in that conversation, and how did things end up being resolved?" This is a stacked follow-up; the judge gave next action 1, 6/8. Nishanth's development label accepted it.
- **v3:** "Thanks for explaining that. What happened after you and the charge nurse sat down with him?" The judge gave 8/8.

## Conclusion

- **GPT-5.4:** we observed no regression in this check. On the original cases, its acceptances rose from 9 to 12 of 16, with 2 v3 judgments unscored.
- **Mini and Gemini: v3 is not recommended as written.**
  - Mini loses the "ask what you did" follow-up and over-applies the outcome rule.
  - Gemini gains nothing on the ChatGPT labels in the pair experiment, and its acknowledgments still assume outcomes (R41).
- **A v4 that keeps v2's general missing-part rule and adds v3's outcome clause** would address the Mini regression, but it is untested.
