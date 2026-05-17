function validateUser(data) {
  const errors = [];

  if (typeof data !== 'object' || data === null) {
    return { valid: false, errors: ['Data must be an object'] };
  }

  const { username, email, password } = data;

  if (typeof username !== 'string' || username.length < 3 || username.length > 30) {
    errors.push('Username must be between 3 and 30 characters');
  } else if (!/^[a-zA-Z0-9]+$/.test(username)) {
    errors.push('Username must be alphanumeric');
  }

  if (typeof email !== 'string' || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
    errors.push('Email must be a valid email address');
  }

  if (typeof password !== 'string' || password.length < 8) {
    errors.push('Password must be at least 8 characters');
  } else if (!/[a-zA-Z]/.test(password) || !/[0-9]/.test(password)) {
    errors.push('Password must contain at least one letter and one number');
  }

  return { valid: errors.length === 0, errors };
}

function validateLogin(data) {
  const errors = [];

  if (typeof data !== 'object' || data === null) {
    return { valid: false, errors: ['Data must be an object'] };
  }

  const { email, password } = data;

  if (typeof email !== 'string' || email.trim().length === 0) {
    errors.push('Email is required');
  }

  if (typeof password !== 'string' || password.trim().length === 0) {
    errors.push('Password is required');
  }

  return { valid: errors.length === 0, errors };
}

function validateUserUpdate(data) {
  const errors = [];

  if (typeof data !== 'object' || data === null) {
    return { valid: false, errors: ['Data must be an object'] };
  }

  if (Object.keys(data).length === 0) {
    return { valid: false, errors: ['At least one field must be provided for update'] };
  }

  if (data.username !== undefined) {
    if (typeof data.username !== 'string' || data.username.length < 3 || data.username.length > 30) {
      errors.push('Username must be between 3 and 30 characters');
    } else if (!/^[a-zA-Z0-9]+$/.test(data.username)) {
      errors.push('Username must be alphanumeric');
    }
  }

  if (data.email !== undefined) {
    if (typeof data.email !== 'string' || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(data.email)) {
      errors.push('Email must be a valid email address');
    }
  }

  if (data.password !== undefined) {
    if (typeof data.password !== 'string' || data.password.length < 8) {
      errors.push('Password must be at least 8 characters');
    } else if (!/[a-zA-Z]/.test(data.password) || !/[0-9]/.test(data.password)) {
      errors.push('Password must contain at least one letter and one number');
    }
  }

  return { valid: errors.length === 0, errors };
}

module.exports = { validateUser, validateLogin, validateUserUpdate };
