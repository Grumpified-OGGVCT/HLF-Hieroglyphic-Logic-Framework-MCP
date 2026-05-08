#!/usr/bin/env python3
"""
Validation script for Phase 2 & 3 MCP Protocol v2025-11-25 implementation.
Tests all core components without requiring a running server.
"""

import sys
from datetime import datetime


def test_imports():
    """Test 1: Module imports"""
    print("\n" + "="*70)
    print("TEST 1: Module Imports")
    print("="*70)
    try:
        import hlf_mcp.mcp_protocol_v2025 as protocol

        required = [
            "CANONICAL_PROTOCOL_VERSION",
            "SUPPORTED_PROTOCOL_VERSIONS",
            "MCPSession",
            "MCPSessionStore",
            "build_mcp_response_headers",
            "validate_protocol_version",
        ]
        missing = [name for name in required if not hasattr(protocol, name)]
        assert not missing, f"Missing protocol exports: {missing}"
        print("✅ All Protocol v2025 imports successful")
        return True
    except ImportError as e:
        print(f"❌ Import failed: {e}")
        return False


def test_version_constants():
    """Test 2: Version constants"""
    print("\n" + "="*70)
    print("TEST 2: Version Constants")
    print("="*70)
    try:
        from hlf_mcp.mcp_protocol_v2025 import (
            CANONICAL_PROTOCOL_VERSION,
            SUPPORTED_PROTOCOL_VERSIONS,
        )

        assert CANONICAL_PROTOCOL_VERSION == "2025-11-25", f"Expected canonical 2025-11-25, got {CANONICAL_PROTOCOL_VERSION}"
        print(f"✅ Canonical version correct: {CANONICAL_PROTOCOL_VERSION}")

        assert isinstance(SUPPORTED_PROTOCOL_VERSIONS, frozenset), "Supported versions must be frozenset"
        assert "2025-11-25" in SUPPORTED_PROTOCOL_VERSIONS, "2025-11-25 not in supported versions"
        assert "2024-11-05" in SUPPORTED_PROTOCOL_VERSIONS, "2024-11-05 not in supported versions"
        print(f"✅ Supported versions correct: {SUPPORTED_PROTOCOL_VERSIONS}")

        return True
    except AssertionError as e:
        print(f"❌ Assertion failed: {e}")
        return False
    except Exception as e:
        print(f"❌ Test failed: {e}")
        return False


def test_session_creation():
    """Test 3: MCPSession creation"""
    print("\n" + "="*70)
    print("TEST 3: MCPSession Creation")
    print("="*70)
    try:
        from hlf_mcp.mcp_protocol_v2025 import MCPSession

        session = MCPSession(
            session_id="test-session-001",
            protocol_version="2025-11-25",
            client_capabilities={"phase2": True, "phase3": True},
        )

        assert session.session_id == "test-session-001", "Session ID not set correctly"
        assert session.protocol_version == "2025-11-25", "Protocol version not set correctly"
        assert session.phase_2_enabled is True, "Phase 2 not enabled"
        assert session.phase_3_enabled is True, "Phase 3 not enabled"
        assert isinstance(session.created_at, datetime), "Created timestamp not datetime"
        assert session.message_count == 0, "Message count should start at 0"

        print(f"✅ Session created: {session.session_id}")
        print(f"   Protocol: {session.protocol_version}")
        print(f"   Phase 2: {session.phase_2_enabled}, Phase 3: {session.phase_3_enabled}")
        print(f"   Messages: {session.message_count}")

        return True
    except AssertionError as e:
        print(f"❌ Assertion failed: {e}")
        return False
    except Exception as e:
        print(f"❌ Test failed: {e}")
        return False


def test_session_operations():
    """Test 4: MCPSession operations"""
    print("\n" + "="*70)
    print("TEST 4: MCPSession Operations")
    print("="*70)
    try:
        from hlf_mcp.mcp_protocol_v2025 import MCPSession

        session = MCPSession(
            session_id="test-ops-001",
            protocol_version="2025-11-25",
            client_capabilities={},
        )

        # Test message recording
        session.record_message("request", "test_method", {"key": "value"})
        assert session.message_count == 1, f"Expected 1 message, got {session.message_count}"
        print(f"✅ Message recorded, count: {session.message_count}")

        session.record_message("response", "test_method", {"result": "ok"})
        assert session.message_count == 2, f"Expected 2 messages, got {session.message_count}"
        print(f"✅ Second message recorded, count: {session.message_count}")

        # Test activity update
        old_activity = session.last_activity
        session.update_activity()
        assert session.last_activity > old_activity, "Activity time not updated"
        print("✅ Activity timestamp updated")

        # Test serialization
        session_dict = session.model_dump()
        assert "session_id" in session_dict, "session_id not in serialization"
        assert "protocol_version" in session_dict, "protocol_version not in serialization"
        print("✅ Session serialized successfully")

        return True
    except AssertionError as e:
        print(f"❌ Assertion failed: {e}")
        return False
    except Exception as e:
        print(f"❌ Test failed: {e}")
        return False


