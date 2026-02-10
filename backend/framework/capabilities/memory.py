"""
记忆能力

提供智能体的记忆管理能力:
- 短期记忆: 当前对话上下文
- 长期记忆: 用户画像、历史偏好
- 工作记忆: 当前任务状态
- 情景记忆: 历史事件记录
- 语义记忆: 知识图谱
"""

from abc import abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Protocol, runtime_checkable
from enum import Enum
import asyncio
import logging

from .base import CapabilityMixin, register_capability
from ..events import Event, EventType, get_event_bus
from ..config import MemoryConfig

logger = logging.getLogger(__name__)


class MemoryType(str, Enum):
    """记忆类型"""
    SHORT_TERM = "short_term"
    LONG_TERM = "long_term"
    WORKING = "working"
    EPISODIC = "episodic"
    SEMANTIC = "semantic"


@dataclass
class Memory:
    """记忆单元"""
    id: str
    content: str
    type: MemoryType
    importance: float = 0.5
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)
    embedding: Optional[List[float]] = None
    access_count: int = 0
    last_accessed: Optional[datetime] = None

    def touch(self) -> None:
        """更新访问信息"""
        self.access_count += 1
        self.last_accessed = datetime.now()


@dataclass
class MemoryContext:
    """记忆上下文"""
    short_term: List[Memory] = field(default_factory=list)
    long_term: List[Memory] = field(default_factory=list)
    working: Dict[str, Any] = field(default_factory=dict)
    user_profile: Optional[Dict[str, Any]] = None

    def to_prompt(self) -> str:
        """转换为提示词格式"""
        parts = []

        if self.user_profile:
            parts.append(f"用户画像: {self.user_profile}")

        if self.long_term:
            long_term_str = "\n".join([m.content for m in self.long_term[:5]])
            parts.append(f"历史记忆:\n{long_term_str}")

        if self.short_term:
            short_term_str = "\n".join([m.content for m in self.short_term[-10:]])
            parts.append(f"近期对话:\n{short_term_str}")

        if self.working:
            parts.append(f"当前任务状态: {self.working}")

        return "\n\n".join(parts)


@runtime_checkable
class MemoryCapability(Protocol):
    """记忆能力协议"""

    async def remember(
        self,
        content: str,
        memory_type: MemoryType = MemoryType.SHORT_TERM,
        importance: float = 0.5,
        metadata: Dict[str, Any] = None
    ) -> Memory:
        """存储记忆"""
        ...

    async def recall(
        self,
        query: str,
        memory_type: Optional[MemoryType] = None,
        k: int = 5
    ) -> List[Memory]:
        """检索记忆"""
        ...

    async def forget(
        self,
        memory_id: str
    ) -> bool:
        """删除记忆"""
        ...

    async def get_context(
        self,
        user_id: str,
        session_id: str,
        query: Optional[str] = None
    ) -> MemoryContext:
        """获取记忆上下文"""
        ...

    async def update_user_profile(
        self,
        user_id: str,
        updates: Dict[str, Any]
    ) -> None:
        """更新用户画像"""
        ...


