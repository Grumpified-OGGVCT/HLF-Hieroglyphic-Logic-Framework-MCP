# HLF Tag Reference

Generated from `governance/templates/dictionary.json` (version 0.4.0).

| Tag | Arity | Arguments | Traits |
| --- | --- | --- | --- |
| `INTENT` | 2 | `action:string, target:path` | - |
| `THOUGHT` | 1 | `reasoning:string` | pure |
| `OBSERVATION` | 1 | `data:any` | pure |
| `PLAN` | 1+ | `steps:any[]` | - |
| `CONSTRAINT` | 2 | `key:string, value:any` | - |
| `EXPECT` | 1 | `outcome:string` | - |
| `ACTION` | 2+ | `verb:string, args:any[]` | - |
| `SET` | 2 | `name:identifier, value:any` | immutable |
| `FUNCTION` | 2+ | `name:identifier, args:any[]` | pure |
| `DELEGATE` | 2 | `role:identifier, intent:string` | - |
| `VOTE` | 2 | `decision:bool, rationale:string` | - |
| `ASSERT` | 2 | `condition:bool, error:string` | - |
| `RESULT` | 2 | `code:int, message:string` | terminator |
| `MODULE` | 1 | `name:identifier` | - |
| `IMPORT` | 1 | `name:identifier` | - |
| `DATA` | 1 | `id:string` | - |
| `MEMORY` | 3 | `entity:string, content:any, confidence:any` | - |
| `RECALL` | 2 | `entity:string, top_k:int` | - |
| `DEFINE` | 2 | `name:string, body:any` | macro |
| `CALL` | 2+ | `name:string, args:any[]` | - |
| `WHILE` | 2+ | `condition:string, body:any[]` | - |
| `TRY` | 1+ | `body:any[]` | - |
| `CATCH` | 1+ | `handler:any[]` | - |
| `RETURN` | 1 | `value:any` | - |
| `CAPSULE` | 2 | `name:identifier, bounds:any` | - |
| `ROUTE` | 2 | `strategy:string, target:any` | - |
| `SOURCE` | 2 | `path:path, provenance:any` | - |
| `PARAM` | 2 | `name:identifier, value:any` | - |
| `PRIORITY` | 2 | `level:string, weight:any` | - |
| `GATE` | 2 | `policy:string, decision:bool` | - |
| `PROVENANCE` | 3 | `source:string, confidence:any, lineage:any` | - |
| `GOVERNANCE` | 2 | `policy:string, action:string` | - |
| `CODE` | 2 | `language:string, body:string` | - |
| `RELATE` | 3 | `relation:string, from:identifier, to:identifier` | - |
| `SPEC` | 2 | `name:string, body:any` | - |
| `SPEC_DEFINE` | 2 | `name:string, body:any` | - |
| `SPEC_GATE` | 2 | `name:string, condition:any` | - |
| `SPEC_UPDATE` | 2 | `name:string, patch:any` | - |
| `SPEC_SEAL` | 2 | `name:string, proof:any` | terminator |
