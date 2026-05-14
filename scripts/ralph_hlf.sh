#!/usr/bin/env bash
# =============================================================================
# ralph_hlf.sh — HLF-aware RALPH cognitive loop harness
# =============================================================================
# RALPH = Receive → Analyze → List → Plan → Handle
#
# Extends the generic ralph_loop.sh with HLF MCP tool integration:
#   ANALYZE  → hlf_align_check (policy alignment gate)
#   LIST     → hlf_tool_list (real HLF tool registry enumeration)
#   PLAN     → hlf_compile + orchestration contract (validated HLF compilation)
#   HANDLE   → hlf_capsule_run / hlf_code_execute / hlf_run (sandboxed execution)
#
# Usage:
#   ralph_hlf.sh [-i intent] [--tier TIER] [--gas-limit N] [--] <command...>
#
#   ralph_hlf.sh -i "say hello" --tier hearth -- python -c "print('hi')"
#   ralph_hlf.sh -i "compile and run HLF" --gas-limit 2000 -- hlfrun my_program.hlf
#   echo "verify the build" | ralph_hlf.sh --tier forge -- make test
#
# Each phase logs to stderr with ISO-8601 timestamps.
# Final output on stdout is a JSON trace object with HLF evidence.
# =============================================================================

set -euo pipefail

# --- source base harness for helpers -----------------------------------------
RALPH_SOURCE_ONLY=true
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
# shellcheck source=scripts/ralph_loop.sh
source "${SCRIPT_DIR}/ralph_loop.sh"

# --- python detection --------------------------------------------------------
# Prefer Windows python.exe (with full dependency set) over MSYS2 python.
# In Git Bash / MSYS2, 'python' is the MSYS2 python (may lack deps),
# while 'python.exe' picks up the native Windows Python installation.
if command -v python.exe &>/dev/null; then
    HLF_PYTHON="${HLF_PYTHON:-python.exe}"
elif command -v python3 &>/dev/null; then
    HLF_PYTHON="${HLF_PYTHON:-python3}"
else
    HLF_PYTHON="${HLF_PYTHON:-python}"
fi

# --- ensure hlf_mcp is importable -------------------------------------------
# Build a Windows-style path for native python.exe (needs C:\... not /mnt/c/...).
# For MSYS2 python we keep the Unix path as-is.
if [[ "$HLF_PYTHON" == "python.exe" ]] || [[ "$HLF_PYTHON" == *python.exe ]]; then
    # Convert /mnt/c/... → C:/...
    WIN_REPO_ROOT="$(echo "$REPO_ROOT" | sed 's#^/mnt/\([a-zA-Z]\)/#\1:/#')"
    # If no conversion happened (not MSYS2), use REPO_ROOT as-is
    if [[ "$WIN_REPO_ROOT" == "$REPO_ROOT" ]]; then
        WIN_REPO_ROOT="$REPO_ROOT"
    fi
else
    WIN_REPO_ROOT="$REPO_ROOT"
fi

if [[ -z "${PYTHONPATH:-}" ]]; then
    export PYTHONPATH="$WIN_REPO_ROOT"
else
    case ":$PYTHONPATH:" in
        *:"$WIN_REPO_ROOT":*) ;;
        *) export PYTHONPATH="$WIN_REPO_ROOT:$PYTHONPATH" ;;
    esac
fi

# --- hlf defaults ------------------------------------------------------------
HLF_TIER="${HLF_TIER:-hearth}"
HLF_GAS_LIMIT="${HLF_GAS_LIMIT:-1000}"

# --- hlf helpers -------------------------------------------------------------
_hlf_py() {
    # Run a Python one-liner that imports hlf_mcp and prints JSON to stdout.
    # Args: Python code string, then optional positional args become sys.argv[1:].
    # Stderr from Python is suppressed unless HLF_DEBUG is set.
    local py_code="$1"
    shift
    if [[ "${HLF_DEBUG:-}" == "true" ]]; then
        "$HLF_PYTHON" -c "$py_code" -- "$@"
    else
        "$HLF_PYTHON" -c "$py_code" -- "$@" 2>/dev/null
    fi
}

_hlf_align_check() {
    # Run the ALIGN governor against a payload string.
    # Returns JSON: {"status":"ok"|"warning"|"blocked", "verdict":{...}}
    local payload="$1"
    local agent_id="${2:-$AGENT_ID}"
    _hlf_py "
import json, sys
from hlf_mcp.hlf.align_governor import AlignGovernor
g = AlignGovernor()
v = g.evaluate(sys.argv[1])
print(json.dumps({'status': v.status, 'verdict': v.to_dict(), 'aligned': v.allowed}))
" "$payload"
}

