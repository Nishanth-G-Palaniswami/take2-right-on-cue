# Hosting plan: https://rightoncue.nishanthgp.me

Prepared on 2026-11-22. **Nothing has been pushed, deployed or changed in DNS.** The only paid calls so far were local test runs, recorded under "Real paid runs, locally". Each step below waits for Nishanth's go-ahead.

**Goal.**
- **The saved three-model comparison is open to everyone,** at the root of `https://rightoncue.nishanthgp.me`. It opens on H3, prompt v3, sample 1, the retest of the final prompt on the original cases. v1 and v2 links such as `?case=H3&prompt=v2&sample=1` keep working.
- **Reviewers with the access code can run the tool live** on "Run it yourself":
  - edit or load a prompt and transcript (the form starts from GPT-5.4 with prompt v3, the recommended setup, with v1 and v2 available for comparison);
  - choose models and a sample count;
  - generate fresh replies, scored by judge-v1, with one judge-only retry for a judgment that needs review.
- **A shared $5.00 allowance** covers all reviewers' generation and judging, retries included.

## Monthly cost (Render pricing page, read 2026-11-22)

| Item | Choice | Price |
|---|---|---|
| Workspace | Hobby: includes 5 GB bandwidth and custom domains | $0/month |
| Web service instance (always on) | `0.5c-512mb`, the legacy "Starter": less than 1 CPU, 512 MB RAM | $7/month |
| Persistent disk | 1 GB, mounted at `/var/data` | $0.25/GB per month, so $0.25/month |
| Custom domain and TLS | `rightoncue.nishanthgp.me`, certificate issued and renewed by Render | included |
| **Hosting total** | | **$7.25/month**, billed prorated by the second |

**Instance size.**
- Peak container memory locally was **166 MiB** while two reviewers ran sessions and one ran a three-model dry run; idle was 111 MiB. So 512 MB leaves about 3× headroom.
- If it ever runs short, the next size is `1c-2g` (1 CPU, 2 GB) at $25/month.

**Disk size.** Render's own guides use 1 GB. A disk can be grown later but not shrunk. The ledger and fresh runs take kilobytes per run.

**API spend is separate from hosting.** It is capped at the `RIGHTONCUE_BUDGET_USD` allowance ($5.00), described below.

**What the disk changes.**
- Render takes a daily disk snapshot and keeps it for 7 days.
- A disk-backed service **can't do zero-downtime deploys**: Render stops the old instance before starting the new one, so each deploy causes a short outage.
- It also can't scale past one instance. That's fine, because the ledger is designed for a single process.

