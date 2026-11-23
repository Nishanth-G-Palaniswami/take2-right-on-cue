# H2 criteria experiment: results

**The result.** The proposed H2 text fixes H2 itself, but it misses the pre-registered Tobias boundary (criterion H2), so it does not pass as written.
- judge-v1 is unchanged and stays live.
- `cases/notes.toml` and every historical score are unchanged.

**Sequence.**
- `500bc35`: plan, proposed text and blind sheet.
- `879c38a`: labels committed before any judge call.
- This commit: scoring and reveal. `revealed/items.json` and `revealed/key.json` match `commitment.json`. Both criteria files are unchanged since the commitment.

**Labels.** AI-drafted labels reviewed in full by Nishanth: 8 `y`, 11 `n`.
- ChatGPT drafted them using the guidance Nishanth had given in earlier reviews.
- Nishanth then personally checked all 19 transcripts, replies, labels and reasons.

**Spend.** $0.471435 of the $0.65 cap, over 126 calls (115 judgments plus retries). Every planned job finished. The records are in `h2-criteria/results/` and the report is `h2-criteria/report.json`.

**Run note.** The scoring process outlived the Claude session that started it and finished every pass on its own.
- The lead briefly had an uncommitted `--resume` option in the script, tested only in scratch. It was reverted while the run was still going.
- With the flag unset its code path is identical, and every record has the committed format (no record is a dry run or a resume).

## The criteria

| # | Requirement (fresh items, proposed text) | Result |
|---|---|---|
| H1 | Explicit-currency conversations labelled `y`: at most 1 rejected | **Met.** 12 accepted, 0 rejected, 0 unscored |
| H2 | Tobias-like conversations labelled `n`: at most 1 accepted, none in both draws | **Missed.** 7 accepted, 1 rejected, 0 unscored. K01, K03 and K16 were accepted in both draws |
| H3 | Tobias-like conversations labelled `y`: at most 1 rejected | **Met.** 4 accepted, 0 rejected |
| H4 | Explicit conversations labelled `n`: none accepted | **Met.** 0 accepted, 13 rejected, 1 unscored |
| H5 | Saved-H2 regression: at least 10 of 12 accepted | **Met.** 12 accepted, 0 rejected, 0 unscored |
| H6 | At most 15% of the 38 judgments unscored | **Met.** 1 unscored (3%) |

## Accepted, rejected and unscored, kept separate

**The saved-H2 path.** These are the six saved v3 H2 replies, scored with H2's case instructions.

| Instructions | Accepted | Rejected | Unscored |
|---|---|---|---|
| Old H2 text (saved judge-v1 records) | 0 | 6 | 0 |
| Proposed text, 2 draws | **12** | 0 | 0 |

**The fresh items** (19 items):

| Instructions | Accepted | Rejected | Unscored | Agreement with the labels |
|---|---|---|---|---|
| Old H2 text, 1 draw | 4 | 14 | 1 | 10 of 19 |
| Proposed text, 2 draws | 23 | 14 | 1 | **30 of 38** |
| No case instructions: general rubric, which is today's live path for pasted transcripts | 10 | 6 | 3 | 13 of 19 |

**By group, on the fresh items** (accepted / rejected / unscored):

| Group | Old | Proposed | General rubric (live path) |
|---|---|---|---|
| Explicit currency, labelled `y` (moving on; one optional question, including three-example questions; "valid through" and "renewed" wording) | 2 / 4 / 0 | **12 / 0 / 0** | 5 / 0 / 1 |
| Explicit currency, labelled `n` (re-asks, a named certification, stacking) | 0 / 6 / 1 | **0 / 13 / 1** | 0 / 6 / 1 |
| Tobias-like, labelled `y` (asks whether current) | 0 / 2 / 0 | **4 / 0 / 0** | 2 / 0 / 0 |
| Tobias-like, labelled `n` (moves on, or asks about extras instead) | 2 / 2 / 0 | **7 / 1 / 0** | 3 / 0 / 1 |

**Known items** (the judge-v5 sheet's 9 certification items, already seen, including Tobias's own conversation):

| Instructions | Accepted | Rejected | Unscored | Agreement |
|---|---|---|---|---|
| Old | 2 | 7 | 0 | 5 of 9 |
| Proposed, 2 draws | 12 | 6 | 0 | 14 of 18 |
| General rubric (saved judge-v1 records from the judge-v5 run) | 5 | 3 | 1 | 7 of 9 |

The proposed text accepted Tobias's own "moves on" and "asks about extras instead" replies in all 4 judgments.

## Why the boundary failed

On every Tobias-like miss, judge-v1 read "I've got BLS and ACLS" or "I hold BLS and ACLS" as confirming they are current.
- One rationale says "confirmed current BLS/ACLS by saying they hold them".
- Another says "in a clear equivalent".

So the "clear equivalent" wording may have made the judge looser on exactly this boundary. The other paths miss it too: the old text accepted 2 of 4, and the general rubric 3 of 4 (plus 1 unscored).

## What it fixed and what it didn't

**Fixed: H2.**
- One focused question about optional certifications, after an explicit or clearly equivalent confirmation, is now accepted: 12 of 12 judgments, against 2 of 6 under the old text. This includes three-example questions and the "valid through" and "renewed" wordings.
- The six saved H2 replies went from 0 of 6 to 12 of 12.
- Re-asks, a certification already named, and stacking stayed rejected.

**Not fixed: the boundary.** The judge still treats holding BLS and ACLS as having current BLS and ACLS.

## Where this applies

These results are for H2's case instructions on the saved-H2 path, and for the same text supplied in this experiment. The live path for pasted transcripts and practice calls uses the general rubric and is unchanged. Its numbers above are a reference only.

## Possible next step (not done)

Narrow the currency wording:
- say plainly that holding, having or having "got" BLS and ACLS is not saying they are current;
- keep only time-anchored equivalents, such as "renewed last month" or "valid through" a future date.

That would need a new fresh check, because these items now inform the fix.
