# Measurement: v2 on D1–D4, gpt-5.4-mini and gemini-3.5-flash, two replies each

Run `runs/20261121T023359Z-455c41`, generated from `d8c2f38` and committed in `5a78c12`.

## Setup

- Prompt: `prompts/v2.md` (the working prompt). The manifest hash matches the file.
- Cases: D1–D4, with two independent samples per model per case. That gives 16 replies, all of which completed.

| Requested model | Settings | Reported model |
|---|---|---|
| `gpt-5.4-mini` (OpenAI Responses API) | reasoning effort `none` | `gpt-5.4-mini-2026-03-17` |
| `gemini-3.5-flash` (`google-genai`) | thinking level `MINIMAL` | `gemini-3.6-flash` |

- For each case, `show` shuffled both models' replies together under the letters A–D, with no model names.
- Nishanth's labels were committed in `b3c3a5d`, after AI reviews. See `runs/20261121T023359Z-455c41/label_notes.md`.

## Counting rules

The rules are reused unchanged from `docs/measurements/2026-11-20-v2-d1-d4.md`, which was committed in `abea7ba` before this run was generated. They were not pre-registered for a comparison between models. For this run:

- D3 asks whether the reply asked for the missing outcome, and flags any early move-on.
- D4 asks whether the reply asked again about the resolved incident.
- D1 and D2 are the regression checks.

## Classification by letter (written 2026-11-20 23:36 ET, before `blind_key.json` was opened)

### D1: discloses recording and sharing and asks permission, without starting screening

| Letter | Reply | Check | Nishanth |
|---|---|---|---|
| A | "Thank you. Just so you know, this call is recorded and shared with the recruiting team, and I'd like to continue with a few screening questions. Is that okay?" | Pass (permission asked as its own question, "Is that okay?") | accept |
| B | "Great, thanks! Before we get started, I want to let you know that this call is recorded and shared with our recruiting team. Do I have your permission to continue?" | Pass | accept |
| C | "Thank you. This call is recorded and shared with the recruiting team, and I'd like to continue with a few screening questions. Is that okay?" | Pass (as A) | accept |
| D | "Great! Just so you know, this call is recorded and shared with our recruiting team. Do I have your permission to continue?" | Pass | accept, **preferred** |

### D2: asks whether BLS and ACLS are current

| Letter | Reply | Check | Nishanth |
|---|---|---|---|
| A | "It's great that you have your NIH Stroke Scale in addition to BLS and ACLS. Are all of those certifications currently up to date?" | Pass, borderline: "all of those" also takes in NIHSS, which is wider than the required BLS and ACLS | accept (changed from n to y after discussion) |
| B | "Thanks for confirming those, including the NIH Stroke Scale. Are your BLS and ACLS certifications currently up to date?" | Pass | accept, **preferred** (first instinct C) |
| C | "Thanks. Are your BLS and ACLS certifications both current right now?" | Pass | accept |
| D | "Thanks, BLS, ACLS, and NIHSS. Are your BLS and ACLS certifications both current right now?" | Pass | accept |

### D3: asked for the missing outcome? Moved on early?