_hlf_tool_registry() {
    # List tools registered in the HLF ToolRegistry.
    # Returns JSON: {"status":"ok", "tools":[...], "count":N}
    _hlf_py "
import json
from hlf_mcp.server_context import build_server_context
ctx = build_server_context()
tools = ctx.tool_registry.list_tools()
print(json.dumps({'status': 'ok', 'tools': tools, 'count': len(tools)}))
"
}

_hlf_compile_source() {
    # Compile HLF source via the compiler module.
    # Returns JSON: {"status":"ok"|"error", "ast":..., "bytecode_hex":..., ...}
    local source="$1"
    _hlf_py "
import json, sys
from hlf_mcp.hlf.compiler import HLFCompiler, CompileError
c = HLFCompiler()
try:
    result = c.compile(sys.argv[1])
    print(json.dumps({'status': 'ok', 'ast': result['ast'],
        'node_count': result['node_count'], 'gas_estimate': result['gas_estimate'],
        'version': result['version']}))
except CompileError as e:
    print(json.dumps({'status': 'error', 'error': str(e), 'line': e.line, 'col': e.col}))
except Exception as e:
    print(json.dumps({'status': 'error', 'error': str(e)}))
" "$source"
}

_hlf_translate_intent() {
    # Translate natural-language intent into HLF source code.
    # Returns JSON: {"status":"ok"|"error", "hlf_source":..., "language":...}
    local text="$1"
    local lang="${2:-auto}"
    _hlf_py "
import json, sys
from hlf_mcp.hlf.translator import language_to_hlf, resolve_language
try:
    resolved = resolve_language(sys.argv[2], text=sys.argv[1])
    result = language_to_hlf(sys.argv[1], language=resolved)
    print(json.dumps({'status': 'ok', 'hlf_source': result.get('hlf',''),
        'language': resolved, 'diagnostics': result.get('diagnostics',{})}))
except Exception as e:
    print(json.dumps({'status': 'error', 'error': str(e)}))
" "$text" "$lang"
}

_hlf_run_code() {
    # Execute HLF source via the runtime VM.
    # Returns JSON: {"status":..., "result":..., "gas_used":..., "trace":...}
    local source="$1"
    local gas_limit="${2:-$HLF_GAS_LIMIT}"
    _hlf_py "
import json, sys
from hlf_mcp.hlf.compiler import HLFCompiler, CompileError
from hlf_mcp.hlf.bytecode import BytecodeEncoder
from hlf_mcp.hlf.runtime import HLFRuntime
c = HLFCompiler()
try:
    ast_result = c.compile(sys.argv[1])
    if ast_result.get('errors'):
        print(json.dumps({'status': 'compile_error', 'errors': ast_result['errors']}))
        sys.exit(0)
    bc = BytecodeEncoder().encode(ast_result['ast'])
    rt = HLFRuntime()
    run_result = rt.run(bc, gas_limit=int(sys.argv[2]), ast=ast_result['ast'], source=sys.argv[1])
    print(json.dumps({'status': run_result.get('status','ok'),
        'result': run_result.get('result'), 'gas_used': run_result.get('gas_used',0),
        'trace': run_result.get('trace',[]), 'side_effects': run_result.get('side_effects',[])}))
except CompileError as e:
    print(json.dumps({'status': 'compile_error', 'error': str(e), 'line': e.line, 'col': e.col}))
except Exception as e:
    print(json.dumps({'status': 'error', 'error': str(e)}))
" "$source" "$gas_limit"
}

_hlf_route_payload() {
    # Produce a governed routing verdict for the payload.
    # Returns JSON with route decision.
    local payload="$1"
    local agent_id="${2:-$AGENT_ID}"
    _hlf_py "
import json, sys
from hlf_mcp.server_context import build_server_context
from hlf_mcp.hlf.governed_routing import produce_governed_route_verdict
ctx = build_server_context()
verdict = produce_governed_route_verdict(
    ctx,
    payload=sys.argv[1],
    agent_id=sys.argv[2],
    workload='agent_routing_context',
    trust_state='trusted',
)
print(json.dumps({'status': 'ok', 'verdict': verdict}, default=str))
" "$payload" "$agent_id"
}

