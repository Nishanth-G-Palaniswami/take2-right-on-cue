# judge-v5: candidate, fresh check and pass criteria (frozen before any judge-v5 call)

Written on 2026-11-22, on branch `judge-v5`, before any fresh item existed and before any paid call.

**Fixed:**
- Riley's prompt v3.
- The case criteria in `cases/notes.toml`.
- Every saved run and score file.
- judge-v1, which stays the production default (`DEFAULT_JUDGE_VERSION`) until v5 passes this check and Nishanth reviews it.

## The candidate

`prompts/judge-v5.md` (sha256 `0046e009f9059c2f93fe932dcb1be82d34f360792cbf521476cd0a11e1f02519`) is judge-v1 plus the changes below. Run `diff prompts/judge.md prompts/judge-v5.md` to see them.
- **Model and settings:** the same as judge-v1. That is `gpt-5.4-mini`, reasoning effort `none`, 1,500 output tokens, and temperature left at the API default of 1.0.
- **Decision rule:** `decide()` is unchanged.

1. **Certifications.** These rules sit in the call brief, so they apply both with case criteria and under the general rubric used for pasted transcripts.
   - **Two right moves.** Once the license is confirmed and BLS and ACLS are said to be current, either of these is right:
     - moving on to the first behavioral question;
     - asking one focused question about optional certifications the applicant hasn't mentioned.
   - **Criteria precedence.** The rule holds even when the case criteria name only moving on. H2's frozen criterion does exactly that, and `cases/notes.toml` stays unchanged.
   - **Still wrong:**
     - asking again about anything already confirmed;
     - asking about a certification the applicant already named;
     - combining the optional question with the behavioral question;
     - moving on, or asking about optional certifications, before BLS and ACLS are confirmed current.
2. **Consent, judged for the new reply in context.**
   - **Earlier turns are context.** An earlier Riley turn that screened too soon is context. A reply that pauses to disclose, offer to stop, or ask permission is a valid recovery. A reply that keeps screening is a violation.
   - **Not screening:** saying screening questions will follow, while asking permission. This is also added as one line under "Asks one thing at a time", for D1.
   - **After permission:** a later screening question is judged under next action, not consent.
   - **Excerpts:** when the conversation doesn't include Riley's introduction, permission is not treated as missing unless the conversation shows it wasn't given, was declined or was withdrawn. Nishanth approved this rule on 2026-11-22.
3. **Self-contradiction is invalid.**
   - The judge lists only the violations the reply commits, each with `committed: true` (new output contract `scorer-3`).
   - Two kinds of listed entry make the judgment `needs_review`, which then gets the existing single retry:
     - an entry with `committed` false;
     - an entry whose own rationale says the reply doesn't commit it.
   - **The rationale check.** `scoring.rationale_denies_violation` is a backstop. It was calibrated in-sample on all 72 critical entries judge-v1 recorded before v5: 35 deny their violation, and 37 assert one, in the lead's reading. It catches all 35 and flags none of the 37 (`tests/fixtures/judge_v1_critical_entries.json`).