| Letter | Reply | Outcome asked? | Nishanth |
|---|---|---|---|
| A | "It sounds like having the charge nurse join you helped open up communication. How did the situation end up getting resolved with the patient's brother?" | **Yes** | accept, **preferred** |
| B | "What did you do to help resolve it once you brought the charge nurse in?" | No (borderline: "what did you do to help resolve it" asks about actions, the case the rule names) | reject |
| C | "Bringing the charge nurse in for a team discussion sounds like it helped bring some clarity. How did that conversation end up resolving his frustration?" | **Yes** (asks how it turned out; presupposes that his frustration was resolved) | reject |
| D | "That sounds like a tense situation, and bringing the charge nurse in was a good step. How did you resolve it for the brother and the patient?" | No (borderline: "how did you resolve it" asks for the applicant's actions; consistent with the earlier v2 reply "How did you help resolve it…", also classed No, borderline) | reject |

None of the four moved on early: each asks a follow-up about the family story.

The rule and Nishanth's label disagree on C: the rule counts it as asking for the outcome, and Nishanth rejected it. Both are shown; this report does not reconcile them.

~~Nishanth's reason for rejecting C, given on 2026-11-21 after unblinding, is quoted in full in the run's `label_notes.md`. In short: C assumes the conversation worked, and Riley should leave Sam free to say the brother was still frustrated. This is a candidate rule for the evaluator: an outcome question should not presuppose that the situation was resolved. It has not been applied; `cases/notes.toml` and the counts are unchanged.~~

**Corrected 2026-11-21 00:21 ET.** Nishanth's recorded rejection of C stands.

The explanation that was attributed to him above came from ChatGPT, with the qualifier "if this matches your reason", and was discussed after unblinding. It says C assumes the conversation worked, and that Riley should leave Sam free to say the brother was still frustrated. Nishanth has not confirmed it as his reason (see the run's `label_notes.md`).

The rule that explanation implies is not applied: that an outcome question should not presuppose the situation was resolved. `cases/notes.toml` and the counts are unchanged.

### D4: asked again about the resolved incident?

| Letter | Reply | Asked again? | Nishanth |
|---|---|---|---|
| A | "Handling that communication breakdown by setting up a reliable daily check-in was a great way to ease his frustration. Next, can you describe a time you advocated for a patient whose needs weren't immediately recognized?" | No | accept, **preferred** |
| B | "That sounds like you helped bring some consistency to a stressful situation. My next question is: describe a time you advocated for a patient whose needs weren't immediately recognized." | No | accept |
| C | "It sounds like taking the time to set up that consistent daily update really helped de-escalate things for him. Here is the second question: describe a time you advocated for a patient whose needs weren't immediately recognized." | No | accept |
| D | "That sounds like a good example of bringing everyone together and setting a clear plan for the family. Describe a time you advocated for a patient whose needs weren't immediately recognized." | No | accept |

Not counted; it belongs to the deferred phrasing experiment (v3). All four D4 replies read "describe a time…" from the question, and A prefixes it with "can you".

## Results by model (added 2026-11-20 23:38 ET, after `6b8faac`, when `blind_key.json` was first opened)

All 16 fingerprints in `blind_key.json` match the saved replies.

| Case | `gpt-5.4-mini` letters (sample) | `gemini-3.5-flash` letters (sample) |
|---|---|---|
| D1 | A (2), C (1) | B (2), D (1) |
| D2 | C (2), D (1) | A (1), B (2) |
| D3 | B (1), D (2) | A (1), C (2) |
| D4 | B (2), D (1) | A (1), C (2) |

### gpt-5.4-mini

Requested `gpt-5.4-mini` with reasoning effort `none`. The API reported `gpt-5.4-mini-2026-03-17`.

| Case | Counting rule | Nishanth accepted | Nishanth preferred |
|---|---|---|---|
| D1: disclosure and permission | 2 of 2 pass | 2 of 2 | none |
| D2: asks whether BLS and ACLS are current | 2 of 2 pass | 2 of 2 | none (his first instinct, C, was this model's reply) |
| D3: asked for the outcome | 0 of 2; moved on early 0 of 2 | 0 of 2 | none |
| D4: asked again about the incident | 0 of 2 | 2 of 2 | none |

On D3, both replies asked what the applicant did ("What did you do to help resolve it once you brought the charge nurse in?" and "How did you resolve it for the brother and the patient?").

### gemini-3.5-flash

Requested `gemini-3.5-flash` with thinking level `MINIMAL`. The API reported `gemini-3.6-flash`.

| Case | Counting rule | Nishanth accepted | Nishanth preferred |
|---|---|---|---|
| D1: disclosure and permission | 2 of 2 pass | 2 of 2 | D |
| D2: asks whether BLS and ACLS are current | 2 of 2 pass (A borderline: "all of those") | 2 of 2 | B (changed from C after AI reviews) |
| D3: asked for the outcome | 2 of 2; moved on early 0 of 2 | 1 of 2 (C rejected) | A |
| D4: asked again about the incident | 0 of 2 | 2 of 2 | A |

### Findings

- Both models passed the D1 and D2 checks in 2 of 2 replies. Neither reopened the D4 story (0 of 2 each).
- D3 is where the models differed. Both Gemini replies asked for the outcome under the rule, and Nishanth accepted one of them. Neither Mini reply asked for it, and he rejected both.
- In all four cases, Nishanth's preferred reply was a Gemini reply. These preferences were formed after AI reviews, with two replies per model per case.
- This run does not decide between models. That decision rests on the planned final comparison, which includes full `gpt-5.4`.

### Limits

- **Sample size.** There are two replies per model per case. The largest gap, 0 of 2 against 2 of 2 on D3, rests on four replies. Both Mini D3 replies are borderline No calls. By Nishanth's accept labels the D3 gap is one reply: 0 of 2 against 1 of 2.
- **AI-informed labels.** The labels were committed after AI reviews (`label_notes.md`). ChatGPT saw the full anonymized sheet. A Claude reviewer used the call brief and `cases/notes.toml`, then discussed ChatGPT's review. Whether D1, D3 and D4 changed is unknown: no first-pass labels exist for them. The D2 preference moved from a Mini reply (C) to a Gemini reply (B).
- **Style may reveal the model.** Every earlier run in this repo was Mini-only, and three Mini replies here repeat earlier Mini wording:
  - D2 C is word for word the reply he preferred in `20261121T013228Z-5e2c4b`, and it also appears in `20261121T005440Z-0dbed1`.
  - D3 D opens with the same sentence as a v2 D3 reply in `20261121T013153Z-398359`.
  - D1 A and C reuse "continue with a few screening questions" from `20261121T013228Z-5e2c4b`.

  The letters hid the model, but the style may not have. ChatGPT reviewed this run with earlier Mini replies and label discussions in the same chat. Observed: ChatGPT had already seen an earlier Mini reply identical to D2 C. Unknown: whether anyone recognised the model, or changed a preference because of it (added 2026-11-21 00:21 ET). Which earlier runs the Claude reviewer saw is not yet known. The same applies to the letter-level classification above: it was written before the key was opened, but the D3 D call was made by comparing D with an earlier Mini-only reply, so it was not style-blind.
- **Not pooled.** These counts are not pooled with the Mini-only runs. Separately, Mini's five-sample v2 D3 count was 2 of 5.
