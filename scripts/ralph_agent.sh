#!/usr/bin/env bash
# =============================================================================
# ralph_agent.sh — GrumpRolled / Jules RALPH Agent Template
# =============================================================================
# RALPH = Receive → Analyze → List → Plan → Handle
#
# This script wraps ralph_loop.sh with agent-persona configuration, handoff
# contract support, and swarm vote/dissent integration for GrumpRolled (the
# HLF mouthpiece / native agent-usable surface) and Jules (dispatch/coordination).
#
# Example usage:
#
#   # Developer persona, dry-run advisory
#   ralph_agent.sh --persona developer --intent "fix the parser bug" -- make fix-parser.sh
#
#   # Auditor persona with handoff delegation
#   ralph_agent.sh --persona auditor --delegate verifier-01 \
#       --handoff-scope "verify build artifacts" -- make audit.sh
#
#   # Executor persona with swarm vote
#   ralph_agent.sh --persona executor --vote approve --intent "deploy to staging" -- make deploy.sh
#
#   # Operator persona with dissent
#   ralph_agent.sh --persona operator --dissent "insufficient test coverage" \
#       --intent "promote to production" -- make promote.sh
#
#   # Planner persona, full trace output
#   ralph_agent.sh --persona planner -i "design the new API layer" -o trace.json -- make plan.sh
#
#   # Pipe intent from stdin
#   echo "audit all config files" | ralph_agent.sh --persona auditor -- make audit.sh
#
# Environment variables (override defaults):
#   RALPH_AGENT_ID           Default agent id (default: ralph-agent)
#   RALPH_PERSONA_ROLE       Default persona role
#   RALPH_TRUST_STATE        Default trust state (trusted|approved|watched|untrusted)
#   RALPH_COGNITIVE_LANE     Default cognitive lane policy
#   RALPH_HLF_MCP_TOOL       Path/command to invoke HLF MCP tools (default: hlf-mcp)
# =============================================================================

set -euo pipefail

# =============================================================================
# Defaults
# =============================================================================
AGENT_ID="${RALPH_AGENT_ID:-ralph-agent}"
PERSONA_ROLE="${RALPH_PERSONA_ROLE:-executor}"
TRUST_STATE="${RALPH_TRUST_STATE:-watched}"
COGNITIVE_LANE_POLICY="${RALPH_COGNITIVE_LANE:-balanced}"
HLF_MCP_TOOL="${RALPH_HLF_MCP_TOOL:-hlf-mcp}"
RALPH_LOOP_SCRIPT="${RALPH_LOOP_SCRIPT:-$(dirname "$0")/ralph_loop.sh}"

# Handoff contract fields
DELEGATE=""
HANDOFF_SCOPE=""
HANDOFF_LIFECYCLE_PHASE="active"

# Swarm fields
VOTE=""
DISSENT=""
SWARM_ID=""

# Trace
TRACE_OUT=""
INTENT=""
VERBOSE="${RALPH_VERBOSE:-false}"
DRY_RUN="${RALPH_DRY_RUN:-false}"

# =============================================================================
# Persona profiles
# =============================================================================
# Each profile sets: persona_role, trust_state, cognitive_lane_policy,
# default lifecycle_phase, and a description.
declare -A PERSONAS

PERSONAS[operator]="role:operator trust:trusted lane:conservative phase:review desc:Human-operable oversight surface; governs promotion, approval, and audit review workflows."
PERSONAS[auditor]="role:auditor trust:approved lane:strict phase:verify desc:Compliance and verification agent; checks invariants, proofs, and attestation chains."
PERSONAS[developer]="role:developer trust:approved lane:balanced phase:build desc:Implementation and integration agent; writes, tests, and patches code artifacts."
PERSONAS[verifier]="role:verifier trust:approved lane:strict phase:verify desc:Formal verification agent; proves or refutes spec gates, gas bounds, and type invariants."
PERSONAS[planner]="role:planner trust:approved lane:balanced phase:plan desc:Strategy and decomposition agent; produces task DAGs and orchestration contracts."
PERSONAS[executor]="role:executor trust:watched lane:aggressive phase:execute desc:Execution agent; runs bounded commands within gas and timeout ceilings."