4. **Speaker labels in quotes (Nishanth's choice, 2026-11-22).**
   - scorer-3 ignores a leading "Riley:" or "Applicant:" on a transcript quote before matching it. The judge's instructions are unchanged.
   - Under judge-v1 these quotes left replies unscored, for example 4 of 18 in the certification check.

Offline tests: `tests/test_scoring_v5.py`.

## What has already been seen (exposure)

- **H2.**
  - Nishanth has seen the 12 v1/v2 H2 replies, with his labels and the judge-v1 verdicts.
  - He has also seen the six v3 H2 replies and their judge-v1 verdicts. Those six items on `docs/measurements/v3-retest-review/review_sheet.md` are therefore not blind for him.
  - H2 shaped the certification rule.
- **Maya (hosted demo).**
  - Nishanth reported this case from a live run and has seen its reply and verdict: judge-v1 gave "not acceptable · 8/8", listing `screening_without_consent` while its rationale described a pause for renewed consent.
  - It shaped the consent rule.
  - It is stored in `docs/measurements/judge-v5/regression/maya-live.json`. No local record of that run exists; the verdict is as Nishanth reported it.
- **D1.** Mini's two v2 D1 replies were rejected by judge-v2a, v2b, v3 and v4. judge-v1 accepted them.
- **The lead.** I wrote v5 having seen all of the above and the 72 calibration entries.
- **So none of these is a held-out test.** The fresh items below are the blind part of this check.

## The fresh check

**The items.**
- A separate agent writes 18 new items: 7 conversations, each with one or more proposed Riley replies.
- It works only from these inputs:
  - Nishanth's two paragraphs on certifications and consent;
  - the excerpt rule;
  - the call brief;
  - the structure below.
- It does not see `prompts/judge-v5.md`.
- **Restrictions:**
  - no names already used in a test case;
  - no conversation that re-skins D1–D4, H1–H4, the certification-check conversations or the prompt-v3 conversations;
  - no applicant who objects to being recorded (the Maya situation).

| Conversation kind | Replies the author is asked to write |
|---|---|
| Certification: license confirmed, BLS and ACLS stated current | moves on; one optional-certification question; re-asks something confirmed; optional question stacked with the behavioral question |
| Certification: certifications listed, currency not stated | asks once whether BLS and ACLS are current; asks about optional certifications instead; moves on |
| Certification: BLS and ACLS current, and an optional certification named | asks about the one already named; one question about a different optional certification |
| Consent: availability given, no disclosure yet | disclosure and permission; disclosure and permission mentioning that screening questions follow; asks about the license |
| Consent: an earlier Riley turn asked the license with no disclosure, and the applicant answered | pauses, discloses and asks permission; carries on screening; asks permission and a certification question in one turn |
| Consent: permission given, then withdrawn | acknowledges and stops; one more quick screening question |
| Consent: an excerpt that starts mid-call, without the introduction | an appropriate next turn |

**The blind sheet and the key.**
- The 18 items are shuffled under neutral IDs (J01–J18) on `docs/measurements/judge-v5/review_sheet.md`.
- The sheet hides the author's intent, all criteria and all scores.
- The items, the author's intents and the ID key live in `holdout-private/judge-v5/` (gitignored), committed by SHA-256 in `docs/measurements/judge-v5/commitment.json`.
- **Nishanth's y/n labels are the truth.**

**Criteria paths.**
- **Certification items** are judged twice: once with one-move case criteria, and once under the general rubric. The one-move criteria are H2's frozen text for the confirmed conversations, and D2's, made generic, for the currency conversation.
- **Consent items** are judged under the general rubric only. D1's real criteria are covered by the regression set.

**Draws.**
- judge-v5: 2 draws per item and criteria path, which is 27 item-paths and 54 judgments.
- judge-v1: 1 draw per item and path, as the reference: 27 judgments.
- A judgment that needs review or fails gets one immediate retry within its draw. Anything still unscored stays unscored. It is never counted as agreement, and denominators do not shrink.

**Known regression cases (exposed, reported separately).**
- **Maya (live):** v5, 2 draws, plus judge-v1, 1 draw.
- **D1:** the four v2 D1 replies from `runs/20261121T023359Z-455c41`, with D1's criteria; v5, 2 draws.
- **H1 and H2:** the six v3 H1 replies and the six v3 H2 replies from run `20261123T004511Z-b08ea8`, with their frozen criteria; v5, 1 draw.

## Pass criteria (all must hold)

| # | Criterion | Requirement |
|---|---|---|
| P1 | No false acceptances | Of v5's scored judgments on items Nishanth labels `n`, at most 1 is acceptable. No `n` item-path is acceptable in both draws. |
| P2 | The certification fix, on both paths | On certification items labelled `y`, v5 accepts at least 90% of its scored judgments, separately under the one-move criteria and under the general rubric. |
| P3 | Consent | v5 lists `screening_without_consent` on no scored judgment of a consent item labelled `y`. On the items the author wrote as screening before permission or after a withdrawal, among those labelled `n`, it lists it on every scored judgment but at most one. |
| P4 | Overall agreement | v5 agrees with the labels on at least 85% of all 54 judgments, unscored counting as disagreement, and on at least as large a share as judge-v1's 27. |
| P5 | Unscored | At most 2 of the 54 v5 judgments are unscored after the retry. Every first attempt rejected as self-contradictory is reported. |
| P6 | Known regressions | **Maya:** both draws scored, and neither lists `screening_without_consent`. Acceptability is not required; directness is scored on the dimensions. **D1:** at least 7 of 8 judgments acceptable, none listing `screening_without_consent`. **H1:** at least 5 of 6 acceptable. **H2:** at least 5 of 6 acceptable under H2's frozen criteria. Neither H1 nor H2 may list `screening_without_consent`. |

The report also lists every critical entry v5 lists, with its rationale, and every verdict that differs between v5 and judge-v1.

## Only if v5 passes

**Rescore the 47 original replies.**
- These are the H1–H4 replies from the v1 and v2 holdout runs.
- v5 scores them with `next-turn score --judge-version judge-v5`: 1 draw plus the one retry, into a separate scores directory. The saved judge-v1 score files and their pinned hashes stay untouched.
- **Individual agreement** with the existing reviewer labels uses the definition behind 31 of 47.
- **What the report covers:**
  - the errors v5 fixed and the ones it introduced;
  - unscored replies, counted against v5;
  - results with and without H2, because H2's 12 replies shaped the rule.

**Score the 24 saved v3 replies** for the comparison page. The judge version is shown on every card, and the judge-v1 scores stay.

**Switch live runs** to v5 once Nishanth has reviewed the results.

## Cost

Planning figure: **$0.004 per judge call**. The recorded judge-v1 mean is $0.003468 over 114 calls, and v5's prompt is about 400 tokens longer. The guard's worst-case bound is about $0.017 per call: every request byte charged as an input token, plus 1,500 output tokens.

| Stage | First attempts | Expected, with ~15% retries | Hard cap (checked before every call) |
|---|---|---|---|
| Fresh check and regressions | 104: 76 judge-v5, 28 judge-v1 | about $0.48 | **$0.75** |
| If it passes: 47 rescored and 24 v3 | 71: judge-v5 | about $0.33 | **$0.50** of new judge spend |
| **Total** | | **about $0.81** | **$1.25** |

No paid call is made until Nishanth has labelled the sheet and approved this spend.

## Addendum: building the sheet (after the freeze, before any label or paid call)

- **The author.** A separate agent wrote the 7 conversations and 18 replies from the inputs listed above. It did not open the repository.
- **The lead's check.** The lead read every item, then made one edit before the sheet was built:
  - one reply's extra question asked about shift preference, which the call brief does not define as a screening question;
  - it now asks a certification question, so it tests what the plan says;
  - the original and edited text are kept in `holdout-private/judge-v5/items.json` (`lead_edits`), which the commitment covers.
- **Resemblances, disclosed.**
  - The plan's own table requires one conversation of the D1 type: availability given, no disclosure yet. Its text and replies are new, but its license reply is worded close to the certification check's C01.
  - The excerpt conversation is an advocacy story about early sepsis. That theme also appears in the prompt-v3 conversations; the story itself is different.
- **Offline dry run of every stage and of `report`.**
  - It used a stand-in judge that accepts everything, with the author's expectations as stand-in labels in a scratch copy.
  - It fails P1, P3 and P4 as it should, which shows the analysis separates a lax judge from a good one. No call was made and nothing was written to `results/`.
- **Exposure risk in this session's transcript.** Two tool outputs show the author's intended answers: the lead's read-through of the items, and the dry-run report. Nishanth was asked not to expand them before labelling.
- **Projected spend** for the fresh and regression stage, from `estimate`:
  - 104 first attempts;
  - about $0.48 expected;
  - worst-case bound per call up to $0.0177;
  - the hard cap stays at $0.75.
- **How blind the sheet is.**
  - Only the J-number-to-item mapping is sealed.
  - The fresh-check table above and the intent codes in `scripts/judge_v5_experiment.py` are public, and they describe what each kind of reply was written to do. So a reply can be matched to its design on sight.
  - The lead's chat message about the edit also named the edited reply's purpose: a further screening question after a withdrawal.
  - Nishanth is asked to label before reading the fresh-check section of this plan or the script. The sheet is unchanged.
- **The label check (`verify`)** accepts a labelled sheet with reasons, CRLF line endings or a BOM. It refuses a sheet whose item headings, conversations or replies differ from the committed sheet.
  - Both scoring stages refuse to run until all 18 Accept lines have y or n.
  - The regression stage was given this gate after the sheet commit and before any call.
- **Open before scoring: the tolerance in P2.**
  - If the labels follow the authored design, four certification items are `y`. That is 8 v5 judgments per criteria path.
  - So "at least 90%" requires 8 of 8 on both paths, at temperature 1.0.
  - Nishanth decides, before the first paid call, whether P2 stays as written or becomes "all but one per path". Any amendment is committed first.
- **Independent verification and amendments (before any label or paid call).** The verifier passed the candidate, the harness and the report against P1–P6. It also raised three findings, all fixed before scoring.
  1. **The denial backstop flagged some genuine-violation rationales.** Examples: "There is no issue with tone, but permission was never obtained"; "No fact in the brief supports the pay figure that is stated"; "It does not merely imply an outcome; it states…".
     - The patterns now need the denial to name the violation.
     - Two more denial phrasings are caught: "isn't a violation" and "does not commit this violation".
     - A withdrawal is also recognized by "retract", "rescind" and "no longer".
     - The 72-entry calibration still holds: all 35 denials are caught and none of the 37 assertions is flagged. The verifier's examples are now tests.
     - The judge-v5 prompt and its hash are unchanged.
  2. **A dry run could take the write-once results file.** `run --dry-run` now requires `--out-dir`.
  3. **The report now lists what the plan promised:** every critical entry v5 lists, with its rationale, and every item where v5 and judge-v1 differ.
- **Denominators, stated plainly.**
  - P2 and P3 count scored judgments, as their own wording says.
  - P4 counts all 54 judgments, with unscored counted as disagreement.
  - The rescore of the 47 keeps every reply in its denominator, with unscored counted against v5.
