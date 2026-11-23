# Prompt v3 experiment: label notes

## First return: AI-generated labels, kept separately

- **What came back.** The first filled sheet, returned on 2026-11-22, had all 96 decisions (67 `y`, 29 `n`) and 96 reasons. It is kept unchanged as `review_sheet_chatgpt.md`. Its attribution line reads, quoted exactly:

  > Reviewer attribution: ChatGPT supplied all 96 decisions and reasons using the requester’s summary of feedback from two students preparing to become doctors. The students gave feedback on sample interviews. These entries are AI-generated judgments.

- **Why it is not the primary measure.** The plan's primary measure is Nishanth's own blind labels (`docs/measurements/2026-11-22-prompt-v3-plan.md`). These are AI-generated judgments, not human labels.
- **What was decided.** Before any reveal, Nishanth chose to label a fresh blank copy himself.
  - `review_sheet.md` was restored to the blank sheet committed in `032930b`. It matches its hash in `commitment.json`.
  - ChatGPT's labels will be reported as a second, AI-generated set, beside his labels and judge-v1's.
- **Blindness.** Nothing was revealed: the key, the generation log and the runs are still private. ChatGPT saw only the blind sheet. Nishanth has seen ChatGPT's decisions, so his labels are blind to model and prompt, but not independent of those decisions.

## Decision: these labels are the ones used (2026-11-22, before the reveal)

- **Nishanth's decision.** Use `review_sheet_chatgpt.md` as the labels for this experiment. His account, quoted exactly:

  > No, use the chatgpt.md itself, review sheet chatgpt.md, because even though ChatGPT did it, I had a call with two other medical students who told me which looks right and which looks wrong. It read through, translated the transcript, and then this gave me the updated files

- **Their status.**
  - The source is two medical students' judgments from a call.
  - ChatGPT turned the call transcript into the 96 decisions and reasons. The sheet itself calls them "AI-generated judgments".
  - They are not Nishanth's own labels, and they are not an unaided human check.
  - The record doesn't show whether the students judged each of the 96 replies individually or ChatGPT applied their feedback to the items.
- **The deviation.** The plan's primary measure was Nishanth's own blind labels. These labels replace that measure, and the deviation is reported with the results.
- **Blindness.** ChatGPT and the students saw only the blind sheet: conversations and replies under neutral IDs, with no model, prompt or score. Nothing had been revealed.
- `review_sheet.md` stays blank, as committed in `032930b`.