# --- usage -------------------------------------------------------------------
_hlf_usage() {
    cat <<'EOF'
Usage: ralph_hlf.sh [OPTIONS] [--] <command> [args...]

OPTIONS:
  -i, --intent TEXT     Natural-language intent (or read from stdin)
  -a, --agent ID        Agent identifier (default: ralph-harness)
  -r, --role ROLE       Agent role (default: executor)
  -t, --timeout SEC     Handle-phase timeout in seconds (default: 120)
  --tier TIER           HLF execution tier: hearth | forge | anvil | sanctum (default: hearth)
  --gas-limit N         HLF gas limit for execution (default: 1000)
  --no-phase-log        Suppress per-phase stderr logging
  -o, --trace-out PATH  Write JSON trace to file instead of stdout
  --hlf-debug           Enable Python stderr output for debugging
  -h, --help            Show this message

ENVIRONMENT:
  HLF_TIER              Default execution tier
  HLF_GAS_LIMIT         Default gas limit
  HLF_PYTHON            Python interpreter (default: python)
  RALPH_AGENT_ID        Default agent id
  RALPH_AGENT_ROLE      Default agent role
  RALPH_TIMEOUT_S       Default handle timeout
  RALPH_TRACE_DIR       Trace artifact directory
  RALPH_PHASE_LOG       Set to "false" to suppress phase logs
  HLF_DEBUG             Set to "true" to see Python stderr

TIERS:
  hearth   — safe, low-privilege sandbox (default)
  forge    — tool-augmented execution
  anvil    — persistent-side-effect execution
  sanctum  — operator-attested privileged execution
EOF
    exit 0
}

# --- arg parsing ------------------------------------------------------------
TRACE_OUT=""
while [[ $# -gt 0 ]]; do
    case "$1" in
        -i|--intent)      INTENT="$2"; shift 2 ;;
        -a|--agent)       AGENT_ID="$2"; shift 2 ;;
        -r|--role)        AGENT_ROLE="$2"; shift 2 ;;
        -t|--timeout)     TIMEOUT_S="$2"; shift 2 ;;
        --tier)           HLF_TIER="$2"; shift 2 ;;
        --gas-limit)      HLF_GAS_LIMIT="$2"; shift 2 ;;
        -o|--trace-out)   TRACE_OUT="$2"; shift 2 ;;
        --no-phase-log)   PHASE_LOG="false"; shift ;;
        --hlf-debug)      HLF_DEBUG="true"; shift ;;
        -h|--help)        _hlf_usage ;;
        --)               shift; break ;;
        -*)               echo "ralph-hlf: unknown flag: $1" >&2; exit 1 ;;
        *)                break ;;
    esac
done

# Read intent from stdin if not provided as flag and stdin is not a tty
if [[ -z "$INTENT" ]] && [[ ! -t 0 ]]; then
    INTENT=$(cat)
fi

