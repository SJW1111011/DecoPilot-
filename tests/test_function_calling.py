"""
Function Calling 模块单元测试
测试 backend/core/function_calling.py 的核心功能
"""
import pytest
import os
import sys

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.core.function_calling import (
    ParameterExtractor, FunctionCall, FunctionCallingResult,
    FunctionCallingEngine, get_function_calling_engine
)


class TestParameterExtractor:
    """测试 ParameterExtractor 类"""

    def test_extract_amount_yuan(self):
        """测试提取元为单位的金额"""
        text = "我买了一套沙发花了5000元"
        amount = ParameterExtractor.extract_amount(text)
        assert amount == 5000.0

    def test_extract_amount_wan(self):
        """测试提取万为单位的金额"""
        text = "装修预算大概10万元"
        amount = ParameterExtractor.extract_amount(text)
        assert amount == 100000.0

    def test_extract_amount_with_context(self):
        """测试带上下文的金额提取"""
        text = "投入了5万，收入了15万"
        investment = ParameterExtractor.extract_amount(text, "投入")
        assert investment == 50000.0

    def test_extract_multiple_amounts(self):
        """测试提取多个金额"""
        text = "投入5万，收入15万，利润10万"
        amounts = ParameterExtractor.extract_multiple_amounts(text)
        assert len(amounts) >= 2
        assert 50000.0 in amounts
        assert 150000.0 in amounts

    def test_extract_area(self):
        """测试提取面积"""
        text = "我家房子120平米"
        area = ParameterExtractor.extract_area(text)
        assert area == 120.0

    def test_extract_area_sqm_symbol(self):
        """测试提取面积（㎡符号）"""
        text = "客厅面积30㎡"
        area = ParameterExtractor.extract_area(text)
        assert area == 30.0

    def test_extract_category_furniture(self):
        """测试提取家具品类"""
        text = "我想买一套沙发"
        category = ParameterExtractor.extract_category(text)
        assert category == "家具"

    def test_extract_category_building_material(self):
        """测试提取建材品类"""
        text = "瓷砖价格怎么样"
        category = ParameterExtractor.extract_category(text)
        assert category == "建材"

    def test_extract_specific_item(self):
        """测试提取具体商品"""
        text = "这个沙发5000元贵不贵"
        item = ParameterExtractor.extract_specific_item(text)
        assert item == "沙发"

    def test_extract_style(self):
        """测试提取装修风格"""
        text = "我喜欢北欧风格的装修"
        style = ParameterExtractor.extract_style(text)
        assert style == "北欧"

    def test_extract_style_default(self):
        """测试默认装修风格"""
        text = "我想装修房子"
        style = ParameterExtractor.extract_style(text)
        assert style == "现代简约"

    def test_extract_period_days(self):
        """测试提取周期天数"""
        text = "最近30天的数据"
        days = ParameterExtractor.extract_period_days(text)
        assert days == 30

    def test_extract_period_months(self):
        """测试提取周期月数"""
        text = "最近3个月的销售情况"
        days = ParameterExtractor.extract_period_days(text)
        assert days == 90


class TestFunctionCall:
    """测试 FunctionCall 类"""

    def test_create_function_call(self):
        """测试创建函数调用"""
        call = FunctionCall(
            name="subsidy_calculator",
            arguments={"amount": 10000, "category": "家具"}
        )
        assert call.name == "subsidy_calculator"
        assert call.arguments["amount"] == 10000
        assert call.result is None
        assert call.error is None

    def test_function_call_with_result(self):
        """测试带结果的函数调用"""
        call = FunctionCall(
            name="subsidy_calculator",
            arguments={"amount": 10000, "category": "家具"},
            result={"final_amount": 500}
        )
        assert call.result["final_amount"] == 500

    def test_function_call_with_error(self):
        """测试带错误的函数调用"""
        call = FunctionCall(
            name="subsidy_calculator",
            arguments={},
            error="缺少必需参数"
        )
        assert call.error == "缺少必需参数"


class TestFunctionCallingResult:
    """测试 FunctionCallingResult 类"""

    def test_create_result(self):
        """测试创建结果"""
        result = FunctionCallingResult()
        assert result.calls == []
        assert result.final_response == ""
        assert result.thinking == []

    def test_result_with_calls(self):
        """测试带调用的结果"""
        result = FunctionCallingResult(
            calls=[
                FunctionCall(
                    name="subsidy_calculator",
                    arguments={"amount": 10000, "category": "家具"},
                    result={"final_amount": 500}
                )
            ],
            thinking=["检测到补贴计算意图"]
        )
        assert len(result.calls) == 1
        assert result.calls[0].name == "subsidy_calculator"
        assert len(result.thinking) == 1


