"""
阶段感知专家系统
让智能体在不同阶段扮演不同的专家角色，真正理解用户需求，给出专业建议
"""
import json
import time
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum

from backend.core.logging_config import get_logger

logger = get_logger("stage_reasoning")


# ============ 阶段定义 ============

class CEndStage(str, Enum):
    """C端装修阶段"""
    PREPARATION = "准备"  # 准备阶段
    DESIGN = "设计"       # 设计阶段
    CONSTRUCTION = "施工" # 施工阶段
    SOFT_DECORATION = "软装"  # 软装阶段
    MOVE_IN = "入住"      # 入住阶段


class BEndStage(str, Enum):
    """B端商家阶段"""
    ONBOARDING = "入驻"       # 入驻阶段
    ACQUISITION = "获客"      # 获客阶段
    ANALYTICS = "经营分析"    # 经营分析阶段
    SETTLEMENT = "核销结算"   # 核销结算阶段


# ============ 专家角色定义 ============

@dataclass
class ExpertRole:
    """专家角色"""
    name: str                    # 角色名称
    stage: str                   # 对应阶段
    core_value: str              # 核心价值
    professional_perspective: str # 专业视角
    system_prompt: str           # 系统提示词


# ============ 阶段上下文 ============

@dataclass
class StageContext:
    """阶段上下文"""
    stage: str                           # 推断的阶段
    stage_confidence: float              # 阶段置信度 0-1
    user_intent: str                     # 用户真实意图
    surface_question: str                # 表面问题
    deep_need: str                       # 深层需求
    potential_needs: List[str]           # 潜在需求（用户没说但可能需要的）
    emotional_state: str                 # 情绪状态
    focus_points: List[str]              # 关注重点
    stage_changed: bool = False          # 阶段是否发生变化
    transition_trigger: Optional[str] = None  # 转换触发原因


@dataclass
class StageTransition:
    """阶段转换"""
    from_stage: str              # 原阶段
    to_stage: str                # 新阶段
    confidence: float            # 置信度
    trigger: str                 # 触发原因
    transition_guidance: str     # 转换引导建议


# ============ C端专家角色提示词 ============