@register_capability("memory", version="2.0.0", description="记忆管理能力")
class MemoryMixin(CapabilityMixin):
    """
    记忆能力混入

    提供完整的记忆管理功能，包括:
    - 多类型记忆存储
    - 基于重要性的记忆淘汰
    - 向量化检索
    - 用户画像管理
    """

    _capability_name = "memory"
    _capability_version = "2.0.0"

    def __init__(self, config: MemoryConfig = None):
        super().__init__()
        self._memory_config = config or MemoryConfig()
        self._memories: Dict[str, Dict[str, Memory]] = {
            MemoryType.SHORT_TERM.value: {},
            MemoryType.LONG_TERM.value: {},
            MemoryType.WORKING.value: {},
            MemoryType.EPISODIC.value: {},
            MemoryType.SEMANTIC.value: {},
        }
        self._user_profiles: Dict[str, Dict[str, Any]] = {}
        self._event_bus = get_event_bus()
        self._memory_counter = 0

    async def _do_initialize(self) -> None:
        """初始化记忆系统"""
        # 可以在这里加载持久化的记忆
        logger.info("Memory system initialized")

    async def _do_shutdown(self) -> None:
        """关闭记忆系统"""
        # 可以在这里持久化记忆
        logger.info("Memory system shutdown")

    async def remember(
        self,
        content: str,
        memory_type: MemoryType = MemoryType.SHORT_TERM,
        importance: float = 0.5,
        metadata: Dict[str, Any] = None
    ) -> Memory:
        """存储记忆"""
        self._memory_counter += 1
        memory_id = f"mem_{self._memory_counter}_{memory_type.value}"

        memory = Memory(
            id=memory_id,
            content=content,
            type=memory_type,
            importance=importance,
            metadata=metadata or {}
        )

        # 存储
        self._memories[memory_type.value][memory_id] = memory

        # 检查容量限制
        await self._check_capacity(memory_type)

        # 发布事件
        await self._event_bus.emit(Event(
            type=EventType.MEMORY_STORED,
            payload={
                "memory_id": memory_id,
                "memory_type": memory_type.value,
                "importance": importance
            },
            source="memory"
        ))

        return memory

    async def recall(
        self,
        query: str,
        memory_type: Optional[MemoryType] = None,
        k: int = 5
    ) -> List[Memory]:
        """检索记忆"""
        await self._event_bus.emit(Event(
            type=EventType.MEMORY_RETRIEVING,
            payload={"query": query, "memory_type": memory_type, "k": k},
            source="memory"
        ))

        results = []

        # 确定要搜索的记忆类型
        types_to_search = [memory_type.value] if memory_type else list(self._memories.keys())

        for mt in types_to_search:
            memories = list(self._memories[mt].values())

            # 简单的关键词匹配（实际应用中应使用向量检索）
            for memory in memories:
                if query.lower() in memory.content.lower():
                    memory.touch()
                    results.append(memory)

        # 按重要性和访问时间排序
        results.sort(key=lambda m: (m.importance, m.access_count), reverse=True)

        await self._event_bus.emit(Event(
            type=EventType.MEMORY_RETRIEVED,
            payload={"query": query, "count": len(results[:k])},
            source="memory"
        ))

        return results[:k]

    async def forget(self, memory_id: str) -> bool:
        """删除记忆"""
        for memories in self._memories.values():
            if memory_id in memories:
                del memories[memory_id]
                return True
        return False

    async def get_context(
        self,
        user_id: str,
        session_id: str,
        query: Optional[str] = None
    ) -> MemoryContext:
        """获取记忆上下文"""
        context = MemoryContext()

        # 获取用户画像
        context.user_profile = self._user_profiles.get(user_id)

        # 获取短期记忆（当前会话）
        short_term = list(self._memories[MemoryType.SHORT_TERM.value].values())
        context.short_term = [m for m in short_term if m.metadata.get("session_id") == session_id]

        # 获取长期记忆
        if query:
            context.long_term = await self.recall(query, MemoryType.LONG_TERM, k=5)
        else:
            long_term = list(self._memories[MemoryType.LONG_TERM.value].values())
            context.long_term = sorted(long_term, key=lambda m: m.importance, reverse=True)[:5]

        # 获取工作记忆
        working = self._memories[MemoryType.WORKING.value]
        context.working = {m.id: m.content for m in working.values() if m.metadata.get("session_id") == session_id}

        return context

    async def update_user_profile(
        self,
        user_id: str,
        updates: Dict[str, Any]
    ) -> None:
        """更新用户画像"""
        if user_id not in self._user_profiles:
            self._user_profiles[user_id] = {
                "user_id": user_id,
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat()
            }

        self._user_profiles[user_id].update(updates)
        self._user_profiles[user_id]["updated_at"] = datetime.now().isoformat()

        await self._event_bus.emit(Event(
            type=EventType.USER_PROFILE_UPDATED,
            payload={"user_id": user_id, "updates": list(updates.keys())},
            source="memory"
        ))

    async def get_user_profile(self, user_id: str) -> Optional[Dict[str, Any]]:
        """获取用户画像"""
        return self._user_profiles.get(user_id)

    async def set_working_memory(
        self,
        session_id: str,
        key: str,
        value: Any
    ) -> None:
        """设置工作记忆"""
        memory_id = f"working_{session_id}_{key}"
        await self.remember(
            content=str(value),
            memory_type=MemoryType.WORKING,
            importance=0.8,
            metadata={"session_id": session_id, "key": key}
        )

    async def get_working_memory(
        self,
        session_id: str,
        key: str
    ) -> Optional[Any]:
        """获取工作记忆"""
        memory_id = f"working_{session_id}_{key}"
        memory = self._memories[MemoryType.WORKING.value].get(memory_id)
        return memory.content if memory else None

    async def _check_capacity(self, memory_type: MemoryType) -> None:
        """检查并执行容量限制"""
        memories = self._memories[memory_type.value]

        # 获取容量限制
        if memory_type == MemoryType.SHORT_TERM:
            max_items = self._memory_config.short_term_max_items
        elif memory_type == MemoryType.LONG_TERM:
            max_items = self._memory_config.long_term_max_items
        else:
            max_items = self._memory_config.working_memory_size

        # 如果超出容量，淘汰低重要性的记忆
        if len(memories) > max_items:
            sorted_memories = sorted(
                memories.values(),
                key=lambda m: (m.importance, m.access_count)
            )
            to_remove = sorted_memories[:len(memories) - max_items]

            for memory in to_remove:
                del memories[memory.id]
                await self._event_bus.emit(Event(
                    type=EventType.MEMORY_EVICTED,
                    payload={"memory_id": memory.id, "reason": "capacity"},
                    source="memory"
                ))

    def get_stats(self) -> Dict[str, Any]:
        """获取记忆统计"""
        return {
            "total_memories": sum(len(m) for m in self._memories.values()),
            "by_type": {k: len(v) for k, v in self._memories.items()},
            "user_profiles": len(self._user_profiles)
        }