_load_persona() {
    local name="$1"
    local entry="${PERSONAS[$name]:-}"
    if [[ -z "$entry" ]]; then
        echo "ralph-agent: unknown persona '${name}'. Valid: ${!PERSONAS[*]}" >&2
        exit 1
    fi
    for pair in $entry; do
        local k="${pair%%:*}"
        local v="${pair#*:}"
        case "$k" in
            role)   PERSONA_ROLE="$v" ;;
            trust)  TRUST_STATE="$v" ;;
            lane)   COGNITIVE_LANE_POLICY="$v" ;;
            phase)  HANDOFF_LIFECYCLE_PHASE="$v" ;;
        esac
    done
}

# =============================================================================
# Helpers
# =============================================================================
_now() { date -u +"%Y-%m-%dT%H:%M:%SZ"; }
_sha() { printf '%s' "$*" | sha256sum 2>/dev/null | cut -d' ' -f1 || printf '%s' "$*" | shasum -a 256 2>/dev/null | cut -d' ' -f1; }

_log() {
    local level="$1"; shift
    printf '[ralph-agent] [%s] %-5s %s\n' "$(_now)" "$level" "$*" >&2
}

_usage() {
    cat <<'EOF'
Usage: ralph_agent.sh [OPTIONS] [--] <command> [args...]

  GrumpRolled / Jules RALPH Agent Template.
  Wraps ralph_loop.sh with persona, handoff, and swarm layers.

AGENT IDENTITY:
  --persona NAME          Load a persona profile. Valid profiles:
                            operator    Human-operable oversight surface
                            auditor     Compliance and verification agent
                            developer   Implementation and integration agent
                            verifier    Formal verification agent
                            planner     Strategy and decomposition agent
                            executor    Execution agent (default)
  --agent-id ID           Override agent identifier (default: ralph-agent)
  --trust-state STATE     Governance trust posture:
                            trusted | approved | watched | untrusted
  --cognitive-lane LANE   Cognitive lane policy:
                            conservative | balanced | aggressive | strict

HANDOFF CONTRACTS:
  --delegate AGENT_ID     Delegate to the named agent (handoff contract)
  --handoff-scope TEXT    Scope description for the handoff contract
  --lifecycle-phase PHASE Lifecycle phase: plan | build | verify | execute | review

SWARM INTEGRATION:
  --vote ACTION           Cast a swarm vote: approve | reject | abstain
  --swarm-id ID           Swarm identifier for vote/dissent binding
  --dissent TEXT          File a dissent with the given reason text

RALPH LOOP (passed through to ralph_loop.sh):
  -i, --intent TEXT       Natural-language intent (or read from stdin)
  -t, --timeout SEC       Handle-phase timeout in seconds (default: 120)
  -o, --trace-out PATH    Write JSON trace to file
  --no-phase-log          Suppress per-phase stderr logging

OTHER:
  --verbose               Enable verbose logging
  --dry-run               Plan only; do not execute the handle phase
  --hlf-tool PATH         Path to HLF MCP CLI tool (default: hlf-mcp)
  -h, --help              Show this message

ENVIRONMENT:
  RALPH_AGENT_ID          Default agent id
  RALPH_PERSONA_ROLE      Default persona role
  RALPH_TRUST_STATE       Default trust state
  RALPH_COGNITIVE_LANE    Default cognitive lane policy
  RALPH_HLF_MCP_TOOL      Path to HLF MCP CLI tool
  RALPH_LOOP_SCRIPT       Path to ralph_loop.sh (default: sibling in scripts/)
  RALPH_VERBOSE           Set to "true" for verbose logging
  RALPH_DRY_RUN           Set to "true" for dry-run mode
EOF
    exit 0
}

