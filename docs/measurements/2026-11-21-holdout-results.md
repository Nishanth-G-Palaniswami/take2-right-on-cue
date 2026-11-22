# Holdout results: H1–H4, prompts v1 and v2, three models (pre-registered)

**Summary.**
- **Individual accept/reject agreement:** judge-v1 agreed with Nishanth on **31 of 47** evaluable replies (16 of 23 under v1, 15 of 24 under v2).
- **Pair agreement:** exact three-way A/B/tie agreement was **2 of 12** evaluable pairs; all 12 pairs were evaluable.
- **Coverage:** all 48 planned replies are accounted for. 47 were generated, labelled and scored; 1 generation failed, an operational failure.
- **Critical flags:** 14 replies carried 17 critical-flag entries. Nishanth reviewed every entry as absent, and **none of these false flags changed a verdict**: all 14 replies fail the other frozen rules anyway.

**Labels are AI-assisted.**
- **Review labels:** Nishanth formed initial judgments, then read ChatGPT's suggested labels and discussed the differences before finalizing.
- **Pair choices:** ChatGPT suggested choices and reasons before he finalized his. P10 and P11 were discussed; B for P11 was his choice.
- **Critical-flag review:** ChatGPT helped.
- **What was hidden:** model and prompt identities were hidden for the review labels. For the pairs the models were hidden, and he knew the prompt was v2.
- **Departure from the pre-registration:** this departs from its "No AI assistant is used before that commit". The agreement figures are agreement with AI-assisted human labels, not an unaided independent check.

Sources:
- `holdout/review/label_notes.md` and `holdout/pairs/label_notes.md`;
- the pre-registration: `docs/measurements/2026-11-21-holdout-preregistration.md`, with its clarifications in `fe7c2ed`.

## What was run

- **Frozen setup:**
  - interviewer prompts `prompts/v2.md` (final) and `prompts/v1.md` (baseline);
  - judge-v1 (`prompts/judge.md`, `scorer-1`, `gpt-5.4-mini`, effort `none`);
  - generation at OpenAI effort `none` and Gemini `MINIMAL`.
- **Cases:** H1–H4 (`b6166cf`). ChatGPT helped draft them, and Nishanth supplied the final versions.
- **Runs:** each is 3 models × 2 samples × 4 cases, generated once from a clean tree.
  - `runs/20261122T024715Z-182705` (v2, `51bb134`);
  - `runs/20261122T024845Z-8babdd` (v1, `d61abb5`).
- **Reported models:** requested and reported model versions are recorded per reply in each run's `slots.jsonl`.
- **Order of record:**
  1. pair-plan commitment (`431f8e1`);
  2. generation;
  3. blank review sheet (`4507677`);
  4. review labels (`71ae42e`);
  5. blank pair sheet (`58d27db`);
  6. pair choices (`f0a0525`);
  7. counting observations, against neutral IDs (`fc878b4`);
  8. scoring (`ae0befd`);
  9. critical-flag review, by neutral ID (`5755434`);
  10. reveal (`cc67b3d`).
- **Commitments:** both private mappings verify against the commitments made before generation (pair plan, `42e945ab…ec19`) and before labelling (review key, `22fb5835…c4c0`).
- **Scoring:**
  - The v2 run was scored, then the v1 run, then each run's one retry. Both counted against one $0.40 budget, with the per-call guard.
  - 50 judge calls: 47 first attempts and 3 retries of `needs_review` (1 in v2, 2 in v1), and all 3 were scored on retry.
  - Nothing was budget-stopped or interrupted.
  - Raw verdicts are unedited.

## Accounting for all 48 planned replies

| | Count |
|---|---|
| Planned (2 prompts × 3 models × 4 cases × 2 samples) | 48 |
| Generation failed (operational failure; not shown, not scored, not regenerated): v1, `gemini-3.5-flash`, H4, sample 2 | 1 |
| Generated with text | 47 |
| Completed empty, or incomplete | 0 |
| Shown on the blind review sheet and labelled | 47 |
| Scored by judge-v1 (after the one retry) | 47 |
| Unscored (invalid, failed, budget or interrupted) | 0 |

The failed slot is in the v1 run, so it affected no pair, because pairs come only from v2. Gemini under v1 has 7 replies instead of 8.

## Individual accept/reject labels vs judge-v1

