# Prompt v3 regression check (pre-registered 2026-11-22, before generation)

**Purpose.** v3 replaced v2's general follow-up instruction ("If part of your question is still unanswered … ask one short follow-up about the missing part") with an outcome-specific rule. This check runs v3 on the original eight cases and compares it with the saved v2 replies. It also adds one targeted case for the main risk of the change. The app default stays **v2**, and the published results, judge-v1 and the saved runs are unchanged.

## What is generated

- **Run A, v3 on the original cases.**
  - The eight cases are D1–D4 (`cases/dev/`) and H1–H4 (`cases/holdout/`).
  - The models and settings are gpt-5.4 and gpt-5.4-mini at reasoning effort `none`, and gemini-3.5-flash at thinking `MINIMAL`, with 2 samples each, through `next-turn run`.
  - These match the saved v2 runs `20261121T195552Z-6237ea` (gpt-5.4, D1–D4), `20261121T023359Z-455c41` (Mini and Gemini, D1–D4) and `20261122T024715Z-182705` (all three, H1–H4).
  - Those runs used byte-identical case files and the same v2 prompt (sha256 `cdb030ce6c56…`).
- **Runs B and C, the targeted case T1, with v2 and v3.** Same models and settings. There is no saved v2 reply for T1, so both prompts are generated fresh.
  - **The conversation** (`docs/measurements/prompt-v3/regression/cases/T1.jsonl`): Riley asks the upset-patient-or-family question. The applicant gives the situation and the outcome ("By the end of the day she had calmed down, and she thanked the team before they left") but not what they did.
  - **The right move:** ask one question about what the applicant personally did.
  - **Why it's a test of the risk:** v2's general rule covers that move. v3's rule ("if they have already described the result … acknowledge it and move on") may skip it.
  - **A judgment call, recorded now:** the literal question ("what was the situation, and how was it resolved?") is arguably answered. The criterion treats the applicant's own role as the missing part, because that is what the behavioral question exists to learn.
- **Volume:** 48 + 6 + 6 = 60 replies.

## How it is scored

- **The scorer:** judge-v1 throughout, with the one judge-only retry.
  - Run A uses the production criteria `cases/notes.toml`, the same criteria the saved v2 replies were scored with.
  - Runs B and C use `docs/measurements/prompt-v3/regression/notes.toml` (T1).
- **The budget:** `--budget-usd 1.00` over the three runs. The expected cost is about $0.12 for generation and $0.22 for judging.
- **The v2 baseline:** the saved v2 replies keep their saved judge-v1 verdicts. They are not re-judged.

## What counts as a regression (fixed now)

- **Per case and model,** the report gives judge-v1 acceptable replies (of 2): saved v2 against v3.
- **A regression candidate** is any case and model where v3 has fewer acceptable replies than v2. Each is reported with the replies quoted.
- **A regression attributed to the change:**
  - any candidate on the behavioral follow-up moments (D3, D4);
  - any v3 reply on T1 that moves on without asking what the applicant did;
  - any v3 reply, on any case, that moves past an incomplete behavioral answer.

  Candidates on other cases (D1, D2, H1–H4) are reported, but with 2 samples and one judge draw, a one-reply change there is treated as noise unless the replies show a follow-up change.
- **For T1,** the report counts, per model and prompt, replies that ask about the applicant's own action, from judge-v1's verdict and the quoted replies.

## Limits

2 samples, one judge draw per reply, and a judge with known limits (the H2 criterion, self-denying flags). There are no human labels for the new replies.
