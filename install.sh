#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$(realpath "$0")")"
PROJECT_ROOT="$(pwd)"

MODE="${1:-}"
PYTHON_CMD=""
OFFLINE=0
CHECK_ONLY=0
SKIP_WIZARD=0
VENV_PYTHON=""

# ── Banner ────────────────────────────────────────────
echo "========================================="
echo "  SwarmGlass - Universal AI Governance"
echo "  install.sh"
echo "========================================="
echo

# ── Help ──────────────────────────────────────────────
print_help() {
    cat <<EOF
SwarmGlass install.sh

Usage:
  ./install.sh                  Install .venv, package, full/dev deps, and verify.
                                 Also launches setup wizard if .env is missing.
  ./install.sh --no-wizard       Skip the setup wizard even if .env is missing.
  ./install.sh --offline         Install without network access (uv cache / wheelhouse).
  ./install.sh --offline-check   Verify a prepared offline install without fetching.
  ./install.sh --check           Verify an existing installation without installing.
  ./install.sh --help            Show this help.

After install:
  python setup_wizard.py              Re-run the configuration wizard
  python setup_wizard.py --quick      Quick setup (defaults + critical keys only)
  python setup_wizard.py --validate   Check your .env for issues
EOF
    exit 0
}

# ── Parse arguments ───────────────────────────────────
case "${MODE}" in
    help|--help|-h)  print_help ;;
    --offline|offline) OFFLINE=1 ;;
    offline-check|--offline-check) OFFLINE=1; CHECK_ONLY=1 ;;
    --check|check) CHECK_ONLY=1 ;;
    --no-wizard) SKIP_WIZARD=1 ;;
esac

# ── Resolve python ────────────────────────────────────
resolve_python() {
    local candidates=("python3.12" "python3" "python")
    for cmd in "${candidates[@]}"; do
        if command -v "$cmd" &>/dev/null; then
            local ver
            ver=$("$cmd" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>/dev/null || echo "0.0")
            local major minor
            IFS='.' read -r major minor <<< "$ver"
            if [[ "$major" -ge 3 && "$minor" -ge 12 ]]; then
                PYTHON_CMD="$cmd"
                VENV_PYTHON="$PROJECT_ROOT/.venv/bin/python"
                echo "[OK] Found Python $ver via '$cmd'."
                return 0
            fi
        fi
    done
    echo "[ERROR] Python 3.12+ is required."
    echo "Install Python 3.12 or newer:"
    echo "  Ubuntu/Debian: sudo apt install python3.12 python3.12-venv"
    echo "  macOS:         brew install python@3.12"
    echo "  Fedora/RHEL:   sudo dnf install python3.12"
    echo "  Arch:          sudo pacman -S python"
    echo "Then run ./install.sh again."
    exit 1
}

resolve_python

# ── Verify (check-only mode) ──────────────────────────
if [[ "$CHECK_ONLY" -eq 1 ]]; then
    if [[ ! -f "$VENV_PYTHON" ]]; then
        echo "[ERROR] .venv is missing. Run ./install.sh first."
        exit 1
    fi
    echo "[VERIFY] Checking package import and MCP surface..."
    "$VENV_PYTHON" -c "
from hlf_mcp import server
print(f'MCP surface: {len(server.REGISTERED_TOOLS)} tools, {len(server.REGISTERED_RESOURCES)} resources, {len(server.REGISTERED_PROMPTS)} prompts')
" || { echo "[ERROR] SwarmGlass MCP import/surface check failed."; exit 1; }

    "$VENV_PYTHON" -c "import hlf_mcp.server; print('module entrypoint: ok')" || exit 1
    "$VENV_PYTHON" -m pytest --version &>/dev/null || { echo "[ERROR] pytest missing."; exit 1; }
    "$VENV_PYTHON" -m ruff --version &>/dev/null || { echo "[ERROR] ruff missing."; exit 1; }

    echo
    echo "========================================="
    echo "  SwarmGlass install verified."
    echo
    echo "  Quick start:"
    echo "    ./run.sh              Start MCP stdio server"
    echo "    ./run.sh http 8123    Start HTTP server"
    echo "    ./run.sh count        Show tool counts"
    echo "    ./run.sh test         Run test suite"
    echo "    ./run.sh help         Show all commands"
    echo
    echo "  Documentation:"
    echo "    docs/SWARMGLASS_HUMAN_OVERVIEW.md"
    echo "    docs/AGENT_USAGE_GUIDE.md"
    echo "========================================="
    exit 0
