const express = require('express');
const dotenv = require('dotenv');
dotenv.config();
const app = express();
app.use(express.json());
app.use(express.urlencoded({ extended: true }));

const knexConfig = require('./knexfile');
const knex = require('knex')(knexConfig[process.env.NODE_ENV || 'development']);
const models = require('./models')(knex);
const auth = require('./middleware/auth')(models);
const validation = {
  user: require('./validation/user'),
  task: require('./validation/task'),
  project: require('./validation/project')
};
const { errorHandler, notFoundHandler, setupErrorHandlers } = require('./middleware/error')();
setupErrorHandlers();

const taskRoutes = require('./routes/tasks')(models, auth, validation.task);
const projectRoutes = require('./routes/projects')(models, auth, validation.project);
const userRoutes = require('./routes/users')(models, auth, validation.user);

app.use('/tasks', taskRoutes);
app.use('/projects', projectRoutes);
app.use('/', userRoutes);
app.use(notFoundHandler);
app.use(errorHandler);

const PORT = process.env.PORT || 3000;
app.listen(PORT, () => console.log(`Server running on port ${PORT}`));
module.exports = app;
