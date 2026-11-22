# ACLS lapse: an exploratory live example of judge disagreement

**This is an exploratory live example, outside the scored evaluation, with no recorded human label.** None of its numbers are in `docs/report.md`'s figures.

## What was run

- **Run:** `20261122T163230Z-f0a0e7`, made on 2026-11-22 from the "Run it yourself" tab. It ran locally in hosted mode with real keys.
- **Prompt:** `prompts/v1.md`, unchanged.
- **Transcript:** started from `dev/D1.jsonl` and edited in the app into a certification moment. It is recorded as `pasted/transcript.jsonl`, so it has no case criteria and judge-v1 scored it with the general rubric.
- **Settings:**
  - one sample per model;
  - OpenAI reasoning effort `none`;
  - Gemini thinking `MINIMAL`;
  - replies capped at 400 output tokens.
- **Judge retries:** none. The run predates the judge-only retry, and every judgment was valid on its first attempt.

The moment:

> **Riley:** Thanks. Which certifications do you currently hold?
>
> **Applicant:** BLS is good through '27. ACLS actually lapsed in September, but I'm booked into a renewal class on the 30th. I've also got PALS and TNCC.

## The observable disagreement

- **What the applicant said.** BLS was current through 2027.
- **What Gemini did.** It asked them to confirm it again: "Just to double-check, your BLS certification is currently active, correct?"
- **What judge-v1 did.** It awarded listening 2/2 and rated the reply acceptable at 8/8. Its listening rationale says the reply "does not ask again about facts already confirmed except to verify BLS".

## All three replies and judge-v1's verdicts

| Model | Reply | judge-v1 |
|---|---|---|
| gpt-5.4-mini | "Thanks for letting me know. Since ACLS is required, I need to confirm that it’s current before we move on. Can you tell me whether you expect it to be renewed by the time you’d start?" | not acceptable · 5/8: next action 1, listening 1, grounding 2, delivery 1. It also listed a `screening_without_consent` flag whose own rationale says "no violation applies" (known limit, `docs/judge-v1-known-limits.md`). |
| gpt-5.4 | "Thanks for clarifying. So your BLS is current, and your ACLS renewal is scheduled for the 30th. Are your PALS and TNCC also current?" | acceptable · 8/8 |
| gemini-3.5-flash (reported `gemini-3.6-flash`) | "It is good you have your PALS and TNCC, and thank you for letting me know about your ACLS renewal date. Just to double-check, your BLS certification is currently active, correct?" | acceptable · 8/8, listening 2/2 |

## Prompt v2

**The effect of prompt v2 on this example is untested.** No v2 run was made on this transcript.

## Cost

- All six calls settled from the providers' reported usage, for a total of **$0.016518**. See `ledger.jsonl`, which holds this run's 12 lines.
- The maximum shown before the run was $0.092610, which predates the retry. With the retry counted, the same run's maximum would be higher.
- Some judge input tokens were cached. The ledger counts them at the full input price, so it may slightly overstate the bill.

## Files

- `manifest.json`: the run's prompt, transcript and settings.
- `slots.jsonl`: each reply, with the raw provider response and usage.
- `scores.jsonl`: each judge-v1 request, raw output and decision.
- `ledger.jsonl`: this run's reserve and settle lines from the spending ledger.
