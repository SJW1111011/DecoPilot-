"""
任务规划器

将复杂任务分解为可执行的步骤
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional
import logging
from uuid import uuid4

from ..events import Event, EventType, get_event_bus

logger = logging.getLogger(__name__)


@dataclass
class PlanStep:
    """计划步骤"""
    index: int
    task: str
    agent_name: str
    description: str = ""
    dependencies: List[int] = field(default_factory=list)  # 依赖的步骤索引
    estimated_complexity: float = 0.5
    metadata: Dict[str, Any] = field(default_factory=dict)
    status: str = "pending"  # pending | running | completed | failed
    result: Optional[Any] = None


@dataclass
class Plan:
    """执行计划"""
    id: str
    request_id: str
    steps: List[PlanStep] = field(default_factory=list)
    requires_collaboration: bool = False
    created_at: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def total_steps(self) -> int:
        return len(self.steps)

    @property
    def completed_steps(self) -> int:
        return sum(1 for s in self.steps if s.status == "completed")

    @property
    def progress(self) -> float:
        return self.completed_steps / self.total_steps if self.total_steps > 0 else 0.0


class TaskPlanner:
    """
    任务规划器

    功能:
    - 任务复杂度分析
    - 任务分解
    - 依赖关系识别
    - 动态重规划

    使用示例:
    ```python
    planner = TaskPlanner()

    # 创建计划
    plan = await planner.create_plan(request)

    # 检查是否需要协作
    if plan.requires_collaboration:
        # 多智能体协作处理
        pass
    ```
    """

    # 复杂任务关键词
    COMPLEX_KEYWORDS = [
        "并且", "同时", "另外", "还有", "以及",
        "首先", "然后", "最后", "接着",
        "比较", "对比", "分析", "评估"
    ]

    # 任务类型到智能体的映射
    TASK_AGENT_MAPPING = {
        "补贴计算": "c_end",
        "风格推荐": "c_end",
        "装修流程": "c_end",
        "商家推荐": "c_end",
        "ROI分析": "b_end",
        "获客策略": "b_end",
        "入驻指导": "b_end",
        "话术生成": "b_end",
    }

    def __init__(self):
        self._event_bus = get_event_bus()
        self._plan_counter = 0

    async def create_plan(self, request: Any) -> Plan:
        """
        创建执行计划

        Args:
            request: 请求对象

        Returns:
            执行计划
        """
        self._plan_counter += 1
        plan_id = f"plan_{self._plan_counter}_{str(uuid4())[:8]}"

        await self._event_bus.emit(Event(
            type=EventType.PLAN_CREATING,
            payload={"plan_id": plan_id, "request_id": request.id},
            source="planner"
        ))

        message = getattr(request, "message", "")
        user_type = getattr(request, "user_type", "c_end")

        # 分析任务复杂度
        complexity = self._analyze_complexity(message)

        # 判断是否需要分解
        if complexity < 0.5:
            # 简单任务，单步执行
            plan = Plan(
                id=plan_id,
                request_id=request.id,
                steps=[
                    PlanStep(
                        index=0,
                        task=message,
                        agent_name=user_type,
                        estimated_complexity=complexity
                    )
                ],
                requires_collaboration=False
            )
        else:
            # 复杂任务，分解为多步
            steps = self._decompose_task(message, user_type)
            plan = Plan(
                id=plan_id,
                request_id=request.id,
                steps=steps,
                requires_collaboration=len(set(s.agent_name for s in steps)) > 1
            )

        await self._event_bus.emit(Event(
            type=EventType.PLAN_CREATED,
            payload={
                "plan_id": plan_id,
                "steps": len(plan.steps),
                "requires_collaboration": plan.requires_collaboration
            },
            source="planner"
        ))

        return plan

    async def replan(self, plan: Plan, failed_result: Any) -> Plan:
        """
        重新规划

        Args:
            plan: 原计划
            failed_result: 失败的结果

        Returns:
            新计划
        """
        await self._event_bus.emit(Event(
            type=EventType.PLAN_REPLANNING,
            payload={"plan_id": plan.id},
            source="planner"
        ))

        # 找到失败的步骤
        failed_step_index = None
        for i, step in enumerate(plan.steps):
            if step.status == "failed":
                failed_step_index = i
                break

        if failed_step_index is None:
            return plan

        # 创建新的步骤来处理失败
        new_steps = plan.steps[:failed_step_index]

        # 添加恢复步骤
        recovery_step = PlanStep(
            index=len(new_steps),
            task=f"处理步骤 {failed_step_index} 的失败: {plan.steps[failed_step_index].task}",
            agent_name=plan.steps[failed_step_index].agent_name,
            description="恢复步骤",
            metadata={"recovery": True, "original_step": failed_step_index}
        )
        new_steps.append(recovery_step)

        # 添加剩余步骤
        for step in plan.steps[failed_step_index + 1:]:
            step.index = len(new_steps)
            new_steps.append(step)

        plan.steps = new_steps
        return plan

    def _analyze_complexity(self, message: str) -> float:
        """分析任务复杂度"""
        complexity = 0.0

        # 关键词分析
        for kw in self.COMPLEX_KEYWORDS:
            if kw in message:
                complexity += 0.1

        # 长度分析
        if len(message) > 50:
            complexity += 0.1
        if len(message) > 100:
            complexity += 0.1
        if len(message) > 200:
            complexity += 0.1

        # 问号数量
        question_count = message.count("？") + message.count("?")
        complexity += 0.15 * (question_count - 1) if question_count > 1 else 0

        return min(1.0, complexity)

    def _decompose_task(self, message: str, default_agent: str) -> List[PlanStep]:
        """分解任务"""
        steps = []

        # 简单的基于关键词的分解
        # 实际应用中可以使用 LLM 进行更智能的分解

        # 检测多个子任务
        subtasks = []

        # 按连接词分割
        for connector in ["并且", "同时", "另外", "还有", "以及"]:
            if connector in message:
                parts = message.split(connector)
                subtasks.extend([p.strip() for p in parts if p.strip()])
                break

        # 如果没有找到连接词，检查是否有多个问题
        if not subtasks:
            # 按问号分割
            parts = message.replace("?", "？").split("？")
            subtasks = [p.strip() + "？" for p in parts if p.strip()]

        # 如果还是只有一个任务
        if len(subtasks) <= 1:
            subtasks = [message]

        # 为每个子任务创建步骤
        for i, task in enumerate(subtasks):
            agent_name = self._determine_agent(task, default_agent)
            steps.append(PlanStep(
                index=i,
                task=task,
                agent_name=agent_name,
                estimated_complexity=0.5
            ))

        return steps

    def _determine_agent(self, task: str, default_agent: str) -> str:
        """确定任务应该由哪个智能体处理"""
        for task_type, agent in self.TASK_AGENT_MAPPING.items():
            if task_type in task:
                return agent
        return default_agent
