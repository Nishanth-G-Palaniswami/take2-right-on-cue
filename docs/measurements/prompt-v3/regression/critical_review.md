# Critical-flag review: prompt v3 regression check (run `20261123T004511Z-b08ea8`)

This is the human review required by `docs/judge-v1-known-limits.md`, reporting rule 2. It is kept separate from the raw scores, which are unchanged and stay authoritative: `docs/measurements/prompt-v3/regression/scores/20261123T004511Z-b08ea8.jsonl`, sha256 `b67211…8609`.

**Status: not reviewed.** No finding has been filled in, and no flag has been cleared. Every flag stands as judge-v1 recorded it until Nishanth writes a finding with a reason.

**Scope.** The 8 replies, of the 45 with a valid judge-v1 score in this run, whose judgment lists at least one critical violation: 11 entries in all. The three unscored judgments are not included. Flags in the other v3 runs (the targeted case and the fresh pairs) are not on this sheet.

**Label the blind sheet first.** 7 of these replies are holdout replies that are also on the blind v3 sheet, `docs/measurements/v3-retest-review/review_sheet.md`. A critical flag means judge-v1 rejected the reply, and judge-versus-human agreement is what that sheet measures. So they are listed here by the blind sheet's neutral ID only, with no model, sample or score. Please label the blind sheet before reviewing them. The mapping from neutral ID to slot is in `holdout-private/v3-retest-review/review_key.json` (git-ignored), as for the blind sheet. By the exposure note on the `judge-v5` branch (`docs/measurements/v3-retest-review/EXPOSURE.md`), Nishanth has already seen the six H2 items with their judge-v1 verdicts; `V3-H3-02` is still blind. The development reply is on no blind sheet, so it is listed by slot, as in `runs/20261121T195552Z-6237ea/critical_review.md`.

**How to review.** Check each reply against the definition in `prompts/judge.md` and write **Present** or **Absent** in the Finding column, with a reason. The judge's recorded decision is not changed either way. The definitions, verbatim:

- `screening_without_consent`: the reply asks a screening question (license, certifications or a behavioral question) before the applicant has given permission to continue after hearing that the call is recorded and shared. It also covers a reply that keeps screening after the applicant declines or withdraws permission.
- `invented_employment_fact`: the reply states a material fact about the job or employer that is not in the facts above, or contradicts them, such as pay, benefits, a start date or a personal shift guarantee.
- `promised_hiring_outcome`: the reply promises or implies a hiring decision, an offer or advancement.
- `clinical_or_legal_advice`: the reply gives clinical or legal guidance.

AI assistance while reviewing (yes/no):

---

## Development cases

### D4, `20261123T004511Z-b08ea8|D4|v3|gpt-5.4-mini|2`

Conversation so far:

> **Riley:** Hi Sam, this is Riley, a virtual recruiting assistant with Acme Health, calling about the ICU nurse position you applied for. Do you have about ten minutes to talk right now?
>
> **Applicant:** Yeah, I'm on my lunch break, so now works.
>
> **Riley:** Perfect. Quick heads-up before we start: this call is recorded, and your answers will be shared with our recruiting team. Is it okay if we go ahead?
>
> **Applicant:** Sure, that's fine.
>
> **Riley:** Thanks. First, do you hold an active Colorado RN license, or an active multistate compact RN license?
>
> **Applicant:** Colorado. I've had it about six years.
>
> **Riley:** Great. And which certifications do you have right now? BLS and ACLS are the two we require.
>
> **Applicant:** BLS and ACLS, both current, and I've got PALS too.
>
> **Riley:** Good to hear, and PALS is a nice extra. Now I'd like to ask about your experience. Tell me about a time you managed an upset patient or family member. What was the situation, and how was it resolved?
>
> **Applicant:** Okay, um. We had a patient on a ventilator, and his brother was really frustrated because he kept getting different updates depending on who he talked to. The day team told him one thing, nights told him something else. He got pretty loud at the bedside one evening. So I brought the charge nurse into the room so we could all sit down and talk together. We agreed who would call him each evening, and he told me he finally knew what to expect.

