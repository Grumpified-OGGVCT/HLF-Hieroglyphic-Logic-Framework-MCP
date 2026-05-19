# HLF Constraint Glossary v1.0 — Frozen at A+ (composite_score 1.0)

*Frozen: 2026-03-27 | Source: test-swarm-coord/test-7-hlf/swarm.hlf | 22-agent e-commerce swarm*

This is the **canonical constraint set** validated at the A+ quality tier with
deepseek-v4-pro:cloud. 22/22 agents complete, 0 errors, all 5 quality sub-scores
at 1.0 (cross_agent_consistency, app_correctness, migration_quality,
service_route_completeness, completion).

Future constraint changes MUST be staged in a new version. Do not modify this
file — add a CONSTRAINTS_V2.md and run the full battery before promoting.

---

## Architecture Constraints

*Applied via `architecture {}` block — these aren't agent constraints per se but
define the execution environment all agents must target.*

| Tag | Description |
|-----|-------------|
| `express` | Framework: Express.js |
| `node-18+` | Runtime: Node.js 18 or later |
| `postgresql` | Database: PostgreSQL |
| `knex` | Query builder: Knex.js |
| `jwt-bcrypt` | Auth: JWT with bcrypt |
| `commonjs` | Module system: CommonJS (`require`/`module.exports`) |
| `jest-supertest` | Test framework: Jest + Supertest |
| `factory-export` | Pattern: Factory function exports |
| `middleware-chain` | Pattern: Middleware chain |
| `error-first` | Pattern: Error-first callbacks |

---

## Cross-Cutting Constraints

*Inheritable constraints that apply to all agents in the swarm.*

| Tag | v1.0 Definition |
|-----|-----------------|
| **COMMONJS** | All files use `require` and `module.exports`. No ES module syntax. |
| **FACTORY-EXPORT** | Services export factory functions: `(knex) -> { methods }`. Every service file must export a callable factory. |
| **FACTORY-SERVICE** | Every service module exports a factory function `function(knex) -> { methods }`. All services (cartService, orderService, reviewService, etc.) follow this pattern identically. |
| **FACTORY-SIGNATURE** | Route modules export `function(services, auth, middleware) -> Router` with `.mount_path` property set. |
| **NULL-ON-MISSING** | `findById` returns `null` when the record doesn't exist — never throws, never returns `undefined`. |
| **NO-INSTALL** | Do NOT run `npm install`. Agents produce code, not runtime side effects. |
| **SLUG-GENERATION** | Entity names generate URL-safe slugs (lowercase, hyphenated, no special chars). |
| **STATUS-FSM** | Orders enforce valid status transitions: `pending→confirmed→shipped→delivered`. Cancellable ONLY from `pending` or `confirmed`. |
| **PURCHASE-VERIFY** | Reviews require verified purchase from a delivered order. Cannot review unpurchased products. |
| **JEST** | Tests use Jest test framework. |
| **SUPERTEST** | Tests use Supertest for HTTP assertions against the Express app. |
| **DESCRIBE-BLOCKS** | Every test file uses `describe()`/`it()` blocks with clear, descriptive test names. |
| **COVERS-CRUD** | Tests cover Create, Read, Update, Delete operations for the domain. |
| **ROLE-CHECKS** | Tests verify role-based access control (admin vs customer permissions). |
| **REUSABLE-HELPERS** | `tests/setup.js` exports reusable `setupTestDb()` and `createTestUser(app, overrides)` helpers. |

---

## Ownership Constraints

*Critical coordination constraints that prevent agent conflicts.*

| Tag | v1.0 Definition |
|-----|-----------------|
| **MIGRATION-OWNERSHIP** | ONLY `SchemaDesigner` creates migration files (`migrations/`). ALL other agents MUST NOT create files in the `migrations/` directory. |
| **ENTRY-POINT-OWNERSHIP** | ONLY `ConfigEngineer` creates `app.js`. `app.js` wires ALL routes and exports the Express app. |
| **NO-DUPLICATE-MIGRATIONS** | Migration sequence numbers `001-010` are RESERVED. Do not reuse any of these numbers. |
| **SEQUENTIAL-NUMBERS** | Migration files use sequential 3-digit prefixes: `001`, `002`, ..., `010`. |

---

## Naming Constraints