class TestFunctionCallingEngine:
    """测试 FunctionCallingEngine 类"""

    @pytest.fixture
    def engine(self):
        """创建测试用的引擎"""
        return FunctionCallingEngine(llm=None)

    def test_get_tools_description(self, engine):
        """测试获取工具描述"""
        description = engine.get_tools_description()
        assert "subsidy_calculator" in description
        assert "roi_calculator" in description

    def test_get_tools_for_llm(self, engine):
        """测试获取 LLM 格式的工具"""
        tools = engine.get_tools_for_llm()
        assert isinstance(tools, list)
        assert len(tools) > 0
        # 检查工具格式
        tool = tools[0]
        assert "name" in tool
        assert "description" in tool
        assert "parameters" in tool

    def test_detect_subsidy_intent(self, engine):
        """测试检测补贴计算意图"""
        message = "我买了1万元的家具，能补贴多少钱？"
        detected = engine._detect_tool_intent(message)
        assert len(detected) > 0
        assert detected[0]["name"] == "subsidy_calculator"
        assert detected[0]["arguments"]["amount"] == 10000.0
        assert detected[0]["arguments"]["category"] == "家具"

    def test_detect_roi_intent(self, engine):
        """测试检测 ROI 计算意图"""
        message = "我投入了5万，收入了15万，ROI是多少？"
        detected = engine._detect_tool_intent(message)
        assert len(detected) > 0
        assert detected[0]["name"] == "roi_calculator"
        assert detected[0]["arguments"]["investment"] == 50000.0
        assert detected[0]["arguments"]["revenue"] == 150000.0

    def test_detect_price_eval_intent(self, engine):
        """测试检测价格评估意图"""
        message = "这个沙发8000元贵不贵？"
        detected = engine._detect_tool_intent(message)
        assert len(detected) > 0
        assert detected[0]["name"] == "price_evaluator"
        assert detected[0]["arguments"]["category"] == "沙发"
        assert detected[0]["arguments"]["price"] == 8000.0

    def test_detect_timeline_intent(self, engine):
        """测试检测工期估算意图"""
        message = "100平米的房子装修需要多久？"
        detected = engine._detect_tool_intent(message)
        assert len(detected) > 0
        assert detected[0]["name"] == "decoration_timeline"
        assert detected[0]["arguments"]["house_area"] == 100.0

    def test_detect_budget_intent(self, engine):
        """测试检测预算规划意图"""
        message = "我有20万预算，100平米的房子，预算怎么分配？"
        detected = engine._detect_tool_intent(message)
        assert len(detected) > 0
        assert detected[0]["name"] == "budget_planner"
        assert detected[0]["arguments"]["total_budget"] == 200000.0
        assert detected[0]["arguments"]["house_area"] == 100.0

    def test_detect_material_intent(self, engine):
        """测试检测材料计算意图"""
        message = "50平米的客厅需要多少瓷砖？"
        detected = engine._detect_tool_intent(message)
        assert len(detected) > 0
        assert detected[0]["name"] == "material_calculator"
        assert detected[0]["arguments"]["material_type"] == "瓷砖"
        assert detected[0]["arguments"]["area"] == 50.0

    def test_detect_no_intent(self, engine):
        """测试无工具调用意图"""
        message = "你好，请问装修有什么注意事项？"
        detected = engine._detect_tool_intent(message)
        assert len(detected) == 0

    def test_process_with_tools_sync(self, engine):
        """测试同步工具处理"""
        message = "我买了2万元的建材，能补贴多少？"
        result = engine.process_with_tools_sync(message)
        assert isinstance(result, FunctionCallingResult)
        assert len(result.calls) > 0
        assert result.calls[0].name == "subsidy_calculator"
        assert result.calls[0].result is not None

    def test_process_with_allowed_tools(self, engine):
        """测试限制允许的工具"""
        message = "我买了2万元的建材，能补贴多少？"
        result = engine.process_with_tools_sync(
            message,
            allowed_tools=["roi_calculator"]  # 不包含 subsidy_calculator
        )
        # 应该跳过 subsidy_calculator
        assert all(call.name != "subsidy_calculator" for call in result.calls)


class TestFunctionCallingIntegration:
    """集成测试"""

    def test_full_workflow(self):
        """测试完整工作流程"""
        engine = get_function_calling_engine()

        # 测试补贴计算
        result = engine.process_with_tools_sync(
            "我买了3万元的家电，能补贴多少钱？"
        )
        assert len(result.calls) > 0
        subsidy_call = result.calls[0]
        assert subsidy_call.name == "subsidy_calculator"
        assert subsidy_call.result is not None
        assert "final_amount" in subsidy_call.result

    def test_multiple_tools_detection(self):
        """测试多工具检测"""
        engine = get_function_calling_engine()

        # 这个消息可能触发多个工具
        message = "我投入5万做营销，收入20万，ROI怎么样？另外100平的房子装修要多久？"
        detected = engine._detect_tool_intent(message)

        # 应该检测到 ROI 计算和工期估算
        tool_names = [d["name"] for d in detected]
        assert "roi_calculator" in tool_names
        assert "decoration_timeline" in tool_names


@pytest.mark.asyncio
class TestFunctionCallingAsync:
    """异步测试"""

    async def test_process_with_tools_async(self):
        """测试异步工具处理"""
        engine = get_function_calling_engine()
        message = "我买了1万元的软装，能补贴多少？"
        result = await engine.process_with_tools(message)
        assert isinstance(result, FunctionCallingResult)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
