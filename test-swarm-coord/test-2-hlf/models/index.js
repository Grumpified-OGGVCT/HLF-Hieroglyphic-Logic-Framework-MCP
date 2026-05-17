const UserFactory = require("./User");
const TaskFactory = require("./Task");
const ProjectFactory = require("./Project");
const LabelFactory = require("./Label");
const CommentFactory = require("./Comment");

/**
 * Model index factory
 * @param {import("knex").Knex} knex
 * @returns {{User: object, Task: object, Project: object, Label: object, Comment: object}}
 */
module.exports = function models(knex) {
  return {
    User: UserFactory(knex),
    Task: TaskFactory(knex),
    Project: ProjectFactory(knex),
    Label: LabelFactory(knex),
    Comment: CommentFactory(knex),
  };
};
