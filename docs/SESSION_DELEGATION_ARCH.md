# HLF VM Session Delegation Architecture

## 1. Problem Statement

### Why Per-Agent Auth Breaks Swarm Usability

The current `HlfVM._dispatch_host()` enforces tier restrictions at every host-function call. When the `SwarmOrchestrator` spawns multiple agents, each agent runs in its own `HlfVM` instance with its own `tier`, `scope`, and `_side_effects`.

This creates three usability failures in swarm mode:

1. **Authentication fatigue**: Every spawned agent must independently authenticate to reach `forge` or `sovereign` tiers. A 5-agent swarm prompts the user 5 times for the same credentials.
2. **Permission drift**: Agents started with `hearth` tier silently fail when they encounter `operators`-tier host functions (e.g., `write_file`, `network_request`). The orchestrator has no way to pre-authorize them.
3. **Audit fragmentation**: Each agent's `_side_effects` list is isolated. There is no traceable link between a parent orchestrator decision and the child agent actions that followed.

Session delegation solves this by allowing a **single authenticated session** to be created once and **inherited by child VMs** via cryptographically signed tokens.

---

## 2. Session Lifecycle

```
create_session(tier="sovereign", effects=["*"], expiry=3600)
        │
        ▼
   ┌─────────────┐
   │  Master VM  │  ←─ session_token stored in vm.session_token
   │  (forge/    │      vm.session_id = ULID
   │   sovereign) │      vm.delegated_effects = ["*"]
   └─────────────┘
        │
        │ delegate_to_child(parent_token, child_tier="hearth",
        │                    child_effects=["write_fs","read_fs"])
        ▼
   ┌─────────────┐
   │  Child VM 1 │  ←─ child_session_token (signed by parent)
   │  (Schema    │      child.session_id = new ULID
   │   Designer) │      child.parent_session_id = master.session_id
   └─────────────┘      child.delegated_effects = ["write_fs","read_fs"]
        │
        │ delegate_to_child(parent_token, child_tier="hearth",
        │                    child_effects=["crypto","write_fs"])
        ▼
   ┌─────────────┐
   │  Child VM 2 │  ←─ child_session_token
   │  (Auth      │
   │   Service)  │
   └─────────────┘
        │
        │ revoke_session(child_session_id)
        ▼
   ┌─────────────┐
   │  REVOKED    │  ←─ token blacklisted; future calls rejected
   └─────────────┘
```

### Phase Detail

| Phase | Actor | Action |
|-------|-------|--------|
| **Create** | Orchestrator or user | Calls `create_session()` with desired tier and effect list. Receives a signed `session_token`. Creates a master `HlfVM` and stores the token in `vm.session_token`. |
| **Delegate** | Master VM / Orchestrator | Calls `delegate_session()` with the parent token and a restricted subset of effects. Receives a child token. Spawns a child `HlfVM` with `parent_session_id` set. |
| **Execute** | Child VM | Child VM calls host functions. `_dispatch_host` validates the child token before checking tier. Token carries the delegated effect list; the host function's required effect must be in that list. |
| **Revoke** | Parent or orchestrator | Calls `revoke_session(session_id)`. The session ID is added to a revocation list. Subsequent `validate_session()` calls return `False`. |
| **Expire** | Time | Tokens embed an `exp` claim. `validate_session()` rejects expired tokens automatically, even if not explicitly revoked. |

---

## 3. Auth Token Format

A lightweight, JWT-inspired signed token (not full JWT — no JOSE dependency).

### Token Structure

```
base64url(header).base64url(payload).base64url(signature)
```

#### Header (JSON)
```json
{
  "alg": "HS256",
  "typ": "HLF-Session-v1"
}
```

#### Payload (JSON)
```json
{
  "sid": "01HV8N...",        // ULID session_id
  "ptier": "sovereign",      // parent tier (original)
  "ctier": "hearth",         // child tier (delegated)
  "eff": ["write_fs", "read_fs", "memory_store"],
  "iat": 1715904000,
  "exp": 1715907600,
  "pid": "01HV8M...",        // parent session_id (null for root)
  "jti": "01HV8N...abc"      // unique token id (prevents replay)
}
```

#### Signature
```
HMAC-SHA256(
  key = HLF_SESSION_SECRET (32-byte env var),
  message = base64url(header) + "." + base64url(payload)
)
```

### Token Size Budget
- Typical payload: ~200–400 bytes
- Base64 overhead: ~33%
- Signature: 32 bytes → 43 bytes base64
- **Total: ~350–600 bytes** — small enough to pass through `scope` dictionaries without bloat.

---

## 4. Child VM Token Validation (No Re-prompting)

When a child `HlfVM` executes `CALL_HOST`, the runtime validates the session **before** applying tier checks.

### Validation Flow in `_dispatch_host`

