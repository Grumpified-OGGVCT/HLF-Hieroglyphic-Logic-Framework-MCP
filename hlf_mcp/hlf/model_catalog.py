from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal
from urllib.parse import urlparse


def aggregate_benchmark_artifacts(
    memory_store, model_name: str, profile_name: str
) -> list[dict[str, Any]]:
    """Aggregate all persisted benchmark artifacts for a given model/profile from RAGMemory."""
    artifacts = []
    try:
        artifacts = memory_store.query_facts(
            entry_kind="benchmark_artifact", model=model_name, profile=profile_name
        )
    except Exception:
        for fact in getattr(memory_store, "all_facts", lambda: [])():
            if fact.get("entry_kind") != "benchmark_artifact":
                continue
            if fact.get("model") != model_name:
                continue
            if fact.get("profile") != profile_name:
                continue
            artifacts.append(fact)
    return artifacts


AccessMode = Literal[
    "local-via-ollama",
    "cloud-via-ollama",
    "remote-direct",
    "registry-known-not-configured",
]

QualificationTier = Literal[
    "advisory-only",
    "baseline-qualified",
    "launch-qualified",
    "promotion-qualified",
]

_DEFAULT_QUALIFICATION_PROFILE_PATH = (
    Path(__file__).resolve().parents[2] / "governance" / "model_qualification_profiles.json"
)


