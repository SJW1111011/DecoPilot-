"""
阶段感知专家系统 — 端到端评估脚本

用法:
    python tests/eval_stage_expert.py --mode keyword    # 仅关键词匹配（快速，CI用）
    python tests/eval_stage_expert.py --mode llm        # 启用LLM深度分析（需要API key）
    python tests/eval_stage_expert.py --mode all         # 两种模式都跑
"""
import os
import sys
import asyncio
import argparse
import time
from typing import List, Tuple, Optional, Dict

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.core.stage_reasoning import (
    StageAwareReasoning, StageUnderstanding, StageTransitionDetector,
    ExpertRoleManager, StageContext, ExpertRole, StageTransition,
)


# ============ C端测试用例 ============

C_END_CASES = [
    # (用户输入, 预期阶段, 预期专家角色, 说明)
    ("我家120平，预算20万，不知道从哪开始", "准备", "装修规划师", "典型准备阶段"),
    ("设计师给了两个方案，不知道选哪个", "设计", "设计顾问", "设计决策困难"),
    ("瓷砖贴完发现有空鼓，工人说没问题", "施工", "工程监理", "施工质量问题"),
    ("客厅沙发选什么颜色好", "软装", "软装搭配师", "软装搭配"),
    ("装修完多久可以入住", "入住", "居家顾问", "入住咨询"),
    # 模糊/边界案例
    ("我想装修但不知道要花多少钱", "准备", "装修规划师", "隐含准备阶段"),
    ("防水做了但不确定合不合格", "施工", "工程监理", "施工验收"),
    ("窗帘和沙发颜色搭不搭", "软装", "软装搭配师", "搭配问题"),
    # 更多覆盖
    ("刚买房，准备装修，不知道从哪入手", "准备", "装修规划师", "新房准备"),
    ("全包半包怎么选", "准备", "装修规划师", "装修方式选择"),
    ("效果图出来了，感觉不太满意", "设计", "设计顾问", "设计方案评估"),
    ("报价单看不懂，感觉有些项目贵了", "设计", "设计顾问", "报价审核"),
    ("水电改造完了，需要验收吗", "施工", "工程监理", "水电验收"),
    ("工人刷漆刷得不均匀怎么办", "施工", "工程监理", "油漆质量"),
    ("灯具选什么样的好看", "软装", "软装搭配师", "灯具选择"),
    ("甲醛超标怎么办", "入住", "居家顾问", "甲醛问题"),
    ("搬家后发现墙面有裂缝", "入住", "居家顾问", "入住后问题"),
]

# ============ B端测试用例 ============

B_END_CASES = [
    ("我是做全屋定制的，想了解入驻条件", "入驻", "商业顾问", "入驻咨询"),
    ("最近转化率下降了，怎么办", "获客", "营销专家", "获客问题"),
    ("我的ROI是多少，怎么提升", "经营分析", "数据分析师", "数据分析"),
    ("这个月的结算什么时候到账", "核销结算", "财务顾问", "结算问题"),
    # 更多覆盖
    ("入驻需要什么资质", "入驻", "商业顾问", "资质咨询"),
    ("保证金多少钱，能退吗", "入驻", "商业顾问", "费用���询"),
    ("客户咨询了但不回复怎么办", "获客", "营销专家", "客户跟进"),
    ("怎么写首次接触客户的话术", "获客", "营销专家", "话术生成"),
    ("转化漏斗哪个环节流失最多", "经营分析", "数据分析师", "漏斗分析"),
    ("佣金怎么算的", "核销结算", "财务顾问", "佣金计算"),
    ("退款后结算金额会变吗", "核销结算", "财务顾问", "退款结算"),
]

# ============ 阶段转换测试用例 ============

TRANSITION_CASES = [
    {
        "name": "设计→施工转换",
        "user_type": "c_end",
        "turns": [
            {"query": "我在看设计方案", "expected_stage": "设计"},
            {"query": "设计定了，下周开工，有什么要注意的？", "expected_stage": "施工"},
        ],
        "expected_transition": ("设计", "施工"),
    },
    {
        "name": "准备→设计转换",
        "user_type": "c_end",
        "turns": [
            {"query": "我打算装修，预算20万", "expected_stage": "准备"},
            {"query": "设计师来量房了，出了效果图", "expected_stage": "设计"},
        ],
        "expected_transition": ("准备", "设计"),
    },
    {
        "name": "施工→软装转换",
        "user_type": "c_end",
        "turns": [
            {"query": "工人在贴瓷砖", "expected_stage": "施工"},
            {"query": "硬装完了，该买家具了", "expected_stage": "软装"},
        ],
        "expected_transition": ("施工", "软装"),
    },
    {
        "name": "入驻→获客转换",
        "user_type": "b_end",
        "turns": [
            {"query": "我刚入驻平台", "expected_stage": "入驻"},
            {"query": "店铺开好了，怎么找客户", "expected_stage": "获客"},
        ],
        "expected_transition": ("入驻", "获客"),
    },
]


