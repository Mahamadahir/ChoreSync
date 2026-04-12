# ==============================================================================
# ChoreSync — Windows 11 Production Environment Setup
# ==============================================================================
#
# BEFORE RUNNING THIS SCRIPT, complete every item on this checklist:
#
#  1. PostgreSQL 16+
#     https://www.postgresql.org/download/windows/
#     - During setup, note the superuser (postgres) password you choose.
#     - Tick "Add PostgreSQL bin to PATH" in the installer, OR add manually:
#       C:\Program Files\PostgreSQL\16\bin
#
#  2. Redis for Windows (Memurai — free community edition)
#     https://www.memurai.com/get-memurai
#     - The installer registers Redis as a Windows service automatically.
#     - Default port 6379, no password needed for local-only use.
#
#  3. Miniconda (Python 3.12)
#     https://docs.conda.io/en/latest/miniconda.html
#     - Choose "Add conda to PATH" or use the Anaconda Prompt.
#
#  4. Node.js 20 LTS
#     https://nodejs.org/en/download
#     - Tick "Add to PATH" during installation.
#
#  5. nginx for Windows
#     https://nginx.org/en/download.html  (Stable version)
#     - Extract to C:\nginx   (the script assumes this path; change NGINX_DIR if needed)
#
#  6. NSSM — Non-Sucking Service Manager (runs Daphne/Celery as Windows services)
#     https://nssm.cc/download
#     - Extract nssm.exe (64-bit) and place it somewhere on your PATH,
#       OR set NSSM_EXE below to the full path.
#
#  7. Cloudflare Tunnel (optional — only needed for public HTTPS)
#     https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/
#     - Install cloudflared, authenticate, and create a tunnel named "choresync".
#     - Update DOMAIN below to match your Cloudflare hostname.
#     - The cloudflared service is NOT created by this script; run:
#         cloudflared service install
#       after updating deploy\cloudflared-config.yml with your tunnel ID.
#
#  8. Run this script from an ADMINISTRATOR PowerShell:
#       Right-click PowerShell → "Run as Administrator"
#       Set-ExecutionPolicy RemoteSigned -Scope Process
#       .\deploy\create_prod_win11.ps1
#
# ==============================================================================

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

# ── Colours ───────────────────────────────────────────────────────────────────
function Step  { param($m) Write-Host "`n▶  $m" -ForegroundColor Cyan }
function Ok    { param($m) Write-Host "✓  $m" -ForegroundColor Green }
function Warn  { param($m) Write-Host "!  $m" -ForegroundColor Yellow }
function Die   { param($m) Write-Host "✗  $m" -ForegroundColor Red; exit 1 }

# ==============================================================================
# ── CONFIGURATION — edit these before running ─────────────────────────────────
# ==============================================================================

# Your public domain (used in Django ALLOWED_HOSTS, CORS, email links, etc.)
$DOMAIN = "choresync.mahamadahir.com"

# PostgreSQL superuser — the account created during PG installation
$PG_SUPERUSER          = "postgres"
$PG_SUPERUSER_PASSWORD = "CHANGE_ME"        # <-- set to your PG install password

# Paths
$REPO_ROOT  = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$BACKEND    = Join-Path $REPO_ROOT "backend"
$FRONTEND   = Join-Path $REPO_ROOT "frontend"
$DEPLOY     = Join-Path $REPO_ROOT "deploy"
$NGINX_DIR  = "C:\nginx"
$NGINX_CONF = Join-Path $NGINX_DIR "conf\choresync.conf"
$NSSM_EXE   = "nssm"          # assumes nssm is on PATH; set full path if not, e.g. "C:\tools\nssm.exe"
$CONDA_ENV  = "choreSync"
$LOG_DIR    = "C:\ProgramData\ChoreSync\logs"

# ==============================================================================
# ── HELPERS ───────────────────────────────────────────────────────────────────
# ==============================================================================

function Require-Command {
    param($cmd, $hint)
    if (-not (Get-Command $cmd -ErrorAction SilentlyContinue)) {
        Die "'$cmd' not found on PATH. $hint"
    }
}

function Random-String {
    param([int]$Length = 32)
    $chars = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'
    -join (1..$Length | ForEach-Object { $chars[(Get-Random -Maximum $chars.Length)] })
}

function Random-UrlSafeString {
    param([int]$Length = 50)
    $chars = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_'
    -join (1..$Length | ForEach-Object { $chars[(Get-Random -Maximum $chars.Length)] })
}

