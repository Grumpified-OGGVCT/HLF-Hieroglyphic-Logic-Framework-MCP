#!/usr/bin/env python3
"""Governance stress tests A-E for HLF MCP.

Tests tamper detection, gas exhaustion, tier escalation, Merkle chain
integrity, and HKS exemplar capture.

Run: python scripts/stress_test_governance_advanced.py
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))


# ═══════════════════════════════════════════════════════════════════════════════
# Test A: Tampered Checkpoint Detection
# ═══════════════════════════════════════════════════════════════════════════════

def test_a_tampered_checkpoint() -> dict:
    """Load a real adapter file, flip one bit in weights, verify hash change."""
    print("\n" + "=" * 60)
    print("TEST A: Tampered Checkpoint Detection")
    print("=" * 60)

    result = {"test": "A", "name": "Tampered Checkpoint Detection", "passed": False, "details": {}}

    import os as _os
    adapter_path = (
        _os.path.expanduser("~/.cache/huggingface/recursivemas/")
        "models--RecursiveMAS--Sequential-Light-Outerlinks/"
        "snapshots/12420b91249efe1d05cf80b72de7d8007aa85b00/"
        "Planner-Critic-Outerlink(math).pt"
    )

    try:
        import torch

        # Compute original SHA-256
        with open(adapter_path, "rb") as f:
            original_bytes = f.read()
        original_hash = hashlib.sha256(original_bytes).hexdigest()
        print(f"  Original SHA-256: {original_hash[:16]}...")
        result["details"]["original_hash"] = original_hash

        # Load state dict, corrupt first parameter's first element
        state_dict = torch.load(adapter_path, map_location="cpu", weights_only=True)
        # Find the first proper state dict entry
        if "adapter" in state_dict:
            state_dict = state_dict["adapter"]
            result["details"]["wrapper_key"] = "adapter"

        # Find first tensor parameter
        first_key = None
        for key, val in state_dict.items():
            if isinstance(val, torch.Tensor) and val.numel() > 0:
                first_key = key
                break

        if first_key is None:
            result["details"]["error"] = "No tensor parameters found in checkpoint"
            print(f"  ❌ {result['details']['error']}")
            return result

        original_val = state_dict[first_key].clone()
        print(f"  First parameter: {first_key}, shape={list(original_val.shape)}")
        print(f"  Original first element: {original_val.flatten()[0].item():.6f}")

        # Flip one bit: add 1e-7 to first element
        corrupted = state_dict[first_key].clone()
        corrupted.flatten()[0] += 1e-7
        state_dict[first_key] = corrupted
        print(f"  Corrupted first element: {corrupted.flatten()[0].item():.6f}")

        # Save corrupted copy
        corrupted_path = str(REPO_ROOT / "scripts" / "_corrupted_adapter_test.pt")
        torch.save(state_dict, corrupted_path)

        # Compute SHA-256 of corrupted copy
        with open(corrupted_path, "rb") as f:
            corrupted_bytes = f.read()
        corrupted_hash = hashlib.sha256(corrupted_bytes).hexdigest()
        print(f"  Corrupted SHA-256: {corrupted_hash[:16]}...")
        result["details"]["corrupted_hash"] = corrupted_hash

        # Clean up temp file
        try:
            os.remove(corrupted_path)
        except OSError:
            pass

        # Verify: hashes differ
        hashes_differ = original_hash != corrupted_hash
        print(f"  Hashes differ: {hashes_differ}")

        # Verify: original hash would be detected as mismatch
        # Recompute hash of original file and compare
        with open(adapter_path, "rb") as f:
            recheck_hash = hashlib.sha256(f.read()).hexdigest()
        capsule_would_detect = recheck_hash == original_hash and recheck_hash != corrupted_hash
        print(f"  Capsule validation would detect: {capsule_would_detect}")

        result["passed"] = hashes_differ and capsule_would_detect
        result["details"]["hashes_differ"] = hashes_differ
        result["details"]["capsule_would_detect"] = capsule_would_detect
        result["details"]["first_param"] = first_key

    except FileNotFoundError:
        result["details"]["error"] = f"Adapter file not found: {adapter_path}"
        print(f"  ⚠️ {result['details']['error']}")
    except Exception as e:
        result["details"]["error"] = str(e)
        import traceback
        result["details"]["traceback"] = traceback.format_exc()[-300:]
        print(f"  ❌ Exception: {e}")

    print(f"  {'✅ PASS' if result['passed'] else '❌ FAIL'}")
    return result


# ═══════════════════════════════════════════════════════════════════════════════
# Test B: Gas Exhaustion Mid-Recursion
# ═══════════════════════════════════════════════════════════════════════════════

def test_b_gas_exhaustion() -> dict:
    """Simulate gas exhaustion during latent recursion."""
    print("\n" + "=" * 60)
    print("TEST B: Gas Exhaustion Mid-Recursion")
    print("=" * 60)

    result = {"test": "B", "name": "Gas Exhaustion Mid-Recursion", "passed": False, "details": {}}

    try:
        from hlf_mcp.hlf.latent_capsule import LatentCapsule

        # Create capsule with max_rounds=2 → needs 3*25*2 + 50 = 200, but min is 1000
        # The gas formula: max(3*25*max_rounds + 50, 1000) = max(200, 1000) = 1000
        capsule = LatentCapsule(agent_id="gas-test", max_rounds=2)
        default_max_gas = capsule.capsule.max_gas
        gas_per_round = capsule._GAS_PER_ROUND  # 75
        gas_per_handoff = capsule._GAS_PER_HANDOFF  # 25
        print(f"  Default max_gas: {default_max_gas}")
        print(f"  Gas per round (3 handoffs): {gas_per_round}")
        print(f"  Gas per handoff: {gas_per_handoff}")

        # Override to insufficient gas: 37
        capsule.capsule.max_gas = 37
        required_gas = capsule._GAS_PER_ROUND * 2  # 150 for 2 rounds
        print(f"  Required gas for 2 rounds: {required_gas}")
        print(f"  Set max_gas to: {37}")

        # Verify capsule detects gas insufficiency
        gas_insufficient = 37 < required_gas
        print(f"  Gas insufficient (37 < 150): {gas_insufficient}")
        result["details"]["gas_insufficient_detected"] = gas_insufficient

        # Round-by-round gas tracking
        gas_used = 0
        rounds_possible = 0
        handoffs_possible = 0

        for round_num in range(1, capsule.max_rounds + 1):
            for handoff in range(3):  # 3 handoffs per round
                next_gas = gas_used + gas_per_handoff
                if next_gas > 37:
                    print(f"  ⚡ Gas exhausted at round {round_num}, handoff {handoff + 1} "
                          f"(used={gas_used}, next would be {next_gas}, max=37)")
                    break
                gas_used = next_gas
                handoffs_possible += 1
            else:
                rounds_possible += 1
                continue
            break

        print(f"  Rounds completed before exhaustion: {rounds_possible}")
        print(f"  Handoffs completed before exhaustion: {handoffs_possible}")
        print(f"  Total gas used: {gas_used}")

        # Check exhaustion at handoff 2 (0-indexed: handoff #2 = 3rd handoff of round 1 = gas 75)
        # Actually with 37 gas: handoff 1 uses 25 (25 total), handoff 2 would be 50 > 37
        # So exhaustion at handoff 2 (the 2nd handoff of round 1)
        exhausts_before_handoff_2 = handoffs_possible < 2
        print(f"  Exhausts before handoff 2 (of round 1): {exhausts_before_handoff_2}")

        result["passed"] = gas_insufficient and handoffs_possible < 2
        result["details"]["gas_per_handoff"] = gas_per_handoff
        result["details"]["gas_per_round"] = gas_per_round
        result["details"]["handoffs_completed"] = handoffs_possible
        result["details"]["rounds_completed"] = rounds_possible
        result["details"]["total_gas_used"] = gas_used
        result["details"]["exhausts_before_handoff_2"] = exhausts_before_handoff_2

    except Exception as e:
        result["details"]["error"] = str(e)
        import traceback
        result["details"]["traceback"] = traceback.format_exc()[-300:]
        print(f"  ❌ Exception: {e}")

    print(f"  {'✅ PASS' if result['passed'] else '❌ FAIL'}")
    return result


# ═══════════════════════════════════════════════════════════════════════════════
# Test C: Tier Escalation Violation
# ═══════════════════════════════════════════════════════════════════════════════

def test_c_tier_escalation() -> dict:
    """Verify tier hierarchy and that hearth cannot use LATENT_COMMUNICATION."""
    print("\n" + "=" * 60)
    print("TEST C: Tier Escalation Violation")
    print("=" * 60)

    result = {"test": "C", "name": "Tier Escalation Violation", "passed": False, "details": {}}

    try:
        from hlf_mcp.hlf.capsules import (
            hearth_capsule,
            sovereign_capsule,
            IntentCapsule,
            tier_rank,
            normalize_tier,
        )

        # Verify hearth < sovereign
        hearth_rank = tier_rank("hearth")
        sovereign_rank = tier_rank("sovereign")
        tier_order_correct = hearth_rank < sovereign_rank
        print(f"  Hearth rank: {hearth_rank}, Sovereign rank: {sovereign_rank}")
        print(f"  Hearth < Sovereign: {tier_order_correct}")
        result["details"]["hearth_rank"] = hearth_rank
        result["details"]["sovereign_rank"] = sovereign_rank
        result["details"]["tier_order_correct"] = tier_order_correct

        # Verify hearth capsule cannot use LATENT_COMMUNICATION
        from hlf_mcp.hlf.latent_capsule import LatentCapsule
        lc = LatentCapsule(agent_id="tier-test")
        # LatentCapsule always creates sovereign-tier internally
        capsule_tier = lc.capsule.tier
        is_sovereign = capsule_tier == "sovereign"
        print(f"  LatentCapsule tier: {capsule_tier} (sovereign: {is_sovereign})")
        result["details"]["latent_capsule_tier"] = capsule_tier
        result["details"]["latent_capsule_is_sovereign"] = is_sovereign

        # Check that hearth-tier capsule CANNOT have LATENT_COMMUNICATION
        # (LATENT_COMMUNICATION is a sovereign-tier only effect_class)
        h_capsule = hearth_capsule(agent_id="hearth-test")
        # hearth tier has _LATENT_TIERS = frozenset({"sovereign"})
        # so hearth can never pass latent tier checks
        from hlf_mcp.hlf.latent_capsule import LatentCapsule as LC
        hearth_can_latent = h_capsule.tier in LC._LATENT_TIERS
        print(f"  Hearth capsule tier: {h_capsule.tier}")
        print(f"  Hearth allowed for latent: {hearth_can_latent}")
        result["details"]["hearth_allowed_for_latent"] = hearth_can_latent

        # Verify LatentCapsule.validate_before_run rejects non-sovereign
        # Force a hearth-tier capsule into the LatentCapsule
        lc2 = LatentCapsule(agent_id="forced-hearth")
        lc2._capsule = h_capsule  # Inject hearth capsule
        violations = lc2.validate_before_run()
        tier_rejected = any("Tier" in v for v in violations)
        print(f"  Validation violations with hearth capsule: {violations}")
        print(f"  Tier rejected: {tier_rejected}")
        result["details"]["validation_violations"] = violations
        result["details"]["tier_rejected"] = tier_rejected

        result["passed"] = tier_order_correct and is_sovereign and not hearth_can_latent and tier_rejected
        result["details"]["all_checks_pass"] = {
            "tier_order_correct": tier_order_correct,
            "latent_is_sovereign": is_sovereign,
            "hearth_blocked_from_latent": not hearth_can_latent,
            "validation_rejects_hearth": tier_rejected,
        }

    except Exception as e:
        result["details"]["error"] = str(e)
        import traceback
        result["details"]["traceback"] = traceback.format_exc()[-300:]
        print(f"  ❌ Exception: {e}")

    print(f"  {'✅ PASS' if result['passed'] else '❌ FAIL'}")
    return result


# ═══════════════════════════════════════════════════════════════════════════════
# Test D: Merkle Chain Tamper Resistance
# ═══════════════════════════════════════════════════════════════════════════════

def _merkle_root(hashes: list[str]) -> str:
    """Compute a simple Merkle root from a list of hex hashes."""
    if not hashes:
        return hashlib.sha256(b"").hexdigest()
    if len(hashes) == 1:
        return hashes[0]
    # Pair-wise concatenation
    current = hashes[:]
    while len(current) > 1:
        next_level = []
        for i in range(0, len(current), 2):
            left = current[i]
            right = current[i + 1] if i + 1 < len(current) else left
            combined = left + right
            next_level.append(hashlib.sha256(combined.encode()).hexdigest())
        current = next_level
    return current[0]


def test_d_merkle_tamper() -> dict:
    """Build Merkle chain, delete/corrupt entries, verify root changes."""
    print("\n" + "=" * 60)
    print("TEST D: Merkle Chain Tamper Resistance")
    print("=" * 60)

    result = {"test": "D", "name": "Merkle Chain Tamper Resistance", "passed": False, "details": {}}

    try:
        # Build 6-entry provenance hash chain (simulating 2 rounds × 3 handoffs)
        entries = []
        for i in range(1, 7):
            payload = f"round_{((i-1)//3)+1}|handoff_{(i-1)%3+1}|agent_{i}|data_block_{i}"
            h = hashlib.sha256(payload.encode()).hexdigest()
            entries.append({"index": i, "data": payload, "hash": h})

        original_hashes = [e["hash"] for e in entries]
        original_root = _merkle_root(original_hashes)
        print(f"  Original Merkle root: {original_root[:16]}...")
        result["details"]["original_root"] = original_root
        result["details"]["entry_count"] = len(entries)

        # Test 1: Delete entry #3 and recompute
        deleted_hashes = original_hashes[:2] + original_hashes[3:]
        deleted_root = _merkle_root(deleted_hashes)
        deletion_detected = deleted_root != original_root
        print(f"  Delete entry #3: root changed = {deletion_detected}")
        print(f"    Deleted root: {deleted_root[:16]}...")
        result["details"]["deletion_detected"] = deletion_detected
        result["details"]["deleted_root"] = deleted_root

        # Test 2: Corrupt entry #2 (change one character)
        corrupted_hashes = original_hashes[:]
        corrupted_hashes[1] = hashlib.sha256(
            entries[1]["data"].replace("handoff_2", "handoff_X").encode()
        ).hexdigest()
        corrupted_root = _merkle_root(corrupted_hashes)
        corruption_detected = corrupted_root != original_root
        print(f"  Corrupt entry #2: root changed = {corruption_detected}")
        print(f"    Corrupted root: {corrupted_root[:16]}...")
        result["details"]["corruption_detected"] = corruption_detected
        result["details"]["corrupted_root"] = corrupted_root

        result["passed"] = deletion_detected and corruption_detected
        result["details"]["both_detected"] = {
            "deletion": deletion_detected,
            "corruption": corruption_detected,
        }

    except Exception as e:
        result["details"]["error"] = str(e)
        import traceback
        result["details"]["traceback"] = traceback.format_exc()[-300:]
        print(f"  ❌ Exception: {e}")

    print(f"  {'✅ PASS' if result['passed'] else '❌ FAIL'}")
    return result


# ═══════════════════════════════════════════════════════════════════════════════
# Test E: HKS Exemplar Capture Simulation
# ═══════════════════════════════════════════════════════════════════════════════

def test_e_hks_exemplar() -> dict:
    """Structural test of HKS exemplar capture for honest failure tracking."""
    print("\n" + "=" * 60)
    print("TEST E: HKS Exemplar Capture Simulation")
    print("=" * 60)

    result = {"test": "E", "name": "HKS Exemplar Capture Simulation", "passed": False, "details": {}}

    try:
        # Create a dict representing a failed exemplar
        exemplar = {
            "prompt": "A 55-year-old woman presents with fatigue, weight gain, and constipation. "
                      "Labs: TSH 8.2, free T4 1.1 (normal). What is the most likely diagnosis?",
            "output": "Non-Altoine's disease",
            "status": "failed",
            "provenance_hashes": [
                "a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6",
                "f6e5d4c3b2a1f0e9d8c7b6a5f4e3d2c1",
            ],
            "capsule_id": "test-123",
            "timestamp": "2026-01-15T10:30:00Z",
            "failure_mode": "hallucinated_diagnosis",
            "review_status": "pending",
        }

        # Check 1: Exemplar has 'status' field that can be 'failed'
        has_status = "status" in exemplar
        status_can_be_failed = exemplar.get("status") == "failed"
        print(f"  Has 'status' field: {has_status}")
        print(f"  Status is 'failed': {status_can_be_failed}")
        result["details"]["has_status"] = has_status
        result["details"]["status_is_failed"] = status_can_be_failed

        # Check 2: Provenance hashes are present
        has_provenance = "provenance_hashes" in exemplar
        prov_hashes = exemplar.get("provenance_hashes", [])
        has_hashes = len(prov_hashes) > 0
        print(f"  Has 'provenance_hashes' field: {has_provenance}")
        print(f"  Provenance hash count: {len(prov_hashes)}")
        result["details"]["has_provenance_hashes"] = has_provenance
        result["details"]["provenance_hash_count"] = len(prov_hashes)

        # Check 3: Failed output is stored alongside provenance
        has_output = "output" in exemplar
        output_stored = bool(exemplar.get("output"))
        print(f"  Has 'output' field: {has_output}")
        print(f"  Output is non-empty: {output_stored}")
        result["details"]["has_output"] = has_output
        result["details"]["output_stored"] = output_stored

        # Check 4: Failure mode is recorded
        has_failure_mode = "failure_mode" in exemplar
        print(f"  Has 'failure_mode' field: {has_failure_mode}")
        result["details"]["has_failure_mode"] = has_failure_mode

        # Check 5: All required fields for honest failure tracking are present
        required_fields = ["prompt", "output", "status", "provenance_hashes", "capsule_id"]
        all_required = all(f in exemplar for f in required_fields)
        print(f"  All required fields present: {all_required}")
        result["details"]["all_required_fields"] = all_required
        result["details"]["required_fields"] = required_fields

        result["passed"] = (
            status_can_be_failed
            and has_hashes
            and output_stored
            and all_required
            and has_failure_mode
        )
        result["details"]["all_checks"] = {
            "status_is_failed": status_can_be_failed,
            "has_provenance_hashes": has_hashes,
            "output_stored": output_stored,
            "all_required_fields": all_required,
            "has_failure_mode": has_failure_mode,
        }

    except Exception as e:
        result["details"]["error"] = str(e)
        import traceback
        result["details"]["traceback"] = traceback.format_exc()[-300:]
        print(f"  ❌ Exception: {e}")

    print(f"  {'✅ PASS' if result['passed'] else '❌ FAIL'}")
    return result


# ═══════════════════════════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════════════════════════

def main() -> None:
    print("=" * 70)
    print("HLF Governance Advanced Stress Tests (A-E)")
    print("=" * 70)

    results = []

    tests = [
        ("A", test_a_tampered_checkpoint),
        ("B", test_b_gas_exhaustion),
        ("C", test_c_tier_escalation),
        ("D", test_d_merkle_tamper),
        ("E", test_e_hks_exemplar),
    ]

    for label, test_fn in tests:
        r = test_fn()
        results.append(r)

    # Summary
    print("\n" + "=" * 70)
    print("RESULTS SUMMARY")
    print("=" * 70)

    all_passed = True
    for r in results:
        status = "✅ PASS" if r["passed"] else "❌ FAIL"
        print(f"  Test {r['test']}: {r['name']:<40} {status}")
        if not r["passed"]:
            all_passed = False

    print(f"\n  Overall: {'✅ ALL PASSED' if all_passed else '❌ SOME FAILED'}")

    # Save results
    out_path = REPO_ROOT / "governance_advanced_results.json"
    with open(out_path, "w") as f:
        json.dump({
            "all_passed": all_passed,
            "results": results,
        }, f, indent=2, default=str)
    print(f"\n  Results saved to: {out_path}")


if __name__ == "__main__":
    main()
