const request = require('supertest');
const express = require('express');
const jwt = require('jsonwebtoken');

// Route factories
const taskRoutes = require('../routes/tasks');
const projectRoutes = require('../routes/projects');
const userRoutes = require('../routes/users');

// Middleware factories
const authFactory = require('../middleware/auth');
const errorFactory = require('../middleware/error');

// Validation modules
const userValidation = require('../validation/user');
const taskValidation = require('../validation/task');
const projectValidation = require('../validation/project');

const JWT_SECRET = 'dev-secret-change-in-production';

// ---------------------------------------------------------------------------
// In-memory mock data stores
// ---------------------------------------------------------------------------
let users = [];
let tasks = [];
let projects = [];

// ---------------------------------------------------------------------------
// Mock Models
// ---------------------------------------------------------------------------
const mockUserModel = {
  async create(data) {
    const id = String(users.length + 1);
    const user = { id, ...data, created_at: new Date().toISOString(), updated_at: new Date().toISOString() };
    users.push(user);
    return this.findById(id);
  },

  async findById(id) {
    const user = users.find((u) => String(u.id) === String(id));
    if (!user) return null;
    const { password_hash, ...publicUser } = user;
    return publicUser;
  },

  async findByEmail(email) {
    return users.find((u) => u.email === email) || null;
  },

  async findAll() {
    return users.map((u) => {
      const { password_hash, ...rest } = u;
      return rest;
    });
  },

  async update(id, data) {
    const idx = users.findIndex((u) => String(u.id) === String(id));
    if (idx === -1) return null;
    users[idx] = { ...users[idx], ...data, updated_at: new Date().toISOString() };
    return this.findById(id);
  },

  async delete(id) {
    const idx = users.findIndex((u) => String(u.id) === String(id));
    if (idx === -1) return 0;
    users.splice(idx, 1);
    return 1;
  }
};

const mockTaskModel = {
  async create(data) {
    const id = String(tasks.length + 1);
    const task = {
      id,
      ...data,
      status: data.status || 'todo',
      priority: data.priority || 'medium',
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString()
    };
    tasks.push(task);
    return this.findById(id);
  },

  async findById(id) {
    const task = tasks.find((t) => String(t.id) === String(id));
    if (!task) return null;
    const project = projects.find((p) => String(p.id) === String(task.project_id));
    const assignee = users.find((u) => String(u.id) === String(task.assignee_id));
    return {
      ...task,
      project_name: project ? project.name : null,
      assignee_username: assignee ? assignee.username : null,
      labels: []
    };
  },

  async findAll(filters = {}) {
    let result = tasks.map((t) => {
      const project = projects.find((p) => String(p.id) === String(t.project_id));
      const assignee = users.find((u) => String(u.id) === String(t.assignee_id));
      return {
        ...t,
        project_name: project ? project.name : null,
        assignee_username: assignee ? assignee.username : null,
        labels: []
      };
    });
    if (filters.status) result = result.filter((t) => t.status === filters.status);
    if (filters.priority) result = result.filter((t) => t.priority === filters.priority);
    if (filters.project_id) result = result.filter((t) => String(t.project_id) === String(filters.project_id));
    if (filters.assignee_id) result = result.filter((t) => String(t.assignee_id) === String(filters.assignee_id));
    return result;
  },

  async update(id, data) {
    const idx = tasks.findIndex((t) => String(t.id) === String(id));
    if (idx === -1) return null;
    tasks[idx] = { ...tasks[idx], ...data, updated_at: new Date().toISOString() };
    return this.findById(id);
  },

  async delete(id) {
    const idx = tasks.findIndex((t) => String(t.id) === String(id));
    if (idx === -1) return 0;
    tasks.splice(idx, 1);
    return 1;
  },

  async findByProject(projectId) {
    return tasks
      .filter((t) => String(t.project_id) === String(projectId))
      .map((t) => ({ ...t, labels: [] }));
  },

  async findByAssignee(userId) {
    return tasks
      .filter((t) => String(t.assignee_id) === String(userId))
      .map((t) => ({ ...t, labels: [] }));
  },

  async addLabel() {
    return [];
  },

  async removeLabel() {
    return [];
  },

  async getLabels() {
    return [];
  },

  async getComments() {
    return [];
  }
};

