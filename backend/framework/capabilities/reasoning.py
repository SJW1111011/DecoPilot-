"""
推理能力

提供智能体的推理能力:
- 直接推理: 简单问答
- 思维链 (CoT): 逐步推理
- 思维树 (ToT): 多路径探索
- ReAct: 推理-行动-观察循环
- 自我反思: 答案优化
"""

from abc import abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Protocol, runtime_checkable
from enum import Enum
import asyncio
import logging

from .base import CapabilityMixin, register_capability
from ..events import Event, EventType, get_event_bus
from ..config import ReasoningConfig, ReasoningStrategy

logger = logging.getLogger(__name__)


@dataclass
class ReasoningStep:
    """推理步骤"""
    step_type: str  # think | act | observe | reflect
    content: str
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ReasoningChain:
    """推理链"""
    id: str
    strategy: ReasoningStrategy
    steps: List[ReasoningStep] = field(default_factory=list)
    conclusion: Optional[str] = None
    confidence: float = 0.0
    started_at: datetime = field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None

    def add_step(self, step_type: str, content: str, **metadata) -> ReasoningStep:
        """添加推理步骤"""
        step = ReasoningStep(
            step_type=step_type,
            content=content,
            metadata=metadata
        )
        self.steps.append(step)
        return step

    def complete(self, conclusion: str, confidence: float = 0.8) -> None:
        """完成推理"""
        self.conclusion = conclusion
        self.confidence = confidence
        self.completed_at = datetime.now()

    def to_prompt(self) -> str:
        """转换为提示词格式"""
        parts = []
        for i, step in enumerate(self.steps, 1):
            if step.step_type == "think":
                parts.append(f"思考 {i}: {step.content}")
            elif step.step_type == "act":
                parts.append(f"行动 {i}: {step.content}")
            elif step.step_type == "observe":
                parts.append(f"观察 {i}: {step.content}")
            elif step.step_type == "reflect":
                parts.append(f"反思 {i}: {step.content}")
        return "\n".join(parts)


@dataclass
class ThoughtNode:
    """思维树节点"""
    id: str
    content: str
    score: float = 0.0
    children: List["ThoughtNode"] = field(default_factory=list)
    parent: Optional["ThoughtNode"] = None
    depth: int = 0
    is_terminal: bool = False


@dataclass
class TaskAnalysis:
    """任务分析结果"""
    complexity: float  # 0-1
    recommended_strategy: ReasoningStrategy
    requires_tools: bool = False
    requires_knowledge: bool = False
    estimated_steps: int = 1
    keywords: List[str] = field(default_factory=list)
    domain: str = "general"


@dataclass
class ReasoningContext:
    """推理上下文"""
    query: str
    task_analysis: Optional[TaskAnalysis] = None
    memory_context: Optional[Any] = None
    knowledge_context: Optional[List[str]] = None
    tool_results: Optional[Dict[str, Any]] = None
    previous_chains: List[ReasoningChain] = field(default_factory=list)


@runtime_checkable
class ReasoningCapability(Protocol):
    """推理能力协议"""

    async def analyze_task(self, query: str) -> TaskAnalysis:
        """分析任务复杂度"""
        ...

    async def select_strategy(self, analysis: TaskAnalysis) -> ReasoningStrategy:
        """选择推理策略"""
        ...

    async def reason(self, context: ReasoningContext) -> ReasoningChain:
        """执行推理"""
        ...


