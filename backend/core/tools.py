"""
工具系统
支持工具注册、动态调用、链式组合和参数验证
"""
import json
import time
import inspect
from typing import Any, Callable, Dict, List, Optional, Tuple, Type, Union
from dataclasses import dataclass, field
from enum import Enum
from abc import ABC, abstractmethod
import threading
from functools import wraps


class ToolCategory(str, Enum):
    """工具类别"""
    SEARCH = "search"           # 搜索类
    CALCULATION = "calculation" # 计算类
    DATA = "data"               # 数据类
    EXTERNAL = "external"       # 外部API
    UTILITY = "utility"         # 工具类


@dataclass
class ToolParameter:
    """工具参数定义"""
    name: str
    param_type: Type
    description: str
    required: bool = True
    default: Any = None
    enum_values: List[Any] = None

    def validate(self, value: Any) -> Tuple[bool, str]:
        """验证参数值"""
        if value is None:
            if self.required:
                return False, f"参数 {self.name} 是必需的"
            return True, ""

        if not isinstance(value, self.param_type):
            try:
                # 尝试类型转换
                value = self.param_type(value)
            except (ValueError, TypeError):
                return False, f"参数 {self.name} 类型错误，期望 {self.param_type.__name__}"

        if self.enum_values and value not in self.enum_values:
            return False, f"参数 {self.name} 必须是以下值之一: {self.enum_values}"

        return True, ""


@dataclass
class ToolResult:
    """工具执行结果"""
    success: bool
    data: Any = None
    error: Optional[str] = None
    execution_time: float = 0.0
    metadata: Dict = field(default_factory=dict)

    def to_dict(self) -> Dict:
        return {
            "success": self.success,
            "data": self.data,
            "error": self.error,
            "execution_time": self.execution_time,
            "metadata": self.metadata,
        }


@dataclass
class ToolDefinition:
    """工具定义"""
    name: str
    description: str
    category: ToolCategory
    parameters: List[ToolParameter]
    handler: Callable
    version: str = "1.0.0"
    enabled: bool = True
    requires_auth: bool = False
    rate_limit: Optional[int] = None  # 每分钟调用次数限制
    tags: List[str] = field(default_factory=list)

    # 统计信息
    call_count: int = 0
    total_time: float = 0.0
    error_count: int = 0
    last_called: Optional[float] = None

    def get_schema(self) -> Dict:
        """获取工具Schema（用于LLM）"""
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {
                "type": "object",
                "properties": {
                    p.name: {
                        "type": p.param_type.__name__,
                        "description": p.description,
                        **({"enum": p.enum_values} if p.enum_values else {}),
                        **({"default": p.default} if p.default is not None else {}),
                    }
                    for p in self.parameters
                },
                "required": [p.name for p in self.parameters if p.required],
            },
        }


