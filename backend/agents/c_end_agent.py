"""
C端智能体 - 业主顾问
服务于业主用户，提供装修咨询、补贴政策、商家推荐等服务
整合记忆系统、推理引擎、工具系统等高级能力
"""
import os
import sys
from typing import List, Dict, Optional, AsyncGenerator

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from backend.agents.enhanced_agent import EnhancedAgent
from backend.agents.prompts.c_end_prompts import (
    C_END_SYSTEM_PROMPT,
    C_END_SUBSIDY_PROMPT,
    C_END_MERCHANT_RECOMMEND_PROMPT,
)
from backend.config.business_rules import (
    SUBSIDY_RULES,
    DEFAULT_SUBSIDY_RULE,
    DECORATION_STYLES,
    DECORATION_PROCESS,
)
from backend.core.output_formatter import OutputFormatter, OutputType
from backend.core.stage_reasoning import get_stage_reasoning, CEndStage


class CEndAgent(EnhancedAgent):
    """C端智能体 - 业主顾问（增强版）

    继承自 EnhancedAgent，具备以下能力：
    - 三层记忆系统（短期/长期/工作记忆）
    - 智能推理引擎（CoT/ToT/ReAct）
    - 工具调用系统
    - 多模态处理
    - 结构化输出
    - 阶段感知专家系统（装修规划师/设计顾问/工程监理/软装搭配师/居家顾问）
    """

    def __init__(self):
        super().__init__(user_type="c_end", agent_name="小洞")

    def _get_system_prompt(self) -> str:
        """获取C端系统提示词"""
        return C_END_SYSTEM_PROMPT

    # === 专家角色方法 ===

    def get_expert_role_for_stage(self, stage: str) -> dict:
        """
        获取指定阶段的专家角色信息

        Args:
            stage: 装修阶段（准备/设计/施工/软装/入住）

        Returns:
            专家角色信息
        """
        expert_role = self.stage_reasoning.expert_manager.get_expert_role(stage, "c_end")
        if expert_role:
            return {
                "name": expert_role.name,
                "stage": expert_role.stage,
                "core_value": expert_role.core_value,
                "professional_perspective": expert_role.professional_perspective,
            }
        return None

    def get_all_expert_roles(self) -> List[dict]:
        """
        获取所有C端专家角色

        Returns:
            专家角色列表
        """
        experts = self.stage_reasoning.expert_manager.get_all_experts("c_end")
        return [
            {
                "name": role.name,
                "stage": role.stage,
                "core_value": role.core_value,
                "professional_perspective": role.professional_perspective,
            }
            for role in experts.values()
        ]

    def get_stage_transition_guidance(self, from_stage: str, to_stage: str) -> str:
        """
        获取阶段转换引导

        Args:
            from_stage: 原阶段
            to_stage: 新阶段

        Returns:
            转换引导文本
        """
        from backend.core.stage_reasoning import C_END_STAGE_TRANSITIONS
        return C_END_STAGE_TRANSITIONS.get((from_stage, to_stage), f"您已进入{to_stage}阶段，有什么可以帮您的？")

    # === 增强版处理方法 ===

    async def process_with_subsidy(self, message: str, session_id: str,
                                    user_id: str = None) -> AsyncGenerator:
        """
        处理补贴相关查询，自动调用补贴计算工具

        Args:
            message: 用户消息
            session_id: 会话ID
            user_id: 用户ID

        Yields:
            输出事件
        """
        # 尝试提取金额和品类
        amount = self._extract_amount(message)
        category = self._extract_category(message)

        # 如果能提取到参数，先计算补贴
        if amount and category:
            subsidy_result = self.calculate_subsidy(amount, category)
            # 将补贴结果存入工作记忆
            self.set_working_memory(session_id, "last_subsidy_calc", subsidy_result)

        # 调用父类的处理方法
        async for event in self.process(message, session_id, user_id):
            yield event

    async def process_with_merchant_recommend(self, message: str, session_id: str,
                                               user_id: str = None,
                                               category: str = None,
                                               budget: float = None) -> AsyncGenerator:
        """
        处理商家推荐查询

        Args:
            message: 用户消息
            session_id: 会话ID
            user_id: 用户ID
            category: 商品品类
            budget: 预算

        Yields:
            输出事件
        """
        # 获取用户画像中的偏好
        profile = self.get_user_profile(user_id or session_id)
        preferred_styles = profile.preferred_styles

        # 存入工作记忆
        self.set_working_memory(session_id, "recommend_context", {
            "category": category,
            "budget": budget,
            "preferred_styles": preferred_styles,
        })

        # 调用父类的处理方法
        async for event in self.process(message, session_id, user_id):
            yield event

    # === 原有业务方法（保持兼容） ===

    def get_subsidy_prompt(self) -> str:
        """获取补贴咨询专用提示词"""
        return C_END_SUBSIDY_PROMPT

    def get_merchant_recommend_prompt(self) -> str:
        """获取商家推荐专用提示词"""
        return C_END_MERCHANT_RECOMMEND_PROMPT

    def calculate_subsidy(self, order_amount: float, category: str) -> dict:
        """
        计算补贴金额

        Args:
            order_amount: 订单金额
            category: 商品品类

        Returns:
            补贴计算结果
        """
        rule = SUBSIDY_RULES.get(category, DEFAULT_SUBSIDY_RULE)
        calculated = order_amount * rule["rate"]
        actual_subsidy = min(calculated, rule["max"])

        return {
            "order_amount": order_amount,
            "category": category,
            "subsidy_rate": rule["rate"],
            "calculated_subsidy": round(calculated, 2),
            "max_subsidy": rule["max"],
            "actual_subsidy": round(actual_subsidy, 2),
            "description": rule.get("description", ""),
            "note": "以上为预估金额，实际补贴以平台规则为准",
        }

    def get_decoration_styles(self) -> dict:
        """获取装修风格推荐"""
        return DECORATION_STYLES

    def get_decoration_process(self) -> list:
        """获取装修流程指南"""
        return DECORATION_PROCESS

    def recommend_style(self, preferences: dict) -> list[dict]:
        """
        根据用户偏好推荐装修风格

        Args:
            preferences: 用户偏好 {budget_level, age_group, house_size}

        Returns:
            推荐的风格列表
        """
        budget = preferences.get("budget_level", "中等")
        recommendations = []

        for style_name, style_info in DECORATION_STYLES.items():
            score = 0
            # 预算匹配
            if style_info["budget_level"] == budget:
                score += 3
            elif budget == "中等":
                score += 1

            # 适合人群匹配
            suitable = style_info.get("suitable_for", [])
            if preferences.get("age_group") in str(suitable):
                score += 2
            if preferences.get("house_size") in str(suitable):
                score += 2

            recommendations.append({
                "style": style_name,
                "score": score,
                "info": style_info,
            })

        # 按分数排序
        recommendations.sort(key=lambda x: x["score"], reverse=True)
        return recommendations[:3]

    def recommend_merchants(
        self,
        category: str,
        budget: float = None,
        style: str = None,
        limit: int = 5,
    ) -> list[dict]:
        """
        推荐商家

        Args:
            category: 商品品类
            budget: 预算范围
            style: 偏好风格
            limit: 返回数量

        Returns:
            推荐商家列表
        """
        # 从知识库检索商家信息
        query = f"{category}"
        if style:
            query += f" {style}"
        if budget:
            query += f" 预算{budget}元"

        results = self.kb.search("merchant_info", query, k=limit)

        merchants = []
        for doc, score in results:
            merchants.append({
                "content": doc.page_content,
                "source": doc.metadata.get("source", "unknown"),
                "relevance_score": round(max(0, 1 - score), 2),
            })

        return merchants


if __name__ == "__main__":
    agent = CEndAgent()

    # 测试补贴计算
    result = agent.calculate_subsidy(10000, "家具")
    print("补贴计算结果:", result)

    # 测试风格推荐
    styles = agent.recommend_style({"budget_level": "中等", "age_group": "年轻人"})
    print("风格推荐:", styles)
