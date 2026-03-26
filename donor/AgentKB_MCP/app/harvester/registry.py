"""
Source Registry - Curated list of official documentation sources to monitor.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional
import yaml


@dataclass
class Source:
    """A single documentation source to monitor."""
    url: str
    type: str  # release_notes, api_reference, configuration, changelog, rss_feed
    check_interval: str = "daily"  # hourly, daily, weekly
    last_hash: Optional[str] = None
    last_checked: Optional[str] = None


@dataclass
class Domain:
    """A technology domain with its official sources."""
    name: str
    sources: list[Source] = field(default_factory=list)


class SourceRegistry:
    """
    Manages the curated list of official documentation sources.
    
    Sources are stored in sources.yaml and loaded at runtime.
    """
    
    def __init__(self, registry_path: Path = None):
        self.registry_path = registry_path or Path("sources.yaml")
        self.domains: dict[str, Domain] = {}
        self._load()
    
    def _load(self) -> None:
        """Load sources from YAML file."""
        if not self.registry_path.exists():
            # Create default registry if missing
            self._create_default()
            return
        
        with open(self.registry_path) as f:
            data = yaml.safe_load(f)
        
        for domain_key, domain_data in data.get("domains", {}).items():
            sources = [
                Source(**src) for src in domain_data.get("sources", [])
            ]
            self.domains[domain_key] = Domain(
                name=domain_data.get("name", domain_key),
                sources=sources,
            )
    
    def _create_default(self) -> None:
        """Create a default registry with common sources."""
        default_config = {
            "domains": {
                "postgresql": {
                    "name": "PostgreSQL",
                    "sources": [
                        {
                            "url": "https://www.postgresql.org/docs/current/release.html",
                            "type": "release_notes",
                            "check_interval": "daily",
                        },
                        {
                            "url": "https://www.postgresql.org/docs/current/runtime-config.html",
                            "type": "configuration",
                            "check_interval": "weekly",
                        },
                    ],
                },
                "nextjs": {
                    "name": "Next.js",
                    "sources": [
                        {
                            "url": "https://nextjs.org/docs",
                            "type": "api_reference",
                            "check_interval": "daily",
                        },
                        {
                            "url": "https://github.com/vercel/next.js/releases.atom",
                            "type": "rss_feed",
                            "check_interval": "hourly",
                        },
                    ],
                },
                "python": {
                    "name": "Python",
                    "sources": [
                        {
                            "url": "https://docs.python.org/3/whatsnew/index.html",
                            "type": "changelog",
                            "check_interval": "weekly",
                        },
                    ],
                },
                "fastapi": {
                    "name": "FastAPI",
                    "sources": [
                        {
                            "url": "https://fastapi.tiangolo.com/release-notes/",
                            "type": "release_notes",
                            "check_interval": "daily",
                        },
                    ],
                },
                "docker": {
                    "name": "Docker",
                    "sources": [
                        {
                            "url": "https://docs.docker.com/engine/release-notes/",
                            "type": "release_notes",
                            "check_interval": "weekly",
                        },
                    ],
                },
                "typescript": {
                    "name": "TypeScript",
                    "sources": [
                        {
                            "url": "https://www.typescriptlang.org/docs/handbook/release-notes/overview.html",
                            "type": "release_notes",
                            "check_interval": "weekly",
                        },
                    ],
                },
                "react": {
                    "name": "React",
                    "sources": [
                        {
                            "url": "https://react.dev/blog",
                            "type": "changelog",
                            "check_interval": "daily",
                        },
                    ],
                },
                "kubernetes": {
                    "name": "Kubernetes",
                    "sources": [
                        {
                            "url": "https://kubernetes.io/docs/setup/release/notes/",
                            "type": "release_notes",
                            "check_interval": "weekly",
                        },
                    ],
                },
                "aws": {
                    "name": "AWS",
                    "sources": [
                        {
                            "url": "https://aws.amazon.com/new/",
                            "type": "changelog",
                            "check_interval": "daily",
                        },
                    ],
                },
                "rust": {
                    "name": "Rust",
                    "sources": [
                        {
                            "url": "https://blog.rust-lang.org/",
                            "type": "changelog",
                            "check_interval": "weekly",
                        },
                    ],
                },
            }
        }
        
        with open(self.registry_path, "w") as f:
            yaml.dump(default_config, f, default_flow_style=False, sort_keys=False)
        
        # Reload
        self._load()
    
    def get_domains(self) -> list[str]:
        """Get all registered domain keys."""
        return list(self.domains.keys())
    
    def get_sources(self, domain: str) -> list[Source]:
        """Get sources for a specific domain."""
        if domain not in self.domains:
            return []
        return self.domains[domain].sources
    
    def get_all_sources(self) -> list[tuple[str, Source]]:
        """Get all sources with their domain keys."""
        result = []
        for domain_key, domain in self.domains.items():
            for source in domain.sources:
                result.append((domain_key, source))
        return result
    
    def add_domain(self, key: str, name: str) -> None:
        """Add a new domain."""
        self.domains[key] = Domain(name=name, sources=[])
        self._save()
    
    def add_source(self, domain: str, source: Source) -> None:
        """Add a source to a domain."""
        if domain not in self.domains:
            raise ValueError(f"Domain '{domain}' not found")
        self.domains[domain].sources.append(source)
        self._save()
    
    def _save(self) -> None:
        """Save the registry back to YAML."""
        data = {"domains": {}}
        for key, domain in self.domains.items():
            data["domains"][key] = {
                "name": domain.name,
                "sources": [
                    {
                        "url": s.url,
                        "type": s.type,
                        "check_interval": s.check_interval,
                    }
                    for s in domain.sources
                ],
            }
        with open(self.registry_path, "w") as f:
            yaml.dump(data, f, default_flow_style=False, sort_keys=False)