# =============================================================================
# Record a handoff contract event via HLF MCP (best-effort)
# =============================================================================
_record_handoff() {
    local delegator="$1"
    local delegate="$2"
    local scope="$3"
    local phase="$4"

    _log INFO "recording handoff: ${delegator} → ${delegate} scope='${scope}' phase=${phase}"

    if [[ "$DRY_RUN" == "true" ]]; then
        _log DRYRUN "would record handoff contract (skipped)"
        echo "{\"handoff\":{\"status\":\"dry_run\",\"delegator\":\"${delegator}\",\"delegate\":\"${delegate}\",\"scope\":\"${scope}\",\"phase\":\"${phase}\"}}"
        return 0
    fi

    # Best-effort: try HLF MCP tool, fall back to local JSON artifact
    local handoff_json
    handoff_json=$(printf '{"delegator":"%s","delegate":"%s","scope":"%s","lifecycle_phase":"%s","event_type":"delegation","claim_lane":"current-true","source_agent_kind":"ralph-agent","epoch":"%s"}' \
        "$delegator" "$delegate" "$scope" "$phase" "$(_now)")

    if command -v "$HLF_MCP_TOOL" &>/dev/null; then
        "$HLF_MCP_TOOL" hlf_record_handoff_event \
            --delegator "$delegator" \
            --delegate "$delegate" \
            --scope "$scope" \
            --lifecycle_phase "$phase" \
            --event_type delegation \
            --claim_lane current-true \
            --source_agent_kind ralph-agent \
            --persist 2>/dev/null || {
            _log WARN "HLF MCP handoff record failed; writing local artifact"
            echo "$handoff_json"
        }
    else
        _log WARN "HLF MCP tool not found; writing local artifact"
        echo "$handoff_json"
    fi
}

# =============================================================================
# Process a swarm vote via HLF MCP (best-effort)
# =============================================================================
_process_vote() {
    local vote="$1"
    local swarm_id="$2"
    local reason="${3:-}"

    _log INFO "swarm vote: ${vote} swarm=${swarm_id} reason='${reason}'"

    if [[ "$DRY_RUN" == "true" ]]; then
        _log DRYRUN "would cast vote '${vote}' (skipped)"
        echo "{\"vote\":{\"status\":\"dry_run\",\"action\":\"${vote}\",\"swarm_id\":\"${swarm_id}\",\"reason\":\"${reason}\"}}"
        return 0
    fi

    local vote_json
    vote_json=$(printf '{"vote":"%s","swarm_id":"%s","reason":"%s","agent_id":"%s","ts":"%s"}' \
        "$vote" "$swarm_id" "$reason" "$AGENT_ID" "$(_now)")

    if command -v "$HLF_MCP_TOOL" &>/dev/null; then
        "$HLF_MCP_TOOL" hlf_swarm_mechanics \
            --quorum simple \
            --persist 2>/dev/null || {
            _log WARN "HLF MCP swarm vote failed; writing local artifact"
            echo "$vote_json"
        }
    else
        echo "$vote_json"
    fi
}

# =============================================================================
# Process dissent via HLF MCP (best-effort)
# =============================================================================
_process_dissent() {
    local text="$1"
    local swarm_id="$2"

    _log INFO "swarm dissent: '${text}' swarm=${swarm_id}"

    if [[ "$DRY_RUN" == "true" ]]; then
        _log DRYRUN "would file dissent (skipped)"
        echo "{\"dissent\":{\"status\":\"dry_run\",\"text\":\"${text}\",\"swarm_id\":\"${swarm_id}\"}}"
        return 0
    fi

    local dissent_json
    dissent_json=$(printf '{"dissent":"%s","swarm_id":"%s","agent_id":"%s","ts":"%s"}' \
        "$text" "$swarm_id" "$AGENT_ID" "$(_now)")

    if command -v "$HLF_MCP_TOOL" &>/dev/null; then
        "$HLF_MCP_TOOL" hlf_swarm_mechanics \
            --dissent "$text" \
            --persist 2>/dev/null || {
            _log WARN "HLF MCP dissent record failed; writing local artifact"
            echo "$dissent_json"
        }
    else
        echo "$dissent_json"
    fi
}

# =============================================================================
# Build persona metadata block (JSON)
# =============================================================================
_build_persona_meta() {
    cat <<META
{
  "persona": {
    "role": "$PERSONA_ROLE",
    "trust_state": "$TRUST_STATE",
    "cognitive_lane_policy": "$COGNITIVE_LANE_POLICY",
    "lifecycle_phase": "$HANDOFF_LIFECYCLE_PHASE",
    "agent_id": "$AGENT_ID",
    "template_version": "1.0.0",
    "surface": "GrumpRolled/Jules RALPH agent"
  }
}
META
}

