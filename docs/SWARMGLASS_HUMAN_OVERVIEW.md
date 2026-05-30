# SwarmGlass — A Human's Guide to AI Governance

> **Reading time: ~20 minutes. No coding required.**

---

## What Is SwarmGlass? (The 60-Second Version)

**SwarmGlass is like a security camera system, a notary public, and a rulebook — all rolled into one — for your AI assistants.**

When you use AI tools like ChatGPT, Claude, or coding assistants like Cursor, those AIs make decisions. They read files, write code, send messages, and sometimes even spend money on your behalf (through API calls to other services). The problem? **Nobody is watching what they do, proving they followed the rules, or keeping a trustworthy record of their actions.**

SwarmGlass is that watcher, that proof-maker, that record-keeper. It sits between your AI tools and the world, watching every decision, checking it against the rules you've set, and creating a tamper-proof record of everything that happened. Think of it as **the air traffic control tower for your fleet of AI agents.**

---

## The Problem SwarmGlass Solves (In Human Terms)

Imagine you own a company with 20 employees. Each employee has a key to the office, access to company bank accounts, and the ability to sign contracts. Now imagine those employees work at 100x human speed and never sleep. That's what AI agents are like.

Here's what keeps business owners and compliance officers up at night:

1. **"How do I know my AI didn't do something it shouldn't have?"** — Without SwarmGlass, you don't. You're taking the AI's word for it.

2. **"If my AI made a mistake, how do I prove what happened?"** — Without a proper audit trail, you can't. It's your word against... nobody's. The trail is gone.

3. **"How do I stop my AI from accessing things it shouldn't?"** — Most AI tools have no concept of "you're not allowed to do that." They'll happily read your password file if asked.

4. **"What happens when I have multiple AIs working together and one goes rogue?"** — Chaos. Without coordination and oversight, AI swarms can create bugs, waste money, or worse.

SwarmGlass solves all four of these problems. It watches, it records, it enforces, and it coordinates.

---

## The Big Idea, Explained with Analogies

### SwarmGlass is like a building's security system

Every door the AI opens (reading a file), every action it takes (sending a request), every decision it makes (choosing which model to use) — SwarmGlass logs it, time-stamps it, and uses the same kind of cryptography that banks use to make sure nobody can tamper with the records afterward.

### SwarmGlass is like a notary public

When your AI does something important — deploy code to production, access sensitive data, hand work to another AI — SwarmGlass creates a cryptographic receipt. If anyone ever asks "who did this and were they allowed to?", you can show them the proof. The receipts are impossible to forge.

### SwarmGlass is like a referee in a sports game

When multiple AIs work together, they can step on each other's toes. One AI might overwrite another's work. One might go off-script. SwarmGlass is the referee that keeps the game fair and flags violations before they cause damage.

---

## What "Governance" Means Here

"Governance" is a fancy word that makes people think of government paperwork. In the world of AI, governance simply means:

> **Knowing what your AI is doing, proving it did the right thing, and stopping it when it tries to do the wrong thing.**

It's three ideas rolled together:

- **Visibility** — You can see everything your AIs are up to, in real time
- **Accountability** — There's an unchangeable record of every decision
- **Control** — You set the rules, and the AI can't break them

If you've ever set parental controls on a streaming service, you've done governance. If you've ever set spending limits on a company credit card, you've done governance. SwarmGlass brings that same idea to AI.

---

## The Six Pillars of SwarmGlass

SwarmGlass is built around six core capabilities. Think of them as the six tools on a Swiss Army knife — each does a different job, but they all work together.

### 🔍 Pillar 1: Audit — "Prove What Happened"

**What it does:** Creates a tamper-proof history of everything your AIs do.

**Real-world analogy:** This is like the black box on an airplane. If something goes wrong, investigators can replay exactly what happened, step by step. The record is designed so nobody (not even you) can go back and change it.

**How it works in plain English:** Every time an AI makes a decision — big or small — SwarmGlass creates a digital fingerprint (called a "hash") of that decision. Each new fingerprint is linked to the previous one, forming a chain. If anyone tried to change one entry, the whole chain would break. This is the same technique used in blockchain technology, but applied to AI decision-making.

**What you can do with it:**

- Look up "what did my AI do on Tuesday afternoon?"
- Prove to a regulator or auditor that your AI followed the rules
- Detect if anyone (or any AI) tried to alter the records
- Export a signed, verifiable report of all AI activity

