"""
Forge Agent: Watches friction drop, validates, proposes grammar extensions.

The Forge is the local custodian of the HLF grammar. It:
1. Monitors the friction drop for new reports
2. Validates friction reports using hlfc/hlflint
3. Proposes grammar extensions (additive-only)
4. Pushes proposals to the master repository via MCP

USAGE:
    python -m hlf.forge_agent --repo /path/to/hlf --interval 5.0

CONFIGURATION:
    Environment variables:
    - MCP_URL: MCP server URL (default: http://localhost:8000)
    - FORGE_VALIDATION_TOKEN: Token from CI after successful test run
    - GITHUB_TOKEN: GitHub PAT for creating PRs
    - GH_REPO: Target repository (default: owner/repo)
"""

import os
import sys
import time
import json
import hashlib
import subprocess
import argparse
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional, Any
from datetime import datetime

# ========================================
# Data Classes
# ========================================

@dataclass
class FrictionReport:
    """Parsed friction report."""
    id: str
    timestamp: float
    grammar_version: str
    grammar_sha256: str
    source_snippet: str
    failure_type: str
    attempted_intent: str
    context: Dict[str, Any]
    proposed_fix: Optional[str]
    agent_metadata: Dict[str, Any]
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class GrammarProposal:
    """Grammar extension proposal."""
    id: str
    friction_id: str
    timestamp: float
    proposed_syntax: str
    rationale: str
    additive_only: bool
    breaking: bool
    tier_required: str
    affected_opcodes: List[str]
    validation_token: str
    status: str = "pending"  # "pending", "submitted", "merged", "rejected"
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ========================================
# Forge Agent Implementation
# ========================================