# ============ 评估引擎 ============

class EvalResult:
    """单个测试用例的评估结果"""
    def __init__(self, query: str, expected_stage: str, expected_expert: str,
                 actual_stage: str, actual_expert: str, confidence: float,
                 description: str, passed: bool):
        self.query = query
        self.expected_stage = expected_stage
        self.expected_expert = expected_expert
        self.actual_stage = actual_stage
        self.actual_expert = actual_expert
        self.confidence = confidence
        self.description = description
        self.passed = passed


class TransitionResult:
    """阶段转换测试结果"""
    def __init__(self, name: str, expected_transition: tuple,
                 actual_transition: Optional[tuple], passed: bool,
                 turn_results: List[dict]):
        self.name = name
        self.expected_transition = expected_transition
        self.actual_transition = actual_transition
        self.passed = passed
        self.turn_results = turn_results


async def evaluate_single_case(
    reasoning: StageAwareReasoning,
    query: str,
    expected_stage: str,
    expected_expert: str,
    description: str,
    user_type: str = "c_end",
) -> EvalResult:
    """评估单个测试用例"""
    context, expert, transition = await reasoning.analyze_and_get_expert(
        query=query,
        conversation_history=[],
        user_profile={},
        previous_stage=None,
        user_type=user_type,
    )

    actual_stage = context.stage
    actual_expert = expert.name if expert else "无"
    confidence = context.stage_confidence

    stage_match = actual_stage == expected_stage
    expert_match = actual_expert == expected_expert
    passed = stage_match and expert_match

    return EvalResult(
        query=query,
        expected_stage=expected_stage,
        expected_expert=expected_expert,
        actual_stage=actual_stage,
        actual_expert=actual_expert,
        confidence=confidence,
        description=description,
        passed=passed,
    )


async def evaluate_transition_case(
    reasoning: StageAwareReasoning,
    case: dict,
) -> TransitionResult:
    """评估阶段转换测试用例"""
    user_type = case["user_type"]
    turns = case["turns"]
    expected_transition = case["expected_transition"]

    previous_stage = None
    actual_transition = None
    turn_results = []

    for turn in turns:
        context, expert, transition = await reasoning.analyze_and_get_expert(
            query=turn["query"],
            conversation_history=[],
            user_profile={},
            previous_stage=previous_stage,
            user_type=user_type,
        )

        turn_result = {
            "query": turn["query"],
            "expected_stage": turn["expected_stage"],
            "actual_stage": context.stage,
            "confidence": context.stage_confidence,
            "stage_match": context.stage == turn["expected_stage"],
        }
        turn_results.append(turn_result)

        if transition:
            actual_transition = (transition.from_stage, transition.to_stage)

        previous_stage = context.stage

    passed = actual_transition == expected_transition

    return TransitionResult(
        name=case["name"],
        expected_transition=expected_transition,
        actual_transition=actual_transition,
        passed=passed,
        turn_results=turn_results,
    )


# ============ 报告生成 ============

def print_header(title: str):
    """打印报告标题"""
    width = 70
    print("\n" + "━" * width)
    print(f"  {title}")
    print("━" * width)


def print_results(results: List[EvalResult], title: str):
    """打印评估结果"""
    print_header(title)

    passed = sum(1 for r in results if r.passed)
    total = len(results)
    accuracy = passed / total * 100 if total > 0 else 0

    print(f"\n  📊 准确率: {passed}/{total} ({accuracy:.1f}%)\n")

    # 置信度分布
    confidences = [r.confidence for r in results]
    if confidences:
        avg_conf = sum(confidences) / len(confidences)
        min_conf = min(confidences)
        max_conf = max(confidences)
        print(f"  📈 置信度: 平均 {avg_conf:.0%} | 最低 {min_conf:.0%} | 最高 {max_conf:.0%}\n")

    # 详细结果
    for r in results:
        status = "✅" if r.passed else "❌"
        print(f"  {status} [{r.description}]")
        print(f"     输入: {r.query[:50]}...")
        if r.passed:
            print(f"     阶段: {r.actual_stage} | 专家: {r.actual_expert} | 置信度: {r.confidence:.0%}")
        else:
            print(f"     期望: {r.expected_stage}/{r.expected_expert}")
            print(f"     实际: {r.actual_stage}/{r.actual_expert} | 置信度: {r.confidence:.0%}")
        print()

    return accuracy


