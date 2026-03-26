# HKS Source Gap Pass 2026-03-23

This document records a source-to-packaged gap pass specifically for HKS-bearing memory, retrieval, and orchestration-adjacent surfaces.

It is a bridge artifact, not a current-truth claim that all upstream HKS architecture has been extracted.

## Source Anchors Reviewed

- [hlf_source/agents/core/context_tiering.py](c:/Users/gerry/generic_workspace/HLF_MCP/hlf_source/agents/core/context_tiering.py)
- [hlf_source/agents/core/memory_scribe.py](c:/Users/gerry/generic_workspace/HLF_MCP/hlf_source/agents/core/memory_scribe.py)
- [hlf_source/agents/core/memory_anchor.py](c:/Users/gerry/generic_workspace/HLF_MCP/hlf_source/agents/core/memory_anchor.py)
- [hlf_source/agents/core/fractal_summarization.py](c:/Users/gerry/generic_workspace/HLF_MCP/hlf_source/agents/core/fractal_summarization.py)
- [hlf_source/agents/core/crew_orchestrator.py](c:/Users/gerry/generic_workspace/HLF_MCP/hlf_source/agents/core/crew_orchestrator.py)
- [hlf_source/agents/core/task_classifier.py](c:/Users/gerry/generic_workspace/HLF_MCP/hlf_source/agents/core/task_classifier.py)

## Packaged Seams Compared

- [hlf_mcp/rag/memory.py](c:/Users/gerry/generic_workspace/HLF_MCP/hlf_mcp/rag/memory.py)
- [hlf_mcp/server_memory.py](c:/Users/gerry/generic_workspace/HLF_MCP/hlf_mcp/server_memory.py)
- [hlf_mcp/server_context.py](c:/Users/gerry/generic_workspace/HLF_MCP/hlf_mcp/server_context.py)
- [hlf_mcp/weekly_artifacts.py](c:/Users/gerry/generic_workspace/HLF_MCP/hlf_mcp/weekly_artifacts.py)

## Constitutive Upstream Patterns

### 1. Context tiering is real upstream architecture

Upstream HKS-bearing code includes explicit cold-to-hot movement via SQLite plus Redis in [hlf_source/agents/core/context_tiering.py](c:/Users/gerry/generic_workspace/HLF_MCP/hlf_source/agents/core/context_tiering.py).

What matters doctrinally is not Redis by itself. The constitutive part is that memory tiering is explicit behavior rather than an implicit storage detail.

### 2. Memory provenance is stronger upstream

[hlf_source/agents/core/memory_anchor.py](c:/Users/gerry/generic_workspace/HLF_MCP/hlf_source/agents/core/memory_anchor.py) binds memory to originating HLF intent and tracks tier, decay, and access patterns as first-class properties.

The constitutive pattern is provenance-linked memory state, not necessarily the exact source implementation.

### 3. Upstream has stronger ingest and retrieval infrastructure

[hlf_source/agents/core/memory_scribe.py](c:/Users/gerry/generic_workspace/HLF_MCP/hlf_source/agents/core/memory_scribe.py) includes vector-aware SQLite writing and a broader schema shape than the packaged memory layer.

The constitutive pattern is broader ingest and retrieval discipline, not the exact sqlite-vec dependency.

### 4. Upstream compression and orchestration surfaces exist near HKS

[hlf_source/agents/core/fractal_summarization.py](c:/Users/gerry/generic_workspace/HLF_MCP/hlf_source/agents/core/fractal_summarization.py), [hlf_source/agents/core/crew_orchestrator.py](c:/Users/gerry/generic_workspace/HLF_MCP/hlf_source/agents/core/crew_orchestrator.py), and [hlf_source/agents/core/task_classifier.py](c:/Users/gerry/generic_workspace/HLF_MCP/hlf_source/agents/core/task_classifier.py) show that HKS-adjacent retrieval was not designed as a thin fact bucket.

These remain bridge inputs rather than automatically packaged requirements, but they do prove the upstream source was already closer to a fuller knowledge substrate than the bounded comparator slice alone.

## Packaged Current Truth

Packaged HKS already has real value:

- SQLite-backed governed memory
- SHA-256 dedup and similarity dedup
- provenance, freshness, and governance fields
- HKS exemplar capture and recall
- local evaluation authority and quarantined external comparison
- weekly artifact hooks

The packaged gap was not “nothing.”

The missing part was explicit acknowledgement that this is still only a subset of the fuller extracted target.

## Highest-Signal Gaps Still Open

| Gap | Upstream signal | Packaged status | Recommendation |
| --- | --- | --- | --- |
| Explicit memory tier behavior | strong | partial | keep extracting via HKS-native memory strata and later tier routing |
| Provenance-anchored memory identity | strong | partial | add intent/provenance linkage as first-class HKS contract field |
| Retrieval orchestration | medium to strong | limited | expand retrieval contracts before importing broader orchestration |
| Compression and archive behavior | medium | absent | add archive/supersession behavior before large-scale ingest |
| Task-aware routing into HKS | medium | absent | bridge later after retrieval contracts are richer |

## Smallest Faithful Next Slice

The smallest faithful next slice was not a broad upstream port.

It was to make explicit HKS memory-tier contracts visible in the packaged product surface first.

That slice has now started in the packaged memory layer by exposing:

- `memory_stratum`
- `storage_tier`
- tier counts through memory stats

This does not complete extraction.

It does make packaged HKS less misleadingly flat and creates a cleaner base for later salience routing, archive behavior, and stronger retrieval contracts.

## Bottom Line

The upstream source was already relatively close to a serious knowledge substrate.

The packaged repo had extracted meaningful HKS pieces, but not the full tiered and orchestration-adjacent substrate.

The right discipline is:

1. keep the three lanes explicit
2. record source-near gaps honestly
3. add constitutive HKS contracts in packaged form before importing larger orchestration machinery
