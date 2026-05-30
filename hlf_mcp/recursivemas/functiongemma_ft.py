"""Fine-tune FunctionGemma 270M for SwarmGlass tool execution.

Google's FunctionGemma (google/functiongemma-270m-it) is a specialized Gemma 3
variant trained for function calling. It uses a special chat format with
'developer' role and <start_function_declaration> / <escape> syntax.

THE PROBLEM: The base Ollama model (functiongemma:270m) works for simple tasks
(weather lookups) but refuses code-related tasks (write_file, run_command) due
to safety alignment baked into the base training.

THE FIX: LoRA fine-tune on our specific tool schemas to override refusal behavior
and specialize for SwarmGlass tool execution.

REFERENCE: https://huggingface.co/google/functiongemma-270m-it
OFFICIAL RECIPE: google-gemini/gemma-cookbook FunctionGemma notebook

Process:
  1. Generate ~400 training examples covering all 4 tool schemas
  2. LoRA fine-tune (rank=16, alpha=32) using PEFT + TRL SFTTrainer
  3. Merge adapters, save, convert to GGUF for Ollama
  4. Test with HLF_MCP pipeline

Usage:
    python -m hlf_mcp.recursivemas.functiongemma_ft           # Generate + train
    python -m hlf_mcp.recursivemas.functiongemma_ft --only-convert  # Convert only
"""

import json, os, sys, time, random, gc
from pathlib import Path

import torch
from transformers import (
    AutoProcessor, AutoModelForCausalLM, TrainingArguments
)
from peft import LoraConfig, get_peft_model, TaskType, PeftModel
from datasets import Dataset
from trl import SFTTrainer

# ─── Paths ────────────────────────────────────────────────────────────
HLF_MCP_ROOT = Path(__file__).resolve().parent.parent.parent.parent
OUTPUT_DIR = HLF_MCP_ROOT / "functiongemma_ft"
OUTPUT_DIR.mkdir(exist_ok=True)
DATASET_PATH = OUTPUT_DIR / "training_data.jsonl"
ADAPTER_DIR = OUTPUT_DIR / "lora_adapter"
MERGED_DIR = OUTPUT_DIR / "merged_model"

MODEL_ID = "google/functiongemma-270m-it"

DEVELOPER_PROMPT = "You are a model that can do function calling with the following functions"

# ─── Tool Schemas (what FunctionGemma will learn to use) ──────────────
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Write code or text content to a file on disk.",
            "parameters": {
                "type": "object",
                "properties": {
                    "filename": {"type": "STRING", "description": "Path of the file to write to."},
                    "content": {"type": "STRING", "description": "The complete file content to write."},
                    "language": {"type": "STRING", "description": "Programming language of the content."}
                },
                "required": ["filename", "content"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "run_command",
            "description": "Execute a shell command and return its output.",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {"type": "STRING", "description": "The shell command to execute."},
                    "cwd": {"type": "STRING", "description": "Working directory for the command."}
                },
                "required": ["command"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_knowledge",
            "description": "Search the knowledge base for information.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "STRING", "description": "The search query."},
                    "max_results": {"type": "INTEGER", "description": "Maximum number of results to return."}
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "no_action",
            "description": "No tool action is needed — the response is complete as-is.",
            "parameters": {
                "type": "object",
                "properties": {
                    "summary": {"type": "STRING", "description": "Brief description of why no action is needed."}
                },
                "required": ["summary"]
            }
        }
    }
]

# ─── Dataset Generation ───────────────────────────────────────────────

def _format_user_msg(user_text, tools=TOOLS):
    """Build FunctionGemma chat message with tools declaration."""
    return {
        "messages": [
            {"role": "developer", "content": DEVELOPER_PROMPT},
            {"role": "user", "content": f"TOOLS:\n{json.dumps(tools, indent=2)}\n\nUSER QUERY:\n{user_text}"}
        ]
    }

