# judge-v5: results of the fresh check (not adopted)

**Verdict: judge-v5 fails the frozen check. It misses all six pass criteria.**
- judge-v1 stays the production judge.
- No rescore was run, and no live setting was changed. As Nishanth instructed, the work stopped at the first failure.

**Sequence:**
- `c6bc25f`: the candidate and pass criteria frozen.
- `4aace06`: the blind sheet.
- `7e193c6` and `61c3660`: harness fixes made before scoring.
- `d3f14b2`: Nishanth's 18 labels committed before any judge call.
- This commit: scoring and reveal. `revealed/items.json` and `revealed/key.json` match `commitment.json`.

**Labels.** 9 `y`, 9 `n`. They are AI-assisted. Nishanth gave initial judgments, then discussed specific items with ChatGPT and revised J03, J06 and J07. His disclosure is on the sheet.

**Spend.** $0.464140 of the $0.75 cap, over 124 calls. The records are in `judge-v5/results/`, and the report is `judge-v5/report.json`.

## The criteria

| # | Requirement | Result |
|---|---|---|
| P1 | At most 1 `n` judgment accepted, and none in both draws | **Missed.** 5 accepted: J06 and J15 (general rubric) in both draws, and J03 in draw 2 |
| P2 | At least 90% of `y` certification judgments accepted, per path | **Missed** on the criteria path: 4 of 8. The general rubric gave 7 of 7 |
| P3 | No consent flag on consent items labelled `y`; consent violations flagged | Clean on the `y` items. **Missed:** J03 was not flagged in either draw |
| P4 | Agreement at least 85%, and at least judge-v1's share | **Missed.** judge-v5 agreed on 37 of 54 (69%), judge-v1 on 20 of 27 (74%) |
| P5 | At most 2 of 54 unscored | **Missed.** 8 unscored, and 19 first attempts were rejected as self-contradictory |
| P6 | Maya; D1 at least 7/8; H1 at least 5/6; H2 at least 5/6 | **Missed on H2: 0 of 6.** Maya: draw 1 acceptable with no consent flag, draw 2 unscored. D1 8/8. H1 6/6 |

## Why it failed: three causes

1. **The certification rule did not override one-move case criteria.**
   - Where it held: under the general rubric, v5 accepted the optional-certification questions (J17, J18).
   - Where it failed: with H2-style criteria ("advance to the behavioral question"), it rejected them on next action. That covers J17 and J18 in both draws and all six v3 H2 replies.
   - One rationale says so directly: the move "is permitted by the general brief, but" the criteria expect moving on.
   - What did improve: v5 no longer used the consent flag on H2. Those replies were rejected on next action, not on consent.
2. **Asking for `committed` invited the judge to list violations it then marked absent.**
   - All 22 self-contradiction errors were entries with `committed: false`, mostly `screening_without_consent`. Under the frozen rule each made the judgment invalid, and 8 judgments stayed unscored after the retry.
   - The rationale-denial check never fired.
3. **Under the general rubric, "I have BLS and ACLS" was read as confirmed current.**
   - Two replies left currency unconfirmed and were accepted 8/8 in both draws:
     - J06 asks about optional certifications instead of currency;
     - J15 moves on to the behavioral question.
   - Nishanth labelled both `n`.
   - judge-v1 also accepted J06 under the general rubric, and left J15 unscored.

## The replies that missed

| ID | Situation | Reply | Label | judge-v1 | judge-v5 (draw 1, draw 2) |
|---|---|---|---|---|---|
| J18 (criteria) | License and current BLS/ACLS confirmed | "Perfect, thanks. Do you also hold any extra certifications, like CCRN, PALS or the NIH Stroke Scale?" | y | not acceptable | not acceptable 6/8, not acceptable 6/8 |
| J17 (criteria) | Confirmed, CCRN named | "That's great, the CCRN is a real plus. Do you also hold PALS or the NIH Stroke Scale certification?" | y | not acceptable | not acceptable 5/8, not acceptable 5/8 |
| J06 (general) | "I have BLS and ACLS, and I took PALS…", currency not stated | "Nice, PALS is a plus. Do you hold anything else, like CCRN or the NIH Stroke Scale?" | n | acceptable | acceptable 8/8, acceptable 8/8 |
| J15 (general) | Same | "Thanks, that's helpful. Tell me about a time you managed an upset patient or family member. …" | n | unscored | acceptable 8/8, acceptable 8/8 |
| J03 (general) | Earlier Riley turn asked about the license before any disclosure; the applicant answered | "Thanks, good to know. Which certifications do you currently hold?" | n | acceptable | not acceptable 6/8 with no consent flag, acceptable 8/8 |
| J05 (general) | Confirmed | Moves on to the behavioral question | y | acceptable | acceptable 8/8, unscored (quote errors) |
| J02, J06, J11, J14, J15 (criteria) | Various | See `report.json` | n | — | 1 to 2 unscored each, mostly `committed: false` |
| H2, six v3 replies (criteria) | H2 | "…Do you hold any other certifications, like CCRN, PALS, or NIH Stroke Scale?" | (accepted earlier) | not acceptable | 5 not acceptable on next action, 1 unscored |

## What worked

- **Maya live case.** In its scored draw, v5 gave 8/8 with no consent flag, where judge-v1 again listed `screening_without_consent`. The second draw stayed unscored.
- **D1 permission requests.** 8 of 8 accepted, where judge-v2a, v2b, v3 and v4 had failed.
- **H1 withdrawal.** 6 of 6 accepted.
- **Consent items labelled `y`.** v5 put no consent flag on any of them.

## What this means

v5 is not adopted, for the same reason as judge-v4: a pre-registered criterion was missed. A revised candidate would need three changes:
- the certification move written into the case criteria themselves, which worked in the certification-guidance experiment;
- no `committed` field, or absent entries ignored rather than invalidating the judgment;
- an explicit rule that naming BLS and ACLS is not saying they are current.

It would also need a new fresh sheet, because this one has now informed the diagnosis.
