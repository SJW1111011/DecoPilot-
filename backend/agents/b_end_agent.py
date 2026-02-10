"""
B端智能体 - 商家助手
服务于商家用户，提供入驻指导、数据产品咨询、获客策略等服务
整合记忆系统、推理引擎、工具系统等高级能力
"""
import os
import sys
from typing import List, Dict, Optional, AsyncGenerator

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from backend.agents.enhanced_agent import EnhancedAgent
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
from backend.core.output_formatter import OutputFormatter, OutputType
from backend.core.stage_reasoning import get_stage_reasoning, BEndStage


class BEndAgent(EnhancedAgent):
    """B端智能体 - 商家助手（增强版）

    继承自 EnhancedAgent，具备以下能力：
    - 三层记忆系统（短期/长期/工作记忆）
    - 智能推理引擎（CoT/ToT/ReAct）
    - 工具调用系统
    - 多模态处理
    - 结构化输出
    - 阶段感知专家系统（商业顾问/营销专家/数据分析师/财务顾问）
    """

    def __init__(self):
        super().__init__(user_type="b_end", agent_name="洞掌柜")

    def _get_system_prompt(self) -> str:
        """获取B端系统提示词"""
        return B_END_SYSTEM_PROMPT

    # === 专家角色方法 ===

    def get_expert_role_for_stage(self, stage: str) -> dict:
        """
        获取指定阶段的专家角色信息

        Args:
            stage: 商家阶段（入驻/获客/经营分析/核销结算）

        Returns:
            专家角色信息
        """
        expert_role = self.stage_reasoning.expert_manager.get_expert_role(stage, "b_end")
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
        获取所有B端专家角色

        Returns:
            专家角色列表
        """
        experts = self.stage_reasoning.expert_manager.get_all_experts("b_end")
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
        from backend.core.stage_reasoning import B_END_STAGE_TRANSITIONS
        return B_END_STAGE_TRANSITIONS.get((from_stage, to_stage), f"您已进入{to_stage}阶段，有什么可以帮您的？")

    # === 增强版处理方法 ===

    async def process_with_roi_analysis(self, message: str, session_id: str,
                                         user_id: str = None,
                                         investment: float = None,
                                         revenue: float = None) -> AsyncGenerator:
        """
        处理 ROI 分析查询，自动调用 ROI 计算工具

        Args:
            message: 用户消息
            session_id: 会话ID
            user_id: 用户ID
            investment: 投入金额（可选，也会从消息中提取）
            revenue: 收入金额（可选，也会从消息中提取）

        Yields:
            输出事件
        """
        # 尝试从参数或消息中提取数值
        if investment is None:
            investment = self._extract_amount(message, "投入")
        if revenue is None:
            revenue = self._extract_amount(message, "收入")

        # 如果能提取到参数，先计算 ROI
        if investment and revenue:
            roi_result = self.analyze_roi(investment, revenue)
            # 将 ROI 结果存入工作记忆
            self.set_working_memory(session_id, "last_roi_analysis", roi_result)

        # 调用父类的处理方法
        async for event in self.process(message, session_id, user_id):
            yield event

    async def process_with_customer_script(self, message: str, session_id: str,
                                            user_id: str = None,
                                            scenario: str = "首次接触",
                                            product_category: str = None) -> AsyncGenerator:
        """
        处理获客话术生成查询

        Args:
            message: 用户消息
            session_id: 会话ID
            user_id: 用户ID
            scenario: 场景（首次接触/跟进/促单）
            product_category: 产品品类

        Yields:
            输出事件
        """
        # 获取商家画像中的主营品类
        profile = self.get_user_profile(user_id or session_id)

        # 如果没有指定品类，尝试从用户画像获取
        if not product_category:
            product_category = profile.metadata.get("main_category", "家居产品")

        # 生成话术并存入工作记忆
        script_result = self.generate_customer_script(scenario, product_category)
        self.set_working_memory(session_id, "last_script", script_result)

        # 调用父类的处理方法
        async for event in self.process(message, session_id, user_id):
            yield event

    # === 原有业务方法（保持兼容） ===

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