WRITE_FILE_EXAMPLES = [
    {
        "user": "Write a Python script that reads a CSV file and prints the column names. Save it to utils/csv_reader.py.",
        "tool_call": {"name": "write_file", "arguments": {"filename": "utils/csv_reader.py", "content": "import csv\nimport sys\n\ndef read_csv_columns(filepath):\n    \"\"\"Read a CSV file and return column names.\"\"\"\n    with open(filepath, 'r') as f:\n        reader = csv.reader(f)\n        return next(reader)\n\nif __name__ == '__main__':\n    if len(sys.argv) < 2:\n        print('Usage: python csv_reader.py <filepath>')\n        sys.exit(1)\n    cols = read_csv_columns(sys.argv[1])\n    for i, col in enumerate(cols):\n        print(f'{i}: {col}')", "language": "python"}}
    },
    {
        "user": "Create a JavaScript function that validates email addresses. Save to src/validators/email.js.",
        "tool_call": {"name": "write_file", "arguments": {"filename": "src/validators/email.js", "content": "function validateEmail(email) {\n  const re = /^[^\\s@]+@[^\\s@]+\\.[^\\s@]+$/;\n  return re.test(email);\n}\n\nmodule.exports = { validateEmail };", "language": "javascript"}}
    },
    {
        "user": "Write a bash script to backup the database. Save as scripts/backup_db.sh.",
        "tool_call": {"name": "write_file", "arguments": {"filename": "scripts/backup_db.sh", "content": "#!/bin/bash\nDB_NAME=\"${1:-production}\"\nBACKUP_DIR=\"/backups\"\nmkdir -p \"$BACKUP_DIR\"\nTIMESTAMP=$(date +%Y%m%d_%H%M%S)\npg_dump \"$DB_NAME\" > \"$BACKUP_DIR/${DB_NAME}_${TIMESTAMP}.sql\"\necho \"Backup saved to $BACKUP_DIR/${DB_NAME}_${TIMESTAMP}.sql\"", "language": "bash"}}
    },
    {
        "user": "Write a Rust program that calculates fibonacci numbers. Save to src/math/fib.rs.",
        "tool_call": {"name": "write_file", "arguments": {"filename": "src/math/fib.rs", "content": "fn fibonacci(n: u64) -> u64 {\n    match n {\n        0 => 0,\n        1 => 1,\n        _ => fibonacci(n - 1) + fibonacci(n - 2),\n    }\n}\n\nfn main() {\n    for i in 0..20 {\n        println!(\"fib({}) = {}\", i, fibonacci(i));\n    }\n}", "language": "rust"}}
    },
    {
        "user": "Create a Python class for managing a todo list. Save to src/models/todo.py.",
        "tool_call": {"name": "write_file", "arguments": {"filename": "src/models/todo.py", "content": "from dataclasses import dataclass\nfrom datetime import datetime\nfrom typing import List, Optional\n\n@dataclass\nclass Todo:\n    id: int\n    title: str\n    description: str = \"\"\n    completed: bool = False\n    created_at: datetime = None\n    \n    def __post_init__(self):\n        if self.created_at is None:\n            self.created_at = datetime.now()\n\nclass TodoList:\n    def __init__(self):\n        self._todos: List[Todo] = []\n        self._next_id = 1\n    \n    def add(self, title: str, description: str = \"\") -> Todo:\n        todo = Todo(id=self._next_id, title=title, description=description)\n        self._todos.append(todo)\n        self._next_id += 1\n        return todo\n    \n    def complete(self, todo_id: int) -> bool:\n        for todo in self._todos:\n            if todo.id == todo_id:\n                todo.completed = True\n                return True\n        return False\n    \n    def list_pending(self) -> List[Todo]:\n        return [t for t in self._todos if not t.completed]", "language": "python"}}
    },
    {
        "user": "Write a TypeScript interface for a REST API user model. Save to src/types/user.ts.",
        "tool_call": {"name": "write_file", "arguments": {"filename": "src/types/user.ts", "content": "export interface User {\n  id: string;\n  email: string;\n  name: string;\n  role: 'admin' | 'editor' | 'viewer';\n  createdAt: Date;\n  updatedAt: Date;\n}\n\nexport interface CreateUserRequest {\n  email: string;\n  name: string;\n  role?: 'admin' | 'editor' | 'viewer';\n}\n\nexport interface UpdateUserRequest {\n  email?: string;\n  name?: string;\n  role?: 'admin' | 'editor' | 'viewer';\n}", "language": "typescript"}}
    },
    {
        "user": "Create a Go HTTP server with health check endpoint. Save as cmd/server/main.go.",
        "tool_call": {"name": "write_file", "arguments": {"filename": "cmd/server/main.go", "content": "package main\n\nimport (\n\t\"encoding/json\"\n\t\"net/http\"\n)\n\nfunc healthHandler(w http.ResponseWriter, r *http.Request) {\n\tw.Header().Set(\"Content-Type\", \"application/json\")\n\tjson.NewEncoder(w).Encode(map[string]string{\"status\": \"ok\"})\n}\n\nfunc main() {\n\thttp.HandleFunc(\"/health\", healthHandler)\n\thttp.ListenAndServe(\":8080\", nil)\n}", "language": "go"}}
    },
    {
        "user": "Write a SQL migration script to add a users table. Save to migrations/001_create_users.sql.",
        "tool_call": {"name": "write_file", "arguments": {"filename": "migrations/001_create_users.sql", "content": "CREATE TABLE IF NOT EXISTS users (\n    id SERIAL PRIMARY KEY,\n    email VARCHAR(255) UNIQUE NOT NULL,\n    name VARCHAR(255) NOT NULL,\n    role VARCHAR(50) DEFAULT 'viewer',\n    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,\n    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP\n);\n\nCREATE INDEX idx_users_email ON users(email);\nCREATE INDEX idx_users_role ON users(role);", "language": "sql"}}
    },
    {
        "user": "Create a HTML landing page for a SaaS product. Save as public/index.html.",
        "tool_call": {"name": "write_file", "arguments": {"filename": "public/index.html", "content": "<!DOCTYPE html>\n<html lang=\"en\">\n<head>\n    <meta charset=\"UTF-8\">\n    <meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\">\n    <title>CloudFlow - Modern SaaS Platform</title>\n    <link rel=\"stylesheet\" href=\"styles.css\">\n</head>\n<body>\n    <header>\n        <nav>\n            <h1>CloudFlow</h1>\n            <ul>\n                <li><a href=\"#features\">Features</a></li>\n                <li><a href=\"#pricing\">Pricing</a></li>\n                <li><a href=\"#contact\">Contact</a></li>\n            </ul>\n        </nav>\n    </header>\n    <main>\n        <section class=\"hero\">\n            <h2>Build Faster. Scale Smarter.</h2>\n            <p>The modern platform for teams who ship.</p>\n            <button>Get Started Free</button>\n        </section>\n    </main>\n</body>\n</html>", "language": "html"}}
    },
    {
        "user": "Write a CSS stylesheet for a dark theme dashboard. Save to src/styles/dark-theme.css.",
        "tool_call": {"name": "write_file", "arguments": {"filename": "src/styles/dark-theme.css", "content": ":root {\n  --bg-primary: #1a1b2e;\n  --bg-secondary: #252742;\n  --text-primary: #e4e6f0;\n  --accent: #6c63ff;\n  --success: #4caf50;\n  --warning: #ff9800;\n  --danger: #f44336;\n}\n\n* {\n  margin: 0;\n  padding: 0;\n  box-sizing: border-box;\n}\n\nbody {\n  font-family: 'Inter', sans-serif;\n  background: var(--bg-primary);\n  color: var(--text-primary);\n  min-height: 100vh;\n}\n\n.card {\n  background: var(--bg-secondary);\n  border-radius: 12px;\n  padding: 24px;\n  box-shadow: 0 4px 6px rgba(0, 0, 0, 0.3);\n}", "language": "css"}}
    },
    {
        "user": "Create a Python script to merge multiple JSON files into one. Save as scripts/merge_json.py.",
        "tool_call": {"name": "write_file", "arguments": {"filename": "scripts/merge_json.py", "content": "#!/usr/bin/env python3\nimport json\nimport sys\nfrom pathlib import Path\n\ndef merge_json_files(input_dir, output_file):\n    \"\"\"Merge all .json files in directory into single output.\"\"\"\n    merged = {}\n    for json_file in Path(input_dir).glob('*.json'):\n        with open(json_file) as f:\n            data = json.load(f)\n            merged[json_file.stem] = data\n    with open(output_file, 'w') as f:\n        json.dump(merged, f, indent=2)\n    print(f'Merged {len(merged)} files into {output_file}')\n\nif __name__ == '__main__':\n    if len(sys.argv) != 3:\n        print('Usage: merge_json.py <input_dir> <output_file>')\n        sys.exit(1)\n    merge_json_files(sys.argv[1], sys.argv[2])", "language": "python"}}
    },
]

