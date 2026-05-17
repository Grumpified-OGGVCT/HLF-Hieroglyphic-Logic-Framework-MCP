/**
 * Project validation module — pure JS, no deps, CommonJS.
 * All functions return { valid: boolean, errors: string[] }.
 */

const MAX_NAME_LENGTH = 100;
const MAX_DESCRIPTION_LENGTH = 5000;

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

function validateProject(data) {
  const errors = [];

  if (!data || typeof data !== 'object') {
    errors.push('Project data must be an object');
    return ok(errors);
  }

  // name
  if (!Object.prototype.hasOwnProperty.call(data, 'name')) {
    errors.push('Name is required');
  } else if (!isNonEmptyString(data.name)) {
    errors.push('Name must be a non-empty string');
  } else if (data.name.length > MAX_NAME_LENGTH) {
    errors.push(`Name must be at most ${MAX_NAME_LENGTH} characters`);
  }

  // description (optional)
  if (Object.prototype.hasOwnProperty.call(data, 'description')) {
    if (!isString(data.description)) {
      errors.push('Description must be a string');
    } else if (data.description.length > MAX_DESCRIPTION_LENGTH) {
      errors.push(`Description must be at most ${MAX_DESCRIPTION_LENGTH} characters`);
    }
  }

  // owner_id
  if (!Object.prototype.hasOwnProperty.call(data, 'owner_id')) {
    errors.push('Owner ID is required');
  } else if (!isPositiveInt(data.owner_id)) {
    errors.push('Owner ID must be a positive integer');
  }

  return ok(errors);
}

function validateProjectUpdate(data) {
  const errors = [];

  if (!data || typeof data !== 'object') {
    errors.push('Project update data must be an object');
    return ok(errors);
  }

  if (Object.prototype.hasOwnProperty.call(data, 'name')) {
    if (!isNonEmptyString(data.name)) {
      errors.push('Name must be a non-empty string');
    } else if (data.name.length > MAX_NAME_LENGTH) {
      errors.push(`Name must be at most ${MAX_NAME_LENGTH} characters`);
    }
  }

  if (Object.prototype.hasOwnProperty.call(data, 'description')) {
    if (!isString(data.description)) {
      errors.push('Description must be a string');
    } else if (data.description.length > MAX_DESCRIPTION_LENGTH) {
      errors.push(`Description must be at most ${MAX_DESCRIPTION_LENGTH} characters`);
    }
  }

  if (Object.prototype.hasOwnProperty.call(data, 'owner_id')) {
    if (!isPositiveInt(data.owner_id)) {
      errors.push('Owner ID must be a positive integer');
    }
  }

  return ok(errors);
}

module.exports = {
  validateProject,
  validateProjectUpdate,
};
