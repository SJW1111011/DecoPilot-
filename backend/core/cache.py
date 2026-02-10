"""
通用缓存工具
提供 LRU 缓存、TTL 缓存等实现
"""
import time
import threading
import math
from typing import Any, Dict, Generic, Optional, TypeVar, Callable, List, Tuple
from collections import OrderedDict
from dataclasses import dataclass, field
from functools import wraps

K = TypeVar('K')
V = TypeVar('V')


@dataclass
class CacheEntry(Generic[V]):
    """缓存条目"""
    value: V
    created_at: float = field(default_factory=time.time)
    last_access: float = field(default_factory=time.time)
    access_count: int = 0


class LRUCache(Generic[K, V]):
    """
    线程安全的 LRU 缓存

    特性：
    - 固定容量，超出时淘汰最久未使用的条目
    - 支持 TTL（可选）
    - 线程安全
    """

    def __init__(self, max_size: int = 1000, ttl: Optional[float] = None):
        """
        初始化 LRU 缓存

        Args:
            max_size: 最大容量
            ttl: 条目存活时间（秒），None 表示永不过期
        """
        self.max_size = max_size
        self.ttl = ttl
        self._cache: OrderedDict[K, CacheEntry[V]] = OrderedDict()
        self._lock = threading.RLock()

        # 统计信息
        self._hits = 0
        self._misses = 0

    def get(self, key: K, default: V = None) -> Optional[V]:
        """获取缓存值"""
        with self._lock:
            if key not in self._cache:
                self._misses += 1
                return default

            entry = self._cache[key]

            # 检查 TTL
            if self.ttl and (time.time() - entry.created_at) > self.ttl:
                del self._cache[key]
                self._misses += 1
                return default

            # 更新访问信息
            entry.last_access = time.time()
            entry.access_count += 1

            # 移动到末尾（最近使用）
            self._cache.move_to_end(key)

            self._hits += 1
            return entry.value

    def set(self, key: K, value: V) -> None:
        """设置缓存值"""
        with self._lock:
            if key in self._cache:
                # 更新现有条目
                self._cache[key].value = value
                self._cache[key].last_access = time.time()
                self._cache.move_to_end(key)
            else:
                # 检查容量
                while len(self._cache) >= self.max_size:
                    self._cache.popitem(last=False)  # 删除最旧的

                # 添加新条目
                self._cache[key] = CacheEntry(value=value)

    def delete(self, key: K) -> bool:
        """删除缓存条目"""
        with self._lock:
            if key in self._cache:
                del self._cache[key]
                return True
            return False

    def clear(self) -> None:
        """清空缓存"""
        with self._lock:
            self._cache.clear()
            self._hits = 0
            self._misses = 0

    def contains(self, key: K) -> bool:
        """检查键是否存在"""
        with self._lock:
            if key not in self._cache:
                return False

            # 检查 TTL
            if self.ttl:
                entry = self._cache[key]
                if (time.time() - entry.created_at) > self.ttl:
                    del self._cache[key]
                    return False

            return True

    def size(self) -> int:
        """获取当前大小"""
        return len(self._cache)

    def stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        total = self._hits + self._misses
        return {
            "size": len(self._cache),
            "max_size": self.max_size,
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": self._hits / total if total > 0 else 0,
        }

    def cleanup_expired(self) -> int:
        """清理过期条目"""
        if not self.ttl:
            return 0

        with self._lock:
            now = time.time()
            expired_keys = [
                k for k, v in self._cache.items()
                if (now - v.created_at) > self.ttl
            ]
            for key in expired_keys:
                del self._cache[key]
            return len(expired_keys)

    def __contains__(self, key: K) -> bool:
        return self.contains(key)

    def __len__(self) -> int:
        return self.size()


class CircularBuffer(Generic[V]):
    """
    循环缓冲区

    用于存储固定数量的历史记录，超出时自动覆盖最旧的
    """

    def __init__(self, max_size: int = 1000):
        self.max_size = max_size
        self._buffer: list = []
        self._lock = threading.Lock()

    def append(self, item: V) -> None:
        """添加条目"""
        with self._lock:
            if len(self._buffer) >= self.max_size:
                self._buffer.pop(0)
            self._buffer.append(item)

    def get_all(self) -> list:
        """获取所有条目"""
        with self._lock:
            return list(self._buffer)

    def get_recent(self, n: int) -> list:
        """获取最近 n 条"""
        with self._lock:
            return list(self._buffer[-n:])

    def clear(self) -> None:
        """清空"""
        with self._lock:
            self._buffer.clear()

    def size(self) -> int:
        """获取当前大小"""
        return len(self._buffer)

    def __len__(self) -> int:
        return self.size()