class ToolRegistry:
    """工具注册中心"""

    def __init__(self):
        self.tools: Dict[str, ToolDefinition] = {}
        self._lock = threading.Lock()
        self._call_history: List[Dict] = []

    def register(self, tool: ToolDefinition) -> bool:
        """注册工具"""
        with self._lock:
            if tool.name in self.tools:
                return False
            self.tools[tool.name] = tool
            return True

    def unregister(self, name: str) -> bool:
        """注销工具"""
        with self._lock:
            if name in self.tools:
                del self.tools[name]
                return True
            return False

    def get(self, name: str) -> Optional[ToolDefinition]:
        """获取工具"""
        return self.tools.get(name)

    def list_tools(self, category: ToolCategory = None,
                   enabled_only: bool = True) -> List[ToolDefinition]:
        """列出工具"""
        tools = list(self.tools.values())
        if category:
            tools = [t for t in tools if t.category == category]
        if enabled_only:
            tools = [t for t in tools if t.enabled]
        return tools

    def get_tools_for_llm(self) -> List[Dict]:
        """获取LLM可用的工具列表"""
        return [t.get_schema() for t in self.list_tools(enabled_only=True)]

    def call(self, name: str, **kwargs) -> ToolResult:
        """调用工具"""
        tool = self.get(name)
        if not tool:
            return ToolResult(success=False, error=f"工具 {name} 不存在")

        if not tool.enabled:
            return ToolResult(success=False, error=f"工具 {name} 已禁用")

        # 参数验证
        for param in tool.parameters:
            value = kwargs.get(param.name, param.default)
            valid, error = param.validate(value)
            if not valid:
                return ToolResult(success=False, error=error)

        # 执行工具
        start_time = time.time()
        try:
            result = tool.handler(**kwargs)
            execution_time = time.time() - start_time

            # 更新统计
            tool.call_count += 1
            tool.total_time += execution_time
            tool.last_called = time.time()

            # 记录调用历史
            self._record_call(name, kwargs, result, execution_time, True)

            return ToolResult(
                success=True,
                data=result,
                execution_time=execution_time
            )
        except Exception as e:
            execution_time = time.time() - start_time
            tool.error_count += 1

            # 记录调用历史
            self._record_call(name, kwargs, None, execution_time, False, str(e))

            return ToolResult(
                success=False,
                error=str(e),
                execution_time=execution_time
            )

    def _record_call(self, name: str, params: Dict, result: Any,
                     execution_time: float, success: bool, error: str = None):
        """记录调用历史"""
        self._call_history.append({
            "tool": name,
            "params": params,
            "result": result if success else None,
            "execution_time": execution_time,
            "success": success,
            "error": error,
            "timestamp": time.time(),
        })
        # 保留最近1000条记录
        if len(self._call_history) > 1000:
            self._call_history = self._call_history[-1000:]

    def get_statistics(self) -> Dict:
        """获取统计信息"""
        stats = {}
        for name, tool in self.tools.items():
            stats[name] = {
                "call_count": tool.call_count,
                "total_time": tool.total_time,
                "avg_time": tool.total_time / tool.call_count if tool.call_count > 0 else 0,
                "error_count": tool.error_count,
                "error_rate": tool.error_count / tool.call_count if tool.call_count > 0 else 0,
                "last_called": tool.last_called,
            }
        return stats


class ToolChain:
    """工具链"""

    def __init__(self, registry: ToolRegistry):
        self.registry = registry
        self.steps: List[Dict] = []

    def add_step(self, tool_name: str, params: Dict = None,
                 output_key: str = None, condition: Callable = None):
        """添加步骤"""
        self.steps.append({
            "tool": tool_name,
            "params": params or {},
            "output_key": output_key or f"step_{len(self.steps)}",
            "condition": condition,
        })
        return self

    def execute(self, initial_context: Dict = None) -> Dict:
        """执行工具链"""
        context = initial_context or {}
        results = {}

        for i, step in enumerate(self.steps):
            # 检查条件
            if step["condition"] and not step["condition"](context):
                continue

            # 解析参数（支持从上下文引用）
            params = {}
            for key, value in step["params"].items():
                if isinstance(value, str) and value.startswith("$"):
                    # 从上下文获取值
                    ref_key = value[1:]
                    params[key] = context.get(ref_key, results.get(ref_key))
                else:
                    params[key] = value

            # 执行工具
            result = self.registry.call(step["tool"], **params)

            # 存储结果
            output_key = step["output_key"]
            results[output_key] = result.data if result.success else None
            context[output_key] = results[output_key]

            # 如果失败，记录错误
            if not result.success:
                results[f"{output_key}_error"] = result.error

        return results


# === 工具装饰器 ===

