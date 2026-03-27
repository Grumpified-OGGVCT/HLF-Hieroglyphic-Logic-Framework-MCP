"""
MCP server utilities.

Task 5: Implement format_mcp_response to sanitize JSON output for coding agents.

This module does not start a server; it provides response formatting helpers that
MCP tool handlers can use to return safe JSON for agent consumption.
"""

from __future__ import annotations

import json
import re
from typing import Any, Dict, Optional, Union


def _extract_json_object(text: str) -> Optional[dict]:
    """
    Extract the first JSON object from a string.

    Supports:
    - raw JSON
    - JSON wrapped in markdown fences
    - JSON embedded in surrounding text
    """
    s = (text or "").strip()
    if not s:
        return None

    # Strip ```json fences if present
    s = re.sub(r"^\s*```(?:json)?\s*", "", s, flags=re.IGNORECASE)
    s = re.sub(r"\s*```\s*$", "", s)
    s = s.strip()

    # Try parse as-is
    try:
        obj = json.loads(s)
        return obj if isinstance(obj, dict) else None
    except Exception:
        pass

    # Extract first {...} block
    m = re.search(r"\{[\s\S]*\}", s)
    if not m:
        return None
    try:
        obj = json.loads(m.group(0))
        return obj if isinstance(obj, dict) else None
    except Exception:
        return None


def format_mcp_response(payload: Union[dict, str], *, fallback_text: Optional[str] = None) -> str:
    """
    Return a JSON string safe for coding agents.

    - Ensures output is valid JSON (a single object)
    - Removes markdown fences around JSON if present
    - If payload is a string, attempts to extract a JSON object
    - If extraction fails, wraps raw text into { "text": "...", "ok": false }
    """
    if isinstance(payload, dict):
        safe_obj: Dict[str, Any] = payload
        return json.dumps(safe_obj, ensure_ascii=False)

    # payload is a string
    extracted = _extract_json_object(payload)
    if extracted is not None:
        return json.dumps(extracted, ensure_ascii=False)

    text = (fallback_text if fallback_text is not None else str(payload)).strip()
    return json.dumps({"ok": False, "text": text}, ensure_ascii=False)


