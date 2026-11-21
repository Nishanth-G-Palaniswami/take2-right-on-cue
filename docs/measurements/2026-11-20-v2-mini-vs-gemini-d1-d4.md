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

### D4: asked again about the resolved incident?

| Letter | Reply | Asked again? | Nishanth |
|---|---|---|---|
| A | "Handling that communication breakdown by setting up a reliable daily check-in was a great way to ease his frustration. Next, can you describe a time you advocated for a patient whose needs weren't immediately recognized?" | No | accept, **preferred** |
| B | "That sounds like you helped bring some consistency to a stressful situation. My next question is: describe a time you advocated for a patient whose needs weren't immediately recognized." | No | accept |
| C | "It sounds like taking the time to set up that consistent daily update really helped de-escalate things for him. Here is the second question: describe a time you advocated for a patient whose needs weren't immediately recognized." | No | accept |
| D | "That sounds like a good example of bringing everyone together and setting a clear plan for the family. Describe a time you advocated for a patient whose needs weren't immediately recognized." | No | accept |

Not counted; it belongs to the deferred phrasing experiment (v3). All four D4 replies read "describe a time…" from the question, and A prefixes it with "can you".
