# -*- coding: utf-8 -*-
"""
智能体工厂

创建和管理基于新框架的智能体实例
"""

import asyncio
import logging
from typing import Dict, Optional, Any
from dataclasses import dataclass, field

from ..runtime import AgentRuntime, create_agent
from ..config import AgentConfig, LLMConfig, MemoryConfig, ReasoningConfig, ToolConfig
from ..capabilities.tools import ToolDefinition, ToolParameter, ToolCategory

logger = logging.getLogger(__name__)


# C端系统提示词
C_END_SYSTEM_PROMPT = """你是"小洞"，洞窝家居平台的AI助手，专门服务于业主用户。

你的职责：
1. 解答装修相关问题（风格选择、材料选购、预算规划等）
2. 介绍平台补贴政策和优惠活动
3. 推荐合适的商家和产品
4. 提供装修流程指导

沟通风格：
- 亲切友好，像朋友一样交流
- 专业但不晦涩，用通俗易懂的语言
- 主动提供有价值的建议
- 关注用户的实际需求

注意事项：
- 补贴金额以平台实际规则为准
- 推荐商家时要客观公正
- 遇到不确定的问题，建议用户咨询平台客服
"""

# B端系统提示词
B_END_SYSTEM_PROMPT = """你是"洞洞"，洞窝家居平台的商家服务助手。

你的职责：
1. 指导商家入驻流程和资质要求
2. 介绍平台数据产品和营销工具
3. 提供获客策略和运营建议
4. 解答商家常见问题

沟通风格：
- 专业高效，直击要点
- 数据驱动，用数据说话
- 提供可操作的建议
- 关注商家的业务增长

注意事项：
- 入驻政策以平台最新规则为准
- 数据产品介绍要准确
- 涉及费用问题建议联系商务经理
"""


@dataclass
class AgentInstance:
    """智能体实例"""
    runtime: AgentRuntime
    config: AgentConfig
    initialized: bool = False


