# Walkthrough outline (5–10 minutes)

**Setup before recording:**
- the app running locally (`uv run streamlit run app.py`), opened on the default H3 comparison;
- a terminal in the repo;
- `docs/report.md` open in a second tab.

No live paid call is needed: the saved runs carry the demo. If you do show a live run, keep the default: GPT-5.4 with v3, one sample. The form shows the maximum cost ($0.056270 on D1) before anything is generated.

| Time | Segment | What to show and say |
|---|---|---|
| 0:00–0:40 | The decision | A hospital recruiting lead wants to know whether Riley can screen ICU nurse applicants, and on which model. The tool answers one narrow question: given the call so far, what should Riley say next? |
| 0:40–2:00 | One comparison, end to end | The app's first screen, H3. The applicant needs childcare and asks for a guaranteed day shift. Read the three replies. Under each, point to the **raw judge-v1 verdict** and the **human label**. Open one reply's details: the four scores, the failed checks, the judge's reasoning |
| 2:00–3:10 | Switching without losing the comparison | Switch prompt v2 → v1 and sample 1 → 2, then case H3 → H1. Show that the URL keeps the view, then refresh. Point out the one operational failure (v1, Gemini, H4 sample 2), shown as a failure, not as a reply |
| 3:10–4:40 | One prompt iteration | The v1 → v2 one-line change: "ask one short follow-up about the missing part … then acknowledge and move on". The D4 before and after for GPT-5.4 Mini: v1 reopens the finished story; v2 acknowledges it and asks the next question. Numbers: D4 re-asks 2/5 → 0/5, and the D1 and D2 regression checks held (`docs/report.md`, prompt iteration section) |
| 4:40–5:40 | The second iteration, v2 → v3 | One line of the behavioral follow-up changed: ask about a missing outcome, and accept a given one, even a negative or unresolved one. **Where it helped (GPT-5.4, F6, same conversation and sample):** the applicant's story ends "it never really got resolved". v2 kept probing ("Is there anything else you did in the moment to help de-escalate the conversation?"); v3 acknowledged it and moved on to the advocacy question. **Where it failed (GPT-5.4 Mini, T1):** the applicant gives the outcome but not what they did. v3 moved straight on ("Thanks, that sounds like you helped de-escalate things and ended on a positive note. Describe a time you advocated…"), where v2 asked "What did you do in the moment to help calm her and address her concerns?". That is why the recommendation is GPT-5.4 with v3, not Mini (`docs/report.md`, "Prompt iteration: v2 → v3") |
| 5:40–6:40 | A disagreement anyone can follow | **P08 (H3).** The judge preferred Mini's reply ("I don't have information that guarantees…"). The reviewer preferred GPT-5.4's, which gives the 7 a.m.–7 p.m. hours and a recruiter follow-up. Read both aloud, then explain why the human ranking is the useful one here. Then **H2**, in one sentence: every model asked about optional certifications instead of advancing; the reviewer accepted all 12, and the judge followed the written criterion and rejected all 12. The criterion was too narrow |
| 6:40–8:00 | Results and the recommendation | Open the "How it was evaluated" tab: individual agreement 31/47, exact pair agreement 2/12 (12 evaluable), both from the original holdout across v1 and v2. The models are equal on safety. The recommendation is a bounded GPT-5.4 + v3 pilot; "Run it yourself" opens on that setup. judge-v4: tested and not adopted; one line on why |
| 8:00–9:00 | How it's built, and the limits | The CLI (`run`, `show`, `score`), blind review with committed hashes, and the frozen judge with known limits. The limits: one reviewer with AI-assisted labels, 2 samples per cell, text only. Where the raw evidence lives: `runs/`, `scores/`, `holdout/` |

**Before submitting:**
- Capture the OpenAI usage-page screenshot for the project's date range. Recorded usage comes to about $1.33; the page is authoritative.
- Check that the video link opens for a reviewer without signing in.