def print_transition_results(results: List[TransitionResult]):
    """打印阶段转换评估结果"""
    print_header("阶段转换检测评估")

    passed = sum(1 for r in results if r.passed)
    total = len(results)
    accuracy = passed / total * 100 if total > 0 else 0

    print(f"\n  📊 准确率: {passed}/{total} ({accuracy:.1f}%)\n")

    for r in results:
        status = "✅" if r.passed else "❌"
        print(f"  {status} {r.name}")
        print(f"     期望转换: {r.expected_transition[0]} → {r.expected_transition[1]}")
        if r.actual_transition:
            print(f"     实际转换: {r.actual_transition[0]} → {r.actual_transition[1]}")
        else:
            print(f"     实际转换: 未检测到")

        for turn in r.turn_results:
            turn_status = "✓" if turn["stage_match"] else "✗"
            print(f"       {turn_status} \"{turn['query'][:40]}\" → {turn['actual_stage']} (期望: {turn['expected_stage']}, 置信度: {turn['confidence']:.0%})")
        print()

    return accuracy


def print_summary(c_end_acc: float, b_end_acc: float, transition_acc: float, mode: str, duration: float):
    """打印总结"""
    print_header("评估总结")
    print(f"\n  🔧 模式: {mode}")
    print(f"  ⏱️  耗时: {duration:.2f}s")
    print(f"\n  C端阶段检测准确率: {c_end_acc:.1f}%")
    print(f"  B端阶段检测准确率: {b_end_acc:.1f}%")
    print(f"  阶段转换检测准确率: {transition_acc:.1f}%")

    overall = (c_end_acc + b_end_acc + transition_acc) / 3
    print(f"\n  📊 综合准确率: {overall:.1f}%")

    if overall >= 80:
        print("\n  🎉 系统表现良好！")
    elif overall >= 60:
        print("\n  ⚠️  系统表现一般，建议优化关键词匹配或启用LLM分析")
    else:
        print("\n  ❌ 系统表现较差，需要检查阶段检测逻辑")

    print("\n" + "━" * 70)


# ============ 主函数 ============

async def run_evaluation(mode: str = "keyword"):
    """运行评估"""
    start_time = time.time()

    # 创建推理引擎
    llm_caller = None
    if mode == "llm":
        try:
            from langchain_community.chat_models import ChatTongyi
            llm = ChatTongyi(model="qwen-plus", temperature=0.3)

            async def _llm_caller(prompt: str) -> str:
                response = await llm.ainvoke(prompt)
                return response.content if hasattr(response, 'content') else str(response)

            llm_caller = _llm_caller
            print("  ✅ LLM已启用 (qwen-plus)")
        except Exception as e:
            print(f"  ⚠️  LLM初始化失败: {e}")
            print("  回退到关键词模式")
            mode = "keyword"

    reasoning = StageAwareReasoning(llm_caller=llm_caller)

    # C端评估
    c_end_results = []
    for query, expected_stage, expected_expert, desc in C_END_CASES:
        result = await evaluate_single_case(
            reasoning, query, expected_stage, expected_expert, desc, "c_end"
        )
        c_end_results.append(result)

    c_end_acc = print_results(c_end_results, "C端阶段检测评估")

    # B端评估
    b_end_results = []
    for query, expected_stage, expected_expert, desc in B_END_CASES:
        result = await evaluate_single_case(
            reasoning, query, expected_stage, expected_expert, desc, "b_end"
        )
        b_end_results.append(result)

    b_end_acc = print_results(b_end_results, "B端阶段检测评估")

    # 阶段转换评估
    transition_results = []
    for case in TRANSITION_CASES:
        result = await evaluate_transition_case(reasoning, case)
        transition_results.append(result)

    transition_acc = print_transition_results(transition_results)

    # 总结
    duration = time.time() - start_time
    print_summary(c_end_acc, b_end_acc, transition_acc, mode, duration)


def main():
    parser = argparse.ArgumentParser(description="阶段感知专家系统评估脚本")
    parser.add_argument(
        "--mode",
        choices=["keyword", "llm", "all"],
        default="keyword",
        help="评估模式: keyword(仅关键词), llm(启用LLM), all(两种都跑)",
    )
    args = parser.parse_args()

    print("\n🔍 阶段感知专家系统 — 端到端评估")
    print("=" * 70)

    if args.mode == "all":
        print("\n📋 模式: keyword (关键词匹配)")
        asyncio.run(run_evaluation("keyword"))
        print("\n\n📋 模式: llm (LLM深度分析)")
        asyncio.run(run_evaluation("llm"))
    else:
        print(f"\n📋 模式: {args.mode}")
        asyncio.run(run_evaluation(args.mode))


if __name__ == "__main__":
    main()
