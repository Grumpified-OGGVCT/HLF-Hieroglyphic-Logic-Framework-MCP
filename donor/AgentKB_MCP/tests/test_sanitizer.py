"""
Tests for PII sanitizer.
"""

import pytest

from app.services.sanitizer import PIISanitizer, SensitiveType


class TestPIISanitizer:
    """Tests for PII/secrets detection."""
    
    @pytest.fixture
    def sanitizer(self):
        return PIISanitizer()
    
    def test_detect_api_key(self, sanitizer):
        """Test detection of API keys."""
        text = "Set your api_key=sk_live_abc123def456ghi789jkl012mno345pqr678"
        
        matches = sanitizer.scan(text)
        
        assert len(matches) > 0
        types = [m.type for m in matches]
        assert SensitiveType.API_KEY in types or SensitiveType.SECRET in types
    
    def test_detect_password(self, sanitizer):
        """Test detection of passwords."""
        text = "The password is: MySecretPassword123!"
        
        matches = sanitizer.scan(text)
        
        assert len(matches) > 0
        assert any(m.type == SensitiveType.PASSWORD for m in matches)
    
    def test_detect_internal_ip(self, sanitizer):
        """Test detection of internal IP addresses."""
        text = "Connect to the server at 192.168.1.100"
        
        matches = sanitizer.scan(text)
        
        assert len(matches) > 0
        assert any(m.type == SensitiveType.IP_ADDRESS for m in matches)
    
    def test_detect_jwt(self, sanitizer):
        """Test detection of JWT tokens."""
        text = "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dozjgNryP4J3jVmNHl0w5N_XgL0n3I9PlFUP0THsR8U"
        
        matches = sanitizer.scan(text)
        
        assert len(matches) > 0
        assert any(m.type == SensitiveType.JWT for m in matches)
    
    def test_detect_aws_key(self, sanitizer):
        """Test detection of AWS keys."""
        text = "AWS_ACCESS_KEY_ID=AKIAIOSFODNN7EXAMPLE"
        
        matches = sanitizer.scan(text)
        
        assert len(matches) > 0
        assert any(m.type == SensitiveType.AWS_KEY for m in matches)
    
    def test_no_false_positive_technical(self, sanitizer):
        """Test that technical content isn't falsely flagged."""
        text = "What is the default max_connections in PostgreSQL 16?"
        
        assert not sanitizer.contains_sensitive(text)
    
    def test_sanitize_text(self, sanitizer):
        """Test text sanitization."""
        text = "Connect with password: secret123 to 192.168.1.1"
        
        sanitized, matches = sanitizer.sanitize(text)
        
        assert "secret123" not in sanitized
        assert "[REDACTED:" in sanitized
    
    def test_contains_sensitive(self, sanitizer):
        """Test the contains_sensitive helper."""
        safe = "How to create a PostgreSQL index?"
        unsafe = "api_key=sk_test_abcdefghijklmnop1234567890"
        
        assert not sanitizer.contains_sensitive(safe)
        assert sanitizer.contains_sensitive(unsafe)
    
    def test_get_summary(self, sanitizer):
        """Test the summary function."""
        text = "api_key=abc123def456 and password=secret123"
        
        summary = sanitizer.get_summary(text)
        
        assert summary["total_matches"] > 0
        assert "by_type" in summary
        assert summary["contains_sensitive"]

