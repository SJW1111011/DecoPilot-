"""
推理引擎单元测试
测试 backend/core/reasoning.py 的核心功能
"""
import pytest
import os
import sys
import time

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.core.reasoning import (
    ReasoningType, TaskComplexity, ReasoningStep, ReasoningChain,
    Plan, ThoughtNode, ThoughtTree, ReActStep,
    TaskAnalyzer, ReasoningEngine, get_reasoning_engine,
    get_reasoning_prompt
)


class TestReasoningStep:
    """测试 ReasoningStep 类"""

    def test_create_step(self):
        """测试创建推理步骤"""
        step = ReasoningStep(
            step_id=1,
            step_type="think",
            content="分析问题",
            confidence=0.8
        )
        assert step.step_id == 1
        assert step.step_type == "think"
        assert step.content == "分析问题"
        assert step.confidence == 0.8


class TestReasoningChain:
    """测试 ReasoningChain 类"""

    def test_create_chain(self):
        """测试创建推理链"""
        chain = ReasoningChain(
            chain_id="test_chain",
            query="如何选择装修风格？",
            reasoning_type=ReasoningType.CHAIN_OF_THOUGHT
        )
        assert chain.chain_id == "test_chain"
        assert chain.query == "如何选择装修风格？"
        assert chain.reasoning_type == ReasoningType.CHAIN_OF_THOUGHT
        assert chain.steps == []

    def test_add_step(self):
        """测试添加步骤"""
        chain = ReasoningChain(
            chain_id="test_chain",
            query="测试问题",
            reasoning_type=ReasoningType.DIRECT
        )
        step = chain.add_step("think", "思考内容", confidence=0.7)
        assert len(chain.steps) == 1
        assert step.step_id == 1
        assert step.content == "思考内容"

    def test_get_thinking_log(self):
        """测试获取思考日志"""
        chain = ReasoningChain(
            chain_id="test_chain",
            query="测试问题",
            reasoning_type=ReasoningType.REACT
        )
        chain.add_step("think", "分析问题")
        chain.add_step("act", "调用工具")
        chain.add_step("observe", "观察结果")

        logs = chain.get_thinking_log()
        assert len(logs) == 3
        assert "思考" in logs[0]
        assert "执行" in logs[1]
        assert "观察" in logs[2]


class TestPlan:
    """测试 Plan 类"""

    def test_create_plan(self):
        """测试创建计划"""
        plan = Plan(plan_id="plan_1", goal="完成装修咨询")
        assert plan.plan_id == "plan_1"
        assert plan.goal == "完成装修咨询"
        assert plan.steps == []
        assert plan.status == "pending"

    def test_add_step(self):
        """测试添加计划步骤"""
        plan = Plan(plan_id="plan_1", goal="测试目标")
        plan.add_step("检索知识库", "获取相关信息", tools=["knowledge_search"])
        assert len(plan.steps) == 1
        assert plan.steps[0]["action"] == "检索知识库"
        assert plan.steps[0]["tools"] == ["knowledge_search"]

    def test_next_step(self):
        """测试获取下一步"""
        plan = Plan(plan_id="plan_1", goal="测试目标")
        plan.add_step("步骤1", "结果1")
        plan.add_step("步骤2", "结果2")

        next_step = plan.next_step()
        assert next_step["action"] == "步骤1"

    def test_complete_step(self):
        """测试完成步骤"""
        plan = Plan(plan_id="plan_1", goal="测试目标")
        plan.add_step("步骤1", "结果1")
        plan.add_step("步骤2", "结果2")

        plan.complete_step("实际结果", success=True)
        assert plan.current_step == 1
        assert plan.steps[0]["status"] == "completed"
        assert plan.steps[0]["actual_result"] == "实际结果"


class TestThoughtTree:
    """测试 ThoughtTree 类"""

    def test_create_tree(self):
        """测试创建思维树"""
        tree = ThoughtTree(
            tree_id="tree_1",
            query="复杂问题",
            root_id="node_0"
        )
        assert tree.tree_id == "tree_1"
        assert tree.query == "复杂问题"
        assert tree.nodes == {}

    def test_add_node(self):
        """测试添加节点"""
        tree = ThoughtTree(
            tree_id="tree_1",
            query="测试问题",
            root_id="node_0"
        )
        root = tree.add_node("根节点思路", score=0.5)
        assert root.node_id == "node_0"
        assert root.depth == 0

        child = tree.add_node("子节点思路", parent_id="node_0", score=0.7)
        assert child.depth == 1
        assert child.parent_id == "node_0"
        assert "node_1" in tree.nodes["node_0"].children

    def test_get_path_to_node(self):
        """测试获取路径"""
        tree = ThoughtTree(
            tree_id="tree_1",
            query="测试问题",
            root_id="node_0"
        )
        tree.add_node("根节点")
        tree.add_node("子节点1", parent_id="node_0")
        tree.add_node("子节点2", parent_id="node_1")

        path = tree.get_path_to_node("node_2")
        assert path == ["node_0", "node_1", "node_2"]

    def test_get_best_leaf(self):
        """测试获取最佳叶子节点"""
        tree = ThoughtTree(
            tree_id="tree_1",
            query="测试问题",
            root_id="node_0"
        )
        tree.add_node("根节点", score=0.5)
        tree.add_node("子节点1", parent_id="node_0", score=0.6)
        tree.add_node("子节点2", parent_id="node_0", score=0.9)

        best = tree.get_best_leaf()
        assert best.node_id == "node_2"
        assert best.score == 0.9


