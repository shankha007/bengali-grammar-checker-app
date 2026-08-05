# Windows shim for the Makefile.
#
# The spec asks for a single Makefile with make dev / test / eval / seed, and the
# repo has one. This machine has no `make` (and no Docker), so the same targets
# are mirrored here for local development:
#
#     .\make.ps1 test
#     .\make.ps1 eval
#
# Keep the two in sync. If a target only exists in one of them, someone's CI or
# someone's laptop is about to disagree with the other.

param(
    [Parameter(Position = 0)]
    [ValidateSet('help', 'dev', 'test', 'eval', 'eval-strict', 'eval-baseline',
                 'seed', 'lint', 'typecheck', 'fmt', 'check', 'fetch-dicts',
                 'normalize-data', 'validate-gold', 'clean',
                 'api', 'web', 'web-install', 'web-check', 'screenshot', 'e2e', 'samples', 'samples-check')]
    [string]$Target = 'help'
)

$ErrorActionPreference = 'Stop'
$env:PYTHONPATH = 'src'
$env:PYTHONIOENCODING = 'utf-8'
$py = 'python'

function Invoke-Step([string]$Label, [scriptblock]$Body) {
    Write-Host "==> $Label" -ForegroundColor Cyan
    & $Body
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}

switch ($Target) {
    'help' {
        Write-Host "Targets: dev api web web-install web-check screenshot e2e samples samples-check test eval eval-strict eval-baseline seed lint typecheck fmt check fetch-dicts normalize-data validate-gold clean"
    }
    'dev'           { Invoke-Step 'install' { & $py -m pip install -e ".[dev,api,hunspell]" } }
    'api'           { Invoke-Step 'uvicorn :8000' { & $py -m uvicorn bhashasetu.api.app:app --reload --port 8000 } }
    'web'           { Invoke-Step 'next dev :3000' { Push-Location frontend; npm run dev; Pop-Location } }
    'web-install'   { Invoke-Step 'npm install' { Push-Location frontend; npm install; Pop-Location } }
    'web-check'     { Invoke-Step 'tsc --noEmit' { Push-Location frontend; npx tsc --noEmit; Pop-Location } }
    'screenshot'    { Invoke-Step 'screenshots' { Push-Location frontend; npm run screenshot; Pop-Location } }
    'e2e'           { Invoke-Step 'browser e2e' { Push-Location frontend; npm run e2e; Pop-Location } }
    'samples'       { Invoke-Step 'generate samples' { & $py scripts/generate_samples.py } }
    'samples-check' { Invoke-Step 'samples up to date' { & $py scripts/generate_samples.py --check } }
    'test'          { Invoke-Step 'pytest' { & $py -m pytest -q } }
    'eval'          { Invoke-Step 'eval' { & $py -m bhashasetu.cli eval } }
    'eval-strict'   { Invoke-Step 'eval --strict' { & $py -m bhashasetu.cli eval --strict } }
    'eval-baseline' { Invoke-Step 'eval --write-baseline' { & $py -m bhashasetu.cli eval --write-baseline } }
    'seed' {
        Invoke-Step 'seed' {
            & $py -c "from bhashasetu.core import storage; from bhashasetu.core.identity import new_device_id; c = storage.connect('bhashasetu.db'); d = new_device_id(); storage.ensure_device(c, d); c.commit(); print('seeded device', d)"
        }
    }
    'lint' {
        Invoke-Step 'ruff' { & $py -m ruff check src tests scripts }
        Invoke-Step 'core language purity' { & $py scripts/lint_core_language_purity.py }
        Invoke-Step 'data normalization' { & $py scripts/lint_data_normalization.py }
    }
    'normalize-data' { Invoke-Step 'normalize data' { & $py scripts/normalize_data_files.py } }
    'validate-gold'  { Invoke-Step 'validate gold' { & $py scripts/validate_gold.py } }
    'typecheck'  { Invoke-Step 'mypy' { & $py -m mypy } }
    'fmt' {
        Invoke-Step 'ruff --fix' { & $py -m ruff check --fix src tests scripts }
        Invoke-Step 'ruff format' { & $py -m ruff format src tests scripts }
    }
    'check' {
        Invoke-Step 'ruff' { & $py -m ruff check src tests scripts }
        Invoke-Step 'core language purity' { & $py scripts/lint_core_language_purity.py }
        Invoke-Step 'data normalization' { & $py scripts/lint_data_normalization.py }
        Invoke-Step 'mypy' { & $py -m mypy }
        Invoke-Step 'pytest' { & $py -m pytest -q }
        Invoke-Step 'validate gold' { & $py scripts/validate_gold.py }
        Invoke-Step 'samples up to date' { & $py scripts/generate_samples.py --check }
        Invoke-Step 'eval' { & $py -m bhashasetu.cli eval }
    }
    'fetch-dicts' { Invoke-Step 'fetch dictionaries' { & $py scripts/fetch_dictionaries.py } }
    'clean' {
        foreach ($p in '.pytest_cache', '.mypy_cache', '.ruff_cache', 'bhashasetu.db') {
            if (Test-Path $p) { Remove-Item -Recurse -Force $p }
        }
        Get-ChildItem -Recurse -Directory -Filter __pycache__ |
            ForEach-Object { Remove-Item -Recurse -Force $_.FullName }
        Write-Host "cleaned"
    }
}