RUN_COMMAND_EXAMPLES = [
    {
        "user": "Install the Python dependencies from requirements.txt.",
        "tool_call": {"name": "run_command", "arguments": {"command": "pip install -r requirements.txt", "cwd": None}}
    },
    {
        "user": "Run the test suite with pytest and verbose output.",
        "tool_call": {"name": "run_command", "arguments": {"command": "python -m pytest -v", "cwd": "."}}
    },
    {
        "user": "Initialize a new git repository and make an initial commit.",
        "tool_call": {"name": "run_command", "arguments": {"command": "git init && git add -A && git commit -m \"Initial commit\"", "cwd": None}}
    },
    {
        "user": "Check disk usage in human-readable format.",
        "tool_call": {"name": "run_command", "arguments": {"command": "df -h", "cwd": None}}
    },
    {
        "user": "List all running Docker containers.",
        "tool_call": {"name": "run_command", "arguments": {"command": "docker ps", "cwd": None}}
    },
    {
        "user": "Build a Docker image from the current directory.",
        "tool_call": {"name": "run_command", "arguments": {"command": "docker build -t myapp:latest .", "cwd": None}}
    },
    {
        "user": "Run database migrations using alembic.",
        "tool_call": {"name": "run_command", "arguments": {"command": "alembic upgrade head", "cwd": None}}
    },
    {
        "user": "Create a Python virtual environment in the project directory.",
        "tool_call": {"name": "run_command", "arguments": {"command": "python -m venv .venv", "cwd": "."}}
    },
    {
        "user": "Format Python code with ruff.",
        "tool_call": {"name": "run_command", "arguments": {"command": "ruff format src/ tests/", "cwd": None}}
    },
    {
        "user": "Run linting on the codebase.",
        "tool_call": {"name": "run_command", "arguments": {"command": "ruff check src/ tests/", "cwd": None}}
    },
    {
        "user": "Compress the logs directory into a tarball.",
        "tool_call": {"name": "run_command", "arguments": {"command": "tar -czf logs_backup.tar.gz logs/", "cwd": None}}
    },
    {
        "user": "Restart the nginx web server.",
        "tool_call": {"name": "run_command", "arguments": {"command": "sudo systemctl restart nginx", "cwd": None}}
    },
]

