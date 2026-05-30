#!/usr/bin/env python3
"""
SwarmGlass Setup Wizard -- Interactive TUI for first-time configuration.

Zero dependencies beyond Python 3.12 stdlib. Runs BEFORE pip install.
Prompts for all configurable values grouped by category, validates inputs,
generates .env and overwatch_config.json.

Usage:
    python setup_wizard.py              Full interactive wizard
    python setup_wizard.py --quick      Accept all defaults, only prompt for critical keys
    python setup_wizard.py --generate   Non-interactive: generate .env from defaults only
    python setup_wizard.py --validate   Check existing .env for completeness
"""

import os
import re
import sys
import json
import secrets
import shutil
from pathlib import Path
from typing import Any, Callable

REPO_ROOT = Path(__file__).resolve().parent
ENV_PATH = REPO_ROOT / ".env"
ENV_EXAMPLE_PATH = REPO_ROOT / ".env.example"
OVERWATCH_CONFIG_PATH = REPO_ROOT / "hlf_mcp" / "hlf" / "overwatch_config.json"

# -----------------------------------------------------------------------------
# Category definitions -- every configurable value organized for the wizard
# -----------------------------------------------------------------------------

CATEGORIES = {
    "transport": {
        "title": "Transport & Networking",
        "icon": "[NET]",
        "vars": {
            "SWARMGLASS_TRANSPORT": {
                "default": "stdio",
                "prompt": "Transport mode",
                "help": "stdio = MCP stdio (local agents) | streamable-http = networked MCP | sse = legacy SSE",
                "choices": ["stdio", "streamable-http", "sse"],
            },
            "SWARMGLASS_HOST": {
                "default": "0.0.0.0",
                "prompt": "Bind host (HTTP modes only)",
                "help": "0.0.0.0 = all interfaces | 127.0.0.1 = localhost only",
            },
            "SWARMGLASS_PORT": {
                "default": "8123",
                "prompt": "Bind port (HTTP modes only)",
                "help": "Port for streamable-http or SSE transport",
                "validate": lambda v: 1024 <= int(v) <= 65535 if v.isdigit() else False,
            },
        },
    },
    "auth": {
        "title": "Authentication & Secrets",
        "icon": "[AUTH]",
        "critical": True,
        "vars": {
            "SWARMGLASS_MASTER_KEY": {
                "default": "",
                "prompt": "Master encryption key (CRITICAL)",
                "help": "AES-256-GCM key for secret encryption + Merkle DR signing. Generate with: python -c \"import secrets; print(secrets.token_hex(32))\"",
                "validate": lambda v: len(v) >= 64 or len(v) == 0,
            },
            "SWARMGLASS_SESSION_SECRET": {
                "default": "",
                "prompt": "Session signing secret (CRITICAL for production)",
                "help": "HMAC secret for session tokens. Must be set for production; dev fallback is hardcoded and unsafe.",
                "validate": lambda v: len(v) >= 32 or len(v) == 0,
            },
            "SWARMGLASS_API_TOKEN": {
                "default": "",
                "prompt": "API bearer token (HTTP auth)",
                "help": "If set, HTTP transport requires this Bearer token. Empty = auth disabled (dev only).",
            },
        },
    },
    "models": {
        "title": "Model Providers",
        "icon": "[AI]",
        "vars": {
            "OLLAMA_HOST": {
                "default": "http://localhost:11434",
                "prompt": "Primary Ollama endpoint",
                "help": "URL of your local Ollama instance",
            },
            "OLLAMA_API_KEY": {
                "default": "",
                "prompt": "Ollama Cloud API key",
                "help": "Only needed if using Ollama Cloud (ollama.ai)",
            },
            "OPENROUTER_API_KEY": {
                "default": "",
                "prompt": "OpenRouter API key",
                "help": "For accessing models through OpenRouter",
            },
            "SWARMGLASS_DEFAULT_MODEL": {
                "default": "kimi-k2.6:cloud",
                "prompt": "Default LLM model",
                "help": "Primary model for governance operations",
            },
            "SWARMGLASS_FALLBACK_MODEL": {
                "default": "deepseek-v4-pro:cloud",
                "prompt": "Fallback LLM model",
                "help": "Used when default model is unavailable",
            },
        },
    },
    "storage": {
        "title": "Storage Paths",
        "icon": "[DATA]",
        "vars": {
            "SWARMGLASS_MEMORY_DB": {
                "default": "db/hlf_memory.db",
                "prompt": "RAG memory database path",
                "help": "SQLite database for provenance-tracked knowledge",
            },
            "SWARMGLASS_AUDIT_DB": {
                "default": "db/hlf_audit.db",
                "prompt": "Audit trail database path",
                "help": "SQLite database for Merkle-chained audit events",
            },
            "SWARMGLASS_AUDIT_CHAIN_LOG": {
                "default": "logs/audit.jsonl",
                "prompt": "Audit chain JSONL log path",
                "help": "Append-only JSONL file for audit chain integrity",
            },
            "SWARMGLASS_STATE_DIR": {
                "default": "state",
                "prompt": "State directory",
                "help": "For pending human-in-the-loop approvals",
            },
        },
    },
    "agent": {
        "title": "Agent Configuration",
        "icon": "[GOAL]",
        "vars": {
            "SWARMGLASS_AGENT_TIER": {
                "default": "sovereign",
                "prompt": "Agent capability tier",
                "help": "hearth = restricted | forge = standard | sovereign = full access",
                "choices": ["hearth", "forge", "sovereign"],
            },
            "SWARMGLASS_AGENT_ID": {
                "default": "swarmglass-agent",
                "prompt": "Agent identifier",
                "help": "Unique ID for this agent instance in the swarm",
            },
        },
    },
    "features": {
        "title": "Feature Flags & Tuning",
        "icon": "[CFG]",
        "vars": {
            "SWARMGLASS_HLF_ENABLED": {
                "default": "0",
                "prompt": "Enable experimental DSL features",
                "help": "0 = governance-only (136 tools) | 1 = full DSL (193 tools, loads compiler/VM)",
                "choices": ["0", "1"],
            },
            "SWARMGLASS_STRICT": {
                "default": "1",
                "prompt": "Strict governance mode",
                "help": "1 = block on ethics violations | 0 = warn only",
                "choices": ["0", "1"],
            },
            "CHROMA_HOST": {
                "default": "localhost",
                "prompt": "ChromaDB vector store host",
                "help": "For hybrid RAG search. Leave default if using Docker ChromaDB.",
            },
            "CHROMA_PORT": {
                "default": "8000",
                "prompt": "ChromaDB port",
                "help": "Default ChromaDB Docker port is 8000",
            },
        },
    },
}

