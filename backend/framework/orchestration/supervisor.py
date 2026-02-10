"""
执行监督器

监督智能体执行，提供错误处理和重试机制
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional
import asyncio
import logging

from ..events import Event, EventType, get_event_bus

logger = logging.getLogger(__name__)


@dataclass
class SupervisionResult:
    """监督执行结果"""
    success: bool
    content: str = ""
    structured_outputs: List[Dict[str, Any]] = field(default_factory=list)
    thinking_logs: List[str] = field(default_factory=list)
    sources: List[Dict[str, Any]] = field(default_factory=list)
    error: Optional[str] = None
    retries: int = 0
    execution_time: float = 0.0
    requires_replanning: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)


class Supervisor:
    """
    执行监督器

    功能:
    - 执行监控
    - 错误处理
    - 自动重试
    - 超时控制
    - 结果验证

    使用示例:
    ```python
    supervisor = Supervisor()

    result = await supervisor.execute_with_supervision(
        agent=agent,
        request=request,
        max_retries=3
    )
    ```
    """

    def __init__(
        self,
        default_timeout: int = 60,
        default_max_retries: int = 2
    ):
        self._default_timeout = default_timeout
        self._default_max_retries = default_max_retries
        self._event_bus = get_event_bus()
        self._execution_history: List[SupervisionResult] = []

    async def execute_with_supervision(
        self,
        agent: Any,
        request: Any,
        max_retries: int = None,
        timeout: int = None,
        validate_result: bool = True
    ) -> SupervisionResult:
        """
        带监督的执行

        Args:
            agent: 智能体实例
            request: 请求对象
            max_retries: 最大重试次数
            timeout: 超时时间（秒）
            validate_result: 是否验证结果

        Returns:
            监督执行结果
        """
        max_retries = max_retries or self._default_max_retries
        timeout = timeout or self._default_timeout

        start_time = datetime.now()
        retries = 0
        last_error = None

        while retries <= max_retries:
            try:
                # 执行智能体
                result = await asyncio.wait_for(
                    self._execute_agent(agent, request),
                    timeout=timeout
                )

                # 验证结果
                if validate_result:
                    validation = self._validate_result(result)
                    if not validation["valid"]:
                        raise ValueError(validation["reason"])

                execution_time = (datetime.now() - start_time).total_seconds()

                supervision_result = SupervisionResult(
                    success=True,
                    content=result.get("answer", ""),
                    structured_outputs=result.get("structured_outputs", []),
                    thinking_logs=result.get("thinking_logs", []),
                    sources=result.get("sources", []),
                    retries=retries,
                    execution_time=execution_time
                )

                self._execution_history.append(supervision_result)
                return supervision_result

            except asyncio.TimeoutError:
                last_error = f"Execution timeout ({timeout}s)"
                logger.warning(f"Agent execution timeout, retry {retries + 1}/{max_retries}")

            except Exception as e:
                last_error = str(e)
                logger.warning(f"Agent execution error: {e}, retry {retries + 1}/{max_retries}")

            retries += 1

            # 重试前等待
            if retries <= max_retries:
                await asyncio.sleep(1.0 * retries)  # 指数退避

        # 所有重试都失败
        execution_time = (datetime.now() - start_time).total_seconds()

        supervision_result = SupervisionResult(
            success=False,
            error=last_error,
            retries=retries - 1,
            execution_time=execution_time,
            requires_replanning=True
        )

        self._execution_history.append(supervision_result)
        return supervision_result

    async def _execute_agent(self, agent: Any, request: Any) -> Dict[str, Any]:
        """执行智能体"""
        if hasattr(agent, "process"):
            return await agent.process(
                message=request.message,
                session_id=request.session_id,
                user_id=request.user_id
            )
        else:
            raise ValueError("Agent does not have process method")

    def _validate_result(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """验证结果"""
        # 检查是否有回答
        answer = result.get("answer", "")
        if not answer or len(answer.strip()) == 0:
            return {"valid": False, "reason": "Empty answer"}

        # 检查回答长度
        if len(answer) < 10:
            return {"valid": False, "reason": "Answer too short"}

        # 检查是否包含错误标记
        error_markers = ["抱歉，我无法", "出错了", "系统错误"]
        for marker in error_markers:
            if marker in answer:
                return {"valid": False, "reason": f"Error marker found: {marker}"}

        return {"valid": True, "reason": None}

    def get_execution_history(self, limit: int = 100) -> List[SupervisionResult]:
        """获取执行历史"""
        return self._execution_history[-limit:]

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        if not self._execution_history:
            return {
                "total_executions": 0,
                "success_rate": 0.0,
                "avg_retries": 0.0,
                "avg_execution_time": 0.0
            }

        total = len(self._execution_history)
        successes = sum(1 for r in self._execution_history if r.success)
        total_retries = sum(r.retries for r in self._execution_history)
        total_time = sum(r.execution_time for r in self._execution_history)

        return {
            "total_executions": total,
            "success_rate": successes / total,
            "avg_retries": total_retries / total,
            "avg_execution_time": total_time / total
        }
