"""
反馈收集器

收集和管理用户反馈，支持显式和隐式反馈
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional
from enum import Enum
import asyncio
import logging
import json
from pathlib import Path

from ..events import Event, EventType, get_event_bus
from ..config import LearningConfig

logger = logging.getLogger(__name__)


class FeedbackType(str, Enum):
    """反馈类型"""
    # 显式反馈
    RATING = "rating"  # 评分（1-5）
    THUMBS = "thumbs"  # 点赞/点踩
    COMMENT = "comment"  # 文字评论
    CORRECTION = "correction"  # 纠正

    # 隐式反馈
    RESPONSE_TIME = "response_time"  # 响应时间
    RETRY_COUNT = "retry_count"  # 重试次数
    SESSION_LENGTH = "session_length"  # 会话长度
    FOLLOW_UP = "follow_up"  # 追问
    ABANDONMENT = "abandonment"  # 放弃
    TOOL_USAGE = "tool_usage"  # 工具使用
    STRATEGY_EFFECTIVENESS = "strategy_effectiveness"  # 策略有效性


@dataclass
class Feedback:
    """反馈数据"""
    id: str
    type: FeedbackType
    value: Any
    request_id: str
    session_id: str
    user_id: str
    agent_name: str
    query: str
    response: str
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "id": self.id,
            "type": self.type.value,
            "value": self.value,
            "request_id": self.request_id,
            "session_id": self.session_id,
            "user_id": self.user_id,
            "agent_name": self.agent_name,
            "query": self.query,
            "response": self.response,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Feedback":
        """从字典创建"""
        data = data.copy()
        data["type"] = FeedbackType(data["type"])
        if isinstance(data["timestamp"], str):
            data["timestamp"] = datetime.fromisoformat(data["timestamp"])
        return cls(**data)


class FeedbackCollector:
    """
    反馈收集器

    功能:
    - 收集显式反馈（用户评分、评论）
    - 收集隐式反馈（响应时间、重试次数等）
    - 反馈聚合和分析
    - 反馈持久化

    使用示例:
    ```python
    collector = FeedbackCollector()

    # 收集显式反馈
    await collector.collect_explicit(
        feedback_type=FeedbackType.RATING,
        value=5,
        request_id="req_123",
        ...
    )

    # 收集隐式反馈
    await collector.collect_implicit(
        feedback_type=FeedbackType.RESPONSE_TIME,
        value=2.5,
        ...
    )

    # 获取反馈统计
    stats = collector.get_stats()
    ```
    """

    def __init__(self, config: LearningConfig = None):
        self._config = config or LearningConfig()
        self._event_bus = get_event_bus()
        self._feedbacks: List[Feedback] = []
        self._feedback_counter = 0
        self._persistence_path = Path(self._config.learning_data_path) / "feedback"
        self._persistence_path.mkdir(parents=True, exist_ok=True)

        # 订阅相关事件以收集隐式反馈
        self._setup_event_listeners()

    def _setup_event_listeners(self) -> None:
        """设置事件监听器"""
        if not self._config.implicit_feedback:
            return

        @self._event_bus.on(EventType.REQUEST_COMPLETED)
        async def on_request_completed(event: Event):
            # 收集响应时间
            if "execution_time" in event.payload:
                await self.collect_implicit(
                    feedback_type=FeedbackType.RESPONSE_TIME,
                    value=event.payload["execution_time"],
                    request_id=event.payload.get("request_id", ""),
                    session_id=event.metadata.get("session_id", ""),
                    user_id=event.metadata.get("user_id", ""),
                    agent_name=event.payload.get("agent_name", ""),
                    query="",
                    response=""
                )

        @self._event_bus.on(EventType.REASONING_COMPLETED)
        async def on_reasoning_completed(event: Event):
            # 收集策略有效性
            await self.collect_implicit(
                feedback_type=FeedbackType.STRATEGY_EFFECTIVENESS,
                value={
                    "strategy": event.payload.get("strategy"),
                    "steps": event.payload.get("steps"),
                    "confidence": event.payload.get("confidence")
                },
                request_id=event.trace_id,
                session_id="",
                user_id="",
                agent_name="",
                query="",
                response=""
            )

    async def collect_explicit(
        self,
        feedback_type: FeedbackType,
        value: Any,
        request_id: str,
        session_id: str,
        user_id: str,
        agent_name: str,
        query: str,
        response: str,
        **metadata
    ) -> Feedback:
        """
        收集显式反馈

        Args:
            feedback_type: 反馈类型
            value: 反馈值
            request_id: 请求ID
            session_id: 会话ID
            user_id: 用户ID
            agent_name: 智能体名称
            query: 用户查询
            response: 智能体响应
            **metadata: 额外元数据

        Returns:
            反馈对象
        """
        if not self._config.explicit_feedback:
            return None

        self._feedback_counter += 1
        feedback = Feedback(
            id=f"fb_{self._feedback_counter}",
            type=feedback_type,
            value=value,
            request_id=request_id,
            session_id=session_id,
            user_id=user_id,
            agent_name=agent_name,
            query=query,
            response=response,
            metadata=metadata
        )

        self._feedbacks.append(feedback)

        await self._event_bus.emit(Event(
            type=EventType.FEEDBACK_RECEIVED,
            payload={
                "feedback_id": feedback.id,
                "feedback_type": feedback_type.value,
                "value": value
            },
            source="feedback_collector"
        ))

        # 持久化
        await self._persist_feedback(feedback)

        return feedback

    async def collect_implicit(
        self,
        feedback_type: FeedbackType,
        value: Any,
        request_id: str,
        session_id: str,
        user_id: str,
        agent_name: str,
        query: str,
        response: str,
        **metadata
    ) -> Feedback:
        """收集隐式反馈"""
        if not self._config.implicit_feedback:
            return None

        self._feedback_counter += 1
        feedback = Feedback(
            id=f"fb_{self._feedback_counter}",
            type=feedback_type,
            value=value,
            request_id=request_id,
            session_id=session_id,
            user_id=user_id,
            agent_name=agent_name,
            query=query,
            response=response,
            metadata={"implicit": True, **metadata}
        )

        self._feedbacks.append(feedback)

        # 隐式反馈不发送事件，避免噪音
        # 但仍然持久化
        await self._persist_feedback(feedback)

        return feedback

    async def _persist_feedback(self, feedback: Feedback) -> None:
        """持久化反馈"""
        try:
            # 按日期分文件存储
            date_str = feedback.timestamp.strftime("%Y-%m-%d")
            file_path = self._persistence_path / f"feedback_{date_str}.jsonl"

            with open(file_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(feedback.to_dict(), ensure_ascii=False) + "\n")
        except Exception as e:
            logger.error(f"Failed to persist feedback: {e}")

    async def load_feedbacks(
        self,
        start_date: datetime = None,
        end_date: datetime = None
    ) -> List[Feedback]:
        """加载历史反馈"""
        feedbacks = []

        for file_path in self._persistence_path.glob("feedback_*.jsonl"):
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    for line in f:
                        if line.strip():
                            feedback = Feedback.from_dict(json.loads(line))

                            # 日期过滤
                            if start_date and feedback.timestamp < start_date:
                                continue
                            if end_date and feedback.timestamp > end_date:
                                continue

                            feedbacks.append(feedback)
            except Exception as e:
                logger.error(f"Failed to load feedback from {file_path}: {e}")

        return feedbacks

    def get_feedbacks(
        self,
        feedback_type: FeedbackType = None,
        agent_name: str = None,
        user_id: str = None,
        limit: int = 100
    ) -> List[Feedback]:
        """获取反馈"""
        feedbacks = self._feedbacks

        if feedback_type:
            feedbacks = [f for f in feedbacks if f.type == feedback_type]
        if agent_name:
            feedbacks = [f for f in feedbacks if f.agent_name == agent_name]
        if user_id:
            feedbacks = [f for f in feedbacks if f.user_id == user_id]

        return feedbacks[-limit:]

    def get_stats(self, agent_name: str = None) -> Dict[str, Any]:
        """获取反馈统计"""
        feedbacks = self._feedbacks
        if agent_name:
            feedbacks = [f for f in feedbacks if f.agent_name == agent_name]

        if not feedbacks:
            return {
                "total_feedbacks": 0,
                "by_type": {},
                "avg_rating": None,
                "positive_rate": None
            }

        # 按类型统计
        by_type = {}
        for f in feedbacks:
            by_type[f.type.value] = by_type.get(f.type.value, 0) + 1

        # 计算平均评分
        ratings = [f.value for f in feedbacks if f.type == FeedbackType.RATING and isinstance(f.value, (int, float))]
        avg_rating = sum(ratings) / len(ratings) if ratings else None

        # 计算正面反馈率
        thumbs = [f.value for f in feedbacks if f.type == FeedbackType.THUMBS]
        positive_rate = sum(1 for t in thumbs if t > 0) / len(thumbs) if thumbs else None

        # 计算平均响应时间
        response_times = [f.value for f in feedbacks if f.type == FeedbackType.RESPONSE_TIME and isinstance(f.value, (int, float))]
        avg_response_time = sum(response_times) / len(response_times) if response_times else None

        return {
            "total_feedbacks": len(feedbacks),
            "by_type": by_type,
            "avg_rating": avg_rating,
            "positive_rate": positive_rate,
            "avg_response_time": avg_response_time
        }

    def get_agent_performance(self, agent_name: str) -> Dict[str, Any]:
        """获取智能体性能指标"""
        feedbacks = [f for f in self._feedbacks if f.agent_name == agent_name]

        if not feedbacks:
            return {"agent_name": agent_name, "no_data": True}

        # 计算各项指标
        ratings = [f.value for f in feedbacks if f.type == FeedbackType.RATING]
        response_times = [f.value for f in feedbacks if f.type == FeedbackType.RESPONSE_TIME]
        retry_counts = [f.value for f in feedbacks if f.type == FeedbackType.RETRY_COUNT]

        return {
            "agent_name": agent_name,
            "total_interactions": len(feedbacks),
            "avg_rating": sum(ratings) / len(ratings) if ratings else None,
            "avg_response_time": sum(response_times) / len(response_times) if response_times else None,
            "avg_retry_count": sum(retry_counts) / len(retry_counts) if retry_counts else None,
            "feedback_distribution": {
                ft.value: len([f for f in feedbacks if f.type == ft])
                for ft in FeedbackType
            }
        }
