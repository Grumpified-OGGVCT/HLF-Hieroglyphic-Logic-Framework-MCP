---
goal: Define the full qualification, launch, and promotion requirements for models used in HLF lanes, including benchmark thresholds and language compatibility
version: 1.0
date_created: 2026-03-18
last_updated: 2026-03-18
owner: GitHub Copilot
status: In progress
tags: [bridge, models, routing, multilingual, benchmarking, governance, launch]
---

# HLF Model Qualification And Promotion Spec

## 1. Purpose

This document defines the full qualification doctrine for models used in HLF lanes.

The question is not merely whether a model can run.

The repo needs to know:

- whether a model is only advisory
- whether it is baseline-qualified
- whether it is launch-qualified
- whether it is promotion-qualified for preferred-lane status

## 2. Qualification Dimensions

Every model evaluation must consider all of the following dimensions:

1. lane compatibility
2. capability compatibility
3. language compatibility for the user-selected language set
4. benchmark performance for the intended workload
5. reachability under the chosen execution path
6. practicality on the detected hardware

## 3. Language Compatibility Rule

If the user intends to run a multilingual lane that includes Chinese, then a model that only supports English is not launch-qualified for that lane.

This remains true even if the model is otherwise fast, available, or strong on English-only benchmarks.

## 4. Tier Definitions

### 4.1 Advisory-only

The model can be discussed, compared, or used as a non-authoritative option, but it does not clear the operational bar for the declared lane and language set.

### 4.2 Baseline-qualified

The model clears the floor for lane, capability, language, and baseline benchmark scores.

This tier is suitable for bounded use and further evaluation.

### 4.3 Launch-qualified

The model clears the lane, language, and benchmark bar required for launch use in the declared workload.

This is the correct tier for shipping behavior.

### 4.4 Promotion-qualified

The model clears stricter benchmark thresholds and may be considered for preferred-lane or default-lane promotion.

This tier is intentionally harder to earn than launch qualification.

## 5. Benchmark Rule

The repo should allow lane-specific thresholds such as:

- translation fidelity
- retrieval quality
- routing quality
- sidecar quality
- verifier accuracy

No model should be promoted into a preferred lane unless it clears the promotion threshold, not just the launch threshold.

## 6. Current Packaged Enforcement Surface

The packaged evaluator now supports:

- explicit lane requirements
- explicit capability requirements
- explicit language requirements
- explicit benchmark thresholds
- reachability checks
- practicality checks
- qualification-tier resolution

This should be used through the synced model catalog workflow whenever operators or agents need to judge whether a model is merely available or actually fit for the intended workload.

## 7. Example Qualification Contract

For a Chinese-capable translation-memory lane, a realistic tiered contract may look like:

- required lane: `retrieval`
- required capabilities: `embedding`, `semantic-recall`
- required languages: `en`, `zh`

Baseline:
- `translation_fidelity >= 0.85`

Launch:
- `translation_fidelity >= 0.90`
- `routing_quality >= 0.80`

Promotion:
- `translation_fidelity >= 0.97`
- `routing_quality >= 0.90`

## 8. Bottom Line

This repo should judge models by full qualification doctrine, not by whether they merely run and not by a reductive MVP-style floor.

The operative question is:

Does this model clear the correct tier for the workload, the lane, and the languages the user actually intends to run?