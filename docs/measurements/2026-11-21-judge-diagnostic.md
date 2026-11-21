# Judge diagnostic: tracing judge-v1, then two candidate arms

This is a development diagnostic. Riley's call prompt stays `prompts/v2.md`. The pass thresholds are unchanged. `prompts/judge.md` (judge-v1) and every judge-v1 score are kept as the baseline. No holdout cases exist in the repo, and none were created or opened. The human labels used here are AI-informed or analysis-informed development labels, not independent agreement data.

Sections 1–4 were written on 2026-11-21 at 08:58 ET. They were committed together with `prompts/judge-v2a.md` and `prompts/judge-v2b.md`, before any judge-v2a or judge-v2b call. Results are added below them afterwards.

## 1. Trace: the pipeline is not the cause

D3-A (`gemini-3.5-flash`, sample 1, accepted) and D3-C (`gemini-3.5-flash`, sample 2, rejected) were traced end to end from `runs/20261121T023359Z-455c41` and `scores/20261121T023359Z-455c41.jsonl`.

- **Reply.** The slot's `output_text` hashes to the record's `text_sha256`. The reply appears verbatim between `<reply>` tags in the judge input.
- **Input.** The judge request was rebuilt from the run manifest's transcript turns, the `cases/notes.toml` D3 criteria and `prompts/judge.md`. It hashes to the recorded `judge_request_sha256`. The input contains:
  - the D3 criteria ("Ask how the situation with the brother turned out…");
  - the full transcript, labelled Riley and Applicant;
  - the reply.

  It contains no model, sample, letter or label.
- **API echo.** The response echoes instructions that hash to `prompts/judge.md`, along with reasoning effort `none`, `max_output_tokens` 1500 and a strict `json_schema` named `next_turn_judgment`. It also reports **temperature 1.0**. The scorer never sets temperature, so this is the API default, and each judgment is one random draw.
- **Scores.** The raw `output_text` in the API response equals the recorded `judge_output_text`. Its JSON holds next action 2, listening 2, grounding 2 and delivery 2 for both replies, with no critical violation. The recorded judgment, the decision and a fresh re-validation all match.
- **Distinct calls.** The two replies came from distinct response IDs (`resp_039ea6d…`, `resp_0d4cf47…`), so there was no cache collision.

**Widened check.** The same checks ran on all 22 judge-v1 records: the 18 lines for `20261121T023359Z-455c41` and the 4 lines for `20261120T225013Z-70fb30` (scored on 2026-11-21 for this diagnostic). For every record:
- the reply hash, the rebuilt request hash, the judge prompt hash and the echoed instructions match;
- the raw text equals the recorded text;
- the raw scores equal the recorded judgment and decision.

**Conclusion.** judge-v1 itself returned four 2s for each of the 16 replies. There is no code or input bug.

## 2. judge-v1 does discriminate elsewhere

judge-v1 was run on the earlier baseline run `20261120T225013Z-70fb30` (v1 prompt, `gpt-5.4-mini`, 4 calls). There it failed two replies:

| Letter (sample) | Reply | judge-v1 | Nishanth (informed labels) |
|---|---|---|---|
| D3 A (1) | "What did you do next to help calm the situation and make sure the family got a consistent update?" | next action 1, listening 2, grounding 2, delivery 2. Total 7/8, **not acceptable** | accepted |
| D3 B (2) | "What did you do after you brought the charge nurse in, and how did the situation end?" | 2/2/2/2, 8/8, acceptable | accepted, preferred |
| D4 A (2) | "That makes sense, especially with the mixed updates. When you brought the charge nurse in, was there anything you did specifically to help calm the brother down while you worked out that plan?" | next action 0, listening 1, grounding 2, delivery 1. Total 4/8, **not acceptable** | rejected |
| D4 B (1) | "That sounds like you helped reduce the mixed messages by involving the charge nurse and setting one clear plan. My next question is, describe a time you advocated…" | 2/2/2/2, 8/8, acceptable | accepted |

The D4 re-probe fails clearly, so the leniency is not general. It is specific to how a D3 follow-up targets the missing part. The 70fb30 D3 A result is also a live instance of the 7/8-but-fails case: next action 1, every other dimension 2. That fail disagrees with Nishanth's accept. In its rationale, the judge said the reply "asks about the outcome", then marked it down for asking two things.

## 3. Candidate arms (wording frozen at commit)