# -----------------------------------------------------------------------------
# Terminal helpers
# -----------------------------------------------------------------------------

CSI = "\033["
RESET = f"{CSI}0m"
BOLD = f"{CSI}1m"
DIM = f"{CSI}2m"
GREEN = f"{CSI}32m"
YELLOW = f"{CSI}33m"
BLUE = f"{CSI}34m"
CYAN = f"{CSI}36m"
RED = f"{CSI}91m"
BRIGHT_GREEN = f"{CSI}92m"

DISABLED = False

# Force UTF-8 on Windows to avoid cp1252 encoding errors with box-drawing chars
if sys.stdout.encoding and sys.stdout.encoding.lower() in ("cp1252", "cp1250", "cp1251", "latin-1"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        DISABLED = True
        CSI = RESET = BOLD = DIM = GREEN = YELLOW = BLUE = CYAN = RED = BRIGHT_GREEN = ""

# Disable colors if output is redirected
if not sys.stdout.isatty() and not DISABLED:
    CSI = RESET = BOLD = DIM = GREEN = YELLOW = BLUE = CYAN = RED = BRIGHT_GREEN = ""


def clear_screen():
    os.system("cls" if os.name == "nt" else "clear")


def header(text: str):
    print(f"\n{BOLD}{CYAN}{'=' * 70}{RESET}")
    print(f"{BOLD}{CYAN}  {text}{RESET}")
    print(f"{BOLD}{CYAN}{'=' * 70}{RESET}\n")


def section(text: str, icon: str = ""):
    print(f"\n{BOLD}{icon}  {text}{RESET}")
    print(f"{DIM}{'-' * 50}{RESET}")


def success(text: str):
    print(f"  {GREEN}[OK]{RESET} {text}")


def warn(text: str):
    print(f"  {YELLOW}[!]{RESET} {text}")


def error(text: str):
    print(f"  {RED}[FAIL]{RESET} {text}")


def info(text: str):
    print(f"  {BLUE}[*]{RESET} {text}")


def info(text: str):
    print(f"  {BLUE}[*]{RESET} {DIM}{text}{RESET}")


def prompt_input(prompt_text: str, default: str = "", help_text: str = "", choices: list[str] | None = None) -> str:
    """Prompt user for input with default and optional choices."""
    if choices:
        choice_str = f" [{', '.join(choices)}]"
    else:
        choice_str = ""

    default_display = f" {DIM}[{default}]{RESET}" if default else ""
    print(f"\n{BOLD}  {prompt_text}{choice_str}{default_display}{RESET}")
    if help_text:
        print(f"  {DIM}{help_text}{RESET}")

    while True:
        try:
            value = input(f"  {BLUE}>{RESET} ").strip()
        except (EOFError, KeyboardInterrupt):
            print(f"\n  {YELLOW}Using default: {default}{RESET}")
            return default

        if not value:
            value = default
            if value:
                print(f"  {DIM}Using default: {value}{RESET}")
            return value

        if choices and value not in choices:
            error(f"Must be one of: {', '.join(choices)}")
            continue

        return value


# -----------------------------------------------------------------------------
# Core logic
# -----------------------------------------------------------------------------


def detect_existing_env() -> dict[str, str]:
    """Parse existing .env file if present."""
    existing = {}
    if ENV_PATH.exists():
        for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, val = line.partition("=")
                existing[key.strip()] = val.strip()
    return existing


def detect_ollama() -> bool:
    """Check if Ollama is reachable."""
    try:
        import urllib.request

        urllib.request.urlopen("http://localhost:11434/api/tags", timeout=2)
        return True
    except Exception:
        return False


def detect_docker() -> bool:
    """Check if Docker is available."""
    return shutil.which("docker") is not None


def generate_key(length: int = 64) -> str:
    """Generate a cryptographically secure hex key."""
    return secrets.token_hex(length // 2)


def write_env_file(values: dict[str, str]):
    """Write .env file with category headers."""
    lines = [
        "# =============================================================================",
        "# SwarmGlass Configuration",
        f"# Generated by setup_wizard.py",
        "# =============================================================================",
        "",
    ]

    for cat_key, cat in CATEGORIES.items():
        lines.append(f"# {'-' * 60}")
        lines.append(f"# {cat['icon']} {cat['title']}")
        lines.append(f"# {'-' * 60}")
        for var_key in cat["vars"]:
            val = values.get(var_key, "")
            lines.append(f"{var_key}={val}")
        lines.append("")

    ENV_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_overwatch_config():
    """Write default overwatch_config.json if it doesn't exist."""
    OVERWATCH_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not OVERWATCH_CONFIG_PATH.exists():
        config = {
            "scan_interval_seconds": 30,
            "alert_thresholds": {
                "cpu_percent": 80,
                "memory_percent": 85,
                "disk_percent": 90,
            },
            "health_checks": [
                {"name": "ollama", "type": "http", "endpoint": "http://localhost:11434/api/tags"},
            ],
            "auto_recover": True,
            "max_restarts": 3,
        }
        OVERWATCH_CONFIG_PATH.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")


def run_interactive(existing: dict[str, str]) -> dict[str, str]:
    """Full interactive wizard through all categories."""
    values = {}
    clear_screen()
    header("SwarmGlass Setup Wizard")
    info("This wizard will configure your SwarmGlass governance layer.")
    info("Press Enter to accept defaults. Ctrl+C to skip remaining categories.")
    print()

    has_ollama = detect_ollama()
    has_docker = detect_docker()

    if has_ollama:
        success("Ollama detected -- model server is reachable")
    else:
        warn("Ollama not detected -- set OLLAMA_HOST if using a remote instance")

    if has_docker:
        success("Docker detected -- overwatch container can be built")
    else:
        info("Docker not found -- overwatch daemon runs in-process instead")

    print()

    try:
        for cat_key, cat in CATEGORIES.items():
            section(cat["title"], cat["icon"])
            for var_key, var_def in cat["vars"].items():
                existing_val = existing.get(var_key, "")
                default = existing_val if existing_val else var_def["default"]
                validate_fn = var_def.get("validate")
                choices = var_def.get("choices")

                while True:
                    val = prompt_input(
                        var_def["prompt"],
                        default=default,
                        help_text=var_def["help"],
                        choices=choices,
                    )
                    if validate_fn and val and not validate_fn(val):
                        error("Invalid value. Please try again.")
                        continue
                    break

                values[var_key] = val
    except KeyboardInterrupt:
        print(f"\n\n{YELLOW}Wizard interrupted. Saving what was configured...{RESET}")

    return values


def run_quick(existing: dict[str, str]) -> dict[str, str]:
    """Quick mode: accept all defaults, only prompt for critical keys."""
    values = {}
    clear_screen()
    header("SwarmGlass Quick Setup")
    info("Accepting defaults for most settings. Only prompting for critical keys.")
    print()

    # First, accept all defaults
    for cat in CATEGORIES.values():
        for var_key, var_def in cat["vars"].items():
            existing_val = existing.get(var_key, "")
            values[var_key] = existing_val if existing_val else var_def["default"]

    # Override critical auth keys
    section("Critical Security Keys", "[KEY]")
    info("These MUST be set for production use.")

    master_key = prompt_input(
        "Master encryption key",
        default=values.get("SWARMGLASS_MASTER_KEY", ""),
        help_text="Generate now? (y = auto-generate, Enter = skip, type value to set manually)",
    )
    if master_key.lower() == "y":
        master_key = generate_key(64)
        success(f"Generated: {master_key[:16]}...")
    elif not master_key:
        warn("Master key not set -- encryption disabled (dev only)")
    values["SWARMGLASS_MASTER_KEY"] = master_key

    session_secret = prompt_input(
        "Session signing secret",
        default=values.get("SWARMGLASS_SESSION_SECRET", ""),
        help_text="Generate now? (y = auto-generate, Enter = skip, type value to set manually)",
    )
    if session_secret.lower() == "y":
        session_secret = generate_key(64)
        success(f"Generated: {session_secret[:16]}...")
    elif not session_secret:
        warn("Session secret not set -- dev fallback used (NOT production-safe)")
    values["SWARMGLASS_SESSION_SECRET"] = session_secret

    api_token = prompt_input(
        "API bearer token (HTTP auth)",
        default=values.get("SWARMGLASS_API_TOKEN", ""),
        help_text="Generate now? (y = auto-generate, Enter = skip = auth disabled)",
    )
    if api_token.lower() == "y":
        api_token = generate_key(32)
        success(f"Generated: {api_token}")
    values["SWARMGLASS_API_TOKEN"] = api_token

    return values


def run_generate(existing: dict[str, str]) -> dict[str, str]:
    """Non-interactive: generate from defaults only."""
    values = {}
    for cat in CATEGORIES.values():
        for var_key, var_def in cat["vars"].items():
            existing_val = existing.get(var_key, "")
            values[var_key] = existing_val if existing_val else var_def["default"]
    return values


def validate_env(values: dict[str, str]) -> list[str]:
    """Check for missing critical values."""
    issues = []

    if not values.get("SWARMGLASS_MASTER_KEY"):
        issues.append("SWARMGLASS_MASTER_KEY is not set -- encryption and Merkle signing disabled")

    if not values.get("SWARMGLASS_SESSION_SECRET"):
        issues.append("SWARMGLASS_SESSION_SECRET is not set -- using hardcoded dev fallback")

    if values.get("SWARMGLASS_TRANSPORT") in ("streamable-http", "sse"):
        if not values.get("SWARMGLASS_API_TOKEN"):
            issues.append("HTTP transport enabled but SWARMGLASS_API_TOKEN is not set -- auth is disabled")

    if values.get("SWARMGLASS_HLF_ENABLED") == "1":
        issues.append("Experimental DSL mode enabled -- compiler/VM/runtime will be loaded (200MB+)")

    return issues


# -----------------------------------------------------------------------------
# Main
# -----------------------------------------------------------------------------


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "interactive"
    existing = detect_existing_env()

    if mode == "--validate":
        if not ENV_PATH.exists():
            print(f"{RED}No .env file found at {ENV_PATH}{RESET}")
            print("Run: python setup_wizard.py")
            sys.exit(1)
        issues = validate_env(existing)
        if issues:
            print(f"\n{YELLOW}Issues found:{RESET}")
            for issue in issues:
                print(f"  {YELLOW}[WARN]{RESET} {issue}")
            sys.exit(1)
        else:
            print(f"{GREEN}[OK] .env configuration looks good{RESET}")
            sys.exit(0)

    if mode in ("--generate", "generate"):
        values = run_generate(existing)
        print(f"\n{BOLD}Generating .env from defaults...{RESET}")
    elif mode in ("--quick", "quick"):
        values = run_quick(existing)
        print(f"\n{BOLD}Saving configuration...{RESET}")
    else:
        values = run_interactive(existing)
        print(f"\n{BOLD}Saving configuration...{RESET}")

    # Write files
    write_env_file(values)
    success(f".env written ({ENV_PATH})")

    write_overwatch_config()
    success(f"overwatch_config.json written ({OVERWATCH_CONFIG_PATH})")

    # Validate
    issues = validate_env(values)
    if issues:
        print(f"\n{YELLOW}[WARN] Configuration warnings:{RESET}")
        for issue in issues:
            warn(issue)
    else:
        print(f"\n{BRIGHT_GREEN}[OK] Configuration complete -- no issues detected{RESET}")

    # Create directories
    for d in ["db", "data", "logs", "state"]:
        (REPO_ROOT / d).mkdir(exist_ok=True)

    print(f"\n{BOLD}{GREEN}Setup complete! Next steps:{RESET}")
    print(f"  {BLUE}1.{RESET} Run {BOLD}install.bat{RESET} to install dependencies")
    print(f"  {BLUE}2.{RESET} Run {BOLD}run.bat{RESET} to start the SwarmGlass MCP server")
    print(f"  {BLUE}3.{RESET} Run {BOLD}run.bat test{RESET} to verify the installation")
    print(f"  {BLUE}4.{RESET} Run {BOLD}run.bat count{RESET} to see available tools")
    print()


if __name__ == "__main__":
    main()