C_END_EXPERT_PROMPTS = {
    "准备": """
# 你的角色：资深装修规划师

## 专业背景
你有15年装修行业经验，帮助过上千位业主规划装修。你深知新手业主的困惑和容易踩的坑。

## 你的核心价值
- 帮用户建立正确的装修认知框架
- 预见并提醒潜在的问题和风险
- 给出切实可行的规划建议

## 思考方式
1. 先了解用户的基本情况（户型、预算、时间、偏好）
2. 从全局视角帮用户梳理装修流程
3. 针对用户情况给出个性化建议
4. 主动提醒容易忽视的问题

## 专业建议原则
- 预算建议要留有余地（建议预留10-15%机动资金）
- 风格选择要结合实际（户型、采光、生活习惯）
- 时间规划要合理（考虑季节、工期、个人安排）
- 主动提供"避坑指南"

## 回答风格
- 像一位经验丰富的朋友在给建议
- 用通俗易懂的语言，避免专业术语堆砌
- 给出具体可操作的下一步建议
""",

    "设计": """
# 你的角色：专业设计顾问

## 专业背景
你是资深室内设计顾问，精通各种装修风格，擅长帮业主评估设计方案的优劣。

## 你的核心价值
- 帮用户理解设计方案的专业细节
- 从多角度分析方案的优缺点
- 帮用户做出明智的设计决策

## 思考方式
1. 理解用户的决策困境是什么
2. 从专业角度分析各方案的优劣
3. 结合用户的偏好和实际情况给出建议
4. 提醒可能被忽视的细节问题

## 专业建议原则
- 设计要兼顾美观和实用
- 关注动线设计、收纳空间、采光通风
- 报价分析要细致（单价、工艺、材料品牌）
- 合同审核要仔细（付款节点、验收标准、售后条款）

## 回答风格
- 专业但不居高临下
- 提供对比分析，让用户自己做决定
- 尊重用户的审美偏好
""",

    "施工": """
# 你的角色：工程监理专家

## 专业背景
你是资深工程监理，精通各工种的施工工艺和验收标准，能快速识别施工问题。

## 你的核心价值
- 帮用户识别施工质量问题
- 提供专业的验收标准和方法
- 快速给出问题的解决方案

## 思考方式
1. 快速判断问题的类型和严重程度
2. 分析问题产生的原因
3. 给出明确的解决方案和验收标准
4. 提供预防类似问题的建议

## 专业建议原则
- 水电隐蔽工程必须拍照留存
- 防水必须做闭水试验（48小时）
- 瓷砖空鼓率不超过5%，空鼓面积不超过单砖15%
- 墙面平整度误差不超过3mm

## 回答风格
- 快速、准确、可操作
- 问题严重时直接指出，不含糊
- 给出具体的验收方法和标准
""",

    "软装": """
# 你的角色：软装搭配师

## 专业背景
你是专业软装设计师，擅长空间搭配和家具选购，能帮用户打造理想的家。

## 你的核心价值
- 提供专业的软装搭配建议
- 帮用户在预算内选到合适的产品
- 避免搭配踩雷，提升整体效果

## 思考方式
1. 了解用户的整体风格和空间特点
2. 分析搭配需求（色彩、材质、尺寸）
3. 提供多个搭配方案供选择
4. 考虑性价比和实用性

## 专业建议原则
- 大件家具先定，小件配饰后选
- 色彩搭配遵循631法则（主色60%、辅色30%、点缀10%）
- 家具尺寸要与空间匹配，预留通道空间
- 灯光设计要分层（主照明、氛围灯、功能灯）

## 回答风格
- 有审美品味但不强加于人
- 提供灵感和选择，尊重用户喜好
- 实用建议与美学建议结合
""",

    "入住": """
# 你的角色：居家生活顾问

## 专业背景
你是居家生活专家，熟悉新房入住的注意事项和日常维护知识。

## 你的核心价值
- 帮用户安心入住新家
- 提供健康安全的入住建议
- 指导日常维护和保养

## 思考方式
1. 确认用户的具体问题
2. 给出准确实用的建议
3. 补充相关注意事项

## 专业建议原则
- 甲醛检测建议找专业机构
- 通风至少3个月，夏季高温通风效果更好
- 保留所有保修凭证和联系方式
- 定期检查水电设施

## 回答风格
- 简洁实用，不制造焦虑
- 给出明确的建议和标准
- 祝贺用户乔迁之喜
"""
}


# ============ B端专家角色提示词 ============

B_END_EXPERT_PROMPTS = {
    "入驻": """
# 你的角色：商业顾问

## 专业背景
你是资深商业顾问，帮助过数百家商家评估平台入驻决策，精通成本收益分析。

## 你的核心价值
- 帮商家客观评估入驻价值
- 算清成本和预期收益
- 给出理性的入驻建议

## 思考方式
1. 了解商家的品类、规模、现有渠道
2. 详细说明入驻条件和流程
3. 计算入驻成本（保证金、服务费、推广费）
4. 预估潜在收益和回本周期
5. 给出客观的入驻建议

## 专业建议原则
- 用数据说话，不做空洞承诺
- 主动说明费用结构，不回避成本问题
- 对比分析平台优势和适合的商家类型
- 给出入驻后的经营建议

## 回答风格
- 专业、务实、有数据支撑
- 帮商家算清账，做理性决策
""",

    "获客": """
# 你的角色：营销专家

## 专业背景
你是资深营销专家，精通家居建材行业的获客策略，帮助过大量商家提升转化率。

## 你的核心价值
- 提供可立即执行的获客策略
- 帮商家优化转化漏斗
- 生成高转化的话术和触达方案

## 思考方式
1. 分析商家当前的获客痛点
2. 识别转化漏斗中的瓶颈
3. 提供针对性的优化策略
4. 给出可执行的话术和时机建议

## 专业建议原则
- 5分钟内响应客户可提升30%转化率
- 话术要场景化（首次接触/跟进/促单）
- 触达时机很重要（工作日10-12点、14-17点最佳）
- 建立客户分层，差异化跟进

## 回答风格
- 策略明确，可立即执行
- 给出具体的话术示例
""",

    "经营分析": """
# 你的角色：数据分析师

## 专业背景
你是资深数据分析师，精通家居建材行业的经营数据分析，擅长从数据中发现问题和机会。

## 你的核心价值
- 帮商家解读经营数据
- 发现问题和增长机会
- 提供数据驱动的优化建议

## 思考方式
1. 收集和整理相关数据
2. 从多维度分析（流量/转化/客单价/复购）
3. 对比行业基准，识别差距
4. 找出关键问题和机会点

## 专业建议原则
- ROI ≥ 200% 为优秀，≥ 100% 为良好
- 转化率行业基准：咨询转化 15-25%，成交转化 5-10%
- 优化建议要有优先级排序

## 回答风格
- 数据说话，有理有据
- 分析深入，建议具体
""",

    "核销结算": """
# 你的角色：财务顾问

## 专业背景
你是平台财务顾问，精通结算规则和费用计算，能准确解答商家的资金问题。

## 你的核心价值
- 准确解答结算规则
- 帮商家理清费用明细
- 消除资金相关的疑虑

## 思考方式
1. 确认商家的具体问题
2. 准确说明相关规则
3. 给出清晰的计算说明

## 专业建议原则
- 标准结算周期 T+7，快速结算 T+1
- 佣金 = 成交金额 × 服务费率（3%）
- 退款会相应扣减已结算佣金

## 回答风格
- 准确、清晰、无歧义
- 给出具体的计算示例
"""
}


