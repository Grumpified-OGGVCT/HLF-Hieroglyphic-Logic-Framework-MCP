from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal
from urllib.parse import urlparse


AccessMode = Literal[
    "local-via-ollama",
    "cloud-via-ollama",
    "remote-direct",
    "registry-known-not-configured",
]


@dataclass(slots=True, frozen=True)
class ModelSpec:
    name: str
    family: str
    lanes: tuple[str, ...]
    capabilities: tuple[str, ...]
    min_vram_gb: float = 0.0
    requires_local: bool = False
    privacy_preserving: bool = False
    notes: tuple[str, ...] = ()


@dataclass(slots=True)
class ModelCatalogEntry:
    name: str
    family: str
    lanes: list[str]
    capabilities: list[str]
    access_mode: AccessMode
    endpoint: str
    installed: bool
    reachable: bool
    pullable: bool
    configured: bool
    known_but_impractical: bool
    requires_local: bool
    privacy_preserving: bool
    min_vram_gb: float
    rationale: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "family": self.family,
            "lanes": list(self.lanes),
            "capabilities": list(self.capabilities),
            "access_mode": self.access_mode,
            "endpoint": self.endpoint,
            "installed": self.installed,
            "reachable": self.reachable,
            "pullable": self.pullable,
            "configured": self.configured,
            "known_but_impractical": self.known_but_impractical,
            "requires_local": self.requires_local,
            "privacy_preserving": self.privacy_preserving,
            "min_vram_gb": self.min_vram_gb,
            "rationale": list(self.rationale),
        }


_DEFAULT_MODEL_SPECS: tuple[ModelSpec, ...] = (
    ModelSpec(
        name="embeddinggemma",
        family="embedding",
        lanes=("retrieval", "explainer"),
        capabilities=("embedding", "local-embedding", "privacy-preserving"),
        requires_local=True,
        privacy_preserving=True,
        notes=("Strong default for privacy-preserving retrieval.",),
    ),
    ModelSpec(
        name="all-minilm",
        family="embedding",
        lanes=("retrieval",),
        capabilities=("embedding", "lightweight"),
        requires_local=True,
        privacy_preserving=True,
        notes=("Useful fallback for CPU-only retrieval lanes.",),
    ),
    ModelSpec(
        name="nomic-embed-text-v2-moe",
        family="embedding",
        lanes=("retrieval", "standards-ingestion"),
        capabilities=("embedding", "multilingual", "semantic-recall"),
        min_vram_gb=10.0,
        requires_local=True,
        privacy_preserving=True,
        notes=("Stronger multilingual retrieval when local GPU capacity is available.",),
    ),
    ModelSpec(
        name="bge-m3",
        family="embedding",
        lanes=("retrieval", "standards-ingestion"),
        capabilities=("embedding", "long-context", "semantic-recall"),
        min_vram_gb=10.0,
        requires_local=True,
        privacy_preserving=True,
    ),
    ModelSpec(
        name="mxbai-embed-large",
        family="embedding",
        lanes=("retrieval", "code-generation"),
        capabilities=("embedding", "code-retrieval"),
        min_vram_gb=4.0,
        requires_local=True,
        privacy_preserving=True,
    ),
    ModelSpec(
        name="granite-embedding:30m",
        family="embedding",
        lanes=("retrieval",),
        capabilities=("embedding", "lightweight"),
        requires_local=True,
        privacy_preserving=True,
    ),
    ModelSpec(
        name="qwen3-embedding:4b",
        family="embedding",
        lanes=("retrieval", "standards-ingestion"),
        capabilities=("embedding", "long-context", "multilingual"),
        min_vram_gb=12.0,
        requires_local=True,
        privacy_preserving=True,
    ),
    ModelSpec(
        name="qwen3:8b",
        family="reasoning",
        lanes=("code-generation", "verifier", "explainer"),
        capabilities=("reasoning", "coding", "explanations"),
        min_vram_gb=8.0,
        notes=("Useful general reasoning lane through Ollama-compatible endpoints.",),
    ),
    ModelSpec(
        name="llama3.1:8b",
        family="reasoning",
        lanes=("code-generation", "explainer"),
        capabilities=("reasoning", "coding", "generalist"),
        min_vram_gb=8.0,
    ),
    ModelSpec(
        name="gemma3:12b",
        family="reasoning",
        lanes=("standards-ingestion", "explainer"),
        capabilities=("reasoning", "analysis", "long-context"),
        min_vram_gb=10.0,
    ),
    ModelSpec(
        name="devstral:24b",
        family="reasoning",
        lanes=("code-generation", "verifier"),
        capabilities=("reasoning", "coding", "review"),
        min_vram_gb=16.0,
        notes=("Stronger coding and verification lane when reachable via cloud-via-ollama.",),
    ),
    ModelSpec(
        name="llava:7b",
        family="multimodal",
        lanes=("multimodal", "explainer"),
        capabilities=("vision", "multimodal", "explanations"),
        min_vram_gb=10.0,
    ),
)


