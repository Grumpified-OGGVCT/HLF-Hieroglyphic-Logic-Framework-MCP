---
goal: Define the measured benchmark path for promoting full-language HLF lanes without projecting winners in advance
version: 1.0
date_created: 2026-03-18
last_updated: 2026-03-18
owner: GitHub Copilot
status: In progress
tags: [bridge, multilingual, benchmarking, chinese, language-evolution, governance]
---

# HLF Language Promotion Benchmark Spec

## 1. Purpose

This document defines how full-language HLF lanes are promoted.

Promotion must be earned by measured results.

It is not enough for a language to be elegant, dense, or theoretically attractive.

## 2. Current Packaged Truth

The current packaged translator and multilingual benchmark lane materially support:

- English (`en`)
- French (`fr`)
- Spanish (`es`)
- Arabic (`ar`)
- Chinese (`zh`)

These are the only languages that should currently appear in packaged benchmark claims.

Russian and German are reasonable future candidates, but they are not current packaged translator or benchmark truth.

## 3. Promotion Principle

Language promotion uses a shared canonical executable HLF core.

Languages compete as ingress, egress, retrieval, and cognitive-substrate lanes under one trust contract.

That means:

- no language becomes a private dialect
- no language is promoted on projection alone
- no language bypasses audit, verifier, and recovery obligations

## 4. Benchmark Categories

Every supported language lane should be measured on at least these signals:

1. compression percentage against natural-language source
2. round-trip fidelity after translation into canonical HLF
3. fallback rate
4. semantic loss flags
5. reverse-summary quality
6. retrieval alignment for multilingual memory and exemplars
7. routing fitness for specialist-lane dispatch

## 5. Ranking Rule

Until a richer evaluation layer exists, benchmark comparisons should rank languages in this order:

1. highest round-trip fidelity
2. lowest fallback rate
3. highest compression

This keeps promotion tied to correctness first, then stability, then efficiency.

## 6. Staged Full-Lane Sequence

The current bridge sequence for full-language maturation is:

1. full English lane
2. full French lane
3. full Chinese lane
4. full Spanish lane
5. then additional major languages such as Russian and German once they are actually implemented and benchmarked

This sequence is a build order, not a claim that English or French are intrinsically superior substrates.

Chinese remains the most important near-term compression candidate to test aggressively, because it is the strongest current natural-language contender for dense cHLF-style payloads.

## 7. Immediate Build Obligations

1. Maintain explicit Chinese coverage in multilingual benchmark regression tests.
2. Expose measured language comparison summaries instead of relying on prose judgments.
3. Keep unsupported future languages out of packaged benchmark claims until templates, translator handling, and tests exist.
4. Extend retrieval and routing evaluations before promoting any language as the preferred cognitive substrate.

## 8. Bottom Line

The repo should expand by quantified comparison.

Chinese is not being undercounted if it is included as a measured lane and allowed to win on evidence.

The failure mode to avoid is pretending that future languages are already implemented, or that a language has won before multilingual proof exists.

The launch-bounded completion contract for the Chinese-enhanced lane is defined in [docs/HLF_CHINESE_COGNITIVE_LANE_LAUNCH_CRITERIA.md](c:/Users/gerry/generic_workspace/HLF_MCP/docs/HLF_CHINESE_COGNITIVE_LANE_LAUNCH_CRITERIA.md).