# ============ 阶段理解关键词（用于快速匹配，LLM分析的补充） ============

C_END_STAGE_KEYWORDS = {
    "准备": {
        "explicit": ["准备装修", "打算装修", "想装修", "要装修", "计划装修", "还没开始", "刚买房", "新房", "毛坯"],
        "implicit": ["预算多少", "怎么开始", "从哪入手", "装修流程", "找谁装", "全包半包", "装修公司怎么选"],
        "questions": ["装修要准备什么", "第一步做什么", "需要多少钱", "要多久"],
    },
    "设计": {
        "explicit": ["设计方案", "设计师", "效果图", "量房", "出图", "设计中", "在设计", "看方案"],
        "implicit": ["风格选择", "户型改造", "布局", "动线", "收纳设计", "报价单", "设计费"],
        "questions": ["方案怎么样", "这个设计好不好", "报价合理吗", "要不要改"],
    },
    "施工": {
        "explicit": ["施工中", "在装修", "正在装", "开工了", "工人", "工地"],
        "implicit": ["水电", "贴砖", "刷漆", "吊顶", "防水", "找平", "木工", "泥工", "油漆工"],
        "questions": ["这样做对吗", "质量有问题", "空鼓", "开裂", "漏水", "验收标准"],
    },
    "软装": {
        "explicit": ["软装", "买家具", "选家具", "硬装完", "快完工", "家具进场"],
        "implicit": ["沙发", "床", "餐桌", "窗帘", "灯具", "地毯", "挂画", "绿植", "搭配"],
        "questions": ["选什么颜色", "尺寸多大", "怎么搭配", "哪个品牌好"],
    },
    "入住": {
        "explicit": ["入住", "搬家", "装完了", "已经装好", "住进去"],
        "implicit": ["通风", "甲醛", "除味", "保洁", "开荒", "家电", "收纳"],
        "questions": ["多久能住", "甲醛超标吗", "怎么除甲醛", "需要检测吗"],
    },
}

B_END_STAGE_KEYWORDS = {
    "入驻": {
        "explicit": ["入驻", "开店", "加入平台", "想入驻", "怎么入驻"],
        "implicit": ["入驻条件", "保证金", "资质要求", "入驻流程", "开店费用"],
        "questions": ["能入驻吗", "需要什么条件", "费用多少", "多久能开通"],
    },
    "获客": {
        "explicit": ["获客", "找客户", "拓客", "引流", "客源"],
        "implicit": ["转化率", "客户跟进", "话术", "触达", "线索", "咨询量"],
        "questions": ["怎么获客", "转化率低", "客户不回复", "怎么跟进"],
    },
    "经营分析": {
        "explicit": ["数据分析", "经营分析", "看数据", "报表"],
        "implicit": ["ROI", "投入产出", "转化漏斗", "客单价", "复购率", "流量"],
        "questions": ["ROI多少", "数据怎么看", "哪里有问题", "怎么提升"],
    },
    "核销结算": {
        "explicit": ["核销", "结算", "提现", "到账", "佣金"],
        "implicit": ["结算周期", "服务费", "扣款", "退款", "账单"],
        "questions": ["什么时候到账", "怎么结算", "扣了多少", "钱去哪了"],
    },
}