```python
def _dispatch_host(fn_name, args, scope, side_effects, *, tier="hearth"):
    # ... existing normalization ...
    fn_info = HOST_FUNCTIONS.get(fn_name, {})

    # ── NEW: Session token validation ───────────────────────────────
    session_token = scope.get("_session_token")
    if session_token:
        auth = validate_session(session_token)
        if not auth.valid:
            raise PermissionError(f"Invalid or expired session: {auth.reason}")

        # Override effective tier with the delegated tier from token
        effective_tier = auth.delegated_tier

        # Effect check: the function's declared effects must be
        # a subset of the token's allowed effects
        required_effects = set(fn_info.get("effects", []))
        allowed_effects = set(auth.delegated_effects)
        if required_effects and not required_effects.issubset(allowed_effects):
            raise PermissionError(
                f"Session '{auth.session_id}' lacks effects {required_effects - allowed_effects}"
            )
    else:
        # Fallback to legacy tier-only enforcement
        effective_tier = tier
        if effective_tier == "hearth" and scope.get("_tier"):
            effective_tier = str(scope["_tier"])

    # ── Existing tier enforcement (now operates on effective_tier) ──
    fn_tier = fn_info.get("tier", "all")
    if fn_tier == "operators" and effective_tier not in ("forge", "sovereign"):
        raise PermissionError(...)

    # ... rest of dispatch ...
```

### Key Design Decisions

1. **Token lives in `scope["_session_token"]`**: The VM's `scope` is already threaded through every host call. No new arguments needed.
2. **Delegated tier can be lower than parent tier**: A `sovereign` parent can spawn a `hearth` child. The child cannot escalate.
3. **Effect whitelist, not blacklist**: The token explicitly lists what is **allowed**. Missing effects are denied by default — defense in depth.
4. **No re-prompting**: Validation is purely cryptographic. The child VM never interacts with the user.

---

## 5. Revocation

### Immediate Revocation (Parent → Child)

```python
revoke_session(child_session_id)
```

- Adds `session_id` to an in-memory revocation set (`_REVOKED_SESSIONS`).
- `validate_session()` checks the revocation set before signature verification.
- Thread-safe via `threading.Lock`.

### Cascade Revocation (Not Implemented by Default)

- If a **parent** session is revoked, all its **children** are implicitly invalid because the parent signature chain breaks.
- For explicit cascade: walk the `parent_session_id` links and revoke each child. This is an orchestrator-level policy, not a runtime requirement.

### Auto-Expiry

- Tokens contain `exp` (Unix timestamp).
- `validate_session()` rejects `expired` tokens without consulting the revocation set.
- No background cleanup needed; the revocation set only grows for **early** revocations.

---

## 6. Audit Trail

Every delegated action carries both the **parent** and **child** session IDs.

### Side-Effect Entry Enhancement

Current:
```json
{"type": "file_write", "fn": "write_file", "args": ["/tmp/out.txt"]}
```

With session delegation:
```json
{
  "type": "file_write",
  "fn": "write_file",
  "args": ["/tmp/out.txt"],
  "session": {
    "sid": "01HV8N...",
    "pid": "01HV8M...",
    "delegated_effects": ["write_fs"],
    "tier": "hearth"
  }
}
```

### Audit Log API

```python
# Inside _dispatch_host, after validation:
if auth and auth.valid:
    side_effects.append({
        "type": eff,
        "fn": fn_name,
        "args": [...],
        "session": {
            "sid": auth.session_id,
            "pid": auth.parent_session_id,
            "delegated_effects": list(auth.delegated_effects),
            "tier": auth.delegated_tier,
        }
    })
```

This enables:
- **Forensics**: Trace any file write back to the swarm orchestrator that authorized it.
- **Billing**: Attribute gas consumption to the parent session.
- **Compliance**: Prove that child agents never exceeded their delegated authority.

---

## 7. Scope Extensions for `HlfVM`

The following additions are required to the `HlfVM` class (`hlf_mcp/hlf/runtime.py`):

### New Fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `session_id` | `str` | ULID | Unique identifier for this VM instance. Generated at `__init__`. |
| `session_token` | `str` | `""` | Signed token stored in this VM. Empty string means no session auth. |
| `parent_session_id` | `str \| None` | `None` | If this VM was spawned by another, the parent's `session_id`. |
| `delegated_effects` | `list[str]` | `[]` | Effects this session is authorized for. Checked by `_dispatch_host`. |

### Modified `__init__`

```python
def __init__(self, tier: str = "hearth", max_gas: int = 100,
             *, session_token: str = "", parent_session_id: str | None = None,
             delegated_effects: list[str] | None = None) -> None:
    self.tier = tier
    self.max_gas = max_gas
    self.gas_used = 0
    self.stack: list[Any] = []
    self.scope: dict[str, Any] = {}
    self.immutables: set[str] = set()
    self.trace: list[dict[str, Any]] = []
    self._halted = False
    self._result_code = 0
    self._result_message = "ok"
    self._side_effects: list[dict[str, Any]] = []

    # ── Session delegation ──
    import ulid
    self.session_id = str(ulid.new())
    self.session_token = session_token
    self.parent_session_id = parent_session_id
    self.delegated_effects = list(delegated_effects) if delegated_effects else []

    # Inject token into scope so _dispatch_host sees it
    if session_token:
        self.scope["_session_token"] = session_token
```

### New Method: `spawn_child_vm()`

