"""
HLF Profile Management

P0: Cloud-only Core
    - Python + SQLite only
    - Direct Ollama Cloud API only when no local daemon is available
    - SQLite hot tier
    - 5 minimal host functions
    - ~50MB RAM idle

P1: Cloud-assisted Workstation  
    - P0 + LRU cache hot tier
    - Local Ollama daemon primary, cloud backup allowed
    - Extended host functions
    - ~75MB RAM idle

P2: Full Sovereign Lite
    - Full stack with Redis
    - Local Ollama daemon + cloud fallback
    - Complete host functions
    - ~200MB RAM idle
"""

import os
import json
from typing import Dict, Any, Optional
from dataclasses import dataclass, asdict
from enum import Enum


class HLFProfile(Enum):
    """HLF deployment profiles"""
    P0 = "P0"  # Cloud-only Core
    P1 = "P1"  # Cloud-assisted Workstation
    P2 = "P2"  # Full Sovereign Lite


@dataclass
class ProfileConfig:
    """Configuration for an HLF profile"""
    name: str
    description: str
    
    # Infrastructure
    use_redis: bool
    use_docker: bool
    use_lru_cache: bool
    
    # Inference
    ollama_mode: str  # "cloud_direct", "cloud_via_daemon", "local_daemon", "hybrid"
    default_model: str
    
    # Memory
    hot_tier: str  # "sqlite", "lru", "redis"
    warm_tier: str  # Always "sqlite"
    cold_tier: str  # Always "parquet"
    
    # Host Functions
    host_function_set: str  # "minimal", "extended", "full"
    
    # Security
    require_acl: bool
    enable_sentinel: bool
    
    # Expected footprint
    expected_ram_mb: int


class ProfileManager:
    """Manages HLF profiles and configuration"""
    
    # Profile definitions
    PROFILES = {
        "P0": ProfileConfig(
            name="P0",
            description="Cloud-only Core - Minimal footprint, full intelligence",
            use_redis=False,
            use_docker=False,
            use_lru_cache=False,
            ollama_mode="local_or_cloud_backup",
            default_model="gpt-oss:20b-cloud",
            hot_tier="sqlite",
            warm_tier="sqlite",
            cold_tier="parquet",
            host_function_set="minimal",
            require_acl=False,
            enable_sentinel=False,
            expected_ram_mb=50
        ),
        "P1": ProfileConfig(
            name="P1",
            description="Cloud-assisted Workstation - Performance optimized",
            use_redis=False,
            use_docker=False,
            use_lru_cache=True,
            ollama_mode="local_daemon",
            default_model="gpt-oss:20b-cloud",
            hot_tier="lru",
            warm_tier="sqlite",
            cold_tier="parquet",
            host_function_set="extended",
            require_acl=True,
            enable_sentinel=False,
            expected_ram_mb=75
        ),
        "P2": ProfileConfig(
            name="P2",
            description="Full Sovereign Lite - Maximum capability",
            use_redis=True,
            use_docker=True,
            use_lru_cache=True,
            ollama_mode="local_daemon",
            default_model="llama3.2",
            hot_tier="redis",
            warm_tier="sqlite",
            cold_tier="parquet",
            host_function_set="full",
            require_acl=True,
            enable_sentinel=True,
            expected_ram_mb=200
        ),
    }
    
    def __init__(self, profile: Optional[str] = None):
        """
        Initialize profile manager.
        
        Args:
            profile: Profile name (P0, P1, P2) or None to auto-detect
        """
        self.current_profile = profile or self._detect_profile()
        self.config = self.PROFILES.get(self.current_profile, self.PROFILES["P0"])
    
    def _detect_profile(self) -> str:
        """Auto-detect appropriate profile from environment"""
        # Check explicit setting
        env_profile = os.getenv("HLF_PROFILE")
        if env_profile in ["P0", "P1", "P2"]:
            return env_profile
        
        # Check for local Ollama
        if self._has_local_ollama():
            return "P2"
        
        # Check for API key (can use cloud)
        if os.getenv("OLLAMA_API_KEY"):
            return "P0"
        
        # Default to P0 (most compatible)
        return "P0"
    
    def _has_local_ollama(self) -> bool:
        """Check if local Ollama daemon is available"""
        try:
            import requests
            response = requests.get("http://localhost:11434/api/tags", timeout=2)
            return response.status_code == 200
        except Exception:
            return False
    
    def is_p0(self) -> bool:
        """Check if running P0 profile"""
        return self.current_profile == "P0"
    
    def is_p1(self) -> bool:
        """Check if running P1 profile"""
        return self.current_profile == "P1"
    
    def is_p2(self) -> bool:
        """Check if running P2 profile"""
        return self.current_profile == "P2"
    
    def get_env_vars(self) -> Dict[str, str]:
        """Get environment variables for current profile"""
        env = {
            "HLF_PROFILE": self.current_profile,
            "HLF_OLLAMA_MODE": self.config.ollama_mode,
            "HLF_DEFAULT_MODEL": self.config.default_model,
            "HLF_HOT_TIER": self.config.hot_tier,
            "HLF_HOST_FUNCTIONS": self.config.host_function_set,
        }
        
        if self.config.ollama_mode == "cloud_direct":
            env["HLF_OLLAMA_USE_CLOUD_DIRECT"] = "1"
        
        return env
    
    def get_summary(self) -> str:
        """Get human-readable profile summary"""
        c = self.config
        return f"""
HLF Profile: {c.name}
Description: {c.description}

Infrastructure:
  Redis: {'Yes' if c.use_redis else 'No'}
  Docker: {'Yes' if c.use_docker else 'No'}
  LRU Cache: {'Yes' if c.use_lru_cache else 'No'}

Inference:
  Mode: {c.ollama_mode}
  Default Model: {c.default_model}

Memory Tiers:
  Hot: {c.hot_tier}
  Warm: {c.warm_tier}
  Cold: {c.cold_tier}

Host Functions: {c.host_function_set}
Security: ACL={'Yes' if c.require_acl else 'No'}, Sentinel={'Yes' if c.enable_sentinel else 'No'}

Expected Footprint: ~{c.expected_ram_mb}MB RAM
"""
    
    def to_dict(self) -> Dict[str, Any]:
        """Export configuration as dictionary"""
        return {
            "profile": self.current_profile,
            "config": asdict(self.config)
        }
    
    def validate(self) -> Dict[str, Any]:
        """
        Validate profile configuration.
        
        Returns:
            Dictionary with 'valid' boolean and 'issues' list
        """
        issues = []
        
        # Check Ollama Cloud API key for P0
        if self.is_p0() and not os.getenv("OLLAMA_API_KEY"):
            issues.append("P0 requires OLLAMA_API_KEY environment variable")
        
        # Check local Ollama for P2
        if self.is_p2() and not self._has_local_ollama():
            issues.append("P2 requires local Ollama daemon (not detected)")
        
        # Check SQLite availability (all profiles)
        try:
            import sqlite3
        except ImportError:
            issues.append("SQLite3 required but not available")
        
        return {
            "valid": len(issues) == 0,
            "issues": issues,
            "profile": self.current_profile
        }


def switch_profile(profile: str) -> ProfileManager:
    """
    Switch to a different profile.
    
    Args:
        profile: Target profile (P0, P1, P2)
        
    Returns:
        New ProfileManager instance
    """
    os.environ["HLF_PROFILE"] = profile
    return ProfileManager(profile)


def get_profile_summary() -> str:
    """Get summary of current profile"""
    return ProfileManager().get_summary()


def validate_current_profile() -> Dict[str, Any]:
    """Validate current profile configuration"""
    return ProfileManager().validate()
