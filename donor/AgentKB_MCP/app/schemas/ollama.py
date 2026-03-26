"""
Ollama API contracts (local + cloud).

Sources:
- API base URL and endpoints: https://docs.ollama.com/api/introduction
- Authentication (ollama.com API keys): https://docs.ollama.com/api/authentication
- Chat endpoint schema: https://docs.ollama.com/api/chat
- Generate endpoint schema: https://docs.ollama.com/api/generate
- Embeddings endpoint schema: https://docs.ollama.com/api/embed
- List models endpoint schema: https://docs.ollama.com/api/tags
- Streaming format (NDJSON): https://docs.ollama.com/api/streaming
- Web search + fetch REST API: https://docs.ollama.com/capabilities/web-search
"""

from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional, Union

from pydantic import BaseModel, Field


class OllamaError(BaseModel):
    error: str


class OllamaToolFunction(BaseModel):
    name: str
    description: Optional[str] = None
    arguments: Dict[str, Any] = Field(default_factory=dict)
    parameters: Optional[Dict[str, Any]] = None
    index: Optional[int] = None


class OllamaToolCall(BaseModel):
    type: Optional[Literal["function"]] = None
    function: OllamaToolFunction


class OllamaToolDefinition(BaseModel):
    type: Literal["function"] = "function"
    function: Dict[str, Any]


class OllamaMessage(BaseModel):
    role: Literal["system", "user", "assistant", "tool"]
    content: Union[str, List[Any]]

    # Tool calling fields (as used in capability docs)
    tool_calls: Optional[List[OllamaToolCall]] = None
    tool_name: Optional[str] = None

    # Thinking output (as returned by /api/chat for thinking-capable models)
    thinking: Optional[str] = None

    # Vision input/output (base64 strings)
    images: Optional[List[str]] = None


class OllamaChatRequest(BaseModel):
    model: str
    messages: List[OllamaMessage]
    tools: Optional[List[OllamaToolDefinition]] = None
    format: Optional[Union[Literal["json"], Dict[str, Any]]] = None
    options: Optional[Dict[str, Any]] = None
    stream: bool = True
    think: Optional[Union[bool, Literal["high", "medium", "low"]]] = None
    keep_alive: Optional[Union[str, int]] = None
    logprobs: Optional[bool] = None
    top_logprobs: Optional[int] = None


class OllamaChatResponse(BaseModel):
    model: str
    created_at: str
    message: OllamaMessage
    done: bool
    done_reason: Optional[str] = None
    total_duration: Optional[int] = None
    load_duration: Optional[int] = None
    prompt_eval_count: Optional[int] = None
    prompt_eval_duration: Optional[int] = None
    eval_count: Optional[int] = None
    eval_duration: Optional[int] = None
    logprobs: Optional[List[Dict[str, Any]]] = None


class OllamaGenerateRequest(BaseModel):
    model: str
    prompt: Optional[str] = None
    suffix: Optional[str] = None
    images: Optional[List[str]] = None
    format: Optional[Union[Literal["json"], Dict[str, Any]]] = None
    system: Optional[str] = None
    stream: bool = True
    think: Optional[Union[bool, Literal["high", "medium", "low"]]] = None
    raw: Optional[bool] = None
    keep_alive: Optional[Union[str, int]] = None
    options: Optional[Dict[str, Any]] = None
    logprobs: Optional[bool] = None
    top_logprobs: Optional[int] = None


class OllamaGenerateResponse(BaseModel):
    model: str
    created_at: str
    response: str
    done: bool
    done_reason: Optional[str] = None
    thinking: Optional[str] = None
    total_duration: Optional[int] = None
    load_duration: Optional[int] = None
    prompt_eval_count: Optional[int] = None
    prompt_eval_duration: Optional[int] = None
    eval_count: Optional[int] = None
    eval_duration: Optional[int] = None
    logprobs: Optional[List[Dict[str, Any]]] = None


class OllamaEmbedRequest(BaseModel):
    model: str
    input: Union[str, List[str]]
    truncate: bool = True
    dimensions: Optional[int] = None
    keep_alive: Optional[str] = None
    options: Optional[Dict[str, Any]] = None


class OllamaEmbedResponse(BaseModel):
    model: str
    embeddings: List[List[float]]
    total_duration: Optional[int] = None
    load_duration: Optional[int] = None
    prompt_eval_count: Optional[int] = None


class OllamaModelDetails(BaseModel):
    format: Optional[str] = None
    family: Optional[str] = None
    families: Optional[List[str]] = None
    parameter_size: Optional[str] = None
    quantization_level: Optional[str] = None


class OllamaModelInfo(BaseModel):
    name: str
    modified_at: Optional[str] = None
    size: Optional[int] = None
    digest: Optional[str] = None
    details: Optional[OllamaModelDetails] = None


class OllamaTagsResponse(BaseModel):
    models: List[OllamaModelInfo]


class OllamaWebSearchRequest(BaseModel):
    query: str
    max_results: Optional[int] = Field(default=None, description="default 5, max 10")


class OllamaWebSearchResult(BaseModel):
    title: str
    url: str
    content: str


class OllamaWebSearchResponse(BaseModel):
    results: List[OllamaWebSearchResult]


class OllamaWebFetchRequest(BaseModel):
    url: str


class OllamaWebFetchResponse(BaseModel):
    title: str
    content: str
    links: List[str]