# ============ 阶段转换引导 ============

C_END_STAGE_TRANSITIONS = {
    ("准备", "设计"): "恭喜您进入设计阶段！这个阶段最重要的是：1）多看几家设计方案做对比；2）仔细审核报价单的每一项；3）合同条款要看清楚，特别是付款节点和验收标准。",
    ("设计", "施工"): "设计定稿后，施工阶段需要重点关注：1）开工前确认材料进场时间；2）水电改造后一定要拍照留存；3）每个节点验收不要马虎，发现问题及时沟通。",
    ("施工", "软装"): "硬装完成了！软装阶段建议您：1）先定大件家具（沙发、床、餐桌），再选小件配饰；2）注意家具尺寸与空间的匹配；3）不必一次买齐，可以慢慢添置。",
    ("软装", "入住"): "即将入住新家！入住前请确保：1）做一次全面的开荒保洁；2）建议做甲醛检测，确保空气质量达标；3）保留好所有的保修凭证和商家联系方式。",
}

B_END_STAGE_TRANSITIONS = {
    ("入驻", "获客"): "入驻成功！接下来获客是关键：1）完善店铺信息，提升曝光；2）及时响应客户咨询，5分钟内回复转化率最高；3）准备好不同场景的话术模板。",
    ("获客", "经营分析"): "获客有了一定基础后，建议关注数据分析：1）定期查看转化漏斗，找出流失环节；2）对比行业基准，了解自己的位置；3）根据数据调整获客策略。",
    ("经营分析", "核销结算"): "经营步入正轨后，结算问题需要了解：1）熟悉结算周期和规则；2）定期核对账单明细；3）有疑问及时联系平台客服。",
}


# ============ 阶段理解类 ============

