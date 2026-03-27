# Usage Tracking & Rate Limiting

## How I Actually Use AgentsKB

### ✅ **I AM Using AgentsKB** (When Appropriate)

When I call the `ask_question` or `search_questions` tools, I'm:
1. **Actually making API calls** to AgentsKB
2. **Getting real responses** from the 26,841 Q&A knowledge base
3. **Not guessing** - I'm using the tool when I need authoritative answers

### 🔍 **My Research Process**

When you ask a technical question:

1. **First**: I check my training data and context
2. **If uncertain or need authoritative answer**: I use AgentsKB
3. **If still need more**: I might search web/docs (if I have those tools)
4. **Combine sources**: I synthesize information from multiple sources when available

### 📊 **Rate Limiting System**

The MCP server now includes:

- **Dynamic Rate Limiting**: Configurable via `AGENTSKB_RATE_LIMIT` env var
- **Monthly Tracking**: Resets automatically each month
- **Usage Monitoring**: New `get_usage` tool to check current usage
- **Automatic Enforcement**: Blocks requests when limit exceeded

## Configuration

### Set Your Limit

In `.env`:
```env
AGENTSKB_RATE_LIMIT=10000  # Pro Plan: 10,000/month
```

Or for Free tier:
```env
AGENTSKB_RATE_LIMIT=300  # Free tier: 300/month
```

### Check Usage

I can call the `get_usage` tool to see:
- Current requests this month
- Remaining requests
- Reset date
- Percentage used

## How I Decide to Use It

### I Use AgentsKB When:
- ✅ Technical questions I'm uncertain about
- ✅ Need authoritative, sourced answers
- ✅ Best practices questions
- ✅ Domain-specific technical details

### I Don't Use It When:
- ❌ Simple questions I'm confident about
- ❌ General conversation
- ❌ Questions outside technical domains
- ❌ When I have sufficient context

## Usage Tracking

The server tracks usage in: `~/.agentskb-usage.json`

Format:
```json
{
  "month": "2025-01",
  "requests": 42,
  "limit": 10000,
  "resetDate": "2025-02-01T00:00:00.000Z"
}
```

## Dynamic Limit Updates

You can change the limit anytime:
1. Update `AGENTSKB_RATE_LIMIT` in `.env`
2. Restart Cursor (or the server will pick it up on next request)
3. The limit applies immediately

## Proactive Usage Management

I'll:
- ✅ Check usage before making requests (via `canMakeRequest()`)
- ✅ Show usage info in responses when relevant
- ✅ Warn when approaching limits
- ✅ Stop automatically when limit reached

## Transparency

Every response from `ask_question` includes usage info:
```json
{
  "question": "...",
  "answer": "...",
  "_usage": {
    "requests": 42,
    "limit": 10000,
    "remaining": 9958,
    "resetDate": "2025-02-01T00:00:00.000Z"
  }
}
```

This way you always know:
- How many requests I've made
- How many remain
- When it resets

## My Commitment

I'll:
- ✅ Use AgentsKB judiciously (not spam it)
- ✅ Respect rate limits automatically
- ✅ Show usage transparency
- ✅ Make smart decisions about when to use it

**I'm actually calling the API - not guessing!** 🎯

