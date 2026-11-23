# H2 criteria, round 2: plan (frozen before any paid call)

Written on 2026-11-22 on branch `h2-criteria-2` (from `c3d78e1`).

**Fixed:**
- judge-v1 (`prompts/judge.md`, sha256 `6df7af13…156af9`) with its model, settings, `scorer-1` and `decide()`;
- Riley's prompt v3, `cases/notes.toml`, and every saved run and score.

Round 1 (`docs/measurements/2026-11-22-h2-criteria-results.md`) stays in the report: five checks passed and one failed, the Tobias boundary.

## The change: H2's case instructions only

**Text.** The proposed text is `docs/measurements/h2-criteria-2/notes-proposed.toml`. Compared with round 1's text, which the judge loosened by quoting "clear equivalent":
- **Non-examples first:** naming a credential ("I have", "I hold", "I've got") or past training does not confirm it.
- **A closed list of confirmations**, with no "such as": "both are current"; "both are up to date"; a clear yes to a direct question about whether they are current; a recent renewal; an expiration date still ahead.
- **Each credential is judged on its own.** If only one is confirmed, Riley asks about the other.
- **Kept from round 1:** moving on or one focused optional-certification question once both are confirmed; one question naming several examples is one request; re-asks and stacking fail.

**Where it applies.** This is the same as round 1. The text is used only where H2's case instructions are passed: the saved-H2 path with `--notes`, and this experiment. Pasted transcripts and practice calls use the general rubric and are unchanged.

**What reaches the judge**, checked offline with the scorer's own `plan_scoring` on the six saved v3 H2 replies (`--case H2`):
- each request carries this text in its `CASE CRITERIA` block;
- the judge-v1 instructions are byte-identical;
- the script refuses to run unless its H2 requests are byte-identical to `plan_scoring`'s.

H2's applicant says "my BLS and ACLS are both current. I renewed them together in September", which counts under the new text.

## The paired fresh items

- **Authorship.** A separate agent wrote 5 frames from Nishanth's description of the rule. It did not see the proposed text.
- **Construction.** Each frame is a conversation identical in every turn except the applicant's last, which comes in two versions. Each frame has three neutral replies, used word for word after both versions.
- **Size.** That makes 15 pairs and 30 items.
- **Built in code.** The items are built as frame × version × reply by `scripts/h2_criteria2_experiment.py`, which asserts that each pair's reply and earlier turns are identical.
- **Only cells whose verdict should flip.** "Asks about both when one is already confirmed" was left out, because Nishanth hasn't ruled on it.

| Frame | Version C (confirmed) | Other version | Replies (each used after both versions) |
|---|---|---|---|
| F1 | "both are current" | U: names BLS and ACLS, mentions past training | moves on; one optional question; asks whether both are current |
| F2 | "both are up to date" | U | moves on; one optional question; asks whether both are current |
| F3 | a clear yes to Riley's direct question | U: names them and past training, no yes | moves on; one optional question; asks whether both are current |
| F4 | renewed both recently | P: BLS renewed recently, ACLS only from nursing school | moves on; one optional question; asks only about ACLS |
| F5 | both valid until a future date | P: ACLS valid until then, BLS only from nursing school | moves on; one optional question; asks only about BLS |

**Labels: Nishanth's own, made blind and without an AI assistant.** He decided this before the sheet was built.
- The 30 items are shuffled under neutral IDs P01–P30 on `docs/measurements/h2-criteria-2/review_sheet.md`.
- The frames and the key are in `holdout-private/h2-criteria-2/` (gitignored), committed by SHA-256 in `commitment.json`. The commitment also pins all three criteria files.
- Nishanth is asked to label before reading this table.

## What is scored