class StageUnderstanding:
    """深度阶段理解"""

    def __init__(self, llm_caller=None):
        """
        初始化阶段理解器

        Args:
            llm_caller: LLM调用函数，签名为 async (prompt: str) -> str
        """
        self.llm_caller = llm_caller

    def set_llm_caller(self, llm_caller):
        """设置LLM调用函数"""
        self.llm_caller = llm_caller

    async def understand_user_context(
        self,
        query: str,
        conversation_history: List[dict],
        user_profile: dict,
        user_type: str = "c_end"
    ) -> StageContext:
        """
        综合理解用户当前状态

        Args:
            query: 当前问题
            conversation_history: 对话历史
            user_profile: 用户画像
            user_type: 用户类型 (c_end/b_end)

        Returns:
            StageContext: 阶段上下文
        """
        # 1. 先用关键词快速匹配
        keyword_stage, keyword_confidence = self._keyword_stage_detection(query, user_type)

        logger.info("关键词阶段检测完成", extra={
            "query": query[:100],
            "user_type": user_type,
            "keyword_stage": keyword_stage,
            "keyword_confidence": keyword_confidence,
            "llm_available": self.llm_caller is not None,
        })

        # 2. 如果有LLM，使用LLM深度分析
        if self.llm_caller and keyword_confidence < 0.8:
            try:
                logger.info("启动LLM深度阶段分析", extra={
                    "query": query[:100],
                    "keyword_confidence": keyword_confidence,
                })
                llm_context = await self._llm_stage_analysis(
                    query, conversation_history, user_profile, user_type
                )
                if llm_context:
                    logger.info("LLM阶段分析成功", extra={
                        "llm_stage": llm_context.stage,
                        "llm_confidence": llm_context.stage_confidence,
                        "emotional_state": llm_context.emotional_state,
                    })
                    return llm_context
            except Exception as e:
                logger.warning(f"LLM阶段分析失败: {e}")

        # 3. 回退到关键词匹配结果
        return self._build_context_from_keywords(
            query, keyword_stage, keyword_confidence, user_profile, user_type
        )

    def _keyword_stage_detection(self, query: str, user_type: str) -> Tuple[str, float]:
        """
        基于关键词的阶段检测

        Returns:
            (阶段, 置信度)
        """
        keywords_map = C_END_STAGE_KEYWORDS if user_type == "c_end" else B_END_STAGE_KEYWORDS
        default_stage = "准备" if user_type == "c_end" else "入驻"

        best_stage = default_stage
        best_score = 0.0
        matched_keywords = []

        for stage, keywords in keywords_map.items():
            score = 0.0

            # 显式关键词权重最高
            for kw in keywords.get("explicit", []):
                if kw in query:
                    score += 3.0
                    matched_keywords.append(f"[显式]{kw}→{stage}")

            # 隐式关键词次之
            for kw in keywords.get("implicit", []):
                if kw in query:
                    score += 2.0
                    matched_keywords.append(f"[隐式]{kw}→{stage}")

            # 问题类型关键词
            for kw in keywords.get("questions", []):
                if kw in query:
                    score += 1.5
                    matched_keywords.append(f"[问题]{kw}→{stage}")

            if score > best_score:
                best_score = score
                best_stage = stage

        # 计算置信度（归一化）
        confidence = min(1.0, best_score / 6.0) if best_score > 0 else 0.3

        if matched_keywords:
            logger.debug("关键词匹配详情", extra={
                "query": query[:100],
                "matched_keywords": matched_keywords,
                "best_stage": best_stage,
                "best_score": best_score,
                "confidence": confidence,
            })

        return best_stage, confidence

    async def _llm_stage_analysis(
        self,
        query: str,
        conversation_history: List[dict],
        user_profile: dict,
        user_type: str
    ) -> Optional[StageContext]:
        """使用LLM进行深度阶段分析"""
        if not self.llm_caller:
            return None

        # 构建分析提示词
        if user_type == "c_end":
            stages_desc = "准备（刚开始了解装修）、设计（在做设计方案）、施工（正在装修中）、软装（硬装完成选家具）、入住（装修完准备入住）"
        else:
            stages_desc = "入驻（了解或办理入驻）、获客（寻找客户）、经营分析（分析经营数据）、核销结算（处理结算问题）"

        # 格式化对话历史
        history_text = self._format_history(conversation_history[-5:]) if conversation_history else "无"

        # 格式化用户画像
        profile_text = self._format_user_profile(user_profile) if user_profile else "无"

        prompt = f"""作为一个装修行业专家，请分析这位用户的情况：

【用户画像】
{profile_text}

【对话历史】
{history_text}

【当前问题】
{query}

【可选阶段】
{stages_desc}

请分析并返回JSON格式：
{{
    "stage": "阶段名称",
    "confidence": 0.8,
    "surface_question": "用户表面在问什么",
    "deep_need": "用户深层需求是什么",
    "potential_needs": ["用户可能还需要但没问的"],
    "emotional_state": "用户情绪状态（焦虑/困惑/期待/平静等）",
    "focus_points": ["用户当前关注的重点"],
    "stage_changed": false,
    "transition_trigger": null
}}

只返回JSON，不要其他内容。"""

        try:
            response = await self.llm_caller(prompt)

            # 解析JSON
            import re
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group())
                return StageContext(
                    stage=data.get("stage", "准备" if user_type == "c_end" else "入驻"),
                    stage_confidence=float(data.get("confidence", 0.7)),
                    user_intent=data.get("deep_need", query),
                    surface_question=data.get("surface_question", query),
                    deep_need=data.get("deep_need", ""),
                    potential_needs=data.get("potential_needs", []),
                    emotional_state=data.get("emotional_state", "平静"),
                    focus_points=data.get("focus_points", []),
                    stage_changed=data.get("stage_changed", False),
                    transition_trigger=data.get("transition_trigger"),
                )
        except Exception as e:
            logger.warning(f"LLM阶段分析解析失败: {e}")

        return None

    def _build_context_from_keywords(
        self,
        query: str,
        stage: str,
        confidence: float,
        user_profile: dict,
        user_type: str
    ) -> StageContext:
        """基于关键词匹配结果构建上下文"""
        return StageContext(
            stage=stage,
            stage_confidence=confidence,
            user_intent=query,
            surface_question=query,
            deep_need=self._infer_deep_need(query, stage, user_type),
            potential_needs=self._infer_potential_needs(stage, user_type),
            emotional_state=self._detect_emotional_state(query),
            focus_points=self._extract_focus_points(query, stage),
            stage_changed=False,
            transition_trigger=None,
        )

    def _format_history(self, history: List[dict]) -> str:
        """格式化对话历史"""
        if not history:
            return "无"

        lines = []
        for item in history:
            role = item.get("role", "user")
            content = item.get("content", "")[:100]
            lines.append(f"- {role}: {content}")

        return "\n".join(lines)

    def _format_user_profile(self, profile: dict) -> str:
        """格式化用户画像"""
        if not profile:
            return "无"

        parts = []
        if profile.get("decoration_stage"):
            parts.append(f"当前阶段: {profile['decoration_stage']}")
        if profile.get("budget_range"):
            parts.append(f"预算: {profile['budget_range']}")
        if profile.get("preferred_styles"):
            parts.append(f"偏好风格: {', '.join(profile['preferred_styles'])}")
        if profile.get("house_area"):
            parts.append(f"房屋面积: {profile['house_area']}平米")

        return "; ".join(parts) if parts else "无"

    def _infer_deep_need(self, query: str, stage: str, user_type: str) -> str:
        """推断深层需求"""
        if user_type == "c_end":
            stage_needs = {
                "准备": "建立正确的装修认知，避免踩坑",
                "设计": "做出明智的设计决策",
                "施工": "确保施工质量，及时发现问题",
                "软装": "打造理想的家居环境",
                "入住": "安心入住，了解维护保养",
            }
        else:
            stage_needs = {
                "入驻": "评估入驻价值，做出理性决策",
                "获客": "高效获取客户，提升转化",
                "经营分析": "发现问题和机会，优化经营",
                "核销结算": "理清资金流，消除疑虑",
            }

        return stage_needs.get(stage, "获得专业帮助")

    def _infer_potential_needs(self, stage: str, user_type: str) -> List[str]:
        """推断潜在需求"""
        if user_type == "c_end":
            potential = {
                "准备": ["预算规划建议", "装修公司选择", "时间规划"],
                "设计": ["报价审核", "合同注意事项", "材料选择"],
                "施工": ["验收标准", "进度把控", "质量问题处理"],
                "软装": ["搭配建议", "品牌推荐", "尺寸选择"],
                "入住": ["甲醛检测", "保养知识", "保修事项"],
            }
        else:
            potential = {
                "入驻": ["费用明细", "入驻流程", "经营建议"],
                "获客": ["话术模板", "触达时机", "客户分层"],
                "经营分析": ["行业对比", "优化建议", "增长机会"],
                "核销结算": ["结算规则", "费用明细", "提现方式"],
            }

        return potential.get(stage, [])

    def _detect_emotional_state(self, query: str) -> str:
        """检测情绪状态"""
        anxiety_words = ["急", "担心", "怕", "焦虑", "着急", "赶紧", "马上"]
        confusion_words = ["不懂", "不知道", "迷茫", "困惑", "怎么办", "纠结"]
        anger_words = ["坑", "骗", "差", "烂", "投诉", "不满"]
        positive_words = ["期待", "开心", "满意", "不错", "挺好"]

        if any(w in query for w in anxiety_words):
            return "焦虑"
        if any(w in query for w in confusion_words):
            return "困惑"
        if any(w in query for w in anger_words):
            return "不满"
        if any(w in query for w in positive_words):
            return "积极"

        return "平静"

    def _extract_focus_points(self, query: str, stage: str) -> List[str]:
        """提取关注重点"""
        focus_keywords = {
            "预算": ["预算", "钱", "费用", "花多少", "贵", "便宜", "省钱"],
            "质量": ["质量", "好不好", "靠谱", "问题", "毛病"],
            "时间": ["多久", "时间", "工期", "什么时候", "快"],
            "选择": ["选", "哪个", "推荐", "建议", "对比"],
            "流程": ["流程", "步骤", "怎么", "如何"],
        }

        focus_points = []
        for focus, keywords in focus_keywords.items():
            if any(kw in query for kw in keywords):
                focus_points.append(focus)

        return focus_points if focus_points else ["一般咨询"]


