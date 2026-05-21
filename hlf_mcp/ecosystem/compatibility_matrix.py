"""
Compatibility Matrix — ecosystem language support matrix for HLF.

Documents which languages have what level of ecosystem integration:
MCP client support, REST client, SDK generation, typed contracts,
provenance passthrough, rate limiting, credential management, and
transport protocol support.

The matrix covers 5 languages: Python, TypeScript, Java, Rust, Go.

Use ``CompatibilityMatrix.render_markdown_table()`` for documentation
and ``CompatibilityMatrix.render_json_matrix()`` for automation.
"""

from __future__ import annotations

import json
from dataclasses import dataclass


@dataclass
class CompatibilityMatrixEntry:
    """A single language's ecosystem compatibility profile.

    Attributes:
        language: Programming language name.
        mcp_client: Can act as an MCP client (connect to HLF MCP server).
        rest_client: Can call HLF REST APIs.
        sdk_gen: SDK generation from HLF contracts is supported.
        typed_contracts: Typed contract support (type-safe client stubs).
        provenance_passthrough: Provenance header passthrough supported.
        rate_limiting: Built-in rate limiting support.
        credential_management: Credential/API key management supported.
        transport_sse: SSE (Server-Sent Events) transport supported.
        transport_stdio: stdio transport supported.
        transport_streamable_http: Streamable HTTP transport supported.
        notes: Free-form notes about the language integration.
    """
    language: str
    mcp_client: bool = False
    rest_client: bool = False
    sdk_gen: bool = False
    typed_contracts: bool = False
    provenance_passthrough: bool = False
    rate_limiting: bool = False
    credential_management: bool = False
    transport_sse: bool = False
    transport_stdio: bool = False
    transport_streamable_http: bool = False
    notes: str = ""

    def to_dict(self) -> dict[str, object]:
        return {
            "language": self.language,
            "mcp_client": self.mcp_client,
            "rest_client": self.rest_client,
            "sdk_gen": self.sdk_gen,
            "typed_contracts": self.typed_contracts,
            "provenance_passthrough": self.provenance_passthrough,
            "rate_limiting": self.rate_limiting,
            "credential_management": self.credential_management,
            "transport_sse": self.transport_sse,
            "transport_stdio": self.transport_stdio,
            "transport_streamable_http": self.transport_streamable_http,
            "notes": self.notes,
        }

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> CompatibilityMatrixEntry:
        return cls(
            language=str(data.get("language", "")),
            mcp_client=bool(data.get("mcp_client", False)),
            rest_client=bool(data.get("rest_client", False)),
            sdk_gen=bool(data.get("sdk_gen", False)),
            typed_contracts=bool(data.get("typed_contracts", False)),
            provenance_passthrough=bool(data.get("provenance_passthrough", False)),
            rate_limiting=bool(data.get("rate_limiting", False)),
            credential_management=bool(data.get("credential_management", False)),
            transport_sse=bool(data.get("transport_sse", False)),
            transport_stdio=bool(data.get("transport_stdio", False)),
            transport_streamable_http=bool(data.get("transport_streamable_http", False)),
            notes=str(data.get("notes", "")),
        )


