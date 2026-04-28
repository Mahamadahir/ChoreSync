#!/usr/bin/env bash
# ── ChoreSync DB reset ────────────────────────────────────────────────────────
# Drops and recreates the Postgres database, then re-runs all migrations.
# Optionally creates a Django superuser at the end.
#
# Usage (from repo root):
#   ./deploy/reset-db.sh                  # production secrets
#   ./deploy/reset-db.sh --dev            # local dev (no secrets file needed)
#   ./deploy/reset-db.sh --dev --no-super # skip superuser prompt
#
# ⚠  THIS DESTROYS ALL DATA.  You will be asked to confirm.
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
CONDA_PYTHON="/home/mahamad/miniconda3/envs/choreSync/bin/python"
BACKEND_DIR="$REPO_ROOT/backend"
SECRETS_FILE="$BACKEND_DIR/secrets.prod.env"

# ── Parse flags ───────────────────────────────────────────────────────────────
DEV_MODE=false
SKIP_SUPER=false
for arg in "$@"; do
  case "$arg" in
    --dev)       DEV_MODE=true ;;
    --no-super)  SKIP_SUPER=true ;;
  esac
done

# ── Colours ───────────────────────────────────────────────────────────────────
RED='\033[0;31m'; YELLOW='\033[1;33m'; GREEN='\033[0;32m'; BLUE='\033[0;34m'; NC='\033[0m'
step()  { echo -e "\n${BLUE}▶ $*${NC}"; }
ok()    { echo -e "${GREEN}✓ $*${NC}"; }
warn()  { echo -e "${YELLOW}⚠ $*${NC}"; }
die()   { echo -e "${RED}✗ $*${NC}"; exit 1; }

# ── Load environment ──────────────────────────────────────────────────────────
if [ "$DEV_MODE" = false ]; then
  [ -f "$SECRETS_FILE" ] || die "Secrets file not found: $SECRETS_FILE (use --dev for local)"
  set -a; source "$SECRETS_FILE"; set +a
  ok "Loaded production secrets"
fi

# Resolve DB connection from DATABASE_URL or defaults
DB_URL="${DATABASE_URL:-postgres://choresync_user:choreSync@localhost:5432/choresync}"
# Parse: postgres://user:pass@host:port/dbname
DB_USER=$(echo "$DB_URL" | sed -E 's|postgres://([^:]+):.*|\1|')
DB_PASS=$(echo "$DB_URL" | sed -E 's|postgres://[^:]+:([^@]+)@.*|\1|')
DB_HOST=$(echo "$DB_URL" | sed -E 's|.*@([^:/]+)[:/].*|\1|')
DB_PORT=$(echo "$DB_URL" | sed -E 's|.*:([0-9]+)/.*|\1|')
DB_NAME=$(echo "$DB_URL" | sed -E 's|.*/([^?]+).*|\1|')

# ── Confirm ───────────────────────────────────────────────────────────────────
echo -e "\n${RED}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${RED}  ⚠  WARNING: This will permanently delete all data in:${NC}"
echo -e "${RED}     Database : ${DB_NAME}${NC}"
echo -e "${RED}     Host     : ${DB_HOST}:${DB_PORT}${NC}"
echo -e "${RED}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}\n"
read -rp "Type 'yes' to confirm: " CONFIRM
[ "$CONFIRM" = "yes" ] || die "Aborted."

# ── Stop services (prod only) ─────────────────────────────────────────────────
if [ "$DEV_MODE" = false ]; then
  step "Stopping backend services..."
  sudo systemctl stop choresync-daphne choresync-celery choresync-celery-beat || true
  ok "Services stopped"
fi

# ── Drop and recreate DB ──────────────────────────────────────────────────────
step "Dropping database '${DB_NAME}'..."
# Use the postgres superuser (via peer auth / sudo) to drop and recreate,
# since choresync_user lacks CREATEDB privilege.
sudo -u postgres psql \
  -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = '${DB_NAME}' AND pid <> pg_backend_pid();" \
  -c "DROP DATABASE IF EXISTS \"${DB_NAME}\";" \
  > /dev/null
ok "Database dropped"

step "Recreating database '${DB_NAME}' owned by '${DB_USER}'..."
sudo -u postgres psql \
  -c "CREATE DATABASE \"${DB_NAME}\" OWNER \"${DB_USER}\";" \
  -c "GRANT ALL PRIVILEGES ON DATABASE \"${DB_NAME}\" TO \"${DB_USER}\";" \
  > /dev/null
ok "Database created and permissions granted"

# ── Run migrations ────────────────────────────────────────────────────────────
step "Running Django migrations..."
cd "$BACKEND_DIR"
step "Installing Python dependencies..."
"$CONDA_PYTHON" -m pip install -q -r requirements.txt
ok "Dependencies installed"

step "Running Django migrations..."
"$CONDA_PYTHON" manage.py migrate --no-input
ok "Migrations applied"

# ── Optional: create superuser ────────────────────────────────────────────────
if [ "$SKIP_SUPER" = false ]; then
  echo ""
  read -rp "Create a Django superuser now? [y/N] " CREATE_SUPER
  if [[ "$CREATE_SUPER" =~ ^[Yy]$ ]]; then
    step "Creating superuser..."
    "$CONDA_PYTHON" manage.py createsuperuser
    ok "Superuser created"
  fi
fi

# ── Restart services (prod only) ──────────────────────────────────────────────
if [ "$DEV_MODE" = false ]; then
  step "Restarting backend services..."
  sudo systemctl start choresync-daphne choresync-celery choresync-celery-beat
  ok "Services restarted"
fi

# ── Seed badges ───────────────────────────────────────────────────────────────
step "Seeding badge definitions..."
"$CONDA_PYTHON" seed_badges.py badges.json
ok "Badges seeded"

# ── Done ──────────────────────────────────────────────────────────────────────
echo -e "\n${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
ok "DB reset complete — ${DB_NAME} is fresh with all migrations applied."
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}\n"
