const request = require('supertest');
const express = require('express');

jest.mock('jsonwebtoken', () => {
  const mockSign = jest.fn(() => 'fake-jwt-token');
  const mockVerify = jest.fn((token) => {
    if (token === 'valid-token') {
      return { id: 1, email: 'test@example.com' };
    }
    if (token === 'valid-refresh-token') {
      return { id: 1, email: 'test@example.com', type: 'refresh' };
    }
    const err = new Error('Invalid token');
    err.name = 'JsonWebTokenError';
    throw err;
  });
  return { sign: mockSign, verify: mockVerify };
});

jest.mock('bcryptjs', () => ({
  hash: jest.fn(() => 'hashed-password'),
  compare: jest.fn((plain, hash) => plain === 'password123')
}));

const jwt = require('jsonwebtoken');
const bcrypt = require('bcryptjs');

let users = [];
let tasks = [];
let projects = [];
let labels = [];
let taskLabels = [];
let comments = [];
let nextId = 1;

function resetStores() {
  users = [];
  tasks = [];
  projects = [];
  labels = [];
  taskLabels = [];
  comments = [];
  nextId = 1;
}

function createInMemoryModels() {
  return {
    User: {
      async create(data) {
        const user = {
          id: nextId++,
          email: data.email,
          display_name: data.display_name,
          password_hash: data.password_hash,
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString()
        };
        users.push(user);
        const { password_hash, ...publicUser } = user;
        return publicUser;
      },
      async findById(id) {
        const user = users.find(u => u.id === id);
        if (!user) return null;
        const { password_hash, ...publicUser } = user;
        return publicUser;
      },
      async findByEmail(email) {
        const user = users.find(u => u.email === email);
        if (!user) return null;
        return user;
      },
      async findAll(filters = {}) {
        let result = users.map(u => {
          const { password_hash, ...publicUser } = u;
          return publicUser;
        });
        if (filters.email) {
          result = result.filter(u => u.email.includes(filters.email.replace(/%/g, '')));
        }
        if (filters.display_name) {
          result = result.filter(u => u.display_name.includes(filters.display_name.replace(/%/g, '')));
        }
        return result;
      },
      async update(id, data) {
        const user = users.find(u => u.id === id);
        if (!user) return null;
        Object.assign(user, data, { updated_at: new Date().toISOString() });
        const { password_hash, ...publicUser } = user;
        return publicUser;
      },
      async delete(id) {
        const idx = users.findIndex(u => u.id === id);
        if (idx === -1) return 0;
        users.splice(idx, 1);
        return 1;
      }
    },
    Task: {
      async create(data) {
        const task = {
          id: nextId++,
          project_id: data.project_id,
          assignee_id: data.assignee_id || null,
          title: data.title,
          description: data.description || null,
          status: data.status || 'pending',
          priority: data.priority || 'medium',
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString()
        };
        tasks.push(task);
        return task;
      },
      async findById(id) {
        const task = tasks.find(t => t.id === id);
        if (!task) return null;
        task.labels = await this.getLabels(id);
        return { ...task };
      },
      async findAll(filters = {}) {
        let result = [...tasks];
        if (filters.project_id) {
          result = result.filter(t => t.project_id === filters.project_id);
        }
        if (filters.assignee_id !== undefined) {
          result = result.filter(t => t.assignee_id === filters.assignee_id);
        }
        if (filters.status) {
          result = result.filter(t => t.status === filters.status);
        }
        if (filters.priority) {
          result = result.filter(t => t.priority === filters.priority);
        }
        if (filters.title) {
          result = result.filter(t => t.title.includes(filters.title.replace(/%/g, '')));
        }
        return result;
      },
      async update(id, data) {
        const task = tasks.find(t => t.id === id);
        if (!task) return null;
        Object.assign(task, data, { updated_at: new Date().toISOString() });
        return { ...task };
      },
      async delete(id) {
        const idx = tasks.findIndex(t => t.id === id);
        if (idx === -1) return 0;
        tasks.splice(idx, 1);
        return 1;
      },
      async findByProject(projectId) {
        return tasks.filter(t => t.project_id === projectId);
      },
      async findByAssignee(assigneeId) {
        return tasks.filter(t => t.assignee_id === assigneeId);
      },
      async addLabel(taskId, labelId) {
        taskLabels.push({ task_id: taskId, label_id: labelId });
        return this.getLabels(taskId);
      },
      async removeLabel(taskId, labelId) {
        taskLabels = taskLabels.filter(tl => !(tl.task_id === taskId && tl.label_id === labelId));
        return this.getLabels(taskId);
      },
      async getLabels(taskId) {
        const labelIds = taskLabels.filter(tl => tl.task_id === taskId).map(tl => tl.label_id);
        return labels.filter(l => labelIds.includes(l.id));
      },
      async getComments(taskId) {
        return comments.filter(c => c.task_id === taskId);
      }
    },
    Project: {
      async create(data) {
        const project = {
          id: nextId++,
          owner_id: data.owner_id,
          name: data.name,
          description: data.description || null,
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString()
        };
        projects.push(project);
        return project;
      },
      async findById(id) {
        return projects.find(p => p.id === id) || null;
      },
      async findAll(filters = {}) {
        let result = [...projects];
        if (filters.name) {
          result = result.filter(p => p.name.includes(filters.name));
        }
        if (filters.owner_id) {
          result = result.filter(p => p.owner_id === Number(filters.owner_id));
        }
        return result;
      },
      async update(id, data) {
        const project = projects.find(p => p.id === id);
        if (!project) return null;
        Object.assign(project, data, { updated_at: new Date().toISOString() });
        return { ...project };
      },
      async delete(id) {
        const idx = projects.findIndex(p => p.id === id);
        if (idx === -1) return 0;
        projects.splice(idx, 1);
        return 1;
      },
      async findByOwner(ownerId) {
        return projects.filter(p => p.owner_id === ownerId);
      }
    },
    Label: {
      async create(data) {
        const label = { id: nextId++, ...data, created_at: new Date().toISOString() };
        labels.push(label);
        return label;
      },
      async findById(id) {
        return labels.find(l => l.id === id) || null;
      },
      async findAll(filters = {}) {
        let result = [...labels];
        if (filters.name) {
          result = result.filter(l => l.name.includes(filters.name));
        }
        return result;
      },
      async update(id, data) {
        const label = labels.find(l => l.id === id);
        if (!label) return null;
        Object.assign(label, data);
        return { ...label };
      },
      async delete(id) {
        const idx = labels.findIndex(l => l.id === id);
        if (idx === -1) return 0;
        labels.splice(idx, 1);
        return 1;
      }
    },
    Comment: {
      async create(data) {
        const comment = {
          id: nextId++,
          task_id: data.task_id,
          author_id: data.author_id,
          content: data.content,
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString()
        };
        comments.push(comment);
        return comment;
      },
      async findById(id) {
        return comments.find(c => c.id === id) || null;
      },
      async findAll(filters = {}) {
        let result = [...comments];
        if (filters.task_id) {
          result = result.filter(c => c.task_id === filters.task_id);
        }
        if (filters.author_id) {
          result = result.filter(c => c.author_id === filters.author_id);
        }
        return result;
      },
      async findByTask(taskId) {
        return comments.filter(c => c.task_id === taskId);
      },
      async update(id, data) {
        const comment = comments.find(c => c.id === id);
        if (!comment) return null;
        Object.assign(comment, data, { updated_at: new Date().toISOString() });
        return { ...comment };
      },
      async delete(id) {
        const idx = comments.findIndex(c => c.id === id);
        if (idx === -1) return 0;
        comments.splice(idx, 1);
        return 1;
      }
    }
  };
}

