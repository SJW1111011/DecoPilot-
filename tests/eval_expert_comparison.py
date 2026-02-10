"""
专家角色 A/B 对比工具

对同一个用户问题，分别用"通用装修顾问"和"阶段专家"生成回答，并排展示对比。

用法:
    python tests/eval_expert_comparison.py                    # 运行所有对比测试
    python tests/eval_expert_comparison.py --case 0           # 只运行第0个测试
    python tests/eval_expert_comparison.py --custom "你的问题"  # 自定义问题
"""
import os
import sys
import asyncio
import argparse
import time

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.core.stage_reasoning import (
    StageAwareReasoning, StageContext, ExpertRole,
)


# ============ 对比测试用例 ============

COMPARISON_CASES = [
    {
        "query": "瓷砖贴完发现有空鼓，工人说没问题",
        "description": "施工质量问题 — 空鼓",
    },
    {
        "query": "我家120平，预算20万，不知道从哪开始",
        "description": "准备阶段 — 新手入门",
    },
    {
        "query": "设计师给了两个方案，一个现代简约一个北欧风，不知道选哪个",
        "description": "设计阶段 — 方案选择",
    },
    {
        "query": "客厅沙发选什么颜色好，墙是白色的，地板是浅木色",
        "description": "软装阶段 — 颜色搭配",
    },
    {
        "query": "装修完3个月了，测了甲醛0.12，能住吗",
        "description": "入住阶段 — 甲醛问题",
    },
    {
        "query": "防水做完了，闭水试验要做多久？楼下说有点渗水",
        "description": "施工阶段 — 防水验收",
    },
    {
        "query": "最近转化率从15%降到8%了，不知道哪里出了问题",
        "description": "B端获客 — 转化率下降",
    },
    {
        "query": "我是做全屋定制的，想了解入驻条件和费用",
        "description": "B端入驻 — 入驻咨询",
    },
]


# ============ 通用系统提示词 ============

GENERIC_SYSTEM_PROMPT = """你是一个专业的装修顾问，请基于你的专业知识回答用户问题。
如果涉及具体数据或标准，请尽量给出准确信息。
回答要实用、具体、有可操作性。"""

GENERIC_B_END_PROMPT = """你是一个平台商家助手，帮助商家解答经营相关问题。
回答要专业、务实，注重数据和效果。"""


# ============ 对比引擎 ============

async def generate_response(llm, system_prompt: str, query: str) -> str:
    """使用指定的系统提示词生成回答"""
    from langchain_core.messages import SystemMessage, HumanMessage

    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=query),
    ]

    response = await llm.ainvoke(messages)
    return response.content if hasattr(response, 'content') else str(response)


async def run_comparison(llm, reasoning: StageAwareReasoning, query: str,
                         description: str, index: int):
    """运行单个对比测试"""
    width = 70

    # 1. 阶段分析
    user_type = "b_end" if "转化率" in query or "入驻" in query or "获客" in query else "c_end"

    context, expert, transition = await reasoning.analyze_and_get_expert(
        query=query,
        conversation_history=[],
        user_profile={},
        previous_stage=None,
        user_type=user_type,
    )

    expert_name = expert.name if expert else "通用顾问"
    expert_prompt = expert.system_prompt if expert else ""

    # 如果有专家，获取定制化的提示词（包含情绪、关注点等）
    if expert:
        expert_prompt = reasoning.get_expert_system_prompt(
            stage=context.stage,
            user_type=user_type,
            context=context,
        )

    # 2. 确定通用提示词
    generic_prompt = GENERIC_SYSTEM_PROMPT if user_type == "c_end" else GENERIC_B_END_PROMPT

    # 3. 并行生成两个回答
    generic_response, expert_response = await asyncio.gather(
        generate_response(llm, generic_prompt, query),
        generate_response(llm, expert_prompt, query) if expert_prompt else asyncio.coroutine(lambda: "（无专家提示词）")(),
    )

    # 4. 输出对比结果
    print("\n" + "━" * width)
    print(f"📋 测试 #{index}: {description}")
    print(f"🎯 检测阶段: {context.stage} (置信度: {context.stage_confidence:.0%})")
    print(f"👤 专家角色: {expert_name}")
    if context.emotional_state and context.emotional_state != "平静":
        print(f"💭 用户情绪: {context.emotional_state}")
    if context.focus_points:
        print(f"🔍 关注重点: {', '.join(context.focus_points)}")
    print(f"\n💬 用户问题: {query}")

    print(f"\n{'─' * width}")
    print(f"【通用装修顾问的回答】")
    print(f"{'─' * width}")
    print(generic_response)

    print(f"\n{'─' * width}")
    print(f"【{expert_name}的回答】")
    print(f"{'─' * width}")
    print(expert_response)

    print("━" * width)

    return {
        "query": query,
        "description": description,
        "stage": context.stage,
        "confidence": context.stage_confidence,
        "expert": expert_name,
        "generic_length": len(generic_response),
        "expert_length": len(expert_response),
    }


