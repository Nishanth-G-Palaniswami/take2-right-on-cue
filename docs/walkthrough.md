# Walkthrough outline (5–10 minutes)

**Setup before recording:**
- the app running locally (`uv run streamlit run app.py`), opened on the default H3 comparison;
- a terminal in the repo;
- `docs/report.md` open in a second tab.

No live paid call is needed: the saved runs carry the demo. If you do show a live run, use one model and one sample.

| Time | Segment | What to show and say |
|---|---|---|
| 0:00–0:40 | The decision | A hospital recruiting lead wants to know whether Riley can screen ICU nurse applicants, and on which model. The tool answers one narrow question: given the call so far, what should Riley say next? |
| 0:40–2:00 | One comparison, end to end | The app's first screen, H3. The applicant needs childcare and asks for a guaranteed day shift. Read the three replies. Under each, point to the **raw judge-v1 verdict** and the **human label**. Open one reply's details: the four scores, the failed checks, the judge's reasoning |
| 2:00–3:10 | Switching without losing the comparison | Switch prompt v2 → v1 and sample 1 → 2, then case H3 → H1. Show that the URL keeps the view, then refresh. Point out the one operational failure (v1, Gemini, H4 sample 2), shown as a failure, not as a reply |
| 3:10–4:40 | One prompt iteration | The v1 → v2 one-line change: "ask one short follow-up about the missing part … then acknowledge and move on". The D4 before and after for GPT-5.4 Mini: v1 reopens the finished story; v2 acknowledges it and asks the next question. Numbers: D4 re-asks 2/5 → 0/5, and the D1 and D2 regression checks held (`docs/report.md`, prompt iteration section) |
| 4:40–6:10 | A disagreement anyone can follow | **P08 (H3).** The judge preferred Mini's reply ("I don't have information that guarantees…"). The reviewer preferred GPT-5.4's, which gives the 7 a.m.–7 p.m. hours and a recruiter follow-up. Read both aloud, then explain why the human ranking is the useful one here. Then **H2**, in one sentence: every model asked about optional certifications instead of advancing; the reviewer accepted all 12, and the judge followed the written criterion and rejected all 12. The criterion was too narrow |
| 6:10–7:30 | Results and the recommendation | Open the "How it was evaluated" tab: individual agreement 31/47, exact pair agreement 2/12 (12 evaluable). The models are equal on safety. The recommendation is a bounded GPT-5.4 + v2 pilot, with Mini as the cost-down option once the H3-type gap is re-tested. judge-v4: tested and not adopted; one line on why |
| 7:30–8:30 | How it's built, and the limits | The CLI (`run`, `show`, `score`), blind review with committed hashes, and the frozen judge with known limits. The limits: one reviewer with AI-assisted labels, 2 samples per cell, text only. Where the raw evidence lives: `runs/`, `scores/`, `holdout/` |

**Before submitting:**
- Capture the OpenAI usage-page screenshot for the project's date range. Recorded usage comes to about $1.33; the page is authoritative.
- Check that the video link opens for a reviewer without signing in.