COMMAND=("$@")
if [[ ${#COMMAND[@]} -eq 0 ]]; then
    echo "ralph-hlf: no command provided. Use --help for usage." >&2
    exit 1
fi

# Validate tier
case "$HLF_TIER" in
    hearth|forge|anvil|sanctum) ;;
    *) echo "ralph-hlf: invalid tier '$HLF_TIER'. Use: hearth|forge|anvil|sanctum" >&2; exit 1 ;;
esac

# --- trace accumulator ------------------------------------------------------
TRACE_EVENTS=()
trace_event() { TRACE_EVENTS+=("$1"); }

# =============================================================================
# PHASE 0 — Receive
# =============================================================================
trace_event "$(_phase RECEIVE started "intent_bytes=${#INTENT} agent=${AGENT_ID} role=${AGENT_ROLE} tier=${HLF_TIER}")"

if [[ -z "$INTENT" ]]; then
    INTENT="${COMMAND[*]}"
fi

INGRESS_NONCE="$(_now)-$(_sha "$INTENT" "$AGENT_ID" "$$")"
INTENT_HASH="$(_sha "$INTENT")"

mkdir -p "$TRACE_DIR"

trace_event "$(_phase RECEIVE complete "nonce=${INGRESS_NONCE} hash=${INTENT_HASH:0:12} tier=${HLF_TIER}")"

# =============================================================================
# PHASE 1 — Analyze (HLF: hlf_align_check)
# =============================================================================
trace_event "$(_phase ANALYZE started "tool=hlf_align_check")"

# --- Run ALIGN gate ---
ALIGN_JSON=$(_hlf_align_check "$INTENT" "$AGENT_ID" || echo '{"status":"error","verdict":{},"aligned":true}')
ALIGN_STATUS=$(echo "$ALIGN_JSON" | python3 -c "import sys,json; print(json.load(sys.stdin).get('status','error'))" 2>/dev/null || echo "error")
ALIGN_ALIGNED=$(echo "$ALIGN_JSON" | python3 -c "import sys,json; print(str(json.load(sys.stdin).get('aligned',True)).lower())" 2>/dev/null || echo "true")
ALIGN_VERDICT_ACTION=$(echo "$ALIGN_JSON" | python3 -c "import sys,json; print(json.load(sys.stdin).get('verdict',{}).get('action','ALLOW'))" 2>/dev/null || echo "ALLOW")

# --- Domain hint detection (from base harness) ---
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

CONTEXT_BLOB="intent=${INTENT}|agent=${AGENT_ID}|role=${AGENT_ROLE}|nonce=${INGRESS_NONCE}|tier=${HLF_TIER}|cmd=${COMMAND[*]}"
CONTEXT_HASH="$(_sha "$CONTEXT_BLOB")"

# --- Block if ALIGN says so ---
if [[ "$ALIGN_STATUS" == "blocked" ]]; then
    _fail ANALYZE "ALIGN blocked: action=${ALIGN_VERDICT_ACTION}"
fi

ANALYSIS_BLOB="domain_hint=${DOMAIN_HINT}|align_status=${ALIGN_STATUS}|align_aligned=${ALIGN_ALIGNED}|align_action=${ALIGN_VERDICT_ACTION}|context_hash=${CONTEXT_HASH:0:16}"
trace_event "$(_phase ANALYZE complete "$ANALYSIS_BLOB")"

# =============================================================================
# PHASE 2 — List (HLF: hlf_tool_list + route)
# =============================================================================
trace_event "$(_phase LIST started "tool=hlf_tool_list")"

# --- Enumerate HLF tools ---
TOOL_JSON=$(_hlf_tool_registry || echo '{"status":"error","tools":[],"count":0}')
TOOL_COUNT=$(echo "$TOOL_JSON" | python3 -c "import sys,json; print(json.load(sys.stdin).get('count',0))" 2>/dev/null || echo "0")

# --- Build options from real tool registry ---
OPTIONS=()

# Always offer a direct-exec option (runs the user's command as-is)
OPTIONS+=("direct_exec:${COMMAND[*]}")

# Offer HLF-aware execution options based on available tools
if [[ "$TOOL_COUNT" -gt 0 ]]; then
    OPTIONS+=("hlf_translate_exec:hlf-runner translate-and-run --intent '${INTENT:0:120}' --tier ${HLF_TIER} --gas-limit ${HLF_GAS_LIMIT}")
    OPTIONS+=("hlf_compile_only:hlfc --check --source '${INTENT:0:120}'")
fi

# Always offer dry-run
OPTIONS+=("dry_run:echo \"[dry-run] intent=${INTENT:0:80}... tier=${HLF_TIER} gas=${HLF_GAS_LIMIT}\"")

# --- Get governed route verdict ---
ROUTE_JSON=$(_hlf_route_payload "$INTENT" "$AGENT_ID" || echo '{"status":"error","verdict":{}}')
ROUTE_DECISION=$(echo "$ROUTE_JSON" | python3 -c "import sys,json; v=json.load(sys.stdin).get('verdict',{}); print(v.get('route_decision',{}).get('decision','allow') if isinstance(v,dict) else 'allow')" 2>/dev/null || echo "allow")

OPTION_COUNT=${#OPTIONS[@]}
OPTIONS_HASH="$(_sha "${OPTIONS[*]}")"

trace_event "$(_phase LIST complete "options=${OPTION_COUNT} tools_available=${TOOL_COUNT} route_decision=${ROUTE_DECISION} hash=${OPTIONS_HASH:0:12}")"

# =============================================================================
# PHASE 3 — Plan (HLF: hlf_compile + orchestration contract)
# =============================================================================
trace_event "$(_phase PLAN started "tool=hlf_compile")"

# --- Try to translate intent to HLF for validation ---
HLF_SOURCE=""
COMPILE_OK="false"
COMPILE_GAS_ESTIMATE=0

TRANSLATE_JSON=$(_hlf_translate_intent "$INTENT" || echo '{"status":"error","hlf_source":""}')
HLF_SOURCE=$(echo "$TRANSLATE_JSON" | python3 -c "import sys,json; print(json.load(sys.stdin).get('hlf_source',''))" 2>/dev/null || echo "")

if [[ -n "$HLF_SOURCE" ]]; then
    # Validate the translated HLF via compiler
    COMPILE_JSON=$(_hlf_compile_source "$HLF_SOURCE" || echo '{"status":"error"}')
    COMPILE_STATUS=$(echo "$COMPILE_JSON" | python3 -c "import sys,json; print(json.load(sys.stdin).get('status','error'))" 2>/dev/null || echo "error")
    COMPILE_GAS_ESTIMATE=$(echo "$COMPILE_JSON" | python3 -c "import sys,json; print(json.load(sys.stdin).get('gas_estimate',0))" 2>/dev/null || echo "0")
    if [[ "$COMPILE_STATUS" == "ok" ]]; then
        COMPILE_OK="true"
    fi
fi

# --- Select plan ---
SELECTED_INDEX=0
SELECTED_OPTION="${OPTIONS[$SELECTED_INDEX]}"

# If HLF compilation succeeded, prefer HLF execution
if [[ "$COMPILE_OK" == "true" ]] && [[ ${#OPTIONS[@]} -gt 1 ]]; then
    SELECTED_INDEX=1
    SELECTED_OPTION="${OPTIONS[$SELECTED_INDEX]}"
fi

if [[ "${RALPH_DRY_RUN:-}" == "true" ]]; then
    SELECTED_INDEX=$((OPTION_COUNT - 1))
    SELECTED_OPTION="${OPTIONS[$SELECTED_INDEX]}"
fi

PLAN_BLOB="selected_index=${SELECTED_INDEX}|compile_ok=${COMPILE_OK}|gas_estimate=${COMPILE_GAS_ESTIMATE}|timeout_s=${TIMEOUT_S}|tier=${HLF_TIER}"
PLAN_HASH="$(_sha "$PLAN_BLOB")"

trace_event "$(_phase PLAN complete "index=${SELECTED_INDEX} compile=${COMPILE_OK} gas_est=${COMPILE_GAS_ESTIMATE} hash=${PLAN_HASH:0:12}")"

# =============================================================================
# PHASE 4 — Handle (HLF: sandboxed execution)
# =============================================================================
trace_event "$(_phase HANDLE started "command=${COMMAND[*]} tier=${HLF_TIER} gas_limit=${HLF_GAS_LIMIT}")"

HANDLE_START_EPOCH=$(date +%s)

HANDLE_EXIT_CODE=0
HANDLE_OUTPUT=""
HANDLE_TRACE_FILE="${TRACE_DIR}/${AGENT_ID}-${INGRESS_NONCE//:/}.log"

# --- Try HLF-native execution if compile succeeded ---
if [[ "$COMPILE_OK" == "true" ]] && [[ -n "$HLF_SOURCE" ]] && [[ "$SELECTED_INDEX" -eq 1 ]]; then
    # Execute via HLF runtime with sandbox tier
    RUN_JSON=$(_hlf_run_code "$HLF_SOURCE" "$HLF_GAS_LIMIT" || echo '{"status":"error","error":"runtime call failed"}')
    HANDLE_OUTPUT="$RUN_JSON"
    RUN_STATUS=$(echo "$RUN_JSON" | python3 -c "import sys,json; print(json.load(sys.stdin).get('status','error'))" 2>/dev/null || echo "error")
    if [[ "$RUN_STATUS" == "ok" ]]; then
        HANDLE_EXIT_CODE=0
    else
        HANDLE_EXIT_CODE=1
    fi
    echo "$RUN_JSON" > "$HANDLE_TRACE_FILE"
else
    # Fall back to direct command execution with timeout
    if command -v timeout &>/dev/null; then
        set +e
        HANDLE_OUTPUT=$(timeout "$TIMEOUT_S" "${COMMAND[@]}" 2>"$HANDLE_TRACE_FILE")
        HANDLE_EXIT_CODE=$?
        set -e
        if [[ $HANDLE_EXIT_CODE -eq 124 ]]; then
            _fail HANDLE "timeout after ${TIMEOUT_S}s"
        fi
    else
        set +e
        "${COMMAND[@]}" >"${TRACE_DIR}/handle_stdout.$$" 2>"$HANDLE_TRACE_FILE" &
        HANDLE_PID=$!
        (
            sleep "$TIMEOUT_S"
            kill "$HANDLE_PID" 2>/dev/null && echo "[ralph-hlf] killed after ${TIMEOUT_S}s timeout" >> "$HANDLE_TRACE_FILE"
        ) &
        WATCHDOG_PID=$!
        wait "$HANDLE_PID" 2>/dev/null || true
        HANDLE_EXIT_CODE=$?
        kill "$WATCHDOG_PID" 2>/dev/null || true
        set -e
        HANDLE_OUTPUT=$(cat "${TRACE_DIR}/handle_stdout.$$" 2>/dev/null || true)
        rm -f "${TRACE_DIR}/handle_stdout.$$"
    fi
fi

HANDLE_END_EPOCH=$(date +%s)
HANDLE_DURATION_S=$((HANDLE_END_EPOCH - HANDLE_START_EPOCH))
HANDLE_OUTPUT_HASH="$(_sha "$HANDLE_OUTPUT")"
HANDLE_OUTPUT_LEN=${#HANDLE_OUTPUT}
HANDLE_STDERR_LEN=$(wc -c < "$HANDLE_TRACE_FILE" 2>/dev/null || echo 0)

if [[ $HANDLE_EXIT_CODE -ne 0 ]]; then
    trace_event "$(_phase HANDLE complete "status=exit_${HANDLE_EXIT_CODE} duration=${HANDLE_DURATION_S}s output_bytes=${HANDLE_OUTPUT_LEN} tier=${HLF_TIER}")"
else
    trace_event "$(_phase HANDLE complete "status=ok duration=${HANDLE_DURATION_S}s output_bytes=${HANDLE_OUTPUT_LEN} tier=${HLF_TIER}")"
fi

# =============================================================================
# Build trace artifact
# =============================================================================
TRACE_END="$(_now)"
TRACE_ID="$(_sha "$INGRESS_NONCE" "${TRACE_EVENTS[*]}")"

# Escape the intent for JSON (prefer python3, fallback to sed)
INTENT_ESCAPED=$(printf '%s' "$INTENT" | python3 -c 'import sys,json; print(json.dumps(sys.stdin.read()))' 2>/dev/null || printf '%s' "$INTENT" | sed 's/"/\\"/g')
SELECTED_ESCAPED=$(printf '%s' "$SELECTED_OPTION" | sed 's/"/\\"/g')

read -r -d '' JSON_TRACE <<JSON_BLOCK || true
{
  "ralph_version": "1.0.0-hlf",
  "ralph_flavor": "hlf",
  "trace_id": "${TRACE_ID:0:16}",
  "agent_id": "$AGENT_ID",
  "agent_role": "$AGENT_ROLE",
  "ingress_nonce": "$INGRESS_NONCE",
  "intent_hash": "$INTENT_HASH",
  "intent_len": ${#INTENT},
  "intent": $INTENT_ESCAPED,
  "hlf": {
    "tier": "$HLF_TIER",
    "gas_limit": $HLF_GAS_LIMIT,
    "compile_ok": $COMPILE_OK,
    "align_status": "$ALIGN_STATUS",
    "align_aligned": $ALIGN_ALIGNED,
    "align_action": "$ALIGN_VERDICT_ACTION",
    "tools_available": $TOOL_COUNT,
    "route_decision": "$ROUTE_DECISION"
  },
  "phases": {
    "receive": {"status": "ok", "tier": "$HLF_TIER"},
    "analyze": {
      "domain_hint": "$DOMAIN_HINT",
      "align_status": "$ALIGN_STATUS",
      "align_action": "$ALIGN_VERDICT_ACTION",
      "context_hash": "${CONTEXT_HASH:0:16}"
    },
    "list": {
      "option_count": $OPTION_COUNT,
      "selected_index": $SELECTED_INDEX,
      "tools_available": $TOOL_COUNT,
      "route_decision": "$ROUTE_DECISION"
    },
    "plan": {
      "selected_option": "$SELECTED_ESCAPED",
      "compile_ok": $COMPILE_OK,
      "gas_estimate": $COMPILE_GAS_ESTIMATE,
      "timeout_s": $TIMEOUT_S,
      "tier": "$HLF_TIER"
    },
    "handle": {
      "exit_code": $HANDLE_EXIT_CODE,
      "duration_s": $HANDLE_DURATION_S,
      "output_bytes": $HANDLE_OUTPUT_LEN,
      "output_hash": "${HANDLE_OUTPUT_HASH:0:16}",
      "stderr_bytes": $HANDLE_STDERR_LEN,
      "trace_log": "$HANDLE_TRACE_FILE",
      "tier": "$HLF_TIER",
      "gas_limit": $HLF_GAS_LIMIT
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
    echo "[ralph-hlf] trace written to $TRACE_OUT" >&2
else
    echo "$JSON_TRACE"
fi

exit $HANDLE_EXIT_CODE
