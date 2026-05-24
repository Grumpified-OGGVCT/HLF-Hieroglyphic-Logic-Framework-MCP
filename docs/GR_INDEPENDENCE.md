# GrumpRolled Independence Declaration

Date: 2026-05-23
Status: Design constraint — enforced for all future GrumpRolled development

## Principle

**GrumpRolled must remain useful without SwarmGlass installed.**

GrumpRolled can discuss, ingest, benchmark, and display SwarmGlass outputs, but must not depend on SwarmGlass for its own core value proposition.

## Why

The original HLF_MCP → GrumpRolled relationship was a dependency mistake: GrumpRolled's documentation and product framing became dependent on HLF as its coordination thesis. When the benchmarks disproved that thesis, both products were affected.

This declaration prevents repeating that mistake with a new name.

## What This Means

### GrumpRolled CAN:
- Display SwarmGlass governance reports as one of many supported formats
- Run SwarmGlass benchmarks as part of a broader benchmark suite
- Reference SwarmGlass as an optional governance layer in documentation
- Import and visualize SwarmGlass audit trails
- Offer a "connect SwarmGlass" integration as an opt-in feature

### GrumpRolled CANNOT:
- Require SwarmGlass to be installed for core functionality
- Present SwarmGlass as the default or required governance solution
- Hard-code SwarmGlass API contracts into its core data model
- Fail to start if SwarmGlass is not available
- Use SwarmGlass-specific terminology in its primary user interface

## Technical Implementation

- SwarmGlass integration lives behind an optional feature flag or plugin interface
- GrumpRolled's core data model is coordination-agnostic
- All SwarmGlass references in GrumpRolled code use late-binding imports
- SwarmGlass-specific features degrade gracefully when not installed

## Relationship to the Migration

This declaration takes effect immediately, even though the SwarmGlass backend migration proceeds in phases. GrumpRolled documentation and product framing should become coordination-agnostic as soon as Gate 1 validates the pivot direction, without waiting for the full migration to complete.
