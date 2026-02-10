"""
智能体编排器

管理多智能体协作和任务分发
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Type
import asyncio
import logging
import threading

from ..events import Event, EventType, get_event_bus
from ..config import OrchestrationConfig
from .router import AgentRouter, RoutingRule
from .planner import TaskPlanner, Plan
from .supervisor import Supervisor

logger = logging.getLogger(__name__)


@dataclass
class Request:
    """请求对象"""
    id: str
    message: str
    user_id: str
    session_id: str
    user_type: str = "c_end"
    context: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class Response:
    """响应对象"""
    request_id: str
    content: str
    agent_name: str
    structured_outputs: List[Dict[str, Any]] = field(default_factory=list)
    thinking_logs: List[str] = field(default_factory=list)
    sources: List[Dict[str, Any]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)
    success: bool = True
    error: Optional[str] = None


class AgentOrchestrator:
    """
    智能体编排器

    功能:
    - 智能体注册和管理
    - 请求路由
    - 任务规划
    - 多智能体协作
    - 执行监督

    使用示例:
    ```python
    orchestrator = AgentOrchestrator()

    # 注册智能体
    orchestrator.register_agent("c_end", CEndAgent())
    orchestrator.register_agent("b_end", BEndAgent())

    # 处理请求
    response = await orchestrator.process(request)
    ```
    """

    def __init__(self, config: OrchestrationConfig = None):
        self._config = config or OrchestrationConfig()
        self._agents: Dict[str, Any] = {}
        self._router = AgentRouter()
        self._planner = TaskPlanner()
        self._supervisor = Supervisor()
        self._event_bus = get_event_bus()
        self._running = False
        self._request_counter = 0

    async def start(self) -> None:
        """启动编排器"""
        if self._running:
            return

        self._running = True

        # 初始化所有智能体
        for name, agent in self._agents.items():
            if hasattr(agent, "initialize"):
                await agent.initialize()

        await self._event_bus.emit(Event(
            type=EventType.SYSTEM_STARTED,
            payload={"component": "orchestrator"},
            source="orchestrator"
        ))

        logger.info("Orchestrator started")

    async def stop(self) -> None:
        """停止编排器"""
        if not self._running:
            return

        # 关闭所有智能体
        for name, agent in self._agents.items():
            if hasattr(agent, "shutdown"):
                await agent.shutdown()

        self._running = False

        await self._event_bus.emit(Event(
            type=EventType.SYSTEM_STOPPED,
            payload={"component": "orchestrator"},
            source="orchestrator"
        ))

        logger.info("Orchestrator stopped")

    def register_agent(
        self,
        name: str,
        agent: Any,
        routing_rules: List[RoutingRule] = None
    ) -> None:
        """
        注册智能体

        Args:
            name: 智能体名称
            agent: 智能体实例
            routing_rules: 路由规则
        """
        self._agents[name] = agent

        # 添加路由规则
        if routing_rules:
            for rule in routing_rules:
                self._router.add_rule(rule)

        self._event_bus.emit_sync(Event(
            type=EventType.AGENT_REGISTERED,
            payload={"agent_name": name},
            source="orchestrator"
        ))

        logger.info(f"Registered agent: {name}")

    def unregister_agent(self, name: str) -> bool:
        """注销智能体"""
        if name in self._agents:
            del self._agents[name]
            self._router.remove_rules_for_agent(name)

            self._event_bus.emit_sync(Event(
                type=EventType.AGENT_UNREGISTERED,
                payload={"agent_name": name},
                source="orchestrator"
            ))

            return True
        return False

    def get_agent(self, name: str) -> Optional[Any]:
        """获取智能体"""
        return self._agents.get(name)

    def list_agents(self) -> List[str]:
        """列出所有智能体"""
        return list(self._agents.keys())

    async def process(self, request: Request) -> Response:
        """
        处理请求

        Args:
            request: 请求对象

        Returns:
            响应对象
        """
        self._request_counter += 1

        await self._event_bus.emit(Event(
            type=EventType.REQUEST_RECEIVED,
            payload={
                "request_id": request.id,
                "user_type": request.user_type
            },
            source="orchestrator"
        ))

        try:
            # 1. 路由到合适的智能体
            agent_name = self._router.route(request)
            if not agent_name:
                agent_name = self._config.default_agent

            agent = self._agents.get(agent_name)
            if not agent:
                return Response(
                    request_id=request.id,
                    content="",
                    agent_name="",
                    success=False,
                    error=f"Agent '{agent_name}' not found"
                )

            await self._event_bus.emit(Event(
                type=EventType.REQUEST_ROUTED,
                payload={
                    "request_id": request.id,
                    "agent_name": agent_name
                },
                source="orchestrator"
            ))

            # 2. 检查是否需要规划
            if self._config.planning_enabled:
                plan = await self._planner.create_plan(request)

                if plan.requires_collaboration and self._config.collaboration_enabled:
                    return await self._collaborative_process(request, plan)

            # 3. 单智能体处理
            response = await self._single_agent_process(request, agent, agent_name)

            await self._event_bus.emit(Event(
                type=EventType.REQUEST_COMPLETED,
                payload={
                    "request_id": request.id,
                    "agent_name": agent_name,
                    "success": response.success
                },
                source="orchestrator"
            ))

            return response

        except Exception as e:
            logger.error(f"Request processing failed: {e}")

            await self._event_bus.emit(Event(
                type=EventType.REQUEST_FAILED,
                payload={
                    "request_id": request.id,
                    "error": str(e)
                },
                source="orchestrator"
            ))

            return Response(
                request_id=request.id,
                content="",
                agent_name="",
                success=False,
                error=str(e)
            )

    async def _single_agent_process(
        self,
        request: Request,
        agent: Any,
        agent_name: str
    ) -> Response:
        """单智能体处理"""
        # 使用监督器执行
        if self._config.supervision_enabled:
            result = await self._supervisor.execute_with_supervision(
                agent=agent,
                request=request,
                max_retries=self._config.max_retries_per_step
            )

            return Response(
                request_id=request.id,
                content=result.content,
                agent_name=agent_name,
                structured_outputs=result.structured_outputs,
                thinking_logs=result.thinking_logs,
                sources=result.sources,
                success=result.success,
                error=result.error
            )
        else:
            # 直接调用智能体
            if hasattr(agent, "process"):
                result = await agent.process(
                    message=request.message,
                    session_id=request.session_id,
                    user_id=request.user_id
                )

                return Response(
                    request_id=request.id,
                    content=result.get("answer", ""),
                    agent_name=agent_name,
                    structured_outputs=result.get("structured_outputs", []),
                    thinking_logs=result.get("thinking_logs", []),
                    sources=result.get("sources", [])
                )
            else:
                return Response(
                    request_id=request.id,
                    content="",
                    agent_name=agent_name,
                    success=False,
                    error="Agent does not have process method"
                )

    async def _collaborative_process(
        self,
        request: Request,
        plan: Plan
    ) -> Response:
        """协作处理"""
        await self._event_bus.emit(Event(
            type=EventType.COLLABORATION_STARTED,
            payload={
                "request_id": request.id,
                "plan_id": plan.id,
                "steps": len(plan.steps)
            },
            source="orchestrator"
        ))

        results = []
        all_thinking_logs = []
        all_sources = []
        all_structured = []

        for step in plan.steps:
            agent = self._agents.get(step.agent_name)
            if not agent:
                continue

            await self._event_bus.emit(Event(
                type=EventType.PLAN_STEP_STARTED,
                payload={
                    "plan_id": plan.id,
                    "step_index": step.index,
                    "agent_name": step.agent_name
                },
                source="orchestrator"
            ))

            # 执行步骤
            step_result = await self._supervisor.execute_with_supervision(
                agent=agent,
                request=Request(
                    id=f"{request.id}_step_{step.index}",
                    message=step.task,
                    user_id=request.user_id,
                    session_id=request.session_id,
                    user_type=request.user_type,
                    context={**request.context, "previous_results": results}
                ),
                max_retries=self._config.max_retries_per_step
            )

            results.append(step_result)
            all_thinking_logs.extend(step_result.thinking_logs)
            all_sources.extend(step_result.sources)
            all_structured.extend(step_result.structured_outputs)

            await self._event_bus.emit(Event(
                type=EventType.PLAN_STEP_COMPLETED,
                payload={
                    "plan_id": plan.id,
                    "step_index": step.index,
                    "success": step_result.success
                },
                source="orchestrator"
            ))

            # 检查是否需要重新规划
            if step_result.requires_replanning:
                plan = await self._planner.replan(plan, step_result)

        # 聚合结果
        final_content = self._aggregate_results(results)

        await self._event_bus.emit(Event(
            type=EventType.COLLABORATION_COMPLETED,
            payload={
                "request_id": request.id,
                "plan_id": plan.id
            },
            source="orchestrator"
        ))

        return Response(
            request_id=request.id,
            content=final_content,
            agent_name="collaborative",
            structured_outputs=all_structured,
            thinking_logs=all_thinking_logs,
            sources=all_sources
        )

    def _aggregate_results(self, results: List[Any]) -> str:
        """聚合多个结果"""
        contents = [r.content for r in results if r.content]
        return "\n\n".join(contents)

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            "total_requests": self._request_counter,
            "registered_agents": list(self._agents.keys()),
            "running": self._running
        }


# 全局编排器实例
_global_orchestrator: Optional[AgentOrchestrator] = None
_orchestrator_lock = threading.Lock()


def get_orchestrator(config: OrchestrationConfig = None) -> AgentOrchestrator:
    """获取全局编排器实例"""
    global _global_orchestrator
    if _global_orchestrator is None:
        with _orchestrator_lock:
            if _global_orchestrator is None:
                _global_orchestrator = AgentOrchestrator(config)
    return _global_orchestrator


def reset_orchestrator() -> None:
    """重置全局编排器"""
    global _global_orchestrator
    with _orchestrator_lock:
        if _global_orchestrator:
            asyncio.create_task(_global_orchestrator.stop())
        _global_orchestrator = None
