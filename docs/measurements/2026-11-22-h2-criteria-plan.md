# H2 criteria experiment: plan (frozen before any paid call)

Written on 2026-11-22 on branch `h2-criteria`, after judge-v5 was recorded as not adopted (`e7ad77b`).

**Fixed:**
- **The judge:** judge-v1 (`prompts/judge.md`, sha256 `6df7af13…156af9`) with its model, settings, `scorer-1` contract and `decide()`.
- **The replies:** Riley's prompts and every saved reply.
- **The saved scores:** every score file, including the H2 entry in `cases/notes.toml`. judge-v1 stays live.

**The only change is H2's case instructions.** The old text is H2's frozen entry in `cases/notes.toml`. The proposed text is `docs/measurements/h2-criteria/notes-proposed.toml`. It builds on the certification-guidance candidate (`docs/measurements/cert-guidance/revealed/criteria-candidate.toml`), with the explicit-currency condition, the clarify branch, Nishanth's currency equivalents and the several-examples rule added.

## Where the change applies

| Scoring path | Case instructions the judge gets | Changed by this experiment? |
|---|---|---|
| Saved H2 replies scored with `--notes docs/measurements/h2-criteria/notes-proposed.toml` (this experiment's H2 regression) | The proposed H2 criterion | Yes, in this experiment only |
| Every historical score; the saved comparison page; `next-turn score` with the default `--notes cases/notes.toml` | The old H2 criterion | No |
| Live "Run it yourself" with a saved case file left unedited | That case's entry in `cases/notes.toml` | No |
| Live pasted or edited transcripts, and practice calls | No case instructions: the general rubric in judge-v1's prompt | No |
| This experiment's fresh items | The old text, the proposed text, or none (general rubric). The script supplies them | Test only |

**Adopting the proposed text would be a separate decision.**
- One route is editing `cases/notes.toml`. That changes the frozen holdout criterion, so the published 31 of 47 would need a note.
- The other route is a general-rubric rule, which judge-v5 tried and failed.
- **The saved-H2 result is reported apart from the general-rubric results**, which stand for today's live path.

## Old and proposed instructions, as the judge receives them

| | Old: H2 in `cases/notes.toml` | Proposed: `notes-proposed.toml` |
|---|---|---|
| Expected next action | Acknowledge the qualifications and advance to the behavioral question about managing an upset patient or family member. | Acknowledge what the applicant has explicitly confirmed. Once the applicant has explicitly confirmed an active license and that BLS and ACLS are current, in those words or a clear equivalent such as "I renewed both last month" or "both are valid through next March", either of two moves is acceptable: advance to the behavioral question about managing an upset patient or family member, or ask one focused question about an optional certification the applicant hasn't addressed. One question that names several examples, such as "Do you also hold CCRN, PALS, or NIH Stroke Scale?", is one request. If the applicant hasn't said, explicitly or in a clear equivalent, that BLS and ACLS are current, ask one focused question about whether they are. |
| Good if | Recognizes that the applicant has supplied the license and required certification information. · Asks about the applicant's experience managing an upset patient or family member. | Recognizes what the applicant has explicitly confirmed. "My BLS and ACLS are both current" settles currency, and so does a clear equivalent such as "I renewed both last month" or "both are valid through next March". · Once currency is settled, either asks about the applicant's experience managing an upset patient or family member, or asks once about an optional certification the applicant hasn't addressed. · Until currency is settled, for example when the applicant lists certifications they hold alongside a course taken years ago, asks once whether BLS and ACLS are current. |
| Fail if | Re-asks which license or required certifications the applicant holds. · Asks whether the license is active or whether BLS and ACLS are current. · Skips the first behavioral question or stacks it with another screening request. | Re-asks a fact the applicant has explicitly settled: whether the license is active, which required certifications they hold, or whether BLS and ACLS are current. · Asks about an optional certification the applicant has already addressed. · Moves on, or asks about optional certifications, before the applicant has said, explicitly or in a clear equivalent, that BLS and ACLS are current. · Stacks two requests in one turn, such as an optional-certification question and the behavioral question. Naming several example certifications in one question is not stacking. |

**What reaches the judge, checked offline with the scorer's own `plan_scoring`, the function `next-turn score` calls.** The check used the six v3 H2 replies (run `20261123T004511Z-b08ea8`), with `--case H2`.
- **The case block.** Each request's `CASE CRITERIA` block is exactly the old text with `cases/notes.toml`, and exactly the proposed text with `notes-proposed.toml`.
- **Everything else is identical:** the judge instructions (judge-v1, `6df7af131725`), the model, the settings and the `scorer-1` schema.
- **Request hashes.** Every request hash changes between the two configurations.
- **The historical scores used the old text.** All 7 saved judge-v1 H2 judgments for those replies carry the exact request hash of today's old request.
- **The script builds the same requests.** `scripts/h2_criteria_experiment.py` refuses to run unless its H2 requests are byte-identical to `plan_scoring`'s.

## What is tested

**Fresh items (the test).**
- 19 new items in 6 conversations, written by a separate agent from Nishanth's description of the rule. The agent did not see the proposed text.
- The first 13 came from the original brief. 6 more came after Nishanth added currency equivalents and the three-example question. The original 13 are unchanged.
- The items are shuffled under neutral IDs K01–K19 on `docs/measurements/h2-criteria/review_sheet.md`.
- The items, intents and key are in `holdout-private/h2-criteria/` (gitignored), committed by SHA-256 in `commitment.json`, which also pins both criteria files.
- **Nishanth's labels are the truth, and they are committed before any call.**

| Conversation kind | What the applicant says | Replies written |
|---|---|---|
| explicit_plain | active license; "my BLS and ACLS are both current" | moves on; one optional-certification question; re-asks currency; optional question stacked with the behavioral question |
| explicit_named | active license; recertified last month, "good for another two years"; holds CCRN | asks about a different optional certification; asks about the CCRN just named; re-asks the license |
| explicit_equiv_valid | active license; BLS and ACLS "valid through" a future date | one question naming three optional certifications; moves on; re-asks currency |
| explicit_equiv_renewed | active license; "renewed both" a few weeks ago | one question naming three optional certifications; stacked; re-asks currency |
| mixed_a, mixed_b | Tobias-like: BLS and ACLS held, plus a course taken years ago; currency never stated | asks whether BLS and ACLS are current; moves on; asks about optional certifications instead |

**Known items (already seen, reported apart).**
- These are the judge-v5 sheet's 9 certification items, including Tobias's own conversation, with Nishanth's committed labels.
- They are scored old and new.
- Their general-rubric verdicts are judge-v1's saved records from the judge-v5 run, so they need no new call.

**H2 regression (the saved-H2 path).**
- The six saved v3 H2 replies, scored with the proposed text in 2 draws.
- The old baseline is judge-v1's saved records for those same requests: 0 accepted, 6 rejected, 0 unscored, with no new call.

**Configurations and draws.**

| Config | Instructions | Draws |
|---|---|---|
| new | proposed text | 2 |
| old | H2's frozen text | 1 |
| general | none, as for pasted transcripts | 1, fresh items only |

- Each judgment that needs review or fails gets one immediate retry.
- Unscored judgments are counted separately, never as agreement.

## Pass criteria for the proposed text (all must hold)

| # | Criterion | Requirement (fresh items, new config, by Nishanth's label) |
|---|---|---|
| H1 | The move-or-ask rule generalizes | On explicit conversations labelled `y`, at most 1 scored judgment rejected |
| H2 | The Tobias boundary | On mixed conversations labelled `n`, at most 1 judgment accepted, and none accepted in both draws |
| H3 | Clarifying is accepted | On mixed conversations labelled `y`, at most 1 scored judgment rejected |
| H4 | Settled facts and stacking still fail | On explicit conversations labelled `n`, no judgment accepted |
| H5 | H2 regression (saved-H2 path) | At least 10 of 12 judgments accepted (6 replies × 2 draws); unscored counts as not accepted |
| H6 | Coverage | At most 15% of the 38 new fresh judgments unscored |

**Reported for every set and config:** accepted, rejected and unscored counts, plus agreement with the labels. The report also gives each item's verdicts under old, new and general, and the critical entries listed under new.

## Exposure

- Nishanth has seen the six v3 H2 replies and their verdicts.
- The known items, Tobias's conversation, and judge-v5's verdicts on them are all known.
- The lead wrote the proposed text after seeing judge-v5's failures and the certification-guidance results.
- So only the fresh items test generalization.
- The fresh sheet's design is described in the table above. Nishanth is asked to label before reading it.

## Cost

The planning figure is $0.0035 per judge-v1 call: the judge-v1 reference calls in the judge-v5 run averaged $0.0035, and the recorded mean is $0.003468. The guard's worst-case bound is $0.016918 per call.

| Set | First attempts | Expected, with ~20% retries |
|---|---|---|
| Fresh: new (38), old (19), general (19) | 76 | about $0.32 |
| Known: new (18), old (9) | 27 | about $0.11 (optional) |
| H2 regression: new | 12 | about $0.05 |
| **Total** | **115** | **about $0.48** |

- **Hard cap: $0.65**, checked before every call across all results files. Without the optional known set, the cap would be $0.50.
- No call is made until Nishanth has labelled the 19 items and approved the run.

## Addendum: the labels (before any paid call)

- **Description, in Nishanth's words: AI-drafted labels reviewed in full by Nishanth.**
  - ChatGPT drafted the 19 labels and reasons, using the guidance Nishanth had given in earlier reviews.
  - Nishanth then personally checked all 19 transcripts, proposed replies, labels and reasons against the rubric.
- **The count:** 8 `y` and 11 `n`, each with a reason.
- **What the criteria measure.** Wherever H1–H6 above say "Nishanth's label", read these reviewed labels. Results are reported as agreement with AI-drafted labels reviewed in full by Nishanth, not as independent human labels.
- **The sheet.** The shown text (headings, conversations, replies) matches the committed sheet, as `verify` confirms. The sheet is committed before any judge call.
