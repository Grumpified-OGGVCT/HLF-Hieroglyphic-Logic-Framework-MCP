# Test 2: Large-Scale Multi-Agent API Build (10 Agents)
## Goal: Verify if HLF interfaces amortize across 10+ agent boundaries

---

## Task: Build a Complete Task Management REST API

**Tech Stack:** Node.js + Express + PostgreSQL + Knex.js + JWT Auth
**Agents:** 10 specialized agents
**Output:** Working API with tests, migrations, models, auth, docs

---

## Agent Architecture

### Layer 1: Foundation (Parallel)
| # | Agent | Role | Output | Downstream Consumers |
|---|-------|------|--------|---------------------|
| 1 | SchemaDesigner | PostgreSQL schema | schema.sql | Agent 2, Agent 3 |
| 2 | MigrationWriter | Knex migrations | migrations/ | Agent 3 |

### Layer 2: Core (Parallel, depends on Layer 1)
| # | Agent | Role | Output | Downstream Consumers |
|---|-------|------|--------|---------------------|
| 3 | ModelBuilder | ORM models | models/ | Agents 4,5,6,7 |
| 4 | AuthEngineer | JWT auth middleware | middleware/auth.js | Agents 5,6,7 |

### Layer 3: Features (Parallel, depends on Layer 2)
| # | Agent | Role | Output | Downstream Consumers |
|---|-------|------|--------|---------------------|
| 5 | TaskEndpoints | Task CRUD API | routes/tasks.js | Agent 9 |
| 6 | ProjectEndpoints | Project CRUD API | routes/projects.js | Agent 9 |
| 7 | UserEndpoints | User management | routes/users.js | Agent 9 |
| 8 | ValidationLayer | Input validation | validation/ | Agents 5,6,7 |

### Layer 4: Integration (Parallel, depends on Layer 3)
| # | Agent | Role | Output | Downstream Consumers |
|---|-------|------|--------|---------------------|
| 9 | ErrorHandler | Centralized errors | middleware/error.js | Agent 10 |
| 10 | IntegrationTester | Full test suite | tests/ | Final report |

---

## Interfaces (HLF Version Only)

```
interface SchemaDesigner {
  input: none
  output: schema.sql (tables, constraints, indexes)
  constraints: [SQL-VALID, RELATIONS-DEFINED]
}

interface ModelBuilder {
  input: schema.sql, migrations/
  output: models/*.js (User, Task, Project, Label, Comment)
  constraints: [KNEX-COMPATIBLE, RELATIONS-MATCH-SCHEMA]
}

interface AuthEngineer {
  input: none
  output: middleware/auth.js (JWT verify, bcrypt, refresh)
  constraints: [EXPRESS-MIDDLEWARE, JWT-SECRET-ENV]
}

interface TaskEndpoints {
  input: models/Task.js, middleware/auth.js, validation/task.js
  output: routes/tasks.js (GET/POST/PUT/DELETE /tasks, /tasks/:id)
  constraints: [RESTFUL, AUTH-GUARDED, VALIDATED]
}

interface IntegrationTester {
  input: ALL routes, models, middleware
  output: tests/*.test.js (integration tests with supertest)
  constraints: [COVERS-ALL-ENDPOINTS, MOCKS-AUTH, ASSERTS-STATUS]
}
```

---

## Why This Tests HLF's Value

1. **Interface count:** 10 agents × avg 2.5 consumers = ~25 interface boundaries
2. **NL coordination cost:** Each agent needs to understand 2-4 other agents' outputs via PLAN.md prose
3. **HLF coordination cost:** Fixed interface declarations, consumed automatically
4. **Amortization hypothesis:** If HLF's per-interface cost is constant but NL's grows with agent count, HLF wins at 10+ agents

---

## Execution Strategy

### Natural Language Swarm (Trial 1)
- Write one PLAN.md describing all 10 agents and their relationships
- Launch agents in dependency batches
- Measure: PLAN.md size, total output, test results, cross-agent bugs

### HLF Swarm (Trial 1)
- Write swarm.hlf with all interfaces, agent declarations, effects
- Launch agents with HLF context
- Measure: swarm.hlf size, total output, test results, traceability

### Compare:
1. Coordination bytes per interface boundary
2. Cross-agent bug count
3. Test pass rate
4. Time to completion
5. Whether the final API actually works end-to-end

---

## Project Structure

```
test-large-api/
├── package.json
├── .env.example
├── knexfile.js
├── server.js
├── migrations/
├── models/
│   ├── User.js
│   ├── Task.js
│   ├── Project.js
│   ├── Label.js
│   └── Comment.js
├── routes/
│   ├── tasks.js
│   ├── projects.js
│   └── users.js
├── middleware/
│   ├── auth.js
│   └── error.js
├── validation/
│   ├── task.js
│   ├── project.js
│   └── user.js
└── tests/
    └── api.test.js
```

---

## Success Criteria
1. All 10 agents produce output
2. Tests pass (integration tests actually test the API)
3. No cross-agent type mismatches in HLF version
4. Can trace which agent wrote which file
5. API can start with `npm start` (structurally correct)

---

## Risk Mitigation
- If an agent fails, document what happened and retry
- If dependencies are circular, break them with interfaces
- If tests fail, attribute failures to specific agent outputs
