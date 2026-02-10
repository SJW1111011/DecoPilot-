# -*- coding: utf-8 -*-
"""
智能体运行时

提供智能体的运行时环境，整合所有能力
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, AsyncGenerator, Callable, Dict, List, Optional, Type
import asyncio
import logging

from ..capabilities import (
    CapabilityMixin,
    MemoryMixin,
    ReasoningMixin,
    ToolMixin,
    MultimodalMixin,
    OutputMixin
)
from ..capabilities.memory import MemoryContext, MemoryType
from ..capabilities.reasoning import ReasoningContext, ReasoningChain
from ..capabilities.tools import ToolResult
from ..capabilities.output import StreamChunk, StructuredOutput
from ..events import Event, EventType, get_event_bus
from ..config import AgentConfig, FrameworkConfig
from ..observability import get_tracer, get_metrics, get_logger
from ..learning import FeedbackCollector, StrategyOptimizer, ExperienceReplay

logger = logging.getLogger(__name__)


@dataclass
class ProcessResult:
    """处理结果"""
    answer: str
    thinking_logs: List[str] = field(default_factory=list)
    sources: List[Dict[str, Any]] = field(default_factory=list)
    structured_outputs: List[Dict[str, Any]] = field(default_factory=list)
    tool_results: List[ToolResult] = field(default_factory=list)
    reasoning_chain: Optional[ReasoningChain] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "answer": self.answer,
            "thinking_logs": self.thinking_logs,
            "sources": self.sources,
            "structured_outputs": self.structured_outputs,
            "tool_results": [
                {"tool_name": r.tool_name, "success": r.success, "result": r.result}
                for r in self.tool_results
            ],
            "metadata": self.metadata
        }


class AgentRuntime(MemoryMixin, ReasoningMixin, ToolMixin, MultimodalMixin, OutputMixin):
    """
    智能体运行时

    整合所有能力，提供完整的智能体运行环境
    """

    def __init__(
        self,
        config: AgentConfig = None,
        llm_client: Any = None,
        knowledge_base: Any = None
    ):
        # 初始化各个能力
        MemoryMixin.__init__(self, config.memory if config else None)
        ReasoningMixin.__init__(self, config.reasoning if config else None)
        ToolMixin.__init__(self, config.tools if config else None)
        MultimodalMixin.__init__(self, config.multimodal if config else None)
        OutputMixin.__init__(self)

        self._config = config or AgentConfig()
        self._llm_client = llm_client
        self._knowledge_base = knowledge_base
        self._event_bus = get_event_bus()
        self._tracer = get_tracer()
        self._metrics = get_metrics()
        self._logger = get_logger()

        # 学习组件
        self._feedback_collector: Optional[FeedbackCollector] = None
        self._strategy_optimizer: Optional[StrategyOptimizer] = None
        self._experience_replay: Optional[ExperienceReplay] = None

        self._initialized = False

    async def initialize(self) -> None:
        """初始化运行时"""
        if self._initialized:
            return

        # 初始化各个能力
        await MemoryMixin.initialize(self)
        await ReasoningMixin.initialize(self)
        await ToolMixin.initialize(self)
        await MultimodalMixin.initialize(self)
        await OutputMixin.initialize(self)

        # 初始化学习组件
        from ..config import LearningConfig, LearningMode
        learning_config = LearningConfig()

        if learning_config.mode != LearningMode.DISABLED:
            self._feedback_collector = FeedbackCollector(learning_config)
            self._strategy_optimizer = StrategyOptimizer(
                self._feedback_collector, learning_config
            )
            self._experience_replay = ExperienceReplay(config=learning_config)

        self._initialized = True

        await self._event_bus.emit(Event(
            type=EventType.AGENT_STARTED,
            payload={"agent_name": self._config.name},
            source="runtime"
        ))

        self._logger.info("Agent runtime initialized", agent_name=self._config.name)

    async def shutdown(self) -> None:
        """关闭运行时"""
        if not self._initialized:
            return

        await MemoryMixin.shutdown(self)
        await ReasoningMixin.shutdown(self)
        await ToolMixin.shutdown(self)
        await MultimodalMixin.shutdown(self)
        await OutputMixin.shutdown(self)

        self._initialized = False

        await self._event_bus.emit(Event(
            type=EventType.AGENT_STOPPED,
            payload={"agent_name": self._config.name},
            source="runtime"
        ))

    async def process(
        self,
        message: str,
        session_id: str,
        user_id: str,
        images: List[str] = None,
        context: Dict[str, Any] = None
    ) -> ProcessResult:
        """处理请求"""
        with self._tracer.span("process_request", user_id=user_id) as span:
            start_time = datetime.now()
            thinking_logs = []
            sources = []
            structured_outputs = []
            tool_results = []

            try:
                # 1. 获取记忆上下文
                memory_context = await self.get_context(user_id, session_id, message)
                thinking_logs.append(f"Load user context: {user_id}")

                # 2. 分析任务
                task_analysis = await self.analyze_task(message)
                thinking_logs.append(f"Task complexity: {task_analysis.complexity:.2f}")

                # 3. 选择推理策略
                if self._strategy_optimizer:
                    strategy = await self._strategy_optimizer.select_strategy(
                        task_analysis.complexity
                    )
                else:
                    strategy = await self.select_strategy(task_analysis)
                thinking_logs.append(f"Strategy: {strategy.value}")

                # 4. 创建推理上下文
                reasoning_context = ReasoningContext(
                    query=message,
                    task_analysis=task_analysis,
                    memory_context=memory_context
                )

                # 5. 执行推理
                reasoning_chain = await self.reason(reasoning_context)
                thinking_logs.extend([
                    f"{step.step_type}: {step.content}"
                    for step in reasoning_chain.steps
                ])

                # 6. 检查是否需要调用工具
                if task_analysis.requires_tools:
                    tool_result = await self._try_call_tools(message)
                    if tool_result:
                        tool_results.append(tool_result)
                        thinking_logs.append(f"Tool called: {tool_result.tool_name}")

                # 7. 知识库检索
                if task_analysis.requires_knowledge and self._knowledge_base:
                    kb_results = await self._search_knowledge(message)
                    sources.extend(kb_results)
                    thinking_logs.append(f"Found {len(kb_results)} knowledge items")

                # 8. 生成回答
                answer = await self._generate_answer(
                    message=message,
                    memory_context=memory_context,
                    reasoning_chain=reasoning_chain,
                    tool_results=tool_results,
                    sources=sources
                )

                # 9. 更新记忆
                await self.remember(
                    f"User: {message}\nAssistant: {answer}",
                    memory_type=MemoryType.SHORT_TERM,
                    metadata={"session_id": session_id}
                )

                # 10. 记录经验
                if self._experience_replay:
                    execution_time = (datetime.now() - start_time).total_seconds()
                    reward = self._experience_replay.calculate_reward(
                        success=True,
                        response_time=execution_time
                    )
                    await self._experience_replay.add(
                        state={"query": message, "context": str(memory_context)},
                        action={"strategy": strategy.value, "tools": [r.tool_name for r in tool_results]},
                        reward=reward
                    )

                # 11. 记录策略结果
                if self._strategy_optimizer:
                    execution_time = (datetime.now() - start_time).total_seconds()
                    await self._strategy_optimizer.record_result(
                        strategy=strategy,
                        success=True,
                        execution_time=execution_time
                    )

                # 记录指标
                self._metrics.counter("decopilot_requests_total").inc()
                self._metrics.histogram("decopilot_request_duration_seconds").observe(
                    (datetime.now() - start_time).total_seconds()
                )

                return ProcessResult(
                    answer=answer,
                    thinking_logs=thinking_logs,
                    sources=sources,
                    structured_outputs=structured_outputs,
                    tool_results=tool_results,
                    reasoning_chain=reasoning_chain
                )

            except Exception as e:
                self._logger.error("Process failed", error=str(e))
                span.set_error(e)
                raise

    async def process_stream(
        self,
        message: str,
        session_id: str,
        user_id: str,
        **kwargs
    ) -> AsyncGenerator[StreamChunk, None]:
        """流式处理请求"""
        # 先执行处理
        result = await self.process(message, session_id, user_id, **kwargs)

        # 流式输出
        async for chunk in self.stream(
            content=result.answer,
            thinking=result.thinking_logs,
            sources=result.sources,
            structured=[
                StructuredOutput(**s) if isinstance(s, dict) else s
                for s in result.structured_outputs
            ]
        ):
            yield chunk

    async def _try_call_tools(self, message: str) -> Optional[ToolResult]:
        """尝试调用工具"""
        import re

        # 补贴计算
        if "subsidy" in message.lower() or "butie" in message.lower():
            amounts = re.findall(r'(\d+(?:\.\d+)?)', message)
            if amounts:
                amount = float(amounts[0])
                category = "furniture"
                return await self.call_tool("subsidy_calculator", {
                    "amount": amount,
                    "category": category
                })

        # ROI 计算
        if "roi" in message.lower():
            amounts = re.findall(r'(\d+(?:\.\d+)?)', message)
            if len(amounts) >= 2:
                return await self.call_tool("roi_calculator", {
                    "investment": float(amounts[0]),
                    "revenue": float(amounts[1])
                })

        return None

    async def _search_knowledge(self, query: str) -> List[Dict[str, Any]]:
        """搜索知识库"""
        if not self._knowledge_base:
            return []

        try:
            results = await self._knowledge_base.search(query, k=5)
            return [
                {"content": r.content, "source": r.metadata.get("source", "unknown")}
                for r in results
            ]
        except Exception as e:
            self._logger.warning("Knowledge search failed", error=str(e))
            return []

    async def _generate_answer(
        self,
        message: str,
        memory_context: MemoryContext,
        reasoning_chain: ReasoningChain,
        tool_results: List[ToolResult],
        sources: List[Dict[str, Any]]
    ) -> str:
        """生成回答"""
        # 这里应该调用 LLM 生成回答
        # 目前返回模拟结果

        if tool_results:
            tool_info = "\n".join([
                f"Tool {r.tool_name} result: {r.result}"
                for r in tool_results if r.success
            ])
            return f"Based on your question, here is the analysis:\n\n{tool_info}\n\nFeel free to ask more questions."

        if sources:
            source_info = "\n".join([s["content"][:200] for s in sources[:3]])
            return f"Based on relevant information:\n\n{source_info}\n\nHope this helps."

        return f"Hello! Regarding your question about [{message}], I am here to help. What else would you like to know?"


def create_agent(
    name: str,
    agent_type: str = "general",
    config: AgentConfig = None,
    **kwargs
) -> AgentRuntime:
    """
    创建智能体

    Args:
        name: 智能体名称
        agent_type: 智能体类型
        config: 配置
        **kwargs: 额外参数

    Returns:
        智能体运行时实例
    """
    if config is None:
        config = AgentConfig(name=name, type=agent_type)
    else:
        config.name = name
        config.type = agent_type

    return AgentRuntime(config=config, **kwargs)
