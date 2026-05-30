#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$(realpath "$0")")"
PROJECT_ROOT="$(pwd)"

MODE="${1:-stdio}"
VENV_PYTHON="$PROJECT_ROOT/.venv/bin/python"

# ── Guard: .venv must exist ───────────────────────────
if [[ ! -f "$VENV_PYTHON" ]]; then
    echo "[ERROR] .venv is missing. Run ./install.sh first." >&2
    exit 1
fi

# ── Pre-flight: .env wizard gate ──────────────────────
if [[ ! -f ".env" ]]; then
    echo "[SETUP] First run detected - no .env found."
    echo "[SETUP] Launching quick setup wizard..."
    if "$VENV_PYTHON" setup_wizard.py --quick; then
        echo "[OK] Configuration complete."
    else
        echo "[WARN] Setup wizard had issues. Run 'python setup_wizard.py' to configure."
    fi
    echo
fi

# ── Print help ────────────────────────────────────────
print_help() {
    cat <<EOF
SwarmGlass run.sh

Usage:
  ./run.sh                       Start MCP stdio transport (default).
  ./run.sh stdio                 Same as default.
  ./run.sh http [port]           Start Streamable HTTP on 127.0.0.1 (default port 8123).
  ./run.sh sse [port]            Start legacy SSE compatibility transport.
  ./run.sh test                  Run pytest suite.
  ./run.sh lint                  Run ruff over hlf_mcp and tests.
  ./run.sh count                 Print live MCP tool/resource/prompt counts.
  ./run.sh setup                 Run the configuration wizard.
  ./run.sh setup --quick         Quick setup (defaults + critical keys only).
  ./run.sh setup --validate      Verify .env configuration.
  ./run.sh overwatch             Start overwatch daemon (Docker or in-process).
  ./run.sh docker-build          Build grumprolled/hlf-mcp-mouthpiece:local.
  ./run.sh docker-up             Build/start the Docker Compose stack.
  ./run.sh docker-down           Stop the Docker Compose stack.
  ./run.sh docker-logs           Show grumprolled-hlf-mcp logs.
  ./run.sh help                  Show this help.
EOF
    exit 0
}

# ── Dispatch ──────────────────────────────────────────
case "${MODE}" in
    stdio|mcp)
        export HLF_TRANSPORT=stdio
        exec "$VENV_PYTHON" -m hlf_mcp.server
        ;;
    http|streamable-http)
        export HLF_TRANSPORT=streamable-http
        export HLF_HOST=127.0.0.1
        export HLF_PORT="${2:-8123}"
        echo "[RUN] Starting SwarmGlass Streamable HTTP on http://${HLF_HOST}:${HLF_PORT}/mcp"
        exec "$VENV_PYTHON" -m hlf_mcp.server
        ;;
    sse|legacy-sse)
        export HLF_TRANSPORT=sse
        export HLF_HOST=127.0.0.1
        export HLF_PORT="${2:-8123}"
        echo "[RUN] Starting legacy SSE transport on http://${HLF_HOST}:${HLF_PORT}"
        exec "$VENV_PYTHON" -m hlf_mcp.server
        ;;
    test)
        exec "$VENV_PYTHON" -m pytest tests -q
        ;;
    lint)
        exec "$VENV_PYTHON" -m ruff check hlf_mcp tests
        ;;
    count)
        exec "$VENV_PYTHON" -c "from hlf_mcp import server; print(len(server.REGISTERED_TOOLS), len(server.REGISTERED_RESOURCES), len(server.REGISTERED_PROMPTS))"
        ;;
    setup|setup-wizard)
        shift 2>/dev/null || true
        exec "$VENV_PYTHON" setup_wizard.py "$@"
        ;;
    overwatch|overwatch-daemon)
        echo "[RUN] Starting overwatch daemon..."
        if [[ -f "Dockerfile.overwatch" ]] && command -v docker &>/dev/null; then
            echo "[DOCKER] Building and starting overwatch container..."
            docker build -t hlf-overwatch:latest -f Dockerfile.overwatch .
            docker run --rm --name hlf-overwatch -d hlf-overwatch:latest
            echo "[OK] Overwatch daemon started in Docker."
            echo "     View logs: docker logs -f hlf-overwatch"
        else
            echo "[INFO] Docker not available, running overwatch in-process..."
            exec "$VENV_PYTHON" -m hlf_mcp.hlf.overwatch_daemon
        fi
        ;;
    docker-build)
        command -v docker &>/dev/null || { echo "[ERROR] Docker not found." >&2; exit 1; }
        docker build -t grumprolled/hlf-mcp-mouthpiece:local .
        ;;
    docker-up)
        command -v docker &>/dev/null || { echo "[ERROR] Docker not found." >&2; exit 1; }
        docker compose up -d --build hlf-mcp-mouthpiece
        ;;
    docker-down)
        command -v docker &>/dev/null || { echo "[ERROR] Docker not found." >&2; exit 1; }
        docker compose down
        ;;
    docker-logs)
        command -v docker &>/dev/null || { echo "[ERROR] Docker not found." >&2; exit 1; }
        docker logs grumprolled-hlf-mcp
        ;;
    help|--help|-h)
        print_help
        ;;
    *)
        echo "[ERROR] Unknown mode: ${MODE}" >&2
        echo "Usage: ./run.sh [stdio|http|sse|test|lint|count|setup|overwatch|docker-build|docker-up|docker-down|docker-logs|help]" >&2
        exit 1
        ;;
esac
