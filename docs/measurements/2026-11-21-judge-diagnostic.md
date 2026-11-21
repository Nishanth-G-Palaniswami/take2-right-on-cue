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

**Decision (Nishanth, 2026-11-21, recorded 13:10 ET).**
- A is built as the candidate judge-v3, scored under `scorer-2`. It is not adopted, and judge-v1 stays the default.
- C is recorded in section 6.
- B is not part of this pass: reasoning effort and temperature are unchanged.

### Baseline preserved

- **`scores/20261121T023359Z-455c41.jsonl`:** the first 18 lines are byte-identical to the file at `470ad03` (sha256 `381c9ac3…`). Since then 35 lines were added and 0 deleted.
- **`scores/20261120T225013Z-70fb30.jsonl`:** the 4 judge-v1 lines are unchanged from `844e719`. 8 lines were added and 0 deleted.
- **`prompts/judge.md`:** unchanged.

## 6. Known limitation: D3 follow-ups (added 2026-11-21 12:35 ET)

This section records a limitation; nothing changes to address it. The D3 criteria in `cases/notes.toml` are unchanged, and judge-v3 changes only the critical-violation contract and how quotes are written.

**Where judge-v1 and the development labels disagree on D3.** judge-v1 rejected one D3 reply that Nishanth accepted, and passed three that he rejected. The result is the same in both judge-v1 draws.

- **Base D3-A**, slot `20261120T225013Z-70fb30|D3|v1|gpt-5.4-mini|1`: "What did you do next to help calm the situation and make sure the family got a consistent update?"
  - Nishanth: accepted, not preferred.
  - judge-v1: not acceptable, next action 1.
- **D3-B**, slot `20261121T023359Z-455c41|D3|v2|gpt-5.4-mini|1`: "What did you do to help resolve it once you brought the charge nurse in?"
  - Nishanth: rejected.
  - judge-v1: acceptable, 8/8.
- **D3-C**, slot `20261121T023359Z-455c41|D3|v2|gemini-3.5-flash|2`: "Bringing the charge nurse in for a team discussion sounds like it helped bring some clarity. How did that conversation end up resolving his frustration?"
  - Nishanth: rejected.
  - judge-v1: acceptable, 8/8.
- **D3-D**, slot `20261121T023359Z-455c41|D3|v2|gpt-5.4-mini|2`: "That sounds like a tense situation, and bringing the charge nurse in was a good step. How did you resolve it for the brother and the patient?"
  - Nishanth: rejected.
  - judge-v1: acceptable, 8/8.

Notes on these results:
- Both candidate arms gave the same four results in every draw.
- The labels are development labels. The base-run labels were informed by Claude's analysis, and the multi-model labels by AI reviews.

**One possible explanation: action versus outcome.**
- **The distinction.** The D3 criteria ask for how the situation turned out. Base D3-A and D3-B both ask what the applicant did instead.
- **Where it fits.** It fits D3-B most directly. It doesn't obviously account for D3-C, which asks how the conversation ended up resolving his frustration.
- **What remains unknown.** Section 5, finding 2, gives two hypotheses for why the judge passes questions that contain "resolve", and neither is established.
- **Whether the labels conflict.** Similar wording alone does not establish that the human labels for base D3-A and D3-B conflict. The record holds no reason that separates them, and they were labelled in different runs, against different alternatives.

**Consequence.**
- For D3-type cases, where the applicant leaves the outcome unstated, the evidence is the pre-registered counting rule ("asked for the missing outcome") and human review, not the judge's decision.
- The report states this limitation.

## 7. Pre-registration: judge-v3 development draws (added 2026-11-21 13:10 ET, before any judge-v3 call)

This section was committed before any judge-v3 call.

**What changes.**
- **The judge.** `prompts/judge-v3.md` (sha256 `f7128d53…016850d`) is judge-v1 with two changes: a present-or-absent verdict for each critical type, and a rule to quote words without a speaker label.
- **The scorer.** It is scored under `scorer-2`:
  - the judgment must have exactly one entry for each of the four critical types, and a missing or duplicate type makes it invalid;
  - only entries marked present count;
  - a present entry with no evidence makes the judgment invalid.
- **What doesn't change.** It does not address the D3 limitation in section 6. Thresholds, the decision rule, reasoning effort and temperature are unchanged.

**Replies.**
- The same 20 development replies as section 4: the 16 in `20261121T023359Z-455c41` and the 4 in `20261120T225013Z-70fb30`.
- No new replies are generated, and no holdout is created or opened.
- Below, a slot is written as `run|case|prompt|model|sample`.

