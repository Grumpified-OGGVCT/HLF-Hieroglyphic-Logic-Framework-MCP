from hlf_mcp import server


def test_hlf_do_dry_run_generates_governed_audit() -> None:
    result = server.hlf_do(
        "Audit /var/log/system.log in read-only mode and summarize the top errors.",
        dry_run=True,
        show_hlf=True,
    )

    assert result["success"] is True
    assert result["dry_run"] is True
    assert result["tier"] == "forge"
    assert result["governed"] is True
    assert result["capsule_violations"] == []
    assert result["hlf_source"].startswith("[HLF-v3]")
    assert "gas_estimate" in result["math"]
    assert "what_hlf_did" in result