class TestTaskAnalyzer:
    """测试 TaskAnalyzer 类"""

    def test_analyze_simple_complexity(self):
        """测试简单问题复杂度分析"""
        complexity = TaskAnalyzer.analyze_complexity("什么是现代简约风格？")
        assert complexity == TaskComplexity.SIMPLE

    def test_analyze_simple_location_query(self):
        """测试简单位置查询"""
        complexity = TaskAnalyzer.analyze_complexity("店铺在哪里？")
        assert complexity == TaskComplexity.SIMPLE

    def test_analyze_simple_contact_query(self):
        """测试简单联系方式查询"""
        complexity = TaskAnalyzer.analyze_complexity("客服电话是多少？")
        assert complexity == TaskComplexity.SIMPLE

    def test_analyze_moderate_complexity(self):
        """测试中等问题复杂度分析"""
        complexity = TaskAnalyzer.analyze_complexity("如何选择适合我的装修风格？")
        assert complexity in [TaskComplexity.MODERATE, TaskComplexity.COMPLEX]

    def test_analyze_complex_with_budget(self):
        """测试涉及预算的复杂问题"""
        complexity = TaskAnalyzer.analyze_complexity(
            "我有100平米的房子，预算20万，想要现代简约风格，"
            "请帮我分析一下应该如何规划装修流程，选择什么材料，"
            "以及如何控制预算？"
        )
        assert complexity in [TaskComplexity.COMPLEX, TaskComplexity.EXPERT]

    def test_analyze_expert_with_multiple_questions(self):
        """测试包含多个问题的专家级查询"""
        complexity = TaskAnalyzer.analyze_complexity(
            "装修风格怎么选？预算怎么控制？材料怎么挑选？工期怎么安排？"
        )
        assert complexity in [TaskComplexity.COMPLEX, TaskComplexity.EXPERT]

    def test_analyze_complexity_with_conditions(self):
        """测试包含条件的问题"""
        complexity = TaskAnalyzer.analyze_complexity(
            "如果预算只有10万，应该怎么规划装修方案？"
        )
        # 包含条件、预算、规划等关键词，复杂度较高
        assert complexity in [TaskComplexity.MODERATE, TaskComplexity.COMPLEX, TaskComplexity.EXPERT]

    def test_analyze_complexity_with_comparison(self):
        """测试比较类问题"""
        complexity = TaskAnalyzer.analyze_complexity(
            "北欧风格和现代简约风格有什么区别？哪个更适合小户型？"
        )
        assert complexity in [TaskComplexity.MODERATE, TaskComplexity.COMPLEX]

    def test_get_complexity_details(self):
        """测试获取复杂度分析详情"""
        details = TaskAnalyzer.get_complexity_details("如何规划100平米房子的装修预算？")
        assert "scores" in details
        assert "matched_keywords" in details
        assert "total_score" in details
        assert "complexity" in details
        assert details["total_score"] > 0  # 应该有正分数

    def test_select_reasoning_type_direct(self):
        """测试选择直接回答模式"""
        reasoning_type = TaskAnalyzer.select_reasoning_type(
            "什么是北欧风格？",
            TaskComplexity.SIMPLE
        )
        assert reasoning_type == ReasoningType.DIRECT

    def test_select_reasoning_type_cot(self):
        """测试选择思维链模式"""
        reasoning_type = TaskAnalyzer.select_reasoning_type(
            "如何选择装修风格？",
            TaskComplexity.MODERATE
        )
        assert reasoning_type == ReasoningType.CHAIN_OF_THOUGHT

    def test_select_reasoning_type_react(self):
        """测试选择 ReAct 模式（工具调用）"""
        reasoning_type = TaskAnalyzer.select_reasoning_type(
            "买1万元家具能补贴多少？",
            TaskComplexity.SIMPLE
        )
        assert reasoning_type == ReasoningType.REACT

    def test_select_reasoning_type_react_roi(self):
        """测试 ROI 计算触发 ReAct 模式"""
        reasoning_type = TaskAnalyzer.select_reasoning_type(
            "我的投资回报率是多少？",
            TaskComplexity.MODERATE
        )
        assert reasoning_type == ReasoningType.REACT

    def test_detect_required_tools(self):
        """测试检测所需工具"""
        tools = TaskAnalyzer.detect_required_tools("买家具能补贴多少钱？")
        assert "subsidy_calculator" in tools

        tools = TaskAnalyzer.detect_required_tools("我的ROI是多少？")
        assert "roi_calculator" in tools

        tools = TaskAnalyzer.detect_required_tools("这个价格划算吗？")
        assert "price_evaluator" in tools

        tools = TaskAnalyzer.detect_required_tools("装修需要几个月？")
        assert "decoration_timeline" in tools

    def test_detect_multiple_tools(self):
        """测试检测多个工具"""
        tools = TaskAnalyzer.detect_required_tools(
            "买1万元家具能补贴多少？这个价格划算吗？"
        )
        assert "subsidy_calculator" in tools
        assert "price_evaluator" in tools

    def test_extract_sub_questions(self):
        """测试提取子问题"""
        sub_questions = TaskAnalyzer.extract_sub_questions(
            "装修风格怎么选？预算怎么控制？"
        )
        assert len(sub_questions) >= 2


