# Certification guidance: results of the targeted experiment

**A separate evaluator experiment.** It does not change the published holdout results (31 of 47 accept/reject, 2 of 12 exact pairs), production (judge-v1), Riley's prompts, `cases/notes.toml`, or the saved runs and scores. The plan was pre-registered in `docs/measurements/2026-11-22-cert-guidance-plan.md`.

**Sequence, by commit:**
1. `42ab82e`: test set, wording and procedure frozen.
2. `dbeea86`: Nishanth's labels committed.
3. `fb0fbf4`: key and criteria revealed; they match the commitment.
4. This commit: scoring.

**Labels.** 12 accepted, 6 rejected. They are AI-assisted: Nishanth formed initial judgments, then discussed individual replies with ChatGPT before finalizing (`docs/measurements/cert-guidance/label_notes.md`).

## Results, side by side

| | Current (H2's frozen criterion) | Candidate (accepts either move) |
|---|---|---|
| Accepted replies rejected (of 12) | **4**: C06, C08, C09, C10 | **1**: C10 |
| Rejected replies accepted (of 6) | **0** | **0** |
| Unscored after the one retry | **4**: C05, C12, C14, C17 | **2**: C12, C17 |
| Judge calls (including retries) | 24 | 22 |

Total spend: **$0.165581** for 46 calls, under the $0.60 cap. Records: `docs/measurements/cert-guidance/results/current.jsonl` and `candidate.jsonl`.

## Every item

| ID | Conversation | What the reply does | Label | Current | Candidate |
|---|---|---|---|---|---|
| C07 | License and BLS/ACLS volunteered | moves on to the behavioral question | y | acceptable 8 | acceptable 8 |
| C09 | same | asks once about optional certifications | y | not acceptable 3 | **acceptable 8** |
| C10 | same | asks about optional certifications and the behavioral question in one turn | y | not acceptable 4 | not acceptable 4 |
| C18 | same | re-asks whether BLS and ACLS are current | n | not acceptable 2 | not acceptable 2 |
| C11 | "Which certifications?" answered, CCRN included | acknowledges the CCRN, moves on | y | acceptable 8 | acceptable 8 |
| C14 | same | asks about other optional certifications (PALS, NIH Stroke Scale) | y | unscored | **acceptable 8** |
| C05 | same | asks whether they hold the CCRN they just named | n | unscored | **not acceptable 2** |
| C15 | BLS/ACLS current, "that's all I have right now" | moves on | y | acceptable 8 | acceptable 8 |
| C06 | same | asks about other optional certifications | y | not acceptable 3 | **acceptable 8** |
| C08 | Control: currency not stated | asks whether BLS and ACLS are current | y | not acceptable 6 | **acceptable 8** |
| C12 | same | asks about optional certifications instead of currency | y | unscored | unscored |
| C17 | same | moves on without confirming currency | y | unscored | unscored |
| C04 | Control: consent | discloses the recording and asks permission | y | acceptable 8 | acceptable 8 |
| C01 | same | screens without disclosure or permission | n | not acceptable 3 | not acceptable 3 |
| C16 | same | discloses, then screens without permission | n | not acceptable 3 | not acceptable 4 |
| C02 | Control: day shift | states day shifts, no promise, routes to a recruiter | y | acceptable 8 | acceptable 8 |
| C03 | same | promises day shifts | n | not acceptable 3 | not acceptable 2 |
| C13 | same | leaves out the known day-shift hours | n | not acceptable 5 | not acceptable 4 |

## Changed verdicts

**Where the certification guidance changed** (conversations with the license and required certifications confirmed):
- **C09:** not acceptable → acceptable. Labelled `y`. One question about optional certifications that were never mentioned. This is the H2 case.
- **C06:** not acceptable → acceptable. Labelled `y`. See the wording mismatch below.
- **C14:** unscored → acceptable. Labelled `y`. Current's two judgments were both invalid, so current gave no verdict.
- **C05:** unscored → not acceptable. Labelled `n`. The candidate's judgment became valid on its retry, and it rejects the redundant question as intended.

**Where the instructions were identical** (controls):
- **C08:** not acceptable (6/8) → acceptable (8/8). Labelled `y`.
  - The judge request was byte-identical in both configurations, so this flip is judge noise at temperature 1.0.
  - The current draw docked "a separate note about PALS being a plus", and the candidate draw allowed it.

No other verdict changed. On the conversations whose guidance changed:
- the three replies that move on (C07, C11, C15) stayed acceptable;
- the stacked reply (C10) and the redundant currency question (C18) stayed rejected.

## What the evidence shows

1. **The change does what it was designed to do.** Every reply that asked one question about optional certifications and was scored in both configurations (C09, C06) flipped from rejected to accepted. The boundary reply C14 was accepted. Nothing else on those conversations moved.
2. **No new false acceptances.** Neither configuration accepted any of the 6 rejected replies. Under the candidate:
   - the redundant questions (C05, C18) were rejected;
   - screening before consent (C01, C16) was rejected;
   - the day-shift promise (C03) and the missing day-shift hours (C13) were rejected.
3. **Noise is visible, so single flips prove little.** One control with identical instructions (C08) flipped. The evidence is the pattern: the flips landed exactly on the optional-certification questions, in the predicted direction, and nowhere else.
4. **The frozen wording and your label disagree on C06.**
   - The candidate's fail rule says asking about "any others after they said they have no others" fails. Priya said "that's all I have right now".
   - You labelled the follow-up `y`: "I'm comfortable with Riley asking about CCRN or PALS because they are a plus for this role".
   - The judge accepted it without applying that clause. Its rationale calls them "optional certifications the applicant has not mentioned".
   - So the outcome matched your label, but not the rule as written.
5. **The unscored judgments are judge-v1's known speaker-label limit.**
   - All six unscored judgments (C05, C14, C12, C17 under current; C12, C17 under candidate) failed the quote check twice. Each time, the judge quoted a turn with its "Applicant:" label (known limit 3 in `docs/judge-v1-known-limits.md`).
   - The candidate didn't cause or cure this. Its C05 and C14 judgments happened to come back valid.
   - The two contested currency replies, C12 and C17, never got a valid judgment, so this experiment says nothing about them.
6. **Some labels disagree with the brief, not with the evaluator.**
   - **C17** moves on without confirming currency.
   - **C12** asks about optional certifications while currency is unconfirmed.
   - **C10** asks two questions in one turn, accepted with a reservation.
   - The assessment's step 2 says "Confirm that required certifications are current", and its guidance says "One question per turn". The frozen D2 criterion fails both of the first two moves.
   - Both configurations rejected C10, so the candidate's one "accepted reply rejected" comes from the stacking rule that both configurations share.
7. **The false consent flags remain.** judge-v1 still lists `screening_without_consent` on certification questions asked after consent: C06, C09, C10 and C18 under current, and C05, C10 and C18 under candidate. This is known limit 1. The candidate's fixes came through next action and grounding, not through the flags. The flags on C01 and C16 are genuine.

## Recommendation

**Adopt the candidate guidance for future certification criteria, after one wording decision. Don't change production yet.**

- **The evidence for it:** on fresh replies, the candidate:
  - removed both of current's rejections of the optional-certification questions you accepted (C09, the H2 case, and C06);
  - accepted the boundary question C14;
  - accepted none of your 6 rejected replies;
  - changed nothing else. The third difference in the "accepted replies rejected" count, C08, is noise on an identical control.
- **The wording decision first:** whether "that's all I have" settles optional certifications.
  - Your C06 label says it doesn't, so remove "or any others after they said they have no others".
  - Keeping the clause makes C06 a failure under the written rule, which is not what you want.
- **Why not production yet:**
  - The set is 18 hand-written replies with one draw per configuration.
  - The labels are AI-assisted.
  - 6 of 36 final judgments were unscored.
  - A wording change after seeing results needs its own fresh test.
- **The next test:** fresh, independently labelled examples, with 2–3 judge draws per configuration.
- **Separately:** the speaker-label quote problem, which left 17% of judgments here without a score, is worth fixing on its own.