function buildApp() {
  const app = express();
  app.use(express.json());

  const models = createInMemoryModels();
  const authFactory = require('../middleware/auth');
  const auth = authFactory(models);

  const taskValidation = require('../validation/task');
  const projectValidation = require('../validation/project');
  const userValidation = require('../validation/user');

  const tasksRouter = require('../routes/tasks')(models, auth, taskValidation);
  const projectsRouter = require('../routes/projects')(models, auth, projectValidation);
  const usersRouter = require('../routes/users')(models, auth, userValidation);

  app.use('/tasks', tasksRouter);
  app.use('/projects', projectsRouter);
  app.use('/', usersRouter);

  const errorModule = require('../middleware/error')();
  app.use(errorModule.notFoundHandler);
  app.use(errorModule.errorHandler);

  return { app, models };
}

describe('API Integration Tests', () => {
  let app;
  let models;

  beforeEach(() => {
    resetStores();
    jwt.verify.mockClear();
    jwt.sign.mockClear();
    bcrypt.hash.mockClear();
    bcrypt.compare.mockClear();
    const built = buildApp();
    app = built.app;
    models = built.models;
  });

  describe('Auth', () => {
    test('POST /auth/register - 201', async () => {
      const res = await request(app)
        .post('/auth/register')
        .send({ email: 'test@example.com', password: 'password123', display_name: 'TestUser' });
      expect(res.statusCode).toBe(201);
      expect(res.body.token).toBe('fake-jwt-token');
      expect(res.body.user.email).toBe('test@example.com');
    });

    test('POST /auth/register - 409 duplicate', async () => {
      await models.User.create({ email: 'test@example.com', password_hash: 'hashed', display_name: 'TestUser' });
      const res = await request(app)
        .post('/auth/register')
        .send({ email: 'test@example.com', password: 'password123', display_name: 'TestUser2' });
      expect(res.statusCode).toBe(409);
      expect(res.body.error).toBe('Email already registered');
    });

    test('POST /auth/login - 200', async () => {
      await models.User.create({ email: 'test@example.com', password_hash: 'hashed-password', display_name: 'TestUser' });
      const res = await request(app)
        .post('/auth/login')
        .send({ email: 'test@example.com', password: 'password123' });
      expect(res.statusCode).toBe(200);
      expect(res.body.token).toBe('fake-jwt-token');
    });

    test('POST /auth/login - 401', async () => {
      await models.User.create({ email: 'test@example.com', password_hash: 'hashed-password', display_name: 'TestUser' });
      const res = await request(app)
        .post('/auth/login')
        .send({ email: 'test@example.com', password: 'wrongpassword' });
      expect(res.statusCode).toBe(401);
      expect(res.body.error).toBe('Invalid credentials');
    });

    test('POST /auth/refresh - 200', async () => {
      await models.User.create({ email: 'test@example.com', password_hash: 'hashed', display_name: 'TestUser' });
      const res = await request(app)
        .post('/auth/refresh')
        .send({ refreshToken: 'valid-refresh-token' });
      expect(res.statusCode).toBe(200);
      expect(res.body.token).toBe('fake-jwt-token');
    });
  });

  describe('Tasks', () => {
    let projectId;
    let taskId;

    beforeEach(async () => {
      const user = await models.User.create({ email: 'u@example.com', password_hash: 'h', display_name: 'U' });
      const project = await models.Project.create({ owner_id: user.id, name: 'P1' });
      const task = await models.Task.create({ project_id: project.id, title: 'T1', status: 'pending' });
      projectId = project.id;
      taskId = task.id;
    });

    test('GET /tasks - 200', async () => {
      const res = await request(app).get('/tasks');
      expect(res.statusCode).toBe(200);
      expect(Array.isArray(res.body)).toBe(true);
      expect(res.body.length).toBe(1);
    });

    test('GET /tasks/:id - 200', async () => {
      const res = await request(app).get(`/tasks/${taskId}`);
      expect(res.statusCode).toBe(200);
      expect(res.body.title).toBe('T1');
    });

    test('GET /tasks/:id - 404', async () => {
      const res = await request(app).get('/tasks/999');
      expect(res.statusCode).toBe(404);
      expect(res.body.error).toBe('Task not found');
    });

    test('POST /tasks - 401 without auth', async () => {
      const res = await request(app)
        .post('/tasks')
        .send({ project_id: projectId, title: 'New Task' });
      expect(res.statusCode).toBe(401);
      expect(res.body.error).toBe('Unauthorized');
    });

    test('POST /tasks - 201 with auth', async () => {
      const res = await request(app)
        .post('/tasks')
        .set('Authorization', 'Bearer valid-token')
        .send({ project_id: projectId, title: 'New Task' });
      expect(res.statusCode).toBe(201);
      expect(res.body.title).toBe('New Task');
    });

    test('PUT /tasks/:id - 200', async () => {
      const res = await request(app)
        .put(`/tasks/${taskId}`)
        .set('Authorization', 'Bearer valid-token')
        .send({ title: 'Updated Task' });
      expect(res.statusCode).toBe(200);
      expect(res.body.title).toBe('Updated Task');
    });

    test('DELETE /tasks/:id - 204', async () => {
      const res = await request(app)
        .delete(`/tasks/${taskId}`)
        .set('Authorization', 'Bearer valid-token');
      expect(res.statusCode).toBe(204);
    });

    test('POST /tasks/:id/labels/:labelId - 201', async () => {
      const label = await models.Label.create({ name: 'bug', color: '#ff0000' });
      const res = await request(app)
        .post(`/tasks/${taskId}/labels/${label.id}`)
        .set('Authorization', 'Bearer valid-token');
      expect(res.statusCode).toBe(201);
      expect(Array.isArray(res.body)).toBe(true);
    });

    test('DELETE /tasks/:id/labels/:labelId - 200', async () => {
      const label = await models.Label.create({ name: 'bug', color: '#ff0000' });
      await models.Task.addLabel(taskId, label.id);
      const res = await request(app)
        .delete(`/tasks/${taskId}/labels/${label.id}`)
        .set('Authorization', 'Bearer valid-token');
      expect(res.statusCode).toBe(200);
      expect(Array.isArray(res.body)).toBe(true);
    });

    test('GET /tasks/:id/comments - 200', async () => {
      const res = await request(app).get(`/tasks/${taskId}/comments`);
      expect(res.statusCode).toBe(200);
      expect(Array.isArray(res.body)).toBe(true);
    });
  });

  describe('Projects', () => {
    let projectId;

    beforeEach(async () => {
      const user = await models.User.create({ email: 'u@example.com', password_hash: 'h', display_name: 'U' });
      const project = await models.Project.create({ owner_id: user.id, name: 'P1' });
      projectId = project.id;
    });

    test('GET /projects - 200', async () => {
      const res = await request(app).get('/projects');
      expect(res.statusCode).toBe(200);
      expect(Array.isArray(res.body)).toBe(true);
      expect(res.body.length).toBe(1);
    });

    test('GET /projects/:id - 200', async () => {
      const res = await request(app).get(`/projects/${projectId}`);
      expect(res.statusCode).toBe(200);
      expect(res.body.name).toBe('P1');
    });

    test('POST /projects - 401 without auth', async () => {
      const res = await request(app)
        .post('/projects')
        .send({ name: 'New Project', owner_id: 1 });
      expect(res.statusCode).toBe(401);
      expect(res.body.error).toBe('Unauthorized');
    });

    test('POST /projects - 201 with auth', async () => {
      const res = await request(app)
        .post('/projects')
        .set('Authorization', 'Bearer valid-token')
        .send({ name: 'New Project', owner_id: 1 });
      expect(res.statusCode).toBe(201);
      expect(res.body.name).toBe('New Project');
    });

    test('PUT /projects/:id - 200', async () => {
      const res = await request(app)
        .put(`/projects/${projectId}`)
        .set('Authorization', 'Bearer valid-token')
        .send({ name: 'Updated Project' });
      expect(res.statusCode).toBe(200);
      expect(res.body.name).toBe('Updated Project');
    });

    test('DELETE /projects/:id - 204', async () => {
      const res = await request(app)
        .delete(`/projects/${projectId}`)
        .set('Authorization', 'Bearer valid-token');
      expect(res.statusCode).toBe(204);
    });

    test('GET /projects/:id/tasks - 200', async () => {
      const res = await request(app).get(`/projects/${projectId}/tasks`);
      expect(res.statusCode).toBe(200);
      expect(Array.isArray(res.body)).toBe(true);
    });
  });

  describe('Users', () => {
    let userId;

    beforeEach(async () => {
      const user = await models.User.create({ email: 'u@example.com', password_hash: 'h', display_name: 'U' });
      userId = user.id;
    });

    test('GET /users/:id - 200', async () => {
      const res = await request(app).get(`/users/${userId}`);
      expect(res.statusCode).toBe(200);
      expect(res.body.display_name).toBe('U');
    });

    test('GET /users/:id/tasks - 200', async () => {
      const res = await request(app).get(`/users/${userId}/tasks`);
      expect(res.statusCode).toBe(200);
      expect(Array.isArray(res.body)).toBe(true);
    });

    test('PUT /users/:id - 200', async () => {
      const res = await request(app)
        .put(`/users/${userId}`)
        .set('Authorization', 'Bearer valid-token')
        .send({ display_name: 'UpdatedUser' });
      expect(res.statusCode).toBe(200);
      expect(res.body.display_name).toBe('UpdatedUser');
    });
  });

  describe('Errors', () => {
    test('404 route', async () => {
      const res = await request(app).get('/nonexistent-route');
      expect(res.statusCode).toBe(404);
    });

    test('400 validation', async () => {
      const res = await request(app)
        .post('/tasks')
        .set('Authorization', 'Bearer valid-token')
        .send({});
      expect(res.statusCode).toBe(400);
      expect(res.body.errors).toBeDefined();
      expect(Array.isArray(res.body.errors)).toBe(true);
    });
  });
});

module.exports.testSuite = {
  test_count: 27,
  coverage: [
    'GET /tasks',
    'GET /tasks/:id',
    'POST /tasks',
    'PUT /tasks/:id',
    'DELETE /tasks/:id',
    'POST /tasks/:id/labels/:labelId',
    'DELETE /tasks/:id/labels/:labelId',
    'GET /tasks/:id/comments',
    'GET /projects',
    'GET /projects/:id',
    'POST /projects',
    'PUT /projects/:id',
    'DELETE /projects/:id',
    'GET /projects/:id/tasks',
    'GET /users/:id',
    'GET /users/:id/tasks',
    'PUT /users/:id',
    'POST /auth/register',
    'POST /auth/login',
    'POST /auth/refresh'
  ],
  mock_strategy: 'in-memory'
};