def lru_cache_method(max_size: int = 128, ttl: Optional[float] = None):
    """
    方法级 LRU 缓存装饰器

    用于缓存实例方法的返回值
    """
    def decorator(func: Callable) -> Callable:
        cache_attr = f"_cache_{func.__name__}"

        @wraps(func)
        def wrapper(self, *args, **kwargs):
            # 获取或创建缓存
            if not hasattr(self, cache_attr):
                setattr(self, cache_attr, LRUCache(max_size=max_size, ttl=ttl))

            cache: LRUCache = getattr(self, cache_attr)

            # 生成缓存键
            key = (args, tuple(sorted(kwargs.items())))

            # 尝试从缓存获取
            result = cache.get(key)
            if result is not None:
                return result

            # 执行函数并缓存结果
            result = func(self, *args, **kwargs)
            if result is not None:
                cache.set(key, result)

            return result

        return wrapper
    return decorator


class CacheManager:
    """
    缓存管理器

    统一管理所有缓存实例，提供监控和清理功能
    """

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._caches: Dict[str, LRUCache] = {}
        return cls._instance

    def register(self, name: str, cache: LRUCache) -> None:
        """注册缓存"""
        self._caches[name] = cache

    def unregister(self, name: str) -> None:
        """注销缓存"""
        if name in self._caches:
            del self._caches[name]

    def get_cache(self, name: str) -> Optional[LRUCache]:
        """获取缓存"""
        return self._caches.get(name)

    def get_all_stats(self) -> Dict[str, Dict]:
        """获取所有缓存统计"""
        return {name: cache.stats() for name, cache in self._caches.items()}

    def cleanup_all(self) -> Dict[str, int]:
        """清理所有过期条目"""
        return {name: cache.cleanup_expired() for name, cache in self._caches.items()}

    def clear_all(self) -> None:
        """清空所有缓存"""
        for cache in self._caches.values():
            cache.clear()


def get_cache_manager() -> CacheManager:
    """获取缓存管理器单例"""
    return CacheManager()


# === 专用缓存类 ===

