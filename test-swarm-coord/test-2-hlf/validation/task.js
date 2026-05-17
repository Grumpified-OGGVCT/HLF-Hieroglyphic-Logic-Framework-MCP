/**
 * Task validation module — pure JS, no deps, CommonJS.
 * All functions return { valid: boolean, errors: string[] }.
 */

const VALID_STATUSES = ['pending', 'in_progress', 'completed', 'cancelled'];
const VALID_PRIORITIES = ['low', 'medium', 'high', 'critical'];
const MAX_TITLE_LENGTH = 200;
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

function isValidDate(val) {
  if (!isString(val)) return false;
  const d = new Date(val);
  return !isNaN(d.getTime());
}

function validateTask(data) {
  const errors = [];

  if (!data || typeof data !== 'object') {
    errors.push('Task data must be an object');
    return ok(errors);
  }

  // title
  if (!Object.prototype.hasOwnProperty.call(data, 'title')) {
    errors.push('Title is required');
  } else if (!isNonEmptyString(data.title)) {
    errors.push('Title must be a non-empty string');
  } else if (data.title.length > MAX_TITLE_LENGTH) {
    errors.push(`Title must be at most ${MAX_TITLE_LENGTH} characters`);
  }

  // description (optional)
  if (Object.prototype.hasOwnProperty.call(data, 'description')) {
    if (!isString(data.description)) {
      errors.push('Description must be a string');
    } else if (data.description.length > MAX_DESCRIPTION_LENGTH) {
      errors.push(`Description must be at most ${MAX_DESCRIPTION_LENGTH} characters`);
    }
  }

  // status (optional, defaults on server)
  if (Object.prototype.hasOwnProperty.call(data, 'status')) {
    if (!VALID_STATUSES.includes(data.status)) {
      errors.push(`Status must be one of: ${VALID_STATUSES.join(', ')}`);
    }
  }

  // priority (optional)
  if (Object.prototype.hasOwnProperty.call(data, 'priority')) {
    if (!VALID_PRIORITIES.includes(data.priority)) {
      errors.push(`Priority must be one of: ${VALID_PRIORITIES.join(', ')}`);
    }
  }

  // due_date (optional)
  if (Object.prototype.hasOwnProperty.call(data, 'due_date')) {
    if (!isValidDate(data.due_date)) {
      errors.push('Due date must be a valid ISO 8601 date string');
    }
  }

  // project_id
  if (!Object.prototype.hasOwnProperty.call(data, 'project_id')) {
    errors.push('Project ID is required');
  } else if (!isPositiveInt(data.project_id)) {
    errors.push('Project ID must be a positive integer');
  }

  // assignee_id (optional)
  if (Object.prototype.hasOwnProperty.call(data, 'assignee_id')) {
    if (data.assignee_id !== null && !isPositiveInt(data.assignee_id)) {
      errors.push('Assignee ID must be a positive integer or null');
    }
  }

  return ok(errors);
}

function validateTaskUpdate(data) {
  const errors = [];

  if (!data || typeof data !== 'object') {
    errors.push('Task update data must be an object');
    return ok(errors);
  }

  if (Object.prototype.hasOwnProperty.call(data, 'title')) {
    if (!isNonEmptyString(data.title)) {
      errors.push('Title must be a non-empty string');
    } else if (data.title.length > MAX_TITLE_LENGTH) {
      errors.push(`Title must be at most ${MAX_TITLE_LENGTH} characters`);
    }
  }

  if (Object.prototype.hasOwnProperty.call(data, 'description')) {
    if (!isString(data.description)) {
      errors.push('Description must be a string');
    } else if (data.description.length > MAX_DESCRIPTION_LENGTH) {
      errors.push(`Description must be at most ${MAX_DESCRIPTION_LENGTH} characters`);
    }
  }

  if (Object.prototype.hasOwnProperty.call(data, 'status')) {
    if (!VALID_STATUSES.includes(data.status)) {
      errors.push(`Status must be one of: ${VALID_STATUSES.join(', ')}`);
    }
  }

  if (Object.prototype.hasOwnProperty.call(data, 'priority')) {
    if (!VALID_PRIORITIES.includes(data.priority)) {
      errors.push(`Priority must be one of: ${VALID_PRIORITIES.join(', ')}`);
    }
  }

  if (Object.prototype.hasOwnProperty.call(data, 'due_date')) {
    if (data.due_date !== null && !isValidDate(data.due_date)) {
      errors.push('Due date must be a valid ISO 8601 date string or null');
    }
  }

  if (Object.prototype.hasOwnProperty.call(data, 'project_id')) {
    if (!isPositiveInt(data.project_id)) {
      errors.push('Project ID must be a positive integer');
    }
  }

  if (Object.prototype.hasOwnProperty.call(data, 'assignee_id')) {
    if (data.assignee_id !== null && !isPositiveInt(data.assignee_id)) {
      errors.push('Assignee ID must be a positive integer or null');
    }
  }

  return ok(errors);
}

function validateTaskFilters(data) {
  const errors = [];

  if (!data || typeof data !== 'object') {
    errors.push('Filter data must be an object');
    return ok(errors);
  }

  if (Object.prototype.hasOwnProperty.call(data, 'status')) {
    if (!VALID_STATUSES.includes(data.status)) {
      errors.push(`Status filter must be one of: ${VALID_STATUSES.join(', ')}`);
    }
  }

  if (Object.prototype.hasOwnProperty.call(data, 'priority')) {
    if (!VALID_PRIORITIES.includes(data.priority)) {
      errors.push(`Priority filter must be one of: ${VALID_PRIORITIES.join(', ')}`);
    }
  }

  if (Object.prototype.hasOwnProperty.call(data, 'project_id')) {
    if (!isPositiveInt(data.project_id)) {
      errors.push('Project ID filter must be a positive integer');
    }
  }

  if (Object.prototype.hasOwnProperty.call(data, 'assignee_id')) {
    if (data.assignee_id !== null && !isPositiveInt(data.assignee_id)) {
      errors.push('Assignee ID filter must be a positive integer or null');
    }
  }

  if (Object.prototype.hasOwnProperty.call(data, 'search')) {
    if (!isString(data.search)) {
      errors.push('Search filter must be a string');
    }
  }

  if (Object.prototype.hasOwnProperty.call(data, 'page')) {
    const page = Number(data.page);
    if (!Number.isInteger(page) || page < 1) {
      errors.push('Page must be a positive integer');
    }
  }

  if (Object.prototype.hasOwnProperty.call(data, 'limit')) {
    const limit = Number(data.limit);
    if (!Number.isInteger(limit) || limit < 1 || limit > 100) {
      errors.push('Limit must be an integer between 1 and 100');
    }
  }

  return ok(errors);
}

module.exports = {
  validateTask,
  validateTaskUpdate,
  validateTaskFilters,
};
