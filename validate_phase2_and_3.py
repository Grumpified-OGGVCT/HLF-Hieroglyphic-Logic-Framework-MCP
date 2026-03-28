#!/usr/bin/env python3
"""
Validation script for Phase 2 & 3 MCP Protocol v2025-11-25 implementation.
Tests all core components matching actual implementation signatures.
"""

import sys


def test_imports():
    """Test 1: Module imports"""
    print("\n" + "="*70)
    print("TEST 1: Module Imports")
    print("="*70)
    try:
        from hlf_mcp.mcp_protocol_v2025 import (
            CANONICAL_PROTOCOL_VERSION,
            SUPPORTED_PROTOCOL_VERSIONS,
            MCPSession,
            MCPSessionStore,
            validate_protocol_version,
            build_mcp_response_headers,
            get_session_store,
        )
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
        
        # Test with explicit session ID
        session = MCPSession(session_id="test-session-001")
        
        assert session.session_id == "test-session-001", "Session ID not set correctly"
        assert isinstance(session.created_at, str), "Created timestamp should be ISO string"
        assert session.message_count == 0, "Message count should start at 0"
        assert session.initialize_called is False, "Initialize should not be called yet"
        
        print(f"✅ Session created: {session.session_id}")
        print(f"   Messages: {session.message_count}")
        print(f"   Initialize Called: {session.initialize_called}")
        
        # Test without explicit session ID (auto-generated)
        session2 = MCPSession()
        assert session2.session_id is not None, "Session ID should be auto-generated"
        assert len(session2.session_id) > 0, "Auto-generated session ID should not be empty"
        print(f"✅ Auto-generated session: {session2.session_id}")
        
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
        
        session = MCPSession(session_id="test-ops-001")
        
        # Test message recording
        session.record_message()
        assert session.message_count == 1, f"Expected 1 message, got {session.message_count}"
        print(f"✅ Message recorded, count: {session.message_count}")
        
        session.record_message()
        assert session.message_count == 2, f"Expected 2 messages, got {session.message_count}"
        print(f"✅ Second message recorded, count: {session.message_count}")
        
        # Test initialize recording
        session.record_initialize()
        assert session.initialize_called is True, "Initialize should be marked as called"
        assert session.message_count == 3, f"Expected 3 messages after initialize, got {session.message_count}"
        print(f"✅ Initialize recorded, message count: {session.message_count}")
        
        # Test serialization
        session_dict = session.to_dict()
        assert "session_id" in session_dict, "session_id not in serialization"
        assert "created_at" in session_dict, "created_at not in serialization"
        assert "message_count" in session_dict, "message_count not in serialization"
        assert "initialize_called" in session_dict, "initialize_called not in serialization"
        print(f"✅ Session serialized successfully")
        
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
        from hlf_mcp.mcp_protocol_v2025 import MCPSessionStore
        
        store = MCPSessionStore()
        
        # Create sessions via store
        session1 = store.create_session()
        assert session1.session_id is not None, "Session 1 ID not created"
        print(f"✅ Session 1 created: {session1.session_id}")
        
        session2 = store.create_session()
        assert session2.session_id is not None, "Session 2 ID not created"
        print(f"✅ Session 2 created: {session2.session_id}")
        
        # Retrieve sessions
        retrieved1 = store.get_session(session1.session_id)
        assert retrieved1 is not None, "Session 1 not retrieved"
        assert retrieved1.session_id == session1.session_id, "Retrieved session 1 ID mismatch"
        print(f"✅ Session 1 retrieved: {retrieved1.session_id}")
        
        # Record message
        success = store.record_message(session1.session_id)
        assert success is True, "Failed to record message for session 1"
        print(f"✅ Message recorded for session 1")
        
        # Record initialize
        success = store.record_initialize(session2.session_id)
        assert success is True, "Failed to record initialize for session 2"
        print(f"✅ Initialize recorded for session 2")
        
        # List sessions
        all_sessions = store.list_sessions()
        assert len(all_sessions) >= 2, f"Expected at least 2 sessions, got {len(all_sessions)}"
        print(f"✅ Sessions listed: {len(all_sessions)} total")
        
        # Verify message counts
        sess1_data = store.get_session(session1.session_id).to_dict()
        assert sess1_data["message_count"] == 1, f"Session 1 should have 1 message, has {sess1_data['message_count']}"
        print(f"✅ Session 1 message count verified: {sess1_data['message_count']}")
        
        sess2_data = store.get_session(session2.session_id).to_dict()
        assert sess2_data["initialize_called"] is True, "Session 2 initialize not recorded"
        print(f"✅ Session 2 initialize flag verified: {sess2_data['initialize_called']}")
        
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
        
        # Valid canonical version
        is_valid, error = validate_protocol_version("2025-11-25")
        assert is_valid is True, f"2025-11-25 should be valid, error: {error}"
        assert error is None, f"No error expected for valid version, got: {error}"
        print(f"✅ Canonical version validates: 2025-11-25")
        
        # Valid fallback version
        is_valid, error = validate_protocol_version("2024-11-05")
        assert is_valid is True, f"2024-11-05 should be valid, error: {error}"
        assert error is None, f"No error expected for valid version, got: {error}"
        print(f"✅ Fallback version validates: 2024-11-05")
        
        # Invalid version
        is_valid, error = validate_protocol_version("1999-01-01")
        assert is_valid is False, "1999-01-01 should be invalid"
        assert error is not None, f"Error expected for invalid version, got: {error}"
        assert "Unsupported" in error, f"Error should mention 'Unsupported', got: {error}"
        print(f"✅ Invalid version rejected: 1999-01-01")
        print(f"   Error message: {error}")
        
        # No version header (backward compatibility)
        is_valid, error = validate_protocol_version(None)
        assert is_valid is True, "Missing header should be valid (backward compat)"
        assert error is None, f"No error expected for missing header, got: {error}"
        print(f"✅ Missing header accepted (backward compatible)")
        
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
        
        # Test with both session_id and protocol_version
        headers = build_mcp_response_headers(
            session_id="test-session-003",
            protocol_version="2025-11-25"
        )
        
        # Check required headers
        assert "MCP-Session-Id" in headers, "Missing session ID header"
        assert headers["MCP-Session-Id"] == "test-session-003", "Wrong session ID"
        print(f"✅ Session ID header: {headers['MCP-Session-Id']}")
        
        assert "MCP-Protocol-Version" in headers, "Missing protocol version header"
        assert headers["MCP-Protocol-Version"] == "2025-11-25", "Wrong protocol version"
        print(f"✅ Protocol version header: {headers['MCP-Protocol-Version']}")
        
        assert "Content-Type" in headers, "Missing Content-Type header"
        assert headers["Content-Type"] == "application/json", "Wrong Content-Type"
        print(f"✅ Content-Type header: {headers['Content-Type']}")
        
        # Test with default protocol version
        headers2 = build_mcp_response_headers(session_id="test-session-004")
        assert headers2["MCP-Protocol-Version"] == "2025-11-25", "Default protocol version should be canonical"
        print(f"✅ Default protocol version: {headers2['MCP-Protocol-Version']}")
        
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
