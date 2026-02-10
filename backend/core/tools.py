"""
工具系统
支持工具注册、动态调用、链式组合和参数验证
"""
import json
import time
import inspect
import asyncio
import concurrent.futures
from functools import wraps
from typing import Any, Callable, Dict, List, Optional, Tuple, Type, Union
from dataclasses import dataclass, field
from enum import Enum
from abc import ABC, abstractmethod
import threading
from backend.core.cache import CircularBuffer
from backend.core.logging_config import get_logger

logger = get_logger("tools")


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

    def __init__(self, max_history: int = 1000):
        self.tools: Dict[str, ToolDefinition] = {}
        self._lock = threading.Lock()
        self._call_history = CircularBuffer(max_size=max_history)

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

    def call(self, name: str, timeout: float = 30.0, **kwargs) -> ToolResult:
        """
        调用工具

        Args:
            name: 工具名称
            timeout: 超时时间（秒），默认30秒
            **kwargs: 工具参数

        Returns:
            ToolResult: 工具执行结果
        """
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

        # 执行工具（带超时控制）
        start_time = time.time()
        try:
            result = self._execute_with_timeout(tool.handler, timeout, **kwargs)
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
        except TimeoutError as e:
            execution_time = time.time() - start_time
            tool.error_count += 1
            error_msg = f"工具 {name} 执行超时（{timeout}秒）"

            # 记录调用历史
            self._record_call(name, kwargs, None, execution_time, False, error_msg)

            return ToolResult(
                success=False,
                error=error_msg,
                execution_time=execution_time,
                metadata={"timeout": True}
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

    def _execute_with_timeout(self, handler: Callable, timeout: float, **kwargs) -> Any:
        """
        带超时控制的工具执行

        Args:
            handler: 工具处理函数
            timeout: 超时时间（秒）
            **kwargs: 工具参数

        Returns:
            工具执行结果

        Raises:
            TimeoutError: 执行超时
        """
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(handler, **kwargs)
            try:
                return future.result(timeout=timeout)
            except concurrent.futures.TimeoutError:
                # 尝试取消任务
                future.cancel()
                raise TimeoutError(f"执行超时（{timeout}秒）")

    async def call_async(self, name: str, timeout: float = 30.0, **kwargs) -> ToolResult:
        """
        异步调用工具（带超时控制）

        Args:
            name: 工具名称
            timeout: 超时时间（秒），默认30秒
            **kwargs: 工具参数

        Returns:
            ToolResult: 工具执行结果
        """
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

        # 异步执行工具（带超时控制）
        start_time = time.time()
        try:
            # 在线程池中执行同步函数
            loop = asyncio.get_event_loop()
            result = await asyncio.wait_for(
                loop.run_in_executor(None, lambda: tool.handler(**kwargs)),
                timeout=timeout
            )
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
        except asyncio.TimeoutError:
            execution_time = time.time() - start_time
            tool.error_count += 1
            error_msg = f"工具 {name} 执行超时（{timeout}秒）"

            # 记录调用历史
            self._record_call(name, kwargs, None, execution_time, False, error_msg)

            return ToolResult(
                success=False,
                error=error_msg,
                execution_time=execution_time,
                metadata={"timeout": True}
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
        """记录调用历史（使用循环缓冲区，自动限制大小）"""
        self._call_history.append({
            "tool": name,
            "params": params,
            "result": result if success else None,
            "execution_time": execution_time,
            "success": success,
            "error": error,
            "timestamp": time.time(),
        })

        # 记录日志
        if success:
            logger.debug(f"工具调用成功: {name}", extra={
                "tool": name,
                "duration_ms": int(execution_time * 1000),
            })
        else:
            logger.warning(f"工具调用失败: {name}", extra={
                "tool": name,
                "error": error,
                "duration_ms": int(execution_time * 1000),
            })

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


def _budget_planner(total_budget: float, house_area: float,
                    style: str = "现代简约") -> Dict:
    """装修预算规划器"""
    # 预算分配比例（根据风格调整）
    BUDGET_RATIOS = {
        "现代简约": {
            "硬装": 0.40, "主材": 0.25, "家具": 0.20,
            "家电": 0.10, "软装": 0.05
        },
        "北欧": {
            "硬装": 0.35, "主材": 0.25, "家具": 0.25,
            "家电": 0.10, "软装": 0.05
        },
        "新中式": {
            "硬装": 0.35, "主材": 0.30, "家具": 0.20,
            "家电": 0.08, "软装": 0.07
        },
        "轻奢": {
            "硬装": 0.30, "主材": 0.30, "家具": 0.25,
            "家电": 0.08, "软装": 0.07
        },
    }

    ratios = BUDGET_RATIOS.get(style, BUDGET_RATIOS["现代简约"])

    # 计算各项预算
    budget_breakdown = {}
    for item, ratio in ratios.items():
        budget_breakdown[item] = {
            "amount": round(total_budget * ratio, 2),
            "ratio": f"{ratio * 100:.0f}%",
            "per_sqm": round(total_budget * ratio / house_area, 2),
        }

    # 计算单价
    per_sqm = total_budget / house_area

    # 评估预算水平
    if per_sqm < 800:
        level = "经济型"
        suggestion = "预算较紧，建议选择性价比高的材料，可以考虑部分软装后期添置"
    elif per_sqm < 1500:
        level = "舒适型"
        suggestion = "预算适中，可以保证基本品质，建议在主材上适当投入"
    elif per_sqm < 2500:
        level = "品质型"
        suggestion = "预算充足，可以选择中高端材料和品牌家具"
    else:
        level = "豪华型"
        suggestion = "预算充裕，可以追求高端定制和进口材料"

    return {
        "total_budget": total_budget,
        "house_area": house_area,
        "style": style,
        "per_sqm": round(per_sqm, 2),
        "budget_level": level,
        "breakdown": budget_breakdown,
        "suggestion": suggestion,
    }


def _material_calculator(material_type: str, area: float,
                         loss_rate: float = 0.05) -> Dict:
    """材料用量计算器"""
    # 材料规格和用量参考
    MATERIAL_SPECS = {
        "瓷砖": {"unit": "平米", "spec": "800x800mm", "per_sqm": 1.0, "price_range": (50, 400)},
        "地板": {"unit": "平米", "spec": "1200x200mm", "per_sqm": 1.0, "price_range": (80, 500)},
        "乳胶漆": {"unit": "升", "spec": "5L/桶", "per_sqm": 0.25, "price_range": (200, 800)},
        "墙纸": {"unit": "卷", "spec": "0.53x10m", "per_sqm": 0.2, "price_range": (50, 300)},
        "水泥": {"unit": "袋", "spec": "50kg/袋", "per_sqm": 0.5, "price_range": (20, 35)},
        "沙子": {"unit": "吨", "spec": "散装", "per_sqm": 0.03, "price_range": (80, 150)},
        "电线": {"unit": "米", "spec": "2.5平方", "per_sqm": 8, "price_range": (2, 5)},
        "水管": {"unit": "米", "spec": "PPR管", "per_sqm": 3, "price_range": (8, 20)},
    }

    if material_type not in MATERIAL_SPECS:
        return {"error": f"暂不支持 {material_type} 的用量计算"}

    spec = MATERIAL_SPECS[material_type]
    base_amount = area * spec["per_sqm"]
    total_amount = base_amount * (1 + loss_rate)

    price_low = total_amount * spec["price_range"][0]
    price_high = total_amount * spec["price_range"][1]

    return {
        "material": material_type,
        "area": area,
        "spec": spec["spec"],
        "unit": spec["unit"],
        "base_amount": round(base_amount, 2),
        "loss_rate": f"{loss_rate * 100:.0f}%",
        "total_amount": round(total_amount, 2),
        "price_estimate": {
            "low": round(price_low, 2),
            "high": round(price_high, 2),
            "unit_price_range": spec["price_range"],
        },
        "tips": f"建议多备 {loss_rate * 100:.0f}% 的损耗量，实际用量可能因施工工艺有所差异",
    }


def _merchant_score_calculator(monthly_orders: int, good_rate: float,
                                response_time: float, years: int = 1) -> Dict:
    """商家评分计算器（B端）"""
    # 评分权重
    WEIGHTS = {
        "order_volume": 0.30,    # 订单量
        "good_rate": 0.35,       # 好评率
        "response": 0.20,        # 响应速度
        "experience": 0.15,      # 经营年限
    }

    # 订单量评分（满分100）
    if monthly_orders >= 100:
        order_score = 100
    elif monthly_orders >= 50:
        order_score = 80
    elif monthly_orders >= 20:
        order_score = 60
    else:
        order_score = 40

    # 好评率评分
    good_score = good_rate * 100

    # 响应速度评分（分钟）
    if response_time <= 5:
        response_score = 100
    elif response_time <= 15:
        response_score = 80
    elif response_time <= 30:
        response_score = 60
    else:
        response_score = 40

    # 经营年限评分
    if years >= 5:
        exp_score = 100
    elif years >= 3:
        exp_score = 80
    elif years >= 1:
        exp_score = 60
    else:
        exp_score = 40

    # 综合评分
    total_score = (
        order_score * WEIGHTS["order_volume"] +
        good_score * WEIGHTS["good_rate"] +
        response_score * WEIGHTS["response"] +
        exp_score * WEIGHTS["experience"]
    )

    # 评级
    if total_score >= 90:
        level = "金牌商家"
        badge = "🥇"
    elif total_score >= 80:
        level = "银牌商家"
        badge = "🥈"
    elif total_score >= 70:
        level = "铜牌商家"
        badge = "🥉"
    else:
        level = "普通商家"
        badge = ""

    return {
        "scores": {
            "order_volume": round(order_score, 1),
            "good_rate": round(good_score, 1),
            "response": round(response_score, 1),
            "experience": round(exp_score, 1),
        },
        "weights": WEIGHTS,
        "total_score": round(total_score, 1),
        "level": level,
        "badge": badge,
        "suggestions": _get_merchant_suggestions(order_score, good_score, response_score),
    }


def _get_merchant_suggestions(order_score: float, good_score: float,
                               response_score: float) -> List[str]:
    """获取商家改进建议"""
    suggestions = []
    if order_score < 60:
        suggestions.append("建议增加营销投入，提升店铺曝光度")
    if good_score < 80:
        suggestions.append("关注客户反馈，提升服务质量和产品品质")
    if response_score < 60:
        suggestions.append("提高响应速度，建议使用自动回复和客服工具")
    if not suggestions:
        suggestions.append("各项指标表现良好，继续保持！")
    return suggestions


# === 新增实用工具 ===

def _material_comparator(materials: str, dimensions: str = None) -> Dict:
    """
    材料对比分析工具（C端）

    对比不同材料的特性，帮助用户做出选择

    Args:
        materials: 要对比的材料，用逗号分隔，如 "瓷砖,木地板"
        dimensions: 对比维度，用逗号分隔，如 "价格,耐用性,环保性"

    Returns:
        对比分析结果
    """
    # 材料数据库
    MATERIAL_DATA = {
        "瓷砖": {
            "价格": {"range": "50-400元/㎡", "level": "中等", "score": 3},
            "耐用性": {"description": "耐磨耐用，使用寿命长", "score": 5},
            "环保性": {"description": "无甲醛释放，环保性好", "score": 5},
            "舒适度": {"description": "冬冷夏凉，脚感较硬", "score": 2},
            "维护": {"description": "易清洁，不怕水", "score": 5},
            "适用空间": ["客厅", "厨房", "卫生间", "阳台"],
            "优点": ["耐磨", "防水", "易清洁", "花色多"],
            "缺点": ["脚感硬", "冬天冷", "施工复杂"],
        },
        "木地板": {
            "价格": {"range": "80-500元/㎡", "level": "中高", "score": 2},
            "耐用性": {"description": "需要保养，怕水怕划", "score": 3},
            "环保性": {"description": "实木环保，复合板需注意甲醛", "score": 3},
            "舒适度": {"description": "脚感温暖舒适", "score": 5},
            "维护": {"description": "需定期保养，怕水", "score": 2},
            "适用空间": ["客厅", "卧室", "书房"],
            "优点": ["脚感好", "温馨", "美观"],
            "缺点": ["怕水", "需保养", "价格较高"],
        },
        "大理石": {
            "价格": {"range": "200-1000元/㎡", "level": "高", "score": 1},
            "耐用性": {"description": "硬度高，但易渗色", "score": 4},
            "环保性": {"description": "天然材料，需注意辐射", "score": 4},
            "舒适度": {"description": "冬冷夏凉，脚感硬", "score": 2},
            "维护": {"description": "需定期保养，易渗色", "score": 2},
            "适用空间": ["客厅", "玄关", "卫生间台面"],
            "优点": ["高档", "美观", "独特纹理"],
            "缺点": ["价格高", "易渗色", "需保养"],
        },
        "乳胶漆": {
            "价格": {"range": "20-100元/㎡", "level": "低", "score": 5},
            "耐用性": {"description": "一般5-8年需重刷", "score": 3},
            "环保性": {"description": "选择大品牌环保性好", "score": 4},
            "舒适度": {"description": "视觉舒适，可调色", "score": 4},
            "维护": {"description": "可擦洗，修补方便", "score": 4},
            "适用空间": ["客厅", "卧室", "书房", "餐厅"],
            "优点": ["价格低", "颜色多", "施工简单"],
            "缺点": ["不耐脏", "需重刷", "单调"],
        },
        "壁纸": {
            "价格": {"range": "50-300元/㎡", "level": "中等", "score": 3},
            "耐用性": {"description": "一般5-10年，怕潮", "score": 3},
            "环保性": {"description": "需注意胶水环保性", "score": 3},
            "舒适度": {"description": "花色丰富，装饰性强", "score": 5},
            "维护": {"description": "不耐水，修补困难", "score": 2},
            "适用空间": ["客厅", "卧室", "书房"],
            "优点": ["花色多", "装饰性强", "遮盖力好"],
            "缺点": ["怕潮", "接缝明显", "更换麻烦"],
        },
        "硅藻泥": {
            "价格": {"range": "80-200元/㎡", "level": "中高", "score": 2},
            "耐用性": {"description": "使用寿命长，不易脱落", "score": 4},
            "环保性": {"description": "可吸附甲醛，环保性极好", "score": 5},
            "舒适度": {"description": "调节湿度，质感好", "score": 4},
            "维护": {"description": "不耐水，不可擦洗", "score": 2},
            "适用空间": ["客厅", "卧室", "书房"],
            "优点": ["环保", "吸附甲醛", "调节湿度"],
            "缺点": ["价格高", "不耐水", "颜色有限"],
        },
    }

    # 解析材料列表
    material_list = [m.strip() for m in materials.split(",") if m.strip()]
    if len(material_list) < 2:
        return {"error": "请至少提供两种材料进行对比"}

    # 解析对比维度
    if dimensions:
        dimension_list = [d.strip() for d in dimensions.split(",") if d.strip()]
    else:
        dimension_list = ["价格", "耐用性", "环保性", "舒适度", "维护"]

    # 构建对比结果
    comparison = {
        "materials": [],
        "dimensions": dimension_list,
        "comparison_table": [],
        "recommendations": [],
    }

    for material in material_list:
        if material not in MATERIAL_DATA:
            comparison["materials"].append({
                "name": material,
                "error": f"暂不支持 {material} 的对比分析"
            })
            continue

        data = MATERIAL_DATA[material]
        material_info = {
            "name": material,
            "适用空间": data.get("适用空间", []),
            "优点": data.get("优点", []),
            "缺点": data.get("缺点", []),
            "scores": {}
        }

        for dim in dimension_list:
            if dim in data:
                dim_data = data[dim]
                if isinstance(dim_data, dict):
                    material_info["scores"][dim] = {
                        "value": dim_data.get("range") or dim_data.get("description", ""),
                        "score": dim_data.get("score", 3),
                        "level": dim_data.get("level", "中等")
                    }

        comparison["materials"].append(material_info)

    # 生成对比表格
    for dim in dimension_list:
        row = {"dimension": dim, "values": []}
        for mat_info in comparison["materials"]:
            if "error" in mat_info:
                row["values"].append({"material": mat_info["name"], "value": "N/A", "score": 0})
            else:
                score_data = mat_info.get("scores", {}).get(dim, {})
                row["values"].append({
                    "material": mat_info["name"],
                    "value": score_data.get("value", "N/A"),
                    "score": score_data.get("score", 0)
                })
        comparison["comparison_table"].append(row)

    # 生成推荐建议
    valid_materials = [m for m in comparison["materials"] if "error" not in m]
    if len(valid_materials) >= 2:
        # 计算综合得分
        for mat in valid_materials:
            total_score = sum(s.get("score", 0) for s in mat.get("scores", {}).values())
            mat["total_score"] = total_score

        # 按得分排序
        sorted_materials = sorted(valid_materials, key=lambda x: x.get("total_score", 0), reverse=True)

        if sorted_materials:
            best = sorted_materials[0]
            comparison["recommendations"].append(
                f"综合评分最高: {best['name']}（总分 {best.get('total_score', 0)}）"
            )

            # 针对不同需求的推荐
            for dim in dimension_list:
                dim_scores = [(m["name"], m.get("scores", {}).get(dim, {}).get("score", 0))
                              for m in valid_materials]
                dim_scores.sort(key=lambda x: x[1], reverse=True)
                if dim_scores:
                    comparison["recommendations"].append(
                        f"最注重{dim}: 推荐 {dim_scores[0][0]}"
                    )

    return comparison


def _quote_validator(items: str, total_amount: float = None,
                     house_area: float = None) -> Dict:
    """
    装修报价审核工具（C端）

    帮助用户识别报价单中的不合理项目

    Args:
        items: 报价项目，格式为 "项目名:金额" 用分号分隔，如 "水电改造:15000;瓷砖铺贴:12000"
        total_amount: 报价总金额（可选）
        house_area: 房屋面积（可选，用于计算单价）

    Returns:
        审核结果
    """
    # 市场参考价格（元/平米或元/项）
    MARKET_PRICES = {
        "水电改造": {"unit": "元/㎡", "low": 80, "mid": 120, "high": 180, "type": "area"},
        "防水": {"unit": "元/㎡", "low": 30, "mid": 50, "high": 80, "type": "area"},
        "瓷砖铺贴": {"unit": "元/㎡", "low": 40, "mid": 60, "high": 100, "type": "area"},
        "地板安装": {"unit": "元/㎡", "low": 20, "mid": 35, "high": 50, "type": "area"},
        "墙面处理": {"unit": "元/㎡", "low": 25, "mid": 40, "high": 60, "type": "area"},
        "吊顶": {"unit": "元/㎡", "low": 80, "mid": 120, "high": 200, "type": "area"},
        "橱柜": {"unit": "元/延米", "low": 800, "mid": 1500, "high": 3000, "type": "fixed"},
        "衣柜": {"unit": "元/㎡", "low": 500, "mid": 800, "high": 1500, "type": "area"},
        "木门": {"unit": "元/樘", "low": 800, "mid": 1500, "high": 3000, "type": "fixed"},
        "开关插座": {"unit": "元/个", "low": 10, "mid": 30, "high": 80, "type": "fixed"},
        "灯具安装": {"unit": "元/个", "low": 20, "mid": 50, "high": 100, "type": "fixed"},
        "拆除": {"unit": "元/㎡", "low": 30, "mid": 50, "high": 80, "type": "area"},
        "垃圾清运": {"unit": "元/次", "low": 300, "mid": 500, "high": 1000, "type": "fixed"},
    }

    # 解析报价项目
    item_list = []
    for item_str in items.split(";"):
        if ":" in item_str:
            parts = item_str.strip().split(":")
            if len(parts) == 2:
                try:
                    item_list.append({
                        "name": parts[0].strip(),
                        "amount": float(parts[1].strip())
                    })
                except ValueError:
                    continue

    if not item_list:
        return {"error": "无法解析报价项目，请使用格式: 项目名:金额;项目名:金额"}

    # 审核结果
    result = {
        "items": [],
        "summary": {
            "total_quoted": sum(item["amount"] for item in item_list),
            "reasonable_items": 0,
            "high_items": 0,
            "low_items": 0,
            "unknown_items": 0,
        },
        "warnings": [],
        "suggestions": [],
    }

    # 审核每个项目
    for item in item_list:
        name = item["name"]
        amount = item["amount"]

        item_result = {
            "name": name,
            "quoted_amount": amount,
            "evaluation": "未知",
            "market_reference": None,
            "notes": []
        }

        # 查找匹配的市场价格
        matched_ref = None
        for ref_name, ref_data in MARKET_PRICES.items():
            if ref_name in name or name in ref_name:
                matched_ref = (ref_name, ref_data)
                break

        if matched_ref:
            ref_name, ref_data = matched_ref
            item_result["market_reference"] = {
                "name": ref_name,
                "unit": ref_data["unit"],
                "range": f"{ref_data['low']}-{ref_data['high']}{ref_data['unit']}"
            }

            # 计算单价（如果有面积）
            if house_area and ref_data["type"] == "area":
                unit_price = amount / house_area
                item_result["unit_price"] = round(unit_price, 2)

                if unit_price < ref_data["low"]:
                    item_result["evaluation"] = "偏低"
                    item_result["notes"].append("价格低于市场价，注意检查材料和工艺质量")
                    result["summary"]["low_items"] += 1
                elif unit_price <= ref_data["mid"]:
                    item_result["evaluation"] = "合理"
                    result["summary"]["reasonable_items"] += 1
                elif unit_price <= ref_data["high"]:
                    item_result["evaluation"] = "中高"
                    item_result["notes"].append("价格偏高，可以尝试议价")
                    result["summary"]["reasonable_items"] += 1
                else:
                    item_result["evaluation"] = "偏高"
                    item_result["notes"].append("价格明显高于市场价，建议重新询价")
                    result["summary"]["high_items"] += 1
                    result["warnings"].append(f"{name} 报价偏高，建议核实")
            else:
                # 无法计算单价，给出参考范围
                item_result["notes"].append(f"市场参考价: {ref_data['low']}-{ref_data['high']}{ref_data['unit']}")
                result["summary"]["unknown_items"] += 1
        else:
            item_result["evaluation"] = "未知"
            item_result["notes"].append("暂无市场参考价格")
            result["summary"]["unknown_items"] += 1

        result["items"].append(item_result)

    # 生成总体建议
    if result["summary"]["high_items"] > 0:
        result["suggestions"].append(
            f"有 {result['summary']['high_items']} 项报价偏高，建议与装修公司沟通或多询几家"
        )

    if result["summary"]["low_items"] > 0:
        result["suggestions"].append(
            f"有 {result['summary']['low_items']} 项报价偏低，注意确认材料品牌和施工工艺"
        )

    if house_area:
        avg_price = result["summary"]["total_quoted"] / house_area
        result["summary"]["average_price_per_sqm"] = round(avg_price, 2)

        if avg_price < 500:
            result["suggestions"].append("整体单价较低，属于经济型装修，注意把控质量")
        elif avg_price < 1000:
            result["suggestions"].append("整体单价适中，属于舒适型装修")
        elif avg_price < 1500:
            result["suggestions"].append("整体单价较高，属于品质型装修")
        else:
            result["suggestions"].append("整体单价很高，属于高端装修，确保物有所值")

    return result


def _customer_analyzer(customer_info: str, interaction_history: str = None) -> Dict:
    """
    客户意向分析工具（B端）

    分析客户的购买意向和偏好，提供个性化话术建议

    Args:
        customer_info: 客户信息，格式为 "key:value" 用分号分隔
                      如 "预算:20万;面积:100平;风格:现代简约;阶段:设计中"
        interaction_history: 交互历史，用分号分隔的关键词
                            如 "询问价格;对比品牌;关注环保"

    Returns:
        分析结果和话术建议
    """
    # 解析客户信息
    info = {}
    for item in customer_info.split(";"):
        if ":" in item:
            parts = item.strip().split(":")
            if len(parts) == 2:
                info[parts[0].strip()] = parts[1].strip()

    # 解析交互历史
    history = []
    if interaction_history:
        history = [h.strip() for h in interaction_history.split(";") if h.strip()]

    # 分析结果
    result = {
        "customer_profile": {},
        "intent_analysis": {},
        "recommended_approach": {},
        "talking_points": [],
        "warnings": [],
    }

    # 1. 客户画像分析
    profile = result["customer_profile"]

    # 预算分析
    budget_str = info.get("预算", "")
    if budget_str:
        try:
            # 提取数字
            import re
            numbers = re.findall(r'(\d+(?:\.\d+)?)', budget_str)
            if numbers:
                budget = float(numbers[0])
                if "万" in budget_str:
                    budget *= 10000
                profile["budget"] = budget
                profile["budget_level"] = (
                    "经济型" if budget < 100000 else
                    "舒适型" if budget < 200000 else
                    "品质型" if budget < 500000 else
                    "高端型"
                )
        except:
            pass

    # 面积分析
    area_str = info.get("面积", "")
    if area_str:
        try:
            import re
            numbers = re.findall(r'(\d+(?:\.\d+)?)', area_str)
            if numbers:
                profile["area"] = float(numbers[0])
        except:
            pass

    # 风格偏好
    style = info.get("风格", "")
    if style:
        profile["preferred_style"] = style

    # 装修阶段
    stage = info.get("阶段", "")
    if stage:
        profile["stage"] = stage

    # 2. 购买意向分析
    intent = result["intent_analysis"]

    # 基于交互历史分析意向
    intent_signals = {
        "high": ["询问价格", "要求报价", "预约量房", "对比方案", "询问工期", "要求看样"],
        "medium": ["了解品牌", "关注环保", "询问材料", "看案例", "问售后"],
        "low": ["随便看看", "还在考虑", "不急", "先了解"]
    }

    high_signals = sum(1 for h in history if any(s in h for s in intent_signals["high"]))
    medium_signals = sum(1 for h in history if any(s in h for s in intent_signals["medium"]))
    low_signals = sum(1 for h in history if any(s in h for s in intent_signals["low"]))

    total_signals = high_signals + medium_signals + low_signals
    if total_signals > 0:
        intent["score"] = round((high_signals * 3 + medium_signals * 2 + low_signals) / (total_signals * 3) * 100)
    else:
        intent["score"] = 50  # 默认中等意向

    intent["level"] = (
        "高意向" if intent["score"] >= 70 else
        "中等意向" if intent["score"] >= 40 else
        "低意向"
    )

    # 分析关注点
    concern_keywords = {
        "价格敏感": ["价格", "便宜", "优惠", "折扣", "预算"],
        "品质导向": ["品牌", "质量", "环保", "进口", "高端"],
        "效率优先": ["工期", "多久", "什么时候", "快"],
        "服务关注": ["售后", "保修", "服务", "安装"],
    }

    concerns = []
    for concern_type, keywords in concern_keywords.items():
        if any(kw in " ".join(history) for kw in keywords):
            concerns.append(concern_type)

    intent["main_concerns"] = concerns if concerns else ["综合考虑"]

    # 3. 推荐沟通策略
    approach = result["recommended_approach"]

    if intent["level"] == "高意向":
        approach["strategy"] = "促成交易"
        approach["urgency"] = "高"
        approach["focus"] = "解决最后顾虑，推动成交"
    elif intent["level"] == "中等意向":
        approach["strategy"] = "深度沟通"
        approach["urgency"] = "中"
        approach["focus"] = "了解需求，建立信任"
    else:
        approach["strategy"] = "培养兴趣"
        approach["urgency"] = "低"
        approach["focus"] = "提供价值信息，保持联系"

    # 4. 话术建议
    talking_points = result["talking_points"]

    # 根据预算级别
    budget_level = profile.get("budget_level", "")
    if budget_level == "经济型":
        talking_points.append("强调性价比和实用性，推荐经济实惠的方案")
    elif budget_level == "高端型":
        talking_points.append("强调品质和独特性，推荐高端定制方案")

    # 根据关注点
    if "价格敏感" in concerns:
        talking_points.append("主动说明价格构成，强调透明报价，提供分期方案")
    if "品质导向" in concerns:
        talking_points.append("展示品牌资质和案例，强调材料环保认证")
    if "效率优先" in concerns:
        talking_points.append("明确工期承诺，说明进度管控措施")
    if "服务关注" in concerns:
        talking_points.append("详细介绍售后服务体系和保修政策")

    # 根据装修阶段
    stage = profile.get("stage", "")
    if "设计" in stage:
        talking_points.append("可以提供免费量房和设计方案，降低决策门槛")
    elif "施工" in stage:
        talking_points.append("强调施工管理能力和工艺标准")
    elif "选材" in stage:
        talking_points.append("提供材料对比和选购建议，展示专业性")

    # 5. 风险提示
    warnings = result["warnings"]

    if intent["level"] == "低意向" and high_signals == 0:
        warnings.append("客户意向较低，避免过度推销，以提供价值为主")

    if "价格敏感" in concerns and budget_level == "经济型":
        warnings.append("客户预算有限且价格敏感，注意不要推荐超预算方案")

    return result


def _conversion_rate_analyzer(visitors: int, inquiries: int,
                               orders: int) -> Dict:
    """转化率分析器（B端）"""
    # 计算各环节转化率
    visit_to_inquiry = (inquiries / visitors * 100) if visitors > 0 else 0
    inquiry_to_order = (orders / inquiries * 100) if inquiries > 0 else 0
    overall = (orders / visitors * 100) if visitors > 0 else 0

    # 行业参考值
    BENCHMARKS = {
        "visit_to_inquiry": 5.0,   # 访客到咨询 5%
        "inquiry_to_order": 20.0,  # 咨询到成交 20%
        "overall": 1.0,            # 整体转化 1%
    }

    # 评估
    analysis = {}
    if visit_to_inquiry < BENCHMARKS["visit_to_inquiry"]:
        analysis["visit_to_inquiry"] = {
            "status": "低于行业平均",
            "suggestion": "优化商品详情页，增加吸引力；检查价格竞争力"
        }
    else:
        analysis["visit_to_inquiry"] = {
            "status": "高于行业平均",
            "suggestion": "保持当前策略，可尝试扩大流量"
        }

    if inquiry_to_order < BENCHMARKS["inquiry_to_order"]:
        analysis["inquiry_to_order"] = {
            "status": "低于行业平均",
            "suggestion": "提升客服话术，加快响应速度；优化报价策略"
        }
    else:
        analysis["inquiry_to_order"] = {
            "status": "高于行业平均",
            "suggestion": "转化能力强，可增加获客投入"
        }

    return {
        "data": {
            "visitors": visitors,
            "inquiries": inquiries,
            "orders": orders,
        },
        "conversion_rates": {
            "visit_to_inquiry": round(visit_to_inquiry, 2),
            "inquiry_to_order": round(inquiry_to_order, 2),
            "overall": round(overall, 2),
        },
        "benchmarks": BENCHMARKS,
        "analysis": analysis,
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

    # 预算规划器
    registry.register(ToolDefinition(
        name="budget_planner",
        description="装修预算规划，根据总预算和面积给出各项分配建议",
        category=ToolCategory.CALCULATION,
        parameters=[
            ToolParameter("total_budget", float, "总预算（元）", required=True),
            ToolParameter("house_area", float, "房屋面积（平米）", required=True),
            ToolParameter("style", str, "装修风格", required=False, default="现代简约"),
        ],
        handler=_budget_planner,
        tags=["预算", "规划", "C端"],
    ))

    # 材料用量计算器
    registry.register(ToolDefinition(
        name="material_calculator",
        description="计算装修材料用量，包括瓷砖、地板、乳胶漆等",
        category=ToolCategory.CALCULATION,
        parameters=[
            ToolParameter("material_type", str, "材料类型",
                         required=True, enum_values=["瓷砖", "地板", "乳胶漆", "墙纸", "水泥", "沙子", "电线", "水管"]),
            ToolParameter("area", float, "施工面积（平米）", required=True),
            ToolParameter("loss_rate", float, "损耗率", required=False, default=0.05),
        ],
        handler=_material_calculator,
        tags=["材料", "计算", "C端"],
    ))

    # 商家评分计算器
    registry.register(ToolDefinition(
        name="merchant_score_calculator",
        description="计算商家综合评分，评估店铺运营状况",
        category=ToolCategory.CALCULATION,
        parameters=[
            ToolParameter("monthly_orders", int, "月订单量", required=True),
            ToolParameter("good_rate", float, "好评率（0-1）", required=True),
            ToolParameter("response_time", float, "平均响应时间（分钟）", required=True),
            ToolParameter("years", int, "经营年限", required=False, default=1),
        ],
        handler=_merchant_score_calculator,
        tags=["评分", "商家", "B端"],
    ))

    # 转化率分析器
    registry.register(ToolDefinition(
        name="conversion_rate_analyzer",
        description="分析店铺转化率，找出优化方向",
        category=ToolCategory.DATA,
        parameters=[
            ToolParameter("visitors", int, "访客数", required=True),
            ToolParameter("inquiries", int, "咨询数", required=True),
            ToolParameter("orders", int, "成交数", required=True),
        ],
        handler=_conversion_rate_analyzer,
        tags=["转化率", "分析", "B端"],
    ))

    # === 新增实用工具 ===

    # 材料对比分析器（C端）
    registry.register(ToolDefinition(
        name="material_comparator",
        description="对比不同装修材料的特性，帮助用户做出选择。支持瓷砖、木地板、大理石、乳胶漆、壁纸、硅藻泥等材料的对比",
        category=ToolCategory.DATA,
        parameters=[
            ToolParameter("materials", str, "要对比的材料，用逗号分隔，如'瓷砖,木地板'", required=True),
            ToolParameter("dimensions", str, "对比维度，用逗号分隔，如'价格,耐用性,环保性'", required=False),
        ],
        handler=_material_comparator,
        tags=["材料", "对比", "C端", "选购"],
    ))

    # 报价审核工具（C端）
    registry.register(ToolDefinition(
        name="quote_validator",
        description="审核装修报价单，识别不合理的报价项目，提供市场参考价格",
        category=ToolCategory.DATA,
        parameters=[
            ToolParameter("items", str, "报价项目，格式为'项目名:金额'用分号分隔，如'水电改造:15000;瓷砖铺贴:12000'", required=True),
            ToolParameter("total_amount", float, "报价总金额", required=False),
            ToolParameter("house_area", float, "房屋面积（平米）", required=False),
        ],
        handler=_quote_validator,
        tags=["报价", "审核", "C端", "预算"],
    ))

    # 客户意向分析器（B端）
    registry.register(ToolDefinition(
        name="customer_analyzer",
        description="分析客户的购买意向和偏好，提供个性化话术建议，帮助商家提高转化率",
        category=ToolCategory.DATA,
        parameters=[
            ToolParameter("customer_info", str, "客户信息，格式为'key:value'用分号分隔，如'预算:20万;面积:100平;风格:现代简约'", required=True),
            ToolParameter("interaction_history", str, "交互历史关键词，用分号分隔，如'询问价格;对比品牌;关注环保'", required=False),
        ],
        handler=_customer_analyzer,
        tags=["客户", "分析", "B端", "转化"],
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