# Read key=value env file into a hashtable
function Read-EnvFile {
    param($Path)
    $h = @{}
    if (-not (Test-Path $Path)) { return $h }
    foreach ($line in Get-Content $Path) {
        $t = $line.Trim()
        if (-not $t -or $t.StartsWith('#')) { continue }
        $idx = $t.IndexOf('=')
        if ($idx -lt 1) { continue }
        $k = $t.Substring(0, $idx).Trim()
        $v = $t.Substring($idx + 1).Trim().Trim('"').Trim("'")
        $h[$k] = $v
    }
    return $h
}

# Write a hashtable back out as key=value, preserving comment blocks at top
function Write-EnvFile {
    param($Path, [hashtable]$Vars, $HeaderComment = "# Auto-generated by create_prod_win11.ps1")
    $lines = @($HeaderComment, "")
    foreach ($k in ($Vars.Keys | Sort-Object)) {
        $v = $Vars[$k]
        # Quote values that contain spaces
        if ($v -match '\s') { $v = "`"$v`"" }
        $lines += "$k=$v"
    }
    Set-Content -Path $Path -Value $lines -Encoding UTF8
}

# ==============================================================================
# ── PRE-FLIGHT CHECKS ─────────────────────────────────────────────────────────
# ==============================================================================
Step "Pre-flight checks"

if (-not ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole(
        [Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Die "This script must be run as Administrator."
}

Require-Command "psql"    "Add PostgreSQL bin directory to PATH."
Require-Command "conda"   "Install Miniconda and add to PATH."
Require-Command "node"    "Install Node.js 20 LTS and add to PATH."
Require-Command "npm"     "npm should come with Node.js."
Require-Command $NSSM_EXE "Download NSSM from https://nssm.cc and add to PATH."

if (-not (Test-Path $NGINX_DIR)) {
    Die "nginx not found at $NGINX_DIR. Extract the nginx Windows zip to C:\nginx."
}

Ok "All prerequisites found"

# ==============================================================================
# ── STEP 1 — Generate random DB credentials ───────────────────────────────────
# ==============================================================================
Step "Generating PostgreSQL app credentials"

$DB_NAME     = "choresync_prod"
$DB_USER     = "choresync_app"
$DB_PASSWORD = Random-String -Length 32

Ok "DB user  : $DB_USER"
Ok "DB name  : $DB_NAME"
Ok "Password : (32-char random — will be written to secrets.prod.env)"

# ==============================================================================
# ── STEP 2 — Generate Django secret keys ──────────────────────────────────────
# ==============================================================================
Step "Generating Django secret keys"

$DJANGO_SECRET_KEY      = Random-UrlSafeString -Length 64
$FIELD_ENCRYPTION_KEY   = [Convert]::ToBase64String(
    (1..32 | ForEach-Object { Get-Random -Maximum 256 }) -as [byte[]]
)

# ==============================================================================
# ── STEP 3 — Create/update secrets.prod.env ───────────────────────────────────
# ==============================================================================
Step "Writing secrets.prod.env"

$secretsPath = Join-Path $BACKEND "secrets.prod.env"

# Preserve any existing OAuth / email secrets so re-runs don't overwrite them
$existing = Read-EnvFile -Path $secretsPath

$secrets = @{
    # Core Django
    SECRET_KEY             = $DJANGO_SECRET_KEY
    DEBUG                  = "False"
    ALLOWED_HOSTS          = "$DOMAIN,localhost,127.0.0.1"
    FIELD_ENCRYPTION_KEY   = $FIELD_ENCRYPTION_KEY

    # Database
    DATABASE_URL           = "postgresql://${DB_USER}:${DB_PASSWORD}@localhost:5432/$DB_NAME"

    # URLs
    FRONTEND_APP_URL                = "https://$DOMAIN"
    FRONTEND_VERIFY_EMAIL_URL       = "https://$DOMAIN/verify-email"
    FRONTEND_RESET_PASSWORD_URL     = "https://$DOMAIN/reset-password"
    CORS_ALLOWED_ORIGINS            = "https://$DOMAIN"
    CSRF_TRUSTED_ORIGINS            = "https://$DOMAIN"
    BACKEND_BASE_URL                = "https://$DOMAIN"
    GOOGLE_OAUTH_REDIRECT_URI       = "https://$DOMAIN/api/calendar/google/callback/"
    OUTLOOK_OAUTH_REDIRECT_URI      = "https://$DOMAIN/api/calendar/outlook/callback/"
    GOOGLE_WEBHOOK_CALLBACK_URL     = "https://$DOMAIN/api/calendar/google/webhook/"
    MOBILE_CALENDAR_REDIRECT_URI    = "choresync://calendar/connected"

    # Redis
    CELERY_BROKER_URL      = "redis://localhost:6379/0"
    CELERY_RESULT_BACKEND  = "redis://localhost:6379/0"

    # AI (Ollama — change if using a remote model)
    OLLAMA_URL             = "http://localhost:11434/api/chat"
    OLLAMA_MODEL           = "phi3:mini"
}

# Carry over OAuth/email secrets from existing file (don't overwrite on re-run)
$carryOver = @(
    'EMAIL_HOST_USER', 'EMAIL_HOST_PASSWORD',
    'GOOGLE_OAUTH_CLIENT_ID', 'GOOGLE_OAUTH_CLIENT_SECRET', 'GOOGLE_MOBILE_CLIENT_IDS',
    'MICROSOFT_CLIENT_ID', 'MICROSOFT_TENANT_ID',
    'MICROSOFT_CLIENT_SECRET', 'MICROSOFT_CLIENT_SECRET_ID', 'OUTLOOK_WEBHOOK_SECRET'
)
foreach ($k in $carryOver) {
    if ($existing.ContainsKey($k) -and $existing[$k]) {
        $secrets[$k] = $existing[$k]
    } else {
        $secrets[$k] = "FILL_IN_$k"
    }
}

Write-EnvFile -Path $secretsPath -Vars $secrets `
    -HeaderComment "# Production secrets — auto-generated by create_prod_win11.ps1`n# Edit OAuth/email values before starting services."

Ok "Written to $secretsPath"

# ==============================================================================
# ── STEP 4 — PostgreSQL: create role + database ───────────────────────────────
# ==============================================================================
Step "Creating PostgreSQL role and database"

$env:PGPASSWORD = $PG_SUPERUSER_PASSWORD

$roleSql = @"
DO `$`$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = '$DB_USER') THEN
        EXECUTE format('CREATE ROLE %I LOGIN PASSWORD %L', '$DB_USER', '$DB_PASSWORD');
    ELSE
        EXECUTE format('ALTER ROLE %I WITH LOGIN PASSWORD %L', '$DB_USER', '$DB_PASSWORD');
    END IF;
END
`$`$;
"@

psql -U $PG_SUPERUSER -h localhost -p 5432 -c $roleSql
psql -U $PG_SUPERUSER -h localhost -p 5432 -c "DROP DATABASE IF EXISTS `"$DB_NAME`";"
psql -U $PG_SUPERUSER -h localhost -p 5432 -c "CREATE DATABASE `"$DB_NAME`" OWNER `"$DB_USER`";"
psql -U $PG_SUPERUSER -h localhost -p 5432 -c "GRANT ALL PRIVILEGES ON DATABASE `"$DB_NAME`" TO `"$DB_USER`";"

$env:PGPASSWORD = ""
Ok "Database '$DB_NAME' created, owned by '$DB_USER'"

# ==============================================================================
# ── STEP 5 — Conda environment + Python packages ──────────────────────────────
# ==============================================================================
Step "Setting up conda environment '$CONDA_ENV'"

$condaExists = (conda env list 2>&1) -match "^\s*$CONDA_ENV\s"
if ($condaExists) {
    Warn "Conda env '$CONDA_ENV' already exists — skipping creation"
} else {
    conda create -n $CONDA_ENV python=3.12 -y
    Ok "Created conda env '$CONDA_ENV'"
}

# Resolve conda python path
$CONDA_PYTHON = (conda run -n $CONDA_ENV python -c "import sys; print(sys.executable)").Trim()
$CONDA_BIN    = Split-Path $CONDA_PYTHON

Ok "Python: $CONDA_PYTHON"

# Install all Python dependencies pinned to the same versions as Linux
$requirementsContent = @"
amqp==5.3.1
asgiref==3.11.1
celery==5.6.2
channels==4.3.2
channels_redis==4.3.0
click==8.3.1
click-didyoumean==0.3.1
click-plugins==1.1.1.2
click-repl==0.3.0
cron-descriptor==1.4.5
cryptography==46.0.5
daphne==4.2.1
Django==5.2.12
django-celery-beat==2.9.0
django-cors-headers==4.9.0
django-environ==0.13.0
django-timezone-field==7.2.1
djangorestframework==3.16.1
djangorestframework_simplejwt==5.5.1
dnspython==2.8.0
email-validator==2.3.0
google-api-core==2.30.0
google-api-python-client==2.192.0
google-auth==2.49.1
google-auth-httplib2==0.3.0
google-auth-oauthlib==1.3.0
googleapis-common-protos==1.73.0
httpx==0.28.1
kombu==5.6.2
oauthlib==3.3.1
pillow==12.1.1
psycopg2-binary==2.9.11
proto-plus==1.27.1
protobuf==6.33.5
PyJWT==2.12.1
python-dateutil==2.9.0.post0
redis==7.3.0
requests==2.32.5
requests-oauthlib==2.0.0
six==1.17.0
sqlparse==0.5.5
Twisted==25.5.0
tzdata==2025.3
tzlocal==5.3.1
ujson==5.12.0
uritemplate==4.2.0
urllib3==2.6.3
vine==5.1.0
whitenoise==6.12.0
"@

$reqFile = Join-Path $DEPLOY "requirements_win11.txt"
Set-Content -Path $reqFile -Value $requirementsContent -Encoding UTF8

& $CONDA_PYTHON -m pip install --upgrade pip
& $CONDA_PYTHON -m pip install -r $reqFile
Ok "Python packages installed"

# ==============================================================================
# ── STEP 6 — Frontend build ───────────────────────────────────────────────────
# ==============================================================================
Step "Building Vue frontend"

Set-Location $FRONTEND
npm ci
npm run build
Ok "Frontend built → frontend/dist/"

# ==============================================================================
# ── STEP 7 — Django migrations + static files ────────────────────────────────
# ==============================================================================
Step "Running Django migrations"

Set-Location $BACKEND

# Load secrets into current process so manage.py can see them
foreach ($pair in (Get-Content $secretsPath)) {
    $t = $pair.Trim()
    if (-not $t -or $t.StartsWith('#')) { continue }
    $idx = $t.IndexOf('=')
    if ($idx -lt 1) { continue }
    $k = $t.Substring(0, $idx).Trim()
    $v = $t.Substring($idx + 1).Trim().Trim('"').Trim("'")
    [System.Environment]::SetEnvironmentVariable($k, $v, 'Process')
}

& $CONDA_PYTHON manage.py migrate --no-input
Ok "Migrations applied"

Step "Collecting static files"
& $CONDA_PYTHON manage.py collectstatic --no-input --clear
Ok "Static files collected"

# ==============================================================================
# ── STEP 8 — nginx configuration ─────────────────────────────────────────────
# ==============================================================================
Step "Configuring nginx"

$repoRootFwd = $REPO_ROOT.Replace('\', '/')

$nginxConf = @"
server {
    listen 80;
    server_name localhost;

    # Frontend SPA
    root $repoRootFwd/frontend/dist;
    index index.html;

    # Backend — API, admin, static
    location ~ ^/(api|admin|static|media)/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host `$host;
        proxy_set_header X-Real-IP `$remote_addr;
        proxy_set_header X-Forwarded-For `$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto https;
        proxy_read_timeout 60s;
    }

    # WebSocket — Django Channels
    location /ws/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade `$http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host `$host;
        proxy_set_header X-Forwarded-Proto https;
        proxy_read_timeout 86400s;
    }

    # SPA fallback
    location / {
        try_files `$uri /index.html;
    }
}
"@

Set-Content -Path $NGINX_CONF -Value $nginxConf -Encoding UTF8

# Include choresync.conf from the main nginx.conf (idempotent)
$mainConf = Join-Path $NGINX_DIR "conf\nginx.conf"
$includeDirective = "    include choresync.conf;"
$mainConfContent = Get-Content $mainConf -Raw
if ($mainConfContent -notmatch [regex]::Escape($includeDirective)) {
    $mainConfContent = $mainConfContent -replace '(http\s*\{)', "`$1`n$includeDirective"
    Set-Content -Path $mainConf -Value $mainConfContent -Encoding UTF8
    Ok "Added include to nginx.conf"
}

# Install nginx as a Windows service via NSSM
$nginxExe = Join-Path $NGINX_DIR "nginx.exe"
if (-not (Get-Service "nginx" -ErrorAction SilentlyContinue)) {
    & $NSSM_EXE install nginx $nginxExe
    & $NSSM_EXE set nginx AppDirectory $NGINX_DIR
    & $NSSM_EXE set nginx Description "nginx reverse proxy for ChoreSync"
    & $NSSM_EXE set nginx Start SERVICE_AUTO_START
    Ok "nginx Windows service created"
} else {
    Warn "nginx service already exists — skipping"
}

# ==============================================================================
# ── STEP 9 — Windows services: Daphne, Celery worker, Celery beat ────────────
# ==============================================================================
Step "Creating Windows services via NSSM"

$daphneExe  = Join-Path $CONDA_BIN "daphne.exe"
$celeryExe  = Join-Path $CONDA_BIN "celery.exe"

New-Item -ItemType Directory -Force -Path $LOG_DIR | Out-Null

function Install-NssmService {
    param($Name, $Exe, $Args, $Description)

    if (Get-Service $Name -ErrorAction SilentlyContinue) {
        Warn "Service '$Name' already exists — removing and recreating"
        & $NSSM_EXE stop $Name 2>$null
        & $NSSM_EXE remove $Name confirm
    }

    & $NSSM_EXE install $Name $Exe $Args
    & $NSSM_EXE set $Name AppDirectory $BACKEND
    & $NSSM_EXE set $Name Description $Description
    & $NSSM_EXE set $Name Start SERVICE_AUTO_START

    # Pipe stdout + stderr to log files
    & $NSSM_EXE set $Name AppStdout (Join-Path $LOG_DIR "$Name.log")
    & $NSSM_EXE set $Name AppStderr (Join-Path $LOG_DIR "$Name-err.log")
    & $NSSM_EXE set $Name AppRotateFiles 1
    & $NSSM_EXE set $Name AppRotateSeconds 86400
    & $NSSM_EXE set $Name AppRotateBytes 5242880   # 5 MB

    # Inject every secret as an environment variable for the service process
    $envString = (Get-Content $secretsPath |
        Where-Object { $_ -match '^\s*[A-Z_]+=.+' -and $_ -notmatch '^\s*#' } |
        ForEach-Object { $_.Trim() }
    ) -join "`n"
    & $NSSM_EXE set $Name AppEnvironmentExtra $envString

    Ok "Service '$Name' installed"
}

Install-NssmService `
    -Name "choresync-daphne" `
    -Exe  $daphneExe `
    -Args "-b 127.0.0.1 -p 8000 chore_sync.asgi:application" `
    -Description "ChoreSync Daphne ASGI server"

Install-NssmService `
    -Name "choresync-celery" `
    -Exe  $celeryExe `
    -Args "-A chore_sync worker -l info --pool=solo" `
    -Description "ChoreSync Celery worker"
# Note: --pool=solo is required on Windows (no fork support)

Install-NssmService `
    -Name "choresync-celery-beat" `
    -Exe  $celeryExe `
    -Args "-A chore_sync beat -l info --scheduler django_celery_beat.schedulers:DatabaseScheduler" `
    -Description "ChoreSync Celery beat scheduler"

# ==============================================================================
# ── STEP 10 — Start all services ─────────────────────────────────────────────
# ==============================================================================
Step "Starting all services"

foreach ($svc in @("nginx", "choresync-daphne", "choresync-celery", "choresync-celery-beat")) {
    Start-Service $svc
    Ok "Started: $svc"
}

# ==============================================================================
# ── DONE ──────────────────────────────────────────────────────────────────────
# ==============================================================================

Write-Host ""
Write-Host "═══════════════════════════════════════════════════════════" -ForegroundColor Green
Write-Host "  ChoreSync production environment ready!" -ForegroundColor Green
Write-Host "═══════════════════════════════════════════════════════════" -ForegroundColor Green
Write-Host ""
Write-Host "  Local URL : http://localhost" -ForegroundColor Cyan
Write-Host "  Public URL: https://$DOMAIN  (requires Cloudflare tunnel)" -ForegroundColor Cyan
Write-Host ""
Write-Host "  DB user   : $DB_USER" -ForegroundColor White
Write-Host "  DB name   : $DB_NAME" -ForegroundColor White
Write-Host "  Secrets   : $secretsPath" -ForegroundColor White
Write-Host "  Logs      : $LOG_DIR" -ForegroundColor White
Write-Host ""
Warn "NEXT STEPS:"
Write-Host "  1. Edit secrets.prod.env and fill in all FILL_IN_* values"
Write-Host "     (Email, Google OAuth, Microsoft OAuth credentials)"
Write-Host "  2. Restart services after editing secrets:"
Write-Host "     Restart-Service choresync-daphne, choresync-celery, choresync-celery-beat"
Write-Host "  3. For public HTTPS, set up Cloudflare tunnel:"
Write-Host "     cloudflared service install"
Write-Host "     (after updating deploy\cloudflared-config.yml with your tunnel ID)"
Write-Host ""
