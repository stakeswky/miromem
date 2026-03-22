#!/bin/bash
# ============================================================
# MiroMem Setup Script
# One-click deployment for the full MiroMem stack
# ============================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
VENDOR_DIR="$PROJECT_DIR/vendor"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

info()  { echo -e "${CYAN}[INFO]${NC}  $*"; }
ok()    { echo -e "${GREEN}[OK]${NC}    $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC}  $*"; }
fail()  { echo -e "${RED}[FAIL]${NC}  $*"; exit 1; }

# ---- 1. Prerequisites ----

info "Checking prerequisites..."

command -v docker >/dev/null 2>&1 || fail "docker is not installed"
ok "docker found"

if docker compose version >/dev/null 2>&1; then
    COMPOSE="docker compose"
elif command -v docker-compose >/dev/null 2>&1; then
    COMPOSE="docker-compose"
else
    fail "docker compose is not installed"
fi
ok "$COMPOSE found"

command -v git >/dev/null 2>&1 || fail "git is not installed"
ok "git found"

# ---- 2. Clone vendor repos ----

info "Setting up vendor dependencies..."
mkdir -p "$VENDOR_DIR"

if [ -d "$VENDOR_DIR/EverMemOS" ]; then
    ok "EverMemOS already cloned"
else
    info "Cloning EverMemOS..."
    git clone --depth 1 https://github.com/EverMind-AI/EverMemOS.git "$VENDOR_DIR/EverMemOS"
    ok "EverMemOS cloned"
fi

if [ -d "$VENDOR_DIR/MiroFish" ]; then
    ok "MiroFish already cloned"
else
    info "Cloning MiroFish..."
    git clone --depth 1 https://github.com/666ghj/MiroFish.git "$VENDOR_DIR/MiroFish"
    ok "MiroFish cloned"
fi

# ---- 3. Environment file ----

ENV_FILE="$PROJECT_DIR/.env"
if [ -f "$ENV_FILE" ]; then
    ok ".env file exists"
else
    info "Creating .env from template..."
    cp "$PROJECT_DIR/.env.template" "$ENV_FILE"
    warn ".env created — please edit it to fill in your API keys:"
    echo ""
    echo "    LLM_API_KEY        — OpenAI-compatible LLM provider key"
    echo "    EMBEDDING_API_KEY  — Embedding model key"
    echo "    RERANKER_API_KEY   — Reranker model key"
    echo ""
    read -rp "Press Enter to continue after editing .env (or Ctrl+C to abort)..."
fi

# ---- 4. Build and start services ----

info "Starting MiroMem stack with $COMPOSE..."
cd "$PROJECT_DIR"
$COMPOSE up -d --build

# ---- 5. Wait for services to be healthy ----

info "Waiting for services to become healthy..."

MAX_WAIT=120
INTERVAL=5
ELAPSED=0

wait_for_url() {
    local name="$1" url="$2"
    while [ $ELAPSED -lt $MAX_WAIT ]; do
        if curl -sf "$url" >/dev/null 2>&1; then
            ok "$name is healthy"
            return 0
        fi
        sleep $INTERVAL
        ELAPSED=$((ELAPSED + INTERVAL))
    done
    warn "$name did not become healthy within ${MAX_WAIT}s"
    return 1
}

wait_for_url "MongoDB"       "http://localhost:27017" || true
ELAPSED=0
wait_for_url "Elasticsearch" "http://localhost:9200"  || true
ELAPSED=0
wait_for_url "Milvus"        "http://localhost:9091/healthz" || true
ELAPSED=0
wait_for_url "EverMemOS"     "http://localhost:1995/health"  || true
ELAPSED=0
wait_for_url "MiroFish"      "http://localhost:5001/api/graph/project/list" || true
ELAPSED=0
wait_for_url "Gateway"       "http://localhost:8000/health"  || true

# ---- 6. Status summary ----

echo ""
echo "============================================================"
echo -e "${GREEN}MiroMem stack is running!${NC}"
echo "============================================================"
echo ""
echo "  Gateway:          http://localhost:8000"
echo "  Gateway Health:   http://localhost:8000/health"
echo "  EverMemOS:        http://localhost:1995"
echo "  MiroFish Backend: http://localhost:5001"
echo "  MiroFish UI:      http://localhost:5173"
echo "  MongoDB:          localhost:27017"
echo "  Milvus:           localhost:19530"
echo "  Elasticsearch:    http://localhost:9200"
echo ""
echo "To stop:  $COMPOSE down"
echo "To logs:  $COMPOSE logs -f"
echo ""