@dataclass(slots=True, frozen=True)
class ModelSpec:
    name: str
    family: str
    lanes: tuple[str, ...]
    capabilities: tuple[str, ...]
    supported_languages: tuple[str, ...] = ()
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
    supported_languages: list[str]
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
            "supported_languages": list(self.supported_languages),
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
        supported_languages=("en",),
        requires_local=True,
        privacy_preserving=True,
        notes=("Strong default for privacy-preserving retrieval.",),
    ),
    ModelSpec(
        name="all-minilm",
        family="embedding",
        lanes=("retrieval",),
        capabilities=("embedding", "lightweight"),
        supported_languages=("en",),
        requires_local=True,
        privacy_preserving=True,
        notes=("Useful fallback for CPU-only retrieval lanes.",),
    ),
    ModelSpec(
        name="nomic-embed-text-v2-moe",
        family="embedding",
        lanes=("retrieval", "standards-ingestion"),
        capabilities=("embedding", "multilingual", "semantic-recall"),
        supported_languages=("en", "fr", "es", "ar", "zh"),
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
        supported_languages=("en", "fr", "es", "ar", "zh"),
        min_vram_gb=10.0,
        requires_local=True,
        privacy_preserving=True,
    ),
    ModelSpec(
        name="mxbai-embed-large",
        family="embedding",
        lanes=("retrieval", "code-generation"),
        capabilities=("embedding", "code-retrieval"),
        supported_languages=("en",),
        min_vram_gb=4.0,
        requires_local=True,
        privacy_preserving=True,
    ),
    ModelSpec(
        name="granite-embedding:30m",
        family="embedding",
        lanes=("retrieval",),
        capabilities=("embedding", "lightweight"),
        supported_languages=("en",),
        requires_local=True,
        privacy_preserving=True,
    ),
    ModelSpec(
        name="qwen3-embedding:4b",
        family="embedding",
        lanes=("retrieval", "standards-ingestion"),
        capabilities=("embedding", "long-context", "multilingual"),
        supported_languages=("en", "fr", "es", "ar", "zh"),
        min_vram_gb=12.0,
        requires_local=True,
        privacy_preserving=True,
    ),
    ModelSpec(
        name="qwen3:8b",
        family="reasoning",
        lanes=("code-generation", "verifier", "explainer"),
        capabilities=("reasoning", "coding", "explanations"),
        supported_languages=("en", "fr", "es", "ar", "zh"),
        min_vram_gb=8.0,
        notes=("Useful general reasoning lane through Ollama-compatible endpoints.",),
    ),
    ModelSpec(
        name="llama3.1:8b",
        family="reasoning",
        lanes=("code-generation", "explainer"),
        capabilities=("reasoning", "coding", "generalist"),
        supported_languages=("en",),
        min_vram_gb=8.0,
    ),
    ModelSpec(
        name="gemma3:12b",
        family="reasoning",
        lanes=("standards-ingestion", "explainer"),
        capabilities=("reasoning", "analysis", "long-context"),
        supported_languages=("en",),
        min_vram_gb=10.0,
    ),
    ModelSpec(
        name="devstral:24b",
        family="reasoning",
        lanes=("code-generation", "verifier"),
        capabilities=("reasoning", "coding", "review"),
        supported_languages=("en",),
        min_vram_gb=16.0,
        notes=("Stronger coding and verification lane when reachable via cloud-via-ollama.",),
    ),
    ModelSpec(
        name="glm-5:cloud",
        family="reasoning",
        lanes=("reasoning", "planning", "analysis", "universal"),
        capabilities=("reasoning", "systems-engineering", "long-context"),
        supported_languages=("en", "zh"),
        notes=("Strong reasoning and complex systems engineering donor model.",),
    ),
    ModelSpec(
        name="nemotron-3-super",
        family="reasoning",
        lanes=("reasoning", "planning", "doer", "coding", "analysis", "universal"),
        capabilities=("reasoning", "tool-use", "agentic", "coding"),
        supported_languages=("en",),
        notes=("Broad agentic fallback with strong long-horizon tool-use behavior.",),
    ),
    ModelSpec(
        name="cogito-2.1:671b-cloud",
        family="reasoning",
        lanes=("reasoning", "planning", "analysis"),
        capabilities=("reasoning", "planning", "math", "strategic-decomposition"),
        supported_languages=("en",),
        notes=("Specialist planning and math-heavy decomposition donor model.",),
    ),
    ModelSpec(
        name="kimi-k2-thinking:cloud",
        family="reasoning",
        lanes=("reasoning", "planning", "analysis"),
        capabilities=("planning", "tool-use", "long-context", "reasoning"),
        supported_languages=("en",),
        notes=("Long-horizon planning and sequential tool-use specialist.",),
    ),
    ModelSpec(
        name="kimi-k2.5:cloud",
        family="multimodal",
        lanes=("planning", "analysis", "multimodal", "universal"),
        capabilities=("planning", "multimodal", "tool-use", "ui-synthesis"),
        supported_languages=("en",),
        notes=("Multimodal planning and UI/repo synthesis donor model.",),
    ),
    ModelSpec(
        name="minimax-m2.7:cloud",
        family="reasoning",
        lanes=("doer", "coding", "universal"),
        capabilities=("coding", "execution", "agentic", "productivity"),
        supported_languages=("en",),
        notes=("Execution-focused software engineering and doer specialist.",),
    ),
    ModelSpec(
        name="devstral-2:123b-cloud",
        family="reasoning",
        lanes=("coding", "doer", "verifier"),
        capabilities=("coding", "review", "tool-use", "repository-navigation"),
        supported_languages=("en",),
        notes=("High-capability coding and repository-scale editing specialist.",),
    ),
    ModelSpec(
        name="qwen3-coder-next:cloud",
        family="reasoning",
        lanes=("coding", "doer", "analysis"),
        capabilities=("coding", "tool-use", "repository-navigation", "efficiency"),
        supported_languages=("en", "zh"),
        notes=("Efficient repo-scale coding specialist and fallback.",),
    ),
    ModelSpec(
        name="qwen3.5:cloud",
        family="multimodal",
        lanes=("reasoning", "analysis", "multimodal", "universal"),
        capabilities=("structured-output", "multimodal", "generalist", "reasoning"),
        supported_languages=("en", "zh"),
        notes=("Universal structured-output and multimodal fallback.",),
    ),
    ModelSpec(
        name="deepseek-v3.2:cloud",
        family="reasoning",
        lanes=("reasoning", "analysis", "ethics", "universal"),
        capabilities=("reasoning", "adversarial-analysis", "efficiency", "safety-backstop"),
        supported_languages=("en", "zh"),
        notes=("Adversarial and analytical backstop with strong efficiency.",),
    ),
    ModelSpec(
        name="llava:7b",
        family="multimodal",
        lanes=("multimodal", "explainer"),
        capabilities=("vision", "multimodal", "explanations"),
        supported_languages=("en",),
        min_vram_gb=10.0,
    ),
)