| Set | Items | Configs |
|---|---|---|
| fresh | the 30 paired items | **new** (this round's text), 2 draws; **prev** (round 1's text, for attribution), 1 draw |
| h2 | the six saved v3 H2 replies | new, 2 draws. Old baseline: the saved judge-v1 records. Prev baseline: round 1's records |
| tobias | the judge-v5 sheet's Tobias conversation (J06, J12, J15), with Nishanth's committed labels | new, 2 draws. Prev baseline: round 1's records |
| round1 | round 1's six Tobias-like items, including K01, K03, K14 and K16, with their committed labels | new, 2 draws. Prev baseline: round 1's records |

**How it runs.** A judgment that needs review or fails gets one immediate retry. Every pass runs in one process (`run-all`), only after the labels are complete and only with the script committed and unmodified. Each record carries the script's SHA-256.

## The readout

**The pre-registered readout is each judgment's next-action score.**
- 2 means the move is right here; this is correct where the label is `y`.
- Below 2 means it is not; this is correct where the label is `n`.
- Unscored judgments are counted separately.

**Why the next-action score.** It isolates the wording effect. In round 1, one rejected judgment still said currency was confirmed. Verdicts (accepted / rejected / unscored) are reported beside the readout for every set and config.

## Pass criteria (all must hold)

| # | Requirement (fresh items, new text, by Nishanth's labels and version) | Shows |
|---|---|---|
| A1 | C versions labelled `y`: next-action score wrong on at most 1 scored judgment | Every listed confirmation is recognized |
| A2 | U versions labelled `n`: wrong on at most 1, and no item scored 2 in both draws | Naming and past training lead to clarifying |
| A3 | U and P versions labelled `y`: wrong on at most 1 | Clarifying is right when status is unclear |
| A4 | P versions labelled `n`: wrong on at most 1, and no item scored 2 in both draws | When only one is clear, Riley asks about the other |
| A5 | C versions labelled `n`: wrong on none | A confirmed status is not re-asked |
| A6 | At least 12 of the 15 pairs right on both versions in both draws (unscored counts as wrong) | The verdict follows the applicant's wording |
| A7 | On U and P items labelled `n`, a smaller share scored 2 under the new text than under round 1's | The improvement is due to the wording, not easier items |
| R1 | The six saved H2 replies: at least 10 of 12 judgments accepted | H2 is still fixed |
| R2 | Tobias and round 1's Tobias-like items: at most 2 of 18 judgments wrong or unscored, and no `n` item scored 2 in both draws | The documented failure is fixed |
| C1 | At most 15% of the 60 fresh new-text judgments unscored | Coverage |

## Exposure

- Nishanth has seen H2's six replies, Tobias's conversation, and round 1's items with their verdicts.
- The lead wrote this round's text after reading round 1's failures, so the regression sets are not held out.
- Only the fresh pairs test the wording.

## Cost

- 120 first attempts: fresh 60 + 30, H2 12, Tobias 6, round 1 12.
- About **$0.50** expected, with ~20% retries, at $0.0035 per judge-v1 call. The worst-case bound is $0.016894 per call.
- **Hard cap: $0.65**, checked before every call.
- No call is made until Nishanth has labelled the 30 items and approved the spend.

## Addendum: independent check (before labels and any paid call)

**Result.** The verifier passed the script against this plan:
- the pairing holds;
- the H2 requests match `plan_scoring`;
- the job counts are 60, 30, 12, 6 and 12;
- the cap, the retry and the label gate behave as specified;
- every criterion flips exactly at its threshold.

**Notes it raised:**
- The label check needs this sheet committed, so it is committed before labelling.
- **Open for Nishanth before the paid run:** A7 reads "smaller" strictly. If round 1's text also scores every fresh U or P item labelled `n` correctly, A7 fails even when the new text is perfect.
- In A1–A5, unscored judgments are not counted as wrong; C1 caps them. In A6 they count as wrong.
- The results files are write-once, so a crash mid-run leaves partial files that a rerun refuses.
- The full report prints the P-ID mapping. It is not shared before labelling.
