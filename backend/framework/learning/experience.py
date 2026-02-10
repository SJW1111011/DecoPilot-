"""
经验回放

存储和回放历史经验，用于强化学习和持续改进
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
import asyncio
import logging
import json
import random
from pathlib import Path
from collections import deque

from ..events import Event, EventType, get_event_bus
from ..config import LearningConfig

logger = logging.getLogger(__name__)


@dataclass
class Experience:
    """经验数据"""
    id: str
    state: Dict[str, Any]  # 状态（查询、上下文等）
    action: Dict[str, Any]  # 动作（策略、工具调用等）
    reward: float  # 奖励（基于反馈计算）
    next_state: Optional[Dict[str, Any]] = None  # 下一状态
    done: bool = False  # 是否结束
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "id": self.id,
            "state": self.state,
            "action": self.action,
            "reward": self.reward,
            "next_state": self.next_state,
            "done": self.done,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Experience":
        """从字典创建"""
        data = data.copy()
        if isinstance(data["timestamp"], str):
            data["timestamp"] = datetime.fromisoformat(data["timestamp"])
        return cls(**data)


class ExperienceReplay:
    """
    经验回放缓冲区

    功能:
    - 存储历史经验
    - 优先级经验回放
    - 批量采样
    - 经验持久化

    使用示例:
    ```python
    replay = ExperienceReplay(capacity=10000)

    # 添加经验
    await replay.add(experience)

    # 采样批次
    batch = replay.sample(batch_size=32)

    # 更新优先级
    replay.update_priorities(indices, priorities)
    ```
    """

    def __init__(
        self,
        capacity: int = 10000,
        config: LearningConfig = None
    ):
        self._capacity = capacity
        self._config = config or LearningConfig()
        self._event_bus = get_event_bus()

        # 经验缓冲区
        self._buffer: deque = deque(maxlen=capacity)

        # 优先级（用于优先级经验回放）
        self._priorities: List[float] = []

        # 经验计数器
        self._experience_counter = 0

        # 持久化路径
        self._persistence_path = Path(self._config.learning_data_path) / "experience"
        self._persistence_path.mkdir(parents=True, exist_ok=True)

        # 加载历史经验
        self._load_experiences()

    def _load_experiences(self) -> None:
        """加载历史经验"""
        experience_file = self._persistence_path / "experiences.jsonl"
        if experience_file.exists():
            try:
                with open(experience_file, "r", encoding="utf-8") as f:
                    for line in f:
                        if line.strip():
                            exp = Experience.from_dict(json.loads(line))
                            self._buffer.append(exp)
                            self._priorities.append(1.0)  # 默认优先级

                logger.info(f"Loaded {len(self._buffer)} experiences")
            except Exception as e:
                logger.error(f"Failed to load experiences: {e}")

    def _save_experience(self, experience: Experience) -> None:
        """保存单个经验"""
        experience_file = self._persistence_path / "experiences.jsonl"
        try:
            with open(experience_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(experience.to_dict(), ensure_ascii=False) + "\n")
        except Exception as e:
            logger.error(f"Failed to save experience: {e}")

    async def add(
        self,
        state: Dict[str, Any],
        action: Dict[str, Any],
        reward: float,
        next_state: Optional[Dict[str, Any]] = None,
        done: bool = False,
        priority: float = 1.0,
        **metadata
    ) -> Experience:
        """
        添加经验

        Args:
            state: 当前状态
            action: 执行的动作
            reward: 获得的奖励
            next_state: 下一状态
            done: 是否结束
            priority: 优先级
            **metadata: 额外元数据

        Returns:
            经验对象
        """
        self._experience_counter += 1
        experience = Experience(
            id=f"exp_{self._experience_counter}",
            state=state,
            action=action,
            reward=reward,
            next_state=next_state,
            done=done,
            metadata=metadata
        )

        # 添加到缓冲区
        if len(self._buffer) >= self._capacity:
            self._priorities.pop(0)

        self._buffer.append(experience)
        self._priorities.append(priority)

        # 持久化
        self._save_experience(experience)

        return experience

    def sample(
        self,
        batch_size: int = 32,
        prioritized: bool = True
    ) -> Tuple[List[Experience], List[int]]:
        """
        采样经验批次

        Args:
            batch_size: 批次大小
            prioritized: 是否使用优先级采样

        Returns:
            (经验列表, 索引列表)
        """
        if len(self._buffer) == 0:
            return [], []

        batch_size = min(batch_size, len(self._buffer))

        if prioritized and self._priorities:
            # 优先级采样
            total_priority = sum(self._priorities)
            probabilities = [p / total_priority for p in self._priorities]
            indices = random.choices(
                range(len(self._buffer)),
                weights=probabilities,
                k=batch_size
            )
        else:
            # 均匀采样
            indices = random.sample(range(len(self._buffer)), batch_size)

        experiences = [self._buffer[i] for i in indices]
        return experiences, indices

    def update_priorities(
        self,
        indices: List[int],
        priorities: List[float]
    ) -> None:
        """
        更新优先级

        Args:
            indices: 经验索引
            priorities: 新优先级
        """
        for idx, priority in zip(indices, priorities):
            if 0 <= idx < len(self._priorities):
                self._priorities[idx] = max(0.01, priority)  # 最小优先级

    def get_recent(self, n: int = 10) -> List[Experience]:
        """获取最近的经验"""
        return list(self._buffer)[-n:]

    def get_high_reward(self, n: int = 10, threshold: float = 0.8) -> List[Experience]:
        """获取高奖励的经验"""
        high_reward = [exp for exp in self._buffer if exp.reward >= threshold]
        return sorted(high_reward, key=lambda e: e.reward, reverse=True)[:n]

    def get_low_reward(self, n: int = 10, threshold: float = 0.2) -> List[Experience]:
        """获取低奖励的经验（用于分析失败案例）"""
        low_reward = [exp for exp in self._buffer if exp.reward <= threshold]
        return sorted(low_reward, key=lambda e: e.reward)[:n]

    def calculate_reward(
        self,
        success: bool,
        response_time: float,
        rating: Optional[float] = None,
        retry_count: int = 0
    ) -> float:
        """
        计算奖励

        Args:
            success: 是否成功
            response_time: 响应时间
            rating: 用户评分
            retry_count: 重试次数

        Returns:
            奖励值 (0-1)
        """
        reward = 0.0

        # 成功奖励
        if success:
            reward += 0.4

        # 响应时间奖励（越快越好）
        time_reward = max(0, 1 - response_time / 10) * 0.2
        reward += time_reward

        # 用户评分奖励
        if rating is not None:
            rating_reward = (rating / 5) * 0.3
            reward += rating_reward
        else:
            reward += 0.15  # 没有评分时给中等奖励

        # 重试惩罚
        retry_penalty = min(0.1, retry_count * 0.03)
        reward -= retry_penalty

        return max(0.0, min(1.0, reward))

    def clear(self) -> None:
        """清空缓冲区"""
        self._buffer.clear()
        self._priorities.clear()

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        if not self._buffer:
            return {
                "size": 0,
                "capacity": self._capacity,
                "avg_reward": 0.0,
                "max_reward": 0.0,
                "min_reward": 0.0
            }

        rewards = [exp.reward for exp in self._buffer]

        return {
            "size": len(self._buffer),
            "capacity": self._capacity,
            "avg_reward": sum(rewards) / len(rewards),
            "max_reward": max(rewards),
            "min_reward": min(rewards),
            "avg_priority": sum(self._priorities) / len(self._priorities) if self._priorities else 0.0
        }

    def __len__(self) -> int:
        return len(self._buffer)
