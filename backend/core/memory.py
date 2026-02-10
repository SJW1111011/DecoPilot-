"""
高级记忆系统
支持短期记忆、长期记忆、工作记忆和知识图谱
"""
import json
import time
import hashlib
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict, field
from datetime import datetime, timedelta
from enum import Enum
from abc import ABC, abstractmethod
import threading


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
    """内存存储实现"""

    def __init__(self, max_size: int = 10000):
        self.store: Dict[str, MemoryItem] = {}
        self.max_size = max_size
        self._lock = threading.Lock()

    def save(self, item: MemoryItem) -> bool:
        with self._lock:
            if len(self.store) >= self.max_size:
                self._evict_oldest()
            self.store[item.id] = item
            return True

    def get(self, item_id: str) -> Optional[MemoryItem]:
        item = self.store.get(item_id)
        if item:
            item.access_count += 1
            item.last_access = time.time()
        return item

    def search(self, query: str, limit: int = 10) -> List[MemoryItem]:
        # 简单的关键词匹配搜索
        results = []
        query_lower = query.lower()
        for item in self.store.values():
            content_str = str(item.content).lower()
            if query_lower in content_str:
                results.append(item)
        # 按重要性和访问时间排序
        results.sort(key=lambda x: (x.importance, x.last_access), reverse=True)
        return results[:limit]

    def delete(self, item_id: str) -> bool:
        with self._lock:
            if item_id in self.store:
                del self.store[item_id]
                return True
            return False

    def _evict_oldest(self):
        """淘汰最旧的记忆"""
        if not self.store:
            return
        # 按最后访问时间排序，删除最旧的10%
        items = sorted(self.store.values(), key=lambda x: x.last_access)
        evict_count = max(1, len(items) // 10)
        for item in items[:evict_count]:
            del self.store[item.id]


class MemoryManager:
    """记忆管理器"""

    def __init__(self):
        self.short_term = InMemoryStore(max_size=1000)
        self.long_term = InMemoryStore(max_size=100000)
        self.working = InMemoryStore(max_size=100)

        self.user_profiles: Dict[str, UserProfile] = {}
        self.conversation_summaries: Dict[str, ConversationSummary] = {}

        # 知识图谱
        self.kg_nodes: Dict[str, KnowledgeNode] = {}
        self.kg_edges: List[KnowledgeEdge] = []

        self._lock = threading.Lock()

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


# 全局记忆管理器实例
_memory_manager: Optional[MemoryManager] = None
_memory_lock = threading.Lock()


def get_memory_manager() -> MemoryManager:
    """获取全局记忆管理器"""
    global _memory_manager
    if _memory_manager is None:
        with _memory_lock:
            if _memory_manager is None:
                _memory_manager = MemoryManager()
    return _memory_manager
