# Right on Cue: next-turn evaluation report

Nishanth G Palaniswami, for Take2's Forward Deployed Engineer take-home. Riley is a virtual recruiting assistant for Acme Health's Medical ICU RN role. The question is what Riley should say next, and which model and interviewer prompt to pilot.

**At a glance**
- **The models agree on safety.** None of the three committed a genuine critical violation in 87 scored replies. That covers screening without consent, invented facts, promises, and clinical or legal advice. Every critical flag the judge raised was reviewed and found absent.
- **They differ on next-move quality and completeness:**
  - **GPT-5.4** gives the most complete answers, but it stacks follow-up questions.
  - **GPT-5.4 Mini** is concise, and the reviewer preferred its tone, but it sometimes asks about actions instead of outcomes, and it once left out a known fact.
  - **Gemini 3.5 Flash** is the most consistent and the judge's favourite, but the reviewer preferred its wording least.
- **The prompt revision (v1 → v2) fixed one specific failure:** re-asking about a story that was already finished. On fresh holdout cases it did not narrow the gaps between models.
- **Recommendation:** a bounded pilot of **GPT-5.4 with prompt v2**, with Mini as the cost-down option once its gap on factual questions is re-tested. See [Recommendation](#recommendation).
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
- **Reviewer:** accepted **8/8** of its holdout replies under the final prompt.
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
| Holdout, v2 (final) | GPT-5.4 | 1.25 | 1.50 | 1.62 | 1.50 | 4/8 | **8/8** |
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
- **H2 depresses every holdout row equally:** all 12 H2 replies scored 3/8.
- **Missing cells:** one Gemini v1 holdout reply failed to generate, and three development replies were left unscored after their retry.

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

**Pilot GPT-5.4 with prompt v2,** time-boxed, with recruiters reviewing transcripts. The reasons, in the order the plan set them:

1. **Safety (consent, grounding, commitments): no difference.** No model committed a genuine critical violation in any scored reply, development or holdout.
2. **Held-out quality: GPT-5.4 is ahead on human labels.** It is the only model whose final-prompt holdout replies the reviewer accepted in full (8/8, against 7/8 for Gemini and 6/8 for Mini). It also won the one pair that turned on factual completeness (P08, below).
3. **Consistency: no human-label splits on the holdout** for GPT-5.4.
4. **Cost is small at this scale:** about **$0.003 per GPT-5.4 reply**, against about **$0.0008 for Mini**, from recorded tokens at standard rates. A 15-turn screening call is a few cents either way.

**Tradeoffs and risks:**
- **Stacked follow-ups.** GPT-5.4 asks two things at once when an answer is incomplete. That is the next prompt change to test: one question about the missing part, with no "what did you say, and…".
- **The evidence conflicts.** The judge rated GPT-5.4 lowest, and the reviewer preferred Mini's tone in 3 of 4 direct GPT-5.4-versus-Mini pairs. Those wins came on closings and acknowledgments; Mini lost the factual pair.
- **When Mini becomes the better choice.** If cost or latency matters more than completeness, Mini is the alternative. The case that should decide it is an H3-type applicant question with a known answer, because that is where Mini fell short twice under v2.
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
- On the holdout, **v2 did not narrow the gaps between models.** The reviewer-label spread went from 0 to 2 of 8, and the judge spread from about 12.5 to 25 points, driven by H3 under v2. v2 stays the final prompt because it fixed the targeted failure without a regression on the development checks.

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
- **The review was blind.** Replies were shuffled under neutral IDs, with model and prompt hidden, and the mappings were committed as salted hashes before generation and verified at reveal.
- **The labels are AI-assisted.** The reviewer formed initial judgments, read ChatGPT's suggested labels, and discussed the differences before finalizing. ChatGPT also suggested pair choices and helped review the critical flags.

**Agreement on the holdout** (`docs/measurements/2026-11-21-holdout-results.md`):
- **Accept/reject:** the judge agreed with the reviewer on **31 of 47** replies.
- **Exact A/B/tie on 12 pre-selected v2 pairs:** **2 of 12**, all 12 evaluable. The judge tied 9 pairs, where both replies scored the same, while the reviewer had a preference in 8 of those 9.
- **Accounting:** all 48 planned holdout replies are covered: 47 scored, 1 generation failure.

### H2: the written criterion versus what the reviewer accepted

- **The criterion.** H2's frozen criterion said Riley should acknowledge the volunteered license and certifications and move to the first behavioral question.
- **What the models did.** All 12 replies, across every model and both prompts, asked instead about *additional* certifications ("Do you hold any other certifications, like CCRN, PALS, or NIH Stroke Scale?").
- **What the reviewer did.** He accepted all 12, because those qualifications are relevant: the call brief lists them as a plus.
- **What the judge did.** It followed the written criterion and rejected all 12, at next action 0–1.
- **The effect:** this one case accounts for 12 of the 16 accept/reject disagreements.
- **The lesson for a pilot:** the criterion was narrower than the brief. Before deployment, decide whether Riley should ask about optional certifications, and write the criterion to match.
- **The false flags.** The judge also raised 12 false `screening_without_consent` flags here, using the consent flag for "keeps screening instead of advancing". The reviewer marked every one absent.

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
- **The effect of prompt v2 on this example is untested.**

### judge-v4: a tested alternative, not adopted

- **The candidate.** judge-v4 kept a stricter critical-violation format, which forces a present/absent verdict for each type, and added wording on follow-up quality.
- **What improved,** on 24 fixed development examples:
  - it caught all four planted genuine violations;
  - it raised no false flags on clean replies, which fixes judge-v1's self-denying flags;
  - it separated "asks for the outcome" from "asks what you did" (14/14), which earlier attempts had missed.
- **Why it wasn't adopted.** It still marked down D1 permission requests that mention "a few screening questions", following the frozen criterion's "as its own question". That missed one pre-registered criterion (1/4), so judge-v1 stays the submission default (`docs/measurements/2026-11-21-judge-v4-plan.md`).

## Limits

- **AI-assisted labels from one reviewer.** Agreement figures are not an independent check.
- **Small samples:** 4 development and 4 holdout cases, 2 samples per cell. Replies within a case are related.
- **Judge draws:** one draw per reply, at temperature 1.0.
- **Judge family:** the judge is a Mini model, so effects from judging its own family are possible.
- **Text only:** the findings cover conversational text, not audio timing, pronunciation or end-to-end calls.

## Deliverables

| Item | Where |
|---|---|
| Initial prompt | `prompts/v1.md` |
| Final prompt | `prompts/v2.md` |
| Judge prompt | `prompts/judge.md` (judge-v1, frozen) |
| Iteration log | This report, plus `docs/measurements/` (each experiment, with rules committed before results) |
| Evaluation method and agreement | This report; `docs/judge-v1-known-limits.md`; `docs/measurements/2026-11-21-holdout-preregistration.md`; `docs/measurements/2026-11-21-holdout-results.md` |
| The tool | `README.md`; the CLI (`uv run next-turn …`); the Streamlit app (`uv run streamlit run app.py`) |
| Saved evidence | `runs/`, `scores/`, `holdout/` |
| Exploratory live example of judge disagreement (outside the scored evaluation, no human label) | `examples/acls-lapse-judge-disagreement/` |
| OpenAI usage | Recorded usage across the project comes to about **$1.33** at standard rates: generation $0.14, judging $0.94, judge-v4 calibration $0.23, preflights $0.01. The usage-page screenshot is authoritative |