# ============ 主函数 ============

async def run_all_comparisons(cases: list, case_index: int = None):
    """运行所有对比测试"""
    try:
        from langchain_community.chat_models import ChatTongyi
    except ImportError:
        print("❌ 需要安装 langchain-community: pip install langchain-community")
        return

    print("\n🔧 初始化 LLM...")
    try:
        llm = ChatTongyi(model="qwen-plus", temperature=0.7)
        # 创建 llm_caller 包装
        async def _llm_caller(prompt: str) -> str:
            response = await llm.ainvoke(prompt)
            return response.content if hasattr(response, 'content') else str(response)

        reasoning = StageAwareReasoning(llm_caller=_llm_caller)
        print("✅ LLM 初始化成功 (qwen-plus)")
    except Exception as e:
        print(f"❌ LLM 初始化失败: {e}")
        print("请确保设置了 DASHSCOPE_API_KEY 环境变量")
        return

    # 选择要运行的用例
    if case_index is not None:
        if 0 <= case_index < len(cases):
            cases_to_run = [(case_index, cases[case_index])]
        else:
            print(f"❌ 无效的用例索引: {case_index} (共 {len(cases)} 个用例)")
            return
    else:
        cases_to_run = list(enumerate(cases))

    print(f"\n📊 共 {len(cases_to_run)} 个对比测试\n")

    start_time = time.time()
    results = []

    for idx, case in cases_to_run:
        result = await run_comparison(
            llm, reasoning,
            case["query"], case["description"], idx
        )
        results.append(result)

    duration = time.time() - start_time

    # 打印总结
    if len(results) > 1:
        print("\n" + "━" * 70)
        print("📊 对比总结")
        print("━" * 70)
        print(f"\n  ⏱️  总耗时: {duration:.1f}s")
        print(f"  📝 测试数量: {len(results)}")

        avg_generic_len = sum(r["generic_length"] for r in results) / len(results)
        avg_expert_len = sum(r["expert_length"] for r in results) / len(results)
        print(f"\n  通用回答平均长度: {avg_generic_len:.0f} 字")
        print(f"  专家回答平均长度: {avg_expert_len:.0f} 字")
        print(f"  专家回答长度比: {avg_expert_len / avg_generic_len:.1%}")

        print(f"\n  阶段分布:")
        stage_counts = {}
        for r in results:
            stage_counts[r["stage"]] = stage_counts.get(r["stage"], 0) + 1
        for stage, count in sorted(stage_counts.items(), key=lambda x: -x[1]):
            print(f"    {stage}: {count} 个")

        avg_confidence = sum(r["confidence"] for r in results) / len(results)
        print(f"\n  平均置信度: {avg_confidence:.0%}")
        print("\n" + "━" * 70)


def main():
    parser = argparse.ArgumentParser(description="专家角色 A/B 对比工具")
    parser.add_argument(
        "--case",
        type=int,
        default=None,
        help="只运行指定索引的测试用例",
    )
    parser.add_argument(
        "--custom",
        type=str,
        default=None,
        help="自定义测试问题",
    )
    args = parser.parse_args()

    print("\n🔬 专家角色 A/B 对比工具")
    print("=" * 70)
    print("对同一问题，对比「通用顾问」vs「阶段专家」的回答质量差异")

    cases = COMPARISON_CASES[:]

    if args.custom:
        cases = [{"query": args.custom, "description": "自定义问题"}]
        asyncio.run(run_all_comparisons(cases))
    else:
        asyncio.run(run_all_comparisons(cases, args.case))


if __name__ == "__main__":
    main()