_NAMED_CHAIN_PROFILES: dict[str, dict[str, Any]] = {
    "reasoning": {
        "required_lanes": ("reasoning",),
        "preferred_lanes": ("analysis", "universal"),
        "preferred_capabilities": ("reasoning", "long-context", "systems-engineering"),
        "fallback_models": ("qwen3.5:cloud",),
    },
    "planning": {
        "required_lanes": ("planning",),
        "preferred_lanes": ("reasoning", "analysis", "universal"),
        "preferred_capabilities": (
            "planning",
            "strategic-decomposition",
            "tool-use",
            "multimodal",
            "long-context",
        ),
        "fallback_models": ("nemotron-3-super", "qwen3.5:cloud"),
    },
    "doer": {
        "required_lanes": ("doer",),
        "preferred_lanes": ("coding", "universal"),
        "preferred_capabilities": ("execution", "agentic", "coding", "productivity"),
        "fallback_models": ("glm-5:cloud", "qwen3.5:cloud"),
    },
    "coding": {
        "required_lanes": ("coding",),
        "preferred_lanes": ("doer", "verifier", "universal"),
        "preferred_capabilities": (
            "coding",
            "repository-navigation",
            "tool-use",
            "review",
        ),
        "fallback_models": ("glm-5:cloud", "qwen3.5:cloud"),
    },
    "analysis": {
        "required_lanes": ("analysis",),
        "preferred_lanes": ("reasoning", "multimodal", "universal"),
        "preferred_capabilities": (
            "structured-output",
            "multimodal",
            "reasoning",
            "adversarial-analysis",
        ),
        "fallback_models": ("deepseek-v3.2:cloud",),
    },
    "ethics": {
        "required_lanes": ("ethics", "analysis"),
        "preferred_lanes": ("reasoning", "universal"),
        "preferred_capabilities": (
            "safety-backstop",
            "adversarial-analysis",
            "reasoning",
        ),
        "fallback_models": ("glm-5:cloud", "qwen3.5:cloud"),
    },
    "universal": {
        "required_lanes": ("universal",),
        "preferred_lanes": ("reasoning", "analysis", "planning"),
        "preferred_capabilities": (
            "generalist",
            "reasoning",
            "tool-use",
            "structured-output",
        ),
        "fallback_models": ("deepseek-v3.2:cloud",),
    },
}


def evaluate_model_requirements(
    entry: dict[str, Any],
    *,
    required_lanes: list[str] | tuple[str, ...] = (),
    required_capabilities: list[str] | tuple[str, ...] = (),
    required_languages: list[str] | tuple[str, ...] = (),
    minimum_benchmark_scores: dict[str, float] | None = None,
    benchmark_scores: dict[str, float] | None = None,
    require_reachable: bool = True,
) -> dict[str, Any]:
    """Evaluate whether a catalog entry satisfies an explicit minimum requirement contract."""
    entry_name = str(entry.get("name", "unknown-model"))
    lanes = {str(item) for item in entry.get("lanes", [])}
    capabilities = {str(item) for item in entry.get("capabilities", [])}
    supported_languages = {str(item) for item in entry.get("supported_languages", [])}
    reachable = bool(entry.get("reachable", False))
    known_but_impractical = bool(entry.get("known_but_impractical", False))

    missing_lanes = sorted(str(item) for item in required_lanes if str(item) not in lanes)
    missing_capabilities = sorted(
        str(item) for item in required_capabilities if str(item) not in capabilities
    )
    missing_languages = sorted(
        str(item) for item in required_languages if str(item) not in supported_languages
    )

    minimum_scores = {str(k): float(v) for k, v in (minimum_benchmark_scores or {}).items()}
    provided_scores = {str(k): float(v) for k, v in (benchmark_scores or {}).items()}
    failed_benchmarks: list[dict[str, Any]] = []
    missing_benchmarks: list[str] = []
    for benchmark_name, minimum_score in minimum_scores.items():
        score = provided_scores.get(benchmark_name)
        if score is None:
            missing_benchmarks.append(benchmark_name)
            continue
        if score < minimum_score:
            failed_benchmarks.append(
                {
                    "benchmark": benchmark_name,
                    "required_minimum": minimum_score,
                    "actual_score": score,
                }
            )

    qualification_failures: list[str] = []
    if require_reachable and not reachable:
        qualification_failures.append("Model is not currently reachable.")
    if known_but_impractical:
        qualification_failures.append("Model is known but impractical on detected hardware.")
    if missing_lanes:
        qualification_failures.append(f"Missing required lanes: {', '.join(missing_lanes)}")
    if missing_capabilities:
        qualification_failures.append(
            f"Missing required capabilities: {', '.join(missing_capabilities)}"
        )
    if missing_languages:
        qualification_failures.append(f"Missing required languages: {', '.join(missing_languages)}")
    if missing_benchmarks:
        qualification_failures.append(f"Missing benchmark scores: {', '.join(missing_benchmarks)}")
    if failed_benchmarks:
        qualification_failures.append("Benchmark thresholds not met.")

    return {
        "model": entry_name,
        "qualified": len(qualification_failures) == 0,
        "required_lanes": list(required_lanes),
        "required_capabilities": list(required_capabilities),
        "required_languages": list(required_languages),
        "minimum_benchmark_scores": minimum_scores,
        "benchmark_scores": provided_scores,
        "missing_lanes": missing_lanes,
        "missing_capabilities": missing_capabilities,
        "missing_languages": missing_languages,
        "missing_benchmarks": missing_benchmarks,
        "failed_benchmarks": failed_benchmarks,
        "qualification_failures": qualification_failures,
    }