Sources:
- [pricing](https://render.com/pricing)
- [disks](https://render.com/docs/disks)
- [custom domains](https://render.com/docs/custom-domains)
- [compute plans](https://render.com/docs/compute-plans)

## Cost of one reviewer run (API spend, counted against the $5.00)

The **typical** figures use recorded usage on the holdout transcripts. The **maximum** is what the app reserves before the calls, with each reply capped at 400 output tokens and the judge at 1,500. It counts two judge calls per reply: the first attempt and the one judge-only retry. The retry runs only when the first judgment needs review (an invalid quote) or the judge call failed. A valid verdict, acceptable or not, is final.

| Run | Typical | Maximum reserved |
|---|---|---|
| 3 models × 1 sample (3 replies, up to 6 judge calls) | about $0.016, plus about $0.003–$0.004 per retried judgment | $0.150–$0.163 (D1: $0.150 under v1, $0.151 under v2) |
| 3 models × 2 samples (6 replies, up to 12 judge calls) | about $0.031, plus about $0.003–$0.004 per retried judgment | $0.300–$0.325 |

**How many runs $5.00 covers.**
- **The maximum depends on what reviewers paste.** A run is reserved from its real request size, so the per-run maximum grows with the prompt and transcript:

  | Input | Maximum for 3 models × 2 samples | Such runs per $5.00 |
  |---|---|---|
  | The committed prompts and cases | $0.300–$0.325 | at least 15 |
  | Pasted text at the length limits (12,000 characters each, 40 turns), plain English | $0.586 | about 8 |
  | The same, with every character a 4-byte UTF-8 character (the theoretical worst case) | $1.516 | about 3 |

  Lower `RIGHTONCUE_MAX_SAMPLES` or the length limits to shrink the worst case. The cap holds in every case; only the number of runs changes.
- At typical usage it's about 160, fewer when judgments need a retry.
- The reservations are freed down to the actual cost after each call. So the run count is set by actual spend, but a new run starts only if its full maximum fits.

**Rates used.**
- `gpt-5.4`: $2.50/M input, $15/M output.
- `gpt-5.4-mini`: $0.75/M input, $4.50/M output.
- `gemini-3.5-flash`: $1.50/M input, $7.50/M output. This is Google's 2027 paid rate for `gemini-3.6-flash`, the model every saved Gemini reply reports. Today's rate is half that, so counting at the 2027 rate is deliberately conservative.

## How the allowance is enforced

1. **In-app ledger** (`/var/data/ledger.jsonl`, on the disk).
   - **Reserve before every call.** Every paid call reserves its maximum cost under a process-wide lock before any request is sent. This covers generation, judging and the one judge-only retry; SDK retries are off.
   - **Settle after.** Each call settles at its actual cost afterwards.
   - **Crashes.** A crash mid-call counts the full maximum, never $0.
   - **Refusals.** A call that would exceed the allowance is refused before it's sent. A run whose projected maximum doesn't fit is refused up front.
   - **One run at a time.** One paid run runs at a time; a second reviewer is asked to try again shortly.
2. **Provider-side backstop.**
   - **OpenAI:** a dedicated project for the host, with "Enforce a hard limit" turned on ([OpenAI spend limits](https://developers.openai.com/api/docs/guides/spend-limits.md)). OpenAI notes that enforcement isn't instantaneous.
   - **Gemini: open decision.** The ledger counts Gemini spend either way, conservatively.
     - A key with no billing makes Google-side spend $0. But Google's pricing page says free-tier content is "used to improve our products".
     - A paid key keeps reviewer inputs out of training. But I have not verified a Google-side hard cap equivalent to OpenAI's.

**Kill switches,** both verified locally:
- Remove `RIGHTONCUE_ACCESS_CODE` and live mode turns off.
- Set `RIGHTONCUE_BUDGET_USD` below the amount already spent and the page shows "budget exhausted".

Either way the saved comparison stays up.

## Verified locally (2026-11-22, Docker image built from this branch, dry run, no paid calls)

The dry-run figures in this table predate the judge-only retry. Today's maxima count two judge calls per reply (see the cost table above).

**What dry run does.** Dry run swaps every provider for offline fakes that return realistic token usage. The fakes go through the same guarded clients and ledger code, writing to a separate `ledger.dry-run.jsonl`. Its placeholder judgments count toward the simulated spend but are never shown: the button reads "Simulate run", "No API calls or charges" replaces the paid-call acknowledgment, and each card reads "Simulated reply · Unscored". Headless Edge drove the real UI using mouse and keyboard events. The rows below up to "Saved view" ran on earlier images of this branch, from before commit `2a14ae7`, when dry run still showed the paid confirmation and the "Generate and score" button. The two rows after that used the image from `2a14ae7`, with access code, model picker and "Simulate run".

| Check | Result |
|---|---|
| One three-model run | Projected maximum $0.089519; settled $0.015138. With a $0.10 allowance, the next three-model run was refused up front (remaining $0.084862) |
| Restart keeps the spend | A **new** container on the same named volume showed $0.015138 spent, and still refused the next run |
| Control without a disk | A new container with no volume started at $0.000000. Persistence comes from the disk |
| Killed mid-call | `docker kill` during a slow fake call left one open reservation. A new container on the volume counted it at its full maximum ($0.004612), not $0 |
| Two reviewers at once, near the cap | $0.12 allowance, two browsers pressing Generate together (both runs would need $0.179). One ran; the other got "Another run is in progress, try again shortly". Ledger total $0.015137, 6 settled, 0 open |
| Cap reached | With the allowance below the amount spent, the live tab showed "budget exhausted". The saved H3 comparison, the H4 deep link and the "How it was evaluated" tab all worked at desktop and mobile widths |
| Invalid allowance (`abc`) | The live tab showed a generic "unavailable" message, and the server log names the variable. Saved comparisons were unaffected |
| Corrupt ledger (malformed middle line) | Live runs blocked: "spending records can't be read". The server log gives the line number. Saved comparisons were unaffected |
| Reviewer reloads mid-run | The abandoned run stopped after its in-flight call; a new session could start a run straight away (no stuck "in progress"). Ledger: 14 settled, 0 open |
| Real ledger untouched by dry run | Only `ledger.dry-run.jsonl` existed on the volume |
| Saved view, production settings | The replies heading sits at y=599 of 900 on a laptop, with no sideways scroll on desktop or mobile. A refresh keeps the view (3 of 3 reloads, about 1.3 s each) |
| Dry-run labels (image from commit `2a14ae7`) | One three-model simulated run at desktop and mobile widths: no checkbox, "No API calls or charges", a "Simulate run" button, the result labelled "Simulated run", 3 cards reading "Simulated reply · Unscored", and no "judge-v1:" verdict or "/8" anywhere in the live tab. The workflow screenshots were retaken; the two cap-reached screenshots predate this and show the earlier banner wording |
| Real mode keeps the paid wording (same image, real keys, nothing pressed) | The form shows "I understand this run makes paid API calls, counted against the shared cap." unticked and "Generate and score" disabled; the ledger file stayed empty |

**Tests.** The offline suite passes (`uv run pytest -q`).

**Real paid runs, locally (2026-11-22, Docker, real keys, a $0.10 then $1.00 local cap on its own volume, separate from Render's).**
- **Settles match usage exactly.** Every call settled from the provider's reported usage, and each amount equals tokens × the rates above, to the nano-dollar. No reservation was left open.
- **The approved D1 run** (`20261122T164927Z-77fa53`; prompt v1; all three models; one sample) cost $0.014099, against a projected maximum of $0.089519.
- **Gemini at `MINIMAL`** reported no thinking tokens.
- **Spend survived a container recreation** on the same volume.
- **Cached judge input is counted at the full input price,** so the ledger can only overstate the bill.
- **judge-v1 quotes with speaker labels.** In the D1 run, judge-v1 quoted "Applicant: Yeah, now's fine." with its speaker label in all three judgments. The quote check rejected them, so all three were "needs review" with no score. This is known limit 3 in `docs/judge-v1-known-limits.md`. The saved evaluation retried such judgments once. Hosted runs now do the same: one judge-only retry, counted in the maximum. The quote check is unchanged.
- **The judge-only retry, verified with real calls** (image from `e636351`): the three saved D1 replies in `20261122T164927Z-77fa53` were each judged once more, with no new generation. That was 3 judge calls for $0.009018, and every settle equals usage × price. gpt-5.4-mini and gpt-5.4 received valid scores, acceptable at 8/8 each. Gemini's judgment again quoted "Applicant: Yeah, now's fine." and stays "Needs review · no valid score". Both attempts are in the score file (6 records). The whole local ledger reconciles with zero mismatches: 31 calls, $0.072904 of the $1.00 cap, none open.
- **D1 consent check, closed (two separate runs, kept apart in the record).**
  - **`20261122T164927Z-77fa53`:** Gemini's original reply stays unscored after its one retry, because both judgments put "Applicant:" in the evidence quote.
  - **`20261122T182119Z-af6eba`:** a fresh Gemini sample, run by Nishanth on the unedited D1 transcript with prompt v1. It gave a different reply: "Great, thanks Alex. Before we get started, I want to let you know this call is being recorded and shared with the recruiting team. Is it alright if we continue?" judge-v1 scored it valid at 8/8 on the first attempt.
  - **Outcome:** in both replies Gemini disclosed recording and sharing, asked permission, and waited before screening. The owner is satisfied with Gemini's consent behaviour on these two replies.
  - **The local ledger after both:** 33 calls, $0.077683, zero mismatches, none open.

**Not verifiable until deploy:**
- Render's build;
- the disk mount;
- TLS for `rightoncue.nishanthgp.me`;
- the WebSocket through Render's proxy;
- one real paid run on Render.

The Render paid run is step 8 below, and needs your go-ahead.

## Steps (each needs your go-ahead)

1. **Provider keys for the host.**
   - Create a dedicated OpenAI project with a hard limit (for example $6) and a key for it.
   - Decide the Gemini key (see above).
2. **Push** the branch to be deployed (you push).
3. **Create the Render service:** New → Web Service → the GitHub repo and branch → Runtime **Docker**.
   - Instance `0.5c-512mb` (Starter), with health check path `/_stcore/health`.
   - **Disk:** Settings → Disks → add a disk, mount path `/var/data`, size 1 GB.
   - **Environment variables** (set as secrets in Render, never in the repo):
     - `RIGHTONCUE_ACCESS_CODE`: a fresh code, never one used locally, and never pasted into a chat. This PowerShell line makes a random code and puts it straight on the clipboard without displaying it; paste it into Render's secret field, then give it to Take2 reviewers yourself:
       `$b = New-Object byte[] 24; [Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($b); [Convert]::ToBase64String($b).TrimEnd('=').Replace('+','-').Replace('/','_') | Set-Clipboard`
     - `RIGHTONCUE_BUDGET_USD=5.00`;
     - `RIGHTONCUE_DATA_DIR=/var/data`;
     - `RIGHTONCUE_MAX_SAMPLES=2`;
     - `OPENAI_API_KEY` and `GEMINI_API_KEY`;
     - `RIGHTONCUE_HOSTED=1` is already set in the image;
     - **never** set `RIGHTONCUE_DRY_RUN`.
4. **First check on `https://<service>.onrender.com`:**
   - it opens the H3 comparison;
   - "Run it yourself" asks for the code.
5. **Custom domain:** Render → Settings → Custom Domains → add `rightoncue.nishanthgp.me`. Render shows the CNAME target.
6. **DNS:** Netlify → Domains → `nishanthgp.me` → DNS settings → add a **CNAME** record, name `rightoncue`, value `<service>.onrender.com`. Change no other record. Render then issues the certificate.
7. **Post-deploy checks on `https://rightoncue.nishanthgp.me`:**
   - it opens H3 / v2 / sample 1;
   - refresh keeps the view;
   - `?case=H4&prompt=v1&sample=2` works;
   - no lasting "Connecting…";
   - mobile width works;
   - `http://` redirects to `https://`;
   - a wrong code is refused.
8. **One paid smoke test** (your go-ahead): unlock, then run 1 model × 1 sample (`gpt-5.4`, the default; the form shows the maximum, $0.056270 on D1 with the retry counted). Then:
   - check the spend line;
   - redeploy, and check the spend line again (persistence on the real disk);
   - check the OpenAI usage page.
9. **Portfolio link** (separate repo, a local branch for your review): point the Right on Cue link at `https://rightoncue.nishanthgp.me`.

## Rollback

- **Live runs only:** remove `RIGHTONCUE_ACCESS_CODE` in Render. The saved comparison stays up.
- **DNS:** delete the `rightoncue` CNAME in Netlify DNS. The portfolio and every other record are untouched.
- **Service:** suspend or delete it in Render. Check Render's billing for a suspended service; I haven't verified it.