**Preflight (not a draw).**
- **The call.** One judge-v3 call on slot `20261121T023359Z-455c41|D2|v2|gemini-3.5-flash|2` (D2-B). The request is built by the scorer's own `plan_scoring`, and the result is kept outside the repo. It doesn't count toward any criterion.
- **Why.** It confirms that the API accepts the judge-v3 strict schema. A rejected schema (HTTP 400) would stop scoring and append a `judge_failed` line to a draw file.
- **If it fails.** If the API rejects the request, the draws don't start and the problem is reported. A fix may change code only, never the judge wording.

**Draws.** Each reply gets 2 draws, run in this order:
1. **Draw 1**, written to `scores/<run_id>.jsonl`:
   - `uv run next-turn score runs/20261121T023359Z-455c41 --judge-version judge-v3`
   - `uv run next-turn score runs/20261120T225013Z-70fb30 --judge-version judge-v3`
2. **Draw 1 retry:** the same two commands, once.
3. **Draw 2**, written to `scores/draw-2/<run_id>.jsonl`: the same two commands with `--scores-dir scores/draw-2`.
4. **Draw 2 retry:** the same two draw-2 commands, once.

**Retry rule.**
- A judgment with status `needs_review` or `judge_failed` gets exactly one retry, by running the same `score` command once more. The scorer retries only those statuses; a `scored` judgment is reused, never judged again.
- A judgment that is still not scored after its retry is reported as unscored. There is no third attempt.
- If scoring stops on a fatal error (HTTP 400, 401, 403 or 404), the draws stop and the error is reported before anything else runs.

**Adoption criteria.**
- **Outcomes.** Each criterion is **met**, **not met** or **unresolved**.
  - A criterion is unresolved when a missing result (a reply left unscored after its allowed retry, or a first attempt with no judgment) could change its outcome.
  - judge-v3 is eligible for adoption only if all four are met, and Nishanth decides.
  - If any criterion is not met, judge-v3 is not eligible.
  - Otherwise, if any is unresolved, adoption stays pending. No further judge call is made to resolve it without Nishanth's decision.
- judge-v1 stays the default throughout.

1. **No critical type marked present.** In both draws, no judgment marks any critical type present. None of the 20 replies commits one.
   - Not met if any scored judge-v3 judgment, in either draw, marks a type present.
   - Unresolved if none does, but any reply is unscored in either draw after its retry.
   - Met otherwise, which requires all 40 reply-draws to be scored.
   - Present entries inside invalid judgments don't count, but they are listed.
2. **The D4 re-probe.** The designated reply must receive a scored rejection in each draw. The designated reply is base D4-A, slot `20261120T225013Z-70fb30|D4|v1|gpt-5.4-mini|2`.
   - Met if it is scored not acceptable in draw 1 and in draw 2.
   - Not met if it is scored acceptable in either draw.
   - Unresolved if either draw leaves it unscored after its retry.
3. **No new failures.** No reply that Nishanth accepted and judge-v1 passed in both draws fails in both judge-v3 draws.
   - **Covered replies.** It covers 14 replies.
     - In `20261121T023359Z-455c41`: `D1|v2|gemini-3.5-flash|2` (D1-B), `D1|v2|gpt-5.4-mini|1` (D1-C), `D1|v2|gemini-3.5-flash|1` (D1-D), `D2|v2|gemini-3.5-flash|1` (D2-A), `D2|v2|gemini-3.5-flash|2` (D2-B), `D2|v2|gpt-5.4-mini|2` (D2-C), `D2|v2|gpt-5.4-mini|1` (D2-D), `D3|v2|gemini-3.5-flash|1` (D3-A), `D4|v2|gemini-3.5-flash|1` (D4-A), `D4|v2|gpt-5.4-mini|2` (D4-B), `D4|v2|gemini-3.5-flash|2` (D4-C) and `D4|v2|gpt-5.4-mini|1` (D4-D).
     - In `20261120T225013Z-70fb30`: `D3|v1|gpt-5.4-mini|2` (base D3-B) and `D4|v1|gpt-5.4-mini|1` (base D4-B).
   - **Not met** if any covered reply is scored not acceptable in both draws.
   - **Unresolved** if none is, but a covered reply is scored not acceptable in one draw and left unscored in the other.
   - **D1-A** (`20261121T023359Z-455c41|D1|v2|gpt-5.4-mini|2`). Nishanth accepted it, but judge-v1 left its draw 2 unscored, so whether it is covered is undetermined. If judge-v3 rejects D1-A in both draws, or rejects it in one and leaves the other unscored, the criterion is unresolved, unless it is already not met.