def evaluate_model_requirement_tiers(
    entry: dict[str, Any],
    *,
    required_lanes: list[str] | tuple[str, ...] = (),
    required_capabilities: list[str] | tuple[str, ...] = (),
    required_languages: list[str] | tuple[str, ...] = (),
    baseline_benchmark_scores: dict[str, float] | None = None,
    launch_benchmark_scores: dict[str, float] | None = None,
    promotion_benchmark_scores: dict[str, float] | None = None,
    benchmark_scores: dict[str, float] | None = None,
    require_reachable: bool = True,
) -> dict[str, Any]:
    """Evaluate a model against advisory, baseline, launch, and promotion qualification tiers."""
    advisory = evaluate_model_requirements(
        entry,
        required_lanes=required_lanes,
        required_capabilities=required_capabilities,
        required_languages=required_languages,
        minimum_benchmark_scores={},
        benchmark_scores=benchmark_scores,
        require_reachable=False,
    )
    baseline = evaluate_model_requirements(
        entry,
        required_lanes=required_lanes,
        required_capabilities=required_capabilities,
        required_languages=required_languages,
        minimum_benchmark_scores=baseline_benchmark_scores,
        benchmark_scores=benchmark_scores,
        require_reachable=require_reachable,
    )
    launch = evaluate_model_requirements(
        entry,
        required_lanes=required_lanes,
        required_capabilities=required_capabilities,
        required_languages=required_languages,
        minimum_benchmark_scores=launch_benchmark_scores,
        benchmark_scores=benchmark_scores,
        require_reachable=require_reachable,
    )
    promotion = evaluate_model_requirements(
        entry,
        required_lanes=required_lanes,
        required_capabilities=required_capabilities,
        required_languages=required_languages,
        minimum_benchmark_scores=promotion_benchmark_scores,
        benchmark_scores=benchmark_scores,
        require_reachable=require_reachable,
    )

    resolved_tier: QualificationTier = "advisory-only"
    if baseline["qualified"]:
        resolved_tier = "baseline-qualified"
    if launch["qualified"]:
        resolved_tier = "launch-qualified"
    if promotion["qualified"]:
        resolved_tier = "promotion-qualified"

    return {
        "model": str(entry.get("name", "unknown-model")),
        "resolved_tier": resolved_tier,
        "tiers": {
            "advisory-only": advisory,
            "baseline-qualified": baseline,
            "launch-qualified": launch,
            "promotion-qualified": promotion,
        },
    }


def load_model_qualification_profiles(file_path: str | None = None) -> dict[str, Any]:
    """Load governed model qualification profiles from repository authority."""
    path = Path(file_path) if file_path else _DEFAULT_QUALIFICATION_PROFILE_PATH
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or "profiles" not in payload:
        raise ValueError(
            "Model qualification profile file must contain a top-level 'profiles' object."
        )
    return payload