_ROLE_LANES: dict[str, tuple[str, ...]] = {
    "retriever": ("retrieval", "standards-ingestion"),
    "researcher": ("retrieval", "standards-ingestion", "explainer"),
    "coder": ("code-generation", "verifier", "explainer"),
    "developer": ("code-generation", "verifier", "explainer"),
    "verifier": ("verifier", "code-generation"),
    "explainer": ("explainer", "retrieval"),
    "multimodal": ("multimodal", "explainer"),
    "generalist": ("retrieval", "code-generation", "explainer"),
}


def infer_ollama_access_mode(endpoint: str) -> AccessMode:
    parsed = urlparse(endpoint)
    hostname = (parsed.hostname or "").lower()
    if hostname in {"", "localhost", "127.0.0.1", "::1"}:
        return "local-via-ollama"
    return "cloud-via-ollama"


def infer_agent_lanes(agent_role: str = "generalist", agent_id: str = "") -> list[str]:
    normalized_role = (agent_role or "generalist").strip().lower()
    if normalized_role in _ROLE_LANES:
        return list(_ROLE_LANES[normalized_role])

    normalized_agent_id = (agent_id or "").strip().lower()
    for keyword, lanes in _ROLE_LANES.items():
        if keyword != "generalist" and keyword in normalized_agent_id:
            return list(lanes)
    return list(_ROLE_LANES["generalist"])


def _is_known_but_impractical(spec: ModelSpec, hardware_summary: dict[str, Any]) -> bool:
    cpu_only = bool(hardware_summary.get("cpu_only", False))
    gpu_vram_gb = float(hardware_summary.get("gpu_vram_gb") or 0.0)
    if cpu_only and spec.min_vram_gb > 0.0:
        return True
    if spec.min_vram_gb > 0.0 and gpu_vram_gb < spec.min_vram_gb:
        return True
    return False


def _entry_sort_key(entry: ModelCatalogEntry) -> tuple[int, int, int, int, float]:
    return (
        1 if entry.reachable else 0,
        1 if entry.installed else 0,
        1 if entry.pullable else 0,
        0 if entry.known_but_impractical else 1,
        -entry.min_vram_gb,
    )


def _pick_best_entry(entries: list[ModelCatalogEntry], *, access_mode: AccessMode | None = None) -> ModelCatalogEntry | None:
    candidates = entries
    if access_mode is not None:
        candidates = [entry for entry in candidates if entry.access_mode == access_mode]
    if not candidates:
        return None
    return sorted(candidates, key=_entry_sort_key, reverse=True)[0]


def _recommend_lane(entries: list[ModelCatalogEntry], lane: str) -> dict[str, Any]:
    lane_entries = [entry for entry in entries if lane in entry.lanes]
    preferred_local_only = bool(lane_entries) and all(entry.requires_local for entry in lane_entries)
    viable_entries = [entry for entry in lane_entries if not entry.known_but_impractical]

    best_local = _pick_best_entry(viable_entries, access_mode="local-via-ollama")
    best_cloud = _pick_best_entry(viable_entries, access_mode="cloud-via-ollama")
    best_remote_direct = _pick_best_entry(viable_entries, access_mode="remote-direct")
    strongest_privacy_preserving = _pick_best_entry(
        [entry for entry in viable_entries if entry.privacy_preserving or entry.requires_local],
        access_mode="local-via-ollama",
    )
    fallback = _pick_best_entry(lane_entries)

    preferred = best_local if preferred_local_only else best_cloud or best_remote_direct or best_local or fallback
    rationale: list[str] = []
    if preferred_local_only:
        rationale.append("This lane prefers required-local models because it depends on governed retrieval or private memory context.")
    else:
        rationale.append("This lane can use the strongest appropriate reachable model, including cloud-via-ollama and explicit remote-direct operator paths when available.")
    if preferred is not None and preferred.known_but_impractical:
        rationale.append("The best-known model for this lane is currently impractical on the detected hardware, so it remains advisory only.")

    return {
        "lane": lane,
        "preferred": preferred.to_dict() if preferred else None,
        "best_local": best_local.to_dict() if best_local else None,
        "best_cloud_via_ollama": best_cloud.to_dict() if best_cloud else None,
        "best_remote_direct": best_remote_direct.to_dict() if best_remote_direct else None,
        "strongest_privacy_preserving": strongest_privacy_preserving.to_dict() if strongest_privacy_preserving else None,
        "fallback": fallback.to_dict() if fallback else None,
        "rationale": rationale,
    }


