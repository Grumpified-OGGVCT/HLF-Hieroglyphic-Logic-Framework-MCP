# How MCP Servers Work

## Quick Answer

**You don't need to start the server manually!** Claude Desktop starts it automatically when you configure it.

## The MCP Architecture

```
┌─────────────────┐
│ Claude Desktop  │  ← You interact with this
│  (MCP Client)    │
└────────┬────────┘
         │
         │ Automatically spawns
         │ (you don't do anything)
         ▼
┌─────────────────┐
│ AgentsKB MCP    │  ← Runs in background
│     Server      │     automatically
└────────┬────────┘
         │
         │ HTTP requests
         ▼
┌─────────────────┐
│  AgentsKB API   │
└─────────────────┘
```

## What Happens When You Configure It

1. **You edit Claude Desktop config** - Add the server configuration
2. **You restart Claude Desktop** - So it reads the new config
3. **Claude Desktop automatically starts the server** - Spawns it as a child process
4. **Server runs in background** - Handles requests automatically
5. **You use it in conversations** - Just ask questions, tools work automatically

## You Never Need To:

- ❌ Run `npm start` manually
- ❌ Keep a terminal window open
- ❌ Start/stop the server
- ❌ Monitor the server process

## What Claude Desktop Does:

- ✅ Spawns the server process automatically
- ✅ Manages the server lifecycle
- ✅ Restarts the server if it crashes
- ✅ Handles all communication via stdio
- ✅ Shows tools in the UI automatically

## Configuration Example

Once you add this to your Claude Desktop config:

```json
{
  "mcpServers": {
    "agentskb": {
      "command": "npx",
      "args": ["-y", "tsx", "C:\\Users\\gerry\\AgentKB_MCP\\src\\index.ts"],
      "env": {
        "AGENTSKB_API_KEY": "your_key_here"
      }
    }
  }
}
```

Claude Desktop will:
1. Run `npx -y tsx C:\Users\gerry\AgentKB_MCP\src\index.ts` automatically
2. Communicate with it via stdin/stdout
3. Show the tools in Claude Desktop UI
4. Call the tools when you ask questions

## Testing (Optional)

If you want to verify the server works, you can test it:

```bash
npm start
```

This will start the server and wait for MCP messages. You can send test JSON-RPC messages to verify it works, but this is **not required** for normal use.

## Troubleshooting

**"The server isn't working"**
- Check Claude Desktop logs (not the server - Claude Desktop manages it)
- Verify the path in config is correct
- Make sure `.env` file exists with API key
- Restart Claude Desktop after config changes

**"I don't see the tools"**
- Restart Claude Desktop (required after config changes)
- Check Claude Desktop logs for errors
- Verify the command path is correct

**"How do I know if it's running?"**
- If tools appear in Claude Desktop, it's running
- Check Claude Desktop's process list (it will show the server as a child process)
- You don't need to check - if it's configured, Claude Desktop manages it

## Summary

Think of it like a browser extension:
- You install it once (configure it)
- It runs automatically when needed
- You don't manually start it
- The application (Claude Desktop) manages it

The MCP server is the same - Claude Desktop manages it completely automatically.