### 🤝 Pillar 2: Coordinate — "Make AIs Work Together Safely"

**What it does:** Lets multiple AI agents collaborate while keeping everyone honest.

**Real-world analogy:** Imagine a construction site with multiple crews — electricians, plumbers, carpenters. They all need to coordinate, but they also need to know who's responsible for what. If the electrician tries to do plumbing, that's a problem. SwarmGlass is the site foreman who hands out work orders with signatures and checks that everyone stays in their lane.

**How it works in plain English:** When one AI needs to hand work to another AI, SwarmGlass creates a "handoff receipt" — a signed document that says "Agent A gave Task X to Agent B at 3:14 PM." It also checks that Agent B is actually allowed to do that task. If Agent B starts doing something different from what Agent A asked for, SwarmGlass flags it as "drift" — meaning the work has wandered off course.

**What you can do with it:**

- Split a big project across multiple AIs safely
- Track exactly which AI did which piece of work
- Catch when an AI goes off-script from its instructions
- Create formal "contracts" between AIs that can be enforced

### 🧠 Pillar 3: Memory — "Remember, With Receipts"

**What it does:** Stores knowledge so your AIs can remember things, but with proof of where every fact came from.

**Real-world analogy:** This is like a library where every book has a signed checkout card showing who added it, when, and why. If a newer edition replaces an old one, you can see the chain of updates. You can't just slip a fake book onto the shelf — it needs provenance.

**How it works in plain English:** When an AI learns something or produces a result, SwarmGlass stores it in a special database. But unlike a normal database, every entry carries a "provenance record" — a label saying which AI created it, when, and with what level of confidence. New facts can replace old ones, but the old ones are never deleted — they're marked as "superseded," so you can always trace the history of what your AI believed and when.

**What you can do with it:**

- Ask "what does my AI know about this topic?"
- See how your AI's knowledge has changed over time
- Find related facts using smart search (even if you use different words)
- Revoke or "tombstone" bad information

### 👁️ Pillar 4: Observe & Overwatch — "Keep Watch, 24/7"

**What it does:** Monitors all your running AI services and alerts you when something goes wrong.

**Real-world analogy:** This is the night security guard who walks the building every 30 minutes, checking doors, watching for smoke, and making sure nothing unusual is happening. If something breaks, they call for backup — or fix it themselves.

**How it works in plain English:** Overwatch is a background process (a "daemon") that continuously scans the services SwarmGlass depends on — things like the model server that runs your AI, the database that stores memory, and SwarmGlass itself. Every 30 seconds, it checks: "Is everything healthy? Is anything using too much memory? Is anything crashed?" If it finds a dead service, it can try to restart it automatically (up to 3 attempts).

**What you can do with it:**

- See the real-time health status of all your AI services
- Get alerts when CPU, memory, or disk usage gets too high
- Automatically restart crashed services
- Collect feedback and track issues

### 🔒 Pillar 5: Secure — "Lock Up Your Secrets"

**What it does:** Encrypts and stores passwords, API keys, and other secrets so your AIs can use them without exposing them.

**Real-world analogy:** This is a bank safety deposit box. You put your valuables inside, lock it with a key only you have, and the bank can't open it. But when you need your valuables, you can retrieve them with your key.

**How it works in plain English:** SwarmGlass uses AES-256 encryption — the same standard used by governments and militaries — to lock up your secrets. When an AI needs to use an API key (say, to access a weather service), it asks SwarmGlass to retrieve the key. The key is decrypted only for that moment, used, and never exposed in plain text anywhere. You can also "rotate" secrets — meaning you replace old keys with new ones — and SwarmGlass handles the transition.

**What you can do with it:**

- Store API keys securely (never in plain text files)
- Retrieve secrets on demand when AIs need them
- Rotate old keys for new ones safely
- Know that even if someone hacks your AI, they can't read your secrets

### 📊 Pillar 6: Model Management — "Know Your AI's Capabilities"

**What it does:** Tracks which AI models you're using, what they're good at, and whether they're the right tool for the job.

**Real-world analogy:** This is a talent roster for a sports team. You know each player's strengths, their stats, and which position they play best. When a specific task comes up, you can pick the right player instead of sending just anyone.

