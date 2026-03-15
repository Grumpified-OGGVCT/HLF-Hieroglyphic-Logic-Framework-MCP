"""
HLF Profile Configuration
Detects and configures P0/P1/P2 runtime profiles
"""

import os
import sys
from enum import Enum
from typing import Dict, Any, Optional
from dataclasses import dataclass


class HLFProfile(Enum):
    """HLF runtime profiles from minimal to full capability."""
    P0_CLOUD_CORE = "P0"      # Cloud-only, minimal local footprint
    P1_WORKSTATION = "P1"     # Cloud-assisted, some local caching
    P2_SOVEREIGN = "P2"       # Full sovereign capability
    UNKNOWN = "unknown"


@dataclass
class ProfileConfig:
    """Configuration for a specific HLF profile."""
    profile: HLFProfile
    hot_store_type: str       # 'lru', 'sqlite', or 'redis'
    use_cloud_direct: bool    # Direct Ollama Cloud API
    use_local_daemon: bool    # Local Ollama daemon
    host_functions: list      # List of enabled host functions
    gas_tolerance_ms: int     # Gas metering tolerance
    max_hot_store_items: int  # Maximum items in hot tier


# Profile defaults
PROFILE_DEFAULTS = {
    HLFProfile.P0_CLOUD_CORE: ProfileConfig(
        profile=HLFProfile.P0_CLOUD_CORE,
        hot_store_type='lru',
        use_cloud_direct=True,
        use_local_daemon=False,
        host_functions=['READ_FILE', 'WRITE_FILE', 'WEB_SEARCH', 'STRUCTURED_OUTPUT', 'SELF_OBSERVE'],
        gas_tolerance_ms=50,
        max_hot_store_items=1000
    ),
    HLFProfile.P1_WORKSTATION: ProfileConfig(
        profile=HLFProfile.P1_WORKSTATION,
        hot_store_type='sqlite',
        use_cloud_direct=True,
        use_local_daemon=True,  # Fallback available
        host_functions=['READ_FILE', 'WRITE_FILE', 'WEB_SEARCH', 'STRUCTURED_OUTPUT', 'SELF_OBSERVE',
                       'MEMORY_STORE', 'MEMORY_RECALL', 'SPEC_VALIDATE'],
        gas_tolerance_ms=20,
        max_hot_store_items=10000
    ),
    HLFProfile.P2_SOVEREIGN: ProfileConfig(
        profile=HLFProfile.P2_SOVEREIGN,
        hot_store_type='redis',
        use_cloud_direct=False,  # Can use, but not required
        use_local_daemon=True,
        host_functions=['*'],  # All available
        gas_tolerance_ms=5,
        max_hot_store_items=100000
    )
}


def detect_profile() -> HLFProfile:
    """
    Detect which HLF profile to use based on environment.
    
    Priority:
    1. HLF_PROFILE environment variable
    2. Presence of Redis (P2)
    3. Presence of local Ollama daemon (P1)
    4. Default to P0 (safest minimal)
    
    Returns:
        Detected HLF profile
    """
    # Check explicit environment variable
    env_profile = os.getenv('HLF_PROFILE', '').upper()
    if env_profile in ['P0', 'P1', 'P2']:
        return HLFProfile(env_profile)
    
    # Check for Redis availability (indicates P2)
    try:
        import redis
        r = redis.Redis(host='localhost', port=6379, socket_connect_timeout=1)
        r.ping()
        return HLFProfile.P2_SOVEREIGN
    except:
        pass
    
    # Check for local Ollama daemon (indicates P1)
    try:
        import requests
        response = requests.get('http://localhost:11434/api/tags', timeout=1)
        if response.status_code == 200:
            return HLFProfile.P1_WORKSTATION
    except:
        pass
    
    # Default to P0 (cloud-only, minimal)
    return HLFProfile.P0_CLOUD_CORE