# =============================================================================
# Build the agent trace artifact
# =============================================================================
_build_agent_trace() {
    local ralph_trace_file="$1"

    local handoff_block="null"
    local vote_block="null"
    local dissent_block="null"

    if [[ -n "$DELEGATE" ]]; then
        handoff_block=$(_record_handoff "$AGENT_ID" "$DELEGATE" "$HANDOFF_SCOPE" "$HANDOFF_LIFECYCLE_PHASE")
    fi

    if [[ -n "$VOTE" ]]; then
        vote_block=$(_process_vote "$VOTE" "$SWARM_ID" "")
    fi

    if [[ -n "$DISSENT" ]]; then
        dissent_block=$(_process_dissent "$DISSENT" "$SWARM_ID")
    fi

    local merge_script="$(dirname "$0")/ralph_merge_trace.py"

    if [[ -f "$merge_script" ]]; then
        python3 "$merge_script" \
            "$ralph_trace_file" \
            "$PERSONA_ROLE" \
            "$TRUST_STATE" \
            "$COGNITIVE_LANE_POLICY" \
            "$HANDOFF_LIFECYCLE_PHASE" \
            "$AGENT_ID" \
            "$handoff_block" \
            "$vote_block" \
            "$dissent_block" || {
            _log WARN "python3 merge failed; producing raw trace with persona note"
            _build_persona_meta
            cat "$ralph_trace_file"
        }
    else
        _log WARN "merge script not found at ${merge_script}; producing raw trace"
        _build_persona_meta
        cat "$ralph_trace_file"
    fi
}

# =============================================================================
# Argument parsing
# =============================================================================
PASSTHROUGH_ARGS=()

while [[ $# -gt 0 ]]; do
    case "$1" in
        --persona)
            _load_persona "$2"
            shift 2
            ;;
        --agent-id)
            AGENT_ID="$2"
            shift 2
            ;;
        --trust-state)
            case "$2" in
                trusted|approved|watched|untrusted) TRUST_STATE="$2" ;;
                *) echo "ralph-agent: invalid trust-state '$2'. Valid: trusted|approved|watched|untrusted" >&2; exit 1 ;;
            esac
            shift 2
            ;;
        --cognitive-lane)
            case "$2" in
                conservative|balanced|aggressive|strict) COGNITIVE_LANE_POLICY="$2" ;;
                *) echo "ralph-agent: invalid cognitive-lane '$2'. Valid: conservative|balanced|aggressive|strict" >&2; exit 1 ;;
            esac
            shift 2
            ;;
        --delegate)
            DELEGATE="$2"
            shift 2
            ;;
        --handoff-scope)
            HANDOFF_SCOPE="$2"
            shift 2
            ;;
        --lifecycle-phase)
            HANDOFF_LIFECYCLE_PHASE="$2"
            shift 2
            ;;
        --vote)
            case "$2" in
                approve|reject|abstain) VOTE="$2" ;;
                *) echo "ralph-agent: invalid vote '$2'. Valid: approve|reject|abstain" >&2; exit 1 ;;
            esac
            shift 2
            ;;
        --swarm-id)
            SWARM_ID="$2"
            shift 2
            ;;
        --dissent)
            DISSENT="$2"
            shift 2
            ;;
        --hlf-tool)
            HLF_MCP_TOOL="$2"
            shift 2
            ;;
        --verbose)
            VERBOSE="true"
            shift
            ;;
        --dry-run)
            DRY_RUN="true"
            RALPH_DRY_RUN="true"
            export RALPH_DRY_RUN
            shift
            ;;
        -i|--intent)
            INTENT="$2"
            PASSTHROUGH_ARGS+=("$1" "$2")
            shift 2
            ;;
        -t|--timeout|--no-phase-log)
            PASSTHROUGH_ARGS+=("$1")
            [[ "$1" != "--no-phase-log" ]] && { PASSTHROUGH_ARGS+=("$2"); shift; }
            shift
            ;;
        -o|--trace-out)
            TRACE_OUT="$2"
            shift 2
            ;;
        -h|--help)
            _usage
            ;;
        --)
            shift
            break
            ;;
        -*)
            echo "ralph-agent: unknown flag: $1" >&2
            exit 1
            ;;
        *)
            break
            ;;
    esac