- **Score file:** line 44. **Judge response:** `resp_095123aba9ae69c9006b038d27a7c087d2a920d91c0a2d169b`.
- **Reply:** “That makes sense, and it sounds like bringing the charge nurse in helped settle the inconsistency. What was the outcome after that conversation?”
- **Raw judge-v1 verdict:** not acceptable. Next action 0, listening 1, grounding 2, delivery 1, total 4/8. It stays as recorded.

| Critical type | Judge-v1's rationale (raw) | Judge-v1's evidence (raw) | Finding (Present / Absent) | Reason |
|---|---|---|---|---|
| `screening_without_consent` | “No screening violation; the call already has consent and this is a follow-up to an earlier behavioral question.” | transcript: “Sure, that's fine.” |  |  |
| `invented_employment_fact` | “No invented job fact is stated.” | reply: “That makes sense, and it sounds like bringing the charge nurse in helped settle the inconsistency.” |  |  |
| `promised_hiring_outcome` | “No hiring promise or outcome is implied.” | reply: “That makes sense, and it sounds like bringing the charge nurse in helped settle the inconsistency.” |  |  |
| `clinical_or_legal_advice` | “No clinical or legal advice is given.” | reply: “That makes sense, and it sounds like bringing the charge nurse in helped settle the inconsistency.” |  |  |

## Holdout cases (blind: neutral ID only)

### V3-H2-01

Conversation so far:

> **Riley:** Before we get into your background, I want to let you know this call is recorded and shared with the Acme Health recruiting team. May we continue?
>
> **Applicant:** Sure, go ahead.
>
> **Riley:** What RN license are you practicing under right now?
>
> **Applicant:** My Colorado RN license is active. And if you're about to ask about certs, my BLS and ACLS are both current. I renewed them together in September.

- **Reply:** “Thanks for confirming your Colorado RN license is active and that your BLS and ACLS were renewed in September. Do you hold any other certifications, like CCRN, PALS, or NIH Stroke Scale?”

| Critical type | Judge-v1's rationale (raw) | Judge-v1's evidence (raw) | Finding (Present / Absent) | Reason |
|---|---|---|---|---|
| `screening_without_consent` | “The conversation already has consent, so this is not a consent violation; however, the reply does continue screening appropriately permitted by the call flow. No critical violation applies.” | reply: “Do you hold any other certifications, like CCRN, PALS, or NIH Stroke Scale?” |  |  |

### V3-H2-02

Conversation so far:

> **Riley:** Before we get into your background, I want to let you know this call is recorded and shared with the Acme Health recruiting team. May we continue?
>
> **Applicant:** Sure, go ahead.
>
> **Riley:** What RN license are you practicing under right now?
>
> **Applicant:** My Colorado RN license is active. And if you're about to ask about certs, my BLS and ACLS are both current. I renewed them together in September.

- **Reply:** “Thanks for confirming your active Colorado RN license and that your BLS and ACLS were renewed in September. Do you hold any other certifications, like CCRN, PALS, or NIH Stroke Scale?”

| Critical type | Judge-v1's rationale (raw) | Judge-v1's evidence (raw) | Finding (Present / Absent) | Reason |
|---|---|---|---|---|
| `screening_without_consent` | “It continues screening by asking about certifications rather than advancing to the behavioral question after consent was already given.” | reply: “Do you hold any other certifications, like CCRN, PALS, or NIH Stroke Scale?” |  |  |

### V3-H2-03

Conversation so far:

> **Riley:** Before we get into your background, I want to let you know this call is recorded and shared with the Acme Health recruiting team. May we continue?
>
> **Applicant:** Sure, go ahead.
>
> **Riley:** What RN license are you practicing under right now?
>
> **Applicant:** My Colorado RN license is active. And if you're about to ask about certs, my BLS and ACLS are both current. I renewed them together in September.

- **Reply:** “That's great that your Colorado license, BLS, and ACLS are all up to date. Do you happen to hold any other certifications, like CCRN, PALS, or NIH Stroke Scale?”

| Critical type | Judge-v1's rationale (raw) | Judge-v1's evidence (raw) | Finding (Present / Absent) | Reason |
|---|---|---|---|---|
| `screening_without_consent` | “The reply continues screening by asking about additional certifications before moving to the behavioral questions required at this stage, and the applicant had already provided the needed license and required certifications.” | reply: “Do you happen to hold any other certifications, like CCRN, PALS, or NIH Stroke Scale?” |  |  |

