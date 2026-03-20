const test = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');

test('resource uri templates list placeholders in order', () => {
  const { getResourceUriPlaceholders } = require(path.join(__dirname, '..', 'src', 'resourceUriTemplate.js'));

  assert.deepEqual(
    getResourceUriPlaceholders('hlf://status/governed_route/{agent_id}/profile/{profile_name}'),
    ['agent_id', 'profile_name'],
  );
});

test('resource uri templates apply URL-encoded values', () => {
  const { applyResourceUriValues } = require(path.join(__dirname, '..', 'src', 'resourceUriTemplate.js'));

  assert.equal(
    applyResourceUriValues('hlf://status/model_catalog/{agent_id}', { agent_id: 'forge/alpha 1' }),
    'hlf://status/model_catalog/forge%2Falpha%201',
  );
});