class KnowledgeQueryCache:
    """
    知识库查询缓存

    缓存知识库检索结果，支持相似查询匹配
    使用优化的相似度搜索算法
    """

    def __init__(self, max_size: int = 500, ttl: float = 3600,
                 similarity_threshold: float = 0.7):
        """
        初始化知识库查询缓存

        Args:
            max_size: 最大缓存条目数
            ttl: 缓存过期时间（秒），默认1小时
            similarity_threshold: 相似度阈值，默认0.7
        """
        self._cache = LRUCache[str, dict](max_size=max_size, ttl=ttl)
        self._query_vectors: Dict[str, Dict] = {}  # 缓存键到查询向量的映射
        self._keyword_index: Dict[str, set] = {}  # 关键词到缓存键的倒排索引
        self._lock = threading.RLock()
        self.similarity_threshold = similarity_threshold

        # 注册到缓存管理器
        get_cache_manager().register("knowledge_query", self._cache)

    def _normalize_query(self, query: str) -> str:
        """标准化查询字符串"""
        return query.strip().lower()

    def _extract_keywords(self, query: str) -> List[str]:
        """提取查询关键词"""
        import re
        words = re.findall(r'[\u4e00-\u9fa5]+|[a-zA-Z]+', query)
        return [w for w in words if len(w) >= 2]

    def _compute_tf_vector(self, keywords: List[str]) -> Dict[str, float]:
        """计算词频向量"""
        tf = {}
        for word in keywords:
            tf[word] = tf.get(word, 0) + 1
        # 归一化
        total = sum(tf.values())
        if total > 0:
            for word in tf:
                tf[word] /= total
        return tf

    def _cosine_similarity(self, vec1: Dict[str, float], vec2: Dict[str, float]) -> float:
        """计算余弦相似度"""
        if not vec1 or not vec2:
            return 0.0

        # 计算点积
        dot_product = sum(vec1.get(k, 0) * vec2.get(k, 0) for k in set(vec1) | set(vec2))

        # 计算模长
        norm1 = math.sqrt(sum(v * v for v in vec1.values()))
        norm2 = math.sqrt(sum(v * v for v in vec2.values()))

        if norm1 == 0 or norm2 == 0:
            return 0.0

        return dot_product / (norm1 * norm2)

    def _jaccard_similarity(self, set1: set, set2: set) -> float:
        """计算 Jaccard 相似度"""
        if not set1 or not set2:
            return 0.0
        intersection = len(set1 & set2)
        union = len(set1 | set2)
        return intersection / union if union > 0 else 0.0

    def _generate_cache_key(self, query: str, user_type: str, k: int) -> str:
        """生成缓存键"""
        import hashlib
        normalized = self._normalize_query(query)
        key_str = f"{normalized}:{user_type}:{k}"
        return hashlib.md5(key_str.encode()).hexdigest()

    def get(self, query: str, user_type: str, k: int = 5) -> Optional[list]:
        """
        获取缓存的查询结果

        Args:
            query: 查询文本
            user_type: 用户类型
            k: 返回结果数量

        Returns:
            缓存的结果列表，未命中返回 None
        """
        cache_key = self._generate_cache_key(query, user_type, k)
        entry = self._cache.get(cache_key)
        return entry["results"] if entry else None

    def set(self, query: str, user_type: str, k: int, results: list) -> None:
        """
        缓存查询结果

        Args:
            query: 查询文本
            user_type: 用户类型
            k: 返回结果数量
            results: 查询结果
        """
        cache_key = self._generate_cache_key(query, user_type, k)
        keywords = self._extract_keywords(query)
        tf_vector = self._compute_tf_vector(keywords)

        # 存储缓存条目
        entry = {
            "query": query,
            "user_type": user_type,
            "k": k,
            "results": results,
            "keywords": set(keywords),
            "tf_vector": tf_vector,
        }
        self._cache.set(cache_key, entry)

        # 更新索引
        with self._lock:
            self._query_vectors[cache_key] = {
                "keywords": set(keywords),
                "tf_vector": tf_vector,
                "user_type": user_type,
                "k": k,
            }
            # 更新关键词倒排索引
            for kw in keywords:
                if kw not in self._keyword_index:
                    self._keyword_index[kw] = set()
                self._keyword_index[kw].add(cache_key)

    def find_similar(self, query: str, user_type: str, k: int = 5,
                     similarity_threshold: float = None) -> Optional[list]:
        """
        查找相似查询的缓存结果（优化版）

        使用两阶段搜索：
        1. 通过关键词倒排索引快速筛选候选
        2. 对候选计算精确相似度

        Args:
            query: 查询文本
            user_type: 用户类型
            k: 返回结果数量
            similarity_threshold: 相似度阈值（可选，默认使用实例阈值）

        Returns:
            相似查询的缓存结果，未找到返回 None
        """
        threshold = similarity_threshold or self.similarity_threshold

        # 首先尝试精确匹配
        exact_result = self.get(query, user_type, k)
        if exact_result is not None:
            return exact_result

        # 提取查询特征
        keywords = self._extract_keywords(query)
        if not keywords:
            return None

        query_keywords_set = set(keywords)
        query_tf_vector = self._compute_tf_vector(keywords)

        with self._lock:
            # 阶段1：通过倒排索引快速筛选候选
            candidate_keys = set()
            for kw in keywords:
                if kw in self._keyword_index:
                    candidate_keys.update(self._keyword_index[kw])

            if not candidate_keys:
                return None

            # 阶段2：计算精确相似度
            best_match = None
            best_similarity = 0.0

            for cache_key in candidate_keys:
                if cache_key not in self._query_vectors:
                    continue

                cached_info = self._query_vectors[cache_key]

                # 检查用户类型和 k 值
                if cached_info["user_type"] != user_type:
                    continue
                if cached_info["k"] != k:
                    continue

                # 计算综合相似度（Jaccard + Cosine 加权平均）
                jaccard_sim = self._jaccard_similarity(
                    query_keywords_set,
                    cached_info["keywords"]
                )
                cosine_sim = self._cosine_similarity(
                    query_tf_vector,
                    cached_info["tf_vector"]
                )

                # 加权平均（Jaccard 权重 0.4，Cosine 权重 0.6）
                combined_sim = 0.4 * jaccard_sim + 0.6 * cosine_sim

                if combined_sim > best_similarity and combined_sim >= threshold:
                    best_similarity = combined_sim
                    best_match = cache_key

            # 返回最佳匹配
            if best_match:
                entry = self._cache.get(best_match)
                if entry:
                    return entry["results"]

        return None

    def find_top_similar(self, query: str, user_type: str, k: int = 5,
                         top_n: int = 3) -> List[Tuple[float, list]]:
        """
        查找最相似的 top_n 个缓存结果

        Args:
            query: 查询文本
            user_type: 用户类型
            k: 返回结果数量
            top_n: 返回的最相似结果数量

        Returns:
            [(相似度, 结果列表), ...] 按相似度降序排列
        """
        keywords = self._extract_keywords(query)
        if not keywords:
            return []

        query_keywords_set = set(keywords)
        query_tf_vector = self._compute_tf_vector(keywords)

        similarities = []

        with self._lock:
            # 通过倒排索引筛选候选
            candidate_keys = set()
            for kw in keywords:
                if kw in self._keyword_index:
                    candidate_keys.update(self._keyword_index[kw])

            for cache_key in candidate_keys:
                if cache_key not in self._query_vectors:
                    continue

                cached_info = self._query_vectors[cache_key]

                if cached_info["user_type"] != user_type:
                    continue
                if cached_info["k"] != k:
                    continue

                # 计算相似度
                jaccard_sim = self._jaccard_similarity(
                    query_keywords_set,
                    cached_info["keywords"]
                )
                cosine_sim = self._cosine_similarity(
                    query_tf_vector,
                    cached_info["tf_vector"]
                )
                combined_sim = 0.4 * jaccard_sim + 0.6 * cosine_sim

                entry = self._cache.get(cache_key)
                if entry:
                    similarities.append((combined_sim, entry["results"]))

        # 按相似度降序排列，返回 top_n
        similarities.sort(key=lambda x: x[0], reverse=True)
        return similarities[:top_n]

    def invalidate_by_collection(self, collection_name: str) -> int:
        """
        使指定集合的缓存失效

        Args:
            collection_name: 集合名称

        Returns:
            失效的缓存条目数
        """
        count = self._cache.size()
        self._cache.clear()
        with self._lock:
            self._query_vectors.clear()
            self._keyword_index.clear()
        return count

    def stats(self) -> Dict[str, Any]:
        """获取缓存统计"""
        base_stats = self._cache.stats()
        with self._lock:
            base_stats["keyword_index_size"] = len(self._keyword_index)
            base_stats["query_vectors_count"] = len(self._query_vectors)
        return base_stats


