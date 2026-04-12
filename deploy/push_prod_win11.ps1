# ==============================================================================
# ChoreSync — Windows 11 Production Deploy
# ==============================================================================
#
# Equivalent of deploy/push-prod.sh for Windows 11.
#
# Run from the repo root (or anywhere — the script resolves paths itself):
#   .\deploy\push_prod_win11.ps1
#
# What it does:
#   1. Builds the Vue frontend (npm run build)
#   2. Runs Django migrations
#   3. Collects static files
#   4. Restarts Daphne, Celery worker, Celery beat, and nginx
#
# PREREQUISITES:
#   - create_prod_win11.ps1 has been run at least once
#   - Run from an ADMINISTRATOR PowerShell (needed to restart services)
#
# ==============================================================================

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

# ── Colours ───────────────────────────────────────────────────────────────────
function Step { param($m) Write-Host "`n▶  $m" -ForegroundColor Cyan }
function Ok   { param($m) Write-Host "✓  $m" -ForegroundColor Green }
function Die  { param($m) Write-Host "✗  $m" -ForegroundColor Red; exit 1 }

# ── Paths ─────────────────────────────────────────────────────────────────────
$REPO_ROOT   = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$BACKEND     = Join-Path $REPO_ROOT "backend"
$FRONTEND    = Join-Path $REPO_ROOT "frontend"
$SECRETS     = Join-Path $BACKEND "secrets.prod.env"
$CONDA_ENV   = "choreSync"

# ── Resolve conda python ──────────────────────────────────────────────────────
if (-not (Get-Command conda -ErrorAction SilentlyContinue)) {
    Die "conda not found. Make sure Miniconda is on PATH."
}

$CONDA_PYTHON = (conda run -n $CONDA_ENV python -c "import sys; print(sys.executable)" 2>&1).Trim()
if (-not (Test-Path $CONDA_PYTHON)) {
    Die "Could not find Python in conda env '$CONDA_ENV'. Run create_prod_win11.ps1 first."
}

if (-not (Test-Path $SECRETS)) {
    Die "secrets.prod.env not found at $SECRETS. Run create_prod_win11.ps1 first."
}

# Load secrets into the current process so manage.py can use them
foreach ($line in Get-Content $SECRETS) {
    $t = $line.Trim()
    if (-not $t -or $t.StartsWith('#')) { continue }
    $idx = $t.IndexOf('=')
    if ($idx -lt 1) { continue }
    $k = $t.Substring(0, $idx).Trim()
    $v = $t.Substring($idx + 1).Trim().Trim('"').Trim("'")
    [System.Environment]::SetEnvironmentVariable($k, $v, 'Process')
}

# ── Admin check ───────────────────────────────────────────────────────────────
if (-not ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole(
        [Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Die "This script must be run as Administrator (needed to restart Windows services)."
}

# ==============================================================================
# ── 1. Frontend build ─────────────────────────────────────────────────────────
# ==============================================================================
Step "Building Vue frontend"

Set-Location $FRONTEND
npm run build
Ok "Frontend built → frontend/dist/"

# ==============================================================================
# ── 2. Django migrations ──────────────────────────────────────────────────────
# ==============================================================================
Step "Running Django migrations"

Set-Location $BACKEND
& $CONDA_PYTHON manage.py migrate --no-input
Ok "Migrations applied"

# ==============================================================================
# ── 3. Collect static files ───────────────────────────────────────────────────
# ==============================================================================
Step "Collecting static files"

& $CONDA_PYTHON manage.py collectstatic --no-input --clear
Ok "Static files collected"

# ==============================================================================
# ── 4. Restart services ───────────────────────────────────────────────────────
# ==============================================================================
Step "Restarting backend services"

foreach ($svc in @("choresync-daphne", "choresync-celery", "choresync-celery-beat")) {
    Restart-Service $svc
    Ok "Restarted: $svc"
}

# Reload nginx (send it a -s reload signal via its exe so connections aren't dropped)
$nginxExe = "C:\nginx\nginx.exe"
if (Test-Path $nginxExe) {
    & $nginxExe -s reload
    Ok "nginx reloaded"
} else {
    Restart-Service nginx -ErrorAction SilentlyContinue
    Ok "nginx restarted"
}

# ==============================================================================
# ── Done ──────────────────────────────────────────────────────────────────────
# ==============================================================================
Write-Host ""
Write-Host "═══════════════════════════════════════════════════════════" -ForegroundColor Green
Write-Host "  Deploy complete — https://$($env:FRONTEND_APP_URL ?? 'localhost')" -ForegroundColor Green
Write-Host "═══════════════════════════════════════════════════════════" -ForegroundColor Green
Write-Host ""
