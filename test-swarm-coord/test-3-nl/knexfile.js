require('dotenv').config();

const baseConfig = {
  client: 'postgresql',
  migrations: {
    directory: './migrations',
  },
  seeds: {
    directory: './seeds',
  },
};

module.exports = {
  development: {
    ...baseConfig,
    connection: process.env.DATABASE_URL || {
      host: process.env.DB_HOST || 'localhost',
      port: process.env.DB_PORT || 5432,
      database: process.env.DB_NAME || 'chat_db',
      user: process.env.DB_USER || 'chat_user',
      password: process.env.DB_PASSWORD || 'chat_pass',
    },
    pool: {
      min: 2,
      max: 10,
    },
  },

  test: {
    ...baseConfig,
    connection: process.env.TEST_DATABASE_URL || {
      host: process.env.DB_HOST || 'localhost',
      port: process.env.DB_PORT || 5432,
      database: process.env.TEST_DB_NAME || 'chat_db_test',
      user: process.env.DB_USER || 'chat_user',
      password: process.env.DB_PASSWORD || 'chat_pass',
    },
    pool: {
      min: 1,
      max: 5,
    },
  },

  production: {
    ...baseConfig,
    connection: process.env.DATABASE_URL,
    pool: {
      min: 2,
      max: 20,
    },
    migrations: {
      directory: './migrations',
    },
    seeds: {
      directory: './seeds',
    },
  },
};
