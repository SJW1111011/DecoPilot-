"""
C端智能体 - 业主顾问
服务于业主用户，提供装修咨询、补贴政策、商家推荐等服务
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from backend.agents.base_agent import BaseAgent
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


class CEndAgent(BaseAgent):
    """C端智能体 - 业主顾问"""

    def __init__(self):
        super().__init__(user_type="c_end")

    def _get_system_prompt(self) -> str:
        """获取C端系统提示词"""
        return C_END_SYSTEM_PROMPT

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

        results = self.multi_kb.search("merchant_info", query, k=limit)

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
