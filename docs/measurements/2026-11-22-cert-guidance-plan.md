# Certification guidance: a targeted experiment (pre-registered 2026-11-22)

**Status: frozen before any label and before any judge call.** This is a separate, targeted experiment. It does not change the published holdout results (31 of 47 accept/reject, 2 of 12 exact pairs), the saved runs and scores, `cases/notes.toml`, or production, which stays on judge-v1.

## Question

On H2, judge-v1 rejected all 12 replies that asked once about optional certifications, because H2's frozen criterion expected Riley to move straight to the first behavioral question. Does a criterion that accepts either move fix those rejections, without accepting replies that should fail (a re-ask of a settled fact, a missing currency check, screening before consent)?

## The two configurations

Everything is identical except one criterion text:

| | Current | Candidate |
|---|---|---|
| Judge prompt | judge-v1, `prompts/judge.md` | same |
| Judge model and settings | gpt-5.4-mini, reasoning effort `none`, 1,500 output tokens | same |
| Scorer and decision rule | scorer-1, `decide()` in `src/rightoncue/scoring.py` | same |
| Criteria where the license and required certifications are confirmed | H2's frozen criterion, verbatim | the candidate guidance below |
| Criteria for every other conversation | frozen D2, D1 and H3 criteria | identical to current |

**Current: H2's frozen criterion, verbatim** (`cases/notes.toml`, [H2]):
- Expected next action: "Acknowledge the qualifications and advance to the behavioral question about managing an upset patient or family member."
- Good if: "Recognizes that the applicant has supplied the license and required certification information." / "Asks about the applicant's experience managing an upset patient or family member."
- Fail if: "Re-asks which license or required certifications the applicant holds." / "Asks whether the license is active or whether BLS and ACLS are current." / "Skips the first behavioral question or stacks it with another screening request."

**Candidate: the one change under test:**
- Expected next action: "Acknowledge the confirmed license and required certifications, then take one of two moves; both are acceptable: advance to the behavioral question about managing an upset patient or family member, or ask one focused question about optional certifications the applicant hasn't mentioned (such as CCRN, PALS or NIH Stroke Scale)."
- Good if: "Recognizes that the applicant has supplied the license and required certification information." / "Either asks about the applicant's experience managing an upset patient or family member, or asks once whether the applicant holds optional certifications they haven't mentioned."
- Fail if: "Re-asks which license or required certifications the applicant holds." / "Asks whether the license is active or whether BLS and ACLS are current." / "Asks about an optional certification the applicant has explicitly settled: one they already named, or any others after they said they have no others." / "Stacks either move with another screening request."

The two re-ask rules are kept word for word. The rule against screening before consent lives in judge-v1's prompt and its critical violation `screening_without_consent`, which are unchanged.

**Controls: identical criteria in both configurations,** taken from frozen criteria with only names of the original transcript's details changed:
- currency not stated: D2 ("NIHSS" becomes "PALS");
- screening before consent: D1 ("'now's fine'" becomes "the applicant's yes to the timing question");
- day shift: H3 ("childcare needs" becomes "the applicant's family situation").

Because a control's request is identical in both configurations, any verdict change on a control shows the judge's draw-to-draw noise (temperature 1.0), not the candidate.

## The test set

- **18 fresh replies to 6 fresh conversations,** written by hand for this experiment on 2026-11-22. None comes from a saved run, and no model generated them.
- **They cover:**
  - both acceptable moves once the license and required certifications are confirmed;
  - redundant questions about settled facts;
  - missing certification currency;
  - screening before consent;
  - day-shift controls.
- **The order is shuffled,** under neutral IDs C01 to C18.
- **Public now:**
  - `docs/measurements/cert-guidance/examples.json`, the conversations and replies;
  - `docs/measurements/cert-guidance/label_sheet.md`, the blind sheet.
- **Private until the labels are committed,** in `holdout-private/cert-guidance/` (gitignored):
  - `key.json`: each item's conversation, category and the designer's intended label. It describes the set and is not used in any count.
  - `criteria-current.toml` and `criteria-candidate.toml`: the criteria per conversation.

  Each file holds a random salt. Their SHA-256 hashes are committed in `docs/measurements/cert-guidance/commitment.json`.

## Labels

- **Who labels:** Nishanth labels all 18 replies, `y` or `n`, on the sheet, before seeing the key, the criteria files or any score. The sheet records whether an AI assistant was used.
- **Ground truth:** his labels. The designer's intended labels are not used in any count.
- **Order:** the labels are committed before any judge call.

## Scoring procedure

1. **Reveal.** Copy the three private files to `docs/measurements/cert-guidance/revealed/` and verify them against the commitment (`scripts/cert_guidance_experiment.py verify`).
2. **Score current, then candidate.** One draw each, through `scripts/cert_guidance_experiment.py run`, which uses the scorer's own request builder, validator and `decide()`.
3. **Retry once.** A judgment that needs review or fails is retried once, immediately. It is still unscored if the retry is also invalid.
4. **Cost.** There is a hard cap of $0.60 for the whole experiment, checked before every call against the call's maximum cost (about $0.016). The expected spend is about $0.12 for 36 calls.
5. **Report.** `scripts/cert_guidance_experiment.py report` writes the results to `docs/measurements/cert-guidance/results/`.

## Counting rules

- **Good** means Nishanth labelled the reply `y`; **bad** means `n`.
- **For each configuration:**
  - good replies rejected (judge-v1 "not acceptable");
  - bad replies accepted (judge-v1 "acceptable");
  - unscored replies (no valid judgment after the retry). These are counted separately, never as accepted or rejected.
- **Verdict changes:** every item whose final verdict differs between the two configurations. Changes are split by conversation:
  - on conversations whose criteria changed, they are attributable to the candidate, subject to noise;
  - on conversations with identical criteria, they are noise.

**What would count as support** (descriptive only; this experiment makes no adoption decision): on the conversations whose criteria changed, the candidate rejects fewer good replies than current and accepts no more bad ones. The controls give the noise to compare against.

## Limits

- 18 items and one draw per configuration: the result is directional, not a measurement of the general rate.
- The replies are hand-written. They target the rule's edges and are not a sample of model output.
- The same session designed the set and will run the scoring. The commitment fixes the set, the wording and the procedure before any label or score exists.
- One reviewer labels.
