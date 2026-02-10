"""
阶段感知专家系统单元测试
测试 backend/core/stage_reasoning.py 的核心功能
"""
import pytest
import os
import sys

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.core.stage_reasoning import (
    CEndStage, BEndStage,
    ExpertRole, StageContext, StageTransition,
    StageUnderstanding, StageTransitionDetector, ExpertRoleManager,
    StageAwareReasoning, get_stage_reasoning,
    C_END_EXPERT_PROMPTS, B_END_EXPERT_PROMPTS,
    C_END_STAGE_KEYWORDS, B_END_STAGE_KEYWORDS,
    C_END_STAGE_TRANSITIONS, B_END_STAGE_TRANSITIONS,
)


class TestCEndStage:
    """测试 C端阶段枚举"""

    def test_stage_values(self):
        """测试阶段值"""
        assert CEndStage.PREPARATION.value == "准备"
        assert CEndStage.DESIGN.value == "设计"
        assert CEndStage.CONSTRUCTION.value == "施工"
        assert CEndStage.SOFT_DECORATION.value == "软装"
        assert CEndStage.MOVE_IN.value == "入住"

    def test_stage_count(self):
        """测试阶段数量"""
        assert len(CEndStage) == 5


class TestBEndStage:
    """测试 B端阶段枚举"""

    def test_stage_values(self):
        """测试阶段值"""
        assert BEndStage.ONBOARDING.value == "入驻"
        assert BEndStage.ACQUISITION.value == "获客"
        assert BEndStage.ANALYTICS.value == "经营分析"
        assert BEndStage.SETTLEMENT.value == "核销结算"

    def test_stage_count(self):
        """测试阶段数量"""
        assert len(BEndStage) == 4


class TestExpertRole:
    """测试 ExpertRole 数据类"""

    def test_create_expert_role(self):
        """测试创建专家角色"""
        role = ExpertRole(
            name="装修规划师",
            stage="准备",
            core_value="帮用户建立正确认知",
            professional_perspective="从全局视角规划",
            system_prompt="你是装修规划师..."
        )
        assert role.name == "装修规划师"
        assert role.stage == "准备"
        assert role.core_value == "帮用户建立正确认知"


class TestStageContext:
    """测试 StageContext 数据类"""

    def test_create_stage_context(self):
        """测试创建阶段上下文"""
        context = StageContext(
            stage="设计",
            stage_confidence=0.85,
            user_intent="选择设计方案",
            surface_question="这个方案好不好",
            deep_need="做出明智的设计决策",
            potential_needs=["报价审核", "合同注意事项"],
            emotional_state="困惑",
            focus_points=["选择", "质量"],
        )
        assert context.stage == "设计"
        assert context.stage_confidence == 0.85
        assert context.emotional_state == "困惑"
        assert len(context.potential_needs) == 2
        assert context.stage_changed is False

    def test_stage_context_with_transition(self):
        """测试带阶段转换的上下文"""
        context = StageContext(
            stage="施工",
            stage_confidence=0.9,
            user_intent="检查施工质量",
            surface_question="瓷砖空鼓怎么办",
            deep_need="确保施工质量",
            potential_needs=[],
            emotional_state="焦虑",
            focus_points=["质量"],
            stage_changed=True,
            transition_trigger="用户提到开工了"
        )
        assert context.stage_changed is True
        assert context.transition_trigger == "用户提到开工了"


class TestStageTransition:
    """测试 StageTransition 数据类"""

    def test_create_stage_transition(self):
        """测试创建阶段转换"""
        transition = StageTransition(
            from_stage="设计",
            to_stage="施工",
            confidence=0.85,
            trigger="用户说设计定了，准备开工",
            transition_guidance="设计定稿后，施工阶段需要重点关注..."
        )
        assert transition.from_stage == "设计"
        assert transition.to_stage == "施工"
        assert transition.confidence == 0.85


