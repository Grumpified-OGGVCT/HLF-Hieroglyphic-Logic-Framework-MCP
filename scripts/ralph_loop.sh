#!/usr/bin/env bash
# =============================================================================
# ralph_loop.sh — Generic RALPH cognitive loop harness
# =============================================================================
# RALPH = Receive → Analyze → List → Plan → Handle
#
# Usage:
#   ralph_loop.sh [-i intent] [-a agent_id] [-r role] [-t timeout_s] <command...>
#
#   ralph_loop.sh "summarize the file" -- agent-scribe summarize-file.sh input.txt
#   echo "fix the build" | ralph_loop.sh -a builder-01 -- make build
#
# Each phase logs to stderr with ISO-8601 timestamps.
# Final output on stdout is a JSON trace object.
# =============================================================================

set -euo pipefail

# --- defaults ---------------------------------------------------------------
AGENT_ID="${RALPH_AGENT_ID:-ralph-harness}"
AGENT_ROLE="${RALPH_AGENT_ROLE:-executor}"
TIMEOUT_S="${RALPH_TIMEOUT_S:-120}"
TRACE_DIR="${RALPH_TRACE_DIR:-${TMPDIR:-/tmp}/ralph-traces}"
INTENT=""
PHASE_LOG="${RALPH_PHASE_LOG:-true}"   # set to false to suppress per-phase logs

# --- helpers ----------------------------------------------------------------
_now() { date -u +"%Y-%m-%dT%H:%M:%SZ"; }
_sha() { printf '%s' "$*" | sha256sum | cut -d' ' -f1; }

_phase() {
    local phase="$1"; shift
    local status="${1:-started}"; shift || true
    local detail="${*:-}"
    local ts
    ts="$(_now)"
    if [[ "$PHASE_LOG" == "true" ]]; then
        printf '[ralph] [%s] %-6s %s %s\n' "$ts" "$phase" "$status" "$detail" >&2
    fi
    printf '{"phase":"%s","status":"%s","ts":"%s","detail":"%s"}\n' \
        "$phase" "$status" "$ts" "$detail"
}

_fail() {
    local phase="$1"; shift
    local reason="$*"
    _phase "$phase" failed "$reason" >&2
    printf '{"error":"%s","phase":"%s","reason":"%s"}\n' "ralph_${phase}_failed" "$phase" "$reason" >&2
    exit 2
}

_usage() {
    cat <<'EOF'
Usage: ralph_loop.sh [OPTIONS] [--] <command> [args...]

OPTIONS:
  -i, --intent TEXT     Natural-language intent (or read from stdin)
  -a, --agent ID        Agent identifier (default: ralph-harness)
  -r, --role ROLE       Agent role (default: executor)
  -t, --timeout SEC     Handle-phase timeout in seconds (default: 120)
  -o, --trace-out PATH  Write JSON trace to file instead of stdout
  --no-phase-log        Suppress per-phase stderr logging
  -h, --help            Show this message

ENVIRONMENT:
  RALPH_AGENT_ID        Default agent id
  RALPH_AGENT_ROLE      Default agent role
  RALPH_TIMEOUT_S       Default handle timeout
  RALPH_TRACE_DIR       Trace artifact directory
  RALPH_PHASE_LOG       Set to "false" to suppress phase logs
EOF
    exit 0
}

# --- source-only guard -------------------------------------------------------
# When sourced by ralph_hlf.sh (or other variants), skip arg parsing + main
# loop and only expose helpers. Set RALPH_SOURCE_ONLY=true before sourcing.
if [[ "${RALPH_SOURCE_ONLY:-}" == "true" ]]; then
    return 0 2>/dev/null || true
fi

# --- arg parsing ------------------------------------------------------------
TRACE_OUT=""
while [[ $# -gt 0 ]]; do
    case "$1" in
        -i|--intent)      INTENT="$2"; shift 2 ;;
        -a|--agent)       AGENT_ID="$2"; shift 2 ;;
        -r|--role)        AGENT_ROLE="$2"; shift 2 ;;
        -t|--timeout)     TIMEOUT_S="$2"; shift 2 ;;
        -o|--trace-out)   TRACE_OUT="$2"; shift 2 ;;
        --no-phase-log)   PHASE_LOG="false"; shift ;;
        -h|--help)        _usage ;;
        --)               shift; break ;;
        -*)               echo "ralph: unknown flag: $1" >&2; exit 1 ;;
        *)                break ;;
    esac
done

# Read intent from stdin if not provided as flag and stdin is not a tty
if [[ -z "$INTENT" ]] && [[ ! -t 0 ]]; then
    INTENT=$(cat)
fi

