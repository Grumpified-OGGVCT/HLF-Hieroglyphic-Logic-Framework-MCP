# Quick Fix - Use the Script

I've created a PowerShell script that will safely add the configuration without breaking your existing settings.

## Run This:

```powershell
.\fix-cursor-config.ps1
```

The script will:
1. ✅ Backup your existing settings
2. ✅ Merge the AgentsKB config properly
3. ✅ Preserve all your other settings
4. ✅ Validate the JSON

## Or Fix Manually

See `MANUAL_FIX.md` for step-by-step manual instructions.

## What Went Wrong?

When you pasted the config, it probably:
- Created duplicate `mcpServers` objects
- Had a syntax error (missing comma, extra comma, etc.)
- Overwrote existing MCP servers

The script fixes all of these issues automatically.

