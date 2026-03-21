const GOVERNANCE_ACTION_POLICY = Object.freeze({
  active: ['revoke', 'tombstone'],
  stale: ['revoke', 'tombstone'],
  superseded: ['revoke', 'tombstone'],
  revoked: ['reinstate'],
  tombstoned: ['reinstate'],
  unknown: ['revoke', 'tombstone'],
});

function normalizeGovernanceState(state) {
  const normalized = String(state || '').trim().toLowerCase();
  return normalized || 'unknown';
}

function getAllowedGovernanceActions(target) {
  const state = normalizeGovernanceState(target?.state ?? target?.governance_status);
  return [...(GOVERNANCE_ACTION_POLICY[state] || GOVERNANCE_ACTION_POLICY.unknown)];
}

function isGovernanceActionAllowed(target, action) {
  const normalizedAction = String(action || '').trim().toLowerCase();
  if (!normalizedAction) {
    return false;
  }
  return getAllowedGovernanceActions(target).includes(normalizedAction);
}

module.exports = {
  getAllowedGovernanceActions,
  isGovernanceActionAllowed,
  normalizeGovernanceState,
};