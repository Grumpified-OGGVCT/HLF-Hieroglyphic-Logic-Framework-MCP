"""
Request models for API endpoints.

These models define the exact schema for incoming requests,
matching the AgentsKB compatibility contract with enhancements.
"""

from pydantic import BaseModel, Field, field_validator
from typing import Optional, List, Literal


class AskRequest(BaseModel):
    """
    Request model for /ask endpoint.
    
    Matches AgentsKB compatibility contract with enhancements
    for software version, stack pack, and realtime research.
    """
    
    question: str = Field(
        ...,
        min_length=5,
        max_length=500,
        description="Atomic, specific technical question. Must be at least 5 characters."
    )
    domain: Optional[str] = Field(
        default=None,
        description="Optional domain filter (e.g., 'postgresql', 'nextjs', 'typescript')"
    )
    tier: Optional[Literal["GOLD", "SILVER", "BRONZE"]] = Field(
        default=None,
        description="Quality tier filter"
    )
    realtime_research: bool = Field(
        default=False,
        description="If true, performs synchronous research on miss"
    )
    software_version: Optional[str] = Field(
        default=None,
        description="Specific software version to query (e.g., '16.0', '14.2.0')"
    )
    stack_pack: Optional[str] = Field(
        default=None,
        description="Stack pack ID to constrain retrieval context"
    )
    session_id: Optional[str] = Field(
        default=None,
        description="Optional session ID for provenance tracking"
    )

    @field_validator("question")
    @classmethod
    def validate_question(cls, v: str) -> str:
        """Ensure question is properly formatted."""
        v = v.strip()
        if not v:
            raise ValueError("Question cannot be empty or whitespace only")
        return v

    @field_validator("domain")
    @classmethod
    def normalize_domain(cls, v: Optional[str]) -> Optional[str]:
        """Normalize domain to lowercase."""
        if v is not None:
            return v.lower().strip()
        return v

    class Config:
        json_schema_extra = {
            "example": {
                "question": "What is the default max_connections in PostgreSQL 16?",
                "domain": "postgresql",
                "tier": "GOLD",
                "software_version": "16",
                "realtime_research": False
            }
        }


class AskBatchRequest(BaseModel):
    """
    Request model for /ask-batch endpoint.
    
    Supports batch processing with optional semantic deduplication.
    """
    
    questions: List[str] = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Array of questions (1-100 questions)"
    )
    domain: Optional[str] = Field(
        default=None,
        description="Optional domain filter for all questions"
    )
    dedupe: bool = Field(
        default=True,
        description="Whether to remove semantic duplicates before processing"
    )
    software_version: Optional[str] = Field(
        default=None,
        description="Specific software version for all questions"
    )
    stack_pack: Optional[str] = Field(
        default=None,
        description="Stack pack ID to constrain retrieval context"
    )

    @field_validator("questions")
    @classmethod
    def validate_questions(cls, v: List[str]) -> List[str]:
        """Validate each question in the batch."""
        validated = []
        for q in v:
            q = q.strip()
            if len(q) < 5:
                raise ValueError(f"Question too short: '{q}' (minimum 5 characters)")
            if len(q) > 500:
                raise ValueError(f"Question too long: '{q[:50]}...' (maximum 500 characters)")
            validated.append(q)
        return validated

    class Config:
        json_schema_extra = {
            "example": {
                "questions": [
                    "What is the default max_connections in PostgreSQL?",
                    "How do I create an index in PostgreSQL?"
                ],
                "domain": "postgresql",
                "dedupe": True
            }
        }


class LockRequest(BaseModel):
    """
    Request model for /lock endpoint.
    
    Generates SHA-256 hashes for specified KB entries
    for reproducible builds.
    """
    
    entry_ids: List[str] = Field(
        ...,
        min_length=1,
        description="List of KB entry IDs to generate locks for"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "entry_ids": [
                    "postgresql-max-connections-0001",
                    "postgresql-create-index-0002"
                ]
            }
        }


class VerifyLockRequest(BaseModel):
    """
    Request model for /verify-lock endpoint.
    
    Verifies that KB entries haven't drifted from locked hashes.
    """
    
    lockfile_version: str = Field(
        default="1",
        description="Lockfile schema version"
    )
    entries: dict = Field(
        ...,
        description="Mapping of entry_id to expected hash"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "lockfile_version": "1",
                "entries": {
                    "postgresql-max-connections-0001": {
                        "sha256": "abc123...",
                        "version": "16"
                    }
                }
            }
        }


class SearchRequest(BaseModel):
    """
    Request model for /search endpoint.
    
    Searches the Q&A database for questions and answers.
    """
    
    query: str = Field(
        ...,
        min_length=1,
        description="Search query"
    )
    domain: Optional[str] = Field(
        default=None,
        description="Optional domain filter"
    )
    limit: int = Field(
        default=10,
        ge=1,
        le=50,
        description="Maximum results to return"
    )
    tier: Optional[Literal["GOLD", "SILVER", "BRONZE"]] = Field(
        default=None,
        description="Quality tier filter"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "query": "postgresql",
                "domain": "database",
                "limit": 10
            }
        }

