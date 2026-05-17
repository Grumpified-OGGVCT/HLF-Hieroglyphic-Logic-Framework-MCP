/**
 * User validation module — pure JS, no deps, CommonJS.
 * All functions return { valid: boolean, errors: string[] }.
 */

const VALID_USERNAME = /^[a-zA-Z0-9_]{3,30}$/;
const VALID_EMAIL = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
const MIN_PASSWORD_LENGTH = 8;
const MAX_DISPLAY_NAME_LENGTH = 100;

function ok(errors) {
  return { valid: errors.length === 0, errors };
}

function isString(val) {
  return typeof val === 'string';
}

function isNonEmptyString(val) {
  return isString(val) && val.trim().length > 0;
}

function isPositiveInt(val) {
  return Number.isInteger(val) && val > 0;
}

function validateUser(data) {
  const errors = [];

  if (!data || typeof data !== 'object') {
    errors.push('User data must be an object');
    return ok(errors);
  }

  // username
  if (!Object.prototype.hasOwnProperty.call(data, 'username')) {
    errors.push('Username is required');
  } else if (!isNonEmptyString(data.username)) {
    errors.push('Username must be a non-empty string');
  } else if (!VALID_USERNAME.test(data.username)) {
    errors.push('Username must be 3-30 characters and contain only letters, numbers, and underscores');
  }

  // email
  if (!Object.prototype.hasOwnProperty.call(data, 'email')) {
    errors.push('Email is required');
  } else if (!isNonEmptyString(data.email)) {
    errors.push('Email must be a non-empty string');
  } else if (!VALID_EMAIL.test(data.email)) {
    errors.push('Email must be a valid email address');
  }

  // password
  if (!Object.prototype.hasOwnProperty.call(data, 'password')) {
    errors.push('Password is required');
  } else if (!isNonEmptyString(data.password)) {
    errors.push('Password must be a non-empty string');
  } else if (data.password.length < MIN_PASSWORD_LENGTH) {
    errors.push(`Password must be at least ${MIN_PASSWORD_LENGTH} characters`);
  }

  // display_name (optional)
  if (Object.prototype.hasOwnProperty.call(data, 'display_name')) {
    if (!isString(data.display_name)) {
      errors.push('Display name must be a string');
    } else if (data.display_name.length > MAX_DISPLAY_NAME_LENGTH) {
      errors.push(`Display name must be at most ${MAX_DISPLAY_NAME_LENGTH} characters`);
    }
  }

  return ok(errors);
}

function validateLogin(data) {
  const errors = [];

  if (!data || typeof data !== 'object') {
    errors.push('Login data must be an object');
    return ok(errors);
  }

  const hasUsername = Object.prototype.hasOwnProperty.call(data, 'username');
  const hasEmail = Object.prototype.hasOwnProperty.call(data, 'email');

  if (!hasUsername && !hasEmail) {
    errors.push('Username or email is required');
  } else {
    if (hasUsername && !isNonEmptyString(data.username)) {
      errors.push('Username must be a non-empty string');
    }
    if (hasEmail && !isNonEmptyString(data.email)) {
      errors.push('Email must be a non-empty string');
    }
  }

  if (!Object.prototype.hasOwnProperty.call(data, 'password')) {
    errors.push('Password is required');
  } else if (!isNonEmptyString(data.password)) {
    errors.push('Password must be a non-empty string');
  }

  return ok(errors);
}

function validateUserUpdate(data) {
  const errors = [];

  if (!data || typeof data !== 'object') {
    errors.push('User update data must be an object');
    return ok(errors);
  }

  if (Object.prototype.hasOwnProperty.call(data, 'username')) {
    if (!isNonEmptyString(data.username)) {
      errors.push('Username must be a non-empty string');
    } else if (!VALID_USERNAME.test(data.username)) {
      errors.push('Username must be 3-30 characters and contain only letters, numbers, and underscores');
    }
  }

  if (Object.prototype.hasOwnProperty.call(data, 'email')) {
    if (!isNonEmptyString(data.email)) {
      errors.push('Email must be a non-empty string');
    } else if (!VALID_EMAIL.test(data.email)) {
      errors.push('Email must be a valid email address');
    }
  }

  if (Object.prototype.hasOwnProperty.call(data, 'password')) {
    if (!isNonEmptyString(data.password)) {
      errors.push('Password must be a non-empty string');
    } else if (data.password.length < MIN_PASSWORD_LENGTH) {
      errors.push(`Password must be at least ${MIN_PASSWORD_LENGTH} characters`);
    }
  }

  if (Object.prototype.hasOwnProperty.call(data, 'display_name')) {
    if (!isString(data.display_name)) {
      errors.push('Display name must be a string');
    } else if (data.display_name.length > MAX_DISPLAY_NAME_LENGTH) {
      errors.push(`Display name must be at most ${MAX_DISPLAY_NAME_LENGTH} characters`);
    }
  }

  return ok(errors);
}

module.exports = {
  validateUser,
  validateLogin,
  validateUserUpdate,
};