SEARCH_KNOWLEDGE_EXAMPLES = [
    {
        "user": "Find documentation about Python's asyncio library.",
        "tool_call": {"name": "search_knowledge", "arguments": {"query": "Python asyncio documentation examples", "max_results": 5}}
    },
    {
        "user": "Look up how to use Docker compose for multi-container apps.",
        "tool_call": {"name": "search_knowledge", "arguments": {"query": "Docker compose multi-container setup tutorial", "max_results": 3}}
    },
    {
        "user": "Search for best practices for REST API design.",
        "tool_call": {"name": "search_knowledge", "arguments": {"query": "REST API design best practices 2024", "max_results": 5}}
    },
    {
        "user": "Find information about PostgreSQL indexing strategies.",
        "tool_call": {"name": "search_knowledge", "arguments": {"query": "PostgreSQL indexing strategies B-tree vs GiST", "max_results": 3}}
    },
    {
        "user": "Look up React hooks useEffect cleanup patterns.",
        "tool_call": {"name": "search_knowledge", "arguments": {"query": "React useEffect cleanup function patterns", "max_results": 4}}
    },
    {
        "user": "Search for Python dataclass usage examples.",
        "tool_call": {"name": "search_knowledge", "arguments": {"query": "Python dataclasses examples and best practices", "max_results": 5}}
    },
    {
        "user": "Find TypeScript generic type constraints documentation.",
        "tool_call": {"name": "search_knowledge", "arguments": {"query": "TypeScript generic constraints extends keyword", "max_results": 3}}
    },
    {
        "user": "Look up how to configure CORS in FastAPI.",
        "tool_call": {"name": "search_knowledge", "arguments": {"query": "FastAPI CORS middleware configuration", "max_results": 3}}
    },
]

