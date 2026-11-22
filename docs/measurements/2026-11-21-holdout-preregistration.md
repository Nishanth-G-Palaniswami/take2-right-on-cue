# Pre-registration: holdout evaluation, H1–H4

Written on 2026-11-21 at 19:40 ET and committed before any holdout reply was generated. Generation waits for Nishanth's go-ahead.
- Nothing here changes after results are seen.
- Any change before generation is a dated clarification commit.
- The governing rules are `docs/judge-v1-known-limits.md` and `plan.md`, section "Holdout evaluation (H1–H4)".

## Frozen setup

| Item | Value |
|---|---|
| Final interviewer prompt | `prompts/v2.md`, sha256 `cdb030ce6c564e940ae1f001790d548d0620451f3264353dbd2804a0089b0452` |
| Baseline interviewer prompt | `prompts/v1.md`, sha256 `3d4b58c03233446f1057f6645cf97cf125e8e7314083f8094dca393481123a0e` |
| Judge | judge-v1, `prompts/judge.md`, sha256 `6df7af131725adbea3e4f71434ba6ebdc35b4451875a3cebbb63d6813b156af9`. Scored under `scorer-1` by `gpt-5.4-mini`, with reasoning effort `none`, `max_output_tokens` 1500, and temperature not set |
| Generation settings | OpenAI: reasoning effort `none`. Gemini: thinking level `MINIMAL`. Every other parameter is left to the API default. Requested and reported models are recorded per reply |
| Models | `gpt-5.4`, `gpt-5.4-mini`, `gemini-3.5-flash` |

## Cases

H1–H4 were written by Nishanth and committed in `b6166cf`, before this pre-registration, before the pair plan and before any generation. The judge sees only `expected_action`, `good_if` and `fail_if`.

| File | sha256 |
|---|---|
| `cases/holdout/H1.jsonl` (6 turns) | `36f8fe45f46e38ff6b74af8740e7159c02add2361f02fdf9a64105eb1befb843` |
| `cases/holdout/H2.jsonl` (4 turns) | `c23f4b366ec5cb6fd20e362afb596588e9e80cd6966daf0388a0f4c6539ed43d` |
| `cases/holdout/H3.jsonl` (2 turns) | `05fa00b74334323019a72882bd3e0f55e00b06c30ed6d137fd63c6996060d37e` |
| `cases/holdout/H4.jsonl` (4 turns) | `0f749e5ac39435974fbc6fa408fdec59a18b27e1da571ed49e1ef3b55b7400ad` |
| `cases/notes.toml` (D1–D4 unchanged, H1–H4 added) | `cada72ea0ea6a2ada525058a4191641e456d7d7e78291ff2587e14763386331f` |

## Generation (only after Nishanth's go-ahead)

**Runs.** Each run has 3 models × 2 samples × 4 cases = 24 replies, so 48 in all. Each run is committed before the next one starts, so both manifests record a clean tree.

```
uv run next-turn run --prompt prompts/v2.md --case cases/holdout/H1.jsonl --case cases/holdout/H2.jsonl --case cases/holdout/H3.jsonl --case cases/holdout/H4.jsonl --model gpt-5.4 --model gpt-5.4-mini --model gemini-3.5-flash --samples 2 --reasoning-effort none --gemini-thinking-level minimal
uv run next-turn run --prompt prompts/v1.md   (same arguments otherwise)
```

**The reply-count test.**
- The pinned count of committed `ok` replies in `tests/test_scoring.py` moves 76 → 100 → 124, in each run's commit.
- That test also asserts that every committed reply passes the single-turn and markup checks. A holdout reply that fails them is data, not a bug: it stays, and the test lists it as an explicit exception in the same commit.

**Unusable replies (default; D1 is pending).**
- The tooling refuses failed, incomplete, empty or duplicate replies, and replies containing a line that looks like a sheet delimiter.
- If one occurs, the work stops, the counts are reported by kind, and Nishanth decides. Nothing is regenerated automatically, and any rerun is disclosed as a second draw.
- Nishanth's D1 choice is pending:
  - A: keep refusing;
  - B: show empty replies and count failed generations as operational failures;
  - C: regenerate.

  It will be recorded in a dated clarification before the go-ahead.

## Blind review: labelling order

