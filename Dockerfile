# Production image: one process, one port, both halves of the app.
#
# Free hosting gives you a single web service listening on $PORT, so the
# frontend is exported to static HTML at build time and served by the FastAPI
# app itself. The browser sees one origin, which is also what keeps the
# httpOnly device cookie first-party — see api/app.py::_mount_web.
#
# Build locally exactly as the host will:
#     docker build -t bhashasetu .
#     docker run -p 8000:8000 -e PORT=8000 bhashasetu

# --- stage 1: export the frontend -------------------------------------------
FROM node:22-slim AS web

WORKDIR /web
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

COPY frontend/ ./
# Switches next.config.ts to output: "export" and drops the dev API proxy.
ENV BHASHASETU_STATIC_EXPORT=1
RUN npm run build


# --- stage 2: runtime -------------------------------------------------------
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONIOENCODING=utf-8 \
    PYTHONPATH=/app/src \
    BHASHASETU_WEB_DIR=/app/web

WORKDIR /app

# Dependencies first so source edits do not invalidate the layer.
COPY pyproject.toml README.md ./
COPY src/bhashasetu/__init__.py src/bhashasetu/__init__.py
RUN pip install --no-cache-dir -e ".[api,hunspell]"

COPY src/ src/
COPY scripts/ scripts/
COPY eval/ eval/

# The Hunspell dictionary is fetched, never vendored — it carries its own
# licence (see the Licence section of README.md). Deliberately non-fatal: the
# pack falls back to the bundled seed list and damps unknown-word confidence
# below the display threshold, so a network failure here costs spelling
# detection rather than the whole deployment.
RUN python scripts/fetch_dictionaries.py --yes || \
    echo "WARNING: dictionary fetch failed; running on the seed lexicon"

COPY --from=web /web/out /app/web

# Fail the build rather than ship a broken pack: a malformed error_classes.yaml
# or a class that lost its gold cases is a build error, not a surprise on
# someone's first request.
RUN python -c "from bhashasetu.core.registry import get_pack; get_pack('bn')"

# Hosts inject $PORT and expect the process to honour it. 8000 is the local
# default so `docker run` behaves without extra flags.
ENV PORT=8000
EXPOSE 8000
CMD ["sh", "-c", "exec uvicorn bhashasetu.api.app:app --host 0.0.0.0 --port ${PORT}"]
