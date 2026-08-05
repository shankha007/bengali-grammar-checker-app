.DEFAULT_GOAL := help
PY ?= python
export PYTHONPATH := src
export PYTHONIOENCODING := utf-8

.PHONY: help dev api web web-install web-check test eval eval-strict eval-baseline seed lint typecheck fmt check fetch-dicts normalize-data validate-gold screenshot e2e samples samples-check clean

help:  ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-16s\033[0m %s\n", $$1, $$2}'

dev:  ## Install the package and dev tooling, editable
	$(PY) -m pip install -e ".[dev,api,hunspell]"

web-install:  ## Install frontend dependencies
	cd frontend && npm install

api:  ## Run the FastAPI backend on :8000
	$(PY) -m uvicorn bhashasetu.api.app:app --reload --port 8000

web:  ## Run the Next.js UI on :3000 (needs `make api` in another shell)
	cd frontend && npm run dev

web-check:  ## Typecheck the frontend
	cd frontend && npx tsc --noEmit

screenshot:  ## Capture page screenshots (needs `make api` + `make web` running)
	cd frontend && npm run screenshot

e2e:  ## Drive the real editor against the real API (needs `make api` + `make web`)
	cd frontend && npm run e2e

test:  ## Unit + integration tests
	$(PY) -m pytest -q

eval:  ## Evaluation harness. Gold-set size warns rather than blocks.
	$(PY) -m bhashasetu.cli eval

eval-strict:  ## Evaluation harness with the spec §8 gold-set gate enforced.
	$(PY) -m bhashasetu.cli eval --strict

eval-baseline:  ## Commit the current numbers as the regression baseline
	$(PY) -m bhashasetu.cli eval --write-baseline

seed:  ## Create a local SQLite database with one anonymous device
	$(PY) -c "from bhashasetu.core import storage; from bhashasetu.core.identity import new_device_id; \
	c = storage.connect('bhashasetu.db'); d = new_device_id(); storage.ensure_device(c, d); c.commit(); \
	print('seeded device', d)"

lint:  ## ruff + core language purity (spec §7) + data normalization
	$(PY) -m ruff check src tests scripts
	$(PY) scripts/lint_core_language_purity.py
	$(PY) scripts/lint_data_normalization.py

normalize-data:  ## Rewrite Bengali data files into canonical composed form
	$(PY) scripts/normalize_data_files.py

validate-gold:  ## Structural checks on the gold set
	$(PY) scripts/validate_gold.py

typecheck:  ## mypy strict
	$(PY) -m mypy

fmt:  ## Autofix what is autofixable
	$(PY) -m ruff check --fix src tests scripts
	$(PY) -m ruff format src tests scripts

check: lint typecheck test validate-gold samples-check eval  ## Everything CI runs

fetch-dicts:  ## Download bn_BD + bn_IN Hunspell dictionaries (network required)
	$(PY) scripts/fetch_dictionaries.py

clean:
	rm -rf .pytest_cache .mypy_cache .ruff_cache bhashasetu.db
	find . -name __pycache__ -type d -prune -exec rm -rf {} +

samples:  ## Regenerate the editor's Sample-button corpus from the gold set
	$(PY) scripts/generate_samples.py

samples-check:  ## Fail if frontend/lib/samples.ts has drifted from the gold set
	$(PY) scripts/generate_samples.py --check
