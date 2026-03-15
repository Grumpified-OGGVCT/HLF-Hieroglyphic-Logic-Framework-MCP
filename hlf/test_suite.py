#!/usr/bin/env python3
"""
HLF Test Suite

Comprehensive tests for:
- Profile management
- SQLite hot store
- Infinite RAG
- Self-observation (meta-intents)
"""

import os
import sys
import time
import json
import unittest
import tempfile
import shutil
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from hlf import ProfileManager, switch_profile
from hlf.sqlite_hot_store import SQLiteHotStore, HybridHotStore, LRUCache
from hlf.infinite_rag_hlf import InfiniteRAGHLF, Fact


class TestLRUCache(unittest.TestCase):
    """Test LRU Cache implementation"""
    
    def setUp(self):
        self.cache = LRUCache(maxsize=10)
    
    def test_basic_operations(self):
        """Test basic get/set operations"""
        self.cache.set("key1", "value1")
        self.assertEqual(self.cache.get("key1"), "value1")
        self.assertIsNone(self.cache.get("nonexistent"))
    
    def test_lru_eviction(self):
        """Test LRU eviction policy"""
        # Fill cache
        for i in range(15):
            self.cache.set(f"key{i}", f"value{i}")
        
        # Oldest items should be evicted
        self.assertIsNone(self.cache.get("key0"))
        self.assertIsNone(self.cache.get("key1"))
        self.assertIsNone(self.cache.get("key2"))
        self.assertIsNone(self.cache.get("key3"))
        self.assertIsNone(self.cache.get("key4"))
        
        # Newest items should remain
        self.assertEqual(self.cache.get("key14"), "value14")
    
    def test_ttl_expiration(self):
        """Test TTL expiration"""
        self.cache.set("key1", "value1", ttl=0.01)  # 10ms TTL
        self.assertEqual(self.cache.get("key1"), "value1")
        
        time.sleep(0.02)  # Wait for expiration
        self.assertIsNone(self.cache.get("key1"))
    
    def test_stats(self):
        """Test cache statistics"""
        self.cache.set("key1", "value1")
        self.cache.get("key1")
        self.cache.get("key1")
        self.cache.get("nonexistent")
        
        stats = self.cache.get_stats()
        self.assertEqual(stats["size"], 1)
        self.assertEqual(stats["hits"], 2)
        self.assertEqual(stats["misses"], 1)


class TestSQLiteHotStore(unittest.TestCase):
    """Test SQLite hot store implementation"""
    
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "test.db")
        self.store = SQLiteHotStore(db_path=self.db_path)
    
    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_meta_intent_operations(self):
        """Test meta-intent storage and retrieval"""
        meta_intent = {
            "source_hash": "abc123",
            "timestamp": time.time(),
            "phase_timings": {"parse": 0.001, "compile": 0.002},
            "warnings": [],
            "errors": [],
            "gas_used": 100,
            "profile": "P0"
        }
        
        self.store.add_meta_intent(meta_intent)
        
        # Retrieve
        intents = self.store.get_recent_meta_intents(since=0, limit=10)
        self.assertEqual(len(intents), 1)
        self.assertEqual(intents[0]["source_hash"], "abc123")
    
    def test_ttl_cleanup(self):
        """Test automatic TTL cleanup"""
        meta_intent = {
            "source_hash": "abc123",
            "timestamp": time.time() - 86400,  # 1 day old
            "phase_timings": {},
            "warnings": [],
            "errors": [],
            "gas_used": 0,
            "profile": "P0"
        }
        
        self.store.add_meta_intent(meta_intent)
        
        # Before cleanup
        intents = self.store.get_recent_meta_intents(since=0, limit=10)
        self.assertEqual(len(intents), 1)
        
        # Cleanup with 1 hour max age
        self.store.cleanup_expired(max_age_hours=1)
        
        # After cleanup
        intents = self.store.get_recent_meta_intents(since=0, limit=10)
        self.assertEqual(len(intents), 0)


