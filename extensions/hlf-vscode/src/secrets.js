const HTTP_BEARER_TOKEN_SECRET_KEY = 'hlf.http.bearerToken';

async function getHttpBearerToken(secretStorage) {
  return secretStorage.get(HTTP_BEARER_TOKEN_SECRET_KEY);
}

async function hasHttpBearerToken(secretStorage) {
  return Boolean(await getHttpBearerToken(secretStorage));
}

async function storeHttpBearerToken(secretStorage, token) {
  await secretStorage.store(HTTP_BEARER_TOKEN_SECRET_KEY, token);
}

async function deleteHttpBearerToken(secretStorage) {
  await secretStorage.delete(HTTP_BEARER_TOKEN_SECRET_KEY);
}

async function buildHttpHeaders(secretStorage, settings) {
  if (settings.httpAuthMode !== 'bearer') {
    return {};
  }

  const token = await getHttpBearerToken(secretStorage);
  if (!token) {
    return {};
  }

  return {
    Authorization: `Bearer ${token}`,
  };
}

module.exports = {
  HTTP_BEARER_TOKEN_SECRET_KEY,
  buildHttpHeaders,
  deleteHttpBearerToken,
  getHttpBearerToken,
  hasHttpBearerToken,
  storeHttpBearerToken,
};