Each arm is judge-v1 plus wording added after the three **next_action** level descriptors. Nothing else changes.

- **judge-v2a** (`prompts/judge-v2a.md`, sha256 `a40a14e7…6a8e8e`):
  > When the applicant has left part of Riley's question unanswered, a 2 asks for that missing part itself. Score 1 when the follow-up asks about something next to the missing part instead, for example what the applicant did when what is missing is how things turned out.

  **Basis.**
  - PRD §3 says to seek the situation *and resolution*.
  - The PRD §7 next-action level 1 is "leaves ambiguity".
  - The D3 notes ask how the situation "turned out".
  - The pre-registered counting rule says "what did you do to resolve it" asks about actions, not the result.

  Its example mirrors D3. If it catches D3 B and D, that is largely by construction, not evidence that it generalises.
- **judge-v2b** (`prompts/judge-v2b.md`, sha256 `a23745bd…b7209e2b8a`): judge-v2a plus:
  > Also score 1 when the question itself takes the missing answer for granted, for example by assuming that a step the applicant took worked.

  **Basis.**
  - It rests on Nishanth's question in the 2026-11-21 diagnostic request: can the judge recognise a question that asks for an outcome while assuming it?
  - Its justification in the PRD is weaker. A presupposing question leaves the real outcome ambiguous, which maps to next-action level 1.
  - No recorded label reason separates D3-A from D3-C. The AI-suggested D3-C explanation is not Nishanth's confirmed reason.
  - The sentence is limited to the question, so an acknowledgment is not judged by it.

Thresholds, the decision rule, the schema and the reasoning effort are unchanged. So is temperature (left at the API default). No model identity, human label or case-specific verdict enters the judge input.

## 4. Plan and counting rules (fixed before any arm call)

**Replies.** 20 development replies:
- **The 16 in `20261121T023359Z-455c41`.** Nishanth accepted 13 and rejected 3: D3 B, C and D. These labels are AI-informed.
- **The 4 in `20261120T225013Z-70fb30`.** He accepted 3 and rejected 1, the D4 A re-probe. These labels were informed by Claude's earlier analysis.

**Draws.** Each judge version gets 2 draws per reply:
- **Draw 1** goes in `scores/<run_id>.jsonl`. judge-v1 draw 1 already exists.
- **Draw 2** goes in `scores/draw-2/<run_id>.jsonl`.
- **Calls.** Planned new calls: judge-v1 draw 2 (20), judge-v2a (40) and judge-v2b (40), so 100 calls plus retries.
- **Invalid judgments.** A judgment marked needs review is retried once within its draw. If it is still invalid, it is reported as unscored.

**Counting.**
- **Per reply and version:** "not acceptable in k of 2 draws".
- **Catches:** how many of the 4 rejected replies are not acceptable in both draws, and how many in 1 of 2.
- **New failures:** how many of the 16 accepted replies are not acceptable in at least one draw. Each is listed next to its judge-v1 result.
- **Scores:** the before and after subscores and totals are reported per reply and draw.

**Expected reading (hypotheses, not targets).**
- **judge-v2a:** catches D3 B and D, the action-focused questions. Whether it catches C is unclear.
- **judge-v2b:** may also catch C. It risks failing D3-A in the multi-model run, whose question "end up getting resolved" assumes a resolution. Nishanth noted that on his sheet and still accepted A.
- **The D4 re-probe:** stays not acceptable under every version.
- **Other risk:** both arms could fail more of the accepted D3 replies in the baseline run.

**After the results.**
- No arm wording changes once results are seen.
- Neither arm becomes the default without Nishanth's decision; judge-v1 stays the default.
- Only the sealed holdouts, after the scorer is frozen, can measure independent agreement.

## 5. Results (added 2026-11-21 09:15 ET, after both draws)

**Calls.** This pass made 113 live `gpt-5.4-mini` judge calls:

| Version | Calls | Breakdown |
|---|---|---|
| judge-v1 | 26 | 4 on 70fb30 draw 1; 22 for draw 2, including 2 retries |
| judge-v2a | 41 | including 1 retry |
| judge-v2b | 46 | including 6 retries |

- **Tokens:** 294,527 input, 38,962 output, 0 reasoning. That is about $0.40 at the PRD's Mini rates; all judge calls so far come to about $0.46.
- **Files:** draw 1 is in `scores/<run_id>.jsonl` and draw 2 in `scores/draw-2/<run_id>.jsonl`.
- **Integrity:** every file under `runs/` has the same SHA-256 before and after.

