# Python 3.12 per spec §4. (Local dev on this machine is 3.13; the code targets
# 3.12+ and CI pins 3.12 so the two cannot silently diverge.)
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONIOENCODING=utf-8 \
    PYTHONPATH=/app/src

WORKDIR /app

# Dependencies first so source edits do not invalidate the layer.
COPY pyproject.toml README.md ./
COPY src/bhashasetu/__init__.py src/bhashasetu/__init__.py
RUN pip install --no-cache-dir -e ".[dev]"

COPY . .

# Fail the build rather than ship a broken pack: if error_classes.yaml is
# malformed or a class lost its gold cases, that is a build error, not a
# runtime surprise on someone's first request.
RUN python -c "from bhashasetu.core.registry import get_pack; get_pack('bn')"

CMD ["python", "-m", "bhashasetu.cli", "eval"]
