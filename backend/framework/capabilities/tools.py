"""
工具能力

提供智能体的工具调用能力:
- 工具注册和发现
- 工具调用和结果处理
- 工具链执行
- 错误处理和重试
"""

from abc import abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Protocol, runtime_checkable, Union
from enum import Enum
import asyncio
import logging
import time

from .base import CapabilityMixin, register_capability
from ..events import Event, EventType, get_event_bus
from ..config import ToolConfig

logger = logging.getLogger(__name__)


class ToolCategory(str, Enum):
    """工具类别"""
    CALCULATION = "calculation"
    SEARCH = "search"
    DATA = "data"
    EXTERNAL = "external"
    UTILITY = "utility"


@dataclass
class ToolParameter:
    """工具参数定义"""
    name: str
    type: str  # string | number | boolean | array | object
    description: str
    required: bool = True
    default: Any = None
    enum: Optional[List[Any]] = None


@dataclass
class ToolDefinition:
    """工具定义"""
    name: str
    description: str
    category: ToolCategory
    parameters: List[ToolParameter] = field(default_factory=list)
    handler: Optional[Callable] = None
    version: str = "1.0.0"
    enabled: bool = True
    rate_limit: Optional[int] = None  # 每分钟最大调用次数
    timeout: int = 30
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_function_schema(self) -> Dict[str, Any]:
        """转换为 OpenAI Function Calling 格式"""
        properties = {}
        required = []

        for param in self.parameters:
            properties[param.name] = {
                "type": param.type,
                "description": param.description
            }
            if param.enum:
                properties[param.name]["enum"] = param.enum
            if param.required:
                required.append(param.name)

        return {
            "name": self.name,
            "description": self.description,
            "parameters": {
                "type": "object",
                "properties": properties,
                "required": required
            }
        }


@dataclass
class ToolResult:
    """工具调用结果"""
    tool_name: str
    success: bool
    result: Any = None
    error: Optional[str] = None
    execution_time: float = 0.0
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ToolCallStats:
    """工具调用统计"""
    total_calls: int = 0
    success_count: int = 0
    error_count: int = 0
    total_time: float = 0.0
    last_called: Optional[datetime] = None

    @property
    def success_rate(self) -> float:
        return self.success_count / self.total_calls if self.total_calls > 0 else 0.0

    @property
    def avg_time(self) -> float:
        return self.total_time / self.total_calls if self.total_calls > 0 else 0.0


@runtime_checkable
class ToolCapability(Protocol):
    """工具能力协议"""

    def register_tool(self, tool: ToolDefinition) -> None:
        """注册工具"""
        ...

    def unregister_tool(self, name: str) -> bool:
        """注销工具"""
        ...

    def list_tools(self, category: Optional[ToolCategory] = None) -> List[ToolDefinition]:
        """列出工具"""
        ...

    async def call_tool(self, name: str, params: Dict[str, Any]) -> ToolResult:
        """调用工具"""
        ...