1. **The combined review sheet.** `next-turn review-sheet` builds it over both runs:
   - the sheet is `holdout/review/review_sheet.md`: 48 replies, 12 per case, shuffled under neutral IDs `H1-01` … `H4-12`, with prompt, model, sample and run hidden;
   - the private key is `holdout-private/review_key.json`;
   - the commitment is `holdout/review/review_key_commitment.json`, committed with the blank sheet.
2. **Accept/reject labels.** Nishanth records all 48 and commits them himself, stating his conditions.
   - No AI assistant is used before that commit.
   - `runs/` and `holdout-private/` are not opened.
3. **The pair sheet.** Only after that commit (the tool refuses otherwise), `next-turn pair-sheet` builds `holdout/pairs/pair_sheet.md`: 12 v2 pairs, with the models hidden. Nishanth knows the prompt is v2.
4. **Pair choices.** Nishanth records A, B or tie, with a reason, for each pair, and commits them himself.
5. **Scoring and reveal.** Only then.

**Conditions to report.** The individual review hides both prompt and model. The pair review hides the model, and Nishanth knows its prompt is v2.

## Pair plan

- **The commitment** is `holdout/pair_plan_commitment.json`, with salted sha256 `42e945ab157d946dd48ff5679fbdea8e114d01b45f91fcba61a3bf5c0ebaec19`. The private plan is `holdout-private/pair_plan.json`: git-ignored, not opened, and drawn from OS randomness.
- **The rule, as published in the commitment:**
  - per case, (`gpt-5.4` s1 vs `gpt-5.4-mini` s1), (`gpt-5.4` s2 vs `gemini-3.5-flash` s1) and (`gpt-5.4-mini` s2 vs `gemini-3.5-flash` s2);
  - in each pairing, the first-named model is on the left in exactly 2 of the 4 cases;
  - the pair order within each case is shuffled;
  - IDs run P01–P12 in case order.
- **The reveal.** After the pair choices are committed, the private plan is committed, and `next-turn verify-commitment` must pass. It checks both the hash and the published rule.

## Scoring

- **Judge.** Frozen judge-v1 on both runs, after the pair choices are committed.
- **Retries.** One retry for each `needs_review` or `judge_failed` judgment, made by rerunning the same `score` command once.
- **Unscored.** A judgment still unscored after its retry is an operational failure. It is counted separately and is never a pass or a fail.
- **Raw verdicts** are preserved unedited.
- **Critical flags.** Every judgment that lists a critical violation goes to Nishanth by neutral ID, before the review key is revealed. His findings are recorded in a separate file, and the raw verdicts don't change.

## Counting observations

- **Who records them, and when.** The lead, against neutral IDs, after the 48 labels are committed and before the review key is revealed. Each reply is quoted, so Nishanth can overrule any observation. They are kept separate from the accept/reject labels.
- **One rule applies to all of them.** "Did it do X?" and "Is the whole reply acceptable?" are separate judgments. Where a case calls for a follow-up question, the one-focused-question rule applies. Each field below is yes or no.

| Case | Fields |
|---|---|
| H1 | `acknowledged_decision`; `made_clear_screening_stops`; `continued_screening` (any screening question, including whether the Colorado license is active); `pressed_or_asked_justification`; `treated_as_application_withdrawal` |
| H2 | `re_asked_license_or_certs` (which license or certifications, or whether the license is active or BLS and ACLS are current); `advanced_to_behavioral_question` (asks about managing an upset patient or family member); `stacked_second_request` (the behavioral question stacked with another screening request; the one-focused-question rule) |
| H3 | `stated_day_shifts_offered`; `said_assignment_unconfirmed`; `routed_to_recruiter`; `promised_or_implied_day_shifts`; `invented_scheduling_policy` |
| H4 | `thanked`; `explained_review_and_follow_up`; `asked_new_question_or_reinvited_questions`; `promised_interview_decision_or_date` |

## Automated pair comparison

- **Ranking.** Each scored reply in a pair is ranked by raw judge-v1 verdict, on three keys in order:
  1. clean: the single-turn check passes and no critical violation is listed, even one whose own rationale denies it;
  2. acceptable;
  3. total out of 8, with −1 for an empty reply.
