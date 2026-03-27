"""
Business logic services.

NOTE:
This package uses lazy imports to avoid circular-import issues between services
and agent modules. Import the concrete modules directly when possible:

- from app.services.retrieval import IntelligentRetriever
- from app.services.research import ResearchAgentService
"""

from __future__ import annotations

from typing import Any

__all__ = [
    "IntelligentRetriever",
    "KBModelService",
    "ResearchAgentService",
    "CacheService",
    "PIISanitizer",
    "KBParser",
    "QueueService",
    "EmbeddingService",
    "OpenRouterClient",
    "ProviderPreferences",
    "RoutingStrategy",
    "DataPolicy",
    "get_openrouter_client",
    "LLMRouter",
    "LLMRoutingStrategy",
    "LLMResponse",
    "create_router",
]


def __getattr__(name: str) -> Any:
    if name == "IntelligentRetriever":
        from app.services.retrieval import IntelligentRetriever as _x
        return _x
    if name == "KBModelService":
        from app.services.kb_model import KBModelService as _x
        return _x
    if name == "ResearchAgentService":
        from app.services.research import ResearchAgentService as _x
        return _x
    if name == "CacheService":
        from app.services.cache import CacheService as _x
        return _x
    if name == "PIISanitizer":
        from app.services.sanitizer import PIISanitizer as _x
        return _x
    if name == "KBParser":
        from app.services.kb_parser import KBParser as _x
        return _x
    if name == "QueueService":
        from app.services.queue_service import QueueService as _x
        return _x
    if name == "EmbeddingService":
        from app.services.embedding import EmbeddingService as _x
        return _x

    if name in {"OpenRouterClient", "ProviderPreferences", "RoutingStrategy", "DataPolicy", "get_openrouter_client"}:
        from app.services import openrouter as _m
        return getattr(_m, name)

    if name in {"LLMRouter", "LLMRoutingStrategy", "LLMResponse", "create_router"}:
        from app.services import llm_router as _m
        return getattr(_m, name)

    raise AttributeError(name)