class TestHybridHotStore(unittest.TestCase):
    """Test hybrid hot store (LRU + SQLite)"""
    
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "test.db")
        self.store = HybridHotStore(db_path=self.db_path, cache_size=10)
    
    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_tiered_storage(self):
        """Test data flows through LRU and SQLite tiers"""
        meta_intent = {
            "source_hash": "abc123",
            "timestamp": time.time(),
            "phase_timings": {"parse": 0.001},
            "warnings": [],
            "errors": [],
            "gas_used": 100,
            "profile": "P1"
        }
        
        self.store.add_meta_intent(meta_intent)
        
        # Should be in both tiers
        intents = self.store.get_recent_meta_intents(since=0, limit=10)
        self.assertEqual(len(intents), 1)
        
        # Stats should show both tiers
        stats = self.store.get_stats()
        self.assertIn("lru", stats)
        self.assertIn("sqlite", stats)


class TestInfiniteRAG(unittest.TestCase):
    """Test Infinite RAG implementation"""
    
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "hlf_rag.db")
    
    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_fact_lifecycle(self):
        """Test complete fact lifecycle"""
        rag = InfiniteRAGHLF(db_path=self.db_path, profile="P0")
        
        # Create
        fact = Fact(
            id="test_1",
            content="HLF test fact",
            source="test_suite"
        )
        fact_id = rag.add_fact(fact)
        self.assertEqual(fact_id, "test_1")
        
        # Retrieve
        retrieved = rag.get_fact(fact_id)
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.content, "HLF test fact")
        self.assertEqual(retrieved.access_count, 1)  # Count incremented
        
        # Search
        results = rag.search_facts("HLF")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].content, "HLF test fact")
    
    def test_meta_intent_self_observation(self):
        """Test self-observation through meta-intents"""
        rag = InfiniteRAGHLF(db_path=self.db_path, profile="P0")
        
        meta_intent = {
            "source_hash": "abc123",
            "timestamp": 1234567890.0,
            "phase_timings": {"parse": 0.001, "compile": 0.002},
            "warnings": ["Deprecation warning"],
            "errors": [],
            "gas_used": 100,
            "profile": "P0"
        }
        
        intent_id = rag.add_meta_intent(meta_intent)
        self.assertGreater(intent_id, 0)
        
        # Retrieve
        intents = rag.get_recent_meta_intents(since=1234567880.0, limit=10)
        self.assertEqual(len(intents), 1)
        self.assertEqual(intents[0]["source_hash"], "abc123")
        self.assertEqual(intents[0]["gas_used"], 100)
    
    def test_profile_switching(self):
        """Test RAG with different profiles"""
        for profile in ["P0", "P1"]:
            db_path = os.path.join(self.temp_dir, f"rag_{profile}.db")
            rag = InfiniteRAGHLF(db_path=db_path, profile=profile)
            
            # Add fact
            fact = Fact(id=f"fact_{profile}", content=f"Test for {profile}", source="test")
            rag.add_fact(fact)
            
            # Verify
            stats = rag.get_stats()
            self.assertEqual(stats["facts"], 1)
            self.assertEqual(stats["profile"], profile)
    
    def test_cleanup(self):
        """Test data cleanup"""
        rag = InfiniteRAGHLF(db_path=self.db_path, profile="P0")
        
        # Add old fact
        old_fact = Fact(
            id="old",
            content="Old fact",
            source="test",
            timestamp=time.time() - (31 * 86400)  # 31 days old
        )
        rag.add_fact(old_fact)
        
        # Add recent fact
        recent_fact = Fact(id="recent", content="Recent fact", source="test")
        rag.add_fact(recent_fact)
        
        # Cleanup 30 days
        removed = rag.cleanup(max_age_days=30)
        self.assertGreater(removed, 0)
        
        # Old fact should be gone
        self.assertIsNone(rag.get_fact("old"))
        # Recent fact should remain
        self.assertIsNotNone(rag.get_fact("recent"))


