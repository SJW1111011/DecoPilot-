"""
工具系统单元测试
测试 backend/core/tools.py 的核心功能
"""
import pytest
import os
import sys
import time

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.core.tools import (
    ToolCategory, ToolParameter, ToolResult, ToolDefinition,
    ToolRegistry, ToolChain, tool, get_tool_registry
)


class TestToolParameter:
    """测试 ToolParameter 类"""

    def test_create_parameter(self):
        """测试创建参数"""
        param = ToolParameter(
            name="amount",
            param_type=float,
            description="订单金额",
            required=True
        )
        assert param.name == "amount"
        assert param.param_type == float
        assert param.required is True

    def test_validate_required_missing(self):
        """测试必需参数缺失"""
        param = ToolParameter(
            name="amount",
            param_type=float,
            description="订单金额",
            required=True
        )
        valid, error = param.validate(None)
        assert valid is False
        assert "必需" in error

    def test_validate_optional_missing(self):
        """测试可选参数缺失"""
        param = ToolParameter(
            name="period",
            param_type=int,
            description="周期",
            required=False,
            default=30
        )
        valid, error = param.validate(None)
        assert valid is True

    def test_validate_type_correct(self):
        """测试类型正确"""
        param = ToolParameter(
            name="amount",
            param_type=float,
            description="金额",
            required=True
        )
        valid, error = param.validate(100.0)
        assert valid is True

    def test_validate_type_conversion(self):
        """测试类型转换"""
        param = ToolParameter(
            name="amount",
            param_type=float,
            description="金额",
            required=True
        )
        # 字符串可以转换为 float
        valid, error = param.validate("100")
        assert valid is True

    def test_validate_enum_values(self):
        """测试枚举值验证"""
        param = ToolParameter(
            name="category",
            param_type=str,
            description="品类",
            required=True,
            enum_values=["家具", "建材", "家电"]
        )
        valid, error = param.validate("家具")
        assert valid is True

        valid, error = param.validate("其他")
        assert valid is False
        assert "必须是以下值之一" in error


class TestToolResult:
    """测试 ToolResult 类"""

    def test_success_result(self):
        """测试成功结果"""
        result = ToolResult(
            success=True,
            data={"amount": 500},
            execution_time=0.1
        )
        assert result.success is True
        assert result.data["amount"] == 500
        assert result.error is None

    def test_error_result(self):
        """测试错误结果"""
        result = ToolResult(
            success=False,
            error="参数错误"
        )
        assert result.success is False
        assert result.error == "参数错误"

    def test_to_dict(self):
        """测试转换为字典"""
        result = ToolResult(
            success=True,
            data={"value": 100},
            execution_time=0.05
        )
        data = result.to_dict()
        assert data["success"] is True
        assert data["data"]["value"] == 100
        assert data["execution_time"] == 0.05


class TestToolDefinition:
    """测试 ToolDefinition 类"""

    def test_create_definition(self):
        """测试创建工具定义"""
        def handler(x: int) -> int:
            return x * 2

        tool_def = ToolDefinition(
            name="double",
            description="将数字翻倍",
            category=ToolCategory.CALCULATION,
            parameters=[
                ToolParameter("x", int, "输入数字", required=True)
            ],
            handler=handler
        )
        assert tool_def.name == "double"
        assert tool_def.category == ToolCategory.CALCULATION
        assert tool_def.enabled is True

    def test_get_schema(self):
        """测试获取 Schema"""
        tool_def = ToolDefinition(
            name="test_tool",
            description="测试工具",
            category=ToolCategory.UTILITY,
            parameters=[
                ToolParameter("param1", str, "参数1", required=True),
                ToolParameter("param2", int, "参数2", required=False, default=10)
            ],
            handler=lambda x, y: x
        )
        schema = tool_def.get_schema()
        assert schema["name"] == "test_tool"
        assert schema["description"] == "测试工具"
        assert "param1" in schema["parameters"]["properties"]
        assert "param1" in schema["parameters"]["required"]
        assert "param2" not in schema["parameters"]["required"]