def sync_model_catalog(
    *,
    ollama_endpoint: str,
    runtime_status: dict[str, Any],
    hardware_summary: dict[str, Any],
    agent_id: str = "unknown-agent",
    agent_role: str = "generalist",
    remote_direct_entries: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    installed_names = {str(name) for name in runtime_status.get("installed_models", [])}
    ollama_access_mode = infer_ollama_access_mode(ollama_endpoint)
    ollama_available = bool(runtime_status.get("ollama_available", False))
    catalog_entries: list[ModelCatalogEntry] = []

    for spec in _DEFAULT_MODEL_SPECS:
        installed = spec.name in installed_names
        known_but_impractical = _is_known_but_impractical(spec, hardware_summary)
        access_mode: AccessMode = ollama_access_mode if ollama_available else "registry-known-not-configured"
        rationale = list(spec.notes)
        if spec.requires_local:
            rationale.append("Embeddings remain locality-constrained unless an operator explicitly changes policy.")
        if known_but_impractical:
            rationale.append("Known model is currently impractical on detected hardware.")
        if ollama_available and not installed:
            rationale.append("Model is registry-known and pullable through the configured Ollama-compatible endpoint.")
        catalog_entries.append(
            ModelCatalogEntry(
                name=spec.name,
                family=spec.family,
                lanes=list(spec.lanes),
                capabilities=list(spec.capabilities),
                access_mode=access_mode,
                endpoint=ollama_endpoint,
                installed=installed,
                reachable=ollama_available and installed,
                pullable=ollama_available and not installed,
                configured=ollama_available,
                known_but_impractical=known_but_impractical,
                requires_local=spec.requires_local,
                privacy_preserving=spec.privacy_preserving,
                min_vram_gb=spec.min_vram_gb,
                rationale=rationale,
            )
        )

    known_names = {entry.name for entry in catalog_entries}
    for installed_name in sorted(installed_names - known_names):
        catalog_entries.append(
            ModelCatalogEntry(
                name=installed_name,
                family="unknown",
                lanes=["code-generation", "explainer"],
                capabilities=["installed-unknown"],
                access_mode=ollama_access_mode,
                endpoint=ollama_endpoint,
                installed=True,
                reachable=ollama_available,
                pullable=False,
                configured=ollama_available,
                known_but_impractical=False,
                requires_local=False,
                privacy_preserving=False,
                min_vram_gb=0.0,
                rationale=["Installed model discovered from the runtime but not yet classified in the packaged registry."],
            )
        )

    for entry in remote_direct_entries or []:
        catalog_entries.append(
            ModelCatalogEntry(
                name=str(entry.get("name", "remote-direct-model")),
                family=str(entry.get("family", "remote-direct")),
                lanes=[str(lane) for lane in entry.get("lanes", ["explainer"])],
                capabilities=[str(cap) for cap in entry.get("capabilities", ["remote-direct"])],
                access_mode="remote-direct",
                endpoint=str(entry.get("endpoint", "")),
                installed=False,
                reachable=bool(entry.get("reachable", False)),
                pullable=False,
                configured=bool(entry.get("endpoint")),
                known_but_impractical=bool(entry.get("known_but_impractical", False)),
                requires_local=False,
                privacy_preserving=bool(entry.get("privacy_preserving", False)),
                min_vram_gb=float(entry.get("min_vram_gb") or 0.0),
                rationale=[str(reason) for reason in entry.get("rationale", ["Remote direct endpoint configured."])],
            )
        )

    lane_recommendations = {
        lane: _recommend_lane(catalog_entries, lane)
        for lane in [
            "retrieval",
            "standards-ingestion",
            "code-generation",
            "verifier",
            "explainer",
            "multimodal",
        ]
    }
    preferred_lanes = infer_agent_lanes(agent_role=agent_role, agent_id=agent_id)
    agent_lane_summary = {lane: lane_recommendations[lane] for lane in preferred_lanes if lane in lane_recommendations}

    return {
        "agent_id": agent_id,
        "agent_role": agent_role,
        "preferred_lanes": preferred_lanes,
        "ollama_endpoint": ollama_endpoint,
        "ollama_access_mode": ollama_access_mode,
        "entries": [entry.to_dict() for entry in sorted(catalog_entries, key=lambda item: (item.family, item.name, item.access_mode))],
        "summary": {
            "total_models": len(catalog_entries),
            "installed_count": sum(1 for entry in catalog_entries if entry.installed),
            "reachable_count": sum(1 for entry in catalog_entries if entry.reachable),
            "pullable_count": sum(1 for entry in catalog_entries if entry.pullable),
            "known_but_impractical_count": sum(1 for entry in catalog_entries if entry.known_but_impractical),
            "configured_remote_direct_count": sum(1 for entry in catalog_entries if entry.access_mode == "remote-direct" and entry.configured),
        },
        "lane_recommendations": lane_recommendations,
        "agent_lane_summary": agent_lane_summary,
        "runtime_status": dict(runtime_status),
        "hardware_summary": dict(hardware_summary),
    }