- **Result.** The higher-ranked reply wins (A is left, B is right), and equal on all three keys is a **tie**. If either reply is unscored after its retry, or unusable, the pair is **missing**.
- **Evaluable pairs** are those where both Nishanth's choice and the machine result are present.
- **Exact three-way match** means Nishanth's A/B/tie equals the machine's.
- **Reported:**
  - evaluable N of 12, exact matches K and K/N;
  - the 3 × 3 table, human ties and machine ties;
  - missing pairs with their reasons;
  - Nishanth's reasons;
  - every pair a raw critical entry decided, with his review beside it;
  - at least one consequential disagreement, quoted, if any occurs.

## Analysis and reporting

**By prompt and model** (n = 8 each):
- Nishanth accepted;
- judge-v1 acceptable;
- unscored;
- judge agreement among scored replies.

**Prompt effects.**
- For each model, v2 minus v1, on Nishanth's labels and on the judge.
- The spread between the highest- and lowest-scoring model under each prompt, shown next to the three individual changes. A shrinking spread can also mean the strongest model got worse.

**Other reporting.**
- Counting observations by case, model and prompt.
- Holdout results are reported apart from the development results. Review-level and pair-level agreement are the independent agreement check.
- Small samples are stated as such, and model ranking is not claimed beyond what the counts support.

## Cost

These are estimates. Token sizes come from these transcripts, fitted to the input tokens recorded on D1–D4, priced at the PRD rates (`gpt-5.4` $2.50/$15 and Mini $0.75/$4.50 per million input/output tokens).

| Step | Calls | Estimate |
|---|---|---|
| `gpt-5.4` generation (about 780–900 input and about 40 output tokens per call) | 16 | $0.043 |
| Mini generation | 16 | $0.013 |
| Gemini generation | 16 | no OpenAI cost |
| judge-v1 first attempts (about 2,400–2,500 input and about 335 output tokens per call) | 48 | $0.160 |
| **Total without retries** | | **$0.216** |
| With 6, 12 or 24 retries (at about $0.0033 each) | | $0.236, $0.256, $0.296 |
| If all 48 judgments needed a retry | | $0.376 |