```python
def spawn_child_vm(self, child_tier: str, child_effects: list[str],
                   max_gas: int = 100) -> HlfVM:
    """Create a child VM with a delegated session token."""
    if not self.session_token:
        raise RuntimeError("Cannot spawn child: parent VM has no session token")

    child_token = delegate_session(
        parent_token=self.session_token,
        child_tier=child_tier,
        child_effects=child_effects,
    )

    child = HlfVM(
        tier=child_tier,
        max_gas=max_gas,
        session_token=child_token,
        parent_session_id=self.session_id,
        delegated_effects=child_effects,
    )
    return child
```

### Modified `_dispatch_host`

- Accept `session_token` from `scope.get("_session_token")`.
- Call `validate_session()` if token present.
- Use delegated tier and effects instead of raw `tier` argument.
- Append session metadata to each side-effect entry.

---

## 8. Swarm Integration

### Orchestrator Creates Master Session

```python
class SwarmOrchestrator:
    def start_swarm(self, task, translator_fn):
        # 1. Create one master session with full permissions
        master_token = create_session(
            tier="sovereign",
            effects=["*"],           # wildcard = all effects
            expiry_seconds=3600,
        )
        master_vm = HlfVM(tier="sovereign", session_token=master_token)

        # 2. Spawn child agents with limited, role-specific effects
        agent1_vm = master_vm.spawn_child_vm(
            child_tier="hearth",
            child_effects=["write_fs", "read_fs", "memory_store"],
        )  # SchemaDesigner: can write files, cannot touch network

        agent5_vm = master_vm.spawn_child_vm(
            child_tier="hearth",
            child_effects=["crypto", "write_fs"],
        )  # AuthService: can crypto + write, cannot spawn agents

        # 3. Execute phases using child VMs
        # ... each child runs independently, no re-auth needed ...
```

### Permission Matrix Example

| Agent | Role | Tier | Delegated Effects | Blocked Effects |
|-------|------|------|-------------------|-----------------|
| Master | Orchestrator | `sovereign` | `["*"]` | — |
| Agent 1 | SchemaDesigner | `hearth` | `write_fs`, `read_fs`, `memory_store` | `network`, `crypto`, `spawn_agent` |
| Agent 2 | CodeWriter | `hearth` | `write_fs`, `read_fs`, `execute_shell` | `network`, `crypto` |
| Agent 3 | Validator | `hearth` | `read_fs`, `hash_sha256` | `write_fs`, `network` |
| Agent 4 | NetworkProbe | `forge` | `network`, `read_fs` | `write_fs`, `crypto`, `spawn_agent` |
| Agent 5 | AuthService | `hearth` | `crypto`, `write_fs` | `network`, `spawn_agent` |

### Why This Works

- **Single sign-on**: User authenticates the master session once.
- **Principle of least privilege**: Each agent gets only the effects it needs.
- **Fail-safe**: An agent that tries to exceed its delegated effects gets a `PermissionError` immediately, with full session IDs in the error for debugging.
- **Composable**: Child VMs can spawn grandchildren, but each delegation further restricts the effect set (no escalation).

---

## 9. Security Considerations

| Threat | Mitigation |
|--------|------------|
| Token theft / replay | Short expiry (default 1h); `jti` uniqueness check optional; tokens live in VM scope, not user-accessible memory. |
| Child escalates tier | `delegate_session` enforces `child_tier <= parent_tier` (hearth < forge < sovereign). |
| Child widens effects | `delegate_session` intersects requested child effects with parent allowed effects. |
| Revocation race | Revocation set checked **before** signature validation, so revoked tokens fail fast. |
| Secret exposure | `HLF_SESSION_SECRET` is a 32-byte environment variable, never logged, rotated via normal secret management. |
| Token size bloat | Compact JSON + base64url; no certificates or key chains. |

---

## 10. Migration Path

1. **Phase 1 (backward-compatible)**: Add `session_auth.py`, new `HlfVM` fields, and modified `_dispatch_host`. Legacy VMs without `session_token` continue to work via the fallback tier path.
2. **Phase 2 (opt-in swarm)**: `SwarmOrchestrator` gains `use_session_delegation=True` flag. When enabled, it creates a master session and spawns children.
3. **Phase 3 (default-on)**: After burn-in, session delegation becomes the default for all swarm executions. Standalone VMs still work without tokens.

---

## 11. Files Added / Modified

| File | Action | Description |
|------|--------|-------------|
| `hlf_mcp/hlf/session_auth.py` | **New** | Core session auth: create, validate, delegate, revoke. |
| `hlf_mcp/hlf/runtime.py` | **Modify** | Add session fields to `HlfVM.__init__`, add `spawn_child_vm()`, modify `_dispatch_host`. |
| `hlf_mcp/hlf/swarm_orchestrator.py` | **Modify** | Use `create_session()` + `spawn_child_vm()` in `run_3_agent_stack()` and `run_5_agent_stack()`. |
| `tests/test_session_auth.py` | **New** | Unit tests for token lifecycle, expiry, revocation, delegation chains. |
| `docs/SESSION_DELEGATION_ARCH.md` | **New** | This document. |