**Notation.** Each cell shows pass or FAIL, then next action, listening, grounding and delivery, then the total. "crit" marks critical-violation entries, and "unscored" means still invalid after one retry.

| Reply | Nishanth | judge-v1 d1 / d2 | judge-v2a d1 / d2 | judge-v2b d1 / d2 |
|---|---|---|---|---|
| D1-A (Mini) | accept | pass 2222 8 / unscored | **FAIL** 2221 7 crit / **FAIL** 2221 7 crit | pass 8 / **FAIL** 1212 6 crit |
| D1-B (Gemini) | accept | pass 8 / pass 8 | pass 8 / pass 8 | pass 8 / unscored |
| D1-C (Mini) | accept | pass 8 / pass 8 | pass 8 / pass 8 | **FAIL** 1221 6 crit / **FAIL** 2221 7 crit |
| D1-D (Gemini) | accept | pass 8 / pass 8 | pass 8 / unscored | unscored / pass 8 |
| D2-A (Gemini) | accept | pass 8 / pass 8 | **FAIL** 1221 6 / pass 8 | pass 8 / pass 8 |
| D2-B, C, D | accept | pass 8 in every draw | pass 8 in every draw | pass 8 in every draw |
| D3-A (Gemini) | accept | pass 8 / pass 8 | pass 8 / pass 8 | pass 8 / pass 8 |
| **D3-B (Mini)** | **reject** | pass 8 / pass 8 | pass 8 / pass 8 | pass 8 / pass 8 |
| **D3-C (Gemini)** | **reject** | pass 8 / pass 8 | pass 8 / pass 8 | pass 8 / pass 8 |
| **D3-D (Mini)** | **reject** | pass 8 / pass 8 | pass 8 / pass 8 | pass 8 / pass 8 |
| D4-A, B, D | accept | pass 8 in every draw | pass 8 in every draw | pass 8 in every draw |
| D4-C (Gemini) | accept | pass 8 / pass 8 | pass 8 / pass 2221 7 | pass 8 / pass 8 |
| base D3-A | accept | **FAIL** 1222 7 / **FAIL** 1121 5 | **FAIL** 1121 5 / **FAIL** 1221 6 | **FAIL** 1222 7 / **FAIL** 1121 5 |
| base D3-B | accept | pass 8 / pass 8 | pass 8 / pass 8 | **FAIL** 1121 5 / pass 8 |
| **base D4-A** | **reject** | **FAIL** 0121 4 crit / **FAIL** 0121 4 crit | **FAIL** 0121 4 crit / **FAIL** 0121 4 crit | **FAIL** 0121 4 crit / **FAIL** 0121 4 crit |
| base D4-B | accept | pass 8 / pass 8 | pass 8 / pass 8 | pass 8 / pass 8 |

**Recorded rejections caught: 1 of 4 under every version.** The D4 re-probe failed in all 6 draws, with next action 0. D3-B, C and D passed 8/8 in every draw: 2 per version, 6 each.

**Accepted replies failed** (16 accepted; "1 of 2" means failed in one of two scored draws):

| Version | Accepted replies failed |
|---|---|
| judge-v1 | base D3-A, 2 of 2 |
| judge-v2a | base D3-A, 2 of 2; **D1-A, 2 of 2** (critical flag only); **D2-A, 1 of 2** |
| judge-v2b | base D3-A, 2 of 2; **D1-C, 2 of 2**; **D1-A, 1 of 2**; **base D3-B, 1 of 2** |

The bold entries are new failures compared with judge-v1.

### Findings

1. **The smallest prompt change does not fix the D3 gap, and it adds false failures.**
   - Neither arm caught D3-B, C or D. Both arms failed accepted replies that judge-v1 passed.
   - On this development set, both arms are worse than judge-v1. Neither is adopted, and judge-v1 stays the default.
