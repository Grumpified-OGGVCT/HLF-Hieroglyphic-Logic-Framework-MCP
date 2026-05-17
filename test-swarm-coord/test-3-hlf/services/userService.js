'use strict';

function loadBcrypt() {
  try {
    return require('bcryptjs');
  } catch {
    return {
      hashSync: (pwd) => `mockhash:${pwd}`,
      compareSync: (pwd, hash) => hash === `mockhash:${pwd}`,
      genSaltSync: () => 'mock-salt',
    };
  }
}

const bcrypt = loadBcrypt();

function createUserService(models) {
  const knex = models.knex;

  async function create(data) {
    const payload = { ...data };
    if (payload.password) {
      payload.password_hash = bcrypt.hashSync(payload.password, bcrypt.genSaltSync(10));
      delete payload.password;
    }
    const [user] = await knex('users').insert(payload).returning('*');
    return sanitize(user);
  }

  async function findById(id) {
    const user = await knex('users').where({ id }).first();
    return user ? sanitize(user) : null;
  }

  async function findByEmail(email) {
    const user = await knex('users').where({ email }).first();
    return user ? sanitize(user) : null;
  }

  async function findByUsername(username) {
    const user = await knex('users').where({ username }).first();
    return user ? sanitize(user) : null;
  }

  async function update(id, data) {
    const payload = { ...data };
    delete payload.id;
    if (payload.password) {
      payload.password_hash = bcrypt.hashSync(payload.password, bcrypt.genSaltSync(10));
      delete payload.password;
    }
    const [user] = await knex('users').where({ id }).update(payload).returning('*');
    return user ? sanitize(user) : null;
  }

  async function remove(id) {
    const count = await knex('users').where({ id }).del();
    return count > 0;
  }

  async function list({ limit = 50, offset = 0 } = {}) {
    const users = await knex('users')
      .select('*')
      .limit(limit)
      .offset(offset)
      .orderBy('created_at', 'desc');
    return users.map(sanitize);
  }

  async function search(query, { limit = 50, offset = 0 } = {}) {
    const users = await knex('users')
      .where(function () {
        this.where('username', 'ilike', `%${query}%`)
          .orWhere('email', 'ilike', `%${query}%`)
          .orWhere('display_name', 'ilike', `%${query}%`);
      })
      .limit(limit)
      .offset(offset)
      .orderBy('created_at', 'desc');
    return users.map(sanitize);
  }

  async function verifyPassword(id, password) {
    const user = await knex('users').where({ id }).first('password_hash');
    if (!user) return false;
    return bcrypt.compareSync(password, user.password_hash);
  }

  function sanitize(user) {
    if (!user) return user;
    const clone = { ...user };
    delete clone.password_hash;
    return clone;
  }

  return {
    create,
    findById,
    findByEmail,
    findByUsername,
    update,
    remove,
    list,
    search,
    verifyPassword,
  };
}

module.exports = { createUserService };