const mockProjectModel = {
  async create(data) {
    const id = String(projects.length + 1);
    const project = {
      id,
      ...data,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString()
    };
    projects.push(project);
    return this.findById(id);
  },

  async findById(id) {
    const project = projects.find((p) => String(p.id) === String(id));
    if (!project) return null;
    const owner = users.find((u) => String(u.id) === String(project.owner_id));
    return {
      ...project,
      owner_username: owner ? owner.username : null
    };
  },

  async findAll(filters = {}) {
    let result = projects.map((p) => {
      const owner = users.find((u) => String(u.id) === String(p.owner_id));
      return { ...p, owner_username: owner ? owner.username : null };
    });
    if (filters.name) result = result.filter((p) => p.name.includes(filters.name));
    if (filters.owner_id) result = result.filter((p) => String(p.owner_id) === String(filters.owner_id));
    return result;
  },

  async update(id, data) {
    const idx = projects.findIndex((p) => String(p.id) === String(id));
    if (idx === -1) return null;
    projects[idx] = { ...projects[idx], ...data, updated_at: new Date().toISOString() };
    return this.findById(id);
  },

  async delete(id) {
    const idx = projects.findIndex((p) => String(p.id) === String(id));
    if (idx === -1) return 0;
    projects.splice(idx, 1);
    return 1;
  }
};

const mockModels = {
  User: mockUserModel,
  Task: mockTaskModel,
  Project: mockProjectModel
};

const validation = {
  validateUser: userValidation.validateUser,
  validateUserUpdate: userValidation.validateUserUpdate,
  validateTask: taskValidation.validateTask,
  validateTaskUpdate: taskValidation.validateTaskUpdate,
  validateTaskFilters: taskValidation.validateTaskFilters,
  validateProject: projectValidation.validateProject,
  validateProjectUpdate: projectValidation.validateProjectUpdate
};

// ---------------------------------------------------------------------------
// Build test Express app with mocked dependencies
// ---------------------------------------------------------------------------
const auth = authFactory(mockModels);
const { errorHandler, notFoundHandler } = errorFactory();

const app = express();
app.use(express.json());
app.use('/tasks', taskRoutes(mockModels, auth, validation));
app.use('/projects', projectRoutes(mockModels, auth, validation));
app.use('/', userRoutes(mockModels, auth, validation));
app.use(notFoundHandler);
app.use(errorHandler);

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------
function generateToken(user) {
  return jwt.sign(
    { userId: user.id, username: user.username, email: user.email },
    JWT_SECRET,
    { expiresIn: '24h' }
  );
}

function generateRefreshToken(user) {
  return jwt.sign(
    { userId: user.id, type: 'refresh' },
    JWT_SECRET,
    { expiresIn: '7d' }
  );
}

function getAuthHeader(user) {
  return `Bearer ${generateToken(user)}`;
}