class ForgeAgent:
    """
    The Forge agent watches friction reports and proposes grammar extensions.
    
    Workflow:
    1. Watch ~/.sovereign/friction/ for new .hlf files
    2. Parse and validate each friction report
    3. If proposed_fix exists, validate it compiles
    4. Create a GrammarProposal
    5. Submit proposal via MCP /tool/push_proposal
    6. Move processed file to processed/ directory
    """
    
    def __init__(self, repo_root: Path, mcp_url: str = None):
        """
        Initialize the Forge agent.
        
        Args:
            repo_root: Path to HLF repository root
            mcp_url: MCP server URL (default: http://localhost:8000)
        """
        self.repo_root = Path(repo_root).resolve()
        self.mcp_url = mcp_url or os.environ.get("MCP_URL", "http://localhost:8000")
        
        # Directories
        self.friction_drop = Path.home() / ".sovereign" / "friction"
        self.processed_dir = self.friction_drop / "processed"
        self.proposals_dir = self.friction_drop / "proposals"
        
        for d in [self.friction_drop, self.processed_dir, self.proposals_dir]:
            d.mkdir(parents=True, exist_ok=True)
        
        # Grammar info
        self.current_grammar_sha = None
        self.current_version = None
        self._load_grammar_info()
        
        # GitHub config
        self.github_token = os.environ.get("GITHUB_TOKEN")
        self.gh_repo = os.environ.get("GH_REPO")
        self.gh_user = os.environ.get("GH_USER", "forge-agent")
        
        # Validation token
        self.validation_token = os.environ.get("FORGE_VALIDATION_TOKEN", "")
        
        # Stats
        self.processed_count = 0
        self.proposed_count = 0
    
    def _load_grammar_info(self):
        """Load current grammar version and SHA."""
        grammar_path = self.repo_root / "hlf" / "spec" / "core" / "grammar.yaml"
        
        if not grammar_path.exists():
            print(f"Warning: Grammar not found at {grammar_path}")
            return
        
        grammar_content = grammar_path.read_text(encoding="utf-8")
        self.current_grammar_sha = hashlib.sha256(grammar_content.encode()).hexdigest()
        
        # Parse version
        try:
            import yaml
            grammar_data = yaml.safe_load(grammar_content)
            self.current_version = grammar_data.get("version", "unknown")
        except ImportError:
            print("Warning: PyYAML not installed, cannot parse grammar version")
            self.current_version = "unknown"
        except Exception as e:
            print(f"Warning: Could not parse grammar: {e}")
            self.current_version = "unknown"
    
    def run(self, poll_interval: float = 5.0, dry_run: bool = False):
        """
        Main loop: watch for friction, process, propose.
        
        Args:
            poll_interval: Polling interval in seconds
            dry_run: If True, don't submit proposals
        """
        print(f"Forge Agent started")
        print(f"Grammar version: {self.current_version}")
        print(f"Grammar SHA256: {self.current_grammar_sha[:16]}...")
        print(f"Watching: {self.friction_drop}")
        print(f"Dry run: {dry_run}")
        print()
        
        seen = set()
        
        # Also check processed files that might have been moved before
        for f in self.processed_dir.glob("*.hlf"):
            seen.add(f.name)
        
        while True:
            self._poll_cycle(seen, dry_run)
            time.sleep(poll_interval)
    
    def _poll_cycle(self, seen: set, dry_run: bool):
        """Process one polling cycle."""
        for friction_file in self.friction_drop.glob("*.hlf"):
            if friction_file.name in seen:
                continue
            
            # Skip in processed directory (shouldn't happen but safety check)
            if friction_file.parent == self.processed_dir:
                continue
            
            print(f"\n{'='*60}")
            print(f"Processing: {friction_file.name}")
            print(f"{'='*60}")
            
            try:
                report = self._parse_friction(friction_file)
                
                if self._validate_friction(report):
                    proposal = self._craft_proposal(report)
                    
                    if proposal:
                        if dry_run:
                            print(f"[DRY RUN] Would submit proposal: {proposal.id}")
                            print(f"  Proposed syntax:\n{proposal.proposed_syntax[:500]}...")
                        else:
                            result = self._submit_proposal(proposal)
                            if result:
                                print(f"Submitted proposal: {proposal.id}")
                                self._save_proposal(proposal)
                                self.proposed_count += 1
                    else:
                        print(f"Could not craft proposal from friction report")
                else:
                    print(f"Friction report validation failed")
                
                # Move to processed
                processed_file = self.processed_dir / friction_file.name
                
                # Handle duplicate names
                if processed_file.exists():
                    processed_file = self.processed_dir / f"{friction_file.stem}_{int(time.time())}.hlf"
                
                friction_file.rename(processed_file)
                print(f"Moved to: {processed_file}")
                
                self.processed_count += 1
                seen.add(friction_file.name)
                
            except Exception as e:
                print(f"Error processing {friction_file.name}: {e}")
                import traceback
                traceback.print_exc()
                seen.add(friction_file.name)
    
    def _parse_friction(self, friction_file: Path) -> FrictionReport:
        """
        Parse a friction file into a FrictionReport.
        
        Args:
            friction_file: Path to friction .hlf file
            
        Returns:
            FrictionReport object
        """
        content = friction_file.read_text(encoding="utf-8")
        
        # Try JSON first
        try:
            data = json.loads(content)
            
            return FrictionReport(
                id=data.get("id", friction_file.stem),
                timestamp=data.get("timestamp", time.time()),
                grammar_version=data.get("grammar_version", "unknown"),
                grammar_sha256=data.get("grammar_sha256", ""),
                source_snippet=data.get("source_snippet", ""),
                failure_type=data.get("failure_type", "unknown"),
                attempted_intent=data.get("attempted_intent", ""),
                context=data.get("context", {}),
                proposed_fix=data.get("proposed_fix"),
                agent_metadata=data.get("agent_metadata", {})
            )
        except json.JSONDecodeError:
            # Parse as HLF (simplified extraction)
            # Try to extract structured content
            friction_id = hashlib.sha256(content.encode()).hexdigest()[:16]
            
            # Try to detect failure type from content
            failure_type = "unknown"
            for ft in ["parse", "compile", "effect", "gas", "expression", "type", "semantic"]:
                if ft in content.lower():
                    failure_type = ft
                    break
            
            return FrictionReport(
                id=friction_file.stem,
                timestamp=friction_file.stat().st_mtime,
                grammar_version=self.current_version or "unknown",
                grammar_sha256=self.current_grammar_sha or "",
                source_snippet=content,
                failure_type=failure_type,
                attempted_intent="",
                context={},
                proposed_fix=None,
                agent_metadata={"file": str(friction_file)}
            )
    
    def _validate_friction(self, report: FrictionReport) -> bool:
        """
        Validate a friction report.
        
        Args:
            report: FrictionReport to validate
            
        Returns:
            True if valid, False otherwise
        """
        # Check grammar version matches
        if self.current_grammar_sha and report.grammar_sha256:
            if self.current_grammar_sha != report.grammar_sha256:
                print(f"Warning: Friction from different grammar version")
                print(f"  Current: {self.current_version}")
                print(f"  Report: {report.grammar_version}")
        else:
            print(f"Warning: Grammar SHA mismatch or missing")
        
        # Check failure type is recognized
        valid_types = {"parse", "compile", "effect", "gas", "expression", "type", "semantic"}
        if report.failure_type not in valid_types:
            print(f"Warning: Unknown failure type: {report.failure_type}")
            return False
        
        # If proposed fix exists, validate it compiles
        if report.proposed_fix:
            try:
                result = self._validate_syntax(report.proposed_fix)
                if not result:
                    print(f"Proposed fix does not compile")
                    return False
                print(f"Proposed fix compiles successfully")
            except Exception as e:
                print(f"Validation error: {e}")
                return False
        
        print(f"Friction report validated")
        return True
    
    def _validate_syntax(self, source: str) -> bool:
        """
        Validate HLF syntax using compiler.
        
        Args:
            source: HLF source to validate
            
        Returns:
            True if valid, False otherwise
        """
        try:
            # Try using the compiler directly
            from hlf.lexer import Lexer
            from hlf.parser import Parser
            
            lexer = Lexer(source)
            tokens = lexer.tokenize()
            
            parser = Parser(tokens, strict=False)
            ast = parser.parse()
            
            return len(parser.errors) == 0
            
        except ImportError:
            # Fall back to subprocess
            result = subprocess.run(
                ["python", "-m", "hlf.hlfc", "--check"],
                input=source,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode != 0:
                print(f"Compiler error: {result.stderr}")
                return False
            
            return True
        except Exception as e:
            print(f"Validation exception: {e}")
            return False
    
    def _craft_proposal(self, report: FrictionReport) -> Optional[GrammarProposal]:
        """
        Craft a grammar extension proposal from friction.
        
        Args:
            report: Validated FrictionReport
            
        Returns:
            GrammarProposal or None
        """
        # If friction has a proposed fix, use it
        if report.proposed_fix:
            proposal_id = hashlib.sha256(
                f"{report.id}:{time.time()}".encode()
            ).hexdigest()[:16]
            
            return GrammarProposal(
                id=proposal_id,
                friction_id=report.id,
                timestamp=time.time(),
                proposed_syntax=report.proposed_fix,
                rationale=f"Proposed by agent to resolve {report.failure_type} friction: {report.attempted_intent}",
                additive_only=True,  # Must be additive-only
                breaking=False,
                tier_required=report.agent_metadata.get("tier", "forge"),
                affected_opcodes=[],  # Would need AST analysis
                validation_token=self.validation_token,
                status="pending"
            )
        
        # If no proposed fix, try to generate one
        # (This would require a more sophisticated proposal generator)
        # For now, return None
        print(f"No proposed fix in friction report, cannot auto-generate proposal")
        return None
    
    def _submit_proposal(self, proposal: GrammarProposal) -> Optional[Dict[str, Any]]:
        """
        Submit proposal via MCP tool.
        
        Args:
            proposal: GrammarProposal to submit
            
        Returns:
            Response from MCP server or None on failure
        """
        import httpx
        
        payload = {
            "title": f"[Forge] Grammar extension proposal {proposal.id}",
            "body": self._format_proposal_body(proposal),
            "head": f"forge/proposal-{proposal.id}",
            "validation_token": proposal.validation_token
        }
        
        try:
            response = httpx.post(
                f"{self.mcp_url}/tool/push_proposal",
                json=payload,
                headers={"Authorization": f"Bearer {self.validation_token}"},
                timeout=30
            )
            response.raise_for_status()
            result = response.json()
            
            proposal.status = "submitted"
            return result
            
        except Exception as e:
            print(f"Failed to submit proposal: {e}")
            return None
    
    def _format_proposal_body(self, proposal: GrammarProposal) -> str:
        """
        Format proposal for GitHub issue/PR.
        
        Args:
            proposal: GrammarProposal
            
        Returns:
            Formatted markdown body
        """
        return f"""# HLF Grammar Extension Proposal

## Proposal ID
{proposal.id}

## Friction Report
{proposal.friction_id}

## Rationale
{proposal.rationale}

## Proposed Syntax
```
{proposal.proposed_syntax}
```

## Metadata
- **Additive-only**: {proposal.additive_only}
- **Breaking**: {proposal.breaking}
- **Tier Required**: {proposal.tier_required}
- **Affected Opcodes**: {', '.join(proposal.affected_opcodes) if proposal.affected_opcodes else 'None'}

## Validation Status
- Grammar version: {self.current_version}
- SHA256: {self.current_grammar_sha}

---

This proposal was automatically generated by the Forge Agent.
All proposals must pass CI validation before merge.
"""
    
    def _save_proposal(self, proposal: GrammarProposal):
        """
        Save proposal to proposals directory.
        
        Args:
            proposal: GrammarProposal to save
        """
        proposal_file = self.proposals_dir / f"{proposal.id}.json"
        proposal_file.write_text(json.dumps(proposal.to_dict(), indent=2))
        print(f"Saved proposal: {proposal_file}")
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get processing statistics.
        
        Returns:
            Stats dict
        """
        return {
            "processed_count": self.processed_count,
            "proposed_count": self.proposed_count,
            "grammar_version": self.current_version,
            "grammar_sha": self.current_grammar_sha,
            "friction_drop": str(self.friction_drop),
            "pending_files": len(list(self.friction_drop.glob("*.hlf"))),
            "processed_files": len(list(self.processed_dir.glob("*.hlf"))),
            "proposals": len(list(self.proposals_dir.glob("*.json")))
        }


# ========================================
# Proposal Generator (Advanced)
# ========================================

class ProposalGenerator:
    """
    Advanced proposal generator that can suggest grammar extensions.
    
    This is a placeholder for future implementation that would:
    - Analyze friction patterns
    - Suggest new syntax based on attempted_intent
    - Generate additive-only extensions
    - Validate against existing grammar
    """
    
    def __init__(self, grammar_path: Path):
        """Initialize with grammar reference."""
        self.grammar_path = grammar_path
    
    def suggest_extension(self, report: FrictionReport) -> Optional[str]:
        """
        Suggest a grammar extension based on friction report.
        
        Args:
            report: FrictionReport
            
        Returns:
            Proposed syntax or None
        """
        # This would require sophisticated language model or rule-based analysis
        # For now, return None
        return None


# ========================================
# CLI Entry Point
# ========================================

def forge_main():
    """CLI entry point for Forge agent."""
    parser = argparse.ArgumentParser(description="HLF Forge Agent")
    parser.add_argument("--repo", default=".", help="Repository root")
    parser.add_argument("--interval", type=float, default=5.0, help="Poll interval in seconds")
    parser.add_argument("--dry-run", action="store_true", help="Don't submit proposals")
    parser.add_argument("--url", default=None, help="MCP server URL")
    parser.add_argument("--stats", action="store_true", help="Show stats and exit")
    
    args = parser.parse_args()
    
    repo_root = Path(args.repo).resolve()
    
    if args.url:
        os.environ["MCP_URL"] = args.url
    
    forge = ForgeAgent(repo_root)
    
    if args.stats:
        stats = forge.get_stats()
        print(json.dumps(stats, indent=2))
        return
    
    print(f"Repository: {repo_root}")
    print(f"MCP URL: {forge.mcp_url}")
    print(f"GitHub: {forge.gh_user}/{forge.gh_repo}")
    print()
    
    forge.run(poll_interval=args.interval, dry_run=args.dry_run)


if __name__ == "__main__":
    forge_main()