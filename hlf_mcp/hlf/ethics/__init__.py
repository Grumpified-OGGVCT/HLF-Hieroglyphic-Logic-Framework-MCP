"""
HLF Ethical Governor package.

Layers:
  constitution    — C-1 through C-5 hard constitutional constraints
  termination     — self-termination protocol, audit log
  red_hat         — security research declaration pathway
  rogue_detection — compromised / hallucinating agent detection
  governor        — orchestrator: runs all layers, single public API

Primary entry point for the compiler and runtime::

    from hlf_mcp.hlf.ethics.governor import GovernorError, check
    result = check(ast, env, source=normalized, tier=tier)
    result.raise_if_blocked()
"""

from .governor import EthicalGovernor, GovernorError, GovernorResult, check

__all__ = [
    "constitution",
    "termination",
    "red_hat",
    "rogue_detection",
    "governor",
    "EthicalGovernor",
    "GovernorError",
    "GovernorResult",
    "check",
]
