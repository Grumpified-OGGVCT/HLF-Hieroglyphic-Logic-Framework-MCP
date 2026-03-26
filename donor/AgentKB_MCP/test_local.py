#!/usr/bin/env python3
"""
Local test script - works without database/Redis.

Tests KB parsing, validation, and sanitizer.
Optionally tests Gemini if API key is provided.
"""

import sys
from pathlib import Path

# Add app to path
sys.path.insert(0, str(Path(__file__).parent))


def test_kb_parsing():
    """Test KB file parsing."""
    print("\n" + "="*60)
    print("Testing KB Parser")
    print("="*60)
    
    from app.services.kb_parser import KBParser
    
    parser = KBParser()
    
    # Parse all KB files
    entries = parser.parse_all()
    
    print(f"\n[OK] Found {len(entries)} KB entries")
    
    for entry in entries:
        is_valid, errors = parser.validate_entry(entry)
        status = "[OK]" if is_valid else "[FAIL]"
        print(f"  {status} {entry.id}")
        if errors:
            for e in errors:
                print(f"      - {e}")
    
    # Get stats
    stats = parser.get_stats()
    print(f"\nStats:")
    print(f"  Domains: {stats['domains']}")
    print(f"  Avg Confidence: {stats['avg_confidence']:.2f}")
    print(f"  By Domain: {stats['entries_by_domain']}")
    
    return True


def test_sanitizer():
    """Test PII/secrets detection."""
    print("\n" + "="*60)
    print("Testing PII Sanitizer")
    print("="*60)
    
    from app.services.sanitizer import PIISanitizer
    
    sanitizer = PIISanitizer()
    
    test_cases = [
        ("What is PostgreSQL?", False),
        ("How do I create an index?", False),
        ("api_key=sk_live_abc123def456ghi789", True),
        ("Connect to 192.168.1.100", True),
        ("password=MySecret123", True),
    ]
    
    all_passed = True
    for text, expected_sensitive in test_cases:
        is_sensitive = sanitizer.contains_sensitive(text)
        status = "[OK]" if is_sensitive == expected_sensitive else "[FAIL]"
        if is_sensitive != expected_sensitive:
            all_passed = False
        print(f"  {status} '{text[:40]}' - Sensitive: {is_sensitive}")
    
    return all_passed


def test_retrieval_local():
    """Test local retrieval (no API needed)."""
    print("\n" + "="*60)
    print("Testing Local Retrieval (no API)")
    print("="*60)
    
    from app.services.kb_parser import KBParser
    
    parser = KBParser()
    
    # Test finding entries by keyword
    test_queries = [
        "max_connections",
        "create index",
        "async await",
        "JSONB",
    ]
    
    for query in test_queries:
        print(f"\n  Query: '{query}'")
        
        # Simple keyword search
        entries = parser.parse_all()
        matches = []
        
        for entry in entries:
            if query.lower() in entry.question.lower() or query.lower() in entry.answer.lower():
                matches.append(entry)
        
        if matches:
            print(f"  [OK] Found {len(matches)} match(es):")
            for m in matches[:2]:
                print(f"      - {m.id}: {m.question[:50]}...")
        else:
            print(f"  [MISS] No matches found")
    
    return True


def test_gemini(api_key: str = None):
    """Test Gemini connection (requires API key)."""
    print("\n" + "="*60)
    print("Testing Gemini Connection")
    print("="*60)
    
    if not api_key:
        import os
        api_key = os.environ.get("GOOGLE_API_KEY")
    
    if not api_key:
        print("  [SKIP] GOOGLE_API_KEY not set - skipping Gemini test")
        print("    Set it with: $env:GOOGLE_API_KEY='your-key'")
        return None
    
    try:
        import google.generativeai as genai
        
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-1.5-flash')
        
        # Simple test
        response = model.generate_content("Say 'Hello from Gemini' and nothing else.")
        
        if response.text:
            print(f"  [OK] Gemini responded: {response.text.strip()}")
            return True
        else:
            print(f"  [FAIL] Empty response from Gemini")
            return False
            
    except Exception as e:
        print(f"  [FAIL] Gemini error: {e}")
        return False


def main():
    print("\n" + "#"*60)
    print("# Verified Developer KB Pro - Local Test Suite")
    print("#"*60)
    
    results = {}
    
    # Test KB parsing
    try:
        results["KB Parsing"] = test_kb_parsing()
    except Exception as e:
        print(f"\n[FAIL] KB Parsing failed: {e}")
        results["KB Parsing"] = False
    
    # Test sanitizer
    try:
        results["Sanitizer"] = test_sanitizer()
    except Exception as e:
        print(f"\n[FAIL] Sanitizer failed: {e}")
        results["Sanitizer"] = False
    
    # Test local retrieval
    try:
        results["Local Retrieval"] = test_retrieval_local()
    except Exception as e:
        print(f"\n[FAIL] Local Retrieval failed: {e}")
        results["Local Retrieval"] = False
    
    # Test Gemini (optional)
    try:
        gemini_result = test_gemini()
        if gemini_result is not None:
            results["Gemini"] = gemini_result
    except Exception as e:
        print(f"\n[FAIL] Gemini test failed: {e}")
    
    # Summary
    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    
    for test_name, passed in results.items():
        status = "[PASS]" if passed else "[FAIL]"
        print(f"  {status}: {test_name}")
    
    all_passed = all(results.values())
    
    if all_passed:
        print("\n[SUCCESS] All tests passed!")
    else:
        print("\n[WARNING] Some tests failed")
    
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())

