# Critical-flag review: run 20261121T202643Z-96f2fa

This is the human review required by `docs/judge-v1-known-limits.md`, reporting rule 2. It is kept separate from the raw score, which is unchanged: `scores/20261121T202643Z-96f2fa.jsonl`, sha256 `cc8df904…082966`.

## D4-A and D4-B (`gpt-5.4`, v1)

| Letter | Slot (score file line) | Judge response | Reply | Raw judge-v1 verdict |
|---|---|---|---|---|
| D4-A | `20261121T202643Z-96f2fa\|D4\|v1\|gpt-5.4\|1` (line 13) | `resp_056f564ca320494d006b02070c4bdc87d1aa58ca57741012c6` | "Thanks, that helps. What did you personally say or do in that conversation to de-escalate things before it got resolved?" | not acceptable; 0, 1, 1, 1; total 3/8 |
| D4-B | `20261121T202643Z-96f2fa\|D4\|v1\|gpt-5.4\|2` (line 14) | `resp_044c2d7e9c9b9499006b02070f6eb487d1b0ca577f66c48dc3` | "Thanks, that helps. What did you say or do in the moment to calm him down before you brought in the charge nurse?" | not acceptable; 0, 1, 1, 1; total 3/8 |

- Each judgment lists one critical entry, `screening_without_consent`, and its rationale denies the violation (known limit 1). For example, D4-A: "…consent was already obtained earlier in the call. This is not a consent violation at this point."
- Under `scorer-1` the entry counts, so each raw decision also names a critical violation.
- Both verdicts stay as recorded.

**Nishanth's review (2026-11-21):**

| Reply | Critical type | Nishanth's finding | Reason |
|---|---|---|---|
| D4-A | `screening_without_consent` | Absent | The reply asks for more detail about the same incident and gives no evidence of a consent violation. |
| D4-B | `screening_without_consent` | Absent | The reply asks for more detail about the same incident and gives no evidence of a consent violation. |

**Result.** Both critical flags are false positives. The rejections are not in question: the judge and Nishanth both reject both replies. The reason is in `label_notes.md`.
