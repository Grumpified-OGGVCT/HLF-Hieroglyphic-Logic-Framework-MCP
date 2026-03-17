# HLF Host Functions Reference

Generated from `governance/host_functions.json`.

Registry version: `1.4.0`

| Name | Args | Returns | Tiers | Gas | Backend | Sensitive |
| --- | --- | --- | --- | --- | --- | --- |
| READ | `path: path` | `string` | hearth, forge, sovereign | 1 | `dapr_file_read` | `false` |
| WRITE | `path: path`, `data: string` | `bool` | hearth, forge, sovereign | 2 | `dapr_file_write` | `false` |
| SPAWN | `image: string`, `env: map` | `string` | forge, sovereign | 5 | `docker_orchestrator` | `false` |
| SLEEP | `ms: int` | `bool` | hearth, forge, sovereign | 0 | `builtin` | `false` |
| HTTP_GET | `url: string` | `string` | forge, sovereign | 3 | `dapr_http_proxy` | `false` |
| HTTP_POST | `url: string`, `body: string` | `string` | forge, sovereign | 5 | `dapr_http_proxy` | `false` |
| WEB_SEARCH | `query: string` | `string` | forge, sovereign | 5 | `dapr_http_proxy` | `true` |
| analyze | `target: string` | `string` | hearth, forge, sovereign | 2 | `builtin` | `false` |
| hash_sha256 | `data: string` | `string` | hearth, forge, sovereign | 2 | `builtin` | `false` |
| merkle_chain | `entry: string` | `string` | hearth, forge, sovereign | 3 | `builtin` | `false` |
| log_emit | `msg: string` | `bool` | hearth, forge, sovereign | 1 | `builtin` | `false` |
| assert_check | `expr: bool` | `bool` | hearth, forge, sovereign | 1 | `builtin` | `false` |
| get_vram | none | `string` | hearth, forge, sovereign | 1 | `builtin` | `false` |
| get_tier | none | `string` | hearth, forge, sovereign | 1 | `builtin` | `false` |
| memory_store | `key: string`, `value: any` | `bool` | hearth, forge, sovereign | 5 | `rag_bridge` | `false` |
| memory_recall | `key: string` | `any` | hearth, forge, sovereign | 5 | `rag_bridge` | `false` |
| vote | `config: string` | `bool` | hearth, forge, sovereign | 1 | `builtin` | `false` |
| delegate | `agent: string`, `goal: string` | `any` | forge, sovereign | 3 | `agent_bridge` | `false` |
| route | `strategy: string` | `any` | forge, sovereign | 2 | `moma_router` | `false` |
| get_timestamp | none | `int` | hearth, forge, sovereign | 1 | `builtin` | `false` |
| generate_ulid | none | `string` | hearth, forge, sovereign | 1 | `builtin` | `false` |
| compress_tokens | `text: string` | `string` | hearth, forge, sovereign | 3 | `hlf_tokenizer` | `false` |
| summarize | `text: string` | `string` | forge, sovereign | 8 | `zai_client` | `false` |
| embed_text | `text: string` | `list` | forge, sovereign | 5 | `zai_client` | `false` |
| cosine_similarity | `a: list`, `b: list` | `float` | hearth, forge, sovereign | 2 | `builtin` | `false` |
| cove_validate | `artifact: any` | `bool` | forge, sovereign | 6 | `cove_engine` | `false` |
| align_verify | `intent: string` | `bool` | hearth, forge, sovereign | 4 | `align_ledger` | `false` |
| z3_verify | `constraints: any` | `bool` | sovereign | 10 | `z3_engine` | `false` |

## Notes

- This file is generated.
- Update the JSON registry first, then regenerate this page.
