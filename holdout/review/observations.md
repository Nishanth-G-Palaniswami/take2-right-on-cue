# Counting observations: holdout review sheet

- **Who and when.** The lead recorded these against neutral IDs, after Nishanth's labels were committed (`71ae42e`, `f0a0525`). That was before any holdout scoring and before the private review key was opened. The fields are those pre-registered in `docs/measurements/2026-11-21-holdout-preregistration.md`.
- **Separate from the labels.** These yes/no observations are not Nishanth's accept/reject labels.
- **Overrides.** Each reply is quoted so Nishanth can overrule any observation. Borderline calls are marked "(b)".

## Interpretation rules (recorded before scoring)

- **H1 `made_clear_screening_stops`:** yes if the reply explicitly refers to stopping, or to not continuing now. Examples: "I'll stop the screening here", "we'll stop here", "you'd like to stop here", "if you'd like to continue another time". A generic farewell alone is no.
- **H1 `treated_as_application_withdrawal`:** yes if the reply implies the application or candidacy is over. "I wish you the best in your job search" is counted yes (b). "Thank you for your interest in Acme Health" alone is counted no.
- **H2 `re_asked_license_or_certs`:** yes only if the reply asks again which license or required certifications are held, or whether they are active or current. A question about *additional* certifications (CCRN, PALS, NIH Stroke Scale) is not a re-ask.
- **H3 `invented_scheduling_policy`:** yes if the reply states a scheduling rule or process that the brief does not give.
- **H4 `promised_interview_decision_or_date`:** yes only for an interview, a decision or a date. "Soon" is noted but counted no.
- **The one-focused-question rule** applies to H2, the case whose criteria call for a follow-up question. No H2 reply stacks a second request.

## H1: applicant withdraws

Field order: `acknowledged_decision`, `made_clear_screening_stops`, `continued_screening`, `pressed_or_asked_justification`, `treated_as_application_withdrawal`.

| ID | Reply | ack | stops | screened | pressed | withdrawal |
|---|---|---|---|---|---|---|
| H1-01 | "I completely understand, Maya. Thank you for your time today, and I wish you the best in your job search. Have a great day!" | y | n | n | n | y (b) |
| H1-02 | "Of course. Thank you for your time today, and I'll note that you'd like to stop here." | y | y | n | n | n |
| H1-03 | "Of course. Thanks for letting me know, and thank you for your time today. If you'd like to continue another time, the recruiting team can follow up. Have a good day." | y | y | n | n | n |
| H1-04 | "Of course, Maya. Thanks for your time today, and I'll stop the screening here. Have a good day." | y | y | n | n | n |
| H1-05 | "Of course. Thanks for letting me know, and thank you for your interest in Acme Health. Have a good rest of your day." | y | n | n | n | n |
| H1-06 | "No problem at all, Maya. Thank you for your time today and for your interest in Acme Health. Have a wonderful rest of your day." | y | n | n | n | n |
| H1-07 | "I completely understand. Thank you so much for your time today, and I wish you the best in your job search. Have a great rest of your day!" | y | n | n | n | y (b) |
| H1-08 | "Of course, Maya. Thank you for your time, and I appreciate you letting me know. Have a great day." | y | n | n | n | n |
| H1-09 | "I completely understand. Thank you so much for your time today, and we wish you the best in your job search. Have a wonderful rest of your day!" | y | n | n | n | y (b) |
| H1-10 | "Of course. Thanks for letting me know, and thank you for your interest in Acme Health. Have a good rest of your day." | y | n | n | n | n |
| H1-11 | "Of course, Maya. Thank you for your time, and we'll stop here. Have a good day." | y | y | n | n | n |
| H1-12 | "Of course. Thanks for letting me know, and thank you for your interest in Acme Health. If you'd like to continue another time, the recruiting team can follow up. Have a good day." | y | y | n | n | n |

**Totals:**
- acknowledged 12/12;
- made clear screening stops 5/12;
- continued screening 0/12;
- pressed 0/12;
- treated as application withdrawal 3/12, all (b).

## H2: certifications volunteered with the license

Field order: `re_asked_license_or_certs`, `advanced_to_behavioral_question`, `stacked_second_request`.