2. **The judge treats "resolve" questions as asking for the outcome. The cause is a hypothesis.**
   - In all 12 next-action rationales for B and D (2 replies, 3 versions, 2 draws each), the judge says the reply asks for "the missing resolution" or "the outcome". Even judge-v2a draw 1 on B, which notes that it "slightly narrows the question to what Riley did rather than the full resolution", still scores 2.
   - The baseline D3-A, "What did you do next to help calm the situation…", contains no "resolve". It is scored next action 1 in all 6 draws, but for two different reasons:
     - 3 rationales say it asks about actions rather than the outcome (judge-v1 draw 2, judge-v2a draw 1, judge-v2b draw 2);
     - 3 mark it down for asking more broadly than one focused question, while still saying it asks for the outcome (judge-v1 draw 1, judge-v2a draw 2, judge-v2b draw 1).
   - Two explanations fit these rationales equally well, and this pass cannot tell them apart:
     - **(a)** A shallow lexical reading at reasoning effort `none`: a question containing "resolve" is taken to ask for the resolution.
     - **(b)** The case criteria the judge receives say "Asks one focused question about the outcome or resolution" and quote "how was it resolved". Several rationales cite "matches the case criteria". The judge may map the reply's "resolve" onto the criteria's "resolution".
   - Wording added to the rubric did not change the behaviour. `cases/notes.toml` is unchanged.
3. **A contract defect in the critical-violation list, discovered here.**
   - The valid judgments hold 17 critical-violation entries across the 20 replies. None of the replies commits a critical violation.
   - On the base D4-A re-probe, the judge filled the list like a checklist, with 12 entries whose own rationales deny a violation. Examples: "The call had already moved past consent, so this is not a consent violation." and "No job fact is invented here." In two draws it listed all four types.
   - The code counts every entry as a violation. For base D4-A the decision was a fail anyway (next action 0), but its printed reasons are wrong.
   - **What makes each entry false.**
     - 12 entries (all on base D4-A) deny a violation in their own rationale.
     - The other 5 (on D1) assert or half-assert one. They are false by the prompt's definition: a screening question asked before permission is a violation, and these replies ask for permission and contain no screening question. Nishanth also accepted both replies.
   - **Invalid judgments.** None of the 15 invalid (`needs_review`) judgments contains a critical entry, so judge-v1 never flagged a D1 reply in any judgment.
   - Under the arms, 5 entries flagged Mini's D1 replies ("I'd like to continue with a few screening questions. Is that okay?") as `screening_without_consent`, though those replies ask permission before any screening. That made three judgments fail on the critical flag alone. These extra failures under the arms were observed over two draws, and judge-v1 showed none of them. With two draws at temperature 1.0, they are not proven to be caused by the added wording.
   - Under the current default (judge-v1), the defect changed no decision in these draws. But it can: a critical entry is decisive.
4. **Evidence quotes with speaker labels.** 15 of 131 judgments were invalid. In 13, the judge quoted a transcript turn with its "Applicant:" or "Riley:" label. One retry fixed most; 4 replies × draws stayed unscored.
5. **Sampling noise is visible at temperature 1.0.** One reply's total moves between draws under one version: base D3-A under judge-v1 scored 7 and then 5. Two draws are enough to show the noise exists, not to measure it.

### Disagreement with the development labels (judge-v1, both draws)

These are AI- or analysis-informed development labels, used here only for diagnosis.

- **Agreement:** judge-v1 agrees on 16 of the 20 replies. It passes 15 of the 16 accepted replies and fails the one re-probe.
- **Rejected replies it passes:** D3-B, C and D. Nishanth rejected them; judge-v1 passes them in every draw.
- **Accepted reply it fails:** base D3-A (next action 1). Nishanth accepted it but didn't prefer it.

Independent agreement is reserved for the sealed holdouts, after the scorer is frozen.

### Options (Nishanth decides; none applied)

- **A. Fix the critical-violation contract** (a new judge version and scorer version).
  - Make the judge give an explicit present/absent verdict for each of the four types, and count only those marked present. Alternatively, instruct it to list only violations the reply commits.
  - Add "quote the words without the speaker label".
  - Expected effect: fewer false fails and fewer invalid judgments. This does not address D3.
- **B. Run the judge at reasoning effort `low`**, a settings change the assessment allows. It tests whether the misreading of "resolve" is about reasoning depth. Its cost is roughly 40 calls plus reasoning tokens.
- **C. Record the misreading as a known limit of the judge.** D3-type cases would rely on the counting rule and human review, and the limit would be reported.

### Baseline preserved

- **`scores/20261121T023359Z-455c41.jsonl`:** the first 18 lines are byte-identical to the file at `470ad03` (sha256 `381c9ac3…`). Since then 35 lines were added and 0 deleted.
- **`scores/20261120T225013Z-70fb30.jsonl`:** the 4 judge-v1 lines are unchanged from `844e719`. 8 lines were added and 0 deleted.
- **`prompts/judge.md`:** unchanged.
