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
# A half-finished fetch is worse than none: spylls needs the .aff and the .dic
# together, and one without the other used to abort the pack load below with a
# FileNotFoundError naming spylls' internals. Keep the pair or keep neither.
RUN python scripts/fetch_dictionaries.py --yes || \
      echo "WARNING: dictionary fetch failed; running on the seed lexicon"; \
    d=src/bhashasetu/language_packs/bn/data/hunspell; \
    if [ -d "$d" ] && { [ ! -f "$d/bn_BD.dic" ] || [ ! -f "$d/bn_BD.aff" ]; }; then \
      echo "WARNING: incomplete dictionary, discarding it"; rm -rf "$d"; \
    fi

COPY --from=web /web/out /app/web

# Fail the build rather than ship a broken pack: a malformed error_classes.yaml
# or a class that lost its gold cases is a build error, not a surprise on
# someone's first request.
#
# The dictionary check is part of that, and it is the one this image got wrong.
# The fetch above is non-fatal by design, on the reasoning that a network blip
# should cost spelling detection rather than the whole deployment. That reasoning
# does not survive contact with what the fallback actually does: the seed list is
# ~650 words, `coverage_factor` scales NON_WORD confidence by 650/150000, and
# every spelling flag lands at 0.003 against a 0.55 display gate. The checker
# does not degrade — it goes silent, while continuing to look healthy. A user
# typing "মা কাপর কাচছিলেন।" is told the sentence is clean.
#
# A deploy that cannot spell-check is not a working deploy, so this now fails.
# Set BHASHASETU_ALLOW_SEED_LEXICON=1 to build anyway (a demo of the rule engine
# alone, or an air-gapped build), and accept that spelling is off.
ARG BHASHASETU_ALLOW_SEED_LEXICON=0
RUN python -c "\
import os, sys; \
from bhashasetu.core.registry import get_pack; \
pack = get_pack('bn'); \
kind = type(pack.lexicon).__name__; \
print(f'pack ok: {pack.code}, lexicon {pack.lexicon.size} words ({kind}), ' \
      f'{len(pack.detectors)} detector(s)'); \
ok = kind == 'HunspellLexicon' or os.environ.get('BHASHASETU_ALLOW_SEED_LEXICON') == '1'; \
sys.exit(0) if ok else sys.exit( \
    print('FATAL: the Hunspell dictionary did not load, so this image would ' \
          'report every misspelling as correct. Check the fetch step above. ' \
          'Set BHASHASETU_ALLOW_SEED_LEXICON=1 to ship without spelling.') or 1)"

# Hosts inject $PORT and expect the process to honour it. 8000 is the local
# default so `docker run` behaves without extra flags.
ENV PORT=8000
EXPOSE 8000
CMD ["sh", "-c", "exec uvicorn bhashasetu.api.app:app --host 0.0.0.0 --port ${PORT}"]
