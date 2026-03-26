# HLF Host Functions Reference

Generated from `governance/host_functions.json`.

Registry version: `1.6.0`

| Name | Args | Returns | Input Schema | Output Schema | Tiers | Gas | Effect | Failure | Audit | Safety | Review | Mode | Supervisory | Backend | Sensitive |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| READ | `path: path` | `string` | `path`:path* | `string` | hearth, forge, sovereign | 1 | `file_read` | `io_error` | `standard` | `none` | `none` | `direct` | `false` | `dapr_file_read` | `false` |
| WRITE | `path: path`, `data: string` | `bool` | `path`:path*, `data`:string* | `boolean` | hearth, forge, sovereign | 2 | `file_write` | `io_error` | `full` | `none` | `none` | `direct` | `false` | `dapr_file_write` | `false` |
| SPAWN | `image: string`, `env: map` | `string` | `image`:string*, `env`:object* | `string` | forge, sovereign | 5 | `process_spawn` | `execution_error` | `full` | `none` | `none` | `direct` | `false` | `docker_orchestrator` | `false` |
| SLEEP | `ms: int` | `bool` | `ms`:integer* | `boolean` | hearth, forge, sovereign | 0 | `timing` | `timeout_error` | `standard` | `none` | `none` | `direct` | `false` | `builtin` | `false` |
| HTTP_GET | `url: string` | `string` | `url`:string* | `string` | forge, sovereign | 3 | `network_read` | `network_error` | `standard` | `none` | `none` | `direct` | `false` | `dapr_http_proxy` | `false` |
| HTTP_POST | `url: string`, `body: string` | `string` | `url`:string*, `body`:string* | `string` | forge, sovereign | 5 | `network_write` | `network_error` | `full` | `none` | `none` | `direct` | `false` | `dapr_http_proxy` | `false` |
| WEB_SEARCH | `query: string` | `string` | `query`:string* | `string` | forge, sovereign | 5 | `web_search` | `network_error` | `sensitive_hash` | `none` | `none` | `direct` | `false` | `dapr_http_proxy` | `true` |
| analyze | `target: string` | `string` | `target`:string* | `string` | hearth, forge, sovereign | 2 | `local_analysis` | `execution_error` | `standard` | `none` | `none` | `direct` | `false` | `builtin` | `false` |
| hash_sha256 | `data: string` | `string` | `data`:string* | `string` | hearth, forge, sovereign | 2 | `cryptographic_hash` | `validation_error` | `standard` | `none` | `none` | `direct` | `false` | `builtin` | `false` |
| merkle_chain | `entry: string` | `string` | `entry`:string* | `string` | hearth, forge, sovereign | 3 | `merkle_append` | `execution_error` | `full` | `none` | `none` | `direct` | `false` | `builtin` | `false` |
| log_emit | `msg: string` | `bool` | `msg`:string* | `boolean` | hearth, forge, sovereign | 1 | `audit_log` | `execution_error` | `full` | `none` | `none` | `direct` | `false` | `builtin` | `false` |
| assert_check | `expr: bool` | `bool` | `expr`:boolean* | `boolean` | hearth, forge, sovereign | 1 | `assertion` | `validation_error` | `standard` | `none` | `none` | `direct` | `false` | `builtin` | `false` |
| get_vram | none | `string` | `object` | `string` | hearth, forge, sovereign | 1 | `environment_read` | `execution_error` | `standard` | `none` | `none` | `direct` | `false` | `builtin` | `false` |
| get_tier | none | `string` | `object` | `string` | hearth, forge, sovereign | 1 | `environment_read` | `execution_error` | `standard` | `none` | `none` | `direct` | `false` | `builtin` | `false` |
| memory_store | `key: string`, `value: any` | `bool` | `key`:string*, `value`:any* | `boolean` | hearth, forge, sovereign | 5 | `memory_write` | `memory_error` | `full` | `none` | `none` | `direct` | `false` | `rag_bridge` | `false` |
| memory_recall | `key: string` | `any` | `key`:string* | `any` | hearth, forge, sovereign | 5 | `memory_read` | `memory_error` | `standard` | `none` | `none` | `direct` | `false` | `rag_bridge` | `false` |
| vote | `config: string` | `bool` | `config`:string* | `boolean` | hearth, forge, sovereign | 1 | `governance_vote` | `governance_error` | `full` | `none` | `none` | `direct` | `false` | `builtin` | `false` |
| delegate | `agent: string`, `goal: string` | `any` | `agent`:string*, `goal`:string* | `any` | forge, sovereign | 3 | `agent_delegation` | `execution_error` | `full` | `none` | `none` | `direct` | `false` | `agent_bridge` | `false` |
| route | `strategy: string` | `any` | `strategy`:string* | `any` | forge, sovereign | 2 | `route_selection` | `policy_denied` | `full` | `none` | `none` | `direct` | `false` | `moma_router` | `false` |
| get_timestamp | none | `int` | `object` | `integer` | hearth, forge, sovereign | 1 | `environment_read` | `execution_error` | `standard` | `none` | `none` | `direct` | `false` | `builtin` | `false` |
| generate_ulid | none | `string` | `object` | `string` | hearth, forge, sovereign | 1 | `environment_read` | `execution_error` | `standard` | `none` | `none` | `direct` | `false` | `builtin` | `false` |
| compress_tokens | `text: string` | `string` | `text`:string* | `string` | hearth, forge, sovereign | 3 | `token_transform` | `execution_error` | `standard` | `none` | `none` | `direct` | `false` | `hlf_tokenizer` | `false` |
| summarize | `text: string` | `string` | `text`:string* | `string` | forge, sovereign | 8 | `model_inference` | `inference_error` | `standard` | `none` | `none` | `direct` | `false` | `zai_client` | `false` |
| embed_text | `text: string` | `list` | `text`:string* | `array` | forge, sovereign | 5 | `embedding_generation` | `inference_error` | `standard` | `none` | `none` | `direct` | `false` | `zai_client` | `false` |
| OCR_EXTRACT | `path: path`, `mode: string` | `map` | `path`:path*, `mode`:string* | `object` | forge, sovereign | 6 | `multimodal_ocr` | `inference_error` | `sensitive_hash` | `none` | `none` | `direct` | `false` | `multimodal_ocr` | `true` |
| IMAGE_SUMMARIZE | `path: path`, `prompt: string` | `string` | `path`:path*, `prompt`:string* | `string` | forge, sovereign | 6 | `multimodal_vision` | `inference_error` | `sensitive_hash` | `none` | `none` | `direct` | `false` | `multimodal_vision` | `true` |
| AUDIO_TRANSCRIBE | `path: path`, `diarize: bool` | `map` | `path`:path*, `diarize`:boolean* | `object` | forge, sovereign | 7 | `multimodal_audio` | `inference_error` | `sensitive_hash` | `none` | `none` | `direct` | `false` | `multimodal_audio` | `true` |
| VIDEO_SUMMARIZE | `path: path`, `prompt: string` | `map` | `path`:path*, `prompt`:string* | `object` | forge, sovereign | 8 | `multimodal_video` | `inference_error` | `sensitive_hash` | `none` | `none` | `direct` | `false` | `multimodal_video` | `true` |
| cosine_similarity | `a: list`, `b: list` | `float` | `a`:array*, `b`:array* | `number` | hearth, forge, sovereign | 2 | `similarity_math` | `validation_error` | `standard` | `none` | `none` | `direct` | `false` | `builtin` | `false` |
| cove_validate | `artifact: any` | `bool` | `artifact`:any* | `boolean` | forge, sovereign | 6 | `verification` | `verification_error` | `full` | `none` | `none` | `direct` | `false` | `cove_engine` | `false` |
| align_verify | `intent: string` | `bool` | `intent`:string* | `boolean` | hearth, forge, sovereign | 4 | `verification` | `policy_denied` | `full` | `none` | `none` | `direct` | `false` | `align_ledger` | `false` |
| z3_verify | `constraints: any` | `bool` | `constraints`:any* | `boolean` | sovereign | 10 | `formal_verification` | `verification_error` | `full` | `none` | `none` | `direct` | `false` | `z3_engine` | `false` |
| SENSOR_READ | `sensor_id: string`, `modality: string`, `read_mode: string`, `max_age_ms: int` | `map` | `sensor_id`:string*, `modality`:string*, `read_mode`:string*, `max_age_ms`:integer* | `object` | forge, sovereign | 4 | `sensor_read` | `io_error` | `standard` | `bounded` | `none` | `simulation_only` | `true` | `embodied_simulation` | `false` |
| WORLD_STATE_RECALL | `world_state_ref: string`, `frame: string`, `max_age_ms: int` | `map` | `world_state_ref`:string*, `frame`:string*, `max_age_ms`:integer* | `object` | forge, sovereign | 4 | `world_state_read` | `memory_error` | `standard` | `bounded` | `none` | `direct` | `true` | `embodied_memory_bridge` | `false` |
| TRAJECTORY_PROPOSE | `envelope: map`, `world_state_ref: string`, `planner_profile: string` | `map` | `envelope`:object*, `world_state_ref`:string*, `planner_profile`:string* | `object` | forge, sovereign | 6 | `trajectory_plan` | `verification_error` | `full` | `high` | `operator_review` | `simulation_only` | `true` | `embodied_simulation` | `false` |
| GUARDED_ACTUATE | `envelope: map`, `evidence_refs: list`, `operator_intent: string` | `map` | `envelope`:object*, `evidence_refs`:array*, `operator_intent`:string* | `object` | forge, sovereign | 8 | `guarded_actuation` | `policy_denied` | `full` | `critical` | `operator_review` | `simulation_only` | `true` | `embodied_simulation` | `false` |
| EMERGENCY_STOP | `reason: string`, `scope: string`, `execution_mode: string` | `map` | `reason`:string*, `scope`:string*, `execution_mode`:string* | `object` | forge, sovereign | 3 | `safety_stop` | `execution_error` | `full` | `critical` | `post_action_review` | `simulation_only` | `true` | `embodied_simulation` | `false` |

## Notes

- This file is generated.
- Update the JSON registry first, then regenerate this page.