fi

# ── Pre-flight: setup wizard ──────────────────────────
if [[ "$SKIP_WIZARD" -eq 0 && ! -f ".env" ]]; then
    echo "[SETUP] No .env found. Launching setup wizard..."
    if "$PYTHON_CMD" setup_wizard.py --quick; then
        echo "[OK] .env created with your configuration."
    else
        echo "[WARN] Setup wizard exited with error. Continuing with defaults."
        echo "[WARN] Run 'python setup_wizard.py' later to configure manually."
    fi
fi

# ── Docker detection ──────────────────────────────────
if command -v docker &>/dev/null; then
    echo "[OK] Docker detected - overwatch container support enabled."
else
    echo "[INFO] Docker not found - overwatch will run in-process."
fi

# ── Create venv ───────────────────────────────────────
if [[ ! -f "$VENV_PYTHON" ]]; then
    echo "[INSTALL] Creating .venv with $PYTHON_CMD..."
    "$PYTHON_CMD" -m venv .venv || {
        echo "[ERROR] Failed to create .venv."
        echo "[FIX] Ensure Python 3.12+ is installed."
        echo "  Ubuntu/Debian: sudo apt install python3.12-venv"
        exit 1
    }
else
    echo "[OK] Existing .venv found."
fi

# ── Bootstrap pip ─────────────────────────────────────
echo "[INSTALL] Bootstrapping pip tooling..."
"$VENV_PYTHON" -m ensurepip --upgrade || {
    echo "[ERROR] Failed to bootstrap pip with ensurepip."
    exit 1
}

if [[ "$OFFLINE" -eq 1 ]]; then
    echo "[OFFLINE] Socket-restricted install; skipping pip/uv upgrade."
else
    echo "[INSTALL] Upgrading pip/setuptools/wheel/uv..."
    "$VENV_PYTHON" -m pip install --upgrade pip setuptools wheel uv || {
        echo "[WARN] Could not upgrade pip/setuptools/wheel/uv."
        echo "[WARN] Continuing with locally available tooling."
    }
fi

# ── Install dependencies ──────────────────────────────
echo "[INSTALL] Installing SwarmGlass with all runtime, full, and dev deps..."

install_online() {
    if [[ -f "uv.lock" ]]; then
        if "$VENV_PYTHON" -m uv --version &>/dev/null; then
            echo "[INSTALL] uv.lock found; attempting frozen uv sync..."
            if "$VENV_PYTHON" -m uv sync --frozen --extra full --extra dev; then
                return 0
            fi
            echo "[WARN] Frozen uv sync failed; falling back to requirements.txt."
        elif command -v uv &>/dev/null; then
            echo "[INSTALL] uv.lock found; attempting frozen uv sync..."
            if uv sync --frozen --extra full --extra dev; then
                return 0
            fi
            echo "[WARN] Frozen uv sync failed; falling back to requirements.txt."
        fi
    fi
    if "$VENV_PYTHON" -m uv --version &>/dev/null; then
        "$VENV_PYTHON" -m uv pip install -r requirements.txt
    elif command -v uv &>/dev/null; then
        uv pip install --python "$VENV_PYTHON" -r requirements.txt
    else
        "$VENV_PYTHON" -m pip install -r requirements.txt
    fi
}

