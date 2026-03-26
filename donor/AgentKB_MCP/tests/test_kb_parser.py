"""
Tests for KB parser.
"""

import pytest
from pathlib import Path

from app.services.kb_parser import KBParser
from app.models.kb import KBEntry


class TestKBParser:
    """Tests for KB parsing functionality."""
    
    def test_parse_entry_from_markdown(self, sample_kb_content):
        """Test parsing a single entry from Markdown."""
        parser = KBParser()
        entries = parser.parse_content(sample_kb_content)
        
        assert len(entries) == 2
        
        entry = entries[0]
        assert entry.id == "postgresql-max-connections-0001"
        assert "max_connections" in entry.question
        assert entry.domain == "postgresql"
        assert entry.software_version == "16.0"
        assert entry.confidence == 1.00
        assert entry.tier == "GOLD"
        assert len(entry.sources) >= 1
        assert len(entry.related_questions) >= 3
    
    def test_parse_file(self, sample_kb_file):
        """Test parsing a KB file."""
        parser = KBParser()
        entries = parser.parse_file(sample_kb_file)
        
        assert len(entries) == 2
        assert all(e.domain == "postgresql" for e in entries)
    
    def test_entry_to_markdown(self):
        """Test serializing entry back to Markdown."""
        entry = KBEntry(
            id="test-entry-0001",
            question="What is a test?",
            answer="A test is a procedure to verify functionality.",
            domain="testing",
            software_version="1.0",
            valid_until="latest",
            confidence=1.0,
            tier="GOLD",
            sources=["https://example.com/docs"],
            related_questions=["How to write tests?", "Why test?", "Test types?"]
        )
        
        markdown = entry.to_markdown()
        
        assert "### ID: test-entry-0001" in markdown
        assert "**Question**: What is a test?" in markdown
        assert "**Domain**: testing" in markdown
        assert "**Confidence**: 1.00" in markdown
    
    def test_entry_sha256(self):
        """Test SHA256 hash generation."""
        entry = KBEntry(
            id="test-entry-0001",
            question="Test",
            answer="Answer",
            domain="test",
            software_version="1.0",
            valid_until="latest",
            confidence=1.0,
            tier="GOLD",
            sources=[],
            related_questions=[]
        )
        
        hash1 = entry.sha256
        hash2 = entry.sha256
        
        # Same content should produce same hash
        assert hash1 == hash2
        assert len(hash1) == 64  # SHA256 hex length
    
    def test_validate_entry_valid(self):
        """Test validation of a valid entry."""
        parser = KBParser()
        entry = KBEntry(
            id="postgresql-test-0001",
            question="What is PostgreSQL?",
            answer="PostgreSQL is an open-source relational database system with over 35 years of development.",
            domain="postgresql",
            software_version="16.0",
            valid_until="latest",
            confidence=1.0,
            tier="GOLD",
            sources=["https://postgresql.org"],
            related_questions=["Q1", "Q2", "Q3"]
        )
        
        is_valid, errors = parser.validate_entry(entry)
        
        assert is_valid
        assert len(errors) == 0
    
    def test_validate_entry_invalid(self):
        """Test validation catches errors."""
        parser = KBParser()
        entry = KBEntry(
            id="bad-id",  # Doesn't match domain
            question="Q",  # Too short
            answer="A",  # Too short
            domain="postgresql",
            software_version="",  # Missing
            valid_until="",  # Missing
            confidence=1.5,  # Out of range
            tier="PLATINUM",  # Invalid tier
            sources=[],  # Empty
            related_questions=["Q1"]  # Not enough
        )
        
        is_valid, errors = parser.validate_entry(entry)
        
        assert not is_valid
        assert len(errors) > 0
    
    def test_version_compatibility(self, sample_kb_content):
        """Test version compatibility checking."""
        parser = KBParser()
        entries = parser.parse_content(sample_kb_content)
        entry = entries[0]
        
        metadata = entry.metadata
        
        # Latest should be compatible with no version
        assert metadata.is_version_compatible(None)
        
        # Same version should be compatible
        assert metadata.is_version_compatible("16.0")
        
        # Different major version might not be compatible
        # (depends on implementation)