def tool(name: str, description: str, category: ToolCategory = ToolCategory.UTILITY,
         tags: List[str] = None, requires_auth: bool = False):
    """工具装饰器"""
    def decorator(func: Callable):
        # 从函数签名提取参数
        sig = inspect.signature(func)
        parameters = []
        for param_name, param in sig.parameters.items():
            param_type = param.annotation if param.annotation != inspect.Parameter.empty else str
            required = param.default == inspect.Parameter.empty
            default = None if required else param.default

            parameters.append(ToolParameter(
                name=param_name,
                param_type=param_type,
                description=f"参数 {param_name}",
                required=required,
                default=default,
            ))

        # 创建工具定义
        tool_def = ToolDefinition(
            name=name,
            description=description,
            category=category,
            parameters=parameters,
            handler=func,
            tags=tags or [],
            requires_auth=requires_auth,
        )

        # 注册到全局注册中心
        get_tool_registry().register(tool_def)

        @wraps(func)
        def wrapper(*args, **kwargs):
            return func(*args, **kwargs)

        wrapper._tool_definition = tool_def
        return wrapper

    return decorator


# === 内置工具 ===

def _subsidy_calculator(amount: float, category: str) -> Dict:
    """补贴计算器"""
    from backend.config.business_rules import SUBSIDY_RULES

    if category not in SUBSIDY_RULES:
        return {"error": f"不支持的品类: {category}"}

    rule = SUBSIDY_RULES[category]
    calculated = amount * rule["rate"]
    final = min(calculated, rule["max"])

    return {
        "category": category,
        "original_amount": amount,
        "subsidy_rate": rule["rate"],
        "calculated_amount": calculated,
        "max_limit": rule["max"],
        "final_amount": final,
        "explanation": f"{category}补贴 = {amount:.0f} × {rule['rate']*100:.0f}% = {calculated:.0f}元"
                       + (f"，超过上限{rule['max']:.0f}元，实际补贴{final:.0f}元"
                          if calculated > rule["max"] else ""),
    }


def _roi_calculator(investment: float, revenue: float,
                    period_days: int = 30) -> Dict:
    """ROI计算器"""
    if investment <= 0:
        return {"error": "投入金额必须大于0"}

    roi = (revenue - investment) / investment * 100
    daily_revenue = revenue / period_days
    payback_days = investment / daily_revenue if daily_revenue > 0 else float('inf')

    return {
        "investment": investment,
        "revenue": revenue,
        "period_days": period_days,
        "roi_percent": round(roi, 2),
        "daily_revenue": round(daily_revenue, 2),
        "payback_days": round(payback_days, 1) if payback_days != float('inf') else None,
        "evaluation": "优秀" if roi >= 200 else "良好" if roi >= 100 else "一般" if roi >= 50 else "较低" if roi >= 0 else "亏损",
    }


def _price_evaluator(category: str, price: float, area: float = None) -> Dict:
    """价格评估器"""
    # 市场参考价格（元/平米或元/件）
    MARKET_PRICES = {
        "瓷砖": {"low": 50, "mid": 150, "high": 400, "unit": "元/平米"},
        "地板": {"low": 80, "mid": 200, "high": 500, "unit": "元/平米"},
        "乳胶漆": {"low": 20, "mid": 50, "high": 100, "unit": "元/平米"},
        "橱柜": {"low": 800, "mid": 1500, "high": 3000, "unit": "元/延米"},
        "沙发": {"low": 3000, "mid": 8000, "high": 20000, "unit": "元/套"},
        "床": {"low": 2000, "mid": 5000, "high": 15000, "unit": "元/张"},
    }

    if category not in MARKET_PRICES:
        return {"error": f"暂不支持 {category} 的价格评估"}

    ref = MARKET_PRICES[category]
    unit_price = price / area if area else price

    if unit_price <= ref["low"]:
        level = "低价位"
        suggestion = "价格较低，注意检查质量"
    elif unit_price <= ref["mid"]:
        level = "中等价位"
        suggestion = "价格合理，性价比较好"
    elif unit_price <= ref["high"]:
        level = "中高价位"
        suggestion = "价格偏高，确认品牌和品质"
    else:
        level = "高价位"
        suggestion = "价格较高，建议多比较"

    return {
        "category": category,
        "price": price,
        "area": area,
        "unit_price": round(unit_price, 2),
        "market_reference": ref,
        "price_level": level,
        "suggestion": suggestion,
    }


