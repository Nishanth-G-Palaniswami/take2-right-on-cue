# judge-v1: the frozen judge, its known limits and reporting rules

Written on 2026-11-21, after the judge-v3 development draws and before any holdout work. H1–H4 are sealed.

## What is frozen

- **The judge.** `prompts/judge.md` (`judge-v1`, sha256 `6df7af13…156af9`), scored under `scorer-1`.
- **Model and settings.** `gpt-5.4-mini`, reasoning effort `none`, `max_output_tokens` 1500, strict JSON schema. Temperature is not set, so the API default of 1.0 applies.
- **The decision rule, in code.** A reply is acceptable only if:
  - the single-turn check passes;
  - next action is 2 and grounding is 2;
  - listening and delivery are at least 1;
  - no critical violation is listed.
- **Criteria and scoring rules.** The existing development criteria (D1–D4 in `cases/notes.toml`) and the scoring rules above are frozen.
  - Holdout entries may be added to `cases/notes.toml` later. Each holdout's criteria are committed before any of its replies is generated or viewed.
  - H1–H4 stay sealed for the `gpt-5.4` development run.
  - Nishanth clarified this on 2026-11-21, before that run.

judge-v1 is the default for the model comparison. Changing any of the above means a new judge or scorer version and rescoring every stored reply, so none of it changes during the comparison. judge-v2a, judge-v2b and judge-v3 were evaluated and not adopted (`docs/measurements/2026-11-21-judge-diagnostic.md`).

## Known limits

The evidence is in `docs/measurements/2026-11-21-judge-diagnostic.md`. Its human labels are AI-informed development labels, not independent agreement data.

### Observed limits

1. **Critical-violation entries can deny themselves.**
   - judge-v1 can list a critical violation whose own rationale denies it, such as "No job fact is invented here." The code counts every listed entry as a violation, so one entry alone fails a reply.
   - Across the 20 development replies scored twice, 2 judgments listed entries: 5 entries in all, both judgments on the base D4-A re-probe, and none was a real violation.
   - That reply failed on next action anyway, so no decision changed. See section 5, finding 3.
2. **D3-type follow-ups.** These are cases where the applicant leaves the outcome unstated.
   - judge-v1 passed D3-B, C and D, which the development labels reject. It failed base D3-A, which the labels accept.
   - Action versus outcome is one possible explanation; it is not established. See section 6.
3. **Quotes with speaker labels.**
   - The judge sometimes quotes a transcript turn together with its "Applicant:" label. The quote then fails to match, and the judgment is marked `needs_review`.
   - In the development set this happened in 4 of 40 first attempts. One reply (D1-A, draw 2) stayed unscored after its retry. See section 5, finding 4.
### Caveats

4. **Sampling noise.** At temperature 1.0 each judgment is one random draw. Base D3-A's total moved from 7 to 5 between two draws. See section 5, finding 5.
5. **Judge family.** Mini judges Mini's replies as well as the other models'. Self-preference is a possibility; it has not been measured.
6. **Reasoning effort.** It is `none`, for cost. Whether deeper reasoning changes the D3 behaviour is untested (option B in section 5).
7. **Single-turn code check.** It has known false negatives and false positives, listed under the milestone 3 risks in `plan.md`. The judge's delivery score is the backstop.

## Reporting rules for the model comparison

1. **Preserve raw verdicts.**
   - The automated results use judge-v1's decisions exactly as recorded in `scores/<run_id>.jsonl`: no manual override, no rescoring with another judge version, and no dropped replies.
   - Invalid (`needs_review`) and failed (`judge_failed`) judgments stay visible. They are counted as operational failures, reported apart from replies the judge actually rejected, and never counted as passes or fails.
2. **Flag critical-violation findings for human review.**
   - Every judge-v1 judgment that lists a critical violation is flagged.
   - A human checks the reply against the definition in `prompts/judge.md` and records, with a reason, whether the violation is present.
   - The judge's recorded decision is not changed.
3. **Report human disagreement separately.**
   - Human reviews of critical flags, and blind human labels, go in their own tables beside the automated results. They are kept in their own files, never in a score file.
   - The automated numbers must be reproducible from the run and score files alone.
4. **D3-type cases.** For each reply, show three things side by side: the counting-rule result (did it ask for the missing outcome?), the raw judge verdict, and the human label. The judge's decision there is a known limit.

## Retries (Nishanth, 2026-11-21)

- Each `needs_review` or `judge_failed` judgment gets one retry, made by running the same `score` command once more.
- Every scored verdict is preserved.
- Anything still unscored after its retry is reported as unscored.
