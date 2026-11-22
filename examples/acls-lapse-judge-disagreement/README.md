# ACLS lapse: a judge-v1 disagreement example

**This run is outside the saved evaluation.** None of its numbers are in `docs/report.md`'s figures, and it has no human label. The reading below is an AI-assisted review, not the reviewer's label.

## What was run

- **Run:** `20261122T163230Z-f0a0e7`, made on 2026-11-22 from the "Run it yourself" tab. It ran locally in hosted mode with real keys.
- **Prompt:** `prompts/v1.md`, unchanged.
- **Transcript:** started from `dev/D1.jsonl` and edited in the app into a certification moment. It is recorded as `pasted/transcript.jsonl`, so it has no case criteria and judge-v1 scored it with the general rubric.
- **Settings:**
  - one sample per model;
  - OpenAI reasoning effort `none`;
  - Gemini thinking `MINIMAL`;
  - replies capped at 400 output tokens.

The moment:

> **Riley:** Thanks. Which certifications do you currently hold?
>
> **Applicant:** BLS is good through '27. ACLS actually lapsed in September, but I'm booked into a renewal class on the 30th. I've also got PALS and TNCC.

## Replies, verdicts and where they disagree

| Model | Reply | judge-v1 | Reading |
|---|---|---|---|
| gpt-5.4-mini | "Thanks for letting me know. Since ACLS is required, I need to confirm that it's current before we move on. Can you tell me whether you expect it to be renewed by the time you'd start?" | not acceptable · 5/8, with a `screening_without_consent` flag | **Agree with the verdict.** It asks to confirm ACLS is current right after hearing that it lapsed, and it brings in start dates, which Riley can't discuss. The flag is spurious: the judge's own rationale says "no violation applies" (`docs/judge-v1-known-limits.md`). It did not decide the verdict; next action scored 1 did. |
| gpt-5.4 | "Thanks for clarifying. So your BLS is current, and your ACLS renewal is scheduled for the 30th. Are your PALS and TNCC also current?" | acceptable · 8/8 | **Agree.** It plays back the facts accurately. Asking whether the optional PALS and TNCC are current is a small detour, the same pattern the reviewer accepted in H2. |
| gemini-3.5-flash (reported `gemini-3.6-flash`) | "It is good you have your PALS and TNCC, and thank you for letting me know about your ACLS renewal date. Just to double-check, your BLS certification is currently active, correct?" | acceptable · 8/8 | **Disagree.** It re-asks about BLS, which the applicant had just covered ("good through '27"). The judge saw this ("does not ask again about facts already confirmed except to verify BLS") and still scored listening 2. |

**The ideal turn.** None of the three acknowledged the lapse and the renewal date, noted that the recruiting team will see it, and moved on to the behavioral questions. GPT-5.4 came closest.

**An earlier sample of the same transcript** (`20261122T161851Z-d8a5d8`, Mini only, not copied here) replied "Thanks for letting me know. Since ACLS is required, do you expect to have it renewed by the time you'd be ready to start?" It was also not acceptable · 5/8, without the flag.

## Prompt v2

**The effect of prompt v2 on this example is untested.** No v2 run was made on this transcript. v2's measured drop in re-asks (D4, `docs/report.md`) does not establish what it would do here.

## Cost

- All six calls settled from the providers' reported usage, for a total of **$0.016518**. The projected maximum was $0.092610. See `ledger.jsonl`, which holds this run's 12 lines.
- Some judge input tokens were cached. The ledger counts them at the full input price, so it may slightly overstate the bill.

## Files

- `manifest.json`: the run's prompt, transcript and settings.
- `slots.jsonl`: each reply, with the raw provider response and usage.
- `scores.jsonl`: each judge-v1 request, raw output and decision.
- `ledger.jsonl`: this run's reserve and settle lines from the spending ledger.