class TestToolRegistry:
    """测试 ToolRegistry 类"""

    @pytest.fixture
    def registry(self):
        """创建测试用的注册中心"""
        return ToolRegistry()

    @pytest.fixture
    def sample_tool(self):
        """创建示例工具"""
        return ToolDefinition(
            name="sample_tool",
            description="示例工具",
            category=ToolCategory.UTILITY,
            parameters=[
                ToolParameter("value", int, "输入值", required=True)
            ],
            handler=lambda value: value * 2
        )

    def test_register_tool(self, registry, sample_tool):
        """测试注册工具"""
        result = registry.register(sample_tool)
        assert result is True
        assert "sample_tool" in registry.tools

    def test_register_duplicate(self, registry, sample_tool):
        """测试重复注册"""
        registry.register(sample_tool)
        result = registry.register(sample_tool)
        assert result is False

    def test_unregister_tool(self, registry, sample_tool):
        """测试注销工具"""
        registry.register(sample_tool)
        result = registry.unregister("sample_tool")
        assert result is True
        assert "sample_tool" not in registry.tools

    def test_get_tool(self, registry, sample_tool):
        """测试获取工具"""
        registry.register(sample_tool)
        tool = registry.get("sample_tool")
        assert tool is not None
        assert tool.name == "sample_tool"

    def test_get_nonexistent_tool(self, registry):
        """测试获取不存在的工具"""
        tool = registry.get("nonexistent")
        assert tool is None

    def test_list_tools(self, registry):
        """测试列出工具"""
        tool1 = ToolDefinition(
            name="tool1",
            description="工具1",
            category=ToolCategory.CALCULATION,
            parameters=[],
            handler=lambda: None
        )
        tool2 = ToolDefinition(
            name="tool2",
            description="工具2",
            category=ToolCategory.SEARCH,
            parameters=[],
            handler=lambda: None
        )
        registry.register(tool1)
        registry.register(tool2)

        all_tools = registry.list_tools()
        assert len(all_tools) == 2

        calc_tools = registry.list_tools(category=ToolCategory.CALCULATION)
        assert len(calc_tools) == 1
        assert calc_tools[0].name == "tool1"

    def test_call_tool_success(self, registry, sample_tool):
        """测试成功调用工具"""
        registry.register(sample_tool)
        result = registry.call("sample_tool", value=5)
        assert result.success is True
        assert result.data == 10

    def test_call_tool_not_found(self, registry):
        """测试调用不存在的工具"""
        result = registry.call("nonexistent")
        assert result.success is False
        assert "不存在" in result.error

    def test_call_tool_disabled(self, registry, sample_tool):
        """测试调用已禁用的工具"""
        sample_tool.enabled = False
        registry.register(sample_tool)
        result = registry.call("sample_tool", value=5)
        assert result.success is False
        assert "已禁用" in result.error

    def test_call_tool_missing_param(self, registry, sample_tool):
        """测试调用工具缺少参数"""
        registry.register(sample_tool)
        result = registry.call("sample_tool")  # 缺少 value 参数
        assert result.success is False
        assert "必需" in result.error

    def test_get_statistics(self, registry, sample_tool):
        """测试获取统计信息"""
        registry.register(sample_tool)
        registry.call("sample_tool", value=5)
        registry.call("sample_tool", value=10)

        stats = registry.get_statistics()
        assert "sample_tool" in stats
        assert stats["sample_tool"]["call_count"] == 2


class TestToolChain:
    """测试 ToolChain 类"""

    @pytest.fixture
    def registry_with_tools(self):
        """创建带工具的注册中心"""
        registry = ToolRegistry()
        registry.register(ToolDefinition(
            name="add",
            description="加法",
            category=ToolCategory.CALCULATION,
            parameters=[
                ToolParameter("a", int, "数字a", required=True),
                ToolParameter("b", int, "数字b", required=True)
            ],
            handler=lambda a, b: a + b
        ))
        registry.register(ToolDefinition(
            name="multiply",
            description="乘法",
            category=ToolCategory.CALCULATION,
            parameters=[
                ToolParameter("x", int, "数字x", required=True),
                ToolParameter("y", int, "数字y", required=True)
            ],
            handler=lambda x, y: x * y
        ))
        return registry

    def test_execute_chain(self, registry_with_tools):
        """测试执行工具链"""
        chain = ToolChain(registry_with_tools)
        chain.add_step("add", {"a": 2, "b": 3}, output_key="sum")
        chain.add_step("multiply", {"x": "$sum", "y": 2}, output_key="result")

        results = chain.execute()
        assert results["sum"] == 5
        assert results["result"] == 10

    def test_chain_with_condition(self, registry_with_tools):
        """测试带条件的工具链"""
        chain = ToolChain(registry_with_tools)
        chain.add_step("add", {"a": 2, "b": 3}, output_key="sum")
        chain.add_step(
            "multiply",
            {"x": "$sum", "y": 2},
            output_key="result",
            condition=lambda ctx: ctx.get("sum", 0) > 10  # 条件不满足
        )

        results = chain.execute()
        assert results["sum"] == 5
        assert results.get("result") is None  # 条件不满足，未执行


