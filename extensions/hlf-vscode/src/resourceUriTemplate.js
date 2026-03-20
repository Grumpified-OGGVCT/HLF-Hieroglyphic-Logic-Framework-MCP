function getResourceUriPlaceholders(resourceUri) {
  const matches = resourceUri.matchAll(/\{([^}]+)\}/g);
  return [...matches].map((match) => match[1]);
}

function applyResourceUriValues(resourceUri, values) {
  let resolved = resourceUri;
  for (const [key, value] of Object.entries(values)) {
    resolved = resolved.replaceAll(`{${key}}`, encodeURIComponent(value));
  }
  return resolved;
}

module.exports = {
  applyResourceUriValues,
  getResourceUriPlaceholders,
};