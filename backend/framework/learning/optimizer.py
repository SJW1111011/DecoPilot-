"""
策略优化器

基于反馈数据优化智能体的推理策略和行为
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
from enum import Enum
import asyncio
import logging
import json
from pathlib import Path
import random

from ..events import Event, EventType, get_event_bus
from ..config import LearningConfig, ReasoningStrategy
from .feedback import FeedbackCollector, Feedback, FeedbackType

logger = logging.getLogger(__name__)


@dataclass
class OptimizationResult:
    """优化结果"""
    success: bool
    strategy: str
    old_params: Dict[str, Any]
    new_params: Dict[str, Any]
    improvement: float
    confidence: float
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class StrategyPerformance:
    """策略性能数据"""
    strategy: ReasoningStrategy
    total_uses: int = 0
    success_count: int = 0
    total_time: float = 0.0
    total_rating: float = 0.0
    rating_count: int = 0

    @property
    def success_rate(self) -> float:
        return self.success_count / self.total_uses if self.total_uses > 0 else 0.0

    @property
    def avg_time(self) -> float:
        return self.total_time / self.total_uses if self.total_uses > 0 else 0.0

    @property
    def avg_rating(self) -> float:
        return self.total_rating / self.rating_count if self.rating_count > 0 else 0.0

    @property
    def score(self) -> float:
        """综合评分"""
        # 综合考虑成功率、响应时间和用户评分
        time_score = max(0, 1 - self.avg_time / 10)  # 10秒以内得分
        rating_score = self.avg_rating / 5 if self.avg_rating > 0 else 0.5
        return (self.success_rate * 0.4 + time_score * 0.3 + rating_score * 0.3)


class StrategyOptimizer:
    """
    策略优化器

    功能:
    - 收集策略使用数据
    - 分析策略效果
    - 自适应调整策略选择
    - A/B 测试支持
    - 多臂老虎机算法

    使用示例:
    ```python
    optimizer = StrategyOptimizer(feedback_collector)

    # 选择最优策略
    strategy = await optimizer.select_strategy(task_complexity)

    # 记录策略结果
    await optimizer.record_result(strategy, success=True, time=2.5)

    # 运行优化
    result = await optimizer.optimize()
    ```
    """

    def __init__(
        self,
        feedback_collector: FeedbackCollector = None,
        config: LearningConfig = None
    ):
        self._feedback_collector = feedback_collector
        self._config = config or LearningConfig()
        self._event_bus = get_event_bus()

        # 策略性能数据
        self._strategy_performance: Dict[ReasoningStrategy, StrategyPerformance] = {
            strategy: StrategyPerformance(strategy=strategy)
            for strategy in ReasoningStrategy
        }

        # 复杂度阈值（可优化的参数）
        self._complexity_thresholds = {
            "simple": 0.3,
            "medium": 0.6
        }

        # 探索率（用于多臂老虎机）
        self._exploration_rate = 0.1

        # 优化历史
        self._optimization_history: List[OptimizationResult] = []

        # 持久化路径
        self._persistence_path = Path(self._config.learning_data_path) / "optimizer"
        self._persistence_path.mkdir(parents=True, exist_ok=True)

        # 加载历史数据
        self._load_state()

    def _load_state(self) -> None:
        """加载状态"""
        state_file = self._persistence_path / "optimizer_state.json"
        if state_file.exists():
            try:
                with open(state_file, "r", encoding="utf-8") as f:
                    state = json.load(f)

                self._complexity_thresholds = state.get("complexity_thresholds", self._complexity_thresholds)
                self._exploration_rate = state.get("exploration_rate", self._exploration_rate)

                # 恢复策略性能数据
                for strategy_name, perf_data in state.get("strategy_performance", {}).items():
                    strategy = ReasoningStrategy(strategy_name)
                    if strategy in self._strategy_performance:
                        perf = self._strategy_performance[strategy]
                        perf.total_uses = perf_data.get("total_uses", 0)
                        perf.success_count = perf_data.get("success_count", 0)
                        perf.total_time = perf_data.get("total_time", 0.0)
                        perf.total_rating = perf_data.get("total_rating", 0.0)
                        perf.rating_count = perf_data.get("rating_count", 0)

                logger.info("Loaded optimizer state")
            except Exception as e:
                logger.error(f"Failed to load optimizer state: {e}")

    def _save_state(self) -> None:
        """保存状态"""
        state = {
            "complexity_thresholds": self._complexity_thresholds,
            "exploration_rate": self._exploration_rate,
            "strategy_performance": {
                strategy.value: {
                    "total_uses": perf.total_uses,
                    "success_count": perf.success_count,
                    "total_time": perf.total_time,
                    "total_rating": perf.total_rating,
                    "rating_count": perf.rating_count
                }
                for strategy, perf in self._strategy_performance.items()
            }
        }

        state_file = self._persistence_path / "optimizer_state.json"
        try:
            with open(state_file, "w", encoding="utf-8") as f:
                json.dump(state, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Failed to save optimizer state: {e}")

    async def select_strategy(
        self,
        task_complexity: float,
        use_exploration: bool = True
    ) -> ReasoningStrategy:
        """
        选择策略

        使用 epsilon-greedy 多臂老虎机算法

        Args:
            task_complexity: 任务复杂度 (0-1)
            use_exploration: 是否使用探索

        Returns:
            推荐的策略
        """
        # 探索：随机选择
        if use_exploration and self._config.ab_testing_enabled:
            if random.random() < self._exploration_rate:
                strategy = random.choice(list(ReasoningStrategy))
                logger.debug(f"Exploration: selected {strategy.value}")
                return strategy

        # 利用：基于复杂度和历史性能选择
        if task_complexity < self._complexity_thresholds["simple"]:
            candidates = [ReasoningStrategy.DIRECT]
        elif task_complexity < self._complexity_thresholds["medium"]:
            candidates = [ReasoningStrategy.CHAIN_OF_THOUGHT, ReasoningStrategy.DIRECT]
        else:
            candidates = [
                ReasoningStrategy.TREE_OF_THOUGHT,
                ReasoningStrategy.CHAIN_OF_THOUGHT,
                ReasoningStrategy.REACT
            ]

        # 根据历史性能选择最佳策略
        best_strategy = None
        best_score = -1

        for strategy in candidates:
            perf = self._strategy_performance[strategy]
            # 使用 UCB (Upper Confidence Bound) 算法
            if perf.total_uses == 0:
                score = float("inf")  # 未尝试的策略优先
            else:
                total_uses = sum(p.total_uses for p in self._strategy_performance.values())
                ucb_bonus = (2 * (total_uses + 1) / (perf.total_uses + 1)) ** 0.5
                score = perf.score + 0.1 * ucb_bonus

            if score > best_score:
                best_score = score
                best_strategy = strategy

        return best_strategy or ReasoningStrategy.CHAIN_OF_THOUGHT

    async def record_result(
        self,
        strategy: ReasoningStrategy,
        success: bool,
        execution_time: float,
        rating: float = None
    ) -> None:
        """
        记录策略执行结果

        Args:
            strategy: 使用的策略
            success: 是否成功
            execution_time: 执行时间
            rating: 用户评分（可选）
        """
        perf = self._strategy_performance[strategy]
        perf.total_uses += 1
        perf.total_time += execution_time

        if success:
            perf.success_count += 1

        if rating is not None:
            perf.total_rating += rating
            perf.rating_count += 1

        # 保存状态
        self._save_state()

    async def optimize(self) -> OptimizationResult:
        """
        运行优化

        基于收集的数据优化策略选择参数

        Returns:
            优化结果
        """
        if not self._config.strategy_optimization_enabled:
            return OptimizationResult(
                success=False,
                strategy="",
                old_params={},
                new_params={},
                improvement=0.0,
                confidence=0.0,
                metadata={"reason": "Optimization disabled"}
            )

        # 检查是否有足够的数据
        total_samples = sum(p.total_uses for p in self._strategy_performance.values())
        if total_samples < self._config.min_samples_for_optimization:
            return OptimizationResult(
                success=False,
                strategy="",
                old_params={},
                new_params={},
                improvement=0.0,
                confidence=0.0,
                metadata={"reason": f"Not enough samples ({total_samples}/{self._config.min_samples_for_optimization})"}
            )

        await self._event_bus.emit(Event(
            type=EventType.LEARNING_STARTED,
            payload={"type": "strategy_optimization"},
            source="optimizer"
        ))

        old_thresholds = self._complexity_thresholds.copy()

        # 分析各策略在不同复杂度下的表现
        # 这里使用简化的优化逻辑，实际可以使用更复杂的算法

        # 计算各策略的综合得分
        strategy_scores = {
            strategy: perf.score
            for strategy, perf in self._strategy_performance.items()
            if perf.total_uses > 0
        }

        # 根据策略得分调整阈值
        if strategy_scores:
            # 如果简单策略表现好，提高简单阈值
            direct_score = strategy_scores.get(ReasoningStrategy.DIRECT, 0)
            cot_score = strategy_scores.get(ReasoningStrategy.CHAIN_OF_THOUGHT, 0)

            if direct_score > cot_score * 1.1:
                self._complexity_thresholds["simple"] = min(0.5, self._complexity_thresholds["simple"] + 0.05)
            elif cot_score > direct_score * 1.1:
                self._complexity_thresholds["simple"] = max(0.2, self._complexity_thresholds["simple"] - 0.05)

        # 计算改进
        improvement = self._calculate_improvement(old_thresholds, self._complexity_thresholds)

        # 保存状态
        self._save_state()

        result = OptimizationResult(
            success=True,
            strategy="complexity_thresholds",
            old_params=old_thresholds,
            new_params=self._complexity_thresholds.copy(),
            improvement=improvement,
            confidence=min(1.0, total_samples / 1000)
        )

        self._optimization_history.append(result)

        await self._event_bus.emit(Event(
            type=EventType.STRATEGY_OPTIMIZED,
            payload={
                "improvement": improvement,
                "new_thresholds": self._complexity_thresholds
            },
            source="optimizer"
        ))

        return result

    def _calculate_improvement(
        self,
        old_params: Dict[str, float],
        new_params: Dict[str, float]
    ) -> float:
        """计算改进幅度"""
        # 简化的改进计算
        total_change = sum(
            abs(new_params.get(k, 0) - old_params.get(k, 0))
            for k in set(old_params.keys()) | set(new_params.keys())
        )
        return total_change

    def get_strategy_stats(self) -> Dict[str, Any]:
        """获取策略统计"""
        return {
            strategy.value: {
                "total_uses": perf.total_uses,
                "success_rate": perf.success_rate,
                "avg_time": perf.avg_time,
                "avg_rating": perf.avg_rating,
                "score": perf.score
            }
            for strategy, perf in self._strategy_performance.items()
        }

    def get_optimization_history(self, limit: int = 10) -> List[OptimizationResult]:
        """获取优化历史"""
        return self._optimization_history[-limit:]

    def get_current_params(self) -> Dict[str, Any]:
        """获取当前参数"""
        return {
            "complexity_thresholds": self._complexity_thresholds.copy(),
            "exploration_rate": self._exploration_rate
        }