class AgentFactory:
    """
    智能体工厂

    负责创建和管理智能体实例
    """

    def __init__(self):
        self._agents: Dict[str, AgentInstance] = {}
        self._lock = asyncio.Lock()
        self._initialized = False

    async def initialize(self) -> None:
        """初始化工厂"""
        if self._initialized:
            return

        # 预创建常用智能体
        await self.get_or_create("c_end_default", "c_end")
        await self.get_or_create("b_end_default", "b_end")

        self._initialized = True
        logger.info("Agent factory initialized")

    async def get_or_create(
        self,
        name: str,
        agent_type: str,
        config: AgentConfig = None
    ) -> AgentRuntime:
        """
        获取或创建智能体

        Args:
            name: 智能体名称
            agent_type: 智能体类型 (c_end | b_end | general)
            config: 可选配置

        Returns:
            智能体运行时实例
        """
        async with self._lock:
            if name in self._agents and self._agents[name].initialized:
                return self._agents[name].runtime

            # 创建配置
            if config is None:
                config = self._create_default_config(name, agent_type)

            # 创建智能体
            runtime = create_agent(name, agent_type, config)

            # 注册领域工具
            self._register_domain_tools(runtime, agent_type)

            # 初始化
            await runtime.initialize()

            # 缓存实例
            self._agents[name] = AgentInstance(
                runtime=runtime,
                config=config,
                initialized=True
            )

            logger.info(f"Created agent: {name} (type={agent_type})")
            return runtime

    def _create_default_config(self, name: str, agent_type: str) -> AgentConfig:
        """创建默认配置"""
        # 根据类型选择系统提示词
        if agent_type == "c_end":
            system_prompt = C_END_SYSTEM_PROMPT
        elif agent_type == "b_end":
            system_prompt = B_END_SYSTEM_PROMPT
        else:
            system_prompt = "你是一个智能助手，可以帮助用户解答问题。"

        return AgentConfig(
            name=name,
            type=agent_type,
            description=f"{agent_type} agent",
            llm=LLMConfig(
                provider="dashscope",
                model="qwen-plus",
                temperature=0.7,
                max_tokens=2000,
            ),
            memory=MemoryConfig(
                short_term_max_items=50,
                long_term_max_items=1000,
            ),
            reasoning=ReasoningConfig(
                max_reasoning_steps=5,
            ),
            tools=ToolConfig(
                timeout=30,
                max_retries=2,
            ),
            system_prompt=system_prompt,
            capabilities=["memory", "reasoning", "tools", "multimodal", "output"],
        )

    def _register_domain_tools(self, runtime: AgentRuntime, agent_type: str) -> None:
        """注册领域特定工具"""
        if agent_type == "c_end":
            self._register_c_end_tools(runtime)
        elif agent_type == "b_end":
            self._register_b_end_tools(runtime)

    def _register_c_end_tools(self, runtime: AgentRuntime) -> None:
        """注册C端工具"""
        # 装修风格推荐工具
        runtime.register_tool(ToolDefinition(
            name="style_recommender",
            description="根据用户偏好推荐装修风格",
            category=ToolCategory.UTILITY,
            parameters=[
                ToolParameter(name="budget_level", type="string", description="预算水平",
                            enum=["低", "中等", "高"]),
                ToolParameter(name="house_size", type="string", description="房屋面积",
                            enum=["小户型", "中户型", "大户型"], required=False),
                ToolParameter(name="age_group", type="string", description="年龄段",
                            enum=["年轻人", "中年人", "老年人"], required=False),
            ],
            handler=self._recommend_style
        ))

        # 装修流程查询工具
        runtime.register_tool(ToolDefinition(
            name="decoration_process",
            description="获取装修流程指南",
            category=ToolCategory.UTILITY,
            parameters=[
                ToolParameter(name="stage", type="string", description="装修阶段",
                            enum=["全部", "准备阶段", "施工阶段", "验收阶段"], required=False),
            ],
            handler=self._get_decoration_process
        ))

    def _register_b_end_tools(self, runtime: AgentRuntime) -> None:
        """注册B端工具"""
        # 入驻流程查询工具
        runtime.register_tool(ToolDefinition(
            name="onboarding_guide",
            description="获取商家入驻指南",
            category=ToolCategory.UTILITY,
            parameters=[
                ToolParameter(name="merchant_type", type="string", description="商家类型",
                            enum=["品牌商", "经销商", "服务商"]),
            ],
            handler=self._get_onboarding_guide
        ))

        # 数据产品介绍工具
        runtime.register_tool(ToolDefinition(
            name="data_products",
            description="介绍平台数据产品",
            category=ToolCategory.UTILITY,
            parameters=[
                ToolParameter(name="product_type", type="string", description="产品类型",
                            enum=["流量分析", "用户画像", "竞品分析", "全部"], required=False),
            ],
            handler=self._get_data_products
        ))

    # === 工具实现 ===

    def _recommend_style(
        self,
        budget_level: str,
        house_size: str = None,
        age_group: str = None
    ) -> Dict[str, Any]:
        """推荐装修风格"""
        styles = {
            "现代简约": {
                "budget_level": "中等",
                "features": ["简洁线条", "功能性强", "易打理"],
                "suitable_for": ["年轻人", "小户型", "中户型"],
                "price_range": "800-1200元/㎡"
            },
            "北欧风格": {
                "budget_level": "中等",
                "features": ["自然元素", "明亮色调", "温馨舒适"],
                "suitable_for": ["年轻人", "小户型"],
                "price_range": "900-1300元/㎡"
            },
            "新中式": {
                "budget_level": "高",
                "features": ["传统元素", "文化底蕴", "大气稳重"],
                "suitable_for": ["中年人", "大户型"],
                "price_range": "1200-2000元/㎡"
            },
            "轻奢风格": {
                "budget_level": "高",
                "features": ["精致细节", "品质感", "低调奢华"],
                "suitable_for": ["中年人", "中户型", "大户型"],
                "price_range": "1500-2500元/㎡"
            },
            "日式风格": {
                "budget_level": "低",
                "features": ["原木元素", "禅意空间", "收纳设计"],
                "suitable_for": ["年轻人", "小户型"],
                "price_range": "600-1000元/㎡"
            },
        }

        recommendations = []
        for name, info in styles.items():
            score = 0
            if info["budget_level"] == budget_level:
                score += 3
            if house_size and house_size in info["suitable_for"]:
                score += 2
            if age_group and age_group in info["suitable_for"]:
                score += 2

            recommendations.append({
                "style": name,
                "score": score,
                "info": info
            })

        recommendations.sort(key=lambda x: x["score"], reverse=True)
        return {
            "recommendations": recommendations[:3],
            "note": "以上推荐仅供参考，具体风格选择还需结合个人喜好"
        }

    def _get_decoration_process(self, stage: str = "全部") -> Dict[str, Any]:
        """获取装修流程"""
        process = {
            "准备阶段": [
                {"step": 1, "name": "确定预算", "description": "根据房屋面积和装修档次确定总预算"},
                {"step": 2, "name": "选择风格", "description": "确定装修风格，可参考样板间"},
                {"step": 3, "name": "找装修公司", "description": "对比多家公司，查看案例和口碑"},
                {"step": 4, "name": "签订合同", "description": "仔细阅读合同条款，明确工期和付款方式"},
            ],
            "施工阶段": [
                {"step": 5, "name": "拆改工程", "description": "墙体拆改、水电改造"},
                {"step": 6, "name": "水电工程", "description": "水电布线、开槽埋管"},
                {"step": 7, "name": "泥瓦工程", "description": "防水、贴砖、找平"},
                {"step": 8, "name": "木工工程", "description": "吊顶、柜体制作"},
                {"step": 9, "name": "油漆工程", "description": "墙面处理、刷漆"},
            ],
            "验收阶段": [
                {"step": 10, "name": "硬装验收", "description": "检查水电、墙面、地面等"},
                {"step": 11, "name": "软装搭配", "description": "家具、窗帘、装饰品"},
                {"step": 12, "name": "通风除醛", "description": "开窗通风，检测空气质量"},
            ],
        }

        if stage == "全部":
            return {"process": process, "total_steps": 12}
        elif stage in process:
            return {"process": {stage: process[stage]}, "stage": stage}
        else:
            return {"error": f"未知阶段: {stage}"}

    def _get_onboarding_guide(self, merchant_type: str) -> Dict[str, Any]:
        """获取入驻指南"""
        guides = {
            "品牌商": {
                "requirements": [
                    "企业营业执照",
                    "品牌授权书",
                    "产品质检报告",
                    "商标注册证",
                ],
                "process": [
                    "提交入驻申请",
                    "资质审核（3-5个工作日）",
                    "签订合作协议",
                    "店铺装修上线",
                    "开始运营",
                ],
                "fees": "保证金5万元，平台服务费3%",
                "benefits": ["品牌专区展示", "流量扶持", "数据分析工具"],
            },
            "经销商": {
                "requirements": [
                    "企业营业执照",
                    "品牌授权书",
                    "经销合同",
                ],
                "process": [
                    "提交入驻申请",
                    "资质审核（3-5个工作日）",
                    "签订合作协议",
                    "店铺装修上线",
                ],
                "fees": "保证金2万元，平台服务费5%",
                "benefits": ["区域流量支持", "营销工具"],
            },
            "服务商": {
                "requirements": [
                    "企业营业执照",
                    "相关资质证书",
                    "服务案例",
                ],
                "process": [
                    "提交入驻申请",
                    "资质审核（5-7个工作日）",
                    "签订服务协议",
                    "开始接单",
                ],
                "fees": "保证金1万元，平台服务费8%",
                "benefits": ["精准客户匹配", "评价体系"],
            },
        }

        if merchant_type in guides:
            return {
                "merchant_type": merchant_type,
                "guide": guides[merchant_type],
                "contact": "商务合作热线：400-xxx-xxxx"
            }
        else:
            return {"error": f"未知商家类型: {merchant_type}"}

    def _get_data_products(self, product_type: str = "全部") -> Dict[str, Any]:
        """获取数据产品介绍"""
        products = {
            "流量分析": {
                "name": "流量分析工具",
                "description": "实时监控店铺流量，分析访客来源和行为",
                "features": ["PV/UV统计", "访客路径分析", "转化漏斗"],
                "price": "基础版免费，高级版299元/月",
            },
            "用户画像": {
                "name": "用户画像系统",
                "description": "深度分析目标用户特征，精准营销",
                "features": ["人群标签", "消费能力分析", "兴趣偏好"],
                "price": "599元/月",
            },
            "竞品分析": {
                "name": "竞品分析报告",
                "description": "了解竞争对手动态，制定差异化策略",
                "features": ["价格监控", "销量排名", "营销活动追踪"],
                "price": "999元/月",
            },
        }

        if product_type == "全部":
            return {"products": products}
        elif product_type in products:
            return {"product": products[product_type]}
        else:
            return {"error": f"未知产品类型: {product_type}"}

    async def shutdown(self) -> None:
        """关闭所有智能体"""
        for name, instance in self._agents.items():
            if instance.initialized:
                try:
                    await instance.runtime.shutdown()
                    logger.info(f"Shutdown agent: {name}")
                except Exception as e:
                    logger.error(f"Error shutting down agent {name}: {e}")

        self._agents.clear()
        self._initialized = False


# 全局工厂实例
_factory: Optional[AgentFactory] = None


def get_agent_factory() -> AgentFactory:
    """获取全局工厂实例"""
    global _factory
    if _factory is None:
        _factory = AgentFactory()
    return _factory


async def create_c_end_agent(name: str = "c_end_default") -> AgentRuntime:
    """创建C端智能体"""
    factory = get_agent_factory()
    return await factory.get_or_create(name, "c_end")


async def create_b_end_agent(name: str = "b_end_default") -> AgentRuntime:
    """创建B端智能体"""
    factory = get_agent_factory()
    return await factory.get_or_create(name, "b_end")
