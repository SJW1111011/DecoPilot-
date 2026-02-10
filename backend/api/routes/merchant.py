"""
商家API路由
提供商家推荐、补贴计算等接口
"""
import os
import sys
from typing import Optional, List

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

from backend.agents.c_end_agent import CEndAgent
from backend.agents.b_end_agent import BEndAgent
from backend.config.business_rules import SUBSIDY_RULES
from backend.core.output_formatter import (
    SubsidyResult, MerchantCard, TableData,
    create_subsidy_result
)

# 导入异步工具
try:
    from backend.core.async_utils import get_async_executor
    ASYNC_UTILS_AVAILABLE = True
except ImportError:
    ASYNC_UTILS_AVAILABLE = False

router = APIRouter(prefix="/merchant", tags=["商家服务"])


class SubsidyCalcRequest(BaseModel):
    """补贴计算请求模型"""
    order_amount: float
    category: str


class SubsidyCalcResponse(BaseModel):
    """补贴计算响应模型"""
    order_amount: float
    category: str
    subsidy_rate: float
    calculated_subsidy: float
    max_subsidy: float
    actual_subsidy: float
    note: str


class MerchantRecommendRequest(BaseModel):
    """商家推荐请求模型"""
    category: str
    budget: Optional[float] = None
    style: Optional[str] = None
    limit: int = 5


class ROIAnalysisRequest(BaseModel):
    """ROI分析请求模型"""
    investment: float
    revenue: float
    period_days: int = 30


class CustomerScriptRequest(BaseModel):
    """获客话术请求模型"""
    scenario: str  # 首次接触/跟进/促单
    product_category: str


# 延迟加载智能体
_c_end_agent = None
_b_end_agent = None


def get_c_end_agent():
    global _c_end_agent
    if _c_end_agent is None:
        _c_end_agent = CEndAgent()
    return _c_end_agent


def get_b_end_agent():
    global _b_end_agent
    if _b_end_agent is None:
        _b_end_agent = BEndAgent()
    return _b_end_agent


# ============ C端接口 ============

@router.post("/recommend")
async def recommend_merchants(request: MerchantRecommendRequest):
    """
    商家推荐接口

    根据用户需求推荐合适的商家
    """
    agent = get_c_end_agent()

    # 使用线程池执行可能阻塞的操作
    if ASYNC_UTILS_AVAILABLE:
        executor = get_async_executor()
        merchants = await executor.run_in_thread(
            agent.recommend_merchants,
            category=request.category,
            budget=request.budget,
            style=request.style,
            limit=request.limit,
        )
    else:
        merchants = agent.recommend_merchants(
            category=request.category,
            budget=request.budget,
            style=request.style,
            limit=request.limit,
        )

    return {
        "category": request.category,
        "budget": request.budget,
        "style": request.style,
        "merchants": merchants,
    }


# ============ 补贴接口 ============

@router.get("/subsidy/rules")
async def get_subsidy_rules():
    """
    获取补贴规则

    返回各品类的补贴比例和上限
    """
    # 从配置获取补贴规则
    rules = {}
    for category, rule in SUBSIDY_RULES.items():
        rules[category] = {
            "rate": rule["rate"],
            "max": rule["max"],
            "description": rule["description"],
        }

    # 构建表格数据
    table = TableData(
        title="洞居平台补贴规则",
        headers=["品类", "补贴比例", "单笔上限", "说明"],
        rows=[
            [cat, f"{r['rate']*100:.0f}%", f"{r['max']}元", r["description"]]
            for cat, r in rules.items()
        ],
        footer="每月补贴领取上限：5000元",
    )

    return {
        "rules": rules,
        "table": {
            "title": table.title,
            "headers": table.headers,
            "rows": table.rows,
            "footer": table.footer,
        },
        "monthly_limit": 5000,
        "note": "以上规则仅供参考，实际补贴以平台规则为准",
    }


@router.post("/subsidy/calc")
async def calculate_subsidy(request: SubsidyCalcRequest):
    """
    计算补贴金额

    根据订单金额和品类计算预估补贴
    """
    if request.order_amount <= 0:
        raise HTTPException(status_code=400, detail="订单金额必须大于0")

    # 从配置获取补贴规则
    category = request.category
    if category not in SUBSIDY_RULES:
        raise HTTPException(
            status_code=400,
            detail=f"不支持的品类: {category}，支持的品类: {', '.join(SUBSIDY_RULES.keys())}"
        )

    rule = SUBSIDY_RULES[category]
    result = create_subsidy_result(
        category=category,
        amount=request.order_amount,
        rate=rule["rate"],
        max_limit=rule["max"],
    )

    return {
        "order_amount": result.original_amount,
        "category": result.category,
        "subsidy_rate": result.subsidy_rate,
        "calculated_subsidy": result.calculated_amount,
        "max_subsidy": result.max_limit,
        "actual_subsidy": result.final_amount,
        "explanation": result.explanation,
        "note": "实际补贴以平台规则为准",
    }


# ============ B端接口 ============

@router.post("/roi/analyze")
async def analyze_roi(request: ROIAnalysisRequest):
    """
    ROI分析接口

    分析商家的投入产出比
    """
    if request.investment <= 0:
        raise HTTPException(status_code=400, detail="投入金额必须大于0")

    agent = get_b_end_agent()

    # 使用线程池执行可能阻塞的操作
    if ASYNC_UTILS_AVAILABLE:
        executor = get_async_executor()
        result = await executor.run_in_thread(
            agent.analyze_roi,
            investment=request.investment,
            revenue=request.revenue,
            period_days=request.period_days,
        )
    else:
        result = agent.analyze_roi(
            investment=request.investment,
            revenue=request.revenue,
            period_days=request.period_days,
        )

    return result


@router.post("/script/generate")
async def generate_customer_script(request: CustomerScriptRequest):
    """
    生成获客话术

    根据场景和产品品类生成话术建议
    """
    valid_scenarios = ["首次接触", "跟进", "促单"]
    if request.scenario not in valid_scenarios:
        raise HTTPException(
            status_code=400,
            detail=f"场景必须是以下之一: {', '.join(valid_scenarios)}"
        )

    agent = get_b_end_agent()

    # 使用线程池执行可能阻塞的操作
    if ASYNC_UTILS_AVAILABLE:
        executor = get_async_executor()
        result = await executor.run_in_thread(
            agent.generate_customer_script,
            scenario=request.scenario,
            product_category=request.product_category,
        )
    else:
        result = agent.generate_customer_script(
            scenario=request.scenario,
            product_category=request.product_category,
        )

    return result


@router.get("/contact-time")
async def get_best_contact_time(customer_type: str = "业主"):
    """
    获取最佳触达时机

    返回联系客户的最佳时间建议
    """
    agent = get_b_end_agent()

    # 使用线程池执行可能阻塞的操作
    if ASYNC_UTILS_AVAILABLE:
        executor = get_async_executor()
        result = await executor.run_in_thread(
            agent.get_best_contact_time, customer_type
        )
    else:
        result = agent.get_best_contact_time(customer_type)

    return result
