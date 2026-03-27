#!/usr/bin/env python3
"""
OpenRouter Integration Test

Tests the OpenRouter client and LLM router functionality.
Requires OPENROUTER_API_KEY environment variable.
"""

import asyncio
import os
import sys
from pathlib import Path

# Add app to path
sys.path.insert(0, str(Path(__file__).parent))


async def test_openrouter_client():
    """Test direct OpenRouter client."""
    print("\n" + "="*60)
    print("Testing OpenRouter Client")
    print("="*60)
    
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        print("  [SKIP] OPENROUTER_API_KEY not set")
        print("    Set it with: $env:OPENROUTER_API_KEY='sk-or-v1-...'")
        return None
    
    from app.services.openrouter import (
        OpenRouterClient,
        ProviderPreferences,
        RoutingStrategy,
        DataPolicy,
    )
    
    client = OpenRouterClient(api_key=api_key)
    
    try:
        # Test 1: Simple completion
        print("\n  Test 1: Simple completion")
        response = await client.chat_completion(
            messages=[{"role": "user", "content": "Say 'Hello from OpenRouter' and nothing else."}],
            model="meta-llama/llama-3.1-8b-instruct:free",  # Free model for testing
            temperature=0.0,
            max_tokens=50,
        )
        
        print(f"    Model: {response.model}")
        print(f"    Content: {response.content[:100]}...")
        print(f"    Finish reason: {response.finish_reason}")
        print(f"    Tokens: {response.usage.total_tokens}")
        print("    [OK] Simple completion works")
        
        # Test 2: With provider preferences
        print("\n  Test 2: Provider preferences (price routing)")
        provider = ProviderPreferences(
            sort=RoutingStrategy.PRICE,
            data_collection=DataPolicy.DENY,
        )
        
        response = await client.chat_completion(
            messages=[{"role": "user", "content": "What is 2+2? Answer with just the number."}],
            model="meta-llama/llama-3.1-8b-instruct:floor",
            provider=provider,
        )
        
        print(f"    Model: {response.model}")
        print(f"    Content: {response.content.strip()}")
        print("    [OK] Provider preferences work")
        
        # Test 3: Cheap query convenience method
        print("\n  Test 3: Cheap query convenience method")
        response = await client.cheap_query("What is Python? One sentence only.")
        
        print(f"    Model: {response.model}")
        print(f"    Content: {response.content[:100]}...")
        print("    [OK] Cheap query works")
        
        await client.close()
        return True
        
    except Exception as e:
        print(f"    [FAIL] Error: {e}")
        await client.close()
        return False


async def test_llm_router():
    """Test LLM router with different strategies."""
    print("\n" + "="*60)
    print("Testing LLM Router")
    print("="*60)
    
    google_key = os.environ.get("GOOGLE_API_KEY")
    openrouter_key = os.environ.get("OPENROUTER_API_KEY")
    
    if not google_key and not openrouter_key:
        print("  [SKIP] No LLM API keys set")
        print("    Set GOOGLE_API_KEY or OPENROUTER_API_KEY")
        return None
    
    from app.services.llm_router import LLMRouter, LLMRoutingStrategy
    
    # Test available strategies
    strategies_to_test = []
    
    if google_key:
        strategies_to_test.append(("PRIMARY_ONLY (Gemini)", LLMRoutingStrategy.PRIMARY_ONLY))
    
    if openrouter_key:
        strategies_to_test.append(("OPENROUTER_ONLY", LLMRoutingStrategy.OPENROUTER_ONLY))
        strategies_to_test.append(("COST_OPTIMIZED", LLMRoutingStrategy.COST_OPTIMIZED))
    
    if google_key and openrouter_key:
        strategies_to_test.append(("FALLBACK", LLMRoutingStrategy.FALLBACK))
    
    all_passed = True
    
    for name, strategy in strategies_to_test:
        print(f"\n  Test: {name}")
        
        try:
            router = LLMRouter(strategy=strategy)
            
            response = await router.route(
                messages=[{"role": "user", "content": "What is 1+1? Answer with just the number."}],
                temperature=0.0,
                max_tokens=10,
            )
            
            print(f"    Provider: {response.provider}")
            print(f"    Model: {response.model}")
            print(f"    Content: {response.content.strip()}")
            print(f"    Tokens: {response.total_tokens}")
            if response.cost_estimate:
                print(f"    Est. Cost: ${response.cost_estimate:.6f}")
            print(f"    [OK] {name} works")
            
        except Exception as e:
            print(f"    [FAIL] {name} error: {e}")
            all_passed = False
    
    return all_passed


async def test_model_listing():
    """Test listing available models."""
    print("\n" + "="*60)
    print("Testing Model Listing")
    print("="*60)
    
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        print("  [SKIP] OPENROUTER_API_KEY not set")
        return None
    
    from app.services.openrouter import OpenRouterClient
    
    client = OpenRouterClient(api_key=api_key)
    
    try:
        models = await client.list_models()
        
        print(f"\n  Total models available: {len(models)}")
        print("\n  Sample models (first 10):")
        
        for model in models[:10]:
            model_id = model.get("id", "unknown")
            context = model.get("context_length", "?")
            pricing = model.get("pricing", {})
            prompt_price = float(pricing.get("prompt", 0)) * 1_000_000
            completion_price = float(pricing.get("completion", 0)) * 1_000_000
            
            print(f"    - {model_id}")
            print(f"      Context: {context}, Price: ${prompt_price:.2f}/${completion_price:.2f} per M tokens")
        
        print(f"\n  [OK] Listed {len(models)} models")
        
        await client.close()
        return True
        
    except Exception as e:
        print(f"  [FAIL] Error: {e}")
        await client.close()
        return False


async def main():
    print("\n" + "#"*60)
    print("# OpenRouter Integration Test Suite")
    print("#"*60)
    
    results = {}
    
    # Test OpenRouter client
    try:
        result = await test_openrouter_client()
        if result is not None:
            results["OpenRouter Client"] = result
    except Exception as e:
        print(f"\n[FAIL] OpenRouter Client crashed: {e}")
        results["OpenRouter Client"] = False
    
    # Test LLM router
    try:
        result = await test_llm_router()
        if result is not None:
            results["LLM Router"] = result
    except Exception as e:
        print(f"\n[FAIL] LLM Router crashed: {e}")
        results["LLM Router"] = False
    
    # Test model listing
    try:
        result = await test_model_listing()
        if result is not None:
            results["Model Listing"] = result
    except Exception as e:
        print(f"\n[FAIL] Model Listing crashed: {e}")
        results["Model Listing"] = False
    
    # Summary
    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    
    if not results:
        print("  No tests ran (no API keys set)")
        print("\n  To run tests, set environment variables:")
        print("    $env:OPENROUTER_API_KEY='sk-or-v1-...'")
        print("    $env:GOOGLE_API_KEY='...'")
        return 0
    
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
    sys.exit(asyncio.run(main()))

