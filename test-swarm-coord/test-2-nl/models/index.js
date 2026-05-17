const User = require('./User');
const Task = require('./Task');
const Project = require('./Project');
const Label = require('./Label');
const Comment = require('./Comment');

module.exports = (knex) => ({
  User: User(knex),
  Task: Task(knex),
  Project: Project(knex),
  Label: Label(knex),
  Comment: Comment(knex),
});
