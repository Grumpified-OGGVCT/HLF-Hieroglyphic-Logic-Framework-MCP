const path = require('node:path');

const CLAIM_LANES = [
  {
    id: 'current-true',
    title: 'Current-True',
    description: 'Implemented and validated packaged truth that is safe to assert now.',
    operatorSummary: 'SwarmGlass is the outward product surface; HLF is the deterministic language engine inside.',
  },
  {
    id: 'bridge-true',
    title: 'Bridge-True',
    description: 'Bounded convergence work that is real, but not full target-state completion.',
    operatorSummary: 'Use for the VS Code bridge shell, staged operator surfaces, and bounded launch or attach workflows.',
  },
  {
    id: 'vision-true',
    title: 'Vision-True',
    description: 'North-star doctrine that remains constitutive even when not fully shipped yet.',
    operatorSummary: 'Use for the larger governed HLF language and operator-shell target, not present-tense product claims.',
  },
];

const CLAIM_GUARDRAILS = [
  'Do not present the extension as a second HLF implementation line.',
  'Do not present the current operator shell as full target-state GUI completion.',
  'Do not collapse HLF into only the packaged MCP bridge or only the extension surface.',
  'SwarmGlass is the outward product brand; HLF is the internal governed language engine. Do not swap or confuse these surfaces.',
  'The sg_* MCP tool namespace is canonical for the outward SwarmGlass surface. The hlf_* namespace is a backward-compat alias.',
];

function getClaimLanePanelEntries() {
  return CLAIM_LANES.map((lane) => ({
    label: lane.id,
    description: lane.title,
    tooltip: `${lane.description}\n${lane.operatorSummary}`,
  }));
}

function getClaimLaneSections() {
  return [
    {
      title: 'Current-True',
      subtitle: 'Safe present-tense packaged truth.',
      body: [
        'SwarmGlass is the outward product surface exposed through sg_* MCP tools and sg:// resource URIs.',
        'Packaged hlf_mcp server remains the implementation authority for the HLF language engine.',
        'Bridge diagnostics, launch or attach state, and packaged action commands are current extension truth.',
      ],
    },
    {
      title: 'Bridge-True',
      subtitle: 'Bounded convergence surface inside VS Code.',
      body: [
        'This extension is a governed bridge shell over packaged truth, not a claim of full operator-shell completion.',
        'Local stdio launch and attached HTTP workflows are credible bridge lanes when diagnostics and packaged surfaces remain explicit.',
        'sg_* tools are canonical; hlf_* tools are backward-compat aliases within the bridge surface.',
      ],
    },
    {
      title: 'Vision-True',
      subtitle: 'North-star operator and language doctrine.',
      body: [
        'HLF is intended to become a governed meaning and execution substrate larger than the current MCP packaging.',
        'Full operator GUI, broader governance surfaces, and deeper coordination layers remain target-state work.',
        'SwarmGlass as an outward product may grow beyond the current HLF-scoped MCP surface over time.',
      ],
    },
    {
      title: 'Brand Boundary',
      subtitle: 'SwarmGlass outward, HLF internal engine.',
      body: [
        'SwarmGlass is the outward product brand and user-facing surface.',
        'HLF (Hieroglyphic Logic Framework) is the deterministic language engine inside SwarmGlass.',
        'The sg_* MCP tool namespace is canonical for SwarmGlass product surface.',
        'The hlf_* MCP tool namespace is a backward-compat alias, not a competing surface.',
        'sg:// is the canonical SwarmGlass resource URI scheme; hlf:// is forward-mapped to it.',
      ],
    },
    {
      title: 'Guardrails',
      subtitle: 'Reject overclaiming and reductionist wording.',
      body: CLAIM_GUARDRAILS,
    },
  ];
}

function getClaimLanesDocPath(workspaceRoot) {
  if (!workspaceRoot) {
    return undefined;
  }

  return path.join(workspaceRoot, 'docs', 'HLF_CLAIM_LANES.md');
}

module.exports = {
  CLAIM_GUARDRAILS,
  CLAIM_LANES,
  getClaimLanePanelEntries,
  getClaimLaneSections,
  getClaimLanesDocPath,
};