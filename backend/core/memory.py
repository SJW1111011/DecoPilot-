"""
高级记忆系统
支持短期记忆、长期记忆、工作记忆和知识图谱
支持多种持久化后端：JSON文件、SQLite、Redis
"""
import json
import time
import hashlib
import os
import sqlite3
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict, field
from datetime import datetime, timedelta
from enum import Enum
from abc import ABC, abstractmethod
import threading
from collections import OrderedDict
from pathlib import Path
from contextlib import contextmanager

from backend.core.logging_config import get_logger

logger = get_logger("memory")


class MemoryType(str, Enum):
    """记忆类型"""
    SHORT_TERM = "short_term"      # 短期记忆（当前对话）
    LONG_TERM = "long_term"        # 长期记忆（用户画像）
    WORKING = "working"            # 工作记忆（当前任务）
    EPISODIC = "episodic"          # 情景记忆（历史事件）
    SEMANTIC = "semantic"          # 语义记忆（知识图谱）


@dataclass
class MemoryItem:
    """记忆项"""
    id: str
    content: Any
    memory_type: MemoryType
    importance: float = 0.5        # 重要性 0-1
    timestamp: float = field(default_factory=time.time)
    access_count: int = 0
    last_access: float = field(default_factory=time.time)
    metadata: Dict = field(default_factory=dict)
    embedding: Optional[List[float]] = None

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "content": self.content,
            "memory_type": self.memory_type.value,
            "importance": self.importance,
            "timestamp": self.timestamp,
            "access_count": self.access_count,
            "last_access": self.last_access,
            "metadata": self.metadata,
        }


@dataclass
class StageTransitionEvent:
    """阶段转换事件"""
    from_stage: str
    to_stage: str
    timestamp: float = field(default_factory=time.time)
    trigger: str = ""  # 触发原因
    confidence: float = 0.0


@dataclass
class DecorationJourney:
    """装修旅程追踪"""
    current_stage: str = "准备"  # 准备/设计/施工/软装/入住
    stage_start_date: Optional[float] = None
    completed_stages: List[str] = field(default_factory=list)
    stage_notes: Dict[str, str] = field(default_factory=dict)  # 各阶段备注
    expected_completion: Optional[float] = None  # 预计完工时间
    actual_progress: float = 0.0  # 实际进度 0-100

    # 各阶段关键决策
    decisions: Dict[str, Dict] = field(default_factory=dict)
    # 例如: {"设计": {"style": "现代简约", "designer": "xxx"}}

    # 阶段转换历史（新增）
    stage_transitions: List[Dict] = field(default_factory=list)

    def record_stage_transition(self, from_stage: str, to_stage: str,
                                 trigger: str = "", confidence: float = 0.0):
        """记录阶段转换"""
        self.stage_transitions.append({
            "from_stage": from_stage,
            "to_stage": to_stage,
            "timestamp": time.time(),
            "trigger": trigger,
            "confidence": confidence,
        })
        # 保留最近20条转换记录
        if len(self.stage_transitions) > 20:
            self.stage_transitions = self.stage_transitions[-20:]

    def get_stage_duration(self, stage: str) -> Optional[float]:
        """获取某阶段持续时间（天）"""
        # 从转换历史中计算
        start_time = None
        end_time = None

        for transition in self.stage_transitions:
            if transition["to_stage"] == stage and start_time is None:
                start_time = transition["timestamp"]
            if transition["from_stage"] == stage:
                end_time = transition["timestamp"]

        if start_time:
            end = end_time or time.time()
            return (end - start_time) / 86400

        return None


@dataclass
class DecisionFactors:
    """决策偏好因素"""
    price_sensitivity: float = 0.5  # 价格敏感度 0-1
    quality_preference: float = 0.5  # 品质偏好 0-1
    brand_preference: float = 0.5  # 品牌偏好 0-1
    eco_preference: float = 0.5  # 环保偏好 0-1
    style_consistency: float = 0.5  # 风格一致性偏好 0-1
    decision_speed: str = "moderate"  # fast/moderate/slow 决策速度


@dataclass
class UserProfile:
    """用户画像"""
    user_id: str
    user_type: str = "c_end"       # c_end / b_end

    # 基础信息
    name: Optional[str] = None
    city: Optional[str] = None

    # C端用户属性
    budget_range: Optional[Tuple[float, float]] = None
    preferred_styles: List[str] = field(default_factory=list)
    house_area: Optional[float] = None
    decoration_stage: Optional[str] = None  # 准备/设计/施工/软装

    # 装修旅程追踪（新增）
    decoration_journey: Optional[DecorationJourney] = None

    # 决策偏好（新增）
    decision_factors: Optional[DecisionFactors] = None

    # 用户痛点记录（新增）
    pain_points: List[Dict] = field(default_factory=list)
    # 例如: [{"type": "预算", "description": "担心超支", "severity": 0.8}]

    # B端用户属性
    shop_name: Optional[str] = None
    shop_category: Optional[str] = None
    monthly_orders: Optional[int] = None

    # 行为数据
    interests: Dict[str, float] = field(default_factory=dict)  # 兴趣标签及权重
    interaction_history: List[Dict] = field(default_factory=list)

    # 偏好设置
    communication_style: str = "friendly"  # friendly/professional/concise
    response_detail_level: str = "medium"  # brief/medium/detailed

    # 元数据
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    total_sessions: int = 0
    total_messages: int = 0

    def update_interest(self, topic: str, weight: float = 0.1):
        """更新兴趣标签"""
        current = self.interests.get(topic, 0)
        self.interests[topic] = min(1.0, current + weight)
        self.updated_at = time.time()

    def decay_interests(self, decay_rate: float = 0.01):
        """兴趣衰减"""
        for topic in self.interests:
            self.interests[topic] = max(0, self.interests[topic] - decay_rate)
        self.interests = {k: v for k, v in self.interests.items() if v > 0.05}

    def update_decoration_stage(self, new_stage: str, trigger: str = "",
                                 confidence: float = 0.0):
        """更新装修阶段"""
        if self.decoration_journey is None:
            self.decoration_journey = DecorationJourney()

        old_stage = self.decoration_journey.current_stage
        if old_stage != new_stage:
            if old_stage not in self.decoration_journey.completed_stages:
                self.decoration_journey.completed_stages.append(old_stage)

            # 记录阶段转换
            self.decoration_journey.record_stage_transition(
                from_stage=old_stage,
                to_stage=new_stage,
                trigger=trigger,
                confidence=confidence,
            )

            self.decoration_journey.current_stage = new_stage
            self.decoration_journey.stage_start_date = time.time()

        self.decoration_stage = new_stage
        self.updated_at = time.time()

    def record_pain_point(self, pain_type: str, description: str, severity: float = 0.5):
        """记录用户痛点"""
        self.pain_points.append({
            "type": pain_type,
            "description": description,
            "severity": severity,
            "timestamp": time.time()
        })
        # 保留最近20个痛点
        if len(self.pain_points) > 20:
            self.pain_points = self.pain_points[-20:]
        self.updated_at = time.time()

    def infer_next_need(self) -> Optional[Dict]:
        """推断用户下一个需求"""
        if self.decoration_journey is None:
            return {"type": "stage_info", "suggestion": "了解装修流程", "reason": "用户刚开始装修"}

        stage = self.decoration_journey.current_stage
        stage_needs = {
            "准备": {"type": "budget_planning", "suggestion": "预算规划和风格选择", "reason": "准备阶段需要明确预算和风格"},
            "设计": {"type": "designer_selection", "suggestion": "设计方案确认", "reason": "设计阶段需要确认方案细节"},
            "施工": {"type": "progress_tracking", "suggestion": "施工进度和质量监督", "reason": "施工阶段需要关注进度和质量"},
            "软装": {"type": "furniture_selection", "suggestion": "家具软装选购", "reason": "软装阶段需要选购家具"},
            "入住": {"type": "maintenance", "suggestion": "入住注意事项", "reason": "入住阶段需要了解维护保养"},
        }

        # 根据痛点调整推荐
        if self.pain_points:
            recent_pain = self.pain_points[-1]
            if recent_pain["severity"] > 0.7:
                return {
                    "type": "pain_point_resolution",
                    "suggestion": f"解决{recent_pain['type']}问题",
                    "reason": recent_pain["description"]
                }

        return stage_needs.get(stage, {"type": "general", "suggestion": "装修咨询", "reason": "通用建议"})