install_offline() {
    if [[ -f "uv.lock" ]]; then
        if "$VENV_PYTHON" -m uv --version &>/dev/null; then
            echo "[OFFLINE] Attempting uv sync --frozen --offline..."
            if "$VENV_PYTHON" -m uv sync --frozen --offline --extra full --extra dev; then
                return 0
            fi
        elif command -v uv &>/dev/null; then
            echo "[OFFLINE] Attempting uv sync --frozen --offline..."
            if uv sync --frozen --offline --extra full --extra dev; then
                return 0
            fi
        fi
    fi
    if "$VENV_PYTHON" -m uv --version &>/dev/null; then
        "$VENV_PYTHON" -m uv pip install --offline -r requirements.txt && return 0
    elif command -v uv &>/dev/null; then
        uv pip install --offline --python "$VENV_PYTHON" -r requirements.txt && return 0
    fi
    if [[ -d "wheelhouse" ]]; then
        echo "[OFFLINE] Installing from wheelhouse..."
        "$VENV_PYTHON" -m pip install --no-index --find-links wheelhouse -r requirements.txt && return 0
    fi
    echo "[ERROR] Offline install could not find uv cache or wheelhouse."
    echo "[FIX] Run ./install.sh once online, then retry --offline."
    return 1
}

if [[ "$OFFLINE" -eq 1 ]]; then
    install_offline || exit 1
else
    install_online || exit 1
fi

# ── Create runtime directories ────────────────────────
mkdir -p db data logs state

# ── VS Code bridge (optional) ─────────────────────────
if [[ -f "extensions/hlf-vscode/package.json" ]]; then
    echo "[INSTALL] Checking VS Code bridge dependencies..."
    if ! command -v npm &>/dev/null; then
        if [[ -d "extensions/hlf-vscode/node_modules" ]]; then
            echo "[OK] Existing node_modules found; npm not required."
        else
            echo "[ERROR] npm not found and node_modules missing."
            echo "Install Node.js LTS: https://nodejs.org"
            exit 1
        fi
    else
        pushd "extensions/hlf-vscode" > /dev/null
        if [[ "$OFFLINE" -eq 1 ]]; then
            if [[ -d "node_modules" ]]; then
                echo "[OFFLINE] Existing node_modules found."
            elif [[ -f "package-lock.json" ]]; then
                npm ci --offline || { popd > /dev/null; echo "[ERROR] npm ci --offline failed."; exit 1; }
            else
                popd > /dev/null
                echo "[ERROR] Offline VS Code install requires package-lock.json + npm cache."
                exit 1
            fi
        elif [[ -f "package-lock.json" ]]; then
            npm ci || { popd > /dev/null; echo "[ERROR] npm ci failed."; exit 1; }
        else
            npm install || { popd > /dev/null; echo "[ERROR] npm install failed."; exit 1; }
        fi
        popd > /dev/null
        echo "[OK] VS Code bridge dependencies installed."
    fi
fi

# ── Build overwatch container ─────────────────────────
if command -v docker &>/dev/null && [[ -f "Dockerfile.overwatch" ]]; then
    echo "[DOCKER] Building overwatch container..."
    if docker build -t hlf-overwatch:latest -f Dockerfile.overwatch .; then
        echo "[OK] Overwatch container built: hlf-overwatch:latest"
    else
        echo "[WARN] Overwatch container build failed - daemon falls back to in-process."
    fi
fi

# ── Final banner ──────────────────────────────────────
echo
echo "========================================="
echo "  SwarmGlass install verified."
echo
echo "  Quick start:"
echo "    ./run.sh              Start MCP stdio server"
echo "    ./run.sh http 8123    Start HTTP server"
echo "    ./run.sh count        Show tool counts"
echo "    ./run.sh test         Run test suite"
echo "    ./run.sh help         Show all commands"
echo
echo "  Documentation:"
echo "    docs/SWARMGLASS_HUMAN_OVERVIEW.md"
echo "    docs/AGENT_USAGE_GUIDE.md"
echo "========================================="