class TestBuiltinTools:
    """测试内置工具"""

    @pytest.fixture
    def registry(self):
        """获取全局注册中心（包含内置工具）"""
        return get_tool_registry()

    def test_subsidy_calculator(self, registry):
        """测试补贴计算器"""
        result = registry.call("subsidy_calculator", amount=10000, category="家具")
        assert result.success is True
        assert "final_amount" in result.data
        assert result.data["final_amount"] == 500  # 10000 * 5% = 500

    def test_subsidy_calculator_with_cap(self, registry):
        """测试补贴计算器上限"""
        result = registry.call("subsidy_calculator", amount=100000, category="家具")
        assert result.success is True
        # 100000 * 5% = 5000，但上限是 2000
        assert result.data["final_amount"] == 2000

    def test_roi_calculator(self, registry):
        """测试 ROI 计算器"""
        result = registry.call("roi_calculator", investment=5000, revenue=15000)
        assert result.success is True
        assert result.data["roi_percent"] == 200.0  # (15000-5000)/5000 * 100

    def test_roi_calculator_invalid_investment(self, registry):
        """测试 ROI 计算器无效投入"""
        result = registry.call("roi_calculator", investment=0, revenue=1000)
        assert result.success is True
        assert "error" in result.data

    def test_price_evaluator(self, registry):
        """测试价格评估器"""
        result = registry.call("price_evaluator", category="瓷砖", price=100, area=1)
        assert result.success is True
        assert "price_level" in result.data
        assert "suggestion" in result.data

    def test_decoration_timeline(self, registry):
        """测试装修工期估算"""
        result = registry.call("decoration_timeline", house_area=100)
        assert result.success is True
        assert "total_days" in result.data
        assert "timeline" in result.data


class TestToolDecorator:
    """测试工具装饰器"""

    def test_tool_decorator(self):
        """测试 @tool 装饰器"""
        @tool(
            name="test_decorated_tool",
            description="测试装饰器工具",
            category=ToolCategory.UTILITY
        )
        def my_tool(x: int, y: int = 10) -> int:
            return x + y

        # 检查工具是否被注册
        registry = get_tool_registry()
        tool_def = registry.get("test_decorated_tool")
        assert tool_def is not None
        assert tool_def.name == "test_decorated_tool"

        # 检查参数是否正确提取
        assert len(tool_def.parameters) == 2
        assert tool_def.parameters[0].name == "x"
        assert tool_def.parameters[0].required is True
        assert tool_def.parameters[1].name == "y"
        assert tool_def.parameters[1].required is False


class TestToolTimeout:
    """测试工具超时控制"""

    @pytest.fixture
    def registry_with_slow_tool(self):
        """创建带慢速工具的注册中心"""
        registry = ToolRegistry()

        def slow_handler(seconds: float) -> str:
            time.sleep(seconds)
            return f"完成，耗时 {seconds} 秒"

        registry.register(ToolDefinition(
            name="slow_tool",
            description="慢速工具",
            category=ToolCategory.UTILITY,
            parameters=[
                ToolParameter("seconds", float, "等待秒数", required=True)
            ],
            handler=slow_handler
        ))
        return registry

    def test_tool_completes_within_timeout(self, registry_with_slow_tool):
        """测试工具在超时时间内完成"""
        result = registry_with_slow_tool.call("slow_tool", timeout=5.0, seconds=0.1)
        assert result.success is True
        assert "完成" in result.data

    def test_tool_timeout(self, registry_with_slow_tool):
        """测试工具超时"""
        result = registry_with_slow_tool.call("slow_tool", timeout=0.5, seconds=2.0)
        assert result.success is False
        assert "超时" in result.error
        assert result.metadata.get("timeout") is True

    def test_default_timeout(self, registry_with_slow_tool):
        """测试默认超时时间（30秒）"""
        # 快速完成的任务应该成功
        result = registry_with_slow_tool.call("slow_tool", seconds=0.1)
        assert result.success is True

    def test_timeout_records_error_count(self, registry_with_slow_tool):
        """测试超时会记录错误计数"""
        tool = registry_with_slow_tool.get("slow_tool")
        initial_error_count = tool.error_count

        registry_with_slow_tool.call("slow_tool", timeout=0.1, seconds=1.0)

        assert tool.error_count == initial_error_count + 1


class TestToolAsyncTimeout:
    """测试异步工具超时控制"""

    @pytest.fixture
    def registry_with_slow_tool(self):
        """创建带慢速工具的注册中心"""
        registry = ToolRegistry()

        def slow_handler(seconds: float) -> str:
            time.sleep(seconds)
            return f"完成，耗时 {seconds} 秒"

        registry.register(ToolDefinition(
            name="slow_tool_async",
            description="慢速工具（异步测试）",
            category=ToolCategory.UTILITY,
            parameters=[
                ToolParameter("seconds", float, "等待秒数", required=True)
            ],
            handler=slow_handler
        ))
        return registry

    @pytest.mark.asyncio
    async def test_async_tool_completes_within_timeout(self, registry_with_slow_tool):
        """测试异步工具在超时时间内完成"""
        result = await registry_with_slow_tool.call_async("slow_tool_async", timeout=5.0, seconds=0.1)
        assert result.success is True
        assert "完成" in result.data

    @pytest.mark.asyncio
    async def test_async_tool_timeout(self, registry_with_slow_tool):
        """测试异步工具超时"""
        result = await registry_with_slow_tool.call_async("slow_tool_async", timeout=0.5, seconds=2.0)
        assert result.success is False
        assert "超时" in result.error
        assert result.metadata.get("timeout") is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
