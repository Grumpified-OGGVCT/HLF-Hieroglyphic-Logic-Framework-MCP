"""
AGENTS-KB PRO (ENTERPRISE UPGRADE)
Schema: API request models (schema-first layer).

This module preserves existing API request fields by inheriting from app.models.requests,
then adds the ResponseStyle control exactly as defined in the upgrade blueprint.
"""

from enum import Enum

from pydantic import Field

from app.models.requests import AskRequest as _BaseAskRequest


class ResponseStyle(str, Enum):
    VERBOSE = "verbose"  # Current default (Full reasoning)
    CONCISE = "concise"  # Short answers
    CODE_FIRST = "code_first"  # Code block top, text bottom
    FEYNMAN = "feynman"  # Simple analogies (User constraint)


class AskRequest(_BaseAskRequest):
    # ... [PRESERVE EXISTING FIELDS] ...
    style: ResponseStyle = Field(
        default=ResponseStyle.VERBOSE, description="Output format style"
    )


