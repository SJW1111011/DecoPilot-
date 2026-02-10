"""
事件类型定义

定义框架中使用的所有事件类型和事件数据结构
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional
from uuid import uuid4


class EventPriority(Enum):
    """事件优先级"""
    LOW = 0
    NORMAL = 1
    HIGH = 2
    CRITICAL = 3


class EventType(str, Enum):
    """预定义的事件类型"""

    # ==================== 生命周期事件 ====================
    SYSTEM_STARTED = "system.started"
    SYSTEM_STOPPED = "system.stopped"
    AGENT_REGISTERED = "agent.registered"
    AGENT_UNREGISTERED = "agent.unregistered"
    AGENT_STARTED = "agent.started"
    AGENT_STOPPED = "agent.stopped"

    # ==================== 请求处理事件 ====================
    REQUEST_RECEIVED = "request.received"
    REQUEST_VALIDATED = "request.validated"
    REQUEST_ROUTED = "request.routed"
    REQUEST_COMPLETED = "request.completed"
    REQUEST_FAILED = "request.failed"

    # ==================== 上下文事件 ====================
    CONTEXT_LOADING = "context.loading"
    CONTEXT_LOADED = "context.loaded"
    USER_PROFILE_LOADED = "user_profile.loaded"
    USER_PROFILE_UPDATED = "user_profile.updated"

    # ==================== 推理事件 ====================
    REASONING_STARTED = "reasoning.started"
    REASONING_STEP = "reasoning.step"
    REASONING_COMPLETED = "reasoning.completed"
    REASONING_FAILED = "reasoning.failed"
    STRATEGY_SELECTED = "strategy.selected"
    STRATEGY_SWITCHED = "strategy.switched"

    # ==================== 工具事件 ====================
    TOOL_CALLING = "tool.calling"
    TOOL_CALLED = "tool.called"
    TOOL_COMPLETED = "tool.completed"
    TOOL_FAILED = "tool.failed"
    TOOL_TIMEOUT = "tool.timeout"

    # ==================== 记忆事件 ====================
    MEMORY_STORING = "memory.storing"
    MEMORY_STORED = "memory.stored"
    MEMORY_RETRIEVING = "memory.retrieving"
    MEMORY_RETRIEVED = "memory.retrieved"
    MEMORY_EVICTED = "memory.evicted"

    # ==================== 知识库事件 ====================
    KNOWLEDGE_SEARCHING = "knowledge.searching"
    KNOWLEDGE_FOUND = "knowledge.found"
    KNOWLEDGE_NOT_FOUND = "knowledge.not_found"
    KNOWLEDGE_ADDED = "knowledge.added"

    # ==================== 多模态事件 ====================
    MEDIA_PROCESSING = "media.processing"
    MEDIA_PROCESSED = "media.processed"
    MEDIA_FAILED = "media.failed"

    # ==================== 输出事件 ====================
    OUTPUT_GENERATING = "output.generating"
    OUTPUT_STREAMING = "output.streaming"
    OUTPUT_COMPLETED = "output.completed"
    STRUCTURED_OUTPUT = "output.structured"

    # ==================== 编排事件 ====================
    PLAN_CREATING = "plan.creating"
    PLAN_CREATED = "plan.created"
    PLAN_STEP_STARTED = "plan.step.started"
    PLAN_STEP_COMPLETED = "plan.step.completed"
    PLAN_REPLANNING = "plan.replanning"
    COLLABORATION_STARTED = "collaboration.started"
    COLLABORATION_COMPLETED = "collaboration.completed"

    # ==================== 学习事件 ====================
    FEEDBACK_RECEIVED = "feedback.received"
    FEEDBACK_PROCESSED = "feedback.processed"
    LEARNING_STARTED = "learning.started"
    LEARNING_COMPLETED = "learning.completed"
    MODEL_UPDATED = "model.updated"
    STRATEGY_OPTIMIZED = "strategy.optimized"
    KNOWLEDGE_DISTILLED = "knowledge.distilled"

    # ==================== 错误事件 ====================
    ERROR_OCCURRED = "error.occurred"
    ERROR_RECOVERED = "error.recovered"
    RATE_LIMITED = "rate.limited"
    TIMEOUT_OCCURRED = "timeout.occurred"

    # ==================== 监控事件 ====================
    METRICS_COLLECTED = "metrics.collected"
    HEALTH_CHECK = "health.check"
    PERFORMANCE_ALERT = "performance.alert"


@dataclass
class Event:
    """
    事件数据结构

    Attributes:
        type: 事件类型
        payload: 事件负载数据
        timestamp: 事件发生时间
        trace_id: 追踪ID，用于分布式追踪
        span_id: Span ID
        parent_span_id: 父 Span ID
        source: 事件来源（模块名）
        priority: 事件优先级
        metadata: 额外元数据
    """
    type: EventType | str
    payload: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)
    trace_id: str = field(default_factory=lambda: str(uuid4()))
    span_id: str = field(default_factory=lambda: str(uuid4())[:8])
    parent_span_id: Optional[str] = None
    source: str = "unknown"
    priority: EventPriority = EventPriority.NORMAL
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """确保 type 是字符串"""
        if isinstance(self.type, EventType):
            self.type = self.type.value

    def with_child_span(self, source: str = None) -> "Event":
        """创建子事件（用于追踪）"""
        return Event(
            type=self.type,
            payload=self.payload.copy(),
            trace_id=self.trace_id,
            parent_span_id=self.span_id,
            source=source or self.source,
            priority=self.priority,
            metadata=self.metadata.copy()
        )

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "type": self.type,
            "payload": self.payload,
            "timestamp": self.timestamp.isoformat(),
            "trace_id": self.trace_id,
            "span_id": self.span_id,
            "parent_span_id": self.parent_span_id,
            "source": self.source,
            "priority": self.priority.value if isinstance(self.priority, EventPriority) else self.priority,
            "metadata": self.metadata
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Event":
        """从字典创建事件"""
        data = data.copy()
        if "timestamp" in data and isinstance(data["timestamp"], str):
            data["timestamp"] = datetime.fromisoformat(data["timestamp"])
        if "priority" in data and isinstance(data["priority"], int):
            data["priority"] = EventPriority(data["priority"])
        return cls(**data)


@dataclass
class EventFilter:
    """事件过滤器"""
    types: Optional[list] = None
    sources: Optional[list] = None
    min_priority: EventPriority = EventPriority.LOW
    trace_id: Optional[str] = None

    def matches(self, event: Event) -> bool:
        """检查事件是否匹配过滤条件"""
        if self.types and event.type not in self.types:
            return False
        if self.sources and event.source not in self.sources:
            return False
        if event.priority.value < self.min_priority.value:
            return False
        if self.trace_id and event.trace_id != self.trace_id:
            return False
        return True
