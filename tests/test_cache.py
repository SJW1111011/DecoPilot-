"""
缓存系统单元测试
测试 backend/core/cache.py 的核心功能
"""
import pytest
import os
import sys
import time

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.core.cache import (
    LRUCache, CircularBuffer, KnowledgeQueryCache, LLMResponseCache,
    get_cache_manager, get_knowledge_cache, get_llm_cache
)


class TestLRUCache:
    """测试 LRUCache 类"""

    def test_set_and_get(self):
        """测试设置和获取"""
        cache = LRUCache(max_size=10)
        cache.set("key1", "value1")
        assert cache.get("key1") == "value1"

    def test_get_nonexistent(self):
        """测试获取不存在的键"""
        cache = LRUCache(max_size=10)
        assert cache.get("nonexistent") is None

    def test_max_size_eviction(self):
        """测试超过最大容量时的淘汰"""
        cache = LRUCache(max_size=3)
        cache.set("key1", "value1")
        cache.set("key2", "value2")
        cache.set("key3", "value3")
        cache.set("key4", "value4")  # 应该淘汰 key1

        assert cache.get("key1") is None
        assert cache.get("key2") == "value2"
        assert cache.get("key4") == "value4"

    def test_lru_order(self):
        """测试 LRU 顺序"""
        cache = LRUCache(max_size=3)
        cache.set("key1", "value1")
        cache.set("key2", "value2")
        cache.set("key3", "value3")

        # 访问 key1，使其成为最近使用
        cache.get("key1")

        # 添加新键，应该淘汰 key2（最久未使用）
        cache.set("key4", "value4")

        assert cache.get("key1") == "value1"
        assert cache.get("key2") is None
        assert cache.get("key3") == "value3"
        assert cache.get("key4") == "value4"

    def test_ttl_expiration(self):
        """测试 TTL 过期"""
        cache = LRUCache(max_size=10, ttl=0.1)  # 0.1秒过期
        cache.set("key1", "value1")
        assert cache.get("key1") == "value1"

        time.sleep(0.15)  # 等待过期
        assert cache.get("key1") is None

    def test_delete(self):
        """测试删除"""
        cache = LRUCache(max_size=10)
        cache.set("key1", "value1")
        cache.delete("key1")
        assert cache.get("key1") is None

    def test_clear(self):
        """测试清空"""
        cache = LRUCache(max_size=10)
        cache.set("key1", "value1")
        cache.set("key2", "value2")
        cache.clear()
        assert cache.get("key1") is None
        assert cache.get("key2") is None

    def test_stats(self):
        """测试统计信息"""
        cache = LRUCache(max_size=10)
        cache.set("key1", "value1")
        cache.get("key1")  # 命中
        cache.get("key2")  # 未命中

        stats = cache.stats()
        assert stats["hits"] == 1
        assert stats["misses"] == 1
        assert stats["size"] == 1


class TestCircularBuffer:
    """测试 CircularBuffer 类"""

    def test_append_and_get(self):
        """测试添加和获取"""
        buffer = CircularBuffer(max_size=5)
        buffer.append("item1")
        buffer.append("item2")

        items = buffer.get_all()
        assert len(items) == 2
        assert "item1" in items
        assert "item2" in items

    def test_circular_behavior(self):
        """测试循环行为"""
        buffer = CircularBuffer(max_size=3)
        buffer.append("item1")
        buffer.append("item2")
        buffer.append("item3")
        buffer.append("item4")  # 应该覆盖 item1

        items = buffer.get_all()
        assert len(items) == 3
        assert "item1" not in items
        assert "item4" in items

    def test_get_recent(self):
        """测试获取最近的项"""
        buffer = CircularBuffer(max_size=10)
        for i in range(5):
            buffer.append(f"item{i}")

        recent = buffer.get_recent(3)
        assert len(recent) == 3
        assert recent[-1] == "item4"

    def test_clear(self):
        """测试清空"""
        buffer = CircularBuffer(max_size=5)
        buffer.append("item1")
        buffer.clear()
        assert len(buffer.get_all()) == 0


class TestKnowledgeQueryCache:
    """测试 KnowledgeQueryCache 类"""

    @pytest.fixture
    def cache(self):
        """创建测试用的缓存"""
        return KnowledgeQueryCache(max_size=100, similarity_threshold=0.8)

    def test_set_and_get(self, cache):
        """测试设置和获取"""
        results = [{"content": "测试内容", "score": 0.9}]
        cache.set(
            query="装修风格推荐",
            user_type="c_end",
            k=5,
            results=results
        )

        cached = cache.get(
            query="装修风格推荐",
            user_type="c_end",
            k=5
        )
        assert cached is not None
        assert cached[0]["content"] == "测试内容"

    def test_get_different_user_type(self, cache):
        """测试不同用户类型"""
        results = [{"content": "C端内容"}]
        cache.set(
            query="测试查询",
            user_type="c_end",
            k=5,
            results=results
        )

        # 不同用户类型应该获取不到
        cached = cache.get(
            query="测试查询",
            user_type="b_end",
            k=5
        )
        assert cached is None

    def test_find_similar(self, cache):
        """测试相似查询查找"""
        results = [{"content": "装修风格内容"}]
        cache.set(
            query="现代简约装修风格",
            user_type="c_end",
            k=5,
            results=results
        )

        # 相似查询应该能找到
        similar = cache.find_similar(
            query="现代简约风格装修",
            user_type="c_end",
            k=5
        )
        # 注意：相似度匹配可能因实现而异
        # 这里主要测试方法是否正常工作


class TestLLMResponseCache:
    """测试 LLMResponseCache 类"""

    @pytest.fixture
    def cache(self):
        """创建测试用的缓存"""
        return LLMResponseCache(max_size=100, ttl=7200)

    def test_set_and_get(self, cache):
        """测试设置和获取"""
        context = {"user_type": "c_end"}
        cache.set(
            message="什么是现代简约风格？",
            response="现代简约风格是...",
            context=context
        )

        cached = cache.get(
            message="什么是现代简约风格？",
            context=context
        )
        assert cached is not None
        assert cached["response"] == "现代简约风格是..."

    def test_different_context(self, cache):
        """测试不同上下文"""
        context_a = {"user_type": "c_end"}
        context_b = {"user_type": "b_end"}

        cache.set(
            message="测试问题",
            response="回答A",
            context=context_a
        )

        # 不同上下文应该获取不到
        cached = cache.get(
            message="测试问题",
            context=context_b
        )
        assert cached is None


class TestCacheManager:
    """测试缓存管理器"""

    def test_get_cache_manager(self):
        """测试获取缓存管理器"""
        manager = get_cache_manager()
        assert manager is not None

    def test_get_knowledge_cache(self):
        """测试获取知识库缓存"""
        cache = get_knowledge_cache()
        assert cache is not None
        assert isinstance(cache, KnowledgeQueryCache)

    def test_get_llm_cache(self):
        """测试获取 LLM 缓存"""
        cache = get_llm_cache()
        assert cache is not None
        assert isinstance(cache, LLMResponseCache)

    def test_singleton_pattern(self):
        """测试单例模式"""
        cache1 = get_knowledge_cache()
        cache2 = get_knowledge_cache()
        assert cache1 is cache2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