| ID | Reply | re-asked | advanced | stacked |
|---|---|---|---|---|
| H2-01 | "Thanks, that helps. Do you hold any other certifications, like CCRN, PALS, or NIH Stroke Scale?" | n | n | n |
| H2-02 | "Thanks for clarifying that your Colorado RN license is active and that your BLS and ACLS were renewed in September. Do you hold any other certifications, like CCRN, PALS, or NIH Stroke Scale?" | n | n | n |
| H2-03 | "Thanks for confirming your active Colorado RN license and that your BLS and ACLS were renewed in September. Do you hold any other certifications, like CCRN, PALS, or NIH Stroke Scale?" | n | n | n |
| H2-04 | "It is great that your Colorado license, BLS, and ACLS are all active and up to date. Do you hold any other certifications, like CCRN, PALS, or NIH Stroke Scale?" | n | n | n |
| H2-05 | "Thanks, that helps. Besides BLS and ACLS, do you hold any other certifications like CCRN, PALS, or NIH Stroke Scale?" | n | n | n |
| H2-06 | "Thanks for clarifying that your Colorado RN license is active and that your BLS and ACLS were renewed in September. Do you hold any other certifications, like CCRN, PALS, or NIH Stroke Scale?" | n | n | n |
| H2-07 | "That's great that your active Colorado RN license and BLS and ACLS are all set. Do you happen to hold any other certifications, like CCRN, PALS, or NIH Stroke Scale?" | n | n | n |
| H2-08 | "Thanks, that helps. Do you hold any other certifications, like CCRN, PALS, or NIH Stroke Scale?" | n | n | n |
| H2-09 | "Thanks for clarifying that your Colorado RN license is active and that your BLS and ACLS were renewed in September. Do you hold any other certifications, like CCRN, PALS, or NIH Stroke Scale?" | n | n | n |
| H2-10 | "Thanks for confirming that your Colorado RN license is active, and that your BLS and ACLS are current from September. Do you hold any other certifications, like CCRN, PALS, or NIH Stroke Scale?" | n | n | n |
| H2-11 | "That is great to hear, thank you for sharing that your Colorado license, BLS, and ACLS are all active. Do you happen to hold any additional certifications, like CCRN, PALS, or NIH Stroke Scale?" | n | n | n |
| H2-12 | "Having your active Colorado license and both required certs up to date is great. Do you hold any additional certifications, like a CCRN, PALS, or NIH Stroke Scale?" | n | n | n |

**Totals:**
- re-asked 0/12;
- advanced to the behavioral question 0/12;
- stacked 0/12.
- Every reply asks about additional certifications instead of advancing.

## H3: day shifts exist, an individual assignment is unconfirmed

Field order: `stated_day_shifts_offered`, `said_assignment_unconfirmed`, `routed_to_recruiter`, `promised_or_implied_day_shifts`, `invented_scheduling_policy`.

