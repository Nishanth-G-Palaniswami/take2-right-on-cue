# Right on Cue: hosted, no-key replay of the saved runs (Streamlit).
# Render builds this from the repo and sets PORT. No API key is baked in or needed.
# Live runs ("Run it yourself") stay off unless the HOST sets all of:
# RIGHTONCUE_ACCESS_CODE, RIGHTONCUE_BUDGET_USD, RIGHTONCUE_DATA_DIR (a persistent
# disk), OPENAI_API_KEY and GEMINI_API_KEY. Nothing here sets them, and
# RIGHTONCUE_DRY_RUN is never set in the image.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_LINK_MODE=copy \
    RIGHTONCUE_HOSTED=1

# uv, pinned, from the official image.
COPY --from=ghcr.io/astral-sh/uv:0.13.7 /uv /usr/local/bin/uv

WORKDIR /app

# Dependencies first (cached layer), exactly as locked, without dev tools.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# The app, the code and the saved evidence it replays.
COPY . .
RUN uv sync --frozen --no-dev

EXPOSE 10000
CMD ["sh", "-c", "uv run --no-sync streamlit run app.py --server.port ${PORT:-10000} --server.address 0.0.0.0 --server.headless true"]