class TestProfileManager(unittest.TestCase):
    """Test profile management"""
    
    def test_auto_detection(self):
        """Test profile auto-detection"""
        # Save current env
        orig_profile = os.getenv("HLF_PROFILE")
        orig_api_key = os.getenv("OLLAMA_API_KEY")
        
        try:
            # Clear env
            if "HLF_PROFILE" in os.environ:
                del os.environ["HLF_PROFILE"]
            if "OLLAMA_API_KEY" in os.environ:
                del os.environ["OLLAMA_API_KEY"]
            
            # Should default to P0
            profile = ProfileManager()
            self.assertEqual(profile.current_profile, "P0")
            
            # With API key, still P0
            os.environ["OLLAMA_API_KEY"] = "test_key"
            profile = ProfileManager()
            self.assertEqual(profile.current_profile, "P0")
        finally:
            # Restore env
            if orig_profile:
                os.environ["HLF_PROFILE"] = orig_profile
            if orig_api_key:
                os.environ["OLLAMA_API_KEY"] = orig_api_key
    
    def test_profile_configs(self):
        """Test all profile configurations"""
        for name in ["P0", "P1", "P2"]:
            profile = ProfileManager(name)
            self.assertEqual(profile.current_profile, name)
            
            config = profile.config
            self.assertIsNotNone(config.description)
            self.assertIsNotNone(config.default_model)
            
            # P0 should have no Redis
            if name == "P0":
                self.assertFalse(config.use_redis)
                self.assertEqual(config.hot_tier, "sqlite")
                self.assertEqual(config.host_function_set, "minimal")
            
            # P1 should have LRU cache
            if name == "P1":
                self.assertTrue(config.use_lru_cache)
                self.assertEqual(config.hot_tier, "lru")
    
    def test_profile_switching(self):
        """Test profile switching"""
        profile = switch_profile("P1")
        self.assertEqual(profile.current_profile, "P1")
        self.assertEqual(os.getenv("HLF_PROFILE"), "P1")


class TestIntegration(unittest.TestCase):
    """Integration tests"""
    
    def test_full_workflow_p0(self):
        """Test complete P0 workflow"""
        temp_dir = tempfile.mkdtemp()
        
        try:
            # 1. Initialize profile
            profile = ProfileManager("P0")
            self.assertTrue(profile.is_p0())
            
            # 2. Create RAG
            db_path = os.path.join(temp_dir, "hlf_rag.db")
            rag = InfiniteRAGHLF(db_path=db_path, profile="P0")
            
            # 3. Store compiler observation
            meta_intent = {
                "source_hash": "compile_123",
                "timestamp": time.time(),
                "phase_timings": {"lex": 0.001, "parse": 0.002, "compile": 0.005},
                "warnings": ["Unused variable"],
                "errors": [],
                "gas_used": 42,
                "profile": "P0"
            }
            rag.add_meta_intent(meta_intent)
            
            # 4. Store knowledge
            fact = Fact(
                id="grammar_rule",
                content="HLF grammar requires semicolons",
                source="hlf_spec"
            )
            rag.add_fact(fact)
            
            # 5. Query and verify
            intents = rag.get_recent_meta_intents(since=0, limit=10)
            self.assertEqual(len(intents), 1)
            self.assertEqual(intents[0]["gas_used"], 42)
            
            facts = rag.search_facts("grammar")
            self.assertEqual(len(facts), 1)
            
            # 6. Get stats
            stats = rag.get_stats()
            self.assertEqual(stats["facts"], 1)
            self.assertEqual(stats["meta_intents"], 1)
            self.assertEqual(stats["profile"], "P0")
            
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)


def run_tests():
    """Run the full test suite"""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add all test classes
    suite.addTests(loader.loadTestsFromTestCase(TestLRUCache))
    suite.addTests(loader.loadTestsFromTestCase(TestSQLiteHotStore))
    suite.addTests(loader.loadTestsFromTestCase(TestHybridHotStore))
    suite.addTests(loader.loadTestsFromTestCase(TestInfiniteRAG))
    suite.addTests(loader.loadTestsFromTestCase(TestProfileManager))
    suite.addTests(loader.loadTestsFromTestCase(TestIntegration))
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(run_tests())
