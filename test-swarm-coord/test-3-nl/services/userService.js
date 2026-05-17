const bcrypt = require('bcryptjs');

function sanitizeUser(user) {
  if (!user) return user;
  const { password_hash, ...safe } = user;
  return safe;
}

function createUserService({ knex }) {
  async function hashPassword(password) {
    const rounds = 10;
    if (typeof bcrypt.hash === 'function') {
      return bcrypt.hash(password, rounds);
    }
    // mock fallback
    return `mock:${password}`;
  }

  async function verifyPassword(password, hash) {
    if (typeof bcrypt.compare === 'function') {
      return bcrypt.compare(password, hash);
    }
    return hash === `mock:${password}`;
  }

  async function create({ username, email, password, display_name, avatar_url, status = 'offline' }) {
    const password_hash = await hashPassword(password);
    const [user] = await knex('users')
      .insert({ username, email, password_hash, display_name, avatar_url, status })
      .returning('*');
    return sanitizeUser(user);
  }

  async function findById(id) {
    const user = await knex('users').where({ id }).first();
    return sanitizeUser(user) || null;
  }

  async function findByEmail(email) {
    const user = await knex('users').where({ email }).first();
    return sanitizeUser(user) || null;
  }

  async function findByUsername(username) {
    const user = await knex('users').where({ username }).first();
    return sanitizeUser(user) || null;
  }

  async function findByEmailWithPassword(email) {
    const user = await knex('users').where({ email }).first();
    return user || null;
  }

  async function update(id, updates) {
    const payload = { ...updates, updated_at: knex.fn.now() };
    if (payload.password) {
      payload.password_hash = await hashPassword(payload.password);
      delete payload.password;
    }
    const [user] = await knex('users')
      .where({ id })
      .update(payload)
      .returning('*');
    return sanitizeUser(user) || null;
  }

  async function remove(id) {
    const count = await knex('users').where({ id }).del();
    return count > 0;
  }

  async function list({ limit = 20, offset = 0 } = {}) {
    const users = await knex('users')
      .select('*')
      .limit(limit)
      .offset(offset)
      .orderBy('created_at', 'desc');
    return users.map(sanitizeUser);
  }

  async function search(query, { limit = 20, offset = 0 } = {}) {
    const like = `%${query}%`;
    const users = await knex('users')
      .where(function () {
        this.whereILike('username', like)
          .orWhereILike('email', like)
          .orWhereILike('display_name', like);
      })
      .limit(limit)
      .offset(offset)
      .orderBy('created_at', 'desc');
    return users.map(sanitizeUser);
  }

  return {
    create,
    findById,
    findByEmail,
    findByEmailWithPassword,
    findByUsername,
    update,
    remove,
    list,
    search,
    verifyPassword,
  };
}

module.exports = { createUserService };
