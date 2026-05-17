# Session Auth Delegation

## Goal

Allow a parent HLF VM to authenticate once and have all child VMs (sub-agents)
inherit its permissions without individual auth prompts.

## How It Works

1. **Parent VM authenticates** with a sufficient tier (e.g. `forge` or
   `sovereign`).
2. When the parent spawns a child VM via `HlfVM.spawn_child()`, the child
   receives:
   - `parent_session_id` — the parent's session id
   - `_tier` copied into its scope via `delegate_session_auth()`
   - `_session_delegated = True` in its scope
3. **`_dispatch_host`** checks the child's effective tier.  If the child is
   `hearth` but `_session_delegated` is True and the parent tier was sufficient
   (`forge`/`sovereign`), the operator-tier host function is allowed.

## API

### `HlfVM.__init__(..., session_id=None, parent_session_id=None)`

Optional params added to the VM constructor.

### `HlfVM.spawn_child(tier=None, max_gas=None) -> HlfVM`

Spawns a child VM with a new `session_id` and `parent_session_id` set to the
parent's `session_id`.  Automatically calls `delegate_session_auth(parent.scope,
child.scope)`.

### `delegate_session_auth(parent_scope, child_scope)`

Helper that copies `_tier` and sets `_session_delegated = True` in the child
scope.

## Usage Example

```python
from hlf_mcp.hlf.runtime import HlfVM

parent = HlfVM(tier="forge", session_id="sess-abc")
parent.scope["_tier"] = "forge"

child = parent.spawn_child(tier="hearth")
# child.scope now has:
#   _tier = "forge"
#   _session_delegated = True

# Child can now call operator-tier host functions even though
# its own tier attribute is "hearth".
```

## Security Notes

- Delegation is **one-way** and **one-level deep** in the current implementation.
  A child delegates from its immediate parent only.
- The `_session_delegated` flag acts as an audit marker; the runtime still
  verifies the parent's tier was sufficient (`forge` or `sovereign`).
- `delegate_session_auth` only copies `_tier` and `_session_delegated` — no
  other scope data is leaked to the child.

## Files Changed

- `hlf_mcp/hlf/runtime.py` — added `session_id`, `parent_session_id`,
  `spawn_child()`, `delegate_session_auth()`, and updated `_dispatch_host` tier
  gate.