COMMAND=("$@")
if [[ ${#COMMAND[@]} -eq 0 ]]; then
    echo "ralph: no command provided. Use --help for usage." >&2
    exit 1
fi

# --- trace accumulator ------------------------------------------------------
TRACE_EVENTS=()
trace_event() { TRACE_EVENTS+=("$1"); }

# =============================================================================
# PHASE 0 — Receive
# =============================================================================
trace_event "$(_phase RECEIVE started "intent_bytes=${#INTENT} agent=${AGENT_ID} role=${AGENT_ROLE}")"

if [[ -z "$INTENT" ]]; then
    # No intent provided — treat the command itself as the intent signal
    INTENT="${COMMAND[*]}"
fi

INGRESS_NONCE="$(_now)-$(_sha "$INTENT" "$AGENT_ID" "$$")"
INTENT_HASH="$(_sha "$INTENT")"

mkdir -p "$TRACE_DIR"

trace_event "$(_phase RECEIVE complete "nonce=${INGRESS_NONCE} hash=${INTENT_HASH:0:12}")"

# =============================================================================
# PHASE 1 — Analyze
# =============================================================================
trace_event "$(_phase ANALYZE started)"

# Build context from intent + environment
CONTEXT_BLOB="intent=${INTENT}|agent=${AGENT_ID}|role=${AGENT_ROLE}|nonce=${INGRESS_NONCE}|cmd=${COMMAND[*]}"
CONTEXT_HASH="$(_sha "$CONTEXT_BLOB")"

# Detect domain hints from intent (lightweight keyword scan)
DOMAIN_HINT="general"
if echo "$INTENT" | grep -qiE 'build|compile|make|cmake|bazel'; then
    DOMAIN_HINT="build"
elif echo "$INTENT" | grep -qiE 'deploy|release|publish|ship|docker|k8s|helm'; then
    DOMAIN_HINT="deploy"
elif echo "$INTENT" | grep -qiE 'test|verify|check|lint|audit|prove'; then
    DOMAIN_HINT="verify"
elif echo "$INTENT" | grep -qiE 'fix|repair|patch|bug|defect|issue'; then
    DOMAIN_HINT="repair"
elif echo "$INTENT" | grep -qiE 'security|vuln|exploit|cve|threat'; then
    DOMAIN_HINT="security"
fi

ANALYSIS_BLOB="domain_hint=${DOMAIN_HINT}|context_hash=${CONTEXT_HASH:0:16}|intent_len=${#INTENT}"
trace_event "$(_phase ANALYZE complete "$ANALYSIS_BLOB")"

# =============================================================================
# PHASE 2 — List
# =============================================================================
trace_event "$(_phase LIST started)"

# Options represent the approaches available. For the generic harness,
# we surface: the command itself, a dry-run variant, and an advisory note.
# Downstream variants (HLF, GrumpRolled) will populate real tool options.
OPTIONS=()
OPTIONS+=("direct_exec:${COMMAND[*]}")
OPTIONS+=("advisory:echo \"[advisory] intent=${INTENT:0:80}...\" && ${COMMAND[*]}")
OPTIONS+=("dry_run:echo \"[dry-run] would execute: ${COMMAND[*]}\"")

OPTION_COUNT=${#OPTIONS[@]}
OPTIONS_HASH="$(_sha "${OPTIONS[*]}")"

trace_event "$(_phase LIST complete "options=${OPTION_COUNT} hash=${OPTIONS_HASH:0:12}")"

# =============================================================================
# PHASE 3 — Plan
# =============================================================================
trace_event "$(_phase PLAN started)"

# Default: select direct_exec as the plan
SELECTED_INDEX=0
SELECTED_OPTION="${OPTIONS[$SELECTED_INDEX]}"

# If RALPH_DRY_RUN is set, use dry_run plan
if [[ "${RALPH_DRY_RUN:-}" == "true" ]]; then
    SELECTED_INDEX=2
    SELECTED_OPTION="${OPTIONS[$SELECTED_INDEX]}"
fi

# If RALPH_ADVISORY is set, use advisory plan
if [[ "${RALPH_ADVISORY:-}" == "true" ]]; then
    SELECTED_INDEX=1
    SELECTED_OPTION="${OPTIONS[$SELECTED_INDEX]}"
fi

PLAN_BLOB="selected_index=${SELECTED_INDEX}|option=${SELECTED_OPTION}|timeout_s=${TIMEOUT_S}"
PLAN_HASH="$(_sha "$PLAN_BLOB")"

trace_event "$(_phase PLAN complete "index=${SELECTED_INDEX} hash=${PLAN_HASH:0:12}")"

# =============================================================================
# PHASE 4 — Handle
# =============================================================================
trace_event "$(_phase HANDLE started "command=${COMMAND[*]}")"

HANDLE_START_EPOCH=$(date +%s)

# Execute with timeout wrapper
HANDLE_EXIT_CODE=0
HANDLE_OUTPUT=""
HANDLE_TRACE_FILE="${TRACE_DIR}/${AGENT_ID}-${INGRESS_NONCE//:/}.log"

if command -v timeout &>/dev/null; then
    # GNU timeout available (Linux / Git Bash)
    set +e
    HANDLE_OUTPUT=$(timeout "$TIMEOUT_S" "${COMMAND[@]}" 2>"$HANDLE_TRACE_FILE")
    HANDLE_EXIT_CODE=$?
    set -e
    if [[ $HANDLE_EXIT_CODE -eq 124 ]]; then
        _fail HANDLE "timeout after ${TIMEOUT_S}s"
    fi
else
    # No timeout command — run directly with background kill fallback
    set +e
    "${COMMAND[@]}" >"${TRACE_DIR}/handle_stdout.$$" 2>"$HANDLE_TRACE_FILE" &
    HANDLE_PID=$!
    (
        sleep "$TIMEOUT_S"
        kill "$HANDLE_PID" 2>/dev/null && echo "[ralph] killed after ${TIMEOUT_S}s timeout" >> "$HANDLE_TRACE_FILE"
    ) &
    WATCHDOG_PID=$!
    wait "$HANDLE_PID" 2>/dev/null || true
    HANDLE_EXIT_CODE=$?
    kill "$WATCHDOG_PID" 2>/dev/null || true
    set -e
    HANDLE_OUTPUT=$(cat "${TRACE_DIR}/handle_stdout.$$" 2>/dev/null || true)
    rm -f "${TRACE_DIR}/handle_stdout.$$"
fi

HANDLE_END_EPOCH=$(date +%s)
HANDLE_DURATION_S=$((HANDLE_END_EPOCH - HANDLE_START_EPOCH))
HANDLE_OUTPUT_HASH="$(_sha "$HANDLE_OUTPUT")"
HANDLE_OUTPUT_LEN=${#HANDLE_OUTPUT}
HANDLE_STDERR_LEN=$(wc -c < "$HANDLE_TRACE_FILE" 2>/dev/null || echo 0)

if [[ $HANDLE_EXIT_CODE -ne 0 ]]; then
    trace_event "$(_phase HANDLE complete "status=exit_${HANDLE_EXIT_CODE} duration=${HANDLE_DURATION_S}s output_bytes=${HANDLE_OUTPUT_LEN}")"
else
    trace_event "$(_phase HANDLE complete "status=ok duration=${HANDLE_DURATION_S}s output_bytes=${HANDLE_OUTPUT_LEN}")"
fi

# =============================================================================
# Build trace artifact
# =============================================================================
TRACE_END="$(_now)"
TRACE_ID="$(_sha "$INGRESS_NONCE" "${TRACE_EVENTS[*]}")"

read -r -d '' JSON_TRACE <<JSON_BLOCK || true
{
  "ralph_version": "1.0.0",
  "trace_id": "${TRACE_ID:0:16}",
  "agent_id": "$AGENT_ID",
  "agent_role": "$AGENT_ROLE",
  "ingress_nonce": "$INGRESS_NONCE",
  "intent_hash": "$INTENT_HASH",
  "intent_len": ${#INTENT},
  "intent": $(printf '%s' "$INTENT" | python3 -c 'import sys,json; sys.stdout.write(json.dumps(sys.stdin.read()))' 2>/dev/null || printf '"%s"' "$INTENT" | sed 's/"/\\"/g'),
  "phases": {
    "receive": {"status": "ok"},
    "analyze": {
      "domain_hint": "$DOMAIN_HINT",
      "context_hash": "${CONTEXT_HASH:0:16}"
    },
    "list": {
      "option_count": $OPTION_COUNT,
      "selected_index": $SELECTED_INDEX
    },
    "plan": {
      "selected_option": "$(printf '%s' "$SELECTED_OPTION" | sed 's/"/\\"/g')",
      "timeout_s": $TIMEOUT_S
    },
    "handle": {
      "exit_code": $HANDLE_EXIT_CODE,
      "duration_s": $HANDLE_DURATION_S,
      "output_bytes": $HANDLE_OUTPUT_LEN,
      "output_hash": "${HANDLE_OUTPUT_HASH:0:16}",
      "stderr_bytes": $HANDLE_STDERR_LEN,
      "trace_log": "$HANDLE_TRACE_FILE"
    }
  },
  "events": [
    $(IFS=,; echo "${TRACE_EVENTS[*]}")
  ],
  "started": "${INGRESS_NONCE}",
  "completed": "$TRACE_END",
  "wall_s": $HANDLE_DURATION_S
}
JSON_BLOCK

if [[ -n "$TRACE_OUT" ]]; then
    echo "$JSON_TRACE" > "$TRACE_OUT"
    echo "[ralph] trace written to $TRACE_OUT" >&2
fi
echo "$JSON_TRACE"

exit $HANDLE_EXIT_CODE
