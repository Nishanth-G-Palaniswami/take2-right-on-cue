# Scorer development run: judge-v1 on the first multi-model run

Development evidence only. These replies come from dev cases D1–D4, which have already informed the prompt. The human labels are AI-informed (see the run's `label_notes.md`). Nothing here measures agreement on held-out cases.

## Setup

| | |
|---|---|
| Replies scored | `runs/20261121T023359Z-455c41`: 16 replies, v2 × D1–D4 × `gpt-5.4-mini` and `gemini-3.5-flash` × 2 |
| Scorer | `scorer-1`, code at `c67e3ab` |
| Judge prompt | `prompts/judge.md`, `judge-v1`, SHA-256 `6df7af13…156af9` |
| Judge | requested `gpt-5.4-mini`, reported `gpt-5.4-mini-2026-03-17`; reasoning effort `none`; `max_output_tokens` 1500; strict JSON schema |
| Judge input | the case criteria from `cases/notes.toml`, the transcript and the reply. It never sees the generating model, sample, letter, prompt version, labels or reviews |
| Scores | `scores/20261121T023359Z-455c41.jsonl`: 18 lines, 16 `scored` and 2 `needs_review`, all kept |

**Calls.** There were three runs of `next-turn score`, making 18 live judge calls in total:
- **First run:** 16 calls. 14 judgments were valid and 2 were marked needs review.
- **Second run:** 2 calls. The 14 valid scores were reused and the 2 needing review were judged again.
- **Third run:** 0 calls, with all 16 reused.

The 18 calls used 45,357 input tokens, 5,755 output tokens and 0 reasoning tokens. At the PRD's Mini rates ($0.75 per million input tokens, $4.50 per million output) that is about $0.06.

**Integrity.**
- Every file under `runs/` (34 files) has the same SHA-256 before and after all three runs.
- `next-turn show` on the run still exits 0.

## Two judgments marked for review, then retried

**What happened.** Both D1 Gemini replies (letters D and B) were scored 2 on every dimension, but they were marked `needs_review`. As listening evidence, the judge quoted `"Applicant: Yeah, now's fine."`, which includes the speaker label from its input. The applicant's turn is just "Yeah, now's fine.", so the quote is not a span of that turn, and validation rejected it as designed. The judge's verbatim output is kept in the first two `needs_review` lines.

**The retry.** On the second run, both were judged again from the same saved text. Both came back valid at 8 out of 8. One quoted "Yeah, now's fine." without the label.

## Result: 16 of 16 acceptable, every reply 8 out of 8

judge-v1 gave every reply 2 on all four dimensions and found no critical violation. On this run it does not separate any reply from another.

| Case | `gpt-5.4-mini` (letters) | `gemini-3.5-flash` (letters) | Nishanth accepted |
|---|---|---|---|
| D1 | A, C: acceptable, 8/8 | B, D: acceptable, 8/8 | A, B, C, D |
| D2 | C, D: acceptable, 8/8 | A, B: acceptable, 8/8 | A, B, C, D |
| D3 | B, D: acceptable, 8/8 | A, C: acceptable, 8/8 | **A only** |
| D4 | B, D: acceptable, 8/8 | A, C: acceptable, 8/8 | A, B, C, D |

The scorer and Nishanth's recorded accept labels agree on 13 of 16 replies. All 3 disagreements are on D3, where the scorer accepted replies Nishanth rejected:
- B (Mini);
- C (Gemini);
- D (Mini).

## D3-B and D3-C: development examples

Nishanth described the two replies like this (milestone 3 instructions, 2026-11-21): "D3-B refers specifically to the charge nurse but asks what Sam did, leaving the outcome open. D3-C asks about the outcome but phrases the question as though the conversation resolved the brother's frustration."

**D3-B** (`gpt-5.4-mini`, sample 1): "What did you do to help resolve it once you brought the charge nurse in?"
- **Counting rule** (v2 report): No. The reply asks about actions, not the result.
- **Nishanth:** rejected.
- **Judge:** next action 2, listening 2, grounding 2, delivery 2. Total 8/8, acceptable.
  - Next action: "The reply stays on the same behavioral question and asks for the missing resolution after the charge nurse was brought in. It is a single focused follow-up that matches the case criteria."
  - Listening: "It references the specific detail that the applicant brought in the charge nurse, showing it is following the applicant's story rather than asking a generic follow-up."

**D3-C** (`gemini-3.5-flash`, sample 2): "Bringing the charge nurse in for a team discussion sounds like it helped bring some clarity. How did that conversation end up resolving his frustration?"
- **Counting rule:** Yes. The reply asks how the situation turned out.
- **Nishanth:** rejected.
- **Judge:** next action 2, listening 2, grounding 2, delivery 2. Total 8/8, acceptable.
  - Next action: "It stays on the same behavioral question and asks for the missing outcome of the situation, which is exactly what the case asks for. It does not move on to the next prompt or add a second request."
  - Listening: "It correctly references the applicant's specific detail about involving the charge nurse, showing it heard and used the example rather than replying generically. It also focuses on the brother's frustration, which matches the applicant's story."

**What this shows.**
- **The judge did not split the dimensions.** On B, it read "what did you do to help resolve it" as asking for "the missing resolution". The counting rule and Nishanth both treat that as a question about actions. On C, it did not mention that the question assumes the conversation resolved the frustration.
- **The D3-D wording disagreement repeats.** For D3-D (Mini, "How did you resolve it for the brother and the patient?"), the judge also said the reply asks "for the outcome of the situation". The counting rule classes this wording as actions.
- **Separate dimensions only help if the judge scores the gap.** In Nishanth's description, B's weakness is next action and its strength is listening. Next action 1 with listening, grounding and delivery at 2 totals 7 out of 8, and the decision rule fails it. `tests/test_scoring.py` pins that case with synthetic data. The live judge never produced that pattern here.
- **What C would need to fail is a judgment call.** If the judge had marked C's presupposition as listening 1, C would still pass, because listening needs only 1. It would fail only if the presupposition counted against next action. Which dimension that weakness belongs to is a rubric decision, not a finding.
- **No visible self-preference.** The Mini judge gave its own family's replies (B, D) and Gemini's (A, C) the same 8 out of 8. This run can't show self-preference, and it can't rule it out.

## Not changed

- `prompts/judge.md`, the counting rules, `cases/notes.toml` and the labels are unchanged.
- The AI-suggested D3-C explanation is not used as Nishanth's reason.

Any change to the judge prompt, the judge settings or the evidence-matching rule would be a new judge or scorer version, and the stored replies would be scored again under it. Whether to make such a change is Nishanth's decision.