@register_capability("tools", version="2.0.0", description="工具调用能力")
class ToolMixin(CapabilityMixin):
    """
    工具能力混入

    提供完整的工具管理功能:
    - 工具注册和发现
    - 参数验证
    - 超时控制
    - 重试机制
    - 调用统计
    """

    _capability_name = "tools"
    _capability_version = "2.0.0"

    def __init__(self, config: ToolConfig = None):
        super().__init__()
        self._tool_config = config or ToolConfig()
        self._tools: Dict[str, ToolDefinition] = {}
        self._stats: Dict[str, ToolCallStats] = {}
        self._event_bus = get_event_bus()
        self._call_history: List[ToolResult] = []
        self._rate_limit_counters: Dict[str, List[float]] = {}

        # 注册内置工具
        self._register_builtin_tools()

    async def _do_initialize(self) -> None:
        """初始化工具系统"""
        logger.info(f"Tool system initialized with {len(self._tools)} tools")

    def _register_builtin_tools(self) -> None:
        """注册内置工具"""
        # 补贴计算器
        self.register_tool(ToolDefinition(
            name="subsidy_calculator",
            description="计算装修补贴金额",
            category=ToolCategory.CALCULATION,
            parameters=[
                ToolParameter(name="amount", type="number", description="订单金额"),
                ToolParameter(name="category", type="string", description="商品类别",
                            enum=["家具", "建材", "家电", "软装", "智能家居"])
            ],
            handler=self._calculate_subsidy
        ))

        # ROI 计算器
        self.register_tool(ToolDefinition(
            name="roi_calculator",
            description="计算投资回报率",
            category=ToolCategory.CALCULATION,
            parameters=[
                ToolParameter(name="investment", type="number", description="投资金额"),
                ToolParameter(name="revenue", type="number", description="收入金额"),
                ToolParameter(name="period_days", type="number", description="周期天数", default=30)
            ],
            handler=self._calculate_roi
        ))

        # 价格评估器
        self.register_tool(ToolDefinition(
            name="price_evaluator",
            description="评估装修价格是否合理",
            category=ToolCategory.CALCULATION,
            parameters=[
                ToolParameter(name="category", type="string", description="装修类别"),
                ToolParameter(name="price", type="number", description="报价金额"),
                ToolParameter(name="area", type="number", description="面积(平方米)", required=False)
            ],
            handler=self._evaluate_price
        ))

    def register_tool(self, tool: ToolDefinition) -> None:
        """注册工具"""
        self._tools[tool.name] = tool
        self._stats[tool.name] = ToolCallStats()
        logger.info(f"Registered tool: {tool.name}")

    def unregister_tool(self, name: str) -> bool:
        """注销工具"""
        if name in self._tools:
            del self._tools[name]
            return True
        return False

    def get_tool(self, name: str) -> Optional[ToolDefinition]:
        """获取工具定义"""
        return self._tools.get(name)

    def list_tools(self, category: Optional[ToolCategory] = None) -> List[ToolDefinition]:
        """列出工具"""
        tools = list(self._tools.values())
        if category:
            tools = [t for t in tools if t.category == category]
        return [t for t in tools if t.enabled]

    def get_function_schemas(self) -> List[Dict[str, Any]]:
        """获取所有工具的 Function Calling Schema"""
        return [t.to_function_schema() for t in self.list_tools()]

    async def call_tool(
        self,
        name: str,
        params: Dict[str, Any],
        timeout: Optional[int] = None
    ) -> ToolResult:
        """调用工具"""
        tool = self._tools.get(name)
        if not tool:
            return ToolResult(
                tool_name=name,
                success=False,
                error=f"Tool '{name}' not found"
            )

        if not tool.enabled:
            return ToolResult(
                tool_name=name,
                success=False,
                error=f"Tool '{name}' is disabled"
            )

        # 检查速率限制
        if not self._check_rate_limit(name, tool.rate_limit):
            return ToolResult(
                tool_name=name,
                success=False,
                error="Rate limit exceeded"
            )

        # 发布调用事件
        await self._event_bus.emit(Event(
            type=EventType.TOOL_CALLING,
            payload={"tool_name": name, "params": params},
            source="tools"
        ))

        # 验证参数
        validation_error = self._validate_params(tool, params)
        if validation_error:
            return ToolResult(
                tool_name=name,
                success=False,
                error=validation_error
            )

        # 执行调用
        start_time = time.time()
        result = await self._execute_tool(tool, params, timeout or tool.timeout)
        execution_time = time.time() - start_time

        # 更新统计
        self._update_stats(name, result.success, execution_time)

        # 记录历史
        result.execution_time = execution_time
        self._call_history.append(result)

        # 发布完成事件
        event_type = EventType.TOOL_COMPLETED if result.success else EventType.TOOL_FAILED
        await self._event_bus.emit(Event(
            type=event_type,
            payload={
                "tool_name": name,
                "success": result.success,
                "execution_time": execution_time
            },
            source="tools"
        ))

        return result

    def _validate_params(self, tool: ToolDefinition, params: Dict[str, Any]) -> Optional[str]:
        """验证参数"""
        for param in tool.parameters:
            if param.required and param.name not in params:
                if param.default is None:
                    return f"Missing required parameter: {param.name}"
                params[param.name] = param.default

            if param.name in params:
                value = params[param.name]
                # 类型检查
                if param.type == "number" and not isinstance(value, (int, float)):
                    return f"Parameter '{param.name}' must be a number"
                if param.type == "string" and not isinstance(value, str):
                    return f"Parameter '{param.name}' must be a string"
                if param.type == "boolean" and not isinstance(value, bool):
                    return f"Parameter '{param.name}' must be a boolean"
                # 枚举检查
                if param.enum and value not in param.enum:
                    return f"Parameter '{param.name}' must be one of {param.enum}"

        return None

    async def _execute_tool(
        self,
        tool: ToolDefinition,
        params: Dict[str, Any],
        timeout: int
    ) -> ToolResult:
        """执行工具"""
        if not tool.handler:
            return ToolResult(
                tool_name=tool.name,
                success=False,
                error="Tool handler not implemented"
            )

        try:
            # 支持同步和异步处理器
            if asyncio.iscoroutinefunction(tool.handler):
                result = await asyncio.wait_for(
                    tool.handler(**params),
                    timeout=timeout
                )
            else:
                result = await asyncio.wait_for(
                    asyncio.get_event_loop().run_in_executor(
                        None, lambda: tool.handler(**params)
                    ),
                    timeout=timeout
                )

            return ToolResult(
                tool_name=tool.name,
                success=True,
                result=result
            )

        except asyncio.TimeoutError:
            return ToolResult(
                tool_name=tool.name,
                success=False,
                error=f"Tool execution timeout ({timeout}s)"
            )
        except Exception as e:
            logger.error(f"Tool {tool.name} execution error: {e}")
            return ToolResult(
                tool_name=tool.name,
                success=False,
                error=str(e)
            )

    def _check_rate_limit(self, name: str, limit: Optional[int]) -> bool:
        """检查速率限制"""
        if not limit:
            limit = self._tool_config.rate_limit

        now = time.time()
        if name not in self._rate_limit_counters:
            self._rate_limit_counters[name] = []

        # 清理过期记录
        self._rate_limit_counters[name] = [
            t for t in self._rate_limit_counters[name]
            if now - t < 60
        ]

        if len(self._rate_limit_counters[name]) >= limit:
            return False

        self._rate_limit_counters[name].append(now)
        return True

    def _update_stats(self, name: str, success: bool, execution_time: float) -> None:
        """更新统计"""
        stats = self._stats.get(name)
        if stats:
            stats.total_calls += 1
            stats.total_time += execution_time
            stats.last_called = datetime.now()
            if success:
                stats.success_count += 1
            else:
                stats.error_count += 1

    def get_stats(self, name: Optional[str] = None) -> Union[ToolCallStats, Dict[str, ToolCallStats]]:
        """获取统计信息"""
        if name:
            return self._stats.get(name, ToolCallStats())
        return dict(self._stats)

    def get_call_history(self, limit: int = 100) -> List[ToolResult]:
        """获取调用历史"""
        return self._call_history[-limit:]

    # ==================== 内置工具实现 ====================

    def _calculate_subsidy(self, amount: float, category: str) -> Dict[str, Any]:
        """计算补贴"""
        rates = {
            "家具": (0.05, 2000),
            "建材": (0.03, 1500),
            "家电": (0.04, 1000),
            "软装": (0.06, 800),
            "智能家居": (0.08, 1500)
        }

        rate, max_subsidy = rates.get(category, (0.03, 1000))
        subsidy = min(amount * rate, max_subsidy)

        return {
            "original_amount": amount,
            "category": category,
            "subsidy_rate": f"{rate*100}%",
            "subsidy_amount": round(subsidy, 2),
            "final_amount": round(amount - subsidy, 2),
            "max_subsidy": max_subsidy
        }

    def _calculate_roi(
        self,
        investment: float,
        revenue: float,
        period_days: int = 30
    ) -> Dict[str, Any]:
        """计算 ROI"""
        profit = revenue - investment
        roi = (profit / investment) * 100 if investment > 0 else 0
        daily_roi = roi / period_days if period_days > 0 else 0
        annual_roi = daily_roi * 365

        return {
            "investment": investment,
            "revenue": revenue,
            "profit": round(profit, 2),
            "roi": f"{round(roi, 2)}%",
            "daily_roi": f"{round(daily_roi, 2)}%",
            "annual_roi": f"{round(annual_roi, 2)}%",
            "period_days": period_days,
            "assessment": "优秀" if roi > 20 else "良好" if roi > 10 else "一般" if roi > 0 else "亏损"
        }

    def _evaluate_price(
        self,
        category: str,
        price: float,
        area: Optional[float] = None
    ) -> Dict[str, Any]:
        """评估价格"""
        # 参考价格范围（每平方米）
        price_ranges = {
            "硬装": (800, 1500),
            "软装": (300, 800),
            "全包": (1200, 2500),
            "半包": (600, 1200)
        }

        low, high = price_ranges.get(category, (500, 1500))

        if area:
            unit_price = price / area
            if unit_price < low:
                assessment = "偏低，注意质量"
            elif unit_price > high:
                assessment = "偏高，建议比价"
            else:
                assessment = "价格合理"

            return {
                "category": category,
                "total_price": price,
                "area": area,
                "unit_price": round(unit_price, 2),
                "reference_range": f"{low}-{high}元/㎡",
                "assessment": assessment
            }
        else:
            return {
                "category": category,
                "total_price": price,
                "reference_range": f"{low}-{high}元/㎡",
                "note": "建议提供面积以获得更准确的评估"
            }
