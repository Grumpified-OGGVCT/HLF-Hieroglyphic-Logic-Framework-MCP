"""
PII and secrets sanitization service.

Detects potentially sensitive information in questions
before sending them to the Research Agent.
"""

import re
import logging
from typing import List, Tuple, Optional
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class SensitiveType(str, Enum):
    """Types of sensitive information."""
    
    API_KEY = "api_key"
    PASSWORD = "password"
    SECRET = "secret"
    TOKEN = "token"
    IP_ADDRESS = "ip_address"
    EMAIL = "email"
    CREDIT_CARD = "credit_card"
    SSN = "ssn"
    PHONE = "phone"
    AWS_KEY = "aws_key"
    PRIVATE_KEY = "private_key"
    JWT = "jwt"
    INTERNAL_PATH = "internal_path"
    CONNECTION_STRING = "connection_string"


@dataclass
class SensitiveMatch:
    """A detected sensitive pattern match."""
    
    type: SensitiveType
    value: str
    start: int
    end: int
    confidence: float


class PIISanitizer:
    """
    Detects and sanitizes PII and secrets in text.
    
    Used to prevent sensitive information from being sent
    to external research services.
    """
    
    # Pattern definitions
    PATTERNS = {
        # API keys and tokens
        SensitiveType.API_KEY: [
            r'(?i)(api[_-]?key|apikey)\s*[:=]\s*["\']?([a-zA-Z0-9_\-]{16,})["\']?',
            r'(?i)sk[-_]?[a-zA-Z0-9]{20,}',  # Stripe-style keys
            r'(?i)ak_[a-zA-Z0-9_\-]{20,}',  # AgentsKB-style keys
        ],
        
        # Passwords
        SensitiveType.PASSWORD: [
            r'(?i)(password|passwd|pwd)\s*[:=]\s*["\']?([^\s"\']{8,})["\']?',
            r'(?i)--password\s+["\']?([^\s"\']+)["\']?',
        ],
        
        # Secrets
        SensitiveType.SECRET: [
            r'(?i)(secret|client[_-]?secret)\s*[:=]\s*["\']?([a-zA-Z0-9_\-]{16,})["\']?',
            r'(?i)AKIA[0-9A-Z]{16}',  # AWS access key ID
        ],
        
        # Tokens
        SensitiveType.TOKEN: [
            r'(?i)(token|auth[_-]?token|access[_-]?token)\s*[:=]\s*["\']?([a-zA-Z0-9_\-\.]{20,})["\']?',
            r'(?i)bearer\s+[a-zA-Z0-9_\-\.]{20,}',
        ],
        
        # IP addresses (internal ranges especially)
        SensitiveType.IP_ADDRESS: [
            r'\b10\.\d{1,3}\.\d{1,3}\.\d{1,3}\b',  # 10.x.x.x
            r'\b172\.(1[6-9]|2[0-9]|3[0-1])\.\d{1,3}\.\d{1,3}\b',  # 172.16-31.x.x
            r'\b192\.168\.\d{1,3}\.\d{1,3}\b',  # 192.168.x.x
        ],
        
        # Email addresses
        SensitiveType.EMAIL: [
            r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
        ],
        
        # Credit cards
        SensitiveType.CREDIT_CARD: [
            r'\b(?:4[0-9]{12}(?:[0-9]{3})?|5[1-5][0-9]{14}|3[47][0-9]{13})\b',
        ],
        
        # AWS keys
        SensitiveType.AWS_KEY: [
            r'(?i)AKIA[0-9A-Z]{16}',
            r'(?i)aws[_-]?access[_-]?key[_-]?id\s*[:=]\s*["\']?([A-Z0-9]{20})["\']?',
            r'(?i)aws[_-]?secret[_-]?access[_-]?key\s*[:=]\s*["\']?([A-Za-z0-9/+=]{40})["\']?',
        ],
        
        # Private keys
        SensitiveType.PRIVATE_KEY: [
            r'-----BEGIN\s+(RSA|DSA|EC|OPENSSH)?\s*PRIVATE KEY-----',
            r'-----BEGIN\s+PGP\s+PRIVATE\s+KEY\s+BLOCK-----',
        ],
        
        # JWT tokens
        SensitiveType.JWT: [
            r'\beyJ[A-Za-z0-9_-]+\.eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\b',
        ],
        
        # Internal paths
        SensitiveType.INTERNAL_PATH: [
            r'(?i)/home/[a-z_][a-z0-9_-]*/[^\s]+',
            r'(?i)C:\\Users\\[^\\]+\\[^\s]+',
            r'(?i)/var/log/[^\s]+',
            r'(?i)/etc/[a-z]+/[^\s]+',
        ],
        
        # Connection strings
        SensitiveType.CONNECTION_STRING: [
            r'(?i)(mongodb|postgresql|mysql|redis)://[^\s]+:[^\s]+@[^\s]+',
            r'(?i)Server=[^;]+;.*Password=[^;]+',
        ],
    }
    
    def __init__(self, strict_mode: bool = False):
        """
        Initialize the sanitizer.
        
        Args:
            strict_mode: If True, flag any potential match.
                        If False, use confidence scoring.
        """
        self.strict_mode = strict_mode
        self._compiled_patterns = {}
        self._compile_patterns()
    
    def _compile_patterns(self) -> None:
        """Compile regex patterns for efficiency."""
        for sensitive_type, patterns in self.PATTERNS.items():
            self._compiled_patterns[sensitive_type] = [
                re.compile(pattern) for pattern in patterns
            ]
    
    def scan(self, text: str) -> List[SensitiveMatch]:
        """
        Scan text for sensitive information.
        
        Args:
            text: The text to scan
            
        Returns:
            List of SensitiveMatch objects for detected patterns
        """
        matches = []
        
        for sensitive_type, patterns in self._compiled_patterns.items():
            for pattern in patterns:
                for match in pattern.finditer(text):
                    # Determine confidence based on pattern type
                    confidence = self._calculate_confidence(sensitive_type, match)
                    
                    if confidence >= 0.5 or self.strict_mode:
                        matches.append(SensitiveMatch(
                            type=sensitive_type,
                            value=match.group(0)[:50] + "..." if len(match.group(0)) > 50 else match.group(0),
                            start=match.start(),
                            end=match.end(),
                            confidence=confidence
                        ))
        
        return matches
    
    def _calculate_confidence(self, sensitive_type: SensitiveType, match: re.Match) -> float:
        """
        Calculate confidence score for a match.
        
        Args:
            sensitive_type: Type of sensitive info
            match: The regex match object
            
        Returns:
            Confidence score between 0 and 1
        """
        # High confidence types (almost always sensitive)
        high_confidence_types = {
            SensitiveType.PRIVATE_KEY,
            SensitiveType.AWS_KEY,
            SensitiveType.JWT,
            SensitiveType.CONNECTION_STRING,
            SensitiveType.CREDIT_CARD,
        }
        
        if sensitive_type in high_confidence_types:
            return 0.95
        
        # Medium confidence (context-dependent)
        medium_confidence_types = {
            SensitiveType.API_KEY,
            SensitiveType.SECRET,
            SensitiveType.TOKEN,
            SensitiveType.PASSWORD,
        }
        
        if sensitive_type in medium_confidence_types:
            # Check if it looks like actual credentials vs example
            value = match.group(0).lower()
            if any(placeholder in value for placeholder in [
                "example", "your", "xxx", "placeholder", "test", "fake", "demo"
            ]):
                return 0.3
            return 0.8
        
        # Lower confidence (might be legitimate technical content)
        if sensitive_type in {SensitiveType.IP_ADDRESS, SensitiveType.EMAIL}:
            return 0.6
        
        return 0.5
    
    def contains_sensitive(self, text: str, threshold: float = 0.7) -> bool:
        """
        Check if text contains sensitive information.
        
        Args:
            text: The text to check
            threshold: Minimum confidence to consider sensitive
            
        Returns:
            True if sensitive info detected above threshold
        """
        matches = self.scan(text)
        return any(m.confidence >= threshold for m in matches)
    
    def get_sensitive_types(self, text: str, threshold: float = 0.7) -> List[SensitiveType]:
        """
        Get types of sensitive information found.
        
        Args:
            text: The text to check
            threshold: Minimum confidence to consider
            
        Returns:
            List of SensitiveType enums found
        """
        matches = self.scan(text)
        return list(set(
            m.type for m in matches if m.confidence >= threshold
        ))
    
    def sanitize(self, text: str) -> Tuple[str, List[SensitiveMatch]]:
        """
        Sanitize text by redacting sensitive information.
        
        Args:
            text: The text to sanitize
            
        Returns:
            Tuple of (sanitized text, list of matches found)
        """
        matches = self.scan(text)
        
        # Sort by position (reverse) to replace from end to start
        matches.sort(key=lambda m: m.start, reverse=True)
        
        sanitized = text
        for match in matches:
            if match.confidence >= 0.5:
                redacted = f"[REDACTED:{match.type.value}]"
                sanitized = sanitized[:match.start] + redacted + sanitized[match.end:]
        
        return sanitized, matches
    
    def get_summary(self, text: str) -> dict:
        """
        Get a summary of sensitive content detection.
        
        Args:
            text: The text to analyze
            
        Returns:
            Summary dict with counts and types
        """
        matches = self.scan(text)
        
        by_type = {}
        for match in matches:
            type_name = match.type.value
            if type_name not in by_type:
                by_type[type_name] = {"count": 0, "max_confidence": 0.0}
            by_type[type_name]["count"] += 1
            by_type[type_name]["max_confidence"] = max(
                by_type[type_name]["max_confidence"],
                match.confidence
            )
        
        high_confidence = [m for m in matches if m.confidence >= 0.8]
        
        return {
            "total_matches": len(matches),
            "high_confidence_matches": len(high_confidence),
            "by_type": by_type,
            "contains_sensitive": self.contains_sensitive(text),
            "recommendation": "needs_review" if high_confidence else "safe"
        }

