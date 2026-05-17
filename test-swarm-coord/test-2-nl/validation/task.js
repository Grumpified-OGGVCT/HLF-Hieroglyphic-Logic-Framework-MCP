function validateTask(data) {
  const errors = [];

  if (typeof data !== 'object' || data === null) {
    return { valid: false, errors: ['Data must be an object'] };
  }

  const { title, status, priority } = data;

  if (typeof title !== 'string' || title.length < 1 || title.length > 200) {
    errors.push('Title must be between 1 and 200 characters');
  }

  const validStatuses = ['todo', 'in_progress', 'done'];
  if (typeof status !== 'string' || !validStatuses.includes(status)) {
    errors.push("Status must be 'todo', 'in_progress', or 'done'");
  }

  const validPriorities = ['low', 'medium', 'high'];
  if (typeof priority !== 'string' || !validPriorities.includes(priority)) {
    errors.push("Priority must be 'low', 'medium', or 'high'");
  }

  return { valid: errors.length === 0, errors };
}

function validateTaskUpdate(data) {
  const errors = [];

  if (typeof data !== 'object' || data === null) {
    return { valid: false, errors: ['Data must be an object'] };
  }

  if (Object.keys(data).length === 0) {
    return { valid: false, errors: ['At least one field must be provided for update'] };
  }

  if (data.title !== undefined) {
    if (typeof data.title !== 'string' || data.title.length < 1 || data.title.length > 200) {
      errors.push('Title must be between 1 and 200 characters');
    }
  }

  if (data.status !== undefined) {
    const validStatuses = ['todo', 'in_progress', 'done'];
    if (typeof data.status !== 'string' || !validStatuses.includes(data.status)) {
      errors.push("Status must be 'todo', 'in_progress', or 'done'");
    }
  }

  if (data.priority !== undefined) {
    const validPriorities = ['low', 'medium', 'high'];
    if (typeof data.priority !== 'string' || !validPriorities.includes(data.priority)) {
      errors.push("Priority must be 'low', 'medium', or 'high'");
    }
  }

  return { valid: errors.length === 0, errors };
}

function validateTaskFilters(query) {
  const errors = [];
  const validStatuses = ['todo', 'in_progress', 'done'];
  const validPriorities = ['low', 'medium', 'high'];

  if (typeof query !== 'object' || query === null) {
    return { valid: false, errors: ['Query must be an object'] };
  }

  if (query.status !== undefined) {
    if (typeof query.status !== 'string' || !validStatuses.includes(query.status)) {
      errors.push("Status filter must be 'todo', 'in_progress', or 'done'");
    }
  }

  if (query.priority !== undefined) {
    if (typeof query.priority !== 'string' || !validPriorities.includes(query.priority)) {
      errors.push("Priority filter must be 'low', 'medium', or 'high'");
    }
  }

  if (query.project_id !== undefined) {
    if (typeof query.project_id !== 'string' || query.project_id.trim().length === 0) {
      errors.push('Project ID filter must be a non-empty string');
    }
  }

  if (query.assignee_id !== undefined) {
    if (typeof query.assignee_id !== 'string' || query.assignee_id.trim().length === 0) {
      errors.push('Assignee ID filter must be a non-empty string');
    }
  }

  return { valid: errors.length === 0, errors };
}

module.exports = { validateTask, validateTaskUpdate, validateTaskFilters };