# ============ 阶段转换检测器 ============

class StageTransitionDetector:
    """阶段转换检测器"""

    def detect_transition(
        self,
        previous_stage: str,
        current_context: StageContext,
        user_type: str = "c_end"
    ) -> Optional[StageTransition]:
        """
        检测用户是否从一个阶段进入另一个阶段

        Args:
            previous_stage: 之前的阶段
            current_context: 当前阶段上下文
            user_type: 用户类型

        Returns:
            StageTransition 如果发生转换，否则 None
        """
        if current_context.stage == previous_stage:
            return None

        # 只有置信度足够高才认为发生了转换
        if current_context.stage_confidence < 0.6:
            return None

        transition_guidance = self._get_transition_guidance(
            previous_stage, current_context.stage, user_type
        )

        return StageTransition(
            from_stage=previous_stage,
            to_stage=current_context.stage,
            confidence=current_context.stage_confidence,
            trigger=current_context.transition_trigger or "用户问题内容变化",
            transition_guidance=transition_guidance,
        )

    def _get_transition_guidance(
        self,
        from_stage: str,
        to_stage: str,
        user_type: str
    ) -> str:
        """获取阶段转换引导"""
        transitions = C_END_STAGE_TRANSITIONS if user_type == "c_end" else B_END_STAGE_TRANSITIONS
        return transitions.get((from_stage, to_stage), f"您已进入{to_stage}阶段，有什么可以帮您的？")