def test_session_store():
    """Test 5: MCPSessionStore"""
    print("\n" + "="*70)
    print("TEST 5: MCPSessionStore")
    print("="*70)
    try:
        from hlf_mcp.mcp_protocol_v2025 import MCPSession, MCPSessionStore

        store = MCPSessionStore()

        # Create and store sessions
        session1 = MCPSession("sess-1", "2025-11-25", {})
        session2 = MCPSession("sess-2", "2025-11-25", {})

        stored1 = store.create_or_update(session1)
        assert stored1.session_id == "sess-1", "Session 1 not stored correctly"
        print(f"✅ Session 1 stored: {stored1.session_id}")

        stored2 = store.create_or_update(session2)
        assert stored2.session_id == "sess-2", "Session 2 not stored correctly"
        print(f"✅ Session 2 stored: {stored2.session_id}")

        # Retrieve sessions
        retrieved1 = store.get("sess-1")
        assert retrieved1 is not None, "Session 1 not retrieved"
        assert retrieved1.session_id == "sess-1", "Retrieved session 1 ID mismatch"
        print(f"✅ Session 1 retrieved: {retrieved1.session_id}")

        # List sessions
        all_sessions = store.list_all()
        assert len(all_sessions) >= 2, f"Expected at least 2 sessions, got {len(all_sessions)}"
        print(f"✅ Sessions listed: {len(all_sessions)} total")

        # Delete session
        deleted = store.delete("sess-1")
        assert deleted is True, "Session 1 not deleted"
        print("✅ Session 1 deleted")

        # Verify deletion
        retrieved_deleted = store.get("sess-1")
        assert retrieved_deleted is None, "Session 1 still exists after deletion"
        print("✅ Deletion verified: session no longer retrievable")

        return True
    except AssertionError as e:
        print(f"❌ Assertion failed: {e}")
        return False
    except Exception as e:
        print(f"❌ Test failed: {e}")
        return False


def test_version_validation():
    """Test 6: Protocol version validation (Phase 2)"""
    print("\n" + "="*70)
    print("TEST 6: Protocol Version Validation (Phase 2)")
    print("="*70)
    try:
        from hlf_mcp.mcp_protocol_v2025 import validate_protocol_version

        # Valid versions
        is_valid = validate_protocol_version("2025-11-25")
        assert is_valid is True, "2025-11-25 should be valid"
        print("✅ Canonical version validates: 2025-11-25")

        is_valid = validate_protocol_version("2024-11-05")
        assert is_valid is True, "2024-11-05 should be valid (fallback)"
        print("✅ Fallback version validates: 2024-11-05")

        # Invalid version
        is_valid = validate_protocol_version("1999-01-01")
        assert is_valid is False, "1999-01-01 should be invalid"
        print("✅ Invalid version rejected: 1999-01-01")

        return True
    except AssertionError as e:
        print(f"❌ Assertion failed: {e}")
        return False
    except Exception as e:
        print(f"❌ Test failed: {e}")
        return False


def test_response_headers():
    """Test 7: MCP response headers (Phase 3 compliance)"""
    print("\n" + "="*70)
    print("TEST 7: MCP Response Headers (Phase 3 Compliance)")
    print("="*70)
    try:
        from hlf_mcp.mcp_protocol_v2025 import build_mcp_response_headers

        headers = build_mcp_response_headers(
            session_id="test-session-003",
            phase_2_enabled=True,
            phase_3_enabled=True,
            message_count=42,
        )

        # Check required headers
        assert "X-MCP-Protocol-Version" in headers, "Missing protocol version header"
        assert headers["X-MCP-Protocol-Version"] == "2025-11-25", "Wrong protocol version"
        print(f"✅ Protocol version header: {headers['X-MCP-Protocol-Version']}")

        assert "X-MCP-Session-ID" in headers, "Missing session ID header"
        assert headers["X-MCP-Session-ID"] == "test-session-003", "Wrong session ID"
        print(f"✅ Session ID header: {headers['X-MCP-Session-ID']}")

        assert "X-MCP-Phase-2-Enabled" in headers, "Missing Phase 2 header"
        assert headers["X-MCP-Phase-2-Enabled"] == "true", "Phase 2 flag not set"
        print(f"✅ Phase 2 header: {headers['X-MCP-Phase-2-Enabled']}")

        assert "X-MCP-Phase-3-Enabled" in headers, "Missing Phase 3 header"
        assert headers["X-MCP-Phase-3-Enabled"] == "true", "Phase 3 flag not set"
        print(f"✅ Phase 3 header: {headers['X-MCP-Phase-3-Enabled']}")

        assert "X-MCP-Message-Count" in headers, "Missing message count header"
        assert headers["X-MCP-Message-Count"] == "42", "Wrong message count"
        print(f"✅ Message count header: {headers['X-MCP-Message-Count']}")

        return True
    except AssertionError as e:
        print(f"❌ Assertion failed: {e}")
        return False
    except Exception as e:
        print(f"❌ Test failed: {e}")
        return False


def main():
    """Run all validation tests"""
    print("\n" + "="*70)
    print("PHASE 2 & 3 PROTOCOL IMPLEMENTATION VALIDATION")
    print("="*70)

    tests = [
        ("Imports", test_imports),
        ("Version Constants", test_version_constants),
        ("Session Creation", test_session_creation),
        ("Session Operations", test_session_operations),
        ("Session Store", test_session_store),
        ("Version Validation", test_version_validation),
        ("Response Headers", test_response_headers),
    ]

    results = {}
    for test_name, test_func in tests:
        try:
            results[test_name] = test_func()
        except Exception as e:
            print(f"\n❌ EXCEPTION in {test_name}: {e}")
            results[test_name] = False

    # Summary
    print("\n" + "="*70)
    print("VALIDATION SUMMARY")
    print("="*70)

    passed = sum(1 for v in results.values() if v)
    total = len(results)

    for test_name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {test_name}")

    print("="*70)
    print(f"OVERALL: {passed}/{total} tests passed")
    print("="*70)

    if passed == total:
        print("\n🎉 Phase 2 & 3 Implementation VALIDATED! All tests passed.")
        return 0
    else:
        print(f"\n⚠️  {total - passed} test(s) failed. Please review the output above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