class LLMResponseCache:
    """
    LLM 响应缓存

    缓存 LLM 生成的响应，支持相似问题匹配
    """

    def __init__(self, max_size: int = 200, ttl: float = 7200):
        """
        初始化 LLM 响应缓存

        Args:
            max_size: 最大缓存条目数
            ttl: 缓存过期时间（秒），默认2小时
        """
        self._cache = LRUCache[str, Dict](max_size=max_size, ttl=ttl)
        self._lock = threading.RLock()

        # 注册到缓存管理器
        get_cache_manager().register("llm_response", self._cache)

    def _generate_cache_key(self, message: str, context_hash: str = "") -> str:
        """生成缓存键"""
        import hashlib
        normalized = message.strip().lower()
        key_str = f"{normalized}:{context_hash}"
        return hashlib.md5(key_str.encode()).hexdigest()

    def _hash_context(self, context: Dict) -> str:
        """计算上下文哈希"""
        import hashlib
        import json
        # 只使用关键上下文信息
        key_context = {
            "user_type": context.get("user_type", ""),
            "has_knowledge": bool(context.get("knowledge")),
            "has_tools": bool(context.get("tool_results")),
        }
        return hashlib.md5(json.dumps(key_context, sort_keys=True).encode()).hexdigest()[:8]

    def get(self, message: str, context: Dict = None) -> Optional[Dict]:
        """
        获取缓存的 LLM 响应

        Args:
            message: 用户消息
            context: 上下文信息

        Returns:
            缓存的响应，未命中返回 None
        """
        context_hash = self._hash_context(context) if context else ""
        cache_key = self._generate_cache_key(message, context_hash)
        return self._cache.get(cache_key)

    def set(self, message: str, response: str, context: Dict = None,
            metadata: Dict = None) -> None:
        """
        缓存 LLM 响应

        Args:
            message: 用户消息
            response: LLM 响应
            context: 上下文信息
            metadata: 额外元数据
        """
        context_hash = self._hash_context(context) if context else ""
        cache_key = self._generate_cache_key(message, context_hash)

        cache_entry = {
            "response": response,
            "cached_at": time.time(),
            "metadata": metadata or {},
        }
        self._cache.set(cache_key, cache_entry)

    def stats(self) -> Dict[str, Any]:
        """获取缓存统计"""
        return self._cache.stats()


# 全局缓存实例
_knowledge_cache: Optional[KnowledgeQueryCache] = None
_llm_cache: Optional[LLMResponseCache] = None
_cache_lock = threading.Lock()


def get_knowledge_cache() -> KnowledgeQueryCache:
    """获取知识库查询缓存单例"""
    global _knowledge_cache
    if _knowledge_cache is None:
        with _cache_lock:
            if _knowledge_cache is None:
                _knowledge_cache = KnowledgeQueryCache()
    return _knowledge_cache


def get_llm_cache() -> LLMResponseCache:
    """获取 LLM 响应缓存单例"""
    global _llm_cache
    if _llm_cache is None:
        with _cache_lock:
            if _llm_cache is None:
                _llm_cache = LLMResponseCache()
    return _llm_cache