def evaluate_model_against_profile(
    entry: dict[str, Any],
    *,
    profile_name: str,
    benchmark_scores: dict[str, float] | None = None,
    require_reachable: bool = True,
    file_path: str | None = None,
) -> dict[str, Any]:
    """Evaluate a model against a governed qualification profile."""
    payload = load_model_qualification_profiles(file_path=file_path)
    profiles = payload.get("profiles") or {}
    profile = profiles.get(profile_name)
    if not isinstance(profile, dict):
        raise ValueError(f"Unknown model qualification profile: {profile_name}")

    required_lanes = [str(item) for item in profile.get("required_lanes", [])]
    required_capabilities = [str(item) for item in profile.get("required_capabilities", [])]
    required_languages = [str(item) for item in profile.get("required_languages", [])]
    tiers = profile.get("tiers") or {}

    # Aggregate all benchmark artifacts for this model/profile
    memory_store = entry.get("memory_store") if "memory_store" in entry else None
    artifact_history = []
    if memory_store is not None:
        artifact_history = aggregate_benchmark_artifacts(
            memory_store, entry.get("name", ""), profile_name
        )

    # Aggregate scores if history is available
    aggregate_scores = {}
    if artifact_history:
        # For each metric, compute mean/min/max/count
        metrics = set()
        for artifact in artifact_history:
            metrics.update(artifact.get("benchmark_scores", {}).keys())
        for metric in metrics:
            values = [
                float(a["benchmark_scores"].get(metric, 0.0))
                for a in artifact_history
                if metric in a.get("benchmark_scores", {})
            ]
            if values:
                aggregate_scores[metric] = {
                    "mean": sum(values) / len(values),
                    "min": min(values),
                    "max": max(values),
                    "count": len(values),
                    "all": values,
                }

    # Use the latest artifact's scores for compatibility, but expose aggregate
    latest_scores = benchmark_scores
    if artifact_history:
        latest_scores = artifact_history[-1].get("benchmark_scores", {})

    evaluation = evaluate_model_requirement_tiers(
        entry,
        required_lanes=required_lanes,
        required_capabilities=required_capabilities,
        required_languages=required_languages,
        baseline_benchmark_scores=tiers.get("baseline-qualified"),
        launch_benchmark_scores=tiers.get("launch-qualified"),
        promotion_benchmark_scores=tiers.get("promotion-qualified"),
        benchmark_scores=latest_scores,
        require_reachable=require_reachable,
    )
    evaluation["profile_name"] = profile_name
    evaluation["profile"] = profile
    evaluation["artifact_history"] = artifact_history
    evaluation["aggregate_scores"] = aggregate_scores
    return evaluation


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


def _pick_best_entry(
    entries: list[ModelCatalogEntry], *, access_mode: AccessMode | None = None
) -> ModelCatalogEntry | None:
    candidates = entries
    if access_mode is not None:
        candidates = [entry for entry in candidates if entry.access_mode == access_mode]
    if not candidates:
        return None
    return sorted(candidates, key=_entry_sort_key, reverse=True)[0]


def _spec_map() -> dict[str, ModelSpec]:
    return {spec.name: spec for spec in _DEFAULT_MODEL_SPECS}


def _build_model_chain_sort_key(
    spec: ModelSpec,
    *,
    required_lanes: tuple[str, ...],
    preferred_lanes: tuple[str, ...],
    preferred_capabilities: tuple[str, ...],
    benchmark_scores: dict[str, float] | None,
) -> tuple[float, int, int, int, int, float, str]:
    lane_set = set(spec.lanes)
    capability_set = set(spec.capabilities)
    benchmark_score = float((benchmark_scores or {}).get(spec.name, 0.0))
    required_lane_hits = sum(1 for lane in required_lanes if lane in lane_set)
    preferred_lane_hits = sum(1 for lane in preferred_lanes if lane in lane_set)
    preferred_capability_hits = sum(1 for capability in preferred_capabilities if capability in capability_set)
    language_breadth = len(spec.supported_languages)
    cloud_ready = 0 if spec.requires_local else 1
    return (
        benchmark_score,
        required_lane_hits,
        preferred_capability_hits,
        preferred_lane_hits,
        cloud_ready,
        language_breadth,
        spec.min_vram_gb,
        spec.name,
    )


