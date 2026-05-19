"""Add idempotence, retry_policy, and sandbox_profile to host_functions.json."""
import json
from collections import Counter

with open("governance/host_functions.json", "r") as f:
    data = json.load(f)

# Effect class → (idempotence, retry_policy, sandbox_profile)
EFFECT_DECLARATIONS = {
    "file_read": {
        "idempotence": "idempotent",
        "retry_policy": {"max_retries": 3, "backoff_ms": 500, "jitter_ms": 100, "strategy": "exponential"},
        "sandbox_profile": {"network": "deny", "filesystem": "read_only", "process_spawn": "deny", "memory_limit_mb": 64, "timeout_ms": 10000},
    },
    "file_write": {
        "idempotence": "conditional",
        "retry_policy": {"max_retries": 2, "backoff_ms": 1000, "jitter_ms": 200, "strategy": "linear"},
        "sandbox_profile": {"network": "deny", "filesystem": "read_write", "process_spawn": "deny", "memory_limit_mb": 128, "timeout_ms": 15000},
    },
    "process_spawn": {
        "idempotence": "not_idempotent",
        "retry_policy": {"max_retries": 1, "backoff_ms": 2000, "jitter_ms": 500, "strategy": "none"},
        "sandbox_profile": {"network": "isolated", "filesystem": "read_write", "process_spawn": "allow", "memory_limit_mb": 512, "timeout_ms": 60000},
    },
    "timing": {
        "idempotence": "idempotent",
        "retry_policy": {"max_retries": 2, "backoff_ms": 100, "jitter_ms": 50, "strategy": "linear"},
        "sandbox_profile": {"network": "deny", "filesystem": "deny", "process_spawn": "deny", "memory_limit_mb": 16, "timeout_ms": 5000},
    },
    "network_read": {
        "idempotence": "idempotent",
        "retry_policy": {"max_retries": 3, "backoff_ms": 1000, "jitter_ms": 300, "strategy": "exponential"},
        "sandbox_profile": {"network": "outbound_only", "filesystem": "deny", "process_spawn": "deny", "memory_limit_mb": 64, "timeout_ms": 30000},
    },
    "network_write": {
        "idempotence": "not_idempotent",
        "retry_policy": {"max_retries": 2, "backoff_ms": 1500, "jitter_ms": 300, "strategy": "exponential"},
        "sandbox_profile": {"network": "outbound_only", "filesystem": "deny", "process_spawn": "deny", "memory_limit_mb": 128, "timeout_ms": 30000},
    },
    "web_search": {
        "idempotence": "idempotent",
        "retry_policy": {"max_retries": 2, "backoff_ms": 2000, "jitter_ms": 500, "strategy": "exponential"},
        "sandbox_profile": {"network": "outbound_only", "filesystem": "deny", "process_spawn": "deny", "memory_limit_mb": 128, "timeout_ms": 30000},
    },
    "local_analysis": {
        "idempotence": "idempotent",
        "retry_policy": {"max_retries": 2, "backoff_ms": 500, "jitter_ms": 100, "strategy": "linear"},
        "sandbox_profile": {"network": "deny", "filesystem": "read_only", "process_spawn": "deny", "memory_limit_mb": 128, "timeout_ms": 15000},
    },
    "cryptographic_hash": {
        "idempotence": "idempotent",
        "retry_policy": {"max_retries": 3, "backoff_ms": 200, "jitter_ms": 50, "strategy": "linear"},
        "sandbox_profile": {"network": "deny", "filesystem": "deny", "process_spawn": "deny", "memory_limit_mb": 64, "timeout_ms": 10000},
    },
    "merkle_append": {
        "idempotence": "conditional",
        "retry_policy": {"max_retries": 2, "backoff_ms": 1000, "jitter_ms": 200, "strategy": "exponential"},
        "sandbox_profile": {"network": "deny", "filesystem": "read_write", "process_spawn": "deny", "memory_limit_mb": 128, "timeout_ms": 15000},
    },
    "audit_log": {
        "idempotence": "idempotent",
        "retry_policy": {"max_retries": 3, "backoff_ms": 500, "jitter_ms": 100, "strategy": "exponential"},
        "sandbox_profile": {"network": "deny", "filesystem": "append_only", "process_spawn": "deny", "memory_limit_mb": 64, "timeout_ms": 5000},
    },
    "assertion": {
        "idempotence": "idempotent",
        "retry_policy": {"max_retries": 3, "backoff_ms": 100, "jitter_ms": 50, "strategy": "linear"},
        "sandbox_profile": {"network": "deny", "filesystem": "deny", "process_spawn": "deny", "memory_limit_mb": 32, "timeout_ms": 5000},
    },
    "environment_read": {
        "idempotence": "idempotent",
        "retry_policy": {"max_retries": 2, "backoff_ms": 500, "jitter_ms": 100, "strategy": "linear"},
        "sandbox_profile": {"network": "deny", "filesystem": "deny", "process_spawn": "deny", "memory_limit_mb": 32, "timeout_ms": 5000},
    },
    "memory_write": {
        "idempotence": "conditional",
        "retry_policy": {"max_retries": 2, "backoff_ms": 1000, "jitter_ms": 200, "strategy": "exponential"},
        "sandbox_profile": {"network": "deny", "filesystem": "read_write", "process_spawn": "deny", "memory_limit_mb": 128, "timeout_ms": 10000},
    },
    "memory_read": {
        "idempotence": "idempotent",
        "retry_policy": {"max_retries": 3, "backoff_ms": 500, "jitter_ms": 100, "strategy": "linear"},
        "sandbox_profile": {"network": "deny", "filesystem": "read_only", "process_spawn": "deny", "memory_limit_mb": 64, "timeout_ms": 10000},
    },
    "governance_vote": {
        "idempotence": "not_idempotent",
        "retry_policy": {"max_retries": 1, "backoff_ms": 500, "jitter_ms": 100, "strategy": "none"},
        "sandbox_profile": {"network": "deny", "filesystem": "append_only", "process_spawn": "deny", "memory_limit_mb": 32, "timeout_ms": 10000},
    },
    "agent_delegation": {
        "idempotence": "not_idempotent",
        "retry_policy": {"max_retries": 2, "backoff_ms": 2000, "jitter_ms": 500, "strategy": "exponential"},
        "sandbox_profile": {"network": "internal_only", "filesystem": "read_write", "process_spawn": "allow", "memory_limit_mb": 256, "timeout_ms": 60000},
    },
    "route_selection": {
        "idempotence": "idempotent",
        "retry_policy": {"max_retries": 2, "backoff_ms": 500, "jitter_ms": 100, "strategy": "linear"},
        "sandbox_profile": {"network": "deny", "filesystem": "deny", "process_spawn": "deny", "memory_limit_mb": 32, "timeout_ms": 5000},
    },
    "token_transform": {
        "idempotence": "idempotent",
        "retry_policy": {"max_retries": 2, "backoff_ms": 500, "jitter_ms": 100, "strategy": "linear"},
        "sandbox_profile": {"network": "deny", "filesystem": "deny", "process_spawn": "deny", "memory_limit_mb": 64, "timeout_ms": 15000},
    },
    "model_inference": {
        "idempotence": "idempotent",
        "retry_policy": {"max_retries": 2, "backoff_ms": 2000, "jitter_ms": 500, "strategy": "exponential"},
        "sandbox_profile": {"network": "outbound_only", "filesystem": "deny", "process_spawn": "deny", "memory_limit_mb": 256, "timeout_ms": 60000},
    },
    "embedding_generation": {
        "idempotence": "idempotent",
        "retry_policy": {"max_retries": 2, "backoff_ms": 1500, "jitter_ms": 300, "strategy": "exponential"},
        "sandbox_profile": {"network": "outbound_only", "filesystem": "deny", "process_spawn": "deny", "memory_limit_mb": 256, "timeout_ms": 45000},
    },
    "multimodal_ocr": {
        "idempotence": "idempotent",
        "retry_policy": {"max_retries": 2, "backoff_ms": 2000, "jitter_ms": 500, "strategy": "exponential"},
        "sandbox_profile": {"network": "deny", "filesystem": "read_only", "process_spawn": "deny", "memory_limit_mb": 512, "timeout_ms": 60000},
    },
    "multimodal_vision": {
        "idempotence": "idempotent",
        "retry_policy": {"max_retries": 2, "backoff_ms": 2000, "jitter_ms": 500, "strategy": "exponential"},
        "sandbox_profile": {"network": "deny", "filesystem": "read_only", "process_spawn": "deny", "memory_limit_mb": 512, "timeout_ms": 60000},
    },
    "multimodal_audio": {
        "idempotence": "idempotent",
        "retry_policy": {"max_retries": 2, "backoff_ms": 2000, "jitter_ms": 500, "strategy": "exponential"},
        "sandbox_profile": {"network": "deny", "filesystem": "read_only", "process_spawn": "deny", "memory_limit_mb": 512, "timeout_ms": 60000},
    },
    "multimodal_video": {
        "idempotence": "idempotent",
        "retry_policy": {"max_retries": 2, "backoff_ms": 3000, "jitter_ms": 500, "strategy": "exponential"},
        "sandbox_profile": {"network": "deny", "filesystem": "read_only", "process_spawn": "deny", "memory_limit_mb": 1024, "timeout_ms": 120000},
    },
    "similarity_math": {
        "idempotence": "idempotent",
        "retry_policy": {"max_retries": 3, "backoff_ms": 200, "jitter_ms": 50, "strategy": "linear"},
        "sandbox_profile": {"network": "deny", "filesystem": "deny", "process_spawn": "deny", "memory_limit_mb": 64, "timeout_ms": 5000},
    },
    "verification": {
        "idempotence": "idempotent",
        "retry_policy": {"max_retries": 2, "backoff_ms": 500, "jitter_ms": 100, "strategy": "linear"},
        "sandbox_profile": {"network": "deny", "filesystem": "read_only", "process_spawn": "deny", "memory_limit_mb": 128, "timeout_ms": 15000},
    },
    "formal_verification": {
        "idempotence": "idempotent",
        "retry_policy": {"max_retries": 2, "backoff_ms": 1000, "jitter_ms": 200, "strategy": "exponential"},
        "sandbox_profile": {"network": "deny", "filesystem": "read_only", "process_spawn": "deny", "memory_limit_mb": 512, "timeout_ms": 60000},
    },
    "sensor_read": {
        "idempotence": "idempotent",
        "retry_policy": {"max_retries": 3, "backoff_ms": 500, "jitter_ms": 100, "strategy": "exponential"},
        "sandbox_profile": {"network": "deny", "filesystem": "deny", "process_spawn": "deny", "memory_limit_mb": 64, "timeout_ms": 15000},
    },
    "world_state_read": {
        "idempotence": "idempotent",
        "retry_policy": {"max_retries": 3, "backoff_ms": 500, "jitter_ms": 100, "strategy": "linear"},
        "sandbox_profile": {"network": "deny", "filesystem": "read_only", "process_spawn": "deny", "memory_limit_mb": 128, "timeout_ms": 15000},
    },
    "trajectory_plan": {
        "idempotence": "idempotent",
        "retry_policy": {"max_retries": 2, "backoff_ms": 1000, "jitter_ms": 300, "strategy": "linear"},
        "sandbox_profile": {"network": "deny", "filesystem": "read_only", "process_spawn": "deny", "memory_limit_mb": 256, "timeout_ms": 30000},
    },
    "guarded_actuation": {
        "idempotence": "not_idempotent",
        "retry_policy": {"max_retries": 0, "backoff_ms": 0, "jitter_ms": 0, "strategy": "none"},
        "sandbox_profile": {"network": "deny", "filesystem": "deny", "process_spawn": "deny", "memory_limit_mb": 128, "timeout_ms": 15000},
    },
    "safety_stop": {
        "idempotence": "idempotent",
        "retry_policy": {"max_retries": 0, "backoff_ms": 0, "jitter_ms": 0, "strategy": "none"},
        "sandbox_profile": {"network": "deny", "filesystem": "deny", "process_spawn": "deny", "memory_limit_mb": 32, "timeout_ms": 5000},
    },
}


def get_default_declaration():
    return {
        "idempotence": "unknown",
        "retry_policy": {"max_retries": 2, "backoff_ms": 1000, "jitter_ms": 200, "strategy": "exponential"},
        "sandbox_profile": {"network": "deny", "filesystem": "deny", "process_spawn": "deny", "memory_limit_mb": 128, "timeout_ms": 30000},
    }


count = 0
for fn in data["functions"]:
    effect = fn.get("effect_class", "")
    decl = EFFECT_DECLARATIONS.get(effect, get_default_declaration())
    fn["idempotence"] = decl["idempotence"]
    fn["retry_policy"] = decl["retry_policy"]
    fn["sandbox_profile"] = decl["sandbox_profile"]
    count += 1

data["version"] = "1.7.0"
data["effect_schema_version"] = 1

with open("governance/host_functions.json", "w") as f:
    json.dump(data, f, indent=2)

print(f"Added effect declarations to {count} functions")
print(f"Version: {data['version']}")

idem = Counter(fn["idempotence"] for fn in data["functions"])
print(f"Idempotence distribution: {dict(idem)}")

# Verify file is valid JSON
with open("governance/host_functions.json", "r") as f:
    json.load(f)
print("File is valid JSON")
