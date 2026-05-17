function validateProject(data) {
  const errors = [];

  if (typeof data !== 'object' || data === null) {
    return { valid: false, errors: ['Data must be an object'] };
  }

  const { name, description } = data;

  if (typeof name !== 'string' || name.length < 1 || name.length > 100) {
    errors.push('Name must be between 1 and 100 characters');
  }

  if (description !== undefined) {
    if (typeof description !== 'string' || description.length > 1000) {
      errors.push('Description must be at most 1000 characters');
    }
  }

  return { valid: errors.length === 0, errors };
}

function validateProjectUpdate(data) {
  const errors = [];

  if (typeof data !== 'object' || data === null) {
    return { valid: false, errors: ['Data must be an object'] };
  }

  if (Object.keys(data).length === 0) {
    return { valid: false, errors: ['At least one field must be provided for update'] };
  }

  if (data.name !== undefined) {
    if (typeof data.name !== 'string' || data.name.length < 1 || data.name.length > 100) {
      errors.push('Name must be between 1 and 100 characters');
    }
  }

  if (data.description !== undefined) {
    if (typeof data.description !== 'string' || data.description.length > 1000) {
      errors.push('Description must be at most 1000 characters');
    }
  }

  return { valid: errors.length === 0, errors };
}

module.exports = { validateProject, validateProjectUpdate };