def build_named_model_chain(
    chain_name: str,
    *,
    available_models: list[str] | tuple[str, ...] | set[str] | None = None,
    benchmark_scores: dict[str, float] | None = None,
) -> list[str]:
    """Build a named workflow chain from packaged policy instead of static winner lists."""
    profile = _NAMED_CHAIN_PROFILES.get(chain_name)
    if profile is None:
        raise ValueError(f"Unknown named model chain: {chain_name}")

    available = {str(name) for name in available_models} if available_models is not None else None
    specs = _spec_map()
    candidates = []
    for spec in _DEFAULT_MODEL_SPECS:
        if available is not None and spec.name not in available:
            continue
        if not any(lane in spec.lanes for lane in profile["required_lanes"]):
            continue
        candidates.append(spec)

    ordered = sorted(
        candidates,
        key=lambda spec: _build_model_chain_sort_key(
            spec,
            required_lanes=tuple(profile["required_lanes"]),
            preferred_lanes=tuple(profile["preferred_lanes"]),
            preferred_capabilities=tuple(profile["preferred_capabilities"]),
            benchmark_scores=benchmark_scores,
        ),
        reverse=True,
    )

    chain: list[str] = []
    seen: set[str] = set()

    def add_model(model_name: str) -> None:
        if available is not None and model_name not in available:
            return
        if model_name in seen or model_name not in specs:
            return
        seen.add(model_name)
        chain.append(model_name)

    for spec in ordered:
        add_model(spec.name)

    for fallback_name in profile.get("fallback_models", ()):
        add_model(str(fallback_name))

    if len(chain) < 2:
        universal_profile = _NAMED_CHAIN_PROFILES["universal"]
        universal_candidates = sorted(
            [
                spec
                for spec in _DEFAULT_MODEL_SPECS
                if available is None or spec.name in available
            ],
            key=lambda spec: _build_model_chain_sort_key(
                spec,
                required_lanes=tuple(universal_profile["required_lanes"]),
                preferred_lanes=tuple(universal_profile["preferred_lanes"]),
                preferred_capabilities=tuple(universal_profile["preferred_capabilities"]),
                benchmark_scores=benchmark_scores,
            ),
            reverse=True,
        )
        for spec in universal_candidates:
            add_model(spec.name)
            if len(chain) >= 2:
                break

    return chain


def build_named_model_chains(
    *,
    available_models: list[str] | tuple[str, ...] | set[str] | None = None,
    benchmark_scores: dict[str, float] | None = None,
) -> dict[str, list[str]]:
    """Return all named workflow chains from packaged policy."""
    return {
        chain_name: build_named_model_chain(
            chain_name,
            available_models=available_models,
            benchmark_scores=benchmark_scores,
        )
        for chain_name in _NAMED_CHAIN_PROFILES
    }


def _recommend_lane(entries: list[ModelCatalogEntry], lane: str) -> dict[str, Any]:
    lane_entries = [entry for entry in entries if lane in entry.lanes]
    preferred_local_only = bool(lane_entries) and all(
        entry.requires_local for entry in lane_entries
    )
    viable_entries = [entry for entry in lane_entries if not entry.known_but_impractical]

    best_local = _pick_best_entry(viable_entries, access_mode="local-via-ollama")
    best_cloud = _pick_best_entry(viable_entries, access_mode="cloud-via-ollama")
    best_remote_direct = _pick_best_entry(viable_entries, access_mode="remote-direct")
    strongest_privacy_preserving = _pick_best_entry(
        [entry for entry in viable_entries if entry.privacy_preserving or entry.requires_local],
        access_mode="local-via-ollama",
    )
    fallback = _pick_best_entry(lane_entries)

    preferred = (
        best_local
        if preferred_local_only
        else best_cloud or best_remote_direct or best_local or fallback
    )
    rationale: list[str] = []
    if preferred_local_only:
        rationale.append(
            "This lane prefers required-local models because it depends on governed retrieval or private memory context."
        )
    else:
        rationale.append(
            "This lane can use the strongest appropriate reachable model, including cloud-via-ollama and explicit remote-direct operator paths when available."
        )
    if preferred is not None and preferred.known_but_impractical:
        rationale.append(
            "The best-known model for this lane is currently impractical on the detected hardware, so it remains advisory only."
        )

    return {
        "lane": lane,
        "preferred": preferred.to_dict() if preferred else None,
        "best_local": best_local.to_dict() if best_local else None,
        "best_cloud_via_ollama": best_cloud.to_dict() if best_cloud else None,
        "best_remote_direct": best_remote_direct.to_dict() if best_remote_direct else None,
        "strongest_privacy_preserving": strongest_privacy_preserving.to_dict()
        if strongest_privacy_preserving
        else None,
        "fallback": fallback.to_dict() if fallback else None,
        "rationale": rationale,
    }


