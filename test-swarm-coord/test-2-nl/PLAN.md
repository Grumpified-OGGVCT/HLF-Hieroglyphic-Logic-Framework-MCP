# Natural Language Swarm: 10-Agent API Build

## Task: Build a Complete Task Management REST API

**Tech Stack:** Node.js + Express + PostgreSQL + Knex.js + JWT
**Goal:** Working API with migrations, models, auth, CRUD endpoints, validation, error handling, and integration tests.

---

## Agent Instructions

### Agent 1: SchemaDesigner
Design the PostgreSQL schema for a task management app.

**Tables needed:**
- `users` (id, username, email, password_hash, created_at, updated_at)
- `projects` (id, name, description, owner_id → users.id, created_at, updated_at)
- `tasks` (id, title, description, status [todo|in_progress|done], priority [low|medium|high], project_id → projects.id, assignee_id → users.id, created_at, updated_at)
- `labels` (id, name, color, created_at)
- `task_labels` (task_id, label_id) - junction table
- `comments` (id, task_id → tasks.id, user_id → users.id, content, created_at)

**Write to:** `migrations/001_initial_schema.js` (Knex migration format)
**Also create:** `schema.sql` as plain SQL reference

### Agent 2: ModelBuilder
Build Knex.js model files for each table.

**Input:** Read `migrations/001_initial_schema.js` and `schema.sql`
**Write to:** `models/User.js`, `models/Task.js`, `models/Project.js`, `models/Label.js`, `models/Comment.js`

**Each model must:**
- Export CRUD methods: create(data), findById(id), findAll(filters), update(id, data), delete(id)
- Handle the relationships (e.g., Task model can fetch its project, comments, labels)
- Use Knex query builder

### Agent 3: AuthEngineer
Build JWT authentication middleware.

**Write to:** `middleware/auth.js`
**Must include:**
- `register(req, res)` - bcrypt hash password, insert user, return JWT
- `login(req, res)` - verify credentials, return JWT + refresh token
- `authenticate(req, res, next)` - verify JWT from Authorization header
- `refresh(req, res)` - refresh access token
- All functions use the User model from `models/User.js`

### Agent 4: ValidationLayer
Create input validation schemas.

**Write to:** `validation/user.js`, `validation/task.js`, `validation/project.js`
**Use:** A lightweight validation approach (can be simple functions or Joi-style objects)
**Must validate:**
- User: username (3-30 chars), email (valid format), password (min 8 chars)
- Task: title (1-200 chars), status enum, priority enum
- Project: name (1-100 chars)

### Agent 5: TaskEndpoints
Build task CRUD routes.

**Input:** `models/Task.js`, `middleware/auth.js`, `validation/task.js`
**Write to:** `routes/tasks.js`
**Endpoints:**
- GET /tasks (with query filters: status, priority, project_id, assignee_id)
- GET /tasks/:id
- POST /tasks (auth required)
- PUT /tasks/:id (auth required)
- DELETE /tasks/:id (auth required)

### Agent 6: ProjectEndpoints
Build project CRUD routes.

**Input:** `models/Project.js`, `middleware/auth.js`, `validation/project.js`
**Write to:** `routes/projects.js`
**Endpoints:**
- GET /projects
- GET /projects/:id
- POST /projects (auth required)
- PUT /projects/:id (auth required)
- DELETE /projects/:id (auth required)

### Agent 7: UserEndpoints
Build user management routes.

**Input:** `models/User.js`, `middleware/auth.js`, `validation/user.js`
**Write to:** `routes/users.js`
**Endpoints:**
- GET /users/:id (public profile)
- GET /users/:id/tasks (all tasks assigned to user)
- PUT /users/:id (auth required, own profile only)

### Agent 8: ErrorHandler
Build centralized error handling middleware.

**Input:** All routes from `routes/`
**Write to:** `middleware/error.js`
**Must:**
- Catch all errors
- Return JSON: `{ error: string, status: number, timestamp: ISO string }`
- Handle 404, 400, 401, 403, 500
- Log errors to console with stack trace in development

### Agent 9: IntegrationTester
Write integration tests.

**Input:** All routes, models, middleware
**Write to:** `tests/api.test.js`
**Must test:**
- Auth: register, login, access protected route
- Tasks: CRUD operations
- Projects: CRUD operations
- Users: profile retrieval
- Error handling: 404, 400, 401 responses
**Use:** supertest + jest

### Agent 10: ProjectAssembler
Create the entry point and configuration files.

**Input:** All files produced by other agents
**Write to:**
- `server.js` - Express app, register all routes, apply middleware
- `package.json` - dependencies: express, knex, pg, bcryptjs, jsonwebtoken, supertest, jest, dotenv
- `knexfile.js` - Knex configuration
- `.env.example` - environment variables template

---

## Critical Rules
1. Every agent MUST read files from agents they depend on
2. Every agent MUST write to their assigned files only
3. If you find a bug in another agent's code, document it in BUGS.md and work around it
4. Use CommonJS (require/module.exports) for compatibility
5. Do NOT install packages - just write the code

---

## Execution Order
1. Agent 1 (SchemaDesigner) - no dependencies
2. Agent 4 (ValidationLayer) - no dependencies (can run with Agent 1)
3. Agent 2 (ModelBuilder) - depends on Agent 1
4. Agent 3 (AuthEngineer) - depends on Agent 2
5. Agents 5, 6, 7 (Endpoints) - depend on Agents 2, 3, 4
6. Agent 8 (ErrorHandler) - depends on Agents 5, 6, 7
7. Agent 9 (IntegrationTester) - depends on ALL
8. Agent 10 (ProjectAssembler) - depends on ALL