class TestStageUnderstanding:
    """测试 StageUnderstanding 类"""

    @pytest.fixture
    def understanding(self):
        """创建测试用的阶段理解器"""
        return StageUnderstanding()

    # === C端阶段理解测试 ===

    def test_c_end_preparation_stage_explicit(self, understanding):
        """测试C端准备阶段 - 显式关键词"""
        stage, confidence = understanding._keyword_stage_detection(
            "我准备装修，不知道从哪开始", "c_end"
        )
        assert stage == "准备"
        assert confidence > 0.3

    def test_c_end_preparation_stage_budget(self, understanding):
        """测试C端准备阶段 - 预算问题"""
        stage, confidence = understanding._keyword_stage_detection(
            "我家120平，预算20万，不知道从哪开始", "c_end"
        )
        assert stage == "准备"

    def test_c_end_design_stage(self, understanding):
        """测试C端设计阶段"""
        stage, confidence = understanding._keyword_stage_detection(
            "设计师给了两个方案，不知道选哪个", "c_end"
        )
        assert stage == "设计"

    def test_c_end_construction_stage(self, understanding):
        """测试C端施工阶段"""
        stage, confidence = understanding._keyword_stage_detection(
            "瓷砖贴完发现有空鼓，工人说没问题", "c_end"
        )
        assert stage == "施工"

    def test_c_end_soft_decoration_stage(self, understanding):
        """测试C端软装阶段"""
        stage, confidence = understanding._keyword_stage_detection(
            "客厅沙发选什么颜色好", "c_end"
        )
        assert stage == "软装"

    def test_c_end_move_in_stage(self, understanding):
        """测试C端入住阶段"""
        stage, confidence = understanding._keyword_stage_detection(
            "装修完多久可以入住", "c_end"
        )
        assert stage == "入住"

    # === B端阶段理解测试 ===

    def test_b_end_onboarding_stage(self, understanding):
        """测试B端入驻阶段"""
        stage, confidence = understanding._keyword_stage_detection(
            "我是做全屋定制的，想了解入驻条件", "b_end"
        )
        assert stage == "入驻"

    def test_b_end_acquisition_stage(self, understanding):
        """测试B端获客阶段"""
        stage, confidence = understanding._keyword_stage_detection(
            "最近转化率下降了，怎么办", "b_end"
        )
        assert stage == "获客"

    def test_b_end_analytics_stage(self, understanding):
        """测试B端经营分析阶段"""
        stage, confidence = understanding._keyword_stage_detection(
            "我的ROI是多少，怎么提升", "b_end"
        )
        assert stage == "经营分析"

    def test_b_end_settlement_stage(self, understanding):
        """测试B端核销结算阶段"""
        stage, confidence = understanding._keyword_stage_detection(
            "这个月的结算什么时候到账", "b_end"
        )
        assert stage == "核销结算"

    # === 情绪检测测试 ===

    def test_detect_anxiety(self, understanding):
        """测试焦虑情绪检测"""
        state = understanding._detect_emotional_state("急死了，工人不靠谱怎么办")
        assert state == "焦虑"

    def test_detect_confusion(self, understanding):
        """测试困惑情绪检测"""
        state = understanding._detect_emotional_state("不知道怎么选，好迷茫")
        assert state == "困惑"

    def test_detect_anger(self, understanding):
        """测试不满情绪检测"""
        state = understanding._detect_emotional_state("被坑了，质量太差了")
        assert state == "不满"

    def test_detect_positive(self, understanding):
        """测试积极情绪检测"""
        state = understanding._detect_emotional_state("效果不错，很期待入住")
        assert state == "积极"

    def test_detect_calm(self, understanding):
        """测试平静情绪检测"""
        state = understanding._detect_emotional_state("请问瓷砖怎么选")
        assert state == "平静"

    # === 关注重点提取测试 ===

    def test_extract_budget_focus(self, understanding):
        """测试预算关注点提取"""
        focus = understanding._extract_focus_points("装修要花多少钱", "准备")
        assert "预算" in focus

    def test_extract_quality_focus(self, understanding):
        """测试质量关注点提取"""
        focus = understanding._extract_focus_points("这个质量好不好", "施工")
        assert "质量" in focus

    def test_extract_time_focus(self, understanding):
        """测试时间关注点提取"""
        focus = understanding._extract_focus_points("装修要多久", "准备")
        assert "时间" in focus


class TestStageTransitionDetector:
    """测试 StageTransitionDetector 类"""

    @pytest.fixture
    def detector(self):
        """创建测试用的阶段转换检测器"""
        return StageTransitionDetector()

    def test_detect_c_end_transition(self, detector):
        """测试C端阶段转换检测"""
        context = StageContext(
            stage="施工",
            stage_confidence=0.85,
            user_intent="开始施工",
            surface_question="开工了有什么要注意的",
            deep_need="确保施工质量",
            potential_needs=[],
            emotional_state="期待",
            focus_points=["流程"],
        )
        transition = detector.detect_transition("设计", context, "c_end")
        assert transition is not None
        assert transition.from_stage == "设计"
        assert transition.to_stage == "施工"
        assert "施工阶段" in transition.transition_guidance

    def test_detect_b_end_transition(self, detector):
        """测试B端阶段转换检测"""
        context = StageContext(
            stage="获客",
            stage_confidence=0.8,
            user_intent="获取客户",
            surface_question="怎么获客",
            deep_need="提升转化",
            potential_needs=[],
            emotional_state="平静",
            focus_points=[],
        )
        transition = detector.detect_transition("入驻", context, "b_end")
        assert transition is not None
        assert transition.from_stage == "入驻"
        assert transition.to_stage == "获客"

    def test_no_transition_same_stage(self, detector):
        """测试同阶段无转换"""
        context = StageContext(
            stage="设计",
            stage_confidence=0.9,
            user_intent="设计问题",
            surface_question="方案怎么样",
            deep_need="评估方案",
            potential_needs=[],
            emotional_state="平静",
            focus_points=[],
        )
        transition = detector.detect_transition("设计", context, "c_end")
        assert transition is None

    def test_no_transition_low_confidence(self, detector):
        """测试低置信度不触发转换"""
        context = StageContext(
            stage="施工",
            stage_confidence=0.4,  # 低置信度
            user_intent="可能是施工",
            surface_question="问题",
            deep_need="需求",
            potential_needs=[],
            emotional_state="平静",
            focus_points=[],
        )
        transition = detector.detect_transition("设计", context, "c_end")
        assert transition is None


