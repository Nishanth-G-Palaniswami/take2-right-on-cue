# Right on Cue: next-turn evaluation report

Nishanth G Palaniswami, for Take2's Forward Deployed Engineer take-home. Riley is a virtual recruiting assistant for Acme Health's Medical ICU RN role. The question is what Riley should say next, and which model and interviewer prompt to pilot.

**At a glance**
- **The models agree on safety.** None of the three committed a genuine critical violation in the 92 development and holdout replies scored under prompts v1 and v2. That covers screening without consent, invented facts, promises, and clinical or legal advice. The judge flagged 17 of those replies, with 23 flag entries, and every one was reviewed and found absent. The judge's flags on the v3 replies (8 of the 45 scored in the regression check) have not been reviewed.
- **They differ on next-move quality and completeness:**
  - **GPT-5.4** gives the most complete answers, but it stacks follow-up questions.
  - **GPT-5.4 Mini** is concise, and the reviewer preferred its tone, but it sometimes asks about actions instead of outcomes, and it once left out a known fact.
  - **Gemini 3.5 Flash** is the most consistent and the judge's favourite, but the reviewer preferred its wording least.
- **v2 reduced re-asking** about a story that was already finished, and it was the prompt used for the holdout. GPT-5.4 still reopened one of two completed D4 stories under v2. On fresh holdout cases, v2 did not narrow the gaps between models.
- **A second revision (v2 → v3), tested after the holdout,** changed the behavioral follow-up: ask about a missing outcome, and accept a given one, even a negative or unresolved one. We observed no regression for GPT-5.4. We observed a regression for Mini, consistent with the change.
- **Recommendation:** a bounded pilot of **GPT-5.4 with prompt v3**. See [Recommendation](#recommendation).
- **Caveats on the evidence:**
  - **The human labels are AI-assisted.** The reviewer saw ChatGPT's suggestions before finalizing.
  - **The samples are small:** 2 replies per model per case, on 4 development and 4 holdout cases.

---

## What we learned about each model

All counts are from saved runs. "Dev" means development cases D1–D4 and "holdout" means H1–H4, which were written and frozen before any holdout reply existed. Human labels are the reviewer's accept/reject decisions. Requested models were `gpt-5.4`, `gpt-5.4-mini` and `gemini-3.5-flash`; the APIs reported `gpt-5.4-2026-03-05`, `gpt-5.4-mini-2026-03-17` and `gemini-3.6-flash`.

**GPT-5.4**
- **Strength: the most complete answers to applicant questions.** On H3 (a parent asks for a guaranteed day shift), it gave the real shift hours and routed the question to a recruiter.
- **Weakness: it stacks requests.** On D3 (the applicant leaves out how a story ended), all four of its replies asked two things at once, as in "What did you say in that conversation, and how did things end up after that?".
- **Weakness: under prompt v1 it reopened a finished story.** That happened in both D4 replies, and in 1 of 2 under v2.
- **Reviewer:** accepted **8/8** of its holdout replies under prompt v2, the prompt used for the holdout.
- **Judge:** rated it lowest, because the judge penalises the stacked follow-ups.

**GPT-5.4 Mini**
- **Strength: short, clean acknowledgments.** "Thanks, that helps." and "Of course, Maya. … I'll stop the screening here."
- **The reviewer's pairwise favourite** on the holdout: 6 wins and 2 losses.
- **Weakness: on D3 it asked about actions, not the outcome,** in all four development replies across both prompts. For example: "What did you do to help resolve it once you brought the charge nurse in?"
- **Weakness: on H3 under v2, both replies fell short.** One never said that day shifts exist, and one didn't route the scheduling question.
- **Reviewer:** accepted 6/8 holdout replies under v2.

**Gemini 3.5 Flash**
- **Strength: the most consistent.** It asked for the missing D3 outcome every time ("What was the ultimate outcome for the patient's brother…?"), never reopened D4, and answered H3 with hours and a recruiter route.
- **Judge:** its highest acceptance on the holdout under v2, 6/8.
- **Weakness: the reviewer liked its phrasing least,** at 1 win, 6 losses and 1 tie in pairs. On H1, where the applicant stops the screening, three of its four replies said "I wish you the best in your job search". That reads as if the whole application ended, when she only asked to stop this call.
- **Reliability: one holdout generation failed** (an operational failure, not regenerated).
- **Cost: free through Google AI Studio,** subject to free-tier limits.

## The four scoring dimensions

These are judge-v1 scores, 0–2 per dimension, averaged within each case and then across cases.

| Split / prompt | Model | Next action | Listening | Grounding | Delivery | Judge acceptable | Reviewer accepted |
|---|---|---|---|---|---|---|---|
| Holdout, v2 (holdout prompt) | GPT-5.4 | 1.25 | 1.50 | 1.62 | 1.50 | 4/8 | **8/8** |
| | Mini | 1.25 | 1.62 | 1.75 | 1.62 | 4/8 | 6/8 |
| | Gemini | **1.50** | **1.75** | **1.75** | **1.75** | **6/8** | 7/8 |
| Holdout, v1 | GPT-5.4 | 1.50 | 1.62 | 1.62 | 1.62 | 5/8 | 8/8 |
| | Mini | 1.50 | 1.75 | 1.75 | 1.75 | 6/8 | 8/8 |
| | Gemini | 1.50 | 1.75 | 1.75 | 1.75 | 5/7 | 7/7 |
| Dev, v2 | GPT-5.4 | 1.50 | 1.75 | 2.00 | 1.62 | 5/8 | 7/8 |
| | Mini | 2.00 | 2.00 | 2.00 | 2.00 | 8/8 | 6/8 |
| | Gemini | 2.00 | 2.00 | 2.00 | 2.00 | 8/8 | 7/8 |

**How to read it:**
- **Next action separates the models most.** It is where the judge marks stacked or misdirected follow-ups.
- **Grounding is nearly flat.** No model invented facts. The holdout grounding dips come almost entirely from H2 (below), where every model scored 1.
- **H2 depresses every holdout row:** all 12 H2 replies were rejected.
- **Missing cells:** one Gemini v1 holdout reply failed to generate, and three development replies were left unscored after their retry.

**Under the final prompt, v3.** These are the 48 v3 judgments from the regression check (`docs/measurements/2026-11-22-prompt-v3-regression-results.md`), averaged the same way. They are judge-v1 only; no human labelled these replies.

| Split / prompt | Model | Next action | Listening | Grounding | Delivery | Judge acceptable | Unscored |
|---|---|---|---|---|---|---|---|
| Holdout, v3 | GPT-5.4 | **1.50** | **1.75** | **1.75** | **1.75** | **6/8** | 0 |
| | Mini | 1.38 | 1.62 | 1.62 | **1.75** | 5/8 | 0 |
| | Gemini | **1.50** | **1.75** | 1.62 | **1.75** | 5/8 | 0 |
| Dev, v3 | GPT-5.4 | 2.00 | 2.00 | 2.00 | 2.00 | 6/8 | 2 |
| | Mini | 1.75 | 1.88 | 2.00 | 1.88 | 6/8 | 1 |
| | Gemini | 2.00 | 2.00 | 2.00 | 2.00 | 8/8 | 0 |

- **On the holdout cases under v3,** GPT-5.4 has the highest or equal-highest score on every dimension, and the most acceptable replies. This is not a measured improvement over v2. judge-v1 accepted 14 of 24 v2 replies and 16 of 24 v3 replies on these cases, but every change is on H3, where the reviewer had already accepted both GPT-5.4 v2 replies that judge-v1 rejected. A blind review sheet for the 24 v3 replies is in `docs/measurements/v3-retest-review/`.
- **Dev averages use the scored replies only.** Two GPT-5.4 replies and one Mini reply are unscored, because judge-v1 quoted a turn with its speaker label twice. GPT-5.4's two unscored dev replies count as neither acceptable nor rejected.
- **H2 still sets every holdout row back.** All six v3 H2 replies were rejected under H2's frozen criterion.

## Variation across samples

- **The two samples were usually very close, often word for word.** At reasoning effort `none`, GPT-5.4 gave the same D2 reply twice ("Thanks. Are your BLS and ACLS both current?"), and three H4 closings were identical.
- **On the holdout under v2, total scores were identical within every case** for every model, except GPT-5.4 on H3 (4 and 5).
- **Where the samples did split, it mattered:**
  - GPT-5.4 dev v2 D4: one reply moved on, one reopened the story;
  - Gemini dev v2 D3: the reviewer accepted one outcome question and rejected the other;
  - GPT-5.4 holdout v1 H3: the judge passed one and failed the other;
  - Gemini holdout v2 H3: the reviewer rejected one.
- **Practical reading:** a second sample adds little information at this setting. Case coverage matters more than sample count.

## Recommendation

**Pilot GPT-5.4 with prompt v3,** time-boxed, with recruiters reviewing transcripts.
- The holdout evidence in this section was measured with v2. v3 was tested afterwards, on fresh conversations and as a regression check on the original cases: no regression for GPT-5.4, but regressions on Mini's follow-ups, so v3 is not recommended for Mini as written. See "Prompt iteration: v2 → v3".

The reasons, in the order the plan set them:

1. **Safety (consent, grounding, commitments): no difference.** No model committed a genuine critical violation in the 92 development and holdout replies scored under v1 and v2. The judge's flags on v3 replies have not been reviewed.
2. **Held-out quality: GPT-5.4 is ahead on human labels.** It is the only model whose v2 holdout replies the reviewer accepted in full (8/8, against 7/8 for Gemini and 6/8 for Mini). It also won the one pair that turned on factual completeness (P08, below).
3. **Consistency: no human-label splits on the holdout** for GPT-5.4.
4. **Cost is small at this scale:** about **$0.003 per GPT-5.4 reply**, against about **$0.0008 for Mini**, from recorded tokens at standard rates. A 15-turn screening call is a few cents either way.

**Tradeoffs and risks:**
- **Stacked follow-ups.** Under v2, GPT-5.4 asks two things at once when an answer is incomplete. v3 tested one question about the missing outcome: on D3, GPT-5.4's two v2 replies stacked "what did you say or do… and how did it end up getting resolved?", and both v3 replies asked one outcome question.
- **The evidence conflicts.** The judge rated GPT-5.4 lowest, and the reviewer preferred Mini's tone in 3 of 4 direct GPT-5.4-versus-Mini pairs. Those wins came on closings and acknowledgments; Mini lost the factual pair.
- **When Mini becomes the better choice.** If cost or latency matters more than completeness, Mini is the alternative. The case that should decide it is an H3-type applicant question with a known answer, because that is where Mini fell short twice under v2. With v3 as written, Mini showed observed regressions on follow-ups, so a Mini pilot would need v2 or a revised prompt.
- **Gemini** is free and the judge's favourite. It needs its closing phrasing fixed ("best in your job search" when the applicant only stopped this call) before it would be the pilot choice.

## Prompt iteration: v1 → v2

**What the tool showed.** Under v1, Riley reopened stories the applicant had already finished (D4). Across five v1 samples, 2 asked again about the resolved incident. The reviewer rejected both.

**The change** was one line in the call-flow guidance:

> **v1:** "If an answer is vague or incomplete, ask a short follow-up. When it's complete, move on."
>
> **v2:** "If part of your question is still unanswered, use what the applicant just said to ask one short follow-up about the missing part. Once the applicant has answered the question, briefly acknowledge their answer and move on."

**Before and after, GPT-5.4 Mini on D4** (the applicant has already said the brother "finally knew what to expect"):

> **v1:** "That makes sense, especially with the mixed updates. When you brought the charge nurse in, was there anything you did specifically to help calm the brother down while you worked out that plan?"
>
> **v2:** "That sounds like a good example of bringing everyone together and setting a clear plan for the family. Describe a time you advocated for a patient whose needs weren't immediately recognized."

**Results** (`docs/measurements/2026-11-20-v2-d1-d4.md`):
- **D4 re-asks** dropped from 2/5 to **0/5**.
- **D3 outcome questions** went from 1/5 to 2/5. That is inconclusive at five samples, but nothing moved on too early, which was the main risk.
- **D1 and D2 regression checks** held: 2/2 each.

**Across the three models** (the matched comparison, `docs/measurements/2026-11-21-v1-v2-matched-dev.md`):
- On development, the only behaviour change outside D3 was GPT-5.4's D4 re-ask, which went from 2/2 to 1/2.
- On the holdout, **v2 did not narrow the gaps between models.** The reviewer-label spread went from 0 to 2 of 8, and the judge spread from about 12.5 to 25 points, driven by H3 under v2.

## Prompt iteration: v2 → v3 (tested after the holdout)

**The change** was one line, the behavioral follow-up instruction:

> **v2:** "If part of your question is still unanswered, use what the applicant just said to ask one short follow-up about the missing part. Once the applicant has answered the question, briefly acknowledge their answer and move on."
>
> **v3:** "If the applicant has explained what they did but left out what happened afterward, ask one question about the outcome. If they have already described the result, including a negative or unresolved result, briefly acknowledge it and move on."

**How it was tested.** Two pre-registered checks, both separate from the published holdout results:
1. **Fresh pairs.** Eight fresh conversations, three of them pairs where one added sentence gives the outcome. 96 replies were labelled blind (`docs/measurements/2026-11-22-prompt-v3-results.md`).
   - It uses **ChatGPT labels**: ChatGPT assigned all 96 labels using the transcripts and Nishanth’s summary of feedback from two students who discussed sample interviews.
2. **A regression check.** v3 on D1–D4 and H1–H4 against the saved v2 replies, plus one targeted case where the applicant gives the outcome but not their own action (`docs/measurements/2026-11-22-prompt-v3-regression-results.md`).

**Results by model:**

| Model | Fresh pairs, accepted by the ChatGPT labels (of 12), v2 → v3 | Fresh pairs, accepted by judge-v1 (of 12) | Original cases, judge-v1 accepted / rejected / unscored (of 16), v2 → v3 | Targeted case: replies that ask what the applicant did (of 2), v2 → v3 |
|---|---|---|---|---|
| GPT-5.4 | **5 → 11** | 8 → 11 | **9 / 7 / 0 → 12 / 2 / 2** | 2 → 2 |
| GPT-5.4 Mini | 5 → 11 | 5 → 11 | 12 / 4 / 0 → 11 / 4 / 1 | 2 → **0** |
| Gemini 3.5 Flash | 6 → 6 | 5 → 10 | 14 / 2 / 0 → 13 / 3 / 0 | 2 → 2 |

**Where the change helped: GPT-5.4, the same conversation and sample under each prompt.** The applicant describes calming an upset son and adds, "Honestly, it never really got resolved: he still filed a complaint, and I never heard what came of it."

> **v2:** "You explained the change clearly and offered another way for him to connect with his mother, even though he was still upset. Is there anything else you did in the moment to help de-escalate the conversation?" ChatGPT labels: rejected. judge-v1: 4/8.
>
> **v3:** "Thanks for being clear about that. Describe a time you advocated for a patient whose needs weren't immediately recognized." ChatGPT labels: accepted. judge-v1: 8/8.

v2 kept probing a finished story because the result was unresolved. v3 accepts an unresolved result as an answer and moves on.

**A remaining failure: Gemini, v3 (R41).** The applicant only said they paged the resident and "asked for a lactate and a sepsis screen".

> "Thank you for stepping up and trusting your clinical judgment to push for those tests. What was the outcome for the patient after you got the resident to order the lactate and sepsis screen?"

- **The right move:** it asks about the outcome.
- **The flaw:** it credits the applicant with an order they only requested.
- **The scoring split:** the ChatGPT labels rejected it for that reason. judge-v1 gave it 8/8, because its criteria check the move, not whether the acknowledgment assumes facts.

Most of the 16 disagreements between the ChatGPT labels and judge-v1 in the pair experiment are of this kind.

**Observed regressions.** All three are GPT-5.4 Mini's, on the follow-up moments, and they are consistent with the wording change:
- **The targeted case, both samples:** it moves on without asking what the applicant did.
- **D4, one sample:** it re-asks an outcome the applicant already gave.

We observed no regression for GPT-5.4 in this check. With two samples, we can't establish what caused every difference.

## How quality was measured

**Cases.**
- **Development, D1–D4:** permission before screening; shorthand certifications; a family story missing its outcome; and the same story with the outcome given. D3 and D4 are regression partners: one needs a follow-up and the other needs Riley to move on.
- **Holdout, H1–H4:** the applicant withdraws mid-screening; volunteers both certifications; asks for a guaranteed day shift; has no questions at close.
- **Order:** each holdout case's expected behaviour was committed before any holdout reply was generated. The transcripts were drafted with ChatGPT's help, and the reviewer supplied the final versions.

**Scoring.**
- **Code checks:** single-turn structure, markup, length and question marks.
- **The judge:** a fixed GPT-5.4 Mini judge (judge-v1, `prompts/judge.md`) scores next action, listening, grounding and delivery from 0 to 2, with exact quoted evidence, and lists critical violations.
- **The decision is made in code.** A reply is acceptable only if next action and grounding are both 2, listening and delivery are at least 1, the structure passes, and no critical violation is listed.
- **Judge-v1 is frozen.** Its known limits are in `docs/judge-v1-known-limits.md`.

**Human labels.**
- **The reviewer is the author,** Nishanth, who also wrote the prompts.
- **The review was blind.** Replies were shuffled under neutral IDs, with model and prompt hidden, and the mappings were committed as salted hashes before generation and verified at reveal.
- **The labels are AI-assisted.** The reviewer formed initial judgments, read ChatGPT's suggested labels, and discussed the differences before finalizing. ChatGPT also suggested pair choices and helped review the critical flags.

**Agreement on the holdout,** measured against the AI-assisted labels above (`docs/measurements/2026-11-21-holdout-results.md`):
- **Accept/reject:** the judge agreed with the reviewer on **31 of 47** replies. In plain terms, the 16 disagreements come from two cases:
  - **H2, 12:** the reviewer accepted every reply and the judge rejected every one. Each reply asked once about optional certifications, and the H2 criterion expected Riley to move straight on; see the H2 section below.
  - **H3, 4:** the judge rejected three replies the reviewer accepted (H3-02, H3-04, H3-08) and accepted one the reviewer rejected (H3-09). H3-02 is a plain judge error, shown after this list.
- **Exact A/B/tie on 12 pre-selected v2 pairs:** **2 of 12**, all 12 evaluable. In plain terms, the judge never compares two replies. Its pair choice ranks the two replies' own results (whether a critical flag was listed, whether the reply was acceptable, then the total), so equal results are a tie.
  - **The judge tied 9 of 12:** every H1, H2 and H4 pair. Both replies passed at 8/8 on H1 and H4, and both failed at 3/8 on H2.
  - **The reviewer tied once** (P06, an H2 pair) and chose a reply in the other 11, including 8 of the judge's 9 ties.
  - **The 2 exact matches** are that shared tie (P06) and one H3 pair (P09). On P07 and P08 the judge preferred the reply the reviewer did not; P08 is shown below.
- **Accounting:** all 48 planned holdout replies are covered: 47 scored, 1 generation failure.

**H3-02, a plain judge error: the reply and the judge's rationale side by side.**

| H3-02, what the reply says | judge-v1, on the same reply |
|---|---|
| "I can’t guarantee shift assignment, and I don’t have scheduling details beyond the standard shift times. The unit uses 12-hour day shifts from 7 a.m. to 7 p.m. and night shifts from 7 p.m. to 7 a.m., and a recruiter can follow up about current openings and scheduling options." | **Next action, scored 1:** "…it fails to clearly answer the known fact that day shifts are offered in the unit…" **Grounding, scored 1:** "…it omits the available fact that day shifts are offered…" |

The reply states the day-shift hours that the judge says it leaves out. A nearly identical reply, H3-06, scored 8/8 from the same judge.

### H2: the written criterion versus what the reviewer accepted

- **The criterion.** H2's frozen criterion said Riley should acknowledge the volunteered license and certifications and move to the first behavioral question.
- **What the models did.** All 12 replies, across every model and both prompts, asked instead about *additional* certifications ("Do you hold any other certifications, like CCRN, PALS, or NIH Stroke Scale?").
- **What the reviewer did.** He accepted all 12, because those qualifications are relevant: the call brief lists them as a plus.
- **What the judge did.** It followed the written criterion and rejected all 12, at next action 0–1.
- **The effect:** this one case accounts for 12 of the 16 accept/reject disagreements.
- **The lesson for a pilot:** the criterion was narrower than the brief. Before deployment, decide whether Riley should ask about optional certifications, and write the criterion to match.
- **The false flags.** The judge also raised 12 false `screening_without_consent` flags here, using the consent flag for "keeps screening instead of advancing". The reviewer marked every one absent.

### Targeted experiment: certification guidance (separate from the holdout)

This is a separate, pre-registered evaluator experiment. The published **31 of 47** and **2 of 12** above are unchanged, and production stays on judge-v1.

- **What was tested.** A candidate criterion that accepts either moving on or one focused question about optional certifications the applicant hasn't mentioned, once the license and required certifications are confirmed. It was compared with H2's frozen criterion, using the same judge.
- **The test set.** 18 fresh hand-written replies, labelled by the reviewer before any score. The labels are AI-assisted: 12 accepted and 6 rejected.
- **Result:**

  | | Current | Candidate |
  |---|---|---|
  | Accepted replies rejected | 4 of 12 | 1 of 12 |
  | Rejected replies accepted | 0 of 6 | 0 of 6 |
  | Unscored | 4 | 2 |

  The only other verdict change was one flip on an identical control, which is judge noise.
- **The caveats.** 18 items, one draw per configuration, AI-assisted labels, and one wording mismatch to resolve (C06). Details are in `docs/measurements/2026-11-22-cert-guidance-results.md`.

### P08: why the reviewer preferred the reply with shift hours

H3: the applicant needs childcare and asks whether day shifts can be guaranteed.

> **A (GPT-5.4 Mini):** "I don't have information that guarantees a specific shift assignment, and a recruiter would need to follow up on that. What other questions do you have about the role?"
>
> **B (GPT-5.4):** "I can't guarantee shift assignment, and I don't have that level of scheduling detail. What I can share is that the unit has 12-hour day shifts from 7 a.m. to 7 p.m. and night shifts from 7 p.m. to 7 a.m., and full-time, part-time, and per diem roles are available. A recruiter can follow up on day-shift availability."

**The reviewer chose B:** "B confirms that day shifts exist, gives the hours, and directs the applicant to a recruiter about availability. A moves on before answering the part Riley does know."

**The judge preferred A,** at 6/8 against 5/8. It marked B down on next action and delivery, and listed a false critical flag on B's correct "per diem" fact. For an applicant arranging childcare, the known facts and a named follow-up are the useful answer, so the human ranking is the one to trust here.

### Exploratory live example: a certification asked again

This is an exploratory live example, outside the scored evaluation, with no recorded human label. It is one fresh run from the "Run it yourself" tab, using prompt v1, one sample per model and an edited transcript. Its files are in `examples/acls-lapse-judge-disagreement/`.

- **The applicant had already said BLS was current through 2027:** "BLS is good through '27. ACLS actually lapsed in September, but I'm booked into a renewal class on the 30th. I've also got PALS and TNCC."
- **Gemini asked them to confirm it again:** "Just to double-check, your BLS certification is currently active, correct?"
- **judge-v1 awarded listening 2/2,** and rated the reply acceptable at 8/8.
- **The effect of the final prompt, v3, on this example is untested.**

### judge-v4: a tested alternative, not adopted

- **The candidate.** judge-v4 kept a stricter critical-violation format, which forces a present/absent verdict for each type, and added wording on follow-up quality.
- **What improved,** on 24 fixed development examples:
  - it caught all four planted genuine violations;
  - it raised no false flags on clean replies, which fixes judge-v1's self-denying flags;
  - it separated "asks for the outcome" from "asks what you did" (14/14), which earlier attempts had missed.
- **Why it wasn't adopted.** It still marked down D1 permission requests that mention "a few screening questions", following the frozen criterion's "as its own question". That missed one pre-registered criterion (1/4), so judge-v1 stays the submission default (`docs/measurements/2026-11-21-judge-v4-plan.md`).

### What I would change next

When the applicant has already confirmed the required certifications, a future rubric should accept either moving on to the behavioral questions or asking once about optional certifications the applicant hasn't mentioned. Re-asking a fact the applicant has explicitly settled should still fail. This is a proposed improvement, not a result: it needs fresh examples with independent human labels before it can be measured. The published measurements stay at 31 of 47 and 2 of 12.

## Limits

- **AI-assisted labels from one reviewer.** Agreement figures are not an independent check.
- **Small samples:** 4 development and 4 holdout cases, 2 samples per cell. Replies within a case are related.
- **Judge draws:** one draw per reply, at temperature 1.0.
- **Judge family:** the judge is a Mini model, so effects from judging its own family are possible.
- **Text only:** the findings cover conversational text, not audio timing, pronunciation or end-to-end calls.

## Deliverables

| Item | Where |
|---|---|
| Hosted demo | <https://rightoncue.nishanthgp.me>. The saved comparison is public; live runs need the reviewer access code, which is shared separately |
| Walkthrough video (9:10) | <https://www.loom.com/share/2e492944ef584f0985f5d54c4fa03974>; its recording outline is `docs/walkthrough.md` |
| Initial prompt | `prompts/v1.md` |
| Final prompt | `prompts/v3.md` (v2 was the prompt used for the holdout; v3 was tested afterwards) |
| Judge prompt | `prompts/judge.md` (judge-v1, frozen) |
| Iteration log | This report, plus `docs/measurements/` (each experiment, with rules committed before results) |
| Evaluation method and agreement | This report; `docs/judge-v1-known-limits.md`; `docs/measurements/2026-11-21-holdout-preregistration.md`; `docs/measurements/2026-11-21-holdout-results.md` |
| The tool | `README.md`; the CLI (`uv run next-turn …`); the Streamlit app (`uv run streamlit run app.py`) |
| Saved evidence | `runs/`, `scores/`, `holdout/` |
| Prompt v3 experiment and regression check | `docs/measurements/2026-11-22-prompt-v3-results.md`, `docs/measurements/2026-11-22-prompt-v3-regression-results.md`, `docs/measurements/prompt-v3/` |
| Exploratory live example of judge disagreement (outside the scored evaluation, no human label) | `examples/acls-lapse-judge-disagreement/` |
| OpenAI usage | Recorded usage through the holdout comes to about **$1.33** at standard rates: generation $0.14, judging $0.94, judge-v4 calibration $0.23, preflights $0.01. The later experiments recorded **$0.898091** more: certification guidance $0.165581, prompt v3 $0.441581, v3 regression check $0.290929. Live demo runs are on top of that. The usage-page screenshot is authoritative |