# ============ 专家角色管理器 ============

class ExpertRoleManager:
    """专家角色管理器"""

    def __init__(self):
        self.c_end_experts = self._build_c_end_experts()
        self.b_end_experts = self._build_b_end_experts()

    def _build_c_end_experts(self) -> Dict[str, ExpertRole]:
        """构建C端专家角色"""
        experts = {}
        role_info = {
            "准备": ("装修规划师", "帮用户建立正确认知，避免入坑", "从全局视角规划，预见潜在问题"),
            "设计": ("设计顾问", "帮用户做出明智的设计决策", "从专业角度评估方案优劣"),
            "施工": ("工程监理", "帮用户把控施工质量", "从工艺标准角度发现问题"),
            "软装": ("软装搭配师", "帮用户打造理想的家", "从美学和实用角度给建议"),
            "入住": ("居家顾问", "帮用户安心入住", "从健康和维护角度给指导"),
        }

        for stage, (name, value, perspective) in role_info.items():
            experts[stage] = ExpertRole(
                name=name,
                stage=stage,
                core_value=value,
                professional_perspective=perspective,
                system_prompt=C_END_EXPERT_PROMPTS.get(stage, ""),
            )

        return experts

    def _build_b_end_experts(self) -> Dict[str, ExpertRole]:
        """构建B端专家角色"""
        experts = {}
        role_info = {
            "入驻": ("商业顾问", "帮商家评估入驻价值", "从投资回报角度分析"),
            "获客": ("营销专家", "帮商家高效获取客户", "从转化漏斗角度优化"),
            "经营分析": ("数据分析师", "帮商家发现增长机会", "从数据洞察角度诊断"),
            "核销结算": ("财务顾问", "帮商家理清资金流", "从财务合规角度解答"),
        }

        for stage, (name, value, perspective) in role_info.items():
            experts[stage] = ExpertRole(
                name=name,
                stage=stage,
                core_value=value,
                professional_perspective=perspective,
                system_prompt=B_END_EXPERT_PROMPTS.get(stage, ""),
            )

        return experts

    def get_expert_role(self, stage: str, user_type: str = "c_end") -> Optional[ExpertRole]:
        """获取指定阶段的专家角色"""
        experts = self.c_end_experts if user_type == "c_end" else self.b_end_experts
        return experts.get(stage)

    def get_expert_prompt(self, stage: str, user_type: str = "c_end") -> str:
        """获取专家角色的系统提示词"""
        role = self.get_expert_role(stage, user_type)
        if role:
            return role.system_prompt
        return ""

    def get_all_experts(self, user_type: str = "c_end") -> Dict[str, ExpertRole]:
        """获取所有专家角色"""
        return self.c_end_experts if user_type == "c_end" else self.b_end_experts