@dataclass
class ConversationSummary:
    """对话摘要"""
    session_id: str
    user_id: str
    start_time: float
    end_time: Optional[float] = None

    # 摘要内容
    main_topics: List[str] = field(default_factory=list)
    key_entities: List[str] = field(default_factory=list)
    user_intents: List[str] = field(default_factory=list)
    action_items: List[str] = field(default_factory=list)

    # 统计信息
    message_count: int = 0
    user_satisfaction: Optional[float] = None  # 0-1

    # 原始摘要文本
    summary_text: str = ""


class MemoryCompressor:
    """
    记忆压缩器

    负责压缩会话记忆和应用遗忘曲线，防止长期运行时内存膨胀
    """

    # 遗忘曲线参数（艾宾浩斯遗忘曲线）
    FORGETTING_INTERVALS = [
        (1, 0.9),      # 1天后保留90%
        (2, 0.75),     # 2天后保留75%
        (7, 0.5),      # 7天后保留50%
        (14, 0.35),    # 14天后保留35%
        (30, 0.2),     # 30天后保留20%
        (60, 0.1),     # 60天后保留10%
    ]

    def __init__(self, importance_threshold: float = 0.3):
        """
        初始化记忆压缩器

        Args:
            importance_threshold: 重要性阈值，低于此值的记忆会被清理
        """
        self.importance_threshold = importance_threshold

    def compress_session(self, memories: List[MemoryItem], max_items: int = 10) -> Dict:
        """
        将会话记忆压缩为摘要

        Args:
            memories: 记忆项列表
            max_items: 压缩后保留的最大条目数

        Returns:
            压缩后的摘要字典
        """
        if not memories:
            return {"summary": "", "key_points": [], "entities": [], "compressed_count": 0}

        # 按重要性排序
        sorted_memories = sorted(memories, key=lambda x: x.importance, reverse=True)

        # 提取关键信息
        key_points = []
        entities = set()
        topics = set()

        for mem in sorted_memories[:max_items]:
            content = mem.content
            if isinstance(content, dict):
                # 提取对话内容
                if "content" in content:
                    key_points.append(content["content"][:200])
                # 提取实体
                if "entities" in content:
                    entities.update(content["entities"])
                # 提取主题
                if "topic" in content:
                    topics.add(content["topic"])
            elif isinstance(content, str):
                key_points.append(content[:200])

        # 生成摘要
        summary = self._generate_summary(key_points, list(topics))

        return {
            "summary": summary,
            "key_points": key_points[:5],  # 保留前5个关键点
            "entities": list(entities)[:20],  # 保留前20个实体
            "topics": list(topics),
            "compressed_count": len(memories),
            "retained_count": min(len(memories), max_items),
            "compression_ratio": min(len(memories), max_items) / len(memories) if memories else 1.0,
            "timestamp": time.time()
        }

    def apply_forgetting_curve(self, memories: List[MemoryItem],
                                current_time: float = None) -> List[MemoryItem]:
        """
        应用遗忘曲线，清理低重要性记忆

        Args:
            memories: 记忆项列表
            current_time: 当前时间戳，默认为当前时间

        Returns:
            过滤后的记忆列表
        """
        if current_time is None:
            current_time = time.time()

        retained = []
        for mem in memories:
            # 计算记忆年龄（天）
            age_days = (current_time - mem.timestamp) / 86400

            # 根据遗忘曲线计算保留概率
            retention_rate = self._calculate_retention_rate(age_days)

            # 调整后的重要性 = 原始重要性 * 保留率 * 访问频率加成
            access_bonus = min(1.0, mem.access_count / 10) * 0.2  # 访问次数加成，最多20%
            adjusted_importance = mem.importance * retention_rate + access_bonus

            # 如果调整后的重要性高于阈值，保留该记忆
            if adjusted_importance >= self.importance_threshold:
                # 更新记忆的重要性
                mem.importance = adjusted_importance
                retained.append(mem)

        logger.debug(f"遗忘曲线应用: {len(memories)} -> {len(retained)} 条记忆")
        return retained

    def _calculate_retention_rate(self, age_days: float) -> float:
        """
        根据遗忘曲线计算保留率

        Args:
            age_days: 记忆年龄（天）

        Returns:
            保留率 0-1
        """
        for days, rate in self.FORGETTING_INTERVALS:
            if age_days <= days:
                return rate
        return 0.05  # 超过60天，保留5%

    def _generate_summary(self, key_points: List[str], topics: List[str]) -> str:
        """
        生成摘要文本

        Args:
            key_points: 关键点列表
            topics: 主题列表

        Returns:
            摘要文本
        """
        if not key_points:
            return ""

        summary_parts = []

        if topics:
            summary_parts.append(f"主题: {', '.join(topics[:3])}")

        if key_points:
            # 取前3个关键点的简短版本
            brief_points = [p[:50] + "..." if len(p) > 50 else p for p in key_points[:3]]
            summary_parts.append(f"要点: {'; '.join(brief_points)}")

        return " | ".join(summary_parts)

    def merge_memories(self, memories: List[MemoryItem],
                       similarity_threshold: float = 0.8) -> List[MemoryItem]:
        """
        合并相似记忆

        Args:
            memories: 记忆项列表
            similarity_threshold: 相似度阈值

        Returns:
            合并后的记忆列表
        """
        if len(memories) <= 1:
            return memories

        merged = []
        used = set()

        for i, mem1 in enumerate(memories):
            if i in used:
                continue

            # 找到所有相似的记忆
            similar_group = [mem1]
            for j, mem2 in enumerate(memories[i+1:], i+1):
                if j in used:
                    continue
                if self._is_similar(mem1, mem2, similarity_threshold):
                    similar_group.append(mem2)
                    used.add(j)

            # 合并相似记忆
            if len(similar_group) > 1:
                merged_mem = self._merge_group(similar_group)
                merged.append(merged_mem)
            else:
                merged.append(mem1)

            used.add(i)

        return merged

    def _is_similar(self, mem1: MemoryItem, mem2: MemoryItem,
                    threshold: float) -> bool:
        """简单的相似度判断"""
        content1 = str(mem1.content).lower()
        content2 = str(mem2.content).lower()

        # 使用简单的词重叠率
        words1 = set(content1.split())
        words2 = set(content2.split())

        if not words1 or not words2:
            return False

        overlap = len(words1 & words2)
        similarity = overlap / max(len(words1), len(words2))

        return similarity >= threshold

    def _merge_group(self, group: List[MemoryItem]) -> MemoryItem:
        """合并一组相似记忆"""
        # 选择重要性最高的作为基础
        base = max(group, key=lambda x: x.importance)

        # 合并访问次数
        total_access = sum(m.access_count for m in group)

        # 取最新的时间戳
        latest_access = max(m.last_access for m in group)

        # 提升重要性（因为多次出现）
        boosted_importance = min(1.0, base.importance * (1 + 0.1 * (len(group) - 1)))

        return MemoryItem(
            id=base.id,
            content=base.content,
            memory_type=base.memory_type,
            importance=boosted_importance,
            timestamp=base.timestamp,
            access_count=total_access,
            last_access=latest_access,
            metadata={**base.metadata, "merged_count": len(group)}
        )


