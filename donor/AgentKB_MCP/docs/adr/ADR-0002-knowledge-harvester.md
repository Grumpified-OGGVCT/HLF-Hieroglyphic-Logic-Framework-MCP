# ADR-0002: Proactive Knowledge Harvester

## Status
**Proposed** - Not yet implemented

## Context
The current system is **reactive**: it only researches when a user query misses. The user requests a **proactive** component that:

1. Continuously monitors official documentation sources
2. Detects new/changed content
3. Automatically generates KB entries
4. Submits to human review queue

## Decision

### Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    KNOWLEDGE HARVESTER                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐      │
│  │   Source     │    │   Change     │    │   Entry      │      │
│  │   Registry   │───▶│   Detector   │───▶│   Generator  │      │
│  └──────────────┘    └──────────────┘    └──────────────┘      │
│         │                   │                   │               │
│         ▼                   ▼                   ▼               │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐      │
│  │  Official    │    │   Content    │    │   Staging    │      │
│  │  Doc URLs    │    │   Hashes     │    │   KB Files   │      │
│  └──────────────┘    └──────────────┘    └──────────────┘      │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
                    ┌──────────────────┐
                    │   Human Review   │
                    │   (git diff)     │
                    └──────────────────┘
                              │
                              ▼
                    ┌──────────────────┐
                    │   Production KB  │
                    └──────────────────┘
```

### Components

#### 1. Source Registry (`sources.yaml`)
A curated list of official documentation URLs to monitor:

```yaml
domains:
  postgresql:
    name: "PostgreSQL"
    sources:
      - url: "https://www.postgresql.org/docs/current/release.html"
        type: "release_notes"
        check_interval: "daily"
      - url: "https://www.postgresql.org/docs/current/config-setting.html"
        type: "configuration"
        check_interval: "weekly"
    
  nextjs:
    name: "Next.js"
    sources:
      - url: "https://nextjs.org/docs/app/api-reference"
        type: "api_reference"
        check_interval: "daily"
      - url: "https://github.com/vercel/next.js/releases.atom"
        type: "rss_feed"
        check_interval: "hourly"
    
  python:
    name: "Python"
    sources:
      - url: "https://docs.python.org/3/whatsnew/"
        type: "changelog"
        check_interval: "weekly"
```

#### 2. Change Detector
- Fetches each source URL on schedule
- Computes content hash (SHA-256)
- Compares against stored hash in DB
- If changed, extracts diff and queues for processing

#### 3. Entry Generator
- Uses Gemini to analyze the changed content
- Identifies discrete Q&A candidates
- Generates entries in canonical format
- Writes to `./kb_staging/{domain}-harvested.md`

#### 4. Deduplication Check
- Before writing, checks if similar question already exists in production KB
- Uses semantic similarity (embedding cosine distance)
- Skips if duplicate detected

### Scheduling Options

| Approach | Pros | Cons |
|----------|------|------|
| **Cron job** | Simple, predictable | Requires always-on server |
| **GitHub Actions** | Free, runs on schedule | Limited minutes (2000/month free) |
| **Cloud Scheduler** | Scalable, reliable | Adds cost |
| **Manual trigger** | No cost, full control | Requires human to run |

### Cost Estimate (per domain, per week)

| Operation | Calls | Cost |
|-----------|-------|------|
| Fetch source pages | ~10 | Free |
| Gemini analysis | ~5 | ~$0.05 |
| Embedding checks | ~20 | ~$0.01 |
| **Total per domain** | | **~$0.06/week** |

For 10 domains: ~$0.60/week, ~$2.50/month

## Consequences

### Positive
- KB grows without user queries
- Catches breaking changes early
- Reduces "first user pays latency" problem
- Creates comprehensive coverage

### Negative
- More human review burden
- Risk of generating low-value entries
- Ongoing API costs (though minimal)
- Need to curate source list carefully

### Risks
- **Noise**: Harvester might generate obvious/useless entries
- **Mitigation**: Strict prompts, confidence thresholds, human review

- **Source drift**: Official docs change structure, breaking parser
- **Mitigation**: Robust error handling, alerts on parse failures

## Implementation Estimate

| Component | Effort |
|-----------|--------|
| Source Registry + Schema | 2 hours |
| Change Detector | 4 hours |
| Entry Generator | 4 hours |
| Dedup Check | 2 hours |
| CLI runner | 2 hours |
| GitHub Actions workflow | 1 hour |
| **Total** | **~15 hours** |

## Decision

**Defer until core system is validated.** The reactive system must work reliably first. The harvester can be added as a Phase 2 enhancement.

## Notes

This ADR documents the concept for future implementation. It is NOT part of the current build.

