const express = require('express');
const dotenv = require('dotenv');

// Load env vars
dotenv.config();

// Create app
const app = express();

// Middleware
app.use(express.json());
app.use(express.urlencoded({ extended: true }));

// Initialize models
const knexConfig = require('./knexfile');
const knex = require('knex')(knexConfig[process.env.NODE_ENV || 'development']);
const models = require('./models')(knex);

// Initialize auth middleware
const auth = require('./middleware/auth')(models);

// Initialize validation
const validation = {
  user: require('./validation/user'),
  task: require('./validation/task'),
  project: require('./validation/project')
};

// Initialize error handling
const { errorHandler, notFoundHandler, setupErrorHandlers } = require('./middleware/error')();
setupErrorHandlers();

// Routes
const taskRoutes = require('./routes/tasks')(models, auth, validation.task);
const projectRoutes = require('./routes/projects')(models, auth, validation.project);
const userRoutes = require('./routes/users')(models, auth, validation.user);

app.use('/tasks', taskRoutes);
app.use('/projects', projectRoutes);
app.use('/users', userRoutes);

// 404 handler
app.use(notFoundHandler);

// Error handler (must be last)
app.use(errorHandler);

// Start server
const PORT = process.env.PORT || 3000;
app.listen(PORT, () => {
  console.log(`Server running on port ${PORT}`);
});

module.exports = app;