@dataclass
class KnowledgeNode:
    """知识图谱节点"""
    id: str
    name: str
    node_type: str  # entity/concept/attribute
    properties: Dict = field(default_factory=dict)
    embedding: Optional[List[float]] = None


@dataclass
class KnowledgeEdge:
    """知识图谱边"""
    source_id: str
    target_id: str
    relation: str
    weight: float = 1.0
    properties: Dict = field(default_factory=dict)


class MemoryStore(ABC):
    """记忆存储抽象基类"""

    @abstractmethod
    def save(self, item: MemoryItem) -> bool:
        pass

    @abstractmethod
    def get(self, item_id: str) -> Optional[MemoryItem]:
        pass

    @abstractmethod
    def search(self, query: str, limit: int = 10) -> List[MemoryItem]:
        pass

    @abstractmethod
    def delete(self, item_id: str) -> bool:
        pass


class InMemoryStore(MemoryStore):
    """
    内存存储实现

    使用 OrderedDict 实现 LRU 淘汰策略
    支持基于重要性的加权淘汰
    """

    def __init__(self, max_size: int = 10000):
        self.max_size = max_size
        self._store: OrderedDict[str, MemoryItem] = OrderedDict()
        self._lock = threading.RLock()

        # 统计信息
        self._hits = 0
        self._misses = 0
        self._evictions = 0

    @property
    def store(self) -> Dict[str, MemoryItem]:
        """兼容旧代码的属性访问"""
        return dict(self._store)

    def save(self, item: MemoryItem) -> bool:
        with self._lock:
            # 如果已存在，更新并移到末尾
            if item.id in self._store:
                self._store[item.id] = item
                self._store.move_to_end(item.id)
                return True

            # 检查容量，需要淘汰时使用加权策略
            while len(self._store) >= self.max_size:
                self._evict_by_score()

            self._store[item.id] = item
            return True

    def get(self, item_id: str) -> Optional[MemoryItem]:
        with self._lock:
            if item_id not in self._store:
                self._misses += 1
                return None

            item = self._store[item_id]
            item.access_count += 1
            item.last_access = time.time()

            # 移到末尾（最近使用）
            self._store.move_to_end(item_id)

            self._hits += 1
            return item

    def search(self, query: str, limit: int = 10) -> List[MemoryItem]:
        """搜索记忆（线程安全）"""
        with self._lock:
            results = []
            query_lower = query.lower()

            for item in self._store.values():
                content_str = str(item.content).lower()
                if query_lower in content_str:
                    results.append(item)

            # 按重要性和访问时间排序
            results.sort(key=lambda x: (x.importance, x.last_access), reverse=True)
            return results[:limit]

    def delete(self, item_id: str) -> bool:
        with self._lock:
            if item_id in self._store:
                del self._store[item_id]
                return True
            return False

    def _evict_by_score(self):
        """
        基于评分的淘汰策略

        评分 = 重要性 * 0.4 + 访问频率 * 0.3 + 时间新鲜度 * 0.3
        淘汰评分最低的条目
        """
        if not self._store:
            return

        now = time.time()
        min_score = float('inf')
        min_key = None

        # 只检查前 20% 的条目（最旧的）
        check_count = max(1, len(self._store) // 5)
        checked = 0

        for key, item in self._store.items():
            if checked >= check_count:
                break

            # 计算评分
            age = now - item.timestamp
            max_age = 86400 * 7  # 7天
            freshness = max(0, 1 - age / max_age)

            max_access = 100
            access_score = min(1, item.access_count / max_access)

            score = item.importance * 0.4 + access_score * 0.3 + freshness * 0.3

            if score < min_score:
                min_score = score
                min_key = key

            checked += 1

        if min_key:
            del self._store[min_key]
            self._evictions += 1

    def stats(self) -> Dict:
        """获取统计信息"""
        total = self._hits + self._misses
        return {
            "size": len(self._store),
            "max_size": self.max_size,
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": self._hits / total if total > 0 else 0,
            "evictions": self._evictions,
        }

    def clear(self):
        """清空存储"""
        with self._lock:
            self._store.clear()
            self._hits = 0
            self._misses = 0
            self._evictions = 0


class PersistentMemoryStore(MemoryStore):
    """
    持久化记忆存储实现

    支持 JSON 文件持久化，可选 Redis 后端
    """

    def __init__(self, storage_path: str, max_size: int = 10000,
                 use_redis: bool = False, redis_config: Dict = None):
        """
        初始化持久化存储

        Args:
            storage_path: JSON 文件存储路径
            max_size: 最大条目数
            use_redis: 是否使用 Redis
            redis_config: Redis 配置 {"host": "localhost", "port": 6379, "db": 0}
        """
        self.storage_path = storage_path
        self.max_size = max_size
        self.use_redis = use_redis
        self._store: OrderedDict[str, MemoryItem] = OrderedDict()
        self._lock = threading.RLock()
        self._dirty = False
        self._last_save = time.time()
        self._save_interval = 60  # 自动保存间隔（秒）

        # Redis 客户端
        self._redis = None
        if use_redis and redis_config:
            try:
                import redis
                self._redis = redis.Redis(
                    host=redis_config.get("host", "localhost"),
                    port=redis_config.get("port", 6379),
                    db=redis_config.get("db", 0),
                    decode_responses=True
                )
                self._redis.ping()
                logger.info("Redis 连接成功")
            except Exception as e:
                logger.warning(f"Redis 连接失败，回退到文件存储: {e}")
                self._redis = None

        # 统计信息
        self._hits = 0
        self._misses = 0

        # 加载已有数据
        self._load()

        # 启动自动保存线程
        self._start_auto_save()

    def _load(self):
        """从存储加载数据"""
        if self._redis:
            self._load_from_redis()
        else:
            self._load_from_file()

    def _load_from_file(self):
        """从 JSON 文件加载"""
        if not os.path.exists(self.storage_path):
            logger.info(f"存储文件不存在，将创建新文件: {self.storage_path}")
            return

        try:
            with open(self.storage_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            for item_data in data.get("items", []):
                item = MemoryItem(
                    id=item_data["id"],
                    content=item_data["content"],
                    memory_type=MemoryType(item_data["memory_type"]),
                    importance=item_data.get("importance", 0.5),
                    timestamp=item_data.get("timestamp", time.time()),
                    access_count=item_data.get("access_count", 0),
                    last_access=item_data.get("last_access", time.time()),
                    metadata=item_data.get("metadata", {}),
                )
                self._store[item.id] = item

            logger.info(f"从文件加载 {len(self._store)} 条记忆")
        except Exception as e:
            logger.error(f"加载记忆文件失败: {e}")

    def _load_from_redis(self):
        """从 Redis 加载"""
        try:
            keys = self._redis.keys("memory:*")
            for key in keys:
                data = self._redis.hgetall(key)
                if data:
                    item = MemoryItem(
                        id=data["id"],
                        content=json.loads(data.get("content", "{}")),
                        memory_type=MemoryType(data["memory_type"]),
                        importance=float(data.get("importance", 0.5)),
                        timestamp=float(data.get("timestamp", time.time())),
                        access_count=int(data.get("access_count", 0)),
                        last_access=float(data.get("last_access", time.time())),
                        metadata=json.loads(data.get("metadata", "{}")),
                    )
                    self._store[item.id] = item

            logger.info(f"从 Redis 加载 {len(self._store)} 条记忆")
        except Exception as e:
            logger.error(f"从 Redis 加载失败: {e}")

    def _save(self):
        """保存数据到存储"""
        if self._redis:
            self._save_to_redis()
        else:
            self._save_to_file()
        self._dirty = False
        self._last_save = time.time()

    def _save_to_file(self):
        """保存到 JSON 文件"""
        try:
            # 确保目录存在
            os.makedirs(os.path.dirname(self.storage_path), exist_ok=True)

            data = {
                "version": "1.0",
                "saved_at": datetime.now().isoformat(),
                "items": [item.to_dict() for item in self._store.values()]
            }

            # 写入临时文件后重命名，确保原子性
            temp_path = self.storage_path + ".tmp"
            with open(temp_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

            os.replace(temp_path, self.storage_path)
            logger.debug(f"保存 {len(self._store)} 条记忆到文件")
        except Exception as e:
            logger.error(f"保存记忆文件失败: {e}")

    def _save_to_redis(self):
        """保存到 Redis"""
        try:
            pipe = self._redis.pipeline()
            for item in self._store.values():
                key = f"memory:{item.id}"
                pipe.hset(key, mapping={
                    "id": item.id,
                    "content": json.dumps(item.content, ensure_ascii=False),
                    "memory_type": item.memory_type.value,
                    "importance": str(item.importance),
                    "timestamp": str(item.timestamp),
                    "access_count": str(item.access_count),
                    "last_access": str(item.last_access),
                    "metadata": json.dumps(item.metadata, ensure_ascii=False),
                })
                # 设置过期时间（7天）
                pipe.expire(key, 7 * 24 * 3600)
            pipe.execute()
            logger.debug(f"保存 {len(self._store)} 条记忆到 Redis")
        except Exception as e:
            logger.error(f"保存到 Redis 失败: {e}")

    def _start_auto_save(self):
        """启动自动保存线程"""
        def auto_save_worker():
            while True:
                time.sleep(self._save_interval)
                if self._dirty:
                    with self._lock:
                        self._save()

        thread = threading.Thread(target=auto_save_worker, daemon=True)
        thread.start()

    @property
    def store(self) -> Dict[str, MemoryItem]:
        """兼容旧代码的属性访问"""
        return dict(self._store)

    def save(self, item: MemoryItem) -> bool:
        """保存记忆项"""
        with self._lock:
            # 检查容量
            while len(self._store) >= self.max_size:
                # 删除最旧的
                oldest_key = next(iter(self._store))
                del self._store[oldest_key]

            self._store[item.id] = item
            self._store.move_to_end(item.id)
            self._dirty = True

            # 如果距离上次保存超过间隔，立即保存
            if time.time() - self._last_save > self._save_interval:
                self._save()

            return True

    def get(self, item_id: str) -> Optional[MemoryItem]:
        """获取记忆项"""
        with self._lock:
            if item_id not in self._store:
                self._misses += 1
                return None

            item = self._store[item_id]
            item.access_count += 1
            item.last_access = time.time()
            self._store.move_to_end(item_id)
            self._hits += 1
            self._dirty = True
            return item

    def search(self, query: str, limit: int = 10) -> List[MemoryItem]:
        """搜索记忆"""
        with self._lock:
            results = []
            query_lower = query.lower()

            for item in self._store.values():
                content_str = str(item.content).lower()
                if query_lower in content_str:
                    results.append(item)

            results.sort(key=lambda x: (x.importance, x.last_access), reverse=True)
            return results[:limit]

    def delete(self, item_id: str) -> bool:
        """删除记忆项"""
        with self._lock:
            if item_id in self._store:
                del self._store[item_id]
                self._dirty = True

                # 从 Redis 删除
                if self._redis:
                    try:
                        self._redis.delete(f"memory:{item_id}")
                    except Exception:
                        pass

                return True
            return False

    def flush(self):
        """强制保存到存储"""
        with self._lock:
            self._save()

    def stats(self) -> Dict:
        """获取统计信息"""
        total = self._hits + self._misses
        return {
            "size": len(self._store),
            "max_size": self.max_size,
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": self._hits / total if total > 0 else 0,
            "storage_type": "redis" if self._redis else "file",
            "dirty": self._dirty,
        }


class SQLiteMemoryStore(MemoryStore):
    """
    SQLite 持久化记忆存储实现

    优点：
    - 支持并发读写（WAL模式）
    - 原子性事务保证数据一致性
    - 支持复杂查询和索引
    - 无需额外服务依赖
    """

    # 数据库表结构
    CREATE_TABLE_SQL = """
    CREATE TABLE IF NOT EXISTS memories (
        id TEXT PRIMARY KEY,
        content TEXT NOT NULL,
        memory_type TEXT NOT NULL,
        importance REAL DEFAULT 0.5,
        timestamp REAL NOT NULL,
        access_count INTEGER DEFAULT 0,
        last_access REAL NOT NULL,
        metadata TEXT DEFAULT '{}',
        user_id TEXT,
        session_id TEXT,
        created_at REAL NOT NULL
    );

    CREATE INDEX IF NOT EXISTS idx_memory_type ON memories(memory_type);
    CREATE INDEX IF NOT EXISTS idx_user_id ON memories(user_id);
    CREATE INDEX IF NOT EXISTS idx_session_id ON memories(session_id);
    CREATE INDEX IF NOT EXISTS idx_timestamp ON memories(timestamp DESC);
    CREATE INDEX IF NOT EXISTS idx_importance ON memories(importance DESC);
    """

    def __init__(self, db_path: str, max_size: int = 100000):
        """
        初始化 SQLite 存储

        Args:
            db_path: 数据库文件路径
            max_size: 最大条目数
        """
        self.db_path = db_path
        self.max_size = max_size
        self._lock = threading.RLock()
        self._local = threading.local()

        # 统计信息
        self._hits = 0
        self._misses = 0

        # 确保目录存在
        os.makedirs(os.path.dirname(db_path), exist_ok=True)

        # 初始化数据库
        self._init_db()

        logger.info(f"SQLite 记忆存储初始化完成: {db_path}")

    @contextmanager
    def _get_connection(self):
        """获取线程本地的数据库连接"""
        if not hasattr(self._local, 'conn') or self._local.conn is None:
            self._local.conn = sqlite3.connect(
                self.db_path,
                check_same_thread=False,
                timeout=30.0
            )
            self._local.conn.row_factory = sqlite3.Row
            # 启用 WAL 模式，提高并发性能
            self._local.conn.execute("PRAGMA journal_mode=WAL")
            self._local.conn.execute("PRAGMA synchronous=NORMAL")
            self._local.conn.execute("PRAGMA cache_size=10000")

        try:
            yield self._local.conn
        except Exception as e:
            self._local.conn.rollback()
            raise e

    def _init_db(self):
        """初始化数据库表"""
        with self._get_connection() as conn:
            conn.executescript(self.CREATE_TABLE_SQL)
            conn.commit()

    def save(self, item: MemoryItem) -> bool:
        """保存记忆项"""
        with self._lock:
            try:
                with self._get_connection() as conn:
                    # 检查容量，需要时清理旧数据
                    cursor = conn.execute("SELECT COUNT(*) FROM memories")
                    count = cursor.fetchone()[0]

                    if count >= self.max_size:
                        # 删除最旧且重要性最低的 10% 数据
                        delete_count = max(1, self.max_size // 10)
                        conn.execute("""
                            DELETE FROM memories WHERE id IN (
                                SELECT id FROM memories
                                ORDER BY importance ASC, timestamp ASC
                                LIMIT ?
                            )
                        """, (delete_count,))

                    # 提取 user_id 和 session_id
                    user_id = item.metadata.get("user_id")
                    session_id = item.metadata.get("session_id")

                    # 插入或更新
                    conn.execute("""
                        INSERT OR REPLACE INTO memories
                        (id, content, memory_type, importance, timestamp,
                         access_count, last_access, metadata, user_id, session_id, created_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        item.id,
                        json.dumps(item.content, ensure_ascii=False),
                        item.memory_type.value,
                        item.importance,
                        item.timestamp,
                        item.access_count,
                        item.last_access,
                        json.dumps(item.metadata, ensure_ascii=False),
                        user_id,
                        session_id,
                        time.time()
                    ))
                    conn.commit()
                    return True
            except Exception as e:
                logger.error(f"SQLite 保存失败: {e}")
                return False

    def get(self, item_id: str) -> Optional[MemoryItem]:
        """获取记忆项"""
        with self._lock:
            try:
                with self._get_connection() as conn:
                    cursor = conn.execute(
                        "SELECT * FROM memories WHERE id = ?", (item_id,)
                    )
                    row = cursor.fetchone()

                    if not row:
                        self._misses += 1
                        return None

                    self._hits += 1

                    # 更新访问信息
                    conn.execute("""
                        UPDATE memories
                        SET access_count = access_count + 1, last_access = ?
                        WHERE id = ?
                    """, (time.time(), item_id))
                    conn.commit()

                    return self._row_to_item(row)
            except Exception as e:
                logger.error(f"SQLite 获取失败: {e}")
                return None

    def search(self, query: str, limit: int = 10) -> List[MemoryItem]:
        """搜索记忆"""
        with self._lock:
            try:
                with self._get_connection() as conn:
                    # 使用 LIKE 进行简单搜索
                    cursor = conn.execute("""
                        SELECT * FROM memories
                        WHERE content LIKE ?
                        ORDER BY importance DESC, last_access DESC
                        LIMIT ?
                    """, (f"%{query}%", limit))

                    return [self._row_to_item(row) for row in cursor.fetchall()]
            except Exception as e:
                logger.error(f"SQLite 搜索失败: {e}")
                return []

    def search_by_user(self, user_id: str, query: str = None,
                       limit: int = 10) -> List[MemoryItem]:
        """按用户搜索记忆"""
        with self._lock:
            try:
                with self._get_connection() as conn:
                    if query:
                        cursor = conn.execute("""
                            SELECT * FROM memories
                            WHERE user_id = ? AND content LIKE ?
                            ORDER BY importance DESC, last_access DESC
                            LIMIT ?
                        """, (user_id, f"%{query}%", limit))
                    else:
                        cursor = conn.execute("""
                            SELECT * FROM memories
                            WHERE user_id = ?
                            ORDER BY timestamp DESC
                            LIMIT ?
                        """, (user_id, limit))

                    return [self._row_to_item(row) for row in cursor.fetchall()]
            except Exception as e:
                logger.error(f"SQLite 用户搜索失败: {e}")
                return []

    def search_by_session(self, session_id: str, limit: int = 20) -> List[MemoryItem]:
        """按会话搜索记忆"""
        with self._lock:
            try:
                with self._get_connection() as conn:
                    cursor = conn.execute("""
                        SELECT * FROM memories
                        WHERE session_id = ?
                        ORDER BY timestamp DESC
                        LIMIT ?
                    """, (session_id, limit))

                    return [self._row_to_item(row) for row in cursor.fetchall()]
            except Exception as e:
                logger.error(f"SQLite 会话搜索失败: {e}")
                return []

    def delete(self, item_id: str) -> bool:
        """删除记忆项"""
        with self._lock:
            try:
                with self._get_connection() as conn:
                    cursor = conn.execute(
                        "DELETE FROM memories WHERE id = ?", (item_id,)
                    )
                    conn.commit()
                    return cursor.rowcount > 0
            except Exception as e:
                logger.error(f"SQLite 删除失败: {e}")
                return False

    def delete_by_session(self, session_id: str) -> int:
        """删除会话的所有记忆"""
        with self._lock:
            try:
                with self._get_connection() as conn:
                    cursor = conn.execute(
                        "DELETE FROM memories WHERE session_id = ?", (session_id,)
                    )
                    conn.commit()
                    return cursor.rowcount
            except Exception as e:
                logger.error(f"SQLite 会话删除失败: {e}")
                return 0

    def _row_to_item(self, row: sqlite3.Row) -> MemoryItem:
        """将数据库行转换为 MemoryItem"""
        return MemoryItem(
            id=row["id"],
            content=json.loads(row["content"]),
            memory_type=MemoryType(row["memory_type"]),
            importance=row["importance"],
            timestamp=row["timestamp"],
            access_count=row["access_count"],
            last_access=row["last_access"],
            metadata=json.loads(row["metadata"]),
        )

    @property
    def store(self) -> Dict[str, MemoryItem]:
        """兼容旧代码的属性访问（返回最近的记忆）"""
        items = {}
        try:
            with self._get_connection() as conn:
                cursor = conn.execute("""
                    SELECT * FROM memories
                    ORDER BY timestamp DESC
                    LIMIT 1000
                """)
                for row in cursor.fetchall():
                    item = self._row_to_item(row)
                    items[item.id] = item
        except Exception as e:
            logger.error(f"SQLite store 属性访问失败: {e}")
        return items

    def stats(self) -> Dict:
        """获取统计信息"""
        total = self._hits + self._misses
        count = 0
        try:
            with self._get_connection() as conn:
                cursor = conn.execute("SELECT COUNT(*) FROM memories")
                count = cursor.fetchone()[0]
        except Exception:
            pass

        return {
            "size": count,
            "max_size": self.max_size,
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": self._hits / total if total > 0 else 0,
            "storage_type": "sqlite",
        }

    def vacuum(self):
        """优化数据库（压缩空间）"""
        with self._lock:
            try:
                with self._get_connection() as conn:
                    conn.execute("VACUUM")
                logger.info("SQLite 数据库优化完成")
            except Exception as e:
                logger.error(f"SQLite VACUUM 失败: {e}")

    def close(self):
        """关闭数据库连接"""
        if hasattr(self._local, 'conn') and self._local.conn:
            self._local.conn.close()
            self._local.conn = None


class UserProfileStore:
    """
    用户画像持久化存储
    """

    def __init__(self, storage_path: str):
        self.storage_path = storage_path
        self._profiles: Dict[str, UserProfile] = {}
        self._lock = threading.RLock()
        self._dirty = False
        self._load()

    def _load(self):
        """加载用户画像"""
        if not os.path.exists(self.storage_path):
            return

        try:
            with open(self.storage_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            for user_id, profile_data in data.get("profiles", {}).items():
                profile = UserProfile(
                    user_id=profile_data["user_id"],
                    user_type=profile_data.get("user_type", "c_end"),
                    name=profile_data.get("name"),
                    city=profile_data.get("city"),
                    budget_range=tuple(profile_data["budget_range"]) if profile_data.get("budget_range") else None,
                    preferred_styles=profile_data.get("preferred_styles", []),
                    house_area=profile_data.get("house_area"),
                    decoration_stage=profile_data.get("decoration_stage"),
                    shop_name=profile_data.get("shop_name"),
                    shop_category=profile_data.get("shop_category"),
                    monthly_orders=profile_data.get("monthly_orders"),
                    interests=profile_data.get("interests", {}),
                    interaction_history=profile_data.get("interaction_history", [])[-100:],
                    communication_style=profile_data.get("communication_style", "friendly"),
                    response_detail_level=profile_data.get("response_detail_level", "medium"),
                    created_at=profile_data.get("created_at", time.time()),
                    updated_at=profile_data.get("updated_at", time.time()),
                    total_sessions=profile_data.get("total_sessions", 0),
                    total_messages=profile_data.get("total_messages", 0),
                )
                self._profiles[user_id] = profile

            logger.info(f"加载 {len(self._profiles)} 个用户画像")
        except Exception as e:
            logger.error(f"加载用户画像失败: {e}")

    def _save(self):
        """保存用户画像"""
        try:
            os.makedirs(os.path.dirname(self.storage_path), exist_ok=True)

            data = {
                "version": "1.0",
                "saved_at": datetime.now().isoformat(),
                "profiles": {}
            }

            for user_id, profile in self._profiles.items():
                data["profiles"][user_id] = {
                    "user_id": profile.user_id,
                    "user_type": profile.user_type,
                    "name": profile.name,
                    "city": profile.city,
                    "budget_range": list(profile.budget_range) if profile.budget_range else None,
                    "preferred_styles": profile.preferred_styles,
                    "house_area": profile.house_area,
                    "decoration_stage": profile.decoration_stage,
                    "shop_name": profile.shop_name,
                    "shop_category": profile.shop_category,
                    "monthly_orders": profile.monthly_orders,
                    "interests": profile.interests,
                    "interaction_history": profile.interaction_history[-100:],
                    "communication_style": profile.communication_style,
                    "response_detail_level": profile.response_detail_level,
                    "created_at": profile.created_at,
                    "updated_at": profile.updated_at,
                    "total_sessions": profile.total_sessions,
                    "total_messages": profile.total_messages,
                }

            temp_path = self.storage_path + ".tmp"
            with open(temp_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

            os.replace(temp_path, self.storage_path)
            self._dirty = False
            logger.debug(f"保存 {len(self._profiles)} 个用户画像")
        except Exception as e:
            logger.error(f"保存用户画像失败: {e}")

    def get(self, user_id: str) -> Optional[UserProfile]:
        """获取用户画像"""
        with self._lock:
            return self._profiles.get(user_id)

    def get_or_create(self, user_id: str, user_type: str = "c_end") -> UserProfile:
        """获取或创建用户画像"""
        with self._lock:
            if user_id not in self._profiles:
                self._profiles[user_id] = UserProfile(
                    user_id=user_id,
                    user_type=user_type
                )
                self._dirty = True
            return self._profiles[user_id]

    def update(self, user_id: str, **kwargs):
        """更新用户画像"""
        with self._lock:
            profile = self.get_or_create(user_id)
            for key, value in kwargs.items():
                if hasattr(profile, key):
                    setattr(profile, key, value)
            profile.updated_at = time.time()
            self._dirty = True

    def save_if_dirty(self):
        """如果有修改则保存"""
        with self._lock:
            if self._dirty:
                self._save()

    def flush(self):
        """强制保存"""
        with self._lock:
            self._save()


class MemoryManager:
    """记忆管理器"""

    # 默认存储路径
    DEFAULT_STORAGE_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "data", "memory")

    # 存储后端类型
    BACKEND_MEMORY = "memory"
    BACKEND_FILE = "file"
    BACKEND_SQLITE = "sqlite"
    BACKEND_REDIS = "redis"

    def __init__(self, storage_dir: str = None, use_persistence: bool = True,
                 backend: str = "sqlite", redis_config: Dict = None,
                 use_redis: bool = False):
        """
        初始化记忆管理器

        Args:
            storage_dir: 存储目录路径
            use_persistence: 是否启用持久化
            backend: 存储后端类型 ("memory", "file", "sqlite", "redis")
            redis_config: Redis 配置
            use_redis: 是否使用 Redis（兼容旧参数）
        """
        self.storage_dir = storage_dir or self.DEFAULT_STORAGE_DIR
        self.use_persistence = use_persistence

        # 兼容旧参数
        if use_redis:
            backend = self.BACKEND_REDIS

        self.backend = backend

        # 确保存储目录存在
        if use_persistence:
            os.makedirs(self.storage_dir, exist_ok=True)

        # 初始化存储
        self._init_stores(backend, redis_config)

        # 初始化记忆压缩器
        self.compressor = MemoryCompressor(importance_threshold=0.3)

        self.user_profiles: Dict[str, UserProfile] = {}
        self.conversation_summaries: Dict[str, ConversationSummary] = {}

        # 知识图谱
        self.kg_nodes: Dict[str, KnowledgeNode] = {}
        self.kg_edges: List[KnowledgeEdge] = []

        self._lock = threading.Lock()

        # 如果有持久化存储，加载用户画像到内存
        if self._profile_store:
            self.user_profiles = self._profile_store._profiles

        logger.info(f"记忆管理器初始化完成，后端: {backend}")

    def _init_stores(self, backend: str, redis_config: Dict = None):
        """初始化存储后端"""
        # 短期记忆和工作记忆始终使用内存存储
        self.short_term = InMemoryStore(max_size=1000)
        self.working = InMemoryStore(max_size=100)

        if not self.use_persistence or backend == self.BACKEND_MEMORY:
            # 纯内存模式
            self.long_term = InMemoryStore(max_size=100000)
            self._profile_store = None

        elif backend == self.BACKEND_SQLITE:
            # SQLite 模式（推荐）
            self.long_term = SQLiteMemoryStore(
                db_path=os.path.join(self.storage_dir, "memory.db"),
                max_size=100000
            )
            self._profile_store = UserProfileStore(
                storage_path=os.path.join(self.storage_dir, "user_profiles.json")
            )

        elif backend == self.BACKEND_REDIS:
            # Redis 模式
            self.long_term = PersistentMemoryStore(
                storage_path=os.path.join(self.storage_dir, "long_term.json"),
                max_size=100000,
                use_redis=True,
                redis_config=redis_config
            )
            self._profile_store = UserProfileStore(
                storage_path=os.path.join(self.storage_dir, "user_profiles.json")
            )

        else:
            # 文件模式（默认回退）
            self.long_term = PersistentMemoryStore(
                storage_path=os.path.join(self.storage_dir, "long_term.json"),
                max_size=100000,
                use_redis=False
            )
            self._profile_store = UserProfileStore(
                storage_path=os.path.join(self.storage_dir, "user_profiles.json")
            )

    # === 短期记忆操作 ===

    def add_to_short_term(self, session_id: str, content: Any,
                          importance: float = 0.5) -> str:
        """添加短期记忆"""
        item_id = f"st_{session_id}_{int(time.time() * 1000)}"
        item = MemoryItem(
            id=item_id,
            content=content,
            memory_type=MemoryType.SHORT_TERM,
            importance=importance,
            metadata={"session_id": session_id}
        )
        self.short_term.save(item)
        return item_id

    def get_short_term_context(self, session_id: str,
                                limit: int = 10) -> List[MemoryItem]:
        """获取短期记忆上下文"""
        results = []
        for item in self.short_term.store.values():
            if item.metadata.get("session_id") == session_id:
                results.append(item)
        results.sort(key=lambda x: x.timestamp, reverse=True)
        return results[:limit]

    # === 长期记忆操作 ===

    def add_to_long_term(self, user_id: str, content: Any,
                         importance: float = 0.5,
                         metadata: Dict = None) -> str:
        """添加长期记忆"""
        item_id = f"lt_{user_id}_{int(time.time() * 1000)}"
        item = MemoryItem(
            id=item_id,
            content=content,
            memory_type=MemoryType.LONG_TERM,
            importance=importance,
            metadata={"user_id": user_id, **(metadata or {})}
        )
        self.long_term.save(item)
        return item_id

    def search_long_term(self, user_id: str, query: str,
                         limit: int = 5) -> List[MemoryItem]:
        """搜索长期记忆"""
        results = []
        for item in self.long_term.store.values():
            if item.metadata.get("user_id") == user_id:
                if query.lower() in str(item.content).lower():
                    results.append(item)
        results.sort(key=lambda x: (x.importance, x.last_access), reverse=True)
        return results[:limit]

    # === 工作记忆操作 ===

    def set_working_memory(self, session_id: str, key: str, value: Any):
        """设置工作记忆"""
        item_id = f"wm_{session_id}_{key}"
        item = MemoryItem(
            id=item_id,
            content={"key": key, "value": value},
            memory_type=MemoryType.WORKING,
            importance=1.0,
            metadata={"session_id": session_id, "key": key}
        )
        self.working.save(item)

    def get_working_memory(self, session_id: str, key: str) -> Optional[Any]:
        """获取工作记忆"""
        item_id = f"wm_{session_id}_{key}"
        item = self.working.get(item_id)
        if item:
            return item.content.get("value")
        return None

    def get_all_working_memory(self, session_id: str) -> Dict[str, Any]:
        """获取所有工作记忆"""
        result = {}
        for item in self.working.store.values():
            if item.metadata.get("session_id") == session_id:
                key = item.metadata.get("key")
                if key:
                    result[key] = item.content.get("value")
        return result

    def clear_working_memory(self, session_id: str):
        """清除工作记忆"""
        to_delete = []
        for item_id, item in self.working.store.items():
            if item.metadata.get("session_id") == session_id:
                to_delete.append(item_id)
        for item_id in to_delete:
            self.working.delete(item_id)

    # === 用户画像操作 ===

    def get_or_create_profile(self, user_id: str,
                               user_type: str = "c_end") -> UserProfile:
        """获取或创建用户画像"""
        if self._profile_store:
            profile = self._profile_store.get_or_create(user_id, user_type)
            self.user_profiles[user_id] = profile
            return profile
        else:
            if user_id not in self.user_profiles:
                self.user_profiles[user_id] = UserProfile(
                    user_id=user_id,
                    user_type=user_type
                )
            return self.user_profiles[user_id]

    def update_profile(self, user_id: str, **kwargs):
        """更新用户画像"""
        profile = self.get_or_create_profile(user_id)
        for key, value in kwargs.items():
            if hasattr(profile, key):
                setattr(profile, key, value)
        profile.updated_at = time.time()
        if self._profile_store:
            self._profile_store._dirty = True

    def record_interaction(self, user_id: str, interaction_type: str,
                           content: str, metadata: Dict = None):
        """记录用户交互"""
        profile = self.get_or_create_profile(user_id)
        profile.interaction_history.append({
            "type": interaction_type,
            "content": content,
            "timestamp": time.time(),
            "metadata": metadata or {}
        })
        # 保留最近100条交互
        if len(profile.interaction_history) > 100:
            profile.interaction_history = profile.interaction_history[-100:]
        profile.total_messages += 1
        profile.updated_at = time.time()
        if self._profile_store:
            self._profile_store._dirty = True

    # === 对话摘要操作 ===

    def create_conversation_summary(self, session_id: str,
                                     user_id: str) -> ConversationSummary:
        """创建对话摘要"""
        summary = ConversationSummary(
            session_id=session_id,
            user_id=user_id,
            start_time=time.time()
        )
        self.conversation_summaries[session_id] = summary
        return summary

    def update_conversation_summary(self, session_id: str, **kwargs):
        """更新对话摘要"""
        if session_id in self.conversation_summaries:
            summary = self.conversation_summaries[session_id]
            for key, value in kwargs.items():
                if hasattr(summary, key):
                    if isinstance(getattr(summary, key), list) and isinstance(value, str):
                        getattr(summary, key).append(value)
                    else:
                        setattr(summary, key, value)

    def finalize_conversation(self, session_id: str,
                               summary_text: str = "") -> Optional[ConversationSummary]:
        """结束对话并生成摘要"""
        if session_id in self.conversation_summaries:
            summary = self.conversation_summaries[session_id]
            summary.end_time = time.time()
            summary.summary_text = summary_text

            # 将摘要存入长期记忆
            self.add_to_long_term(
                user_id=summary.user_id,
                content=asdict(summary),
                importance=0.7,
                metadata={"type": "conversation_summary"}
            )
            return summary
        return None

    # === 知识图谱操作 ===

    def add_kg_node(self, name: str, node_type: str,
                    properties: Dict = None) -> str:
        """添加知识图谱节点"""
        node_id = hashlib.md5(f"{node_type}:{name}".encode()).hexdigest()[:12]
        node = KnowledgeNode(
            id=node_id,
            name=name,
            node_type=node_type,
            properties=properties or {}
        )
        self.kg_nodes[node_id] = node
        return node_id

    def add_kg_edge(self, source_name: str, target_name: str,
                    relation: str, weight: float = 1.0):
        """添加知识图谱边"""
        # 查找或创建节点
        source_id = None
        target_id = None
        for node in self.kg_nodes.values():
            if node.name == source_name:
                source_id = node.id
            if node.name == target_name:
                target_id = node.id

        if source_id and target_id:
            edge = KnowledgeEdge(
                source_id=source_id,
                target_id=target_id,
                relation=relation,
                weight=weight
            )
            self.kg_edges.append(edge)

    def get_related_nodes(self, node_name: str,
                          relation: str = None) -> List[Tuple[str, str, float]]:
        """获取相关节点"""
        results = []
        node_id = None
        for node in self.kg_nodes.values():
            if node.name == node_name:
                node_id = node.id
                break

        if not node_id:
            return results

        for edge in self.kg_edges:
            if edge.source_id == node_id:
                if relation is None or edge.relation == relation:
                    target_node = self.kg_nodes.get(edge.target_id)
                    if target_node:
                        results.append((target_node.name, edge.relation, edge.weight))
            elif edge.target_id == node_id:
                if relation is None or edge.relation == relation:
                    source_node = self.kg_nodes.get(edge.source_id)
                    if source_node:
                        results.append((source_node.name, edge.relation, edge.weight))

        return results

    # === 记忆整合 ===

    def get_context_for_query(self, user_id: str, session_id: str,
                               query: str) -> Dict:
        """获取查询的完整上下文"""
        context = {
            "user_profile": None,
            "short_term_memory": [],
            "long_term_memory": [],
            "working_memory": {},
            "related_knowledge": [],
        }

        # 用户画像
        if user_id in self.user_profiles:
            profile = self.user_profiles[user_id]
            context["user_profile"] = {
                "user_type": profile.user_type,
                "interests": profile.interests,
                "preferred_styles": profile.preferred_styles,
                "budget_range": profile.budget_range,
                "communication_style": profile.communication_style,
            }

        # 短期记忆
        short_term = self.get_short_term_context(session_id, limit=5)
        context["short_term_memory"] = [item.content for item in short_term]

        # 长期记忆
        long_term = self.search_long_term(user_id, query, limit=3)
        context["long_term_memory"] = [item.content for item in long_term]

        # 工作记忆
        context["working_memory"] = self.get_all_working_memory(session_id)

        return context

    def consolidate_memories(self, user_id: str):
        """记忆整合（将重要的短期记忆转为长期记忆）"""
        # 找出该用户的高重要性短期记忆
        to_consolidate = []
        for item in self.short_term.store.values():
            if (item.metadata.get("user_id") == user_id and
                item.importance > 0.7):
                to_consolidate.append(item)

        # 转移到长期记忆
        for item in to_consolidate:
            self.add_to_long_term(
                user_id=user_id,
                content=item.content,
                importance=item.importance,
                metadata=item.metadata
            )
            self.short_term.delete(item.id)

    # === 记忆压缩操作 ===

    def compress_session_memories(self, session_id: str) -> Dict:
        """
        压缩会话记忆

        Args:
            session_id: 会话ID

        Returns:
            压缩摘要
        """
        memories = self.get_short_term_context(session_id, limit=100)
        if not memories:
            return {"summary": "", "compressed_count": 0}

        summary = self.compressor.compress_session(memories)

        # 将摘要存入长期记忆
        if summary.get("summary"):
            self.add_to_long_term(
                user_id=session_id,
                content=summary,
                importance=0.8,
                metadata={"type": "session_summary", "session_id": session_id}
            )

        # 清理已压缩的短期记忆（保留最近5条）
        memories_to_delete = memories[5:]
        for mem in memories_to_delete:
            self.short_term.delete(mem.id)

        logger.info(f"会话 {session_id} 记忆压缩完成: {len(memories)} -> {min(5, len(memories))}")
        return summary

    def apply_forgetting(self, user_id: str = None):
        """
        应用遗忘曲线清理记忆

        Args:
            user_id: 可选，指定用户ID，不指定则清理所有
        """
        # 获取长期记忆
        all_memories = list(self.long_term.store.values())

        if user_id:
            all_memories = [m for m in all_memories if m.metadata.get("user_id") == user_id]

        if not all_memories:
            return

        # 应用遗忘曲线
        retained = self.compressor.apply_forgetting_curve(all_memories)
        retained_ids = {m.id for m in retained}

        # 删除被遗忘的记忆
        deleted_count = 0
        for mem in all_memories:
            if mem.id not in retained_ids:
                self.long_term.delete(mem.id)
                deleted_count += 1

        logger.info(f"遗忘曲线应用完成: 删除 {deleted_count} 条记忆")

    def merge_similar_memories(self, user_id: str):
        """
        合并用户的相似记忆

        Args:
            user_id: 用户ID
        """
        # 获取用户的长期记忆
        user_memories = [
            m for m in self.long_term.store.values()
            if m.metadata.get("user_id") == user_id
        ]

        if len(user_memories) <= 1:
            return

        # 合并相似记忆
        merged = self.compressor.merge_memories(user_memories)

        # 如果有合并发生，更新存储
        if len(merged) < len(user_memories):
            # 删除旧记忆
            for mem in user_memories:
                self.long_term.delete(mem.id)

            # 保存合并后的记忆
            for mem in merged:
                self.long_term.save(mem)

            logger.info(f"用户 {user_id} 记忆合并: {len(user_memories)} -> {len(merged)}")

    def run_maintenance(self):
        """
        运行记忆系统维护任务

        包括：遗忘曲线应用、相似记忆合并、数据库优化
        """
        logger.info("开始记忆系统维护...")

        # 1. 应用遗忘曲线
        self.apply_forgetting()

        # 2. 合并相似记忆（对每个用户）
        user_ids = set()
        for mem in self.long_term.store.values():
            uid = mem.metadata.get("user_id")
            if uid:
                user_ids.add(uid)

        for uid in user_ids:
            self.merge_similar_memories(uid)

        # 3. 数据库优化（如果是SQLite）
        if isinstance(self.long_term, SQLiteMemoryStore):
            self.long_term.vacuum()

        logger.info("记忆系统维护完成")

    def flush(self):
        """强制保存所有持久化数据"""
        if isinstance(self.long_term, PersistentMemoryStore):
            self.long_term.flush()
        if self._profile_store:
            self._profile_store.flush()
        logger.info("记忆系统数据已保存")

    def shutdown(self):
        """关闭记忆管理器，保存所有数据"""
        self.flush()
        logger.info("记忆管理器已关闭")

    def get_stats(self) -> Dict:
        """获取记忆系统统计信息"""
        stats = {
            "short_term": self.short_term.stats(),
            "long_term": self.long_term.stats(),
            "working": self.working.stats(),
            "user_profiles_count": len(self.user_profiles),
            "conversation_summaries_count": len(self.conversation_summaries),
            "kg_nodes_count": len(self.kg_nodes),
            "kg_edges_count": len(self.kg_edges),
        }
        return stats


# 全局记忆管理器实例
_memory_manager: Optional[MemoryManager] = None
_memory_lock = threading.Lock()


def get_memory_manager() -> MemoryManager:
    """
    获取全局记忆管理器

    从环境变量读取配置：
    - MEMORY_PERSIST: 是否持久化 (true/false)
    - MEMORY_BACKEND: 后端类型 (memory/file/sqlite/redis)
    """
    global _memory_manager
    if _memory_manager is None:
        with _memory_lock:
            if _memory_manager is None:
                # 从环境变量读取配置
                use_persistence = os.environ.get("MEMORY_PERSIST", "true").lower() == "true"
                backend = os.environ.get("MEMORY_BACKEND", "sqlite")

                # Redis 配置
                redis_config = None
                if backend == "redis":
                    redis_config = {
                        "host": os.environ.get("REDIS_HOST", "localhost"),
                        "port": int(os.environ.get("REDIS_PORT", 6379)),
                        "password": os.environ.get("REDIS_PASSWORD"),
                    }

                _memory_manager = MemoryManager(
                    use_persistence=use_persistence,
                    backend=backend,
                    redis_config=redis_config,
                )
    return _memory_manager
