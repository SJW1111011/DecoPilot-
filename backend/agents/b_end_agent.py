"""
B端智能体 - 商家助手
服务于商家用户，提供入驻指导、数据产品咨询、获客策略等服务
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from backend.agents.base_agent import BaseAgent
from backend.agents.prompts.b_end_prompts import (
    B_END_SYSTEM_PROMPT,
    B_END_ONBOARDING_PROMPT,
    B_END_DATA_PRODUCT_PROMPT,
    B_END_CUSTOMER_ACQUISITION_PROMPT,
)
from backend.config.business_rules import (
    MERCHANT_ONBOARDING,
    CUSTOMER_SCRIPTS,
    BEST_CONTACT_TIMES,
)


class BEndAgent(BaseAgent):
    """B端智能体 - 商家助手"""

    def __init__(self):
        super().__init__(user_type="b_end")

    def _get_system_prompt(self) -> str:
        """获取B端系统提示词"""
        return B_END_SYSTEM_PROMPT

    def get_onboarding_prompt(self) -> str:
        """获取入驻指导专用提示词"""
        return B_END_ONBOARDING_PROMPT

    def get_data_product_prompt(self) -> str:
        """获取数据产品咨询专用提示词"""
        return B_END_DATA_PRODUCT_PROMPT

    def get_customer_acquisition_prompt(self) -> str:
        """获取获客策略专用提示词"""
        return B_END_CUSTOMER_ACQUISITION_PROMPT

    def get_onboarding_info(self) -> dict:
        """获取入驻指南信息"""
        return MERCHANT_ONBOARDING

    def analyze_roi(self, investment: float, revenue: float, period_days: int = 30) -> dict:
        """
        分析ROI

        Args:
            investment: 投入金额
            revenue: 收入金额
            period_days: 统计周期（天）

        Returns:
            ROI分析结果
        """
        if investment <= 0:
            return {"error": "投入金额必须大于0"}

        roi = (revenue - investment) / investment * 100
        daily_revenue = revenue / period_days
        daily_investment = investment / period_days
        profit = revenue - investment

        # 计算回本周期
        if daily_revenue > daily_investment:
            payback_days = investment / (daily_revenue - daily_investment)
        else:
            payback_days = None

        return {
            "investment": investment,
            "revenue": revenue,
            "period_days": period_days,
            "roi_percentage": round(roi, 2),
            "daily_revenue": round(daily_revenue, 2),
            "daily_investment": round(daily_investment, 2),
            "profit": round(profit, 2),
            "payback_days": round(payback_days, 1) if payback_days else "无法回本",
            "assessment": self._assess_roi(roi),
            "suggestions": self._get_roi_suggestions(roi, profit),
        }

    def _assess_roi(self, roi: float) -> dict:
        """评估ROI水平"""
        if roi >= 200:
            return {
                "level": "优秀",
                "description": "ROI表现非常好，建议继续保持当前策略",
                "color": "green",
            }
        elif roi >= 100:
            return {
                "level": "良好",
                "description": "ROI表现不错，可以考虑适度增加投入",
                "color": "blue",
            }
        elif roi >= 50:
            return {
                "level": "一般",
                "description": "ROI有提升空间，建议优化投放策略",
                "color": "yellow",
            }
        elif roi >= 0:
            return {
                "level": "较低",
                "description": "ROI偏低，建议分析原因并调整策略",
                "color": "orange",
            }
        else:
            return {
                "level": "亏损",
                "description": "当前投入产出为负，建议暂停并重新评估",
                "color": "red",
            }

    def _get_roi_suggestions(self, roi: float, profit: float) -> list[str]:
        """根据ROI给出优化建议"""
        suggestions = []
        if roi < 50:
            suggestions.append("检查投放渠道的精准度，优化目标人群定向")
            suggestions.append("分析转化漏斗，找出流失最严重的环节")
        if roi < 100:
            suggestions.append("优化落地页内容，提高转化率")
            suggestions.append("测试不同的投放时段和素材")
        if profit < 0:
            suggestions.append("建议暂停低效投放，重新评估策略")
            suggestions.append("考虑调整产品定价或促销策略")
        if roi >= 100:
            suggestions.append("当前策略效果良好，可以考虑扩大投放规模")
            suggestions.append("尝试拓展新的获客渠道")
        return suggestions

    def generate_customer_script(self, scenario: str, product_category: str) -> dict:
        """
        生成获客话术

        Args:
            scenario: 场景（首次接触/跟进/促单）
            product_category: 产品品类

        Returns:
            话术建议
        """
        script_template = CUSTOMER_SCRIPTS.get(scenario, CUSTOMER_SCRIPTS["首次接触"])

        # 替换模板中的品类占位符
        script = {
            "opening": script_template["opening"].format(category=product_category),
            "value_proposition": script_template["value"],
            "call_to_action": script_template["action"],
        }

        return {
            "scenario": scenario,
            "product_category": product_category,
            "script": script,
            "tips": script_template.get("tips", []),
        }

    def get_best_contact_time(self, customer_type: str = "业主") -> dict:
        """
        获取最佳触达时机建议

        Args:
            customer_type: 客户类型

        Returns:
            触达时机建议
        """
        time_config = BEST_CONTACT_TIMES.get(customer_type, BEST_CONTACT_TIMES["业主"])

        return {
            "customer_type": customer_type,
            "best_times": time_config["best"],
            "avoid_times": time_config["avoid"],
            "tips": "建议根据客户的实际反馈调整联系时间",
        }

    def calculate_commission(self, order_amount: float) -> dict:
        """
        计算平台佣金

        Args:
            order_amount: 订单金额

        Returns:
            佣金计算结果
        """
        service_rate = MERCHANT_ONBOARDING["fees"]["service_rate"]
        commission = order_amount * service_rate

        return {
            "order_amount": order_amount,
            "service_rate": service_rate,
            "commission": round(commission, 2),
            "net_income": round(order_amount - commission, 2),
            "note": MERCHANT_ONBOARDING["fees"]["service_note"],
        }


if __name__ == "__main__":
    agent = BEndAgent()

    # 测试ROI分析
    roi_result = agent.analyze_roi(5000, 15000, 30)
    print("ROI分析结果:", roi_result)

    # 测试话术生成
    script = agent.generate_customer_script("首次接触", "定制家具")
    print("获客话术:", script)

    # 测试入驻信息
    onboarding = agent.get_onboarding_info()
    print("入驻信息:", onboarding)