def get_profile_config(profile: Optional[HLFProfile] = None) -> ProfileConfig:
    """
    Get configuration for a specific profile.
    
    Args:
        profile: Profile to get config for (auto-detect if None)
        
    Returns:
        Profile configuration
    """
    if profile is None:
        profile = detect_profile()
    
    config = PROFILE_DEFAULTS.get(profile, PROFILE_DEFAULTS[HLFProfile.P0_CLOUD_CORE])
    
    # Apply environment overrides
    if os.getenv('HLF_HOT_STORE_TYPE'):
        config.hot_store_type = os.getenv('HLF_HOT_STORE_TYPE')
    if os.getenv('HLF_OLLAMA_USE_CLOUD_DIRECT'):
        config.use_cloud_direct = os.getenv('HLF_OLLAMA_USE_CLOUD_DIRECT') == '1'
    if os.getenv('HLF_GAS_TOLERANCE_MS'):
        config.gas_tolerance_ms = int(os.getenv('HLF_GAS_TOLERANCE_MS'))
    
    return config


def create_hot_store(config: Optional[ProfileConfig] = None):
    """
    Create appropriate hot store based on profile configuration.
    
    Args:
        config: Profile configuration (auto-detect if None)
        
    Returns:
        Hot store instance
    """
    if config is None:
        config = get_profile_config()
    
    if config.hot_store_type == 'lru':
        from .stores.lru_hot_store import LRUHotStore
        return LRUHotStore(maxsize=config.max_hot_store_items)
    
    elif config.hot_store_type == 'sqlite':
        from .stores.sqlite_hot_store import SQLiteHotStore
        db_path = os.getenv('HLF_SQLITE_PATH', './data/hlf_hot.db')
        return SQLiteHotStore(db_path=db_path)
    
    elif config.hot_store_type == 'redis':
        try:
            import redis
            redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
            return redis.from_url(redis_url)
        except ImportError:
            print("Warning: Redis not available, falling back to SQLite", file=sys.stderr)
            from .stores.sqlite_hot_store import SQLiteHotStore
            return SQLiteHotStore()
    
    else:
        raise ValueError(f"Unknown hot store type: {config.hot_store_type}")


def get_ollama_base_url(config: Optional[ProfileConfig] = None) -> str:
    """
    Get appropriate Ollama base URL based on profile.
    
    Args:
        config: Profile configuration (auto-detect if None)
        
    Returns:
        Ollama API base URL
    """
    if config is None:
        config = get_profile_config()
    
    if config.use_cloud_direct:
        return "https://ollama.com/api"
    
    if config.use_local_daemon:
        return os.getenv('OLLAMA_HOST', 'http://localhost:11434')
    
    # Default to cloud direct if no local daemon
    return "https://ollama.com/api"


def is_host_function_enabled(function_name: str, config: Optional[ProfileConfig] = None) -> bool:
    """
    Check if a host function is enabled for the current profile.
    
    Args:
        function_name: Name of the host function
        config: Profile configuration (auto-detect if None)
        
    Returns:
        True if function is enabled
    """
    if config is None:
        config = get_profile_config()
    
    if '*' in config.host_functions:
        return True
    
    return function_name in config.host_functions


def get_profile_info() -> Dict[str, Any]:
    """
    Get comprehensive profile information.
    
    Returns:
        Dictionary with profile details
    """
    profile = detect_profile()
    config = get_profile_config(profile)
    
    return {
        'profile': profile.value,
        'description': {
            'P0': 'Cloud-only Core - Minimal local footprint',
            'P1': 'Cloud-assisted Workstation - Balanced',
            'P2': 'Full Sovereign - Maximum capability'
        }.get(profile.value, 'Unknown'),
        'hot_store': {
            'type': config.hot_store_type,
            'max_items': config.max_hot_store_items
        },
        'ollama': {
            'use_cloud_direct': config.use_cloud_direct,
            'use_local_daemon': config.use_local_daemon,
            'base_url': get_ollama_base_url(config)
        },
        'gas': {
            'tolerance_ms': config.gas_tolerance_ms
        },
        'host_functions': {
            'enabled': config.host_functions if '*' not in config.host_functions else 'all',
            'count': len(config.host_functions) if '*' not in config.host_functions else 'all'
        }
    }


# Convenience function for CLI
if __name__ == '__main__':
    import json
    info = get_profile_info()
    print(json.dumps(info, indent=2))
