#!/usr/bin/env bash
# ── ChoreSync production deploy ───────────────────────────────────────────────
# Usage:  ./deploy/push-prod.sh
# Runs from the repo root.  Rebuilds frontend, collects static, restarts
# backend services, then keeps the Cloudflare tunnel alive in the foreground.
# Press Ctrl-C to stop the tunnel (services keep running).
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
CONDA_PYTHON="/home/mahamad/miniconda3/envs/choreSync/bin/python"
FRONTEND_DIR="$REPO_ROOT/frontend"
BACKEND_DIR="$REPO_ROOT/backend"
SECRETS="$BACKEND_DIR/secrets.prod.env"

# ── Colours ───────────────────────────────────────────────────────────────────
GREEN='\033[0;32m'; BLUE='\033[0;34m'; RED='\033[0;31m'; NC='\033[0m'
step() { echo -e "\n${BLUE}▶ $*${NC}"; }
ok()   { echo -e "${GREEN}✓ $*${NC}"; }
die()  { echo -e "${RED}✗ $*${NC}"; exit 1; }

# ── 1. Frontend build ─────────────────────────────────────────────────────────
step "Building frontend..."
cd "$FRONTEND_DIR"
npm run build
ok "Frontend built → dist/"

# ── 2. Install/sync Python dependencies ──────────────────────────────────────
step "Installing Python dependencies..."
cd "$BACKEND_DIR"
"$CONDA_PYTHON" -m pip install -e ".[dev]" --quiet
ok "Dependencies installed"

# ── 3. Django: migrate + collectstatic ───────────────────────────────────────
step "Running migrations..."
cd "$BACKEND_DIR"
set -a; source "$SECRETS"; set +a
"$CONDA_PYTHON" manage.py migrate --no-input
ok "Migrations applied"

step "Collecting static files..."
"$CONDA_PYTHON" manage.py collectstatic --no-input --clear
ok "Static files collected → staticfiles/"

# ── 4. Restart backend services ───────────────────────────────────────────────
step "Restarting backend services..."
sudo systemctl restart choresync-daphne choresync-celery choresync-celery-beat
sudo systemctl reload nginx
ok "Daphne, Celery, Nginx restarted"

# ── 5. Done ───────────────────────────────────────────────────────────────────
ok "Deploy complete — https://choresync.mahamadahir.com is live"
echo -e "  (Cloudflare tunnel is a background systemd service — already running)"
