"""
Direct Ollama Cloud API Gateway for HLF

Bypasses local Ollama daemon entirely.
Uses https://ollama.com/api directly with API key authentication.

Key Features:
- Lower latency (no local daemon hop)
- Native structured outputs
- Tool calling support
- Automatic fallback handling
"""

import os
import json
import time
import requests
from typing import Optional, Dict, Any, List, Generator, Union
from dataclasses import dataclass
from enum import Enum
import logging

logger = logging.getLogger(__name__)

class ModelCapability(Enum):
    """Capabilities available in Ollama Cloud models"""
    CHAT = "chat"
    TOOLS = "tools"
    STRUCTURED_OUTPUTS = "structured_outputs"
    EMBEDDINGS = "embeddings"


@dataclass
class OllamaResponse:
    """Structured response from Ollama Cloud API"""
    content: str
    model: str
    usage: Dict[str, int]
    structured_output: Optional[Dict[str, Any]] = None
    tool_calls: Optional[List[Dict]] = None
    latency_ms: float = 0.0
    success: bool = True
    error: Optional[str] = None


class OllamaCloudGateway:
    """
    Direct gateway to Ollama Cloud API.
    
    Bypasses local Ollama daemon for lower latency and simpler setup.
    Supports chat completions, structured outputs, and tool calling.
    """
    
    # Ollama Cloud API endpoints
    BASE_URL = "https://ollama.com/api"
    CHAT_ENDPOINT = f"{BASE_URL}/chat/completions"
    GENERATE_ENDPOINT = f"{BASE_URL}/generate"
    EMBED_ENDPOINT = f"{BASE_URL}/embeddings"
    MODELS_ENDPOINT = f"{BASE_URL}/tags"
    
    # Recommended models for HLF
    CONTROLLER_MODEL = "gpt-oss:20b-cloud"  # Best for orchestration
    CODER_MODEL = "qwen3-coder:480b-cloud"  # Best for code generation
    REASONING_MODEL = "glm-5:cloud"  # Best for complex reasoning
    
    def __init__(self, api_key: Optional[str] = None, timeout: int = 60):
        """
        Initialize Ollama Cloud gateway.
        
        Args:
            api_key: Ollama Cloud API key (or from OLLAMA_API_KEY env var)
            timeout: Request timeout in seconds
        """
        self.api_key = api_key or os.getenv("OLLAMA_API_KEY")
        self.timeout = timeout
        self.session = requests.Session()
        
        if not self.api_key:
            logger.warning("No OLLAMA_API_KEY provided. Cloud API calls will fail.")
        
        self._headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
    
    def handshake(self) -> Dict[str, Any]:
        """
        Perform handshake with Ollama Cloud API.
        
        Verifies connectivity and retrieves available models.
        
        Returns:
            Dictionary with status, models, and latency info
        """
        start_time = time.time()
        
        try:
            response = self.session.get(
                self.MODELS_ENDPOINT,
                headers=self._headers,
                timeout=10
            )
            response.raise_for_status()
            
            latency_ms = (time.time() - start_time) * 1000
            models = response.json().get("models", [])
            
            return {
                "status": "connected",
                "signal": "📡",
                "latency_ms": round(latency_ms, 2),
                "models_available": len(models),
                "recommended_models": [
                    m for m in models 
                    if any(r in m.get("name", "") for r in ["gpt-oss", "qwen3-coder", "glm-5"])
                ],
                "api_version": response.headers.get("Ollama-Version", "unknown"),
            }
            
        except requests.exceptions.RequestException as e:
            latency_ms = (time.time() - start_time) * 1000
            return {
                "status": "disconnected",
                "signal": "❌",
                "latency_ms": round(latency_ms, 2),
                "error": str(e),
                "models_available": 0,
            }
    
    def is_connected(self) -> bool:
        """Quick check if cloud API is accessible"""
        try:
            result = self.handshake()
            return result["status"] == "connected"
        except Exception:
            return False
    
    def chat(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        tools: Optional[List[Dict]] = None,
        tool_choice: Optional[str] = None,
        stream: bool = False,
    ) -> Union[OllamaResponse, Generator[str, None, None]]:
        """
        Send chat completion request to Ollama Cloud.
        
        Args:
            messages: List of message dicts with 'role' and 'content'
            model: Model to use (defaults to CONTROLLER_MODEL)
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            tools: Optional list of tool definitions
            tool_choice: Tool selection strategy
            stream: Whether to stream response
            
        Returns:
            OllamaResponse or generator if streaming
        """
        model = model or self.CONTROLLER_MODEL
        
        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "stream": stream,
        }
        
        if max_tokens:
            payload["max_tokens"] = max_tokens
        
        if tools:
            payload["tools"] = tools
        
        if tool_choice:
            payload["tool_choice"] = tool_choice
        
        start_time = time.time()
        
        try:
            if stream:
                return self._stream_chat(payload)
            
            response = self.session.post(
                self.CHAT_ENDPOINT,
                headers=self._headers,
                json=payload,
                timeout=self.timeout
            )
            response.raise_for_status()
            
            latency_ms = (time.time() - start_time) * 1000
            data = response.json()
            
            message = data.get("message", {})
            content = message.get("content", "")
            
            # Check for tool calls
            tool_calls = message.get("tool_calls")
            
            return OllamaResponse(
                content=content,
                model=data.get("model", model),
                usage=data.get("usage", {}),
                tool_calls=tool_calls,
                latency_ms=latency_ms,
                success=True
            )
            
        except requests.exceptions.RequestException as e:
            latency_ms = (time.time() - start_time) * 1000
            logger.error(f"Ollama Cloud API error: {e}")
            return OllamaResponse(
                content="",
                model=model,
                usage={},
                latency_ms=latency_ms,
                success=False,
                error=str(e)
            )
    
    def _stream_chat(self, payload: Dict) -> Generator[str, None, None]:
        """Stream chat response"""
        try:
            response = self.session.post(
                self.CHAT_ENDPOINT,
                headers=self._headers,
                json=payload,
                stream=True,
                timeout=self.timeout
            )
            response.raise_for_status()
            
            for line in response.iter_lines():
                if line:
                    try:
                        data = json.loads(line.decode("utf-8"))
                        if "message" in data and "content" in data["message"]:
                            yield data["message"]["content"]
                    except json.JSONDecodeError:
                        continue
                        
        except requests.exceptions.RequestException as e:
            logger.error(f"Streaming error: {e}")
            yield f"[ERROR: {e}]"
    
    def generate_structured(
        self,
        prompt: str,
        schema: Dict[str, Any],
        model: Optional[str] = None,
        temperature: float = 0.2,
    ) -> OllamaResponse:
        """
        Generate structured JSON output.
        
        Args:
            prompt: The prompt to send
            schema: JSON Schema for validation
            model: Model to use
            temperature: Lower for structured outputs
            
        Returns:
            OllamaResponse with structured_output field
        """
        model = model or self.CONTROLLER_MODEL
        
        messages = [
            {
                "role": "system",
                "content": f"You must respond with valid JSON matching this schema: {json.dumps(schema)}"
            },
            {"role": "user", "content": prompt}
        ]
        
        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "format": {"type": "json_object"},
            "stream": False,
        }
        
        start_time = time.time()
        
        try:
            response = self.session.post(
                self.CHAT_ENDPOINT,
                headers=self._headers,
                json=payload,
                timeout=self.timeout
            )
            response.raise_for_status()
            
            latency_ms = (time.time() - start_time) * 1000
            data = response.json()
            
            message = data.get("message", {})
            content = message.get("content", "")
            
            # Parse structured output
            structured = None
            try:
                structured = json.loads(content)
            except json.JSONDecodeError as e:
                logger.warning(f"Failed to parse structured output: {e}")
            
            return OllamaResponse(
                content=content,
                model=data.get("model", model),
                usage=data.get("usage", {}),
                structured_output=structured,
                latency_ms=latency_ms,
                success=structured is not None
            )
            
        except requests.exceptions.RequestException as e:
            latency_ms = (time.time() - start_time) * 1000
            logger.error(f"Structured generation error: {e}")
            return OllamaResponse(
                content="",
                model=model,
                usage={},
                latency_ms=latency_ms,
                success=False,
                error=str(e)
            )
    
    def embed(self, texts: List[str], model: str = "nomic-embed-text") -> Optional[List[List[float]]]:
        """
        Generate embeddings for texts.
        
        Args:
            texts: List of texts to embed
            model: Embedding model to use
            
        Returns:
            List of embedding vectors or None on error
        """
        payload = {
            "model": model,
            "input": texts,
        }
        
        try:
            response = self.session.post(
                self.EMBED_ENDPOINT,
                headers=self._headers,
                json=payload,
                timeout=self.timeout
            )
            response.raise_for_status()
            
            data = response.json()
            embeddings = data.get("embeddings", [])
            return embeddings
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Embedding error: {e}")
            return None
    
    def get_recommended_model(self, task: str) -> str:
        """
        Get recommended model for specific task.
        
        Args:
            task: One of 'controller', 'coder', 'reasoning', 'general'
            
        Returns:
            Model name
        """
        models = {
            "controller": self.CONTROLLER_MODEL,
            "coder": self.CODER_MODEL,
            "reasoning": self.REASONING_MODEL,
            "general": self.CONTROLLER_MODEL,
        }
        return models.get(task, self.CONTROLLER_MODEL)