| Tag | v1.0 Definition |
|-----|-----------------|
| **NAMING-CONVENTION** | Route files use `*Routes.js` suffix (e.g., `cartRoutes.js`, `orderRoutes.js`). Each route file pairs with its service file. |
| **ROUTE-NAMING** | Every route file follows `*Routes.js` naming convention consistently. No deviations. |
| **IMPORT-PATHS** | `app.js` uses explicit require paths (e.g., `require('./services/auth')`, `require('./routes/auth')`). NO barrel imports without `index.js`. |

---

## SchemaDesigner Constraints

| Tag | v1.0 Definition |
|-----|-----------------|
| **SQL-VALID** | All SQL in migration files must be syntactically valid PostgreSQL. |
| **FK-CONSTRAINTS** | Foreign key constraints must be defined for all relationships. |
| **INDEXES-DEFINED** | Indexes must be defined on commonly queried columns. |
| **DOMAIN-COVERAGE** | SchemaDesigner MUST create a migration table for EVERY domain listed in `architecture.domains`. |

---

## ConfigEngineer Constraints

| Tag | v1.0 Definition |
|-----|-----------------|
| **NODE-18+** | All scripts and configuration must target Node.js 18+. |
| **PG-DB** | Knex configuration must target PostgreSQL. |
| **EXPRESS-WIRING** | `app.js` must wire all routes, middleware, and export the app. |
| **SECURITY-MIDDLEWARE** | `app.js` applies `helmet()`, `cors()`, and `express.json()` middleware BEFORE mounting routes. |
| **IMPORT-PATHS** | See cross-cutting above. |

---

## MiddlewareEngineer Constraints

| Tag | v1.0 Definition |
|-----|-----------------|
| **EXPRESS-MIDDLEWARE** | All middleware follows Express `(req, res, next)` signature. |
| **JSON-ERRORS** | Error responses are JSON objects with `{ error, status }` structure. |

---

## AuthService Constraints

| Tag | v1.0 Definition |
|-----|-----------------|
| **JWT-SECRET-ENV** | JWT secret read from `process.env.JWT_SECRET`. |
| **BCRYPTJS** | Password hashing uses bcryptjs library. |
| **ROLE-AWARE** | Auth middleware supports role-based access: `authenticate`, `optionalAuth`, `requireRole(roles)`. |

---

## Test Agent Constraints

| Tag | v1.0 Definition |
|-----|-----------------|
| **JEST** | See cross-cutting above. |
| **SUPERTEST** | See cross-cutting above. |
| **COVERS-CRUD** | See cross-cutting above. |
| **COMMONJS** | See cross-cutting above. |
| **ROLE-CHECKS** | See cross-cutting above. |
| **DESCRIBE-BLOCKS** | See cross-cutting above. |
| **PURCHASE-VERIFY** | See cross-cutting above. |

---

## Effect System

*Not constraints per se, but the effect lines define explicit READ/WRITE
dependencies that enforce the constraint mesh.*

Layer 1 agents (`SchemaDesigner`, `ConfigEngineer`, `MiddlewareEngineer`) have
no read dependencies — they generate from architecture alone.

Layer 2 agents (all 10 service agents) read `migrations/` and write their
`services/*.js` and `routes/*.js`.

Layer 3 agents (all 9 test agents) read the output of layers 1-2 and write
`tests/*.test.js`.

The effect graph is what makes "inconsistency harder than consistency" — every
agent's output shape is pre-declared, and downstream agents read upstream
output, creating a self-validating coordination mesh.

---

## Constraint Inheritance Rules

1. Cross-cutting constraints apply UNLESS explicitly overridden.
2. Agent-specific constraints ADD to cross-cutting, never replace them.
3. Ownership constraints are non-negotiable — violating one breaks the mesh.
4. The `no_create` field prevents agents from writing to owned directories
   even if the model hallucinates doing so.

---

## Validation Score (v1.0, deepseek-v4-pro:cloud)

| Dimension | Score | Weight |
|-----------|-------|--------|
| completion | 1.0 | 0.15 |
| app_correctness | 1.0 | 0.25 |
| migration_quality | 1.0 | 0.20 |
| service_route_completeness | 1.0 | 0.20 |
| cross_agent_consistency | 1.0 | 0.20 |
| **composite** | **1.0** | — |

*22/22 agents, 50 files, 131,438 tokens, 389s wall time.*