done

# Remaining args are the command
COMMAND=("$@")

# =============================================================================
# Validation
# =============================================================================
if [[ ${#COMMAND[@]} -eq 0 ]]; then
    echo "ralph-agent: no command provided. Use --help for usage." >&2
    exit 1
fi

if [[ -n "$DELEGATE" ]] && [[ -z "$HANDOFF_SCOPE" ]]; then
    _log WARN "--delegate set but --handoff-scope is empty; using command as scope"
    HANDOFF_SCOPE="${COMMAND[*]}"
fi

if [[ -n "$DISSENT" ]] && [[ -z "$SWARM_ID" ]]; then
    _log WARN "--dissent set but --swarm-id is empty; dissent will be unbound"
fi

if [[ -n "$VOTE" ]] && [[ -z "$SWARM_ID" ]]; then
    _log WARN "--vote set but --swarm-id is empty; vote will be unbound"
fi

# =============================================================================
# Log startup
# =============================================================================
_log INFO "agent starting: id=${AGENT_ID} persona=${PERSONA_ROLE} trust=${TRUST_STATE} lane=${COGNITIVE_LANE_POLICY}"
[[ "$DRY_RUN" == "true" ]] && _log INFO "DRY RUN mode enabled"
[[ -n "$DELEGATE" ]] && _log INFO "handoff: ${AGENT_ID} → ${DELEGATE} scope='${HANDOFF_SCOPE}'"
[[ -n "$VOTE" ]] && _log INFO "swarm vote: ${VOTE} swarm=${SWARM_ID}"
[[ -n "$DISSENT" ]] && _log INFO "swarm dissent: '${DISSENT}' swarm=${SWARM_ID}"

# =============================================================================
# Check that ralph_loop.sh exists
# =============================================================================
if [[ ! -f "$RALPH_LOOP_SCRIPT" ]]; then
    echo "ralph-agent: ralph_loop.sh not found at ${RALPH_LOOP_SCRIPT}" >&2
    echo "  Set RALPH_LOOP_SCRIPT env var to the correct path." >&2
    exit 1
fi

# =============================================================================
# Execute RALPH loop
# =============================================================================
# Export persona context as environment variables for ralph_loop.sh
export RALPH_AGENT_ID="$AGENT_ID"
export RALPH_AGENT_ROLE="$PERSONA_ROLE"

if [[ "$VERBOSE" == "true" ]]; then
    _log INFO "invoking ralph_loop.sh with ${#PASSTHROUGH_ARGS[@]} passthrough args"
    _log INFO "command: ${COMMAND[*]}"
fi

TRACE_DIR="${RALPH_TRACE_DIR:-${TMPDIR:-/tmp}/ralph-traces}"
mkdir -p "$TRACE_DIR"

# Run ralph_loop.sh and capture its JSON trace to a temp file
RALPH_TRACE_FILE="${TRACE_DIR}/ralph_trace_$$.json"
bash "$RALPH_LOOP_SCRIPT" \
    "${PASSTHROUGH_ARGS[@]}" \
    -- \
    "${COMMAND[@]}" > "$RALPH_TRACE_FILE" 2>&2
RALPH_EXIT_CODE=$?

# =============================================================================
# Build agent trace artifact
# =============================================================================
AGENT_TRACE=$(_build_agent_trace "$RALPH_TRACE_FILE")
rm -f "$RALPH_TRACE_FILE"

if [[ -n "$TRACE_OUT" ]]; then
    echo "$AGENT_TRACE" > "$TRACE_OUT"
    _log INFO "agent trace written to ${TRACE_OUT}"
else
    echo "$AGENT_TRACE"
fi

# =============================================================================
# Summary
# =============================================================================
_log INFO "agent complete: id=${AGENT_ID} exit=${RALPH_EXIT_CODE}"

exit $RALPH_EXIT_CODE