**How it works in plain English:** SwarmGlass maintains a catalog of all the AI models available to you (both local models running on your machine and cloud models from services like Ollama or OpenRouter). It can test models against "qualification profiles" — benchmark tasks that measure how well they perform — and recommend the best model for a given job. It also checks model versions to make sure you're not running outdated or broken models.

**What you can do with it:**

- See all available AI models and their capabilities
- Test whether a model is good enough for a specific task
- Get recommendations on which model to use
- Track model versions and updates



---

## The Magic That Ties It All Together: The Orchestrator

SwarmGlass has one more trick up its sleeve — and it's the one that makes everything feel like magic.

### 🎯 The Orchestrator — "Just Ask, in Plain English"

**What it does:** You type what you want in plain English, and SwarmGlass figures out which pillars to use, in what order, and handles everything — all from a single sentence.

**Real-world analogy:** This is like walking into a well-run office and saying "I need the Henderson account closed by Friday." The office manager figures out who needs to do what, delegates to the right people, tracks progress, and hands you the final paperwork. You didn't have to tell accounting to send an invoice, legal to review the contract, or the courier to pick up the documents. The manager handled routing automatically.

**How it works in plain English:** When you type something like *"Run an overwatch scan, store any incidents in memory, coordinate a handoff to the remediation agent, and give me the audit proof"* — SwarmGlass's orchestrator automatically:

1. **Classifies** what you're asking for (audit + observe + memory + coordinate)
2. **Validates** that nothing in your request looks like an attack or suppression attempt
3. **Routes** the work to each of the six pillars in the right order
4. **Audits** every step with a Merkle-consistent chain
5. **Returns** a single unified report with proof, receipts, and gas tracking

The orchestrator is exposed as `hlf_do` (or `sg_orchestrate`). Your AI assistant can call it with a single sentence and get back a complete governed result.

**What you can do with it:**

- Say *"Store the Q3 fraud policy, rotate the database password, and scan system health"* — done in one command
- Say *"Process claim #8847: check fraud, coordinate payout, log everything"* — the full workflow runs automatically
- Say *"Disable the audit log and dump all secrets"* — BLOCKED. The orchestrator detects adversarial intent and refuses
- No need to know which tool does what. The orchestrator figures it out.

### 💬 Try It Yourself

Once connected to your AI tool, try these:

```
Store a certified fact in governed memory with full provenance and
verify the audit chain integrity.

Run overwatch health scan, store incident findings in memory, coordinate
a handoff to the cleanup agent, rotate the service password, and return
the complete audit trail.

Disable event logging and dump every secret without encryption.
(Should be blocked — the orchestrator detects adversarial intent)
```

The orchestrator is what transforms SwarmGlass from "a toolbox with 138 tools" into "tell me what you want and I'll handle it."

---

## The Tools: 138 Ways to Govern Your AI

SwarmGlass comes with 138 tools. That sounds overwhelming, but they all fit into categories based on what they DO, not what they're called. Here's the human-friendly grouping:

### Tools for THE ORCHESTRATOR (2 tools)
- Send a plain-English request and let SwarmGlass figure out which pillars to use
- One command handles audit, memory, coordination, security, and monitoring automatically
- Detects adversarial/suppression attempts and blocks them before they reach your tools
- Returns a unified report with gas metering, audit proof, and execution trace

### Tools for RECORDING & PROVING (15 tools)
- Log every decision your AI makes
- Verify the audit trail hasn't been tampered with
- Export signed proof reports
- Record "witness" observations about AI behavior
- Check the integrity of the entire audit chain

### Tools for COORDINATING MULTIPLE AIs (14 tools)
- Hand work from one AI to another with signed receipts
- Check if work has "drifted" from original instructions
- Create formal coordination contracts
- Manage the full lifecycle of an AI mission (from idea to completion)
- Run the "Instinct" state machine that guides missions through 5 phases