class TestExpertRoleManager:
    """测试 ExpertRoleManager 类"""

    @pytest.fixture
    def manager(self):
        """创建测试用的专家角色管理器"""
        return ExpertRoleManager()

    # === C端专家角色测试 ===

    def test_get_c_end_preparation_expert(self, manager):
        """测试获取C端准备阶段专家"""
        expert = manager.get_expert_role("准备", "c_end")
        assert expert is not None
        assert expert.name == "装修规划师"
        assert expert.stage == "准备"
        assert "规划" in expert.system_prompt

    def test_get_c_end_design_expert(self, manager):
        """测试获取C端设计阶段专家"""
        expert = manager.get_expert_role("设计", "c_end")
        assert expert is not None
        assert expert.name == "设计顾问"

    def test_get_c_end_construction_expert(self, manager):
        """测试获取C端施工阶段专家"""
        expert = manager.get_expert_role("施工", "c_end")
        assert expert is not None
        assert expert.name == "工程监理"

    def test_get_c_end_soft_decoration_expert(self, manager):
        """测试获取C端软装阶段专家"""
        expert = manager.get_expert_role("软装", "c_end")
        assert expert is not None
        assert expert.name == "软装搭配师"

    def test_get_c_end_move_in_expert(self, manager):
        """测试获取C端入住阶段专家"""
        expert = manager.get_expert_role("入住", "c_end")
        assert expert is not None
        assert expert.name == "居家顾问"

    # === B端专家角色测试 ===

    def test_get_b_end_onboarding_expert(self, manager):
        """测试获取B端入驻阶段专家"""
        expert = manager.get_expert_role("入驻", "b_end")
        assert expert is not None
        assert expert.name == "商业顾问"

    def test_get_b_end_acquisition_expert(self, manager):
        """测试获取B端获客阶段专家"""
        expert = manager.get_expert_role("获客", "b_end")
        assert expert is not None
        assert expert.name == "营销专家"

    def test_get_b_end_analytics_expert(self, manager):
        """测试获取B端经营分析阶段专家"""
        expert = manager.get_expert_role("经营分析", "b_end")
        assert expert is not None
        assert expert.name == "数据分析师"

    def test_get_b_end_settlement_expert(self, manager):
        """测试获取B端核销结算阶段专家"""
        expert = manager.get_expert_role("核销结算", "b_end")
        assert expert is not None
        assert expert.name == "财务顾问"

    # === 专家提示词测试 ===

    def test_get_expert_prompt(self, manager):
        """测试获取专家提示词"""
        prompt = manager.get_expert_prompt("准备", "c_end")
        assert "装修规划师" in prompt
        assert "专业背景" in prompt

    def test_get_all_c_end_experts(self, manager):
        """测试获取所有C端专家"""
        experts = manager.get_all_experts("c_end")
        assert len(experts) == 5
        assert "准备" in experts
        assert "设计" in experts
        assert "施工" in experts
        assert "软装" in experts
        assert "入住" in experts

    def test_get_all_b_end_experts(self, manager):
        """测试获取所有B端专家"""
        experts = manager.get_all_experts("b_end")
        assert len(experts) == 4
        assert "入驻" in experts
        assert "获客" in experts
        assert "经营分析" in experts
        assert "核销结算" in experts