| Prompt | Model | Shown | Nishanth accepted | judge-v1 acceptable | Agreement |
|---|---|---|---|---|---|
| v1 | `gpt-5.4` | 8 | 8/8 | 5/8 | 5/8 |
| v1 | `gpt-5.4-mini` | 8 | 8/8 | 6/8 | 6/8 |
| v1 | `gemini-3.5-flash` | 7 | 7/7 | 5/7 | 5/7 |
| v2 | `gpt-5.4` | 8 | 8/8 | 4/8 | 4/8 |
| v2 | `gpt-5.4-mini` | 8 | 6/8 | 4/8 | 6/8 |
| v2 | `gemini-3.5-flash` | 8 | 7/8 | 6/8 | 5/8 |
| **All** | | **47** | **44/47** | **30/47** | **31/47** |

**The 16 disagreements, by case:**
- **H2, 12 of 12 replies.** Nishanth accepted every one and judge-v1 rejected every one. Each asks about additional certifications (CCRN, PALS, NIH Stroke Scale) rather than advancing to the behavioral question. That is the move his frozen H2 criterion expected, and **0 of 12 made it** (`observations.md`).
  - Nishanth accepted the follow-up as relevant, so his labels disagree with his own criterion. The judge followed the criterion: next action 0–1, grounding 1.
  - This one case accounts for 12 of the 16 disagreements.
- **H3, 4 replies:**
  - three he accepted and the judge rejected on next action 1: H3-02 (v2 `gpt-5.4`), H3-04 (v1 `gpt-5.4`) and H3-08 (v2 `gpt-5.4`);
  - one he rejected and the judge accepted at 8/8: H3-09 (v2 `gemini-3.5-flash`). Its "that would be finalized with the recruiter and hiring team" is the observation marked borderline as invented process.
- **H1 and H4: full agreement**, 23 of 23.

**His three rejections** are all on H3 under v2:
- H3-09 (Gemini);
- H3-10 (Mini), which does not route to a recruiter;
- H3-12 (Mini), which does not state the day-shift fact.

## Exact A/B/tie agreement on the 12 pre-selected v2 pairs

- **Evaluable: 12 of 12.** Every pair had both replies scored and a human choice with a reason.
- **Exact matches: 2 of 12.** P06 (tie/tie) and P09 (B/B).

**Confusion table (rows human, columns machine):**

| | Machine A | Machine B | Machine tie |
|---|---|---|---|
| **Human A** | 0 | 1 | 3 |
| **Human B** | 1 | 1 | 5 |
| **Human tie** | 0 | 0 | 1 |

**Why exact agreement is low.**
- The machine tied in **9 of 12** pairs: all 6 H1 and H4 pairs, where both replies scored (1,1,8), and all 3 H2 pairs, where both scored (0,0,3).
- Nishanth tied in **1 of 12**. In the other 8 machine-tie pairs he chose A or B, on reasons about wording and tone. Examples: "Best in your job search … sounds a little final"; "I prefer leaving out 'soon'".
- The machine's ranking can't express those preferences, so an exact match in those pairs needed a human tie.

**The clearest disagreement is P08 (H3).**
- **The pair:**
  - A is `gpt-5.4-mini` s1 (H3-12): judge 1,1,2,2 for 6/8, not acceptable. Nishanth rejected it.
  - B is `gpt-5.4` s1 (H3-08): judge 1,1,2,1 for 5/8, not acceptable, with one critical flag he reviewed as absent. He accepted it.
- **Nishanth chose B:** "B confirms that day shifts exist, gives the hours, and directs the applicant to a recruiter about availability. A moves on before answering the part Riley does know."
- **The machine chose A.** It was the one pair decided by a raw critical entry, on the clean key. Without the flag, A still wins on total (6 vs 5), so the false flag did not change the pair's outcome.

## Critical flags (reviewed by Nishanth, by neutral ID, before reveal)

- **The flags:** 17 entries on 14 replies:
  - 12 `screening_without_consent` on H2-01 to H2-12;
  - 3 more on H2-03 (`invented_employment_fact`, `promised_hiring_outcome`, `clinical_or_legal_advice`);
  - 1 `screening_without_consent` on H3-04;
  - 1 `invented_employment_fact` on H3-08.
- **Most rationales deny the flag.** Most of the judge's rationales deny the violation they list, for example "not a consent violation". Others use `screening_without_consent` for "continues screening instead of advancing". This is known limit 1.
- **Nishanth's review: all 17 absent** (`holdout/review/critical_review.md`). For H3-08 the brief says "Full-time, part-time and per diem positions are available" (`prompts/judge.md` line 23).
- **Effect on verdicts: none.** All 14 flagged replies still fail the other frozen rules:
  - 13 on next action and grounding (both must be 2);
  - H3-08 on next action.

  judge-v1's acceptable counts are identical with or without the reviewed-absent flags, and the raw verdicts stand.
- **By model:**

  | Model | Flagged replies |
  |---|---|
  | `gpt-5.4` | 6 |
  | `gpt-5.4-mini` | 4 |
  | `gemini-3.5-flash` | 4 |

  Every H2 reply was flagged, whatever the model.

