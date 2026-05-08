from __future__ import annotations

from hlf_mcp.hlf.authority import (
    AUTHORITY_SURFACES,
    DownstreamTask,
    authority_matrix,
    downstream_guidance,
)


def test_authority_matrix_distinguishes_all_required_lanes() -> None:
    matrix = authority_matrix()

    assert set(matrix) == {
        "full-original-target",
        "present-packaged-current-truth",
        "bridge-recovery-material",
        "invalid-mistaken-checkout-artifact",
    }
    assert "SSOT_HLF_MCP.md" in matrix["present-packaged-current-truth"]["authorities"]
    assert any(
        "HLF_MCP_WORKING" in authority
        for authority in matrix["bridge-recovery-material"]["authorities"]
    )
    assert any(
        "msty_playground/hlf_repo" in authority
        for authority in matrix["invalid-mistaken-checkout-artifact"]["authorities"]
    )


def test_authority_surface_uses_repo_relative_authorities() -> None:
    for surface in AUTHORITY_SURFACES:
        for authority in surface.authorities:
            assert ":\\" not in authority
            assert not authority.startswith("/")


def test_downstream_guidance_names_restore_and_internal_hlf_constraints() -> None:
    restore = downstream_guidance(DownstreamTask.RESTORE_GRAMMAR)
    internal = downstream_guidance("mandatory-internal-hlf")

    assert any("grammar.py" in item and "dictionary.json" in item for item in restore)
    assert any("wrong-checkout" in item for item in restore)
    assert any("fail closed" in item for item in internal)
    assert any("SSOT_HLF_MCP.md" in item for item in internal)
