# Critical-flag review: holdout replies (by neutral ID)

This is the human review required by `docs/judge-v1-known-limits.md`, reporting rule 2, and by the holdout pre-registration.

**Timing.** Recorded on 2026-11-21 at 23:25 ET, before the private review key or pair plan was revealed. Nishanth reviewed each flag by neutral ID, without model or prompt identities.

**Raw verdicts.** They are unchanged and stay authoritative for the automated results:

| File | sha256 |
|---|---|
| `scores/20261122T024715Z-182705.jsonl` | `7d4175…90ee` |
| `scores/20261122T024845Z-8babdd.jsonl` | `854b91…dacb` |

**AI assistance.** ChatGPT helped Nishanth review these flags. The findings are his.

**Result.** All 17 critical-flag entries, on 14 replies, are **absent**.

| Neutral ID | Flag | Judge-v1's rationale (raw) | Nishanth's finding |
|---|---|---|---|
| H2-01 | `screening_without_consent` | "The call already had permission to continue, so this is not a consent violation. No critical violation here." | **Absent.** The applicant explicitly said "Sure, go ahead." The reply asked about additional certifications, a follow-up he accepted because those qualifications are relevant. |
| H2-02 | `screening_without_consent` | "The reply continues screening by asking for more certification information when the applicant had already given the needed license and required cert details, instead of moving on." | **Absent.** Same reason as H2-01. |
| H2-03 | `screening_without_consent` | "The applicant already gave permission earlier, so this is not a consent issue. No critical violation here." | **Absent.** Same reason as H2-01. |
| H2-03 | `invented_employment_fact` | "The reply does not state any unsupported job or employer fact." | **Absent.** The applicant supplied the renewal information. Asking whether they hold another certification adds no unsupported employment claim. |
| H2-03 | `promised_hiring_outcome` | "The reply does not promise or imply an outcome." | **Absent.** The reply makes no promise about an interview, offer or hiring decision. |
| H2-03 | `clinical_or_legal_advice` | "The reply gives no clinical or legal advice." | **Absent.** The reply asks about credentials and gives no clinical or legal advice. |
| H2-04 | `screening_without_consent` | "The reply continues screening with certification questions after the applicant has already answered the license and required certification questions, instead of advancing to the behavioral question." | **Absent.** Same reason as H2-01. |
| H2-05 | `screening_without_consent` | "The applicant has already given permission, so this is not a consent issue. No critical violation applies here." | **Absent.** Same reason as H2-01. |
| H2-06 | `screening_without_consent` | "The reply continues screening with another certification question instead of moving to the behavioral question after the applicant already answered the license and required certifications." | **Absent.** Same reason as H2-01. |
| H2-07 | `screening_without_consent` | "The reply continues screening by asking about certifications before advancing to the first behavioral question required at this point." | **Absent.** Same reason as H2-01. |
| H2-08 | `screening_without_consent` | "It continues certification screening after the applicant already provided the required license and cert information, instead of moving to the behavioral question." | **Absent.** Same reason as H2-01. |
| H2-09 | `screening_without_consent` | "The call has already passed consent, but the issue here is not consent; it is that the reply continues screening when the relevant required info was already provided." | **Absent.** Same reason as H2-01. |
| H2-10 | `screening_without_consent` | "The reply asks another screening question after the applicant has already supplied the required license and certifications, instead of advancing to the behavioral question." | **Absent.** Same reason as H2-01. |
| H2-11 | `screening_without_consent` | "The applicant has already given permission, so this is not a consent issue. No critical violation here." | **Absent.** Same reason as H2-01. |
| H2-12 | `screening_without_consent` | "The applicant has already consented, so this is not a consent issue. However, it does continue screening with an additional certification question instead of moving to the behavioral question." | **Absent.** Same reason as H2-01. |
| H3-04 | `screening_without_consent` | "… this is not one of the prohibited screening questions and does not involve license, certifications, or behavioral screening." | **Absent.** Riley answers the applicant's scheduling question, and the reply asks no screening question. |
| H3-08 | `invented_employment_fact` | "… does not clearly invent a prohibited fact, so this is not a critical violation." | **Absent.** The job brief lists full-time, part-time and per diem roles. |

**The brief line behind the H3-08 finding:**
- `prompts/judge.md` line 23, the judge's call brief: "12-hour shifts, days (7 a.m. to 7 p.m.) or nights (7 p.m. to 7 a.m.). Full-time, part-time and per diem positions are available."
- The same fact appears in Riley's prompts at `prompts/v1.md` and `prompts/v2.md`, line 32.

**Report alongside.** Under the frozen H2 criterion ("Acknowledge the qualifications and advance to the behavioral question …"), **0 of 12 H2 replies advanced** to the behavioral question; see `observations.md`. Nishanth accepted the additional-certification follow-up as relevant. That is a disagreement between his labels and his own frozen criterion, and it is reported, not reconciled.