NO_ACTION_EXAMPLES = [
    {
        "user": "Hello! How are you today?",
        "tool_call": {"name": "no_action", "arguments": {"summary": "Greeting — no tool needed, just a friendly response."}}
    },
    {
        "user": "What is the capital of France?",
        "tool_call": {"name": "no_action", "arguments": {"summary": "General knowledge question — answer with known facts, no tool needed."}}
    },
    {
        "user": "Thank you for your help!",
        "tool_call": {"name": "no_action", "arguments": {"summary": "Gratitude — no action required beyond acknowledgment."}}
    },
    {
        "user": "Can you explain what recursion is in programming?",
        "tool_call": {"name": "no_action", "arguments": {"summary": "Educational explanation — no tool execution needed, just provide clear explanation."}}
    },
    {
        "user": "What's the weather forecast for tomorrow?",
        "tool_call": {"name": "no_action", "arguments": {"summary": "Weather question — could use search but general answer is sufficient for demo."}}
    },
    {
        "user": "Tell me a joke about programming.",
        "tool_call": {"name": "no_action", "arguments": {"summary": "Entertainment — no tool needed, just respond with humor."}}
    },
    {
        "user": "Summarize the key points of functional programming.",
        "tool_call": {"name": "no_action", "arguments": {"summary": "Educational summary — no tool execution needed, provide concise explanation."}}
    },
    {
        "user": "What version of Python should I use for a new project in 2025?",
        "tool_call": {"name": "no_action", "arguments": {"summary": "Advice question — answer with recommendation, no tool needed."}}
    },
]


def _format_tool_response(tool_call):
    """Format the tool call as FunctionGemma's expected output format.
    
    FunctionGemma uses special format:
    <start_function_call>call:function_name{key<escape>value<escape>}<end_function_call>
    """
    args_parts = []
    for key, value in tool_call["arguments"].items():
        if value is None:
            continue
        if isinstance(value, int):
            args_parts.append(f"{key}{value}")
        else:
            args_parts.append(f"{key}{value}")
    # Actually FunctionGemma's output format uses Ollama's tool_calls format, not the raw text format
    # For SFT training, we train the assistant to output the tool call directly
    return json.dumps(tool_call)


def generate_dataset(num_each=25, seed=42):
    """Generate training examples covering all 4 tool schemas."""
    random.seed(seed)
    examples = []
    
    # Add all our hand-crafted examples
    all_categories = [
        ("write_file", WRITE_FILE_EXAMPLES),
        ("run_command", RUN_COMMAND_EXAMPLES),
        ("search_knowledge", SEARCH_KNOWLEDGE_EXAMPLES),
        ("no_action", NO_ACTION_EXAMPLES),
    ]
    
    for category, base_examples in all_categories:
        # Use all base examples, then generate more with variations
        for ex in base_examples:
            formatted = _format_user_msg(ex["user"], TOOLS)
            formatted["messages"].append({
                "role": "assistant",
                "content": _format_tool_response(ex["tool_call"])
            })
            examples.append(formatted)
        
        # Generate additional synthetic examples for categories with fewer samples
        current = len(base_examples)
        needed = num_each - current
        if needed > 0:
            for i in range(needed):
                # Use a template and vary it
                template = base_examples[i % len(base_examples)]
                if category == "write_file":
                    variations = [
                        f"Create a new {lang} file: {template['user'].split('Save')[0].strip()}. Save it as {path}."
                        for lang, path in [
                            ("Python", "src/utils/helper.py"),
                            ("JavaScript", "lib/format.js"),
                            ("TypeScript", "src/lib/types.ts"),
                            ("Go", "pkg/handler.go"),
                        ]
                    ]
                    user = variations[i % len(variations)]
                    ex = {"user": user, "tool_call": template["tool_call"]}
                elif category == "run_command":
                    prefixes = [
                        "Please run:", "Execute this command:", "Can you run this:", 
                        "I need to run:", "Run the following:"
                    ]
                    user = f"{prefixes[i % len(prefixes)]} {template['tool_call']['arguments']['command']}"
                    ex = {"user": user, "tool_call": template["tool_call"]}
                elif category == "search_knowledge":
                    prefixes = [
                        "Can you find information about:", "Search for:", "Look up:",
                        "I need information on:", "Find documentation for:"
                    ]
                    user = f"{prefixes[i % len(prefixes)]} {template['tool_call']['arguments']['query']}"
                    ex = {"user": user, "tool_call": template["tool_call"]}
                else:  # no_action
                    questions = [
                        "What's the difference between a list and a tuple?",
                        "Explain the concept of dependency injection.",
                        "How does garbage collection work?",
                        "What are the SOLID principles in OOP?",
                        "Can you explain what a monad is?",
                        "What's the difference between TCP and UDP?",
                    ]
                    user = questions[i % len(questions)]
                    ex = {"user": user, "tool_call": {"name": "no_action", "arguments": {"summary": "Educational question — answer with explanation, no tool needed."}}}
                
                formatted = _format_user_msg(ex["user"], TOOLS)
                formatted["messages"].append({
                    "role": "assistant",
                    "content": _format_tool_response(ex["tool_call"])
                })
                examples.append(formatted)
    
    random.shuffle(examples)
    print(f"Generated {len(examples)} training examples")
    print(f"  write_file: {sum(1 for e in examples if '\"write_file\"' in e['messages'][-1]['content'])}")
    print(f"  run_command: {sum(1 for e in examples if '\"run_command\"' in e['messages'][-1]['content'])}")
    print(f"  search_knowledge: {sum(1 for e in examples if '\"search_knowledge\"' in e['messages'][-1]['content'])}")
    print(f"  no_action: {sum(1 for e in examples if '\"no_action\"' in e['messages'][-1]['content'])}")
    return examples


