"""HLF Swarm Compiler — parse .hlf swarm files into executable dependency graphs.

Syntax supported (outside HLF v3 grammar):
  interface Name { field: type, ... }
  agent Name { role: str, input: Type|none, output: Type|{...}, constraints: [...] }
  effect AgentName -> [READ("path"), WRITE("path")]
  layer_N: [AgentName, ...]
  constraint: NAME: description
  trace { ... }
  checkpoint { ... }

Produces:
  SwarmSpec — full parsed specification
  DependencyGraph — agent dependency DAG
  ExecutionPlan — layer-by-layer schedule
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any


@dataclass
class Interface:
    name: str
    fields: dict[str, str]


@dataclass
class AgentDecl:
    name: str
    role: str
    input_spec: str | dict[str, Any]
    output_spec: str | dict[str, Any]
    constraints: list[str] = field(default_factory=list)
    schema_variant: str = "full"  # "full", "summary", "delta", "proof"
    persona: str = ""  # assigned persona name (e.g., "Builder", "Steward")


@dataclass
class PersonaDef:
    """Persona-first agent definition."""
    name: str
    description: str = ""
    capabilities: list[str] = field(default_factory=list)
    trust_tier: str = "hearth"
    default_constraints: list[str] = field(default_factory=list)
    communication_style: str = "precise"
    supervision: list[str] = field(default_factory=list)  # agents this persona supervises


@dataclass
class Effect:
    agent: str
    actions: list[dict[str, str]]


@dataclass
class SwarmSpec:
    interfaces: dict[str, Interface] = field(default_factory=dict)
    agents: dict[str, AgentDecl] = field(default_factory=dict)
    effects: dict[str, Effect] = field(default_factory=dict)
    layers: list[list[str]] = field(default_factory=list)
    constraints: dict[str, str] = field(default_factory=dict)
    personas: dict[str, PersonaDef] = field(default_factory=dict)
    architecture: dict[str, Any] = field(default_factory=dict)
    trace_config: dict[str, Any] = field(default_factory=dict)
    checkpoint_config: dict[str, Any] = field(default_factory=dict)
    raw_source: str = ""


@dataclass
class DependencyGraph:
    """Agent dependency DAG derived from input/output specs and effects."""

    spec: SwarmSpec
    edges: list[tuple[str, str]] = field(default_factory=list)  # (producer, consumer)
    layer_map: dict[str, int] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self._build()

    def _build(self) -> None:
        agent_names = set(self.spec.agents.keys())
        # Build edges from agent input specs referencing other agents' outputs
        for name, agent in self.spec.agents.items():
            inp = agent.input_spec
            if isinstance(inp, str) and inp != "none" and inp in agent_names:
                self.edges.append((inp, name))
            elif isinstance(inp, dict):
                for val in inp.values():
                    v = str(val)
                    if v in agent_names:
                        self.edges.append((v, name))
            # Also check effects for READ dependencies
            eff = self.spec.effects.get(name)
            if eff:
                for act in eff.actions:
                    if act.get("type") == "READ":
                        path = act.get("path", "")
                        # Map file paths back to likely producer agents
                        for other_name, other_agent in self.spec.agents.items():
                            if other_name == name:
                                continue
                            out = other_agent.output_spec
                            if isinstance(out, dict):
                                out_str = json.dumps(out)
                                if path in out_str:
                                    self.edges.append((other_name, name))
        # Assign layers from explicit layer declarations
        for layer_idx, layer in enumerate(self.spec.layers):
            for agent_name in layer:
                self.layer_map[agent_name] = layer_idx

    def topological_order(self) -> list[str]:
        """Return agents in dependency-respecting order."""
        in_degree: dict[str, int] = {name: 0 for name in self.spec.agents}
        adj: dict[str, list[str]] = {name: [] for name in self.spec.agents}
        for src, dst in self.edges:
            if src in adj and dst in in_degree:
                adj[src].append(dst)
                in_degree[dst] += 1
        queue = [n for n, d in in_degree.items() if d == 0]
        order: list[str] = []
        while queue:
            n = queue.pop(0)
            order.append(n)
            for neighbor in adj[n]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)
        # Add any remaining (shouldn't happen in DAG)
        for n in self.spec.agents:
            if n not in order:
                order.append(n)
        return order

    def ready_agents(self, completed: set[str]) -> list[str]:
        """Agents whose dependencies are all satisfied."""
        result = []
        for name in self.spec.agents:
            if name in completed:
                continue
            deps = [src for src, dst in self.edges if dst == name]
            if all(d in completed for d in deps):
                result.append(name)
        return result


@dataclass
class ExecutionPlan:
    """Layer-by-layer execution schedule."""

    spec: SwarmSpec
    graph: DependencyGraph
    schedule: list[list[str]] = field(default_factory=list)

    def __post_init__(self) -> None:
        self._build_schedule()

    def _build_schedule(self) -> None:
        completed: set[str] = set()
        while len(completed) < len(self.spec.agents):
            ready = self.graph.ready_agents(completed)
            if not ready:
                break
            # Group by explicit layer if available
            layer_idx = min(self.graph.layer_map.get(a, 999) for a in ready)
            batch = [a for a in ready if self.graph.layer_map.get(a, 999) == layer_idx]
            if not batch:
                batch = ready[:]
            self.schedule.append(batch)
            completed.update(batch)


class SwarmCompiler:
    """Parse .hlf swarm files into SwarmSpec."""

    def parse(self, source: str) -> SwarmSpec:
        spec = SwarmSpec(raw_source=source)
        lines = source.splitlines()
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            if not line or line.startswith("#"):
                i += 1
                continue
            if line.startswith("interface "):
                i = self._parse_interface(lines, i, spec)
            elif line.startswith("persona "):
                i = self._parse_persona(lines, i, spec)
            elif line.startswith("agent "):
                i = self._parse_agent(lines, i, spec)
            elif line.startswith("architecture {"):
                i = self._parse_architecture(lines, i, spec)
            elif line.startswith("effect "):
                i = self._parse_effect(lines, i, spec)
            elif re.match(r"layer_\d+:", line):
                i = self._parse_layer(lines, i, spec)
            elif line.startswith("trace {"):
                i = self._parse_trace(lines, i, spec)
            elif line.startswith("checkpoint {"):
                i = self._parse_checkpoint(lines, i, spec)
            elif line.startswith("constraints:") or line.startswith("constraint:"):
                i = self._parse_constraint(lines, i, spec)
            elif re.match(r"[A-Z-]+:", line) and not line.startswith("##"):
                i = self._parse_constraint(lines, i, spec)
            else:
                i += 1
        return spec

    def compile(self, source: str) -> tuple[SwarmSpec, DependencyGraph, ExecutionPlan]:
        """Full compile: parse → dependency graph → execution plan."""
        spec = self.parse(source)
        graph = DependencyGraph(spec)
        plan = ExecutionPlan(spec, graph)
        return spec, graph, plan

    def _parse_interface(self, lines: list[str], i: int, spec: SwarmSpec) -> int:
        header = lines[i].strip()
        name = header[len("interface "):].split("{")[0].strip()
        fields: dict[str, str] = {}
        i += 1
        while i < len(lines) and not lines[i].strip().startswith("}"):
            line = lines[i].strip().rstrip(",")
            if ":" in line:
                k, v = line.split(":", 1)
                fields[k.strip()] = v.strip()
            i += 1
        spec.interfaces[name] = Interface(name, fields)
        return i + 1

    def _parse_architecture(self, lines: list[str], i: int, spec: SwarmSpec) -> int:
        """Parse architecture { key: value, ... } block."""
        i += 1
        while i < len(lines) and not lines[i].strip().startswith("}"):
            line = lines[i].strip().rstrip(",")
            if ":" in line and not line.startswith("#"):
                k, v = line.split(":", 1)
                key = k.strip()
                val = v.strip()
                # Parse list values: [item1, item2]
                if val.startswith("[") and val.endswith("]"):
                    items = [x.strip().strip('"') for x in val[1:-1].split(",") if x.strip()]
                    spec.architecture[key] = items
                else:
                    spec.architecture[key] = val.strip('"')
            i += 1
        return i + 1

    def _parse_agent(self, lines: list[str], i: int, spec: SwarmSpec) -> int:
        header = lines[i].strip()
        name = header[len("agent "):].split("{")[0].strip()
        role = ""
        input_spec: str | dict[str, Any] = "none"
        output_spec: str | dict[str, Any] = "none"
        constraints: list[str] = []
        schema_variant = "full"
        persona = ""
        i += 1
        while i < len(lines) and not lines[i].strip().startswith("}"):
            line = lines[i].strip().rstrip(",")
            if line.startswith("role:"):
                role = line.split(":", 1)[1].strip().strip('"')
            elif line.startswith("persona:"):
                persona = line.split(":", 1)[1].strip().strip('"')
            elif line.startswith("input:"):
                raw = line.split(":", 1)[1].strip()
                input_spec = self._parse_type_or_dict(raw)
            elif line.startswith("output:"):
                raw = line.split(":", 1)[1].strip()
                output_spec = self._parse_type_or_dict(raw)
            elif line.startswith("schema_variant:") or line.startswith("schema-variant:"):
                schema_variant = line.split(":", 1)[1].strip().strip('"')
            elif line.startswith("constraints:"):
                raw = line.split(":", 1)[1].strip()
                constraints = [c.strip().strip('"') for c in raw.strip("[]").split(",") if c.strip()]
            i += 1
        spec.agents[name] = AgentDecl(name, role, input_spec, output_spec, constraints, schema_variant, persona)
        return i + 1

    def _parse_persona(self, lines: list[str], i: int, spec: SwarmSpec) -> int:
        """Parse a persona block: persona Name { ... }."""
        header = lines[i].strip()
        name = header[len("persona "):].split("{")[0].strip()
        description = ""
        capabilities: list[str] = []
        trust_tier = "hearth"
        default_constraints: list[str] = []
        communication_style = "precise"
        supervision: list[str] = []
        i += 1
        while i < len(lines) and not lines[i].strip().startswith("}"):
            line = lines[i].strip().rstrip(",")
            if ":" in line:
                k, v = line.split(":", 1)
                k = k.strip()
                v = v.strip().strip('"')
                if k == "description":
                    description = v
                elif k == "capabilities":
                    v_clean = v.strip("[]")
                    capabilities = [c.strip().strip('"') for c in v_clean.split(",") if c.strip()]
                elif k == "trust_tier":
                    trust_tier = v
                elif k == "default_constraints":
                    v_clean = v.strip("[]")
                    default_constraints = [c.strip().strip('"') for c in v_clean.split(",") if c.strip()]
                elif k == "communication_style":
                    communication_style = v
                elif k == "supervision":
                    v_clean = v.strip("[]")
                    supervision = [s.strip().strip('"') for s in v_clean.split(",") if s.strip()]
            i += 1
        spec.personas[name] = PersonaDef(
            name=name,
            description=description,
            capabilities=capabilities,
            trust_tier=trust_tier,
            default_constraints=default_constraints,
            communication_style=communication_style,
            supervision=supervision,
        )
        return i + 1

    def _parse_type_or_dict(self, raw: str) -> str | dict[str, Any]:
        raw = raw.strip()
        if raw == "none":
            return "none"
        if raw.startswith("{"):
            # Naive JSON-like parse
            try:
                # Replace file("...") with string placeholder
                s = re.sub(r'file\("([^"]+)"\)', r'"file:\1"', raw)
                s = re.sub(r'list\(([^)]+)\)', r'[\1]', s)
                return json.loads(s)
            except json.JSONDecodeError:
                return raw
        return raw

    def _parse_effect(self, lines: list[str], i: int, spec: SwarmSpec) -> int:
        line = lines[i].strip()
        m = re.match(r'effect\s+(\w+)\s*->\s*\[(.*?)\]', line)
        if m:
            agent = m.group(1)
            actions_raw = m.group(2)
            actions: list[dict[str, str]] = []
            for act in re.findall(r'(READ|WRITE)\("([^"]+)"\)', actions_raw):
                actions.append({"type": act[0], "path": act[1]})
            # Handle all_routes, all_services, all_middleware as wildcards
            for act in re.findall(r'(READ)\((\w+)\)', actions_raw):
                actions.append({"type": act[0], "path": f"wildcard:{act[1]}"})
            spec.effects[agent] = Effect(agent, actions)
        return i + 1

    def _parse_layer(self, lines: list[str], i: int, spec: SwarmSpec) -> int:
        line = lines[i].strip()
        m = re.match(r'layer_(\d+):\s*\[(.*?)\]', line)
        if m:
            agents = [a.strip() for a in m.group(2).split(",") if a.strip()]
            spec.layers.append(agents)
        return i + 1

    def _parse_trace(self, lines: list[str], i: int, spec: SwarmSpec) -> int:
        i += 1
        body = []
        while i < len(lines) and not lines[i].strip().startswith("}"):
            body.append(lines[i].strip().rstrip(","))
            i += 1
        spec.trace_config = self._parse_kv_block(body)
        return i + 1

    def _parse_checkpoint(self, lines: list[str], i: int, spec: SwarmSpec) -> int:
        i += 1
        body = []
        while i < len(lines) and not lines[i].strip().startswith("}"):
            body.append(lines[i].strip().rstrip(","))
            i += 1
        spec.checkpoint_config = self._parse_kv_block(body)
        return i + 1

    def _parse_constraint(self, lines: list[str], i: int, spec: SwarmSpec) -> int:
        line = lines[i].strip()
        # Handle "constraints:" block header — parse subsequent bullet lines
        if line.lower() == "constraints:" or line.lower() == "constraint:":
            i += 1
            while i < len(lines):
                next_line = lines[i].strip()
                if not next_line or next_line.startswith("##"):
                    i += 1
                    continue
                if next_line.startswith("- ") and ":" in next_line:
                    # "- TAG: description" format
                    content = next_line[2:]  # strip "- "
                    if ":" in content:
                        k, v = content.split(":", 1)
                        k = k.strip()
                        if k.isupper() or "-" in k:
                            spec.constraints[k] = v.strip()
                    i += 1
                elif self._is_constraint_line(next_line):
                    k, v = next_line.split(":", 1)
                    k = k.strip()
                    if k.isupper() or "-" in k:
                        spec.constraints[k] = v.strip()
                    i += 1
                else:
                    # End of constraints block
                    break
            return i

        # Single constraint line
        if ":" in line and not line.startswith("##"):
            # Strip leading bullet if present
            content = line
            if content.startswith("- "):
                content = content[2:]
            k, v = content.split(":", 1)
            k = k.strip()
            if k.isupper() or "-" in k:
                spec.constraints[k] = v.strip()
        return i + 1

    def _is_constraint_line(self, line: str) -> bool:
        """Check if a line looks like a constraint definition: TAG: description."""
        if ":" not in line:
            return False
        k = line.split(":", 1)[0].strip()
        return bool(re.match(r"^[A-Z][A-Z0-9-]*$", k))

    def _parse_kv_block(self, lines: list[str]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for line in lines:
            if ":" in line:
                k, v = line.split(":", 1)
                k = k.strip()
                v = v.strip().strip('"')
                if v.startswith("[") and v.endswith("]"):
                    v = [x.strip().strip('"') for x in v[1:-1].split(",") if x.strip()]
                elif v.lower() == "true":
                    v = True
                elif v.lower() == "false":
                    v = False
                result[k] = v
        return result


def compile_swarm(source: str) -> tuple[SwarmSpec, DependencyGraph, ExecutionPlan]:
    """Convenience function: compile swarm source into executable plan."""
    compiler = SwarmCompiler()
    return compiler.compile(source)
