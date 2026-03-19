# Legacy Probe Scripts

These scripts were removed from the repo root after the canonical automated test surface was narrowed to [tests](../../tests).

They are preserved here only as manual compatibility probes for the older `hlf/` MCP stack.

Run them from the repository root if needed, for example:

```powershell
python scripts/legacy_probes/test_mcp_minimal.py
python scripts/legacy_probes/test_mcp.py
```

They are not part of default `pytest` collection and should not be treated as the packaged-product regression suite.