class CompatibilityMatrix:
    """Ecosystem compatibility matrix across all supported languages.

    Provides query, rendering, and serialization for the HLF ecosystem
    language support grid.  The matrix is populated at construction with
    the current truth for each language.

    Python and TypeScript have full support (they are the primary runtime
    and primary extension language respectively).  Java and Rust have
    SDK generation and typed contracts (via schema_translator).  Go has
    REST client support only (via existing Go struct generation).
    """

    def __init__(self) -> None:
        self.entries: list[CompatibilityMatrixEntry] = self._build_default_matrix()

    def _build_default_matrix(self) -> list[CompatibilityMatrixEntry]:
        """Build the canonical compatibility matrix.

        Returns a list of entries ordered by integration depth:
        Python (full) → TypeScript (full) → Java (SDK gen) → Rust (SDK gen) → Go (REST).
        """
        return [
            CompatibilityMatrixEntry(
                language="Python",
                mcp_client=True,
                rest_client=True,
                sdk_gen=True,
                typed_contracts=True,
                provenance_passthrough=True,
                rate_limiting=True,
                credential_management=True,
                transport_sse=True,
                transport_stdio=True,
                transport_streamable_http=True,
                notes="Primary runtime. Full MCP server + client via FastMCP.",
            ),
            CompatibilityMatrixEntry(
                language="TypeScript",
                mcp_client=True,
                rest_client=True,
                sdk_gen=True,
                typed_contracts=True,
                provenance_passthrough=True,
                rate_limiting=True,
                credential_management=True,
                transport_sse=True,
                transport_stdio=True,
                transport_streamable_http=True,
                notes="VS Code extension + StreamableHttpMcpClient reference impl.",
            ),
            CompatibilityMatrixEntry(
                language="Java",
                mcp_client=False,
                rest_client=False,
                sdk_gen=True,
                typed_contracts=True,
                provenance_passthrough=False,
                rate_limiting=False,
                credential_management=False,
                transport_sse=False,
                transport_stdio=False,
                transport_streamable_http=False,
                notes="SDK generation via schema_translator (Jackson annotations).",
            ),
            CompatibilityMatrixEntry(
                language="Rust",
                mcp_client=False,
                rest_client=False,
                sdk_gen=True,
                typed_contracts=True,
                provenance_passthrough=False,
                rate_limiting=False,
                credential_management=False,
                transport_sse=False,
                transport_stdio=False,
                transport_streamable_http=False,
                notes="SDK generation via schema_translator (serde derives).",
            ),
            CompatibilityMatrixEntry(
                language="Go",
                mcp_client=False,
                rest_client=True,
                sdk_gen=False,
                typed_contracts=False,
                provenance_passthrough=False,
                rate_limiting=False,
                credential_management=False,
                transport_sse=False,
                transport_stdio=False,
                transport_streamable_http=False,
                notes="REST client only via schema_translator Go struct generation.",
            ),
        ]

    # ── Query API ──────────────────────────────────────────────────────────────

    def get_supported_languages(self) -> list[str]:
        """Return languages that have ANY level of ecosystem support."""
        return [entry.language for entry in self.entries]

    def get_feature_coverage(self, language: str) -> dict[str, object]:
        """Return per-language feature coverage as a dict.

        Args:
            language: Language name (case-insensitive match).

        Returns:
            Dict with feature keys and boolean values, plus 'language'
            and 'notes'.  Returns empty dict if language not found.
        """
        for entry in self.entries:
            if entry.language.lower() == language.lower():
                return entry.to_dict()
        return {}

    def get_entry(self, language: str) -> CompatibilityMatrixEntry | None:
        """Return the full CompatibilityMatrixEntry for a language, or None."""
        for entry in self.entries:
            if entry.language.lower() == language.lower():
                return entry
        return None

    def languages_with_feature(self, feature: str) -> list[str]:
        """Return languages that support a specific feature.

        Args:
            feature: Attribute name (e.g., 'sdk_gen', 'mcp_client').

        Returns:
            List of language names supporting the feature.
        """
        result: list[str] = []
        for entry in self.entries:
            if getattr(entry, feature, False):
                result.append(entry.language)
        return result

    # ── Rendering ──────────────────────────────────────────────────────────────

    def render_markdown_table(self) -> str:
        """Render the compatibility matrix as a GitHub-flavored markdown table.

        Columns: Language, MCP Client, REST Client, SDK Gen, Typed Contracts,
        Provenance, Rate Limiting, Credential Mgmt, SSE, stdio, Streamable HTTP, Notes.

        Returns:
            A multi-line markdown string.
        """
        headers = [
            "Language",
            "MCP Client",
            "REST Client",
            "SDK Gen",
            "Typed Contracts",
            "Provenance",
            "Rate Limiting",
            "Credential Mgmt",
            "SSE",
            "stdio",
            "Streamable HTTP",
            "Notes",
        ]

        def _check(b: bool) -> str:
            return "✅" if b else "❌"

        lines: list[str] = []
        # Header row
        lines.append("| " + " | ".join(headers) + " |")
        # Separator row
        lines.append("|" + "|".join(" --- " for _ in headers) + "|")
        # Data rows
        for entry in self.entries:
            row = [
                entry.language,
                _check(entry.mcp_client),
                _check(entry.rest_client),
                _check(entry.sdk_gen),
                _check(entry.typed_contracts),
                _check(entry.provenance_passthrough),
                _check(entry.rate_limiting),
                _check(entry.credential_management),
                _check(entry.transport_sse),
                _check(entry.transport_stdio),
                _check(entry.transport_streamable_http),
                entry.notes,
            ]
            lines.append("| " + " | ".join(row) + " |")

        return "\n".join(lines)

    def render_json_matrix(self) -> str:
        """Render the compatibility matrix as a JSON string for automation.

        Returns:
            Pretty-printed JSON string with indentation.
        """
        data = {
            "compatibility_matrix": [entry.to_dict() for entry in self.entries],
            "generated_by": "hlf_mcp.ecosystem.CompatibilityMatrix",
        }
        return json.dumps(data, indent=2, sort_keys=False)

    def render_compact(self) -> str:
        """Render a compact markdown table with only the most important columns.

        Columns: Language, MCP, REST, SDK Gen, Typed, Provenance, Notes.

        Returns:
            A compact multi-line markdown string.
        """
        headers = [
            "Language",
            "MCP",
            "REST",
            "SDK Gen",
            "Typed",
            "Provenance",
            "Notes",
        ]

        def _check(b: bool) -> str:
            return "✅" if b else "❌"

        lines: list[str] = []
        lines.append("| " + " | ".join(headers) + " |")
        lines.append("|" + "|".join(" --- " for _ in headers) + "|")
        for entry in self.entries:
            row = [
                entry.language,
                _check(entry.mcp_client),
                _check(entry.rest_client),
                _check(entry.sdk_gen),
                _check(entry.typed_contracts),
                _check(entry.provenance_passthrough),
                entry.notes,
            ]
            lines.append("| " + " | ".join(row) + " |")

        return "\n".join(lines)

    # ── Stats / Introspection ──────────────────────────────────────────────────

    def feature_coverage_summary(self) -> dict[str, object]:
        """Return a summary of feature coverage across all languages.

        Returns:
            Dict mapping feature name → count of languages supporting it.
        """
        features = [
            "mcp_client", "rest_client", "sdk_gen", "typed_contracts",
            "provenance_passthrough", "rate_limiting", "credential_management",
            "transport_sse", "transport_stdio", "transport_streamable_http",
        ]
        result: dict[str, object] = {"total_languages": len(self.entries)}
        for feat in features:
            count = sum(1 for e in self.entries if getattr(e, feat, False))
            result[feat] = count
        return result

    def __len__(self) -> int:
        return len(self.entries)

    def __iter__(self):
        return iter(self.entries)