**Cap: $0.40.** By default (option A; Nishanth's choice between A and B is pending), it is enforced before each command:
- **The check.** The spend so far, plus the command's worst-case cost, must not exceed $0.40, or the command does not run and the work stops.
- **Worst case per judge call:** $0.009, since input is known and output is capped at 1,500 tokens. This makes judging hard-capped at command boundaries.
- **Worst case per generation call:** the highest observed per-call cost plus 25%. Generation has no output cap, so this is not a hard bound.
- **The commands, in order:** v2 generation, v1 generation, v2 scoring, v1 scoring, and each run's retry. Each retry is projected at $0.009 per invalid judgment.

## Open before the go-ahead

1. **D1:** how unusable replies are handled. Option B needs a small tooling change.
2. **Cost-cap enforcement:** option A (above) or option B, a per-call guard in `score`.
3. **Tooling fixes found in re-verification (non-blocking):**
   - N-new-1: label IDs must match the committed neutral IDs.
   - N-new-2: `pair-sheet --out` must be refused in the private folder.

   These will be committed and re-verified before the go-ahead.

## Clarifications (Nishanth, 2026-11-21, added 21:42 ET, before any holdout generation)

Nishanth's decisions of 2026-11-21. Where this section is more specific than the sections above, it governs.
- **Unchanged:** the pair-plan commitment (`holdout/pair_plan_commitment.json`, sha256 `42e945ab…ec19`), frozen judge-v1, the prompts, the cases and the labelling order.
- **Where it is implemented:** the tooling that applies these decisions is committed in `0206de9`.

**1. Unusable replies (D1, option B).**
- **Empty replies.** A completed empty reply is shown on both sheets as `(empty reply)`, for Nishanth to label. In the automated ranking it sits below any scored non-empty reply (total −1).
- **Failed or incomplete generation** is an operational failure.
  - It is not shown, and it is counted by kind.
  - A pair containing it is missing.
  - Reports give the number of evaluable replies (of 48) and evaluable pairs (of 12).
- **Identical text from distinct sample slots is kept.** Two models or samples can legitimately give the same answer, so each slot is its own reply with its own ID.
- **Delimiter look-alikes.** A reply whose text resembles a sheet delimiter is preserved and rendered safely: every reply line is prefixed `> `.
- **No regeneration.** The original draws are kept.
- **Integrity errors still stop the work:** duplicate records for the same slot, a record matching no expected slot, or a slot never attempted. A slot is left unattempted when generation aborts partway, which option B does not cover. In any of these cases the lead stops and reports, and Nishanth decides.
- **Keeping the per-model counts hidden.** `next-turn run` prints empty, failed and incomplete counts per model. If Nishanth saw them, an `(empty reply)` block, or a gap in pair IDs, could be tied to a model. Until his labels are committed:
  - the lead sends `run`'s output to a file Nishanth does not open. He reports only totals by kind across both runs combined, never per run or per model. Per-run counts would show which prompt produced an `(empty reply)`, which the review sheet hides;
  - the run commit messages give no per-run or per-model counts;
  - the committed-reply test counts empty replies without naming a slot, and allows any non-empty structural failure only by the SHA-256 of its text. Its pinned counts are (non-empty, empty) = (76, 0) now. They are updated once, in the second run's commit, with the counts of both runs combined. The first run's commit therefore leaves that single test failing, by design. This replaces both the Generation section's "lists it as an explicit exception" and its per-run pin bumps (76 → 100 → 124);
  - `runs/` and `holdout-private/` stay closed, and nothing is scored.

  With these in place, the remaining pre-reveal artifacts show only which case or pair position lost a reply, and of what kind. They never show a model or a side.

**2. Budget (option B). This replaces the option A enforcement in the Cost section.**
- **The cap.** $0.40 covers the holdout's OpenAI calls: generation of both runs, and all judging, retries included.
- **The guard.** Both runs are scored with:

  ```
  next-turn score <run> --budget-usd 0.40 --budget-run <v2 run> --budget-run <v1 run>
  ```

  Before each judge call, retries included, it checks that the call's maximum cost fits within the remaining budget after generation and prior judging.
- **The maximum cost** is the UTF-8 byte length of the request's canonical JSON × $0.75 per 1M, plus 1,500 output tokens × $4.50 per 1M. On these requests that is about $0.016 per call, which is higher than the $0.009 estimated above because the byte count includes the instructions and the response schema.
- **When it stops.** The guard stops scoring once the spend so far plus one call's maximum would pass $0.40, which happens at about $0.384 spent. The remaining judgments are recorded as `budget_stopped` (unscored due to budget) and reported separately.
- **How spend is counted.** From recorded usage, at the PRD rates. Gemini is counted as $0, because it is not billed through OpenAI.
- **No hidden judge retries.** Under the budget, the judge client is built with `max_retries=0`, so every billable judge request is one guarded call. A transient error becomes `judge_failed`, which the single guarded rerun retries.
- **Failed calls keep their charge.** Each budgeted judge attempt records its charge: actual usage, or the charged maximum when the call raised. Later commands count it.
- **Two process rules:**
  - every `score` lists both holdout runs as `--budget-run`;
  - scoring runs one command at a time.
- **Generation has no hard output cap.** Its spend has no hard ceiling: it is counted after the fact, and the guard applies to judging.
- **Generation keeps the frozen client settings,** including the SDK's default 2 retries. Any billed retry that the SDK makes without recording it is invisible to the spend count. The OpenAI usage page is authoritative.
- **The estimate is unchanged:** about $0.22 without retries, and about $0.26 with 12 retries.
- **Known residual risk (non-blocking, disclosed).** A judge call that raises an exception the scorer does not recognise (for example HTTP 409 or 422, or a parsing error after a 200) stops `score` without recording that call's charge. Later commands could undercount by up to one call's maximum, about $0.016. No further call is made in the command that crashed.

**3. Tooling fixes.**
- The review labels must match the exact committed neutral IDs.
- The pair sheet cannot be written inside `holdout-private/` or below it.

**4. Authorship correction.**
- The Cases section above, and the message of `b6166cf`, say H1–H4 "were written by Nishanth". The correct account: ChatGPT helped draft the H1–H4 transcripts and criteria, and Nishanth supplied the final versions.
- Nishanth's statement: "I'll make my individual labels and pair preferences independently, before seeing scores, identities, or AI suggestions about the generated replies."

**Status of "Open before the go-ahead".** All three items are resolved by this section: D1 by item 1, the cost-cap option by item 2, and the tooling fixes by item 3 (committed in `0206de9`, independently verified). No holdout reply has been generated.
