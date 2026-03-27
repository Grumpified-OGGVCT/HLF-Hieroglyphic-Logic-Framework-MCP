"""
Ollama client (local + cloud).

Implements:
- /api/tags (list models): https://docs.ollama.com/api/tags
- /api/chat (chat): https://docs.ollama.com/api/chat
- /api/generate (generate): https://docs.ollama.com/api/generate
- /api/embed (embeddings): https://docs.ollama.com/api/embed
- /api/web_search and /api/web_fetch: https://docs.ollama.com/capabilities/web-search
- Streaming is application/x-ndjson: https://docs.ollama.com/api/streaming
- Errors: https://docs.ollama.com/api/errors

Cloud base URL and auth:
- Cloud API base: https://ollama.com/api (same API surface): https://docs.ollama.com/api/introduction
- API key auth for ollama.com: https://docs.ollama.com/api/authentication
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, AsyncIterator, Dict, Optional, Union

import httpx
import structlog

from app.config import get_settings
from app.schemas.ollama import (
    OllamaChatRequest,
    OllamaChatResponse,
    OllamaEmbedRequest,
    OllamaEmbedResponse,
    OllamaGenerateRequest,
    OllamaGenerateResponse,
    OllamaTagsResponse,
    OllamaWebFetchRequest,
    OllamaWebFetchResponse,
    OllamaWebSearchRequest,
    OllamaWebSearchResponse,
)

logger = structlog.get_logger()


class OllamaAPIError(RuntimeError):
    def __init__(self, message: str, status_code: Optional[int] = None, payload: Optional[dict] = None):
        super().__init__(message)
        self.status_code = status_code
        self.payload = payload or {}


@dataclass(frozen=True)
class OllamaClientConfig:
    base_url: str
    api_key: Optional[str] = None
    timeout_seconds: float = 120.0


class OllamaClient:
    """
    Minimal Ollama HTTP client.

    - For local Ollama: base_url is typically "http://localhost:11434/api"
    - For Ollama Cloud: base_url is "https://ollama.com/api"
    """

    def __init__(self, config: Optional[OllamaClientConfig] = None):
        settings = get_settings()
        if config is None:
            base_url = settings.ollama.base_url or "http://localhost:11434/api"
            api_key = settings.ollama.api_key.get_secret_value() or None
            config = OllamaClientConfig(base_url=base_url, api_key=api_key)
        self.config = config
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            headers = {"Content-Type": "application/json"}
            if self.config.api_key:
                headers["Authorization"] = f"Bearer {self.config.api_key}"
            self._client = httpx.AsyncClient(
                base_url=self.config.base_url.rstrip("/"),
                timeout=self.config.timeout_seconds,
                headers=headers,
            )
        return self._client

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    async def list_models(self) -> OllamaTagsResponse:
        client = await self._get_client()
        resp = await client.get("/tags")
        return self._parse_json_response(resp, OllamaTagsResponse)

    async def chat(self, request: OllamaChatRequest) -> OllamaChatResponse:
        """
        Non-streaming chat completion.

        Use request.stream=False for easiest parsing (recommended for structured outputs).
        """
        client = await self._get_client()
        resp = await client.post("/chat", json=request.model_dump())
        return self._parse_json_response(resp, OllamaChatResponse)

    async def chat_stream(self, request: OllamaChatRequest) -> AsyncIterator[dict]:
        """
        Streaming chat completion (NDJSON).

        Yields decoded JSON objects per line.
        """
        client = await self._get_client()
        payload = request.model_dump()
        payload["stream"] = True

        async with client.stream("POST", "/chat", json=payload) as resp:
            if resp.status_code >= 400:
                await self._raise_http_error(resp)
            async for line in resp.aiter_lines():
                if not line:
                    continue
                try:
                    data = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(data, dict) and "error" in data:
                    raise OllamaAPIError(str(data.get("error", "unknown streaming error")), status_code=resp.status_code, payload=data)
                yield data

    async def generate(self, request: OllamaGenerateRequest) -> OllamaGenerateResponse:
        client = await self._get_client()
        resp = await client.post("/generate", json=request.model_dump())
        return self._parse_json_response(resp, OllamaGenerateResponse)

    async def generate_stream(self, request: OllamaGenerateRequest) -> AsyncIterator[dict]:
        """
        Streaming generate (NDJSON).
        """
        client = await self._get_client()
        payload = request.model_dump()
        payload["stream"] = True

        async with client.stream("POST", "/generate", json=payload) as resp:
            if resp.status_code >= 400:
                await self._raise_http_error(resp)
            async for line in resp.aiter_lines():
                if not line:
                    continue
                try:
                    data = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(data, dict) and "error" in data:
                    raise OllamaAPIError(str(data.get("error", "unknown streaming error")), status_code=resp.status_code, payload=data)
                yield data

    async def embed(self, request: OllamaEmbedRequest) -> OllamaEmbedResponse:
        client = await self._get_client()
        resp = await client.post("/embed", json=request.model_dump())
        return self._parse_json_response(resp, OllamaEmbedResponse)

    async def web_search(self, request: OllamaWebSearchRequest) -> OllamaWebSearchResponse:
        client = await self._get_client()
        resp = await client.post("/web_search", json=request.model_dump())
        return self._parse_json_response(resp, OllamaWebSearchResponse)

    async def web_fetch(self, request: OllamaWebFetchRequest) -> OllamaWebFetchResponse:
        client = await self._get_client()
        resp = await client.post("/web_fetch", json=request.model_dump())
        return self._parse_json_response(resp, OllamaWebFetchResponse)

    def _parse_json_response(self, resp: httpx.Response, model_cls: Any):
        if resp.status_code >= 400:
            # Errors are JSON: {"error": "..."} per docs.
            try:
                payload = resp.json()
            except Exception:
                payload = {"error": resp.text}
            raise OllamaAPIError(str(payload.get("error", "ollama error")), status_code=resp.status_code, payload=payload)
        try:
            data = resp.json()
        except Exception as e:
            raise OllamaAPIError(f"Invalid JSON response: {e}", status_code=resp.status_code) from e
        return model_cls.model_validate(data)

    async def _raise_http_error(self, resp: httpx.Response) -> None:
        try:
            payload = await resp.aread()
            text = payload.decode("utf-8", errors="replace")
        except Exception:
            text = ""
        raise OllamaAPIError(f"Ollama HTTP error {resp.status_code}: {text}", status_code=resp.status_code)


