# Walkthrough outline (5–10 minutes)

**Setup before recording:**
- **The app.** Either the hosted app (<https://rightoncue.nishanthgp.me>) with the access code, or the app running locally with your own keys (`uv run streamlit run app.py`).
- A terminal in the repo.
- `docs/report.md` open in a second tab.

**The live run is part of the video.** It shows the full workflow: load a prompt and a transcript, choose models and a sample count, generate, and inspect the scores. The form shows the projected maximum cost before anything is generated. With prompt v3 on `dev/D3.jsonl` and all three models:
- 1 sample: **$0.162194**;
- 2 samples: **$0.324388**.

The hosted cap is $5.00.

| Time | Segment | What to show and say |
|---|---|---|
| 0:00–0:40 | The decision | A hospital recruiting lead wants to know whether Riley can screen ICU nurse applicants, and on which model. The tool answers one narrow question: given the call so far, what should Riley say next? |
| 0:40–2:40 | A live run, end to end | Open **Run it yourself** and unlock it with the access code, or use your own keys locally. **Load:** keep prompt **v3** (the default) and pick the transcript **`dev/D3.jsonl`**: the applicant describes calling in the charge nurse for an upset brother, but not how it ended. Show that both the prompt and the transcript can be edited. **Select:** all three models, and a sample count of **2**. Read the projected maximum cost aloud before generating. **Generate.** **Inspect the scores:** under each reply, the judge-v1 verdict and total. Open "Scores, checks and reasoning" on one reply: the four dimension scores, the single-turn check and flags, and the judge's quoted evidence. Say whether each reply asks one question about the outcome, which is what v3 is for |
| 2:40–3:40 | The saved comparison | The first tab opens on H3 with prompt v2, the holdout run. Read the three replies; under each, point to the **raw judge-v1 verdict** and the **human label**. Switch prompt v2 → v1 and sample 1 → 2, then case H3 → H1, and show that the URL keeps the view. Point out the one operational failure (v1, Gemini, H4 sample 2), shown as a failure, not as a reply |
| 3:40–5:10 | Two prompt iterations | **v1 → v2** (one line: "ask one short follow-up about the missing part … then acknowledge and move on"). On D4 with GPT-5.4 Mini, v2 reduced re-asking a finished story from 2/5 to 0/5. GPT-5.4 still reopened one of two completed D4 stories under v2. **v2 → v3** (one line: ask about a missing outcome, and accept a given one, even a negative or unresolved one). **Where it helped (GPT-5.4, F6, same conversation and sample):** the applicant's story ends "it never really got resolved". v2 kept probing: "Is there anything else you did in the moment to help de-escalate the conversation?" v3 acknowledged it and moved on to the advocacy question. **Where it failed (GPT-5.4 Mini, T1):** the applicant gives the outcome but not what they did. v3 moved straight on ("Thanks, that sounds like you helped de-escalate things and ended on a positive note. Describe a time you advocated…"), where v2 asked "What did you do in the moment to help calm her and address her concerns?" (`docs/report.md`, both prompt-iteration sections) |
| 5:10–6:10 | A disagreement anyone can follow | **P08 (H3).** The judge preferred Mini's reply ("I don't have information that guarantees…"). The reviewer preferred GPT-5.4's, which gives the 7 a.m.–7 p.m. hours and a recruiter follow-up. Read both aloud, then explain why the human ranking is the useful one here. Then **H2**, in one sentence: every model asked about optional certifications instead of advancing. The reviewer accepted all 12; the judge followed the written criterion and rejected all 12. The criterion was too narrow |
| 6:10–7:30 | Results and the recommendation | Open the "How it was evaluated" tab: individual agreement 31/47, exact pair agreement 2/12 (12 evaluable), both from the original holdout across v1 and v2. The models are equal on safety. In the report, show the four-dimension table under the final prompt v3. The recommendation is a bounded **GPT-5.4 + v3** pilot; "Run it yourself" opens on that setup. We observed no regression for GPT-5.4 in the v3 regression check, and an observed regression for Mini. judge-v4 was tested and not adopted; one line on why |
| 7:30–8:30 | How it's built, and the limits | The CLI (`run`, `show`, `score`), blind review with committed hashes, and the frozen judge with known limits. **The limits:** one reviewer with AI-assisted labels for the holdout; ChatGPT labels for the v3 experiment; 2 samples per cell; text only. The raw evidence lives in `runs/`, `scores/`, `holdout/` and `docs/measurements/` |

**Before submitting:**
- **OpenAI usage.** Capture the usage-page screenshot for the project's date range. Recorded usage is about $1.33 through the holdout, plus $0.898091 for the later experiments, plus the live demo runs. The page is authoritative.
- **The video link.** Add it at the top of `README.md` ("Video walkthrough"), and check that it opens for a reviewer without signing in.