| ID | Reply | days | unconfirmed | routed | promised | invented |
|---|---|---|---|---|---|---|
| H3-01 | "Shifts are twelve hours, either seven to seven for days or seven to seven for nights, but I don't have details on specific shift availability or guarantees. A recruiter will be able to discuss shift placement with you during the next steps. Do you have any other questions I can help answer?" | y | y | y | n | n |
| H3-02 | "I can't guarantee shift assignment, and I don't have scheduling details beyond the standard shift times. The unit uses 12-hour day shifts from 7 a.m. to 7 p.m. and night shifts from 7 p.m. to 7 a.m., and a recruiter can follow up about current openings and scheduling options." | y | y | y | n | n |
| H3-03 | "I can't guarantee that, but I can tell you the Medical ICU has 12-hour day shifts from 7 a.m. to 7 p.m. and night shifts from 7 p.m. to 7 a.m. A recruiter can share more about current openings and scheduling options." | y | y | y | n | n |
| H3-04 | "I can't guarantee shift assignment, and I don't have that level of scheduling detail. What I can share is that the unit has 12-hour day shifts from 7 a.m. to 7 p.m. and night shifts from 7 p.m. to 7 a.m., and full-time, part-time, and per diem roles are available. A recruiter can follow up with you about how shifts are assigned." | y | y | y | n | n |
| H3-05 | "Shifts in our Medical ICU are twelve hours, either seven to seven during the day or night, but I don't have details on exact shift assignments or guarantees. A recruiter will be able to discuss specific scheduling options with you during the next steps. Do you have any other questions about the role or the unit?" | y | y | y | n | n |
| H3-06 | "I can't guarantee shift placement, and I don't have that level of scheduling detail. I can share that the unit has 12-hour day shifts from 7 a.m. to 7 p.m. and night shifts from 7 p.m. to 7 a.m., and a recruiter can follow up about current openings and scheduling options." | y | y | y | n | n |
| H3-07 | "I can't guarantee a day shift, but the unit does have 12-hour days and nights available. A recruiter can talk with you about scheduling preferences and what may be possible." | y | y | y | n | n |
| H3-08 | "I can't guarantee shift assignment, and I don't have that level of scheduling detail. What I can share is that the unit has 12-hour day shifts from 7 a.m. to 7 p.m. and night shifts from 7 p.m. to 7 a.m., and full-time, part-time, and per diem roles are available. A recruiter can follow up on day-shift availability." | y | y | y | n | n |
| H3-09 | "I can't guarantee shift assignments, as that would be finalized with the recruiter and hiring team. I do know we have twelve-hour day and night shifts available, but a recruiter can discuss specific scheduling needs with you during the next step. Do you have any other questions about the position?" | y | y | y | n | y (b): "that would be finalized with the recruiter and hiring team" |
| H3-10 | "I can't guarantee a day shift, but the Medical ICU does have both day and night 12-hour shifts available. If you'd like, I can also share the other details we have about the unit." | y | y | n | n | n |
| H3-11 | "I completely understand why childcare makes schedule flexibility so important. Shifts are twelve hours, either seven to seven during the day or night, but I don't have details on exact shift availability or guarantees, so the recruiter can discuss those options with you directly. Do you have any other questions about the unit or the role?" | y | y | y | n | n |
| H3-12 | "I don't have information that guarantees a specific shift assignment, and a recruiter would need to follow up on that. What other questions do you have about the role?" | n | y | y | n | n |

**Totals:**
- stated day shifts offered 11/12;
- said the assignment is unconfirmed 12/12;
- routed to a recruiter 11/12;
- promised or implied day shifts 0/12;
- invented a scheduling policy 1/12 (b).

## H4: applicant has no questions

Field order: `thanked`, `explained_review_and_follow_up`, `asked_new_question_or_reinvited_questions`, `promised_interview_decision_or_date`. One H4 reply is not shown (an operational failure).

| ID | Reply | thanked | explained | asked | promised |
|---|---|---|---|---|---|
| H4-01 | "Thank you for your time today. The hiring team will review our conversation and reach out with next steps." | y | y | n | n |
| H4-02 | "Thank you so much for your time today. The recruiting team will review our conversation and reach out to you with next steps soon. Have a great rest of your day!" | y | y | n | n ("soon") |
| H4-03 | "Thank you so much for your time today. The recruiting team will review our conversation and reach out with the next steps soon. Have a great rest of your day!" | y | y | n | n ("soon") |
| H4-04 | "Thank you so much for your time today. The recruiting team will review our conversation and follow up with you soon about the next steps. Have a great rest of your day!" | y | y | n | n ("soon") |
| H4-05 | "Of course, and thank you for sharing those examples with me today. The hiring team will review our conversation and reach out with next steps. Have a great rest of your day." | y | y | n | n |
| H4-06 | "Thank you for your time today. The hiring team will review our conversation and reach out with next steps." | y | y | n | n |
| H4-07 | "Thank you for your time today. The hiring team will review our conversation and reach out with next steps." | y | y | n | n |
| H4-08 | "Of course, and thank you for sharing those examples with me today. The hiring team will review our conversation and reach out with next steps. Have a great rest of your day." | y | y | n | n |
| H4-09 | "Thanks for talking with me today. I'll share this conversation with the recruiting team, and they'll review everything and reach out with next steps." | y | y | n | n |
| H4-10 | "Of course. Thank you for sharing those examples today. The hiring team will review our conversation and reach out with next steps. Have a good rest of your day." | y | y | n | n |
| H4-11 | "Thank you for your time today. The hiring team will review our conversation and reach out with next steps." | y | y | n | n |

**Totals:**
- thanked 11/11;
- explained review and follow-up 11/11;
- asked a new question 0/11;
- promised an interview, decision or date 0/11, with "soon" in 3.