def _decoration_timeline(house_area: float, style: str = "现代简约") -> Dict:
    """装修工期估算"""
    # 基础工期（天）
    BASE_TIMELINE = {
        "前期准备": 7,
        "设计阶段": 14,
        "拆改阶段": 7,
        "水电阶段": 10,
        "泥木阶段": 21,
        "油漆阶段": 14,
        "安装阶段": 10,
        "软装入住": 7,
    }

    # 面积系数
    area_factor = 1.0
    if house_area > 150:
        area_factor = 1.3
    elif house_area > 100:
        area_factor = 1.15

    # 风格系数
    style_factors = {
        "现代简约": 1.0,
        "北欧": 1.0,
        "新中式": 1.2,
        "轻奢": 1.15,
        "欧式": 1.3,
    }
    style_factor = style_factors.get(style, 1.0)

    # 计算各阶段工期
    timeline = {}
    total_days = 0
    for stage, base_days in BASE_TIMELINE.items():
        days = int(base_days * area_factor * style_factor)
        timeline[stage] = days
        total_days += days

    return {
        "house_area": house_area,
        "style": style,
        "timeline": timeline,
        "total_days": total_days,
        "estimated_months": round(total_days / 30, 1),
        "note": "实际工期可能因施工条件、材料供应等因素有所变化",
    }


def register_builtin_tools(registry: ToolRegistry):
    """注册内置工具"""
    # 补贴计算器
    registry.register(ToolDefinition(
        name="subsidy_calculator",
        description="计算装修补贴金额，根据品类和订单金额计算可获得的补贴",
        category=ToolCategory.CALCULATION,
        parameters=[
            ToolParameter("amount", float, "订单金额（元）", required=True),
            ToolParameter("category", str, "商品品类",
                         required=True, enum_values=["家具", "建材", "家电", "软装", "智能家居"]),
        ],
        handler=_subsidy_calculator,
        tags=["补贴", "计算", "C端"],
    ))

    # ROI计算器
    registry.register(ToolDefinition(
        name="roi_calculator",
        description="计算投入产出比(ROI)，评估营销投入效果",
        category=ToolCategory.CALCULATION,
        parameters=[
            ToolParameter("investment", float, "投入金额（元）", required=True),
            ToolParameter("revenue", float, "收入金额（元）", required=True),
            ToolParameter("period_days", int, "统计周期（天）", required=False, default=30),
        ],
        handler=_roi_calculator,
        tags=["ROI", "计算", "B端"],
    ))

    # 价格评估器
    registry.register(ToolDefinition(
        name="price_evaluator",
        description="评估装修材料或家具价格是否合理",
        category=ToolCategory.CALCULATION,
        parameters=[
            ToolParameter("category", str, "商品品类", required=True),
            ToolParameter("price", float, "价格（元）", required=True),
            ToolParameter("area", float, "面积（平米），如适用", required=False),
        ],
        handler=_price_evaluator,
        tags=["价格", "评估", "C端"],
    ))

    # 装修工期估算
    registry.register(ToolDefinition(
        name="decoration_timeline",
        description="估算装修工期，根据房屋面积和装修风格",
        category=ToolCategory.CALCULATION,
        parameters=[
            ToolParameter("house_area", float, "房屋面积（平米）", required=True),
            ToolParameter("style", str, "装修风格", required=False, default="现代简约"),
        ],
        handler=_decoration_timeline,
        tags=["工期", "估算", "C端"],
    ))


# 全局工具注册中心
_tool_registry: Optional[ToolRegistry] = None
_registry_lock = threading.Lock()


def get_tool_registry() -> ToolRegistry:
    """获取全局工具注册中心"""
    global _tool_registry
    if _tool_registry is None:
        with _registry_lock:
            if _tool_registry is None:
                _tool_registry = ToolRegistry()
                register_builtin_tools(_tool_registry)
    return _tool_registry