// ---------------------------------------------------------------------------
// Test Suite
// ---------------------------------------------------------------------------
describe('Task Management API Integration Tests', () => {
  beforeEach(() => {
    users = [];
    tasks = [];
    projects = [];
  });

  // ========================================================================
  // Auth Tests
  // ========================================================================
  describe('Auth Endpoints', () => {
    describe('POST /auth/register', () => {
      it('creates a new user and returns 201 with token', async () => {
        const res = await request(app)
          .post('/auth/register')
          .send({
            username: 'testuser',
            email: 'test@example.com',
            password: 'password123'
          });

        expect(res.status).toBe(201);
        expect(res.body).toHaveProperty('token');
        expect(res.body).toHaveProperty('refreshToken');
        expect(res.body).toHaveProperty('user');
        expect(res.body.user).toHaveProperty('id');
        expect(res.body.user.username).toBe('testuser');
        expect(res.body.user.email).toBe('test@example.com');
        expect(res.body.user).not.toHaveProperty('password_hash');
      });

      it('returns 409 for duplicate email', async () => {
        await request(app)
          .post('/auth/register')
          .send({
            username: 'testuser',
            email: 'test@example.com',
            password: 'password123'
          });

        const res = await request(app)
          .post('/auth/register')
          .send({
            username: 'testuser2',
            email: 'test@example.com',
            password: 'password123'
          });

        expect(res.status).toBe(409);
        expect(res.body.error).toMatch(/already exists/i);
      });
    });

    describe('POST /auth/login', () => {
      it('returns 200 with token for valid credentials', async () => {
        await request(app)
          .post('/auth/register')
          .send({
            username: 'testuser',
            email: 'test@example.com',
            password: 'password123'
          });

        const res = await request(app)
          .post('/auth/login')
          .send({
            email: 'test@example.com',
            password: 'password123'
          });

        expect(res.status).toBe(200);
        expect(res.body).toHaveProperty('token');
        expect(res.body).toHaveProperty('refreshToken');
        expect(res.body).toHaveProperty('user');
      });

      it('returns 401 for invalid credentials', async () => {
        await request(app)
          .post('/auth/register')
          .send({
            username: 'testuser',
            email: 'test@example.com',
            password: 'password123'
          });

        const res = await request(app)
          .post('/auth/login')
          .send({
            email: 'test@example.com',
            password: 'wrongpassword'
          });

        expect(res.status).toBe(401);
        expect(res.body.error).toMatch(/invalid credentials/i);
      });
    });

    describe('POST /auth/refresh', () => {
      it('returns new token pair for valid refresh token', async () => {
        const regRes = await request(app)
          .post('/auth/register')
          .send({
            username: 'testuser',
            email: 'test@example.com',
            password: 'password123'
          });

        const refreshToken = regRes.body.refreshToken;

        const res = await request(app)
          .post('/auth/refresh')
          .send({ refreshToken });

        expect(res.status).toBe(200);
        expect(res.body).toHaveProperty('token');
        expect(res.body).toHaveProperty('refreshToken');
        expect(res.body.token).not.toBe(regRes.body.token);
      });
    });
  });

  // ========================================================================
  // Task Tests
  // ========================================================================
  describe('Task Endpoints', () => {
    let testUser;
    let authHeader;

    beforeEach(async () => {
      const regRes = await request(app)
        .post('/auth/register')
        .send({
          username: 'taskuser',
          email: 'task@example.com',
          password: 'password123'
        });
      testUser = regRes.body.user;
      authHeader = getAuthHeader(testUser);
    });

    it('GET /tasks returns 200 with array (public)', async () => {
      const res = await request(app).get('/tasks');
      expect(res.status).toBe(200);
      expect(Array.isArray(res.body)).toBe(true);
    });

    it('GET /tasks/:id returns 200 with task', async () => {
      const createRes = await request(app)
        .post('/tasks')
        .set('Authorization', authHeader)
        .send({
          title: 'Test Task',
          status: 'todo',
          priority: 'medium'
        });

      const taskId = createRes.body.id;
      const res = await request(app).get(`/tasks/${taskId}`);

      expect(res.status).toBe(200);
      expect(res.body).toHaveProperty('id', taskId);
      expect(res.body).toHaveProperty('title', 'Test Task');
    });

    it('GET /tasks/:id returns 404 for non-existent task', async () => {
      const res = await request(app).get('/tasks/9999');
      expect(res.status).toBe(404);
      expect(res.body.error).toMatch(/not found/i);
    });

    it('POST /tasks without auth returns 401', async () => {
      const res = await request(app)
        .post('/tasks')
        .send({
          title: 'Test Task',
          status: 'todo',
          priority: 'medium'
        });
      expect(res.status).toBe(401);
    });

    it('POST /tasks with auth returns 201', async () => {
      const res = await request(app)
        .post('/tasks')
        .set('Authorization', authHeader)
        .send({
          title: 'New Task',
          status: 'in_progress',
          priority: 'high'
        });

      expect(res.status).toBe(201);
      expect(res.body).toHaveProperty('id');
      expect(res.body.title).toBe('New Task');
      expect(res.body.status).toBe('in_progress');
      expect(res.body.priority).toBe('high');
    });

    it('PUT /tasks/:id with auth updates task', async () => {
      const createRes = await request(app)
        .post('/tasks')
        .set('Authorization', authHeader)
        .send({
          title: 'Original Title',
          status: 'todo',
          priority: 'medium'
        });

      const taskId = createRes.body.id;
      const res = await request(app)
        .put(`/tasks/${taskId}`)
        .set('Authorization', authHeader)
        .send({
          title: 'Updated Title',
          status: 'done'
        });

      expect(res.status).toBe(200);
      expect(res.body.title).toBe('Updated Title');
      expect(res.body.status).toBe('done');
    });

    it('DELETE /tasks/:id with auth deletes task', async () => {
      const createRes = await request(app)
        .post('/tasks')
        .set('Authorization', authHeader)
        .send({
          title: 'Task to Delete',
          status: 'todo',
          priority: 'medium'
        });

      const taskId = createRes.body.id;
      const res = await request(app)
        .delete(`/tasks/${taskId}`)
        .set('Authorization', authHeader);

      expect(res.status).toBe(204);

      const getRes = await request(app).get(`/tasks/${taskId}`);
      expect(getRes.status).toBe(404);
    });
  });

  // ========================================================================
  // Project Tests
  // ========================================================================
  describe('Project Endpoints', () => {
    let testUser;
    let authHeader;

    beforeEach(async () => {
      const regRes = await request(app)
        .post('/auth/register')
        .send({
          username: 'projectuser',
          email: 'project@example.com',
          password: 'password123'
        });
      testUser = regRes.body.user;
      authHeader = getAuthHeader(testUser);
    });

    it('GET /projects returns 200 with array', async () => {
      const res = await request(app).get('/projects');
      expect(res.status).toBe(200);
      expect(Array.isArray(res.body)).toBe(true);
    });

    it('GET /projects/:id returns 200 with project', async () => {
      const createRes = await request(app)
        .post('/projects')
        .set('Authorization', authHeader)
        .send({
          name: 'Test Project',
          description: 'A test project'
        });

      const projectId = createRes.body.id;
      const res = await request(app).get(`/projects/${projectId}`);

      expect(res.status).toBe(200);
      expect(res.body).toHaveProperty('id', projectId);
      expect(res.body).toHaveProperty('name', 'Test Project');
    });

    it('POST /projects without auth returns 401', async () => {
      const res = await request(app)
        .post('/projects')
        .send({
          name: 'Test Project',
          description: 'A test project'
        });
      expect(res.status).toBe(401);
    });

    it('POST /projects with auth creates project', async () => {
      const res = await request(app)
        .post('/projects')
        .set('Authorization', authHeader)
        .send({
          name: 'New Project',
          description: 'Project description'
        });

      expect(res.status).toBe(201);
      expect(res.body).toHaveProperty('id');
      expect(res.body.name).toBe('New Project');
      expect(res.body.owner_id).toBe(testUser.id);
    });
  });

  // ========================================================================
  // User Tests
  // ========================================================================
  describe('User Endpoints', () => {
    let testUser;

    beforeEach(async () => {
      const regRes = await request(app)
        .post('/auth/register')
        .send({
          username: 'profileuser',
          email: 'profile@example.com',
          password: 'password123'
        });
      testUser = regRes.body.user;
    });

    it('GET /users/:id returns public profile', async () => {
      const res = await request(app).get(`/users/${testUser.id}`);

      expect(res.status).toBe(200);
      expect(res.body).toHaveProperty('id', testUser.id);
      expect(res.body).toHaveProperty('username', 'profileuser');
      expect(res.body).toHaveProperty('email', 'profile@example.com');
      expect(res.body).not.toHaveProperty('password_hash');
    });

    it('GET /users/:id/tasks returns user tasks', async () => {
      const authHeader = getAuthHeader(testUser);

      await request(app)
        .post('/tasks')
        .set('Authorization', authHeader)
        .send({
          title: 'User Task 1',
          status: 'todo',
          priority: 'medium'
        });

      await request(app)
        .post('/tasks')
        .set('Authorization', authHeader)
        .send({
          title: 'User Task 2',
          status: 'in_progress',
          priority: 'high'
        });

      const res = await request(app).get(`/users/${testUser.id}/tasks`);

      expect(res.status).toBe(200);
      expect(Array.isArray(res.body)).toBe(true);
      expect(res.body.length).toBe(2);
    });
  });

  // ========================================================================
  // Error Tests
  // ========================================================================
  describe('Error Handling', () => {
    it('GET /nonexistent returns 404 with JSON error', async () => {
      const res = await request(app).get('/nonexistent');

      expect(res.status).toBe(404);
      expect(res.body).toHaveProperty('error');
      expect(res.body).toHaveProperty('status', 404);
      expect(res.body).toHaveProperty('timestamp');
    });

    it('POST /tasks with invalid data returns 400', async () => {
      const regRes = await request(app)
        .post('/auth/register')
        .send({
          username: 'erroruser',
          email: 'error@example.com',
          password: 'password123'
        });

      const authHeader = getAuthHeader(regRes.body.user);

      const res = await request(app)
        .post('/tasks')
        .set('Authorization', authHeader)
        .send({
          title: '',
          status: 'invalid_status',
          priority: 'invalid_priority'
        });

      expect(res.status).toBe(400);
      expect(res.body).toHaveProperty('error');
      expect(res.body).toHaveProperty('status', 400);
    });
  });
});
