# H2 criteria, round 2: results

**Verdict: the round-2 text misses four of its ten pre-registered criteria (A2, A4, A6, R2), so it is not adopted.**
- judge-v1, Riley's prompt, `cases/notes.toml` and every historical score are unchanged.
- Round 1 (`docs/measurements/2026-11-22-h2-criteria-results.md`, five passes and one failed check) stays in the report.

**Sequence.**
- `e3a110b`: text, paired sheet, script and plan.
- `8511de2`: labels committed before any call.
- `ca945c4`: A7 amended before scoring.
- This commit: scoring and reveal. `revealed/frames.json` and `revealed/key.json` match `commitment.json`.
- Every record carries the committed script's SHA-256 (`aa08b5cb…`).

**Labels.** In Nishanth's words on the sheet: "Nishanth reviewed all 30 replies himself and dictated his judgments without reading ChatGPT's draft." His AI-assistance answer is "No". 15 `y`, 15 `n`.

**Spend.** $0.503692 of the $0.65 cap, over 132 calls (120 judgments plus retries). Every planned job finished, in one process.

## The criteria

The readout is the next-action score: 2 is right where the label is `y`, below 2 is right where it is `n`.

| # | Requirement | Result |
|---|---|---|
| A1 | Confirmations recognized (C, `y`) | **Met.** 20 right, 0 wrong, 0 unscored |
| A2 | Naming plus past training leads to clarifying (U, `n`) | **Missed.** 8 right, 2 wrong, 2 unscored. F2's "moves on" scored 2 in both draws |
| A3 | Clarifying accepted (U and P, `y`) | **Met.** 10 right, 0 wrong |
| A4 | Only one clear: ask about the other (P, `n`) | **Missed.** 3 right, 3 wrong, 2 unscored |
| A5 | A confirmed status not re-asked (C, `n`) | **Met.** 10 right, 0 wrong |
| A6 | At least 12 of 15 pairs right throughout | **Missed.** 9 of 15 |
| A7 | Fewer `n` items scored 2 than with round 1's text (amended: a tie at zero passes) | **Met.** 5 of 20 against 3 of 10 (25% against 30%), a small difference |
| R1 | The six saved H2 replies: at least 10 of 12 accepted | **Met.** 10 accepted, 2 rejected, 0 unscored |
| R2 | Tobias and round 1's Tobias-like items: at most 2 of 18 wrong or unscored | **Missed.** 15 right, 1 wrong, 2 unscored |
| C1 | At most 9 of 60 unscored | **Met.** 4 unscored |

## Verdicts: accepted, rejected and unscored

| Set | Text | Accepted | Rejected | Unscored |
|---|---|---|---|---|
| Fresh pairs (60 judgments) | round 2 | 35 | 21 | 4 |
| Fresh pairs (30 judgments) | round 1 | 18 | 12 | 0 |
| Saved H2 replies | round 2 | 10 | 2 | 0 |
| Saved H2 replies | round 1 (its records) | 12 | 0 | 0 |
| Saved H2 replies | old H2 text (saved judge-v1 records) | 0 | 6 | 0 |
| Tobias (6 judgments) | round 2 | 2 | 3 | 1 |
| Round 1's Tobias-like items (12 judgments) | round 2 | 5 | 6 | 1 |

## What changed, and what didn't

**The documented failures improved a lot, though R2's threshold was still missed.** Next-action readout, round-1 text against round-2 text:
- Tobias went from 2 right and 4 wrong to 5 right, 0 wrong and 1 unscored.
- Round 1's six Tobias-like items went from 5 right and 7 wrong to 10 right, 1 wrong and 1 unscored.

**The optional-certification reply mostly respects the boundary.** Where Nishanth labelled it `n`, it scored 2 in 1 of 9 scored judgments.

**Moving on still slips through.**
- Where Nishanth labelled the "moves on" reply `n`, it scored 2 in 4 of 7 scored judgments, with 3 unscored. Round 1's text did the same on those items (2 of 5).
- The judge is inconsistent on the same item. One draw applies the rule ("did not explicitly confirm that either is current… moving straight to a behavioral question is premature"). Another says the credentials are "effectively confirmed current enough to move forward".

**Unscored judgments decided two criteria.**
- judge-v1 quoted a transcript turn with its "Applicant:" label, or quoted the reply with "?" where it says ".". The quote check then failed, a known judge-v1 limit.
- These cost three pairs in A6 and two of R2's three misses.

**H2.** The two rejections are the same Gemini reply in both draws. Its acknowledgment restates the applicant's license and certifications, and the round-2 text's "re-asks a settled fact" was applied to that restatement.

## What this means

- **What wording alone can and can't do.** Changing H2's case wording fixes the optional-certification question and most of round 1's documented failures. It does not make judge-v1, at temperature 1.0 with no reasoning effort, reliably refuse to move on when currency is unconfirmed.
- **Neither round's text is adopted.** judge-v1 and `cases/notes.toml` stay as they are.
- **What a further attempt would need:** a change outside the case wording, such as reasoning effort or a deterministic check, and a new fresh sheet.