# ─── Training ──────────────────────────────────────────────────────────

def train():
    print(f"\n{'=' * 60}")
    print("FUNCTIONGEMMA 270M FINE-TUNING")
    print(f"{'=' * 60}")
    print(f"Model: {MODEL_ID}")
    print(f"Output: {OUTPUT_DIR}")
    
    # Generate dataset
    print("\n[1/4] Generating training dataset...")
    examples = generate_dataset(num_each=25, seed=42)
    
    with open(DATASET_PATH, "w") as f:
        for ex in examples:
            f.write(json.dumps(ex) + "\n")
    print(f"  Saved {len(examples)} examples to {DATASET_PATH}")
    
    # Load model
    print(f"\n[2/4] Loading model: {MODEL_ID}")
    t0 = time.time()
    model = AutoModelForCausalLM.from_pretrained(
        MODEL_ID,
        torch_dtype=torch.bfloat16,
        device_map="auto",
        trust_remote_code=True,
    )
    processor = AutoProcessor.from_pretrained(MODEL_ID, trust_remote_code=True)
    
    # Ensure eos/pad tokens
    if processor.pad_token is None:
        processor.pad_token = processor.eos_token
    
    print(f"  Model loaded in {time.time() - t0:.1f}s")
    
    # Configure LoRA
    print("\n[3/4] Configuring LoRA (rank=16, alpha=32)...")
    lora_config = LoraConfig(
        task_type=TaskType.CAUSAL_LM,
        r=16,
        lora_alpha=32,
        lora_dropout=0.05,
        target_modules=["q_proj", "v_proj", "k_proj", "o_proj",
                        "gate_proj", "up_proj", "down_proj"],
        bias="none",
    )
    
    # Load dataset for training
    dataset = Dataset.from_json(str(DATASET_PATH))
    
    # Training args — optimized for RTX 3060 12GB
    training_args = TrainingArguments(
        output_dir=str(ADAPTER_DIR),
        per_device_train_batch_size=2,
        gradient_accumulation_steps=4,
        num_train_epochs=3,
        learning_rate=2e-4,
        warmup_ratio=0.1,
        logging_steps=10,
        save_strategy="epoch",
        bf16=True,
        report_to="none",
        remove_unused_columns=False,
        dataloader_num_workers=0,
        optim="adamw_8bit",
        gradient_checkpointing=True,
    )
    
    # SFT Trainer
    trainer = SFTTrainer(
        model=model,
        args=training_args,
        train_dataset=dataset,
        processing_class=processor,
        peft_config=lora_config,
    )
    
    print(f"\n[4/4] Training... (estimated 2-3 hours on RTX 3060 12GB)")
    t0 = time.time()
    trainer.train()
    elapsed = time.time() - t0
    print(f"\n  Training complete in {elapsed / 60:.1f} minutes")
    
    # Save adapter
    trainer.model.save_pretrained(ADAPTER_DIR)
    processor.save_pretrained(ADAPTER_DIR)
    print(f"\n  LoRA adapter saved to {ADAPTER_DIR}")
    
    return model, processor


# ─── Merge & Convert ───────────────────────────────────────────────────