class TestReasoningEngine:
    """测试 ReasoningEngine 类"""

    @pytest.fixture
    def engine(self):
        """创建测试用的推理引擎"""
        return ReasoningEngine()

    def test_create_chain(self, engine):
        """测试创建推理链"""
        chain = engine.create_chain("测试问题")
        assert chain.query == "测试问题"
        assert chain.chain_id is not None

    def test_think_step(self, engine):
        """测试添加思考步骤"""
        chain = engine.create_chain("测试问题")
        step = engine.think(chain, "分析问题", confidence=0.8)
        assert step.step_type == "think"
        assert step.content == "分析问题"
        assert step.confidence == 0.8

    def test_act_step(self, engine):
        """测试添加执行步骤"""
        chain = engine.create_chain("测试问题")
        step = engine.act(chain, "调用知识库", tool="knowledge_search")
        assert step.step_type == "act"
        assert step.metadata["tool"] == "knowledge_search"

    def test_observe_step(self, engine):
        """测试添加观察步骤"""
        chain = engine.create_chain("测试问题")
        step = engine.observe(chain, "找到3条相关信息")
        assert step.step_type == "observe"

    def test_reflect_step(self, engine):
        """测试添加反思步骤"""
        chain = engine.create_chain("测试问题")
        step = engine.reflect(chain, "答案是否完整？", confidence=0.7)
        assert step.step_type == "reflect"

    def test_finalize_chain(self, engine):
        """测试完成推理链"""
        chain = engine.create_chain("测试问题")
        engine.think(chain, "分析问题")
        engine.finalize(chain, "最终答案", confidence=0.9)

        assert chain.final_answer == "最终答案"
        assert chain.confidence == 0.9
        assert chain.end_time is not None

    def test_chain_of_thought(self, engine):
        """测试思维链推理"""
        chain = engine.chain_of_thought("如何选择装修风格？")
        assert chain.reasoning_type == ReasoningType.CHAIN_OF_THOUGHT
        assert len(chain.steps) > 0

    def test_multi_step_reasoning(self, engine):
        """测试多步推理"""
        chain = engine.multi_step_reasoning("复杂的装修规划问题")
        assert chain.reasoning_type == ReasoningType.MULTI_STEP
        assert len(chain.steps) > 0

    def test_tree_of_thought(self, engine):
        """测试思维树推理"""
        chain = engine.tree_of_thought("非常复杂的问题")
        assert chain.reasoning_type == ReasoningType.TREE_OF_THOUGHT
        assert len(chain.steps) > 0

    def test_react_reasoning(self, engine):
        """测试 ReAct 推理"""
        chain = engine.react_reasoning("计算补贴金额")
        assert chain.reasoning_type == ReasoningType.REACT
        assert len(chain.steps) > 0

    def test_create_thought_tree(self, engine):
        """测试创建思维树"""
        tree = engine.create_thought_tree("复杂问题", max_depth=2)
        assert tree.query == "复杂问题"
        assert tree.max_depth == 2
        assert tree.root_id in tree.nodes


class TestGetReasoningPrompt:
    """测试 get_reasoning_prompt 函数"""

    def test_cot_prompt(self):
        """测试思维链提示词"""
        prompt = get_reasoning_prompt(
            ReasoningType.CHAIN_OF_THOUGHT,
            "如何选择装修风格？",
            "参考信息..."
        )
        assert "思维链" in prompt
        assert "如何选择装修风格？" in prompt

    def test_multi_step_prompt(self):
        """测试多步推理提示词"""
        prompt = get_reasoning_prompt(
            ReasoningType.MULTI_STEP,
            "复杂问题",
            "参考信息...",
            sub_questions=["子问题1", "子问题2"]
        )
        assert "多步推理" in prompt
        assert "子问题1" in prompt

    def test_react_prompt(self):
        """测试 ReAct 提示词"""
        prompt = get_reasoning_prompt(
            ReasoningType.REACT,
            "计算补贴",
            "参考信息...",
            tools_description="补贴计算器"
        )
        assert "ReAct" in prompt
        assert "补贴计算器" in prompt

    def test_tot_prompt(self):
        """测试思维树提示词"""
        prompt = get_reasoning_prompt(
            ReasoningType.TREE_OF_THOUGHT,
            "复杂问题",
            "参考信息..."
        )
        assert "思维树" in prompt


class TestGetReasoningEngine:
    """测试全局推理引擎获取"""

    def test_singleton(self):
        """测试单例模式"""
        engine1 = get_reasoning_engine()
        engine2 = get_reasoning_engine()
        assert engine1 is engine2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