class ModelGateway:
    """
    Unified model gateway with Ollama Cloud as primary.
    
    Falls back to local Ollama daemon if cloud unavailable.
    """
    
    def __init__(
        self,
        use_cloud_direct: bool = True,
        cloud_api_key: Optional[str] = None,
        local_base_url: str = "http://localhost:11434"
    ):
        self.use_cloud_direct = use_cloud_direct
        self.local_base_url = local_base_url
        self.cloud = OllamaCloudGateway(api_key=cloud_api_key) if use_cloud_direct else None
        self._cloud_available = None
    
    def _check_cloud(self) -> bool:
        """Check if cloud API is available (cached)"""
        if self._cloud_available is None:
            self._cloud_available = self.cloud.is_connected() if self.cloud else False
        return self._cloud_available
    
    def chat(self, messages: List[Dict[str, str]], **kwargs) -> OllamaResponse:
        """Chat with automatic fallback"""
        if self.use_cloud_direct and self._check_cloud():
            return self.cloud.chat(messages, **kwargs)
        
        # Fallback to local Ollama daemon
        return self._local_chat(messages, **kwargs)
    
    def _local_chat(self, messages: List[Dict[str, str]], **kwargs) -> OllamaResponse:
        """Fallback to local Ollama daemon"""
        try:
            import requests
            
            model = kwargs.get("model", "llama3.2")
            temperature = kwargs.get("temperature", 0.7)
            
            payload = {
                "model": model,
                "messages": messages,
                "temperature": temperature,
                "stream": False,
            }
            
            start_time = time.time()
            response = requests.post(
                f"{self.local_base_url}/api/chat",
                json=payload,
                timeout=60
            )
            response.raise_for_status()
            latency_ms = (time.time() - start_time) * 1000
            
            data = response.json()
            message = data.get("message", {})
            
            return OllamaResponse(
                content=message.get("content", ""),
                model=data.get("model", model),
                usage=data.get("usage", {}),
                latency_ms=latency_ms,
                success=True
            )
            
        except Exception as e:
            return OllamaResponse(
                content="",
                model=kwargs.get("model", "unknown"),
                usage={},
                latency_ms=0,
                success=False,
                error=f"Local fallback failed: {e}"
            )
    
    def generate_structured(self, prompt: str, schema: Dict[str, Any], **kwargs) -> OllamaResponse:
        """Generate structured output with fallback"""
        if self.use_cloud_direct and self._check_cloud():
            return self.cloud.generate_structured(prompt, schema, **kwargs)
        
        # Local fallback - try to parse JSON from text
        messages = [
            {"role": "user", "content": f"{prompt}\n\nRespond with valid JSON only."}
        ]
        response = self._local_chat(messages, **kwargs)
        
        if response.success:
            try:
                structured = json.loads(response.content)
                response.structured_output = structured
            except json.JSONDecodeError:
                response.success = False
                response.error = "Failed to parse JSON from local model"
        
        return response


# Convenience function
def create_gateway(profile: str = "P0") -> ModelGateway:
    """
    Create appropriate model gateway for profile.
    
    Args:
        profile: "P0", "P1", or "P2"
        
    Returns:
        Configured ModelGateway instance
    """
    if profile == "P0":
        # P0: Cloud-only, direct API
        return ModelGateway(use_cloud_direct=True)
    elif profile == "P1":
        # P1: Cloud preferred, local fallback
        return ModelGateway(use_cloud_direct=True)
    else:
        # P2: Full stack, local preferred
        return ModelGateway(use_cloud_direct=False)