class TestStageAwareReasoning:
    """测试 StageAwareReasoning 类"""

    @pytest.fixture
    def reasoning(self):
        """创建测试用的阶段感知推理引擎"""
        return StageAwareReasoning()

    @pytest.mark.asyncio
    async def test_analyze_c_end_preparation(self, reasoning):
        """测试C端准备阶段分析"""
        context, expert, transition = await reasoning.analyze_and_get_expert(
            query="我家120平，预算20万，不知道从哪开始",
            conversation_history=[],
            user_profile={},
            previous_stage=None,
            user_type="c_end"
        )
        assert context.stage == "准备"
        assert expert.name == "装修规划师"
        assert transition is None

    @pytest.mark.asyncio
    async def test_analyze_c_end_with_transition(self, reasoning):
        """测试C端阶段转换分析"""
        # 使用更明确的施工阶段关键词
        context, expert, transition = await reasoning.analyze_and_get_expert(
            query="开工了，工人在贴砖，有什么要注意的",
            conversation_history=[],
            user_profile={},
            previous_stage="设计",
            user_type="c_end"
        )
        assert context.stage == "施工"
        assert expert.name == "工程监理"
        # 转换可能发生也可能不发生，取决于置信度
        if transition:
            assert transition.from_stage == "设计"
            assert transition.to_stage == "施工"

    @pytest.mark.asyncio
    async def test_analyze_b_end_onboarding(self, reasoning):
        """测试B端入驻阶段分析"""
        context, expert, transition = await reasoning.analyze_and_get_expert(
            query="我是做全屋定制的，想了解入驻条件",
            conversation_history=[],
            user_profile={},
            previous_stage=None,
            user_type="b_end"
        )
        assert context.stage == "入驻"
        assert expert.name == "商业顾问"

    def test_get_expert_system_prompt_basic(self, reasoning):
        """测试获取基础专家系统提示词"""
        prompt = reasoning.get_expert_system_prompt("准备", "c_end")
        assert "装修规划师" in prompt

    def test_get_expert_system_prompt_with_context(self, reasoning):
        """测试获取带上下文的专家系统提示词"""
        context = StageContext(
            stage="施工",
            stage_confidence=0.9,
            user_intent="检查质量",
            surface_question="空鼓怎么办",
            deep_need="确保质量",
            potential_needs=["验收标准"],
            emotional_state="焦虑",
            focus_points=["质量"],
        )
        prompt = reasoning.get_expert_system_prompt("施工", "c_end", context)
        assert "工程监理" in prompt
        assert "焦虑" in prompt or "安抚" in prompt


class TestGlobalInstance:
    """测试全局实例"""

    def test_get_stage_reasoning_singleton(self):
        """测试单例模式"""
        reasoning1 = get_stage_reasoning()
        reasoning2 = get_stage_reasoning()
        assert reasoning1 is reasoning2


class TestExpertPrompts:
    """测试专家提示词配置"""

    def test_c_end_prompts_complete(self):
        """测试C端提示词完整性"""
        assert "准备" in C_END_EXPERT_PROMPTS
        assert "设计" in C_END_EXPERT_PROMPTS
        assert "施工" in C_END_EXPERT_PROMPTS
        assert "软装" in C_END_EXPERT_PROMPTS
        assert "入住" in C_END_EXPERT_PROMPTS

    def test_b_end_prompts_complete(self):
        """测试B端提示词完整性"""
        assert "入驻" in B_END_EXPERT_PROMPTS
        assert "获客" in B_END_EXPERT_PROMPTS
        assert "经营分析" in B_END_EXPERT_PROMPTS
        assert "核销结算" in B_END_EXPERT_PROMPTS

    def test_c_end_prompt_content(self):
        """测试C端提示词内容"""
        for stage, prompt in C_END_EXPERT_PROMPTS.items():
            assert "角色" in prompt
            assert "专业背景" in prompt
            assert "核心价值" in prompt

    def test_b_end_prompt_content(self):
        """测试B端提示词内容"""
        for stage, prompt in B_END_EXPERT_PROMPTS.items():
            assert "角色" in prompt
            assert "专业背景" in prompt
            assert "核心价值" in prompt


class TestStageKeywords:
    """测试阶段关键词配置"""

    def test_c_end_keywords_structure(self):
        """测试C端关键词结构"""
        for stage, keywords in C_END_STAGE_KEYWORDS.items():
            assert "explicit" in keywords
            assert "implicit" in keywords
            assert "questions" in keywords
            assert len(keywords["explicit"]) > 0

    def test_b_end_keywords_structure(self):
        """测试B端关键词结构"""
        for stage, keywords in B_END_STAGE_KEYWORDS.items():
            assert "explicit" in keywords
            assert "implicit" in keywords
            assert "questions" in keywords
            assert len(keywords["explicit"]) > 0


class TestStageTransitions:
    """测试阶段转换配置"""

    def test_c_end_transitions(self):
        """测试C端阶段转换引导"""
        assert ("准备", "设计") in C_END_STAGE_TRANSITIONS
        assert ("设计", "施工") in C_END_STAGE_TRANSITIONS
        assert ("施工", "软装") in C_END_STAGE_TRANSITIONS
        assert ("软装", "入住") in C_END_STAGE_TRANSITIONS

    def test_b_end_transitions(self):
        """测试B端阶段转换引导"""
        assert ("入驻", "获客") in B_END_STAGE_TRANSITIONS
        assert ("获客", "经营分析") in B_END_STAGE_TRANSITIONS
        assert ("经营分析", "核销结算") in B_END_STAGE_TRANSITIONS


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
