# Deploying BhashaSetu

The app ships as **one container**: the frontend is exported to static HTML at
build time and served by the FastAPI process, so there is a single origin and a
single port. That is not only simpler to host — it is what keeps the httpOnly
device cookie first-party, the same reason `make web` proxies `/api` through
Next during development.

Nothing about the local workflow changes. `make api` + `make web` still run the
two servers separately; the static export only happens when
`BHASHASETU_STATIC_EXPORT=1` is set, which only the Docker build sets.

---

## Render (recommended — free, no card)

The repository contains [`render.yaml`](render.yaml), so the service is defined
in code rather than in dashboard settings nobody can review.

1. Sign in at **https://dashboard.render.com** with the GitHub account that owns
   the repository.
2. **New → Blueprint**, choose `shankha007/bengali-grammar-checker-app`, and
   approve the plan Render shows you. It reads `render.yaml`: one free Docker
   web service, health check on `/api/health`, and a generated value for
   `BHASHASETU_RECOVERY_PEPPER`.
3. First build takes roughly 5–8 minutes — most of it `npm ci` and the Next
   build. When it goes green the URL is
   `https://bhashasetu.onrender.com` (Render appends a suffix if the name is
   taken).

**Know before you share the link:** a free instance spins down after ~15 minutes
idle, and the next visitor waits ~50 s while it wakes. Every visit after that is
fast until it goes quiet again. Paid tiers remove the sleep; nothing else about
the deployment changes.

## Hugging Face Spaces (also free, no card)

Same image, no `render.yaml` needed:

1. **https://huggingface.co/new-space** → SDK **Docker** → blank template.
2. Push this repository to the Space remote, or point the Space at GitHub.
3. Add a Space secret `BHASHASETU_RECOVERY_PEPPER` with any long random string.

Spaces sets `PORT` to 7860; the `CMD` already honours `$PORT`.

## Anywhere else

Any host that can build a Dockerfile and inject `$PORT` will work — Fly.io,
Railway, Koyeb, a VPS:

```bash
docker build -t bhashasetu .
docker run -p 8000:8000 -e PORT=8000 bhashasetu
```

---

## What the image does

| Stage | Step |
|---|---|
| build | `npm ci`, then `next build` with `BHASHASETU_STATIC_EXPORT=1` → `out/` |
| runtime | `pip install -e ".[api,hunspell]"` |
| runtime | `scripts/fetch_dictionaries.py --yes` |
| runtime | loads the `bn` pack — a malformed pack fails the **build**, not a request |
| serve | `uvicorn` on `0.0.0.0:$PORT`, serving `/api/*` and the exported UI |

The Hunspell dictionary is **fetched during the build, never vendored** — it
carries its own licence (see the Licence section of the README). The fetch is
deliberately non-fatal: if it fails, the pack falls back to the bundled
580-word seed list and damps unknown-word confidence below the display
threshold. You lose spelling detection, not the deployment. To confirm which
one you got, check the build log for the warning.

## Environment variables

| Variable | Required | Meaning |
|---|---|---|
| `PORT` | injected by the host | Port to bind. Defaults to 8000. |
| `BHASHASETU_RECOVERY_PEPPER` | recommended | Peppers the recovery-phrase HMAC. Rotating it invalidates every issued phrase. |
| `BHASHASETU_WEB_DIR` | no | Where the exported frontend lives. The image sets it; locally it defaults to `frontend/out`. |

## Verifying a deployment

```bash
curl https://YOUR-URL/api/health
```

**Then check the dictionary, which is the one thing that can be wrong without
looking wrong:**

```bash
curl https://YOUR-URL/api/languages
```

`"dictionary":"hunspell"` with a `lexiconSize` around 80,000 is a healthy
deploy. `"dictionary":"seed"` with a `lexiconSize` under a thousand means the
build-time fetch failed and **spelling errors are not being reported at all** —
`coverage_factor` scales every `NON_WORD` confidence by roughly 650/150000, so
they land at 0.003 against a 0.55 display gate. The app does not error, does not
warn in the API response, and returns "no issues found" for plainly misspelt
Bengali. It looks like a working checker that thinks your text is fine.

Since this was first hit in production, three things guard it: the image build
now fails outright rather than shipping without a dictionary (override with
`--build-arg BHASHASETU_ALLOW_SEED_LEXICON=1`), the pack logs a loud warning at
startup, and the editor shows a banner instead of implying silence means clean.

A one-line check that distinguishes it from a stale deploy — type this into the
live editor:

```
মা কাপর কাচছিলেন।
```

Nothing flagged means the dictionary is missing. `কাপর → কাপড়` means it is fine.
(For contrast, `এর কারন কী?` flags in *both* cases: `NOTVA_SHOTVA` runs off a
hand-written list and is never dictionary-damped, so it is not a useful test.)

Then, against the live URL:

```bash
cd frontend && BASE_URL=https://YOUR-URL npm run e2e
```

That is the same 37-case browser suite CI runs — it types Bengali into the real
editor and asserts on what gets flagged. It was run against this exact
single-origin configuration locally before the deployment files were committed.