def build_lane_trace_context(catalog: dict[str, Any], selected_lane: str) -> dict[str, Any]:
    lane_recommendations = dict(catalog.get("lane_recommendations") or {})
    lane_summary = dict(lane_recommendations.get(selected_lane) or {})
    return {
        "selected_lane": selected_lane,
        "preferred_lanes": list(catalog.get("preferred_lanes") or []),
        "summary": {
            "preferred": lane_summary.get("preferred"),
            "best_local": lane_summary.get("best_local"),
            "best_cloud_via_ollama": lane_summary.get("best_cloud_via_ollama"),
            "best_remote_direct": lane_summary.get("best_remote_direct"),
            "fallback": lane_summary.get("fallback"),
            "rationale": list(lane_summary.get("rationale") or []),
        },
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
        access_mode: AccessMode = (
            ollama_access_mode if ollama_available else "registry-known-not-configured"
        )
        rationale = list(spec.notes)
        if spec.requires_local:
            rationale.append(
                "Embeddings remain locality-constrained unless an operator explicitly changes policy."
            )
        if known_but_impractical:
            rationale.append("Known model is currently impractical on detected hardware.")
        if ollama_available and not installed:
            rationale.append(
                "Model is registry-known and pullable through the configured Ollama-compatible endpoint."
            )
        catalog_entries.append(
            ModelCatalogEntry(
                name=spec.name,
                family=spec.family,
                lanes=list(spec.lanes),
                capabilities=list(spec.capabilities),
                supported_languages=list(spec.supported_languages),
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
                supported_languages=[],
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
                rationale=[
                    "Installed model discovered from the runtime but not yet classified in the packaged registry."
                ],
            )
        )

    for entry in remote_direct_entries or []:
        catalog_entries.append(
            ModelCatalogEntry(
                name=str(entry.get("name", "remote-direct-model")),
                family=str(entry.get("family", "remote-direct")),
                lanes=[str(lane) for lane in entry.get("lanes", ["explainer"])],
                capabilities=[str(cap) for cap in entry.get("capabilities", ["remote-direct"])],
                supported_languages=[
                    str(language) for language in entry.get("supported_languages", [])
                ],
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
                rationale=[
                    str(reason)
                    for reason in entry.get("rationale", ["Remote direct endpoint configured."])
                ],
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
    agent_lane_summary = {
        lane: lane_recommendations[lane] for lane in preferred_lanes if lane in lane_recommendations
    }

    return {
        "agent_id": agent_id,
        "agent_role": agent_role,
        "preferred_lanes": preferred_lanes,
        "ollama_endpoint": ollama_endpoint,
        "ollama_access_mode": ollama_access_mode,
        "entries": [
            entry.to_dict()
            for entry in sorted(
                catalog_entries, key=lambda item: (item.family, item.name, item.access_mode)
            )
        ],
        "summary": {
            "total_models": len(catalog_entries),
            "installed_count": sum(1 for entry in catalog_entries if entry.installed),
            "reachable_count": sum(1 for entry in catalog_entries if entry.reachable),
            "pullable_count": sum(1 for entry in catalog_entries if entry.pullable),
            "known_but_impractical_count": sum(
                1 for entry in catalog_entries if entry.known_but_impractical
            ),
            "configured_remote_direct_count": sum(
                1
                for entry in catalog_entries
                if entry.access_mode == "remote-direct" and entry.configured
            ),
        },
        "lane_recommendations": lane_recommendations,
        "agent_lane_summary": agent_lane_summary,
        "runtime_status": dict(runtime_status),
        "hardware_summary": dict(hardware_summary),
    }
