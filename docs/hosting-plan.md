# Hosting plan: https://rightoncue.nishanthgp.me

Prepared on 2026-11-22. **Nothing has been pushed, deployed or changed in DNS.** Each step below waits for Nishanth's go-ahead.

**Goal.** A public, no-key replay of the saved results at the root of `https://rightoncue.nishanthgp.me`.
- It opens directly on the saved three-model comparison of H3 (prompt v2, sample 1).
- Live evaluation stays local only.

## What exists today (checked 2026-11-22, read-only)

- **The portfolio is static.** `nishanthgp.me` is the Vite/React portfolio, served by Netlify (response header `Server: Netlify`, `netlify.toml` publishes `dist`). It is static, so it cannot run the Streamlit server itself.
- **DNS is Netlify DNS.** The nameservers are `dns1`–`dns4.p03.nsone.net`, and the SOA contact is `domains+netlify.netlify.com`. So the new record is added in Netlify's DNS panel.
- **The subdomain doesn't exist yet.** `rightoncue.nishanthgp.me` returns NXDOMAIN.

## Proposed host: Render web service (Docker)

**Why Render.**

| Requirement | Render's documentation |
|---|---|
| A custom domain on this exact subdomain, with HTTPS | Free web services support custom domains and managed TLS; certificates are issued and renewed automatically ([free](https://render.com/docs/free), [FAQ](https://render.com/docs/faq)) |
| WebSockets (Streamlit's live connection, `/_stcore/stream`) | WebSocket connections are a listed web-service feature ([web services](https://render.com/docs/web-services)) |
| Runs a long-lived Python server | Yes, as a web service. The Docker runtime uses the repo's `Dockerfile` |

**Alternatives ruled out.**
- **Netlify:** static and functions only. It probably doesn't proxy WebSockets ([staff answer](https://answers.netlify.com/t/does-netlify-support-websocket-proxying/11230)).
- **Streamlit Community Cloud:** no custom domains.
- **Hugging Face Spaces:** custom domains need a paid PRO or Team plan ([changelog](https://huggingface.co/changelog/custom-domains-for-spaces)).

**Free or paid instance (your choice).**
- **Free:** the service spins down after 15 minutes without traffic. The next visit takes about a minute, and Render shows a loading page meanwhile ([free](https://render.com/docs/free)).
- **Paid:** a paid instance does not spin down. Check the current price on Render's pricing page.
- For days when reviewers are likely to visit, a paid instance avoids the cold start.

## Verified locally (2026-11-22)

**The container.**
- `docker build -t rightoncue:local .` succeeded (image 1.42 GB).
- `docker run -p 127.0.0.1:3001:10000 -e PORT=10000 rightoncue:local` serves the app at `/`, and `/_stcore/health` returns `ok`.
- Inside the image: `RIGHTONCUE_HOSTED=1`, no `.env`, no `holdout-private/`, and no API-key variables. The saved `runs/`, `scores/`, `holdout/` and `docs/` are present.

**The browser,** using headless Edge over CDP at 1440×900 and 390×844 (mobile emulation), checked by DOM (screenshots in `docs/screenshots/`):
- the first screen is the H3 comparison: the applicant's question, then three model cards, each with the raw judge-v1 verdict and the human label;
- the replies heading sits at y=557 of 900 on desktop;
- there is no horizontal scroll at either width;
- cards sit side by side on desktop and stack on mobile;
- the deep link `?case=H4&prompt=v1&sample=2` opens that view, including the one operational failure (v1, Gemini, H4, sample 2);
- refresh keeps the view: 4 of 4 repeated desktop reloads, plus mobile. One earlier desktop refresh check failed once and did not reproduce;
- the "How it was evaluated" tab shows 31 of 47 and 2 of 12, and the experiment history.

**Tests.** 443 offline tests pass, including the app tests (AppTest), with no paid calls.

**Not verifiable until deploy:** Render's build, the TLS certificate for `rightoncue.nishanthgp.me`, DNS propagation, and the WebSocket through Render's proxy at that domain. These are covered by the post-deploy checks below.

## Steps (each needs your go-ahead)

1. **Push** the branch to be deployed (you push). It must contain the `Dockerfile`, `.dockerignore`, the app, and the committed `runs/`, `scores/`, `holdout/` and `docs/`.
2. **Create the Render service:** New → Web Service → the GitHub repo and branch → Runtime: **Docker** (`Dockerfile` at the root).
   - Instance type: Free or paid.
   - Health check path: `/_stcore/health`.
   - Environment variable: `RIGHTONCUE_HOSTED=1` (also set in the image).
   - **No API keys or secrets.**
   - Render sets `PORT`, and the image listens on it.
3. **First check on Render's own URL:** `https://<service>.onrender.com` opens the H3 comparison.
4. **Add the custom domain:** Render → Settings → Custom Domains → add `rightoncue.nishanthgp.me`. Render shows the CNAME target, `<service>.onrender.com`.
5. **Add the DNS record:** Netlify → Domains → `nishanthgp.me` → DNS settings → Add record: **CNAME**, name `rightoncue`, value `<service>.onrender.com`. Change no other record.
6. **Certificate:** Render verifies the record and issues the certificate automatically.
7. **Post-deploy checks on `https://rightoncue.nishanthgp.me`:**
   - it opens H3 / v2 / sample 1;
   - refresh keeps the view;
   - `?case=H4&prompt=v1&sample=2` works;
   - no lasting "Connecting…" state, which would mean the WebSocket is blocked;
   - mobile width works;
   - `http://` redirects to `https://`;
   - "Run it yourself" shows the local-only notice.
8. **Portfolio link (separate repo, a local branch for your review):** point the Right on Cue project link at `https://rightoncue.nishanthgp.me`.

## Rollback

- **DNS:** delete the `rightoncue` CNAME in Netlify DNS. The portfolio and every other record are untouched.
- **Service:** suspend or delete the Render service.

## Notes

- **No spending is possible from the hosted app.** It shows only committed data and needs no key. With `RIGHTONCUE_HOSTED=1`, live generation and scoring are hidden, so a visitor cannot spend money.
- **The data is already public.** Everything the image serves is already in the public GitHub repo: runs, scores, holdout labels and revealed mappings.
