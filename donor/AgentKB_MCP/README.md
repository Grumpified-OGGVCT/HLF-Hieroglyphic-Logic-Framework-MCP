# Verified Developer KB Pro

A production-grade, self-expanding developer knowledge base that provides instant, grounded, high-confidence answers.

## 🎯 Features

- **Instant Retrieval**: Pre-researched answers in < 1s
- **Strict Grounding**: Answers only from curated KB content (no hallucination)
- **Self-Expanding**: Misses are queued, researched from official sources, and added back
- **Version-Aware**: Handles versioned documentation (e.g., PostgreSQL 16 vs 15)
- **Confidence Scoring**: Every answer includes a 0.00-1.00 confidence score
- **Lockfiles**: SHA-256 hashes for reproducible builds
- **Stack Packs**: Curated entry collections for specific tech stacks

## 📁 Project Structure

```
├── app/                    # FastAPI application
│   ├── api/               # API endpoints
│   ├── db/                # Database models and connection
│   ├── models/            # Pydantic request/response models
│   ├── services/          # Business logic services
│   ├── main.py            # Application entry point
│   ├── worker.py          # Research worker
│   ├── monitoring.py      # Metrics and health checks
│   └── config.py          # Configuration management
├── tools/                  # CLI tools
│   ├── validate_kb.py     # KB validation
│   ├── promote_staging.py # Staging to production promotion
│   ├── generate_lock.py   # Lockfile generation
│   └── verify_lock.py     # Lockfile verification
├── prompts/               # System prompts (sacrosanct)
│   ├── kb_model.xml       # KB model prompt
│   └── research_model.xml # Research agent prompt
├── kb_files/              # Production KB (read-only)
├── kb_staging/            # Staging KB (pending review)
├── stack_packs/           # Stack pack manifests
├── locks/                 # Lockfiles
├── tests/                 # Test suite
├── evaluation/            # Golden dataset
└── docker-compose.yml     # Local development
```

## 🚀 Quick Start

### Prerequisites

- Python 3.11+
- PostgreSQL with pgvector extension
- Redis
- Google Gemini API key

### Local Development

1. **Clone and setup:**
   ```bash
   git clone <your-repo>
   cd verified-kb-pro
   cp env.example .env
   # Edit .env with your API keys
   ```

2. **Start services with Docker:**
   ```bash
   docker-compose up -d postgres redis
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Run the API:**
   ```bash
   uvicorn app.main:app --reload
   ```

5. **Run the worker (separate terminal):**
   ```bash
   python -m app.worker
   ```

### Full Docker Setup

```bash
# Start everything
docker-compose up -d

# View logs
docker-compose logs -f api worker

# Stop
docker-compose down
```

## 📡 API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | API info |
| GET | `/health` | Health check |
| GET | `/stats` | KB statistics |
| POST | `/ask` | Ask a question |
| POST | `/ask-batch` | Batch questions |
| GET | `/search` | Search KB |
| POST | `/lock` | Generate lockfile |
| POST | `/verify-lock` | Verify lockfile |
| GET | `/queue-status` | Queue status |

### Example Request

```bash
curl -X POST http://localhost:8000/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "What is the default max_connections in PostgreSQL 16?"}'
```

### Example Response

```json
{
  "question": "What is the default max_connections in PostgreSQL 16?",
  "answer": "The default value for max_connections in PostgreSQL 16 is 100...",
  "confidence": 0.98,
  "tier": "GOLD",
  "sources": ["https://www.postgresql.org/docs/16/runtime-config-connection.html"],
  "related_questions": ["How do I increase max_connections?"],
  "cache_hit": false,
  "entry_id": "postgresql-max-connections-default-0001"
}
```

## 🛠️ CLI Tools

```bash
# Validate KB files
python -m tools.validate_kb --path ./kb_files

# Promote staging to production
python -m tools.promote_staging --staging ./kb_staging --production ./kb_files

# Generate lockfile
python -m tools.generate_lock --kb ./kb_files --out ./locks/lockfile.json

# Verify lockfile
python -m tools.verify_lock --lockfile ./locks/lockfile.json --kb ./kb_files
```

## 📝 Adding Knowledge

### Manual Entry

1. Create/edit a file in `./kb_files/{domain}.md`
2. Follow the exact template format
3. Run validation: `python -m tools.validate_kb`

### Research Queue

1. Questions with confidence < 0.80 are queued
2. Worker researches from official sources
3. New entries go to `./kb_staging/{domain}-pending.md`
4. Human reviews and promotes to production

## 🚢 Deployment (Railway)

1. Create a Railway account
2. Connect your GitHub repo
3. Add PostgreSQL and Redis services
4. Set environment variables
5. Deploy automatically on push

See `railway.json` for configuration.

## 📊 Monitoring

- **Prometheus metrics**: `/metrics`
- **Structured logging**: JSON format in production
- **Health checks**: `/health` includes all service statuses

## 🧪 Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=app --cov-report=html

# Run specific test
pytest tests/test_kb_parser.py -v
```

## 📄 License

Private - All Rights Reserved

## 🤝 Contributing

See SINGLE_SOURCE_OF_TRUTH.md for the complete system specification.