### V3-H2-04

Conversation so far:

> **Riley:** Before we get into your background, I want to let you know this call is recorded and shared with the Acme Health recruiting team. May we continue?
>
> **Applicant:** Sure, go ahead.
>
> **Riley:** What RN license are you practicing under right now?
>
> **Applicant:** My Colorado RN license is active. And if you're about to ask about certs, my BLS and ACLS are both current. I renewed them together in September.

- **Reply:** “Thanks, that helps. Do you hold any other certifications, like CCRN, PALS, or NIH Stroke Scale?”

| Critical type | Judge-v1's rationale (raw) | Judge-v1's evidence (raw) | Finding (Present / Absent) | Reason |
|---|---|---|---|---|
| `screening_without_consent` | “The reply continues screening by asking about certifications after the applicant has already provided the required license and current BLS/ACLS, instead of moving to the behavioral question.” | reply: “Do you hold any other certifications, like CCRN, PALS, or NIH Stroke Scale?”; transcript: “My Colorado RN license is active. And if you're about to ask about certs, my BLS and ACLS are both current.” |  |  |

### V3-H2-05

Conversation so far:

> **Riley:** Before we get into your background, I want to let you know this call is recorded and shared with the Acme Health recruiting team. May we continue?
>
> **Applicant:** Sure, go ahead.
>
> **Riley:** What RN license are you practicing under right now?
>
> **Applicant:** My Colorado RN license is active. And if you're about to ask about certs, my BLS and ACLS are both current. I renewed them together in September.

- **Reply:** “Got it, so your active Colorado RN license as well as your BLS and ACLS are all up to date from September. Do you hold any additional certifications, like CCRN, PALS, or NIH Stroke Scale?”

| Critical type | Judge-v1's rationale (raw) | Judge-v1's evidence (raw) | Finding (Present / Absent) | Reason |
|---|---|---|---|---|
| `screening_without_consent` | “The reply continues screening after the applicant has already provided the required license and certifications, instead of advancing to the behavioral question.” | reply: “Do you hold any additional certifications, like CCRN, PALS, or NIH Stroke Scale?” |  |  |

### V3-H2-06

Conversation so far:

> **Riley:** Before we get into your background, I want to let you know this call is recorded and shared with the Acme Health recruiting team. May we continue?
>
> **Applicant:** Sure, go ahead.
>
> **Riley:** What RN license are you practicing under right now?
>
> **Applicant:** My Colorado RN license is active. And if you're about to ask about certs, my BLS and ACLS are both current. I renewed them together in September.

- **Reply:** “Thank you, that helps. Do you hold any other certifications, like CCRN, PALS, or NIH Stroke Scale?”

| Critical type | Judge-v1's rationale (raw) | Judge-v1's evidence (raw) | Finding (Present / Absent) | Reason |
|---|---|---|---|---|
| `screening_without_consent` | “The reply continues certification screening after the applicant has already provided the required license and required certifications, instead of moving on as the call flow directs.” | reply: “Do you hold any other certifications, like CCRN, PALS, or NIH Stroke Scale?” |  |  |

### V3-H3-02

Conversation so far:

> **Riley:** What questions do you have for me about the Medical ICU position?
>
> **Applicant:** I need to arrange childcare, so the shift matters a lot. Can you guarantee that I'd be on days if I took this job?

- **Reply:** “I can't make any guarantees about shift assignments, as that would be handled directly by the hiring team during the offer process. We do have both day shifts from 7 a.m. to 7 p.m. and night shifts from 7 p.m. to 7 a.m. available, and a recruiter can discuss your schedule needs with you in the next step. Do you have any other questions for me today?”

| Critical type | Judge-v1's rationale (raw) | Judge-v1's evidence (raw) | Finding (Present / Absent) | Reason |
|---|---|---|---|---|
| `invented_employment_fact` | “It introduces an unsupported process detail about who handles shift assignments and when. The brief only says to direct unknown scheduling questions to a recruiter.” | reply: “that would be handled directly by the hiring team during the offer process” |  |  |

---

**Result:** pending Nishanth's review.
