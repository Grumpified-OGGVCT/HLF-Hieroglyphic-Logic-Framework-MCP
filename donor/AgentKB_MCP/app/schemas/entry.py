"""
AGENTS-KB PRO (ENTERPRISE UPGRADE)
Schema: KBEntry with Graph RAG + Sandbox metadata.

This module preserves existing KBEntry fields by inheriting from app.models.kb.KBEntry,
then injects the new metadata fields exactly as specified in the upgrade blueprint.
"""

from typing import List, Optional

from pydantic import BaseModel, Field

from app.models.kb import KBEntry as _BaseKBEntry


class Relationship(BaseModel):
    subject: str
    predicate: str
    object: str


class KBEntry(_BaseKBEntry):
    # ... [PRESERVE EXISTING FIELDS] ...

    # NEW: Graph RAG Metadata
    related_entities: List[str] = Field(
        default_factory=list, description="Key concepts mentioned in this entry"
    )
    relationships: List[Relationship] = Field(
        default_factory=list, description="Subject-predicate-object triples"
    )

    # NEW: Sandbox Metadata
    verified_execution: bool = Field(
        default=False, description="Has this code been executed in a sandbox?"
    )
    execution_log: Optional[str] = Field(
        None, description="Output log from the verification run"
    )