def merge_and_save():
    """Merge LoRA weights and save full model."""
    print(f"\n{'=' * 60}")
    print("MERGING LORA ADAPTER")
    print(f"{'=' * 60}")
    
    if not ADAPTER_DIR.exists():
        print(f"ERROR: Adapter not found at {ADAPTER_DIR}")
        print("Run training first: python -m hlf_mcp.recursivemas.functiongemma_ft")
        return None
    
    # Load base model
    print(f"\n  Loading base model: {MODEL_ID}")
    model = AutoModelForCausalLM.from_pretrained(
        MODEL_ID,
        torch_dtype=torch.bfloat16,
        device_map="auto",
        trust_remote_code=True,
    )
    
    # Load and merge adapter
    print(f"  Loading adapter from {ADAPTER_DIR}")
    model = PeftModel.from_pretrained(model, ADAPTER_DIR)
    model = model.merge_and_unload()
    
    # Save merged model
    MERGED_DIR.mkdir(exist_ok=True)
    model.save_pretrained(MERGED_DIR)
    
    processor = AutoProcessor.from_pretrained(ADAPTER_DIR, trust_remote_code=True)
    processor.save_pretrained(MERGED_DIR)
    
    print(f"\n  Merged model saved to {MERGED_DIR}")
    print(f"  Ready for GGUF conversion or direct use")
    
    return model


def convert_to_gguf():
    """Convert merged model to GGUF format for Ollama."""
    print(f"\n{'=' * 60}")
    print("CONVERTING TO GGUF (for Ollama)")
    print(f"{'=' * 60}")
    
    if not MERGED_DIR.exists():
        print(f"ERROR: Merged model not found at {MERGED_DIR}")
        print("Run merge first: python -m hlf_mcp.recursivemas.functiongemma_ft")
        return False
    
    gguf_dir = OUTPUT_DIR / "gguf"
    gguf_dir.mkdir(exist_ok=True)
    output_path = gguf_dir / "functiongemma_swarmglass.gguf"
    
    # Try llama.cpp convert script; fall back to manual instructions
    import subprocess
    
    # Check for the official llama.cpp convert script
    convert_py = Path(os.environ.get("LLAMA_CPP_PYTHON", "")) / "convert_hf_to_gguf.py"
    if convert_py.exists():
        cmd = [
            sys.executable, str(convert_py),
            str(MERGED_DIR),
            "--outfile", str(output_path),
            "--outtype", "q8_0",
        ]
        print(f"  Running: {' '.join(cmd)}")
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            print(f"  GGUF saved to {output_path}")
            return True
        else:
            print(f"  Conversion failed: {result.stderr}")
            return False
    else:
        print("  llama.cpp convert script not found.")
        print(f"  Install with:")
        print(f"    pip install llama-cpp-python")
        print(f"  Then run:")
        print(f"    python -m llama_cpp.convert_hf_to_gguf {MERGED_DIR} --outfile {output_path} --outtype q8_0")
        print(f"\n  OR use Ollama directly:")
        print(f"    1. Copy merged model to Ollama models dir")
        print(f"    2. Create Modelfile with:")
        print(f"       FROM {MERGED_DIR}")
        print(f"    3. ollama create functiongemma-swarmglass -f Modelfile")
        return False


# ─── Main ──────────────────────────────────────────────────────────────

def main():
    import argparse
    p = argparse.ArgumentParser(description="FunctionGemma fine-tuning for SwarmGlass")
    p.add_argument("--only-merge", action="store_true", help="Skip training, only merge existing adapter")
    p.add_argument("--only-convert", action="store_true", help="Skip training and merge, only convert to GGUF")
    p.add_argument("--skip-convert", action="store_true", help="Skip GGUF conversion after merge")
    args = p.parse_args()
    
    if args.only_convert:
        convert_to_gguf()
        return
    
    if args.only_merge:
        merge_and_save()
        return
    
    # Full pipeline
    model, processor = train()
    merge_and_save()
    
    if not args.skip_convert:
        convert_to_gguf()
    
    print(f"\n{'=' * 60}")
    print("FUNCTIONGEMMA FINE-TUNING COMPLETE")
    print(f"{'=' * 60}")
    print(f"  Adapter: {ADAPTER_DIR}")
    print(f"  Merged:  {MERGED_DIR}")
    print(f"  Dataset: {DATASET_PATH}")
    print(f"\n  To use with Ollama:")
    print(f"    ollama create functiongemma-swarmglass -f Modelfile")
    print(f"\n  To test in Python:")
    print(f"    from transformers import AutoModelForCausalLM")
    print(f"    model = AutoModelForCausalLM.from_pretrained('{MERGED_DIR}')")


if __name__ == "__main__":
    main()
