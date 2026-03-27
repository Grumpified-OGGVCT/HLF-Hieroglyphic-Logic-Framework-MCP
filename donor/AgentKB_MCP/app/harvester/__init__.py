"""
Knowledge Harvester - Proactive KB Expansion

This module provides automated monitoring of official documentation sources
to continuously expand the knowledge base without waiting for user queries.

Status: SCAFFOLD - Not yet fully implemented
"""

from app.harvester.registry import SourceRegistry
from app.harvester.detector import ChangeDetector
from app.harvester.generator import EntryGenerator

__all__ = [
    "SourceRegistry",
    "ChangeDetector",
    "EntryGenerator",
]

