#!/usr/bin/env python3
"""Merge ralph trace JSON with agent persona/metadata.

Usage: ralph_merge_trace.py <trace_file> <role> <trust> <lane> <phase> <agent_id> <handoff_json> <vote_json> <dissent_json>
"""
import json
import sys


def main():
    if len(sys.argv) != 10:
        print(f"Usage: {sys.argv[0]} <trace_file> <role> <trust> <lane> <phase> <agent_id> <handoff_json> <vote_json> <dissent_json>", file=sys.stderr)
        sys.exit(1)

    trace_file = sys.argv[1]
    with open(trace_file, 'r') as f:
        trace = json.load(f)

    def parse_optional(json_str):
        if json_str == 'null':
            return None
        return json.loads(json_str)

    meta = {
        'agent_template': 'ralph_agent.sh',
        'persona': {
            'role': sys.argv[2],
            'trust_state': sys.argv[3],
            'cognitive_lane_policy': sys.argv[4],
            'lifecycle_phase': sys.argv[5],
            'agent_id': sys.argv[6],
            'template_version': '1.0.0',
            'surface': 'GrumpRolled/Jules RALPH agent',
        },
        'handoff_contract': parse_optional(sys.argv[7]),
        'swarm_vote': parse_optional(sys.argv[8]),
        'swarm_dissent': parse_optional(sys.argv[9]),
    }
    trace.update(meta)
    json.dump(trace, sys.stdout, indent=2)


if __name__ == '__main__':
    main()