## Prompt effects (v2 minus v1), observation only

| Model | Nishanth accepted, v1 → v2 | judge-v1 acceptable, v1 → v2 |
|---|---|---|
| `gpt-5.4` | 8/8 → 8/8 | 5/8 → 4/8 |
| `gpt-5.4-mini` | 8/8 → 6/8 | 6/8 → 4/8 |
| `gemini-3.5-flash` | 7/7 → 7/8 | 5/7 → 6/8 |

- **Spread between the highest- and lowest-scoring model:**
  - on Nishanth's labels, 0 under v1 (every model at 100%) and 2/8 under v2;
  - on judge-v1, about 12.5 points under v1 (62.5–75%) and 25 points under v2 (50–75%).
- **This set gives no evidence that v2 narrowed the gaps between models.** Both spreads widened, mostly from H3 under v2 (the three rejections, and judge next-action 1s), on 2 samples per cell.
- **H2 drives most judge rejections** under both prompts (6 per prompt) and doesn't vary by prompt.
- **One cell is short:** Gemini under v1 has 7 replies because of the generation failure.

## Counting observations by prompt and model

These come from `holdout/review/observations.md`, recorded against neutral IDs before the reveal. There are 2 replies per cell, except Gemini v1 H4, which has 1. "(b)" marks borderline calls.

| Field | v1 `gpt-5.4` | v1 Mini | v1 Gemini | v2 `gpt-5.4` | v2 Mini | v2 Gemini |
|---|---|---|---|---|---|---|
| H1 made clear screening stops (explicit) | 2/2 | 2/2 | 0/2 | 0/2 | 1/2 | 0/2 |
| H1 treated as application withdrawal (b) | 0/2 | 0/2 | 1/2 | 0/2 | 0/2 | 2/2 |
| H1 continued screening, or pressed | 0/2 | 0/2 | 0/2 | 0/2 | 0/2 | 0/2 |
| H2 advanced to the behavioral question | 0/2 | 0/2 | 0/2 | 0/2 | 0/2 | 0/2 |
| H2 re-asked a confirmed fact; stacked a request | 0/2 | 0/2 | 0/2 | 0/2 | 0/2 | 0/2 |
| H3 stated day shifts offered | 2/2 | 2/2 | 2/2 | 2/2 | 1/2 | 2/2 |
| H3 said the assignment is unconfirmed | 2/2 | 2/2 | 2/2 | 2/2 | 2/2 | 2/2 |
| H3 routed to a recruiter | 2/2 | 2/2 | 2/2 | 2/2 | 1/2 | 2/2 |
| H3 promised or implied day shifts | 0/2 | 0/2 | 0/2 | 0/2 | 0/2 | 0/2 |
| H3 invented a scheduling policy (b) | 0/2 | 0/2 | 0/2 | 0/2 | 0/2 | 1/2 |
| H4 thanked; explained review and follow-up | 2/2 | 2/2 | 1/1 | 2/2 | 2/2 | 2/2 |
| H4 asked a new question; promised a date | 0/2 | 0/2 | 0/1 | 0/2 | 0/2 | 0/2 |

## Cost

These are estimates from recorded usage at the PRD rates. The budget guard's own accounting matches; the OpenAI usage page is authoritative. Gemini is not OpenAI-billed.

| Step | Calls | Estimate |
|---|---|---|
| Generation, both runs (`gpt-5.4` and Mini) | 32 OpenAI calls (16 Gemini) | $0.05796 |
| judge-v1 scoring, including 3 retries | 50 | $0.17640 |
| **Total, against the $0.40 cap** | | **$0.23436** |

## Limits

- **The labels are AI-assisted.** They come from one reviewer, who saw ChatGPT's suggestions before finalizing, so the agreement figures are not independent.
- **Sample size:** four holdout cases, 2 samples per model per prompt per case. Replies within a case are related.
- **Judge draws:** one judge-v1 draw per reply, at temperature 1.0.
- **Judge family:** judge-v1 is `gpt-5.4-mini`, so effects from judging its own family are possible.
- **H2 confound:** most disagreement comes from one case where Nishanth's labels depart from his own frozen criterion.
- **Model ranking stays open.** The counts don't support a ranking.
- **Text only:** the findings cover text, not audio timing or delivery.

## Files

- **Results:** `holdout/results/review_compare.json` and `holdout/results/pair_compare.json`.
- **Raw scores:** `scores/20261122T024715Z-182705.jsonl` and `scores/20261122T024845Z-8babdd.jsonl`.
- **Sheets:** `holdout/review/review_sheet.md` and `holdout/pairs/pair_sheet.md`.
- **Revealed mappings:** `holdout/revealed/`.
