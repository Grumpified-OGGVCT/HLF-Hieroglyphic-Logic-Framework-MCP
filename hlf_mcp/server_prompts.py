from __future__ import annotations

import textwrap
from typing import Any

from mcp.server.fastmcp import FastMCP

from hlf_mcp.hlf.agent_prompt import build_hlf_native_system_prompt
import warnings


def register_agent_prompts(mcp: FastMCP) -> dict[str, Any]:
    @mcp.prompt()
    def hlf_native_agent(
        tier: str = "forge",
        language: str = "en",
        focus: str = "",
        swarm_mode: bool = False,
    ) -> str:
        """HLF-native agent prompt enforcing NLP→HLF→gates→execution/coordination→NLP."""
        warnings.warn("hlf_native_agent is deprecated, use sg_prompt_native_agent instead", DeprecationWarning, stacklevel=2)
        return build_hlf_native_system_prompt(
            tier=tier,
            language=language,
            focus=focus,
            swarm_mode=swarm_mode,
        )

    @mcp.prompt()
    def hlf_onboarding() -> str:
        """What is HLF and how to use it — onboarding prompt for new agents."""
        warnings.warn("hlf_onboarding is deprecated, use sg_prompt_onboarding instead", DeprecationWarning, stacklevel=2)
        return textwrap.dedent("""\
            # SwarmGlass Onboarding

            SwarmGlass is a **governance framework for AI agents**, built on HLF
            (Hieroglyphic Logic Framework) — a structured intent language that compresses
            natural-language instructions into deterministic, typed, gas-metered
            glyphs that compile to bytecode and execute in a sandboxed VM.

            ## Why SwarmGlass + HLF?

            - **Deterministic**: Same input → same output, every time.
            - **Compressed**: 12–30% fewer tokens than prose for complex intents.
            - **Governed**: ALIGN Ledger enforces security rules at compile time.
            - **Auditable**: Every execution produces a Merkle-linked trace.
            - **Swarm-aware**: `interface` declarations eliminate cross-agent bugs.

            ## Quick Syntax

            ```hlf
            [HLF-v3]
            Δ [INTENT] goal="audit_seccomp"
              Ж [CONSTRAINT] mode="ro"
              Ж [EXPECT] vulnerability_shorthand
              ⨝ [VOTE] consensus="strict"
            Ω
            ```

            - `Δ` (DELTA) — Primary action / analysis intent
            - `Ж` (ZHE) — Constraint / assertion / enforce
            - `⨝` (JOIN) — Consensus / vote / join
            - `⌘` (COMMAND) — Command / delegate / route
            - `∇` (NABLA) — Source / parameter / data flow
            - `⩕` (BOWTIE) — Priority / weight / rank
            - `⊎` (UNION) — Branch / condition / union
            - `Ω` — Terminator (required at end)

            ## Agent Workflow

            1. **Receive** natural-language request from user.
            2. **Translate** to HLF using `hlf_translate_to_hlf` or internal reasoning.
            3. **Validate** with `hlf_validate` or `hlf_capsule_validate`.
            4. **Execute** with `hlf_run` or `hlf_code_execute`.
            5. **Report** results in natural language with trace references.

            ## Safety

            - Always use `hearth` tier for untrusted input.
            - Gas limits prevent runaway execution.
            - ALIGN Ledger blocks credential exposure and injection patterns.

            For the full grammar, see `hlf://grammar` or `docs/HLF_GRAMMAR_REFERENCE.md`.
        """)

    @mcp.prompt()
    def hlf_swarm_agent() -> str:
        """How to use HLF for multi-agent swarm coordination."""
        warnings.warn("hlf_swarm_agent is deprecated, use sg_prompt_swarm_agent instead", DeprecationWarning, stacklevel=2)
        return textwrap.dedent("""\
            # HLF Swarm Coordination Guide

            When coordinating multiple agents, HLF replaces ambiguous prose plans
            with explicit `interface` declarations that every agent can read.

            ## Swarm Syntax

            ```hlf
            [HLF-v3]
            agent AuthService {
              interface LoginModule {
                effect: (username, password) -> { token, expires }
              }
            }
            agent ApiGateway {
              depends_on: AuthService
              interface RouteModule {
                effect: (path, headers) -> { status, body }
              }
            }
            spawn ApiGateway after AuthService
            Ω
            ```

            ## Key Rules

            - **interface** declares inputs, outputs, and side effects.
            - **depends_on** establishes execution order.
            - **spawn** launches agents in dependency-respecting batches.
            - Agents with no upstream dependencies run in parallel.

            ## Why HLF Beats Prose at Scale

            | Agents | NL Bugs | HLF Bugs | Winner |
            |--------|---------|----------|--------|
            | 3      | 2       | 0        | NL (cheaper) |
            | 10     | 1       | 0        | HLF (+48% savings) |
            | 15     | 3       | 0        | HLF (+58% savings) |

            Breakpoint: ~5–7 agents. Above this, HLF dominates on cost, speed,
            and correctness.

            ## Tools

            - `hlf_native_speak` — Compile and run HLF, return structured result.
            - `hlf_validate_output` — Check swarm output for required tags and gas.
            - `hlf_workflow_benchmark` — Compare NL vs HLF for a given task.
        """)

    @mcp.prompt()
    def hlf_feedback_guide() -> str:
        """How to submit feedback to the HLF repository."""
        warnings.warn("hlf_feedback_guide is deprecated, use sg_prompt_feedback instead", DeprecationWarning, stacklevel=2)
        return textwrap.dedent("""\
            # HLF Feedback Guide

            Found a bug? Have a feature request? Want to report a security issue?
            Use the built-in feedback tools to create GitHub issues directly.

            ## Submitting Feedback

            ```
            hlf_feedback_submit(
                title="Bug: hlf_run fails on empty source",
                body="When I pass an empty string to hlf_run, it crashes...",
                labels=["bug", "mcp"]
            )
            ```

            ## Parameters

            - **title** — Required, max 256 characters.
            - **body** — Detailed description. Markdown supported.
            - **labels** — Optional list (e.g., ["bug"], ["feature"], ["feedback"]).
            - **repo** — Optional override (default: Grumpified-OGGVCT/SwarmGlass-MCP).

            ## Listing Issues

            ```
            hlf_feedback_list(state="open", limit=10)
            ```

            ## Viewing an Issue

            ```
            hlf_feedback_view(issue_number=42)
            ```

            ## Requirements

            - `gh` CLI must be installed and authenticated.
            - The user must have push access to create issues (or the repo must be public).
        """)

    def _register_sg_aliases(mcp: FastMCP, aliases: dict):
        """Register sg_ aliases that delegate to existing hlf_ prompts."""
        import functools
        for sg_name, hlf_func in aliases.items():
            def _make_wrapper(_name, _func):
                @functools.wraps(_func)
                def _wrapper(*args, **kwargs):
                    return _func(*args, **kwargs)
                _wrapper.__name__ = _name
                return _wrapper
            wrapper = _make_wrapper(sg_name, hlf_func)
            mcp.prompt(name=sg_name)(wrapper)

    _register_sg_aliases(mcp, {
        "sg_prompt_native_agent": hlf_native_agent,
        "sg_prompt_onboarding": hlf_onboarding,
        "sg_prompt_swarm_agent": hlf_swarm_agent,
        "sg_prompt_feedback": hlf_feedback_guide,
    })

    return {
        "hlf_native_agent": hlf_native_agent,
        "hlf_onboarding": hlf_onboarding,
        "hlf_swarm_agent": hlf_swarm_agent,
        "hlf_feedback_guide": hlf_feedback_guide,
        "sg_prompt_native_agent": hlf_native_agent,
        "sg_prompt_onboarding": hlf_onboarding,
        "sg_prompt_swarm_agent": hlf_swarm_agent,
        "sg_prompt_feedback": hlf_feedback_guide,
    }
