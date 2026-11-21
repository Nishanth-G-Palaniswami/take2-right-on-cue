# Label notes: run 20261121T023359Z-455c41

Nishanth committed his labels for this run himself, in `b3c3a5d` (2026-11-20 23:33 ET). Written 2026-11-20 23:36 ET, before `blind_key.json` was opened.

## What the record says about AI assistance

There are only two statements on record, quoted exactly:

- The subject line of the label commit: "Record Nishanth's D1-D4 labels for the first multi-model run (after AI reviews)".
- A note on the D2 section of `blind_sheet.md`: "Revised after reviewing ChatGPT's and Claude's labels. First instinct was C; changed to B after adopting the conditional-acknowledgment rule. A changed from n to y after discussion."

Not recorded:

- Whether D1, D3 and D4 changed after the AI reviews.
- What the reviewing assistants were shown.
- What the "conditional-acknowledgment rule" says, beyond the D2 reason on the sheet.

This coding session gave no labels, preferences or comments on these replies before `b3c3a5d`. It showed the replies only.

## What this means for the record

- The labels are blind to the model and to sample order, because `blind_key.json` was not opened before `b3c3a5d`. They are not independent of other assistants' suggestions. Treat all four cases as human labels informed by AI, not as unaided human judgments.
- This run does not meet the plan's condition that labels are committed before any other model is consulted (`plan.md`, milestone 2 part 1, item 7).
- Any figure for agreement between a judge or a counting rule and these labels measures agreement with labels that other assistants may have shaped. Report it with this caveat, and keep it apart from unaided blind labels.

## Integrity checks (2026-11-20 23:36 ET)

- Since `5a78c12`, `blind_key.json`, `manifest.json` and `slots.jsonl` are unchanged.
- `blind_sheet.md` changed only in the answer fields, plus one added line that isn't an answer: the D2 note quoted above.
- `next-turn show` exits 0, and the sheet's SHA-256 is identical before and after.

## Nishanth's answers (2026-11-21 00:11 ET, after unblinding)

Given in reply to three questions asked after the results were reported (`c21fc81`). Quoted exactly.

**What the reviewers saw:**

> "ChatGPT saw the full anonymized D1–D4 sheet for this run, and earlier Mini replies and label discussions were already in the same chat. The separate Claude reviewer said it used the call brief and notes.toml. I later shared ChatGPT's review with it for discussion. I can confirm it reviewed the current replies, but I'd need to check its chat to say exactly which earlier runs it saw."

**Whether the labels changed:**

> "D2 is the documented change: my first instinct was C, and my recorded preference was B. I don't have a documented first-pass comparison for D1, D3, or D4."

Whether D1, D3 and D4 changed after the reviews therefore remains unknown.

**Why D3 C was rejected.** The message introduced this reason with "If this matches your reason, use:":

> "I rejected C because 'How did that conversation end up resolving his frustration?' assumes the conversation worked. Sam had only said he brought the charge nurse in. I wanted Riley to ask what happened and leave Sam free to say the brother was still frustrated."

This reason was given after unblinding. An earlier version of the measurement report (`ef40780`) had already suggested a similar explanation as Claude's inference. That inference was removed in `c21fc81`, before the question was asked.

What this adds to the record:

- ChatGPT reviewed this run with earlier Mini-only replies in the same chat. It could therefore have recognised Mini's wording, for example D2 C, which repeats an earlier Mini reply word for word.
- The Claude reviewer saw the expected behaviours in `cases/notes.toml`, and later saw ChatGPT's review.