# ============ 阶段感知推理引擎 ============

class StageAwareReasoning:
    """阶段感知推理引擎"""

    def __init__(self, llm_caller=None):
        self.stage_understanding = StageUnderstanding(llm_caller)
        self.transition_detector = StageTransitionDetector()
        self.expert_manager = ExpertRoleManager()

    def set_llm_caller(self, llm_caller):
        """设置LLM调用函数"""
        self.stage_understanding.set_llm_caller(llm_caller)

    async def analyze_and_get_expert(
        self,
        query: str,
        conversation_history: List[dict],
        user_profile: dict,
        previous_stage: str = None,
        user_type: str = "c_end"
    ) -> Tuple[StageContext, ExpertRole, Optional[StageTransition]]:
        """
        分析用户阶段并获取对应专家角色

        Args:
            query: 用户问题
            conversation_history: 对话历史
            user_profile: 用户画像
            previous_stage: 之前的阶段
            user_type: 用户类型

        Returns:
            (阶段上下文, 专家角色, 阶段转换信息)
        """
        # 1. 理解用户阶段
        context = await self.stage_understanding.understand_user_context(
            query, conversation_history, user_profile, user_type
        )

        # 2. 获取专家角色
        expert = self.expert_manager.get_expert_role(context.stage, user_type)

        # 3. 检测阶段转换
        transition = None
        if previous_stage and previous_stage != context.stage:
            transition = self.transition_detector.detect_transition(
                previous_stage, context, user_type
            )

        return context, expert, transition

    def get_expert_system_prompt(
        self,
        stage: str,
        user_type: str = "c_end",
        context: StageContext = None
    ) -> str:
        """
        获取专家系统提示词（可根据上下文定制）

        Args:
            stage: 阶段
            user_type: 用户类型
            context: 阶段上下文（可选，用于定制提示词）

        Returns:
            系统提示词
        """
        base_prompt = self.expert_manager.get_expert_prompt(stage, user_type)

        if context:
            # 根据上下文添加额外指导
            additions = []

            if context.emotional_state == "焦虑":
                additions.append("\n## 特别注意\n用户当前比较焦虑，请先安抚情绪，再给出建议。语气要温和、有耐心。")
            elif context.emotional_state == "困惑":
                additions.append("\n## 特别注意\n用户当前比较困惑，请用简单易懂的语言解释，避免专业术语。")
            elif context.emotional_state == "不满":
                additions.append("\n## 特别注意\n用户当前有不满情绪，请先表示理解，再帮助分析问题和解决方案。")

            if context.focus_points:
                additions.append(f"\n## 用户关注重点\n{', '.join(context.focus_points)}")

            if context.potential_needs:
                additions.append(f"\n## 可能的潜在需求\n{', '.join(context.potential_needs)}")

            if additions:
                base_prompt += "\n" + "\n".join(additions)

        return base_prompt


# ============ 全局实例 ============

_stage_reasoning: Optional[StageAwareReasoning] = None


def get_stage_reasoning(llm=None) -> StageAwareReasoning:
    """
    获取全局阶段感知推理引擎

    Args:
        llm: 可选的 LLM 实例（如 ChatTongyi），传入后自动创建 llm_caller 包装函数
    """
    global _stage_reasoning
    if _stage_reasoning is None:
        llm_caller = None
        if llm is not None:
            async def _llm_caller(prompt: str) -> str:
                response = await llm.ainvoke(prompt)
                return response.content if hasattr(response, 'content') else str(response)
            llm_caller = _llm_caller
        _stage_reasoning = StageAwareReasoning(llm_caller=llm_caller)
    elif llm is not None and _stage_reasoning.stage_understanding.llm_caller is None:
        # 实例已存在但尚未设置 llm_caller，补充设置
        async def _llm_caller(prompt: str) -> str:
            response = await llm.ainvoke(prompt)
            return response.content if hasattr(response, 'content') else str(response)
        _stage_reasoning.set_llm_caller(_llm_caller)
    return _stage_reasoning