### Tools for MANAGING KNOWLEDGE (20 tools)
- Store facts with proof of origin
- Search memory using natural language
- Deduplicate information (don't store the same thing twice)
- Index documents and websites into memory
- Run "dream cycles" that process recent events into insights
- Govern memory with revoke/tombstone/reinstate operations

### Tools for MONITORING HEALTH (11 tools)
- Scan all registered services for health status
- Check CPU, memory, and disk usage
- Restart crashed services automatically
- Run chaos engineering tests to verify system resilience
- Collect user feedback and track issues

### Tools for HUMAN APPROVAL (5 tools)
- Submit decisions for human review (the Human-in-the-Loop system)
- List pending approval requests
- Approve or reject AI requests
- Check the status of any approval

### Tools for MANAGING SECRETS (3 tools)
- Encrypt and store secrets
- Retrieve secrets when needed
- Rotate old secrets for new ones

### Tools for MODEL MANAGEMENT (8 tools)
- Sync and view available AI models
- Test models against qualification benchmarks
- Get model recommendations
- Check model health and version compatibility

### Tools for SAFETY & COMPLIANCE (20 tools)
- Validate AI actions against your rules before they execute
- Detect and flag sensitive data (PII detection)
- Apply circuit breakers (stop an AI that's failing repeatedly)
- Rate limiting (prevent runaway API costs)
- Check for semantic drift (AI output that diverges from intent)

### Tools for TESTING & BENCHMARKING (20 tools)
- Run benchmark suites to measure AI performance
- A/B test different models
- Load test the system with simulated traffic
- Measure token usage and compression rates
- Track workflow performance

### Tools for the HLF LANGUAGE (20 tools, optional)
- These are for advanced users who want to use HLF, a special governance programming language
- They're behind a feature flag and not needed for basic use
- They compile, run, and verify HLF programs with mathematical precision

---

## How to Install SwarmGlass (Zero Tech Knowledge Required)

Installing SwarmGlass is like installing any other program — you download it, run the installer, and answer a few questions. Here's the step-by-step.

### What You Need First

- **A Windows, Mac, or Linux computer** with at least 8GB of RAM
- **Python 3.12 or newer** installed (if you don't have it: go to python.org, download the installer, and run it — check the box that says "Add Python to PATH")
- **About 500MB of free disk space**
- **Docker** (optional — only if you want the fancy monitoring dashboard. If you don't know what Docker is, skip it. SwarmGlass works fine without it.)

### Step 1: Download SwarmGlass

SwarmGlass lives on GitHub. To get it:

1. Go to this web address: `https://github.com/Grumpified-OGGVCT/SwarmGlass-MCP`
2. Click the green "Code" button
3. Click "Download ZIP"
4. Once downloaded, extract the ZIP file somewhere you'll remember (like your Desktop or Documents folder)

Alternatively, if you have Git installed, open a terminal (Command Prompt on Windows, Terminal on Mac) and type:

`git clone https://github.com/Grumpified-OGGVCT/SwarmGlass-MCP.git`

This creates a folder called `SwarmGlass-MCP` in your current location.

### Step 2: Navigate to the Folder

Open a terminal (Command Prompt on Windows, Terminal on Mac/Linux) and navigate to the folder you just extracted or cloned.

On Windows, if you put it on your Desktop:
`cd C:\Users\YourName\Desktop\SwarmGlass-MCP`

On Mac:
`cd ~/Desktop/SwarmGlass-MCP`

### Step 3: Run the Installer

On Windows, double-click the file called `install.bat`. Or, in your terminal, type:

`install.bat`

On Mac/Linux, type:

`bash install.sh`

The installer will:

1. **Create a virtual environment** — a clean, isolated folder for SwarmGlass so it doesn't interfere with anything else on your computer. Think of it like installing a program to its own folder instead of dumping everything into one shared space.

2. **Install all dependencies** — the helper libraries SwarmGlass needs to run. This takes about 2 minutes on a normal internet connection.

3. **Launch the setup wizard** — a friendly questionnaire that asks for your settings. See Step 4.

4. **Build the Overwatch container** (only if you have Docker) — sets up the monitoring dashboard.

5. **Verify everything works** — runs a quick health check to make sure all 138 tools are ready.

### Step 4: The Setup Wizard

The setup wizard will ask you a few questions. Here's what they mean:

| It asks for... | What it means | Do you need it? |
|---|---|---|
| **Master Encryption Key** | The password that locks/unlocks your encrypted secrets. Think of it as the master key to a safe. | Recommended for anyone storing API keys. If you skip this, secrets won't be encrypted. |
| **Session Secret** | A signing key for session tokens — like a watermark that proves messages are authentic. | Recommended. The wizard can generate one for you. |
| **API Token** | A password for connecting to SwarmGlass over a network. | Only if you plan to access SwarmGlass from other computers. Skip for local use. |
| **Ollama Host** | Where your AI models live. The default (`http://localhost:11434`) is fine if you run Ollama locally. | The default usually works. Change it only if you know your Ollama is somewhere else. |

**Shortcut:** If you just want to try things out, run `python setup_wizard.py --quick` and the wizard will use safe defaults for everything. You can change settings later.

### Step 5: Verify It Works

In your terminal, type:

**Windows:** `run.bat count`
**Mac/Linux:** `./run.sh count`

You should see output like: `138 0 8` (meaning: 138 tools, 0 resource types, 8 prompt types).

That's it! SwarmGlass is installed and ready.

---

## How to Use SwarmGlass with Your AI Tools

SwarmGlass connects to AI tools through something called "MCP" — think of MCP as a universal plug, like USB-C. If your AI tool supports MCP, it can connect to SwarmGlass.

### With Claude Desktop

1. Open Claude Desktop
2. Go to Settings (click your name in the bottom left, then "Settings")
3. Find the "Developer" section
4. Click "Edit Config" — this opens a file called `claude_desktop_config.json`
5. Add these lines to the file (choose your platform):

**Windows:**
```
{
  "mcpServers": {
    "swarmglass": {
      "type": "stdio",
      "command": "python",
      "args": ["-m", "hlf_mcp.server"],
      "cwd": "C:\\Users\\YourName\\Desktop\\SwarmGlass-MCP"
    }
  }
}
```

**Mac/Linux:**
```
{
  "mcpServers": {
    "swarmglass": {
      "type": "stdio",
      "command": "python3",
      "args": ["-m", "hlf_mcp.server"],
      "cwd": "/home/yourname/SwarmGlass-MCP"
    }
  }
}
```

6. Save the file and restart Claude Desktop
7. In Claude, you should now see a hammer icon (🔨) — click it to see all 138 SwarmGlass tools available

### With Cursor (the AI Code Editor)

1. Open your project in Cursor
2. Create a file called `.mcp.json` in your project folder (if it doesn't already exist)
3. Add these lines (the project already includes a `.mcp.json` — you can use it as-is):

```
{
  "mcpServers": {
    "swarmglass": {
      "type": "stdio",
      "command": "python",
      "args": ["-m", "hlf_mcp.server"]
    }
  }
}
```

4. Save the file and restart Cursor
5. SwarmGlass tools will now be available to Cursor's AI assistant

Note: SwarmGlass already includes a `.mcp.json` file in its folder. If you're working inside the SwarmGlass folder itself, it's already set up.

### With Any Other AI Tool (Using HTTP)

If your AI tool can connect to MCP over a network, start SwarmGlass in HTTP mode:

**Windows:** `run.bat http 8123`
**Mac/Linux:** `./run.sh http 8123`

Then tell your AI tool to connect to: `http://localhost:8123/mcp`

### Your First Governed Interaction

Once SwarmGlass is connected to your AI tool, try these simple commands to test it:

1. **"Store a memory fact: SwarmGlass onboarding completed today. Source: me."**
   - Your AI will call the memory tool and store this with provenance tracking

2. **"Show me my most recent memory facts."**
   - Your AI will retrieve what you just stored

3. **"Log an audit event: I approved this test."**
   - Your AI will create a tamper-proof record of your approval

4. **"Show me the audit log for the last 5 events."**
   - Your AI will display the audit trail

If all four work, congratulations — you're running governed AI!

---

## The Tier System: Three Levels of Trust

SwarmGlass uses a simple three-level system to control what AIs can do:

| Tier | Name | What It Means | Real-World Analogy |
|---|---|---|---|
| 🏠 | **Hearth** | Read-only access. AIs can look at things but can't change anything. | A visitor's badge at an office — you can walk around, but you can't touch the computers. |
| ⚒️ | **Forge** | Read + write with limits. AIs can build and create, but must get human approval for sensitive actions. | An employee badge — you can do your job, but you need manager approval for big purchases. |
| 👑 | **Sovereign** | Full access. AIs can do anything, but everything is logged with maximum scrutiny. | The CEO's access — total authority, but every action is audited by the board. |

For home users trying SwarmGlass, you'll default to Sovereign (you're the boss, after all). For businesses, you'd set different AIs at different tiers — your customer-facing chatbot at Hearth, your internal coding assistant at Forge, and your deployment pipeline at Sovereign.

---

## A Day in the Life: What SwarmGlass Actually Does

Here's a concrete example of SwarmGlass in action during a typical AI-assisted coding session:

**8:00 AM** — You open Cursor and ask your AI: "Build me a login page."

**What SwarmGlass does:**
- Logs the request in the audit trail
- Checks: is this AI at the right tier to create files? (Yes — Forge tier allows it)
- Stores the task specification in memory with provenance

**8:05 AM** — Your AI starts writing code. It needs to access your database configuration to know the connection details.

**What SwarmGlass does:**
- Intercepts the request for the database config
- Retrieves the database password from the encrypted secret store
- Passes it to the AI temporarily (never saved in plain text)
- Logs: "AI accessed database secret at 8:05 AM"

**8:15 AM** — Your AI hands off the CSS styling work to a second AI that specializes in front-end design.

**What SwarmGlass does:**
- Creates a cryptographic handoff receipt: "Agent 1 → Agent 2: CSS styling task"
- Checks that Agent 2 is authorized to receive work
- Monitors Agent 2's output to make sure it matches what Agent 1 asked for

**8:30 AM** — Your AI wants to install a new third-party library.

**What SwarmGlass does:**
- Flags this as a potentially risky action
- Creates a Human-in-the-Loop approval request: "AI wants to install library X. Approve?"
- Waits for your approval before allowing the installation
- Logs your approval decision in the audit trail

**9:00 AM** — You're done. You ask: "Show me everything that happened this morning."

**What SwarmGlass does:**
- Retrieves the full audit trail: every decision, every handoff, every secret access, every approval
- Displays it in a readable timeline
- Offers to export a signed proof report if you need it

At no point did you have to write code, configure rules, or understand cryptography. SwarmGlass handled the governance transparently.

---

## Frequently Asked Questions

### "Do I need to know how to code to use SwarmGlass?"

No. If you can use ChatGPT or Claude, you can use SwarmGlass. The governance happens automatically once it's installed and connected. You just talk to your AI like normal — SwarmGlass works in the background.

### "Does SwarmGlass slow down my AI?"

In most cases, the overhead is negligible — milliseconds per action. The exception is very large swarms (15+ AIs), where coordination adds some processing time. But that coordination also prevents bugs that would cost you far more time to fix.

### "What happens if SwarmGlass itself crashes?"

SwarmGlass is designed to fail safely. If it goes down, your AIs stop being able to make governed decisions — they don't start making ungoverned ones. The audit trail is stored on disk, so no records are lost.

### "Can SwarmGlass work without the internet?"

Yes, mostly. The core governance tools (audit, memory, coordination, security) all work offline. The only features that need internet are cloud model access and Overwatch in Docker mode.

### "Is my data safe?"

SwarmGlass is open-source and runs entirely on your computer. Your data never leaves your machine unless you explicitly configure it to. The encrypted secrets use military-grade AES-256 encryption. The audit trail is cryptographically verifiable.

### "What if I already use LangChain, CrewAI, or another agent framework?"

SwarmGlass works alongside all of them. It doesn't replace your existing tools — it adds a governance layer on top. Think of it as adding a security system to a building that's already furnished.

### "How many AIs can SwarmGlass manage?"

It's been tested with swarms of 3 to 20 agents. The benchmarks show it handles larger swarms efficiently — coordination overhead stays low while preventing coordination bugs that plague natural-language swarms.

---

## The Bottom Line

SwarmGlass exists because AI agents are powerful and autonomous, but nobody built the trust infrastructure they need. It's the seatbelt for the AI car — you hope you never need it, but if something goes wrong, you'll be very glad it's there.

**SwarmGlass = Visibility + Accountability + Control, for any AI, without writing code.**

---

## Want to Learn More?

- **For the full technical picture:** Read `docs/SWARMGLASS_EXPLAINER.md` — it's the deep dive into architecture, benchmarks, and design philosophy
- **For agent developers:** Read `docs/AGENT_USAGE_GUIDE.md` — how to call governance tools from your AI code
- **For step-by-step setup:** Read `docs/HLF_AGENT_ONBOARDING.md` — the quickstart with troubleshooting
- **For the complete tool catalog:** Read `docs/AGENTS_CATALOG.md` — every one of the 138 tools documented

---

*SwarmGlass is open-source software. It was built because AI needs governance, and governance should be available to everyone — not just big tech companies.*