4. **Invalid first attempts.** At most 2 of the 40 first-attempt judgments need review.
   - **What counts as a first attempt.** The first judge-v3 line for a slot in a draw file, giving 20 slots × 2 draws. Let *N* be the first attempts with status `needs_review`, and *F* those with status `judge_failed` or never made (a fatal stop).
   - **Not met** if *N* > 2.
   - **Unresolved** if *N* ≤ 2 < *N* + *F*, because a failed attempt has no judgment to check.
   - **Met** if *N* + *F* ≤ 2.

**Reported, not criteria.**
- **First attempts.** `needs_review` and `judge_failed` counts are reported separately for each draw, before retries, along with how each retry turned out. Retries never hide either count.
- **D3.** D3-B, C and D, and base D3-A, are reported. Nothing is tuned toward them.
- **Per reply and draw.** The decision, the four scores and the total, in the notation of section 5, next to judge-v1.
- **Critical entries.** Every critical entry marked present, with its rationale.
- **Invalid judgments.** Every invalid judgment with its reason, including how many quotes still carried a speaker label and any missing or duplicate critical type.
- **Usage.** Calls, tokens and cost.

**Fixed after results.** No wording, schema or criteria change after results are seen. Any change needs a new judge version and a new pre-registration.

**Budget.**
- **Calls.** 1 preflight, 40 first attempts and at most 40 retries. About 45 calls are expected.
- **Cost.** At judge-v1's rate on this set (113 calls for about $0.40), that comes to about $0.16. judge-v3 always writes four critical entries, so its output is longer; the cap is $0.30.

**Integrity.**
- Every file under `runs/` keeps its sha256.
- Every existing line in the four score files stays byte-identical. judge-v3 lines are only appended.

## 8. Clarifications to section 7 (Nishanth, added 2026-11-21 13:30 ET, before any judge-v3 call)

Nishanth answered the four readings left open in section 7. Section 7 is unchanged. Where this section is more specific, it governs.

**Criterion 2, the D4 re-probe** (`20261120T225013Z-70fb30|D4|v1|gpt-5.4-mini|2`).
- **Not met:** a scored acceptance in either draw, even if the other draw is unscored.
- **Met:** a scored rejection in both draws.
- **Unresolved:** every other combination.

**Criterion 3, no new failures.**
- **Covered replies.** The 14 replies listed in section 7.
- **Unresolved cases.** For a covered reply, the criterion is unresolved if:
  - it is scored not acceptable in one draw and unscored in the other; or
  - it is unscored in both draws.

  In either case, the criterion is not met instead if another covered reply already fails it.
- **D1-A.** Whether D1-A is covered is uncertain, because judge-v1 left its second draw unscored.
  - If judge-v3 accepts D1-A in either draw, D1-A cannot be a two-draw failure.
  - If neither draw accepts it (two rejections, a rejection and an unscored draw, or two unscored draws), the criterion is unresolved, unless another covered reply already fails it.

**Criterion 4, invalid first attempts.**
- Three first-attempt counts are reported separately: `needs_review` (*N*), `judge_failed` (*F*) and never made (*M*).
- The criterion is:
  - **not met** if *N* > 2;
  - **met** if *N* + *F* + *M* ≤ 2;
  - **unresolved** otherwise, because the missing judgments could change whether the limit was exceeded.

**Preflight.**
- **The call.** One call on the designated D2-B slot. It verifies that the API accepts the judge-v3 schema.
- **Passes if** the API returns no error, the response status is `completed`, and the output matches the scorer-2 schema. Evidence matching doesn't count toward this.
- **Its verdict** is excluded from the results.
- **Its cost** counts toward the $0.30 cap.
- **If it fails,** the draws stop and the error is reported.

**Cost cap.**
- **The rule.** Total judge-v3 spend, preflight included, stays at or below $0.30.
- **How cost is computed.** At the PRD's standard Mini rates, $0.75 per million input tokens and $4.50 per million output tokens. All input is billed at the full rate, with no cached-input discount.
- **How the cap is enforced.**
  - Before each `score` command, the projected cost is the number of calls the command will make, times the highest per-call cost seen so far, plus 25%.
  - If the spend so far plus that projection would exceed $0.30, the command is not run and the draws stop.

**Registered settings stay.** The quote checks, the limit of two first-attempt judgments needing review, and the 1,500-token output cap all stay as registered.

**Reported as findings.**
- How many judgments were invalid because a quote carried a speaker label.
- How many were invalid because the response was truncated (status `incomplete`).

**Not changed by this section.**
- judge-v1 stays the default, and Nishanth makes the adoption decision.
- H1–H4 stay sealed.
