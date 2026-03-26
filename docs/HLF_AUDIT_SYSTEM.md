# HLF Audit System

This document defines a bounded audit system for high-risk work in this repository.

It exists to make important judgments reviewable after the fact without turning ordinary implementation work into paperwork theater.

## 1. Authority Boundary

- [AGENTS.md](../AGENTS.md) defines doctrine.
- [docs/HLF_AGENT_OPERATING_PROTOCOL.md](./HLF_AGENT_OPERATING_PROTOCOL.md) defines operating behavior.
- This document defines when and how to leave backward-verifiable audit artifacts.
- [SSOT_HLF_MCP.md](../SSOT_HLF_MCP.md) remains the executable current-truth surface and should not absorb process boilerplate.

## 2. When Audit Artifacts Are Required

Audit artifacts are required for:

- architectural changes with constitutive-surface implications
- recovery or extraction judgments
- doctrine-sensitive edits
- governance-sensitive edits
- claim-lane-sensitive documentation or summaries
- major reviews that conclude a surface is optional, superseded, misaligned, or wrongly omitted

## 3. When Audit Artifacts Are Not Required

Audit artifacts are not required for:

- routine bugfixes
- narrow implementation edits with no lane ambiguity
- low-risk refactors that do not change doctrine, claim lane, or constitutive-surface judgment

## 4. Audit Artifact Types

Use only the artifacts that materially improve traceability.

- decision record: what was decided and why
- comparison record: what was compared and what was excluded
- measurement record: how capability, trust, or integrity impact was judged
- omission or reconstruction record: what constitutive surface is still missing or downgraded
- review record: the explicit answers to a high-risk review conclusion

## 5. Minimum Contents For Every Artifact

Every audit artifact should state:

- the subject being evaluated
- the lane
- the work type
- the sources consulted
- the conclusion reached
- any material exclusions

Keep these records concise. Precision matters more than volume.

## 6. Exclusion Reporting Rule

If a comparison or review did not cover the full relevant surface, list the exclusions explicitly.

If there were no material exclusions, say so plainly.

Do not imply complete coverage when only partial coverage occurred.

## 7. Comparison Record Rule

A comparison record should state:

- what was compared
- the method used
- the verdict
- what was excluded
- what consequence the comparison has for lane or architecture judgment

## 8. Measurement Rule

Use a measurement record only when judging whether a change materially advances:

- capability
- trust
- doctrine fidelity
- architectural integrity

Do not require a measurement record for every task.

## 9. Omission And Recovery Logging

When a constitutive surface is found to be missing, downgraded, or wrongly replaced, record that judgment in a bounded way and cross-reference existing recovery authorities such as [docs/HLF_REJECTED_EXTRACTION_AUDIT.md](./HLF_REJECTED_EXTRACTION_AUDIT.md).

Do not fork a second sprawling omission doctrine when an existing audit surface already carries the core history.

## 10. Backward Verification Procedure

To verify a high-risk task after the fact:

1. identify the task, lane, and work type
2. check whether required comparison or decision artifacts exist
3. check whether exclusions were stated
4. check whether wording stayed in the correct lane
5. reject any result that silently upgraded maturity or flattened a constitutive surface without evidence

## 11. Storage And Naming Guidance

Keep audit records in one predictable location if adopted operationally.

Recommended pattern:

- `docs/audit/` for repo-shared records
- short, dated filenames when the record needs stable later reference

Do not generate files merely to satisfy ceremony.

## 12. Anti-Bureaucracy Clause

This audit system exists to preserve architectural truth, traceability, and governed leverage.

If an artifact does not improve reviewability or future correction quality, do not create it.

## 13. Compact Templates

### Decision record

- subject
- lane
- work type
- sources consulted
- conclusion
- exclusions

### Comparison record

- item A
- item B
- method
- verdict
- exclusions

### Review record

- claim lane
- constitutive-surface judgment
- trust and legibility judgment
- capability versus tidiness judgment