@register_capability("reasoning", version="2.0.0", description="推理能力")
class ReasoningMixin(CapabilityMixin):
    """
    推理能力混入

    提供多种推理策略:
    - 自适应策略选择
    - 思维链推理
    - 思维树探索
    - ReAct 循环
    """

    _capability_name = "reasoning"
    _capability_version = "2.0.0"

    # 复杂度关键词
    COMPLEX_KEYWORDS = [
        "分析", "比较", "评估", "设计", "规划", "优化",
        "为什么", "如何", "怎样", "什么区别", "哪个更好",
        "多少钱", "计算", "预算", "方案"
    ]

    SIMPLE_KEYWORDS = [
        "是什么", "在哪里", "什么时候", "谁", "多少",
        "有没有", "能不能", "可以吗"
    ]

    def __init__(self, config: ReasoningConfig = None):
        super().__init__()
        self._reasoning_config = config or ReasoningConfig()
        self._event_bus = get_event_bus()
        self._chain_counter = 0
        self._strategy_stats: Dict[str, Dict[str, int]] = {}

    async def _do_initialize(self) -> None:
        """初始化推理引擎"""
        logger.info("Reasoning engine initialized")

    async def analyze_task(self, query: str) -> TaskAnalysis:
        """分析任务复杂度"""
        complexity = 0.0
        keywords = []

        # 关键词分析
        for kw in self.COMPLEX_KEYWORDS:
            if kw in query:
                complexity += 0.15
                keywords.append(kw)

        for kw in self.SIMPLE_KEYWORDS:
            if kw in query:
                complexity -= 0.1
                keywords.append(kw)

        # 长度分析
        if len(query) > 100:
            complexity += 0.1
        if len(query) > 200:
            complexity += 0.1

        # 多问题检测
        question_marks = query.count("？") + query.count("?")
        if question_marks > 1:
            complexity += 0.2 * (question_marks - 1)

        # 限制范围
        complexity = max(0.0, min(1.0, complexity))

        # 确定推荐策略
        if complexity < self._reasoning_config.complexity_threshold_simple:
            strategy = ReasoningStrategy.DIRECT
            estimated_steps = 1
        elif complexity < self._reasoning_config.complexity_threshold_medium:
            strategy = ReasoningStrategy.CHAIN_OF_THOUGHT
            estimated_steps = 3
        else:
            strategy = ReasoningStrategy.TREE_OF_THOUGHT
            estimated_steps = 5

        # 检测是否需要工具
        requires_tools = any(kw in query for kw in ["计算", "查询", "搜索", "多少钱"])

        # 检测是否需要知识库
        requires_knowledge = any(kw in query for kw in ["政策", "流程", "指南", "规定", "标准"])

        return TaskAnalysis(
            complexity=complexity,
            recommended_strategy=strategy,
            requires_tools=requires_tools,
            requires_knowledge=requires_knowledge,
            estimated_steps=estimated_steps,
            keywords=keywords
        )

    async def select_strategy(self, analysis: TaskAnalysis) -> ReasoningStrategy:
        """选择推理策略"""
        if self._reasoning_config.default_strategy != ReasoningStrategy.ADAPTIVE:
            return self._reasoning_config.default_strategy

        strategy = analysis.recommended_strategy

        # 检查策略是否启用
        if strategy == ReasoningStrategy.CHAIN_OF_THOUGHT and not self._reasoning_config.cot_enabled:
            strategy = ReasoningStrategy.DIRECT
        elif strategy == ReasoningStrategy.TREE_OF_THOUGHT and not self._reasoning_config.tot_enabled:
            strategy = ReasoningStrategy.CHAIN_OF_THOUGHT if self._reasoning_config.cot_enabled else ReasoningStrategy.DIRECT

        await self._event_bus.emit(Event(
            type=EventType.STRATEGY_SELECTED,
            payload={
                "strategy": strategy.value,
                "complexity": analysis.complexity
            },
            source="reasoning"
        ))

        return strategy

    async def reason(self, context: ReasoningContext) -> ReasoningChain:
        """执行推理"""
        # 分析任务
        if not context.task_analysis:
            context.task_analysis = await self.analyze_task(context.query)

        # 选择策略
        strategy = await self.select_strategy(context.task_analysis)

        # 创建推理链
        self._chain_counter += 1
        chain = ReasoningChain(
            id=f"chain_{self._chain_counter}",
            strategy=strategy
        )

        await self._event_bus.emit(Event(
            type=EventType.REASONING_STARTED,
            payload={
                "chain_id": chain.id,
                "strategy": strategy.value,
                "query": context.query
            },
            source="reasoning"
        ))

        # 根据策略执行推理
        try:
            if strategy == ReasoningStrategy.DIRECT:
                await self._direct_reasoning(chain, context)
            elif strategy == ReasoningStrategy.CHAIN_OF_THOUGHT:
                await self._cot_reasoning(chain, context)
            elif strategy == ReasoningStrategy.TREE_OF_THOUGHT:
                await self._tot_reasoning(chain, context)
            elif strategy == ReasoningStrategy.REACT:
                await self._react_reasoning(chain, context)
            elif strategy == ReasoningStrategy.SELF_REFLECTION:
                await self._reflection_reasoning(chain, context)

            await self._event_bus.emit(Event(
                type=EventType.REASONING_COMPLETED,
                payload={
                    "chain_id": chain.id,
                    "steps": len(chain.steps),
                    "confidence": chain.confidence
                },
                source="reasoning"
            ))

        except Exception as e:
            logger.error(f"Reasoning failed: {e}")
            await self._event_bus.emit(Event(
                type=EventType.REASONING_FAILED,
                payload={"chain_id": chain.id, "error": str(e)},
                source="reasoning"
            ))
            raise

        return chain

    async def _direct_reasoning(self, chain: ReasoningChain, context: ReasoningContext) -> None:
        """直接推理"""
        chain.add_step("think", f"直接回答问题: {context.query}")
        chain.complete("", confidence=0.9)

    async def _cot_reasoning(self, chain: ReasoningChain, context: ReasoningContext) -> None:
        """思维链推理"""
        # 步骤1: 理解问题
        chain.add_step("think", f"理解问题: {context.query}")

        # 步骤2: 分解问题
        chain.add_step("think", "分解问题为子问题")

        # 步骤3: 逐步推理
        for i in range(context.task_analysis.estimated_steps - 2):
            chain.add_step("think", f"推理步骤 {i+1}")

            await self._event_bus.emit(Event(
                type=EventType.REASONING_STEP,
                payload={"chain_id": chain.id, "step": i+1},
                source="reasoning"
            ))

        # 步骤4: 综合结论
        chain.add_step("think", "综合以上分析得出结论")
        chain.complete("", confidence=0.85)

    async def _tot_reasoning(self, chain: ReasoningChain, context: ReasoningContext) -> None:
        """思维树推理"""
        # 创建根节点
        root = ThoughtNode(id="root", content=context.query)

        # 生成多个思路分支
        chain.add_step("think", "生成多个解决思路")

        branches = ["思路A: 从用户需求角度", "思路B: 从技术可行性角度", "思路C: 从成本效益角度"]

        for i, branch in enumerate(branches[:self._reasoning_config.max_tree_branches]):
            chain.add_step("think", f"探索 {branch}")
            child = ThoughtNode(
                id=f"node_{i}",
                content=branch,
                parent=root,
                depth=1
            )
            root.children.append(child)

        # 评估并选择最佳路径
        chain.add_step("think", "评估各思路的可行性")
        chain.add_step("think", "选择最优思路并深入分析")

        chain.complete("", confidence=0.9)

    async def _react_reasoning(self, chain: ReasoningChain, context: ReasoningContext) -> None:
        """ReAct 推理"""
        for i in range(self._reasoning_config.max_reasoning_steps):
            # 思考
            chain.add_step("think", f"思考第 {i+1} 步应该做什么")

            # 行动
            chain.add_step("act", f"执行行动 {i+1}")

            # 观察
            chain.add_step("observe", f"观察行动 {i+1} 的结果")

            # 检查是否完成
            if i >= 2:  # 至少3轮
                break

        chain.complete("", confidence=0.85)

    async def _reflection_reasoning(self, chain: ReasoningChain, context: ReasoningContext) -> None:
        """自我反思推理"""
        # 初始回答
        chain.add_step("think", "生成初始回答")

        # 反思
        chain.add_step("reflect", "检查回答是否完整")
        chain.add_step("reflect", "检查回答是否准确")
        chain.add_step("reflect", "检查是否有遗漏")

        # 优化
        chain.add_step("think", "根据反思优化回答")

        chain.complete("", confidence=0.9)

    def get_stats(self) -> Dict[str, Any]:
        """获取推理统计"""
        return {
            "total_chains": self._chain_counter,
            "strategy_stats": self._strategy_stats
        }
