"""
高级推理系统
支持思维链(CoT)、多步推理、自我反思和规划能力
"""
import json
import time
from typing import Any, Dict, List, Optional, Callable, Tuple
from dataclasses import dataclass, field
from enum import Enum
from abc import ABC, abstractmethod


class ReasoningType(str, Enum):
    """推理类型"""
    DIRECT = "direct"              # 直接回答
    CHAIN_OF_THOUGHT = "cot"       # 思维链
    MULTI_STEP = "multi_step"      # 多步推理
    TREE_OF_THOUGHT = "tot"        # 思维树
    SELF_REFLECTION = "reflection" # 自我反思


class TaskComplexity(str, Enum):
    """任务复杂度"""
    SIMPLE = "simple"       # 简单问答
    MODERATE = "moderate"   # 中等复杂
    COMPLEX = "complex"     # 复杂推理
    EXPERT = "expert"       # 专家级


@dataclass
class ReasoningStep:
    """推理步骤"""
    step_id: int
    step_type: str           # think/act/observe/reflect
    content: str
    confidence: float = 0.0
    timestamp: float = field(default_factory=time.time)
    metadata: Dict = field(default_factory=dict)


@dataclass
class ReasoningChain:
    """推理链"""
    chain_id: str
    query: str
    reasoning_type: ReasoningType
    steps: List[ReasoningStep] = field(default_factory=list)
    final_answer: Optional[str] = None
    confidence: float = 0.0
    start_time: float = field(default_factory=time.time)
    end_time: Optional[float] = None

    def add_step(self, step_type: str, content: str,
                 confidence: float = 0.0, metadata: Dict = None):
        """添加推理步骤"""
        step = ReasoningStep(
            step_id=len(self.steps) + 1,
            step_type=step_type,
            content=content,
            confidence=confidence,
            metadata=metadata or {}
        )
        self.steps.append(step)
        return step

    def get_thinking_log(self) -> List[str]:
        """获取思考日志"""
        logs = []
        for step in self.steps:
            prefix = {
                "think": "💭 思考",
                "act": "🔧 执行",
                "observe": "👁️ 观察",
                "reflect": "🔄 反思",
                "plan": "📋 规划",
                "verify": "✅ 验证",
            }.get(step.step_type, "📝")
            logs.append(f"{prefix}: {step.content}")
        return logs


@dataclass
class Plan:
    """执行计划"""
    plan_id: str
    goal: str
    steps: List[Dict] = field(default_factory=list)
    current_step: int = 0
    status: str = "pending"  # pending/executing/completed/failed

    def add_step(self, action: str, expected_result: str,
                 tools: List[str] = None):
        """添加计划步骤"""
        self.steps.append({
            "step_id": len(self.steps) + 1,
            "action": action,
            "expected_result": expected_result,
            "tools": tools or [],
            "status": "pending",
            "actual_result": None,
        })

    def next_step(self) -> Optional[Dict]:
        """获取下一步"""
        if self.current_step < len(self.steps):
            return self.steps[self.current_step]
        return None

    def complete_step(self, result: str, success: bool = True):
        """完成当前步骤"""
        if self.current_step < len(self.steps):
            self.steps[self.current_step]["actual_result"] = result
            self.steps[self.current_step]["status"] = "completed" if success else "failed"
            self.current_step += 1


class TaskAnalyzer:
    """任务分析器"""

    # 复杂任务关键词
    COMPLEX_KEYWORDS = [
        "比较", "对比", "分析", "评估", "规划", "设计",
        "如何", "为什么", "怎么办", "应该",
        "多少钱", "预算", "报价", "计算",
        "推荐", "建议", "选择",
    ]

    # 简单任务关键词
    SIMPLE_KEYWORDS = [
        "是什么", "什么是", "定义", "解释",
        "在哪", "哪里", "地址", "电话",
        "营业时间", "开放时间",
    ]

    @classmethod
    def analyze_complexity(cls, query: str) -> TaskComplexity:
        """分析任务复杂度"""
        query_lower = query.lower()

        # 检查复杂关键词
        complex_count = sum(1 for kw in cls.COMPLEX_KEYWORDS if kw in query)
        simple_count = sum(1 for kw in cls.SIMPLE_KEYWORDS if kw in query)

        # 检查问题长度
        length_factor = len(query) / 50  # 50字为基准

        # 检查是否包含多个问题
        question_marks = query.count("？") + query.count("?")

        # 综合评分
        score = complex_count * 2 - simple_count + length_factor + question_marks

        if score <= 1:
            return TaskComplexity.SIMPLE
        elif score <= 3:
            return TaskComplexity.MODERATE
        elif score <= 5:
            return TaskComplexity.COMPLEX
        else:
            return TaskComplexity.EXPERT

    @classmethod
    def select_reasoning_type(cls, query: str,
                               complexity: TaskComplexity) -> ReasoningType:
        """选择推理类型"""
        if complexity == TaskComplexity.SIMPLE:
            return ReasoningType.DIRECT
        elif complexity == TaskComplexity.MODERATE:
            return ReasoningType.CHAIN_OF_THOUGHT
        elif complexity == TaskComplexity.COMPLEX:
            return ReasoningType.MULTI_STEP
        else:
            return ReasoningType.TREE_OF_THOUGHT

    @classmethod
    def extract_sub_questions(cls, query: str) -> List[str]:
        """提取子问题"""
        sub_questions = []

        # 按标点分割
        separators = ["？", "?", "，", ",", "；", ";", "、"]
        parts = [query]
        for sep in separators:
            new_parts = []
            for part in parts:
                new_parts.extend(part.split(sep))
            parts = new_parts

        # 过滤有效问题
        for part in parts:
            part = part.strip()
            if len(part) > 5:  # 至少5个字符
                sub_questions.append(part)

        return sub_questions if len(sub_questions) > 1 else [query]


class ReasoningEngine:
    """推理引擎"""

    def __init__(self, llm_caller: Callable = None):
        """
        初始化推理引擎

        Args:
            llm_caller: LLM调用函数，签名为 (prompt: str) -> str
        """
        self.llm_caller = llm_caller
        self.chains: Dict[str, ReasoningChain] = {}

    def create_chain(self, query: str,
                     reasoning_type: ReasoningType = None) -> ReasoningChain:
        """创建推理链"""
        chain_id = f"chain_{int(time.time() * 1000)}"

        if reasoning_type is None:
            complexity = TaskAnalyzer.analyze_complexity(query)
            reasoning_type = TaskAnalyzer.select_reasoning_type(query, complexity)

        chain = ReasoningChain(
            chain_id=chain_id,
            query=query,
            reasoning_type=reasoning_type
        )
        self.chains[chain_id] = chain
        return chain

    def think(self, chain: ReasoningChain, thought: str,
              confidence: float = 0.5) -> ReasoningStep:
        """添加思考步骤"""
        return chain.add_step("think", thought, confidence)

    def act(self, chain: ReasoningChain, action: str,
            tool: str = None) -> ReasoningStep:
        """添加执行步骤"""
        return chain.add_step("act", action, metadata={"tool": tool})

    def observe(self, chain: ReasoningChain,
                observation: str) -> ReasoningStep:
        """添加观察步骤"""
        return chain.add_step("observe", observation)

    def reflect(self, chain: ReasoningChain,
                reflection: str, confidence: float = 0.5) -> ReasoningStep:
        """添加反思步骤"""
        return chain.add_step("reflect", reflection, confidence)

    def verify(self, chain: ReasoningChain,
               verification: str, passed: bool) -> ReasoningStep:
        """添加验证步骤"""
        return chain.add_step("verify", verification,
                              confidence=1.0 if passed else 0.0,
                              metadata={"passed": passed})

    def finalize(self, chain: ReasoningChain, answer: str,
                 confidence: float = 0.8):
        """完成推理链"""
        chain.final_answer = answer
        chain.confidence = confidence
        chain.end_time = time.time()

    # === 推理模式实现 ===

    def direct_answer(self, query: str, context: str = "") -> ReasoningChain:
        """直接回答模式"""
        chain = self.create_chain(query, ReasoningType.DIRECT)
        self.think(chain, f"这是一个简单问题，可以直接回答")
        return chain

    def chain_of_thought(self, query: str, context: str = "") -> ReasoningChain:
        """思维链推理"""
        chain = self.create_chain(query, ReasoningType.CHAIN_OF_THOUGHT)

        # 步骤1: 理解问题
        self.think(chain, f"首先理解问题：{query}")

        # 步骤2: 分解问题
        sub_questions = TaskAnalyzer.extract_sub_questions(query)
        if len(sub_questions) > 1:
            self.think(chain, f"问题可以分解为：{', '.join(sub_questions)}")

        # 步骤3: 检索相关信息
        self.act(chain, "检索知识库获取相关信息", tool="knowledge_search")

        # 步骤4: 分析信息
        self.think(chain, "分析检索到的信息，提取关键点")

        # 步骤5: 综合推理
        self.think(chain, "综合以上信息进行推理")

        return chain

    def multi_step_reasoning(self, query: str,
                              context: str = "") -> ReasoningChain:
        """多步推理"""
        chain = self.create_chain(query, ReasoningType.MULTI_STEP)

        # 步骤1: 问题分析
        self.think(chain, f"分析复杂问题：{query}")

        # 步骤2: 制定计划
        self.think(chain, "制定解决方案的步骤计划")

        # 步骤3: 逐步执行
        sub_questions = TaskAnalyzer.extract_sub_questions(query)
        for i, sub_q in enumerate(sub_questions, 1):
            self.think(chain, f"步骤{i}: 解决子问题 - {sub_q}")
            self.act(chain, f"执行步骤{i}", tool="knowledge_search")
            self.observe(chain, f"步骤{i}的结果")

        # 步骤4: 整合结果
        self.think(chain, "整合各步骤的结果")

        # 步骤5: 验证答案
        self.verify(chain, "验证答案的完整性和准确性", True)

        return chain

    def self_reflection(self, chain: ReasoningChain,
                        initial_answer: str) -> ReasoningChain:
        """自我反思"""
        # 反思1: 检查答案完整性
        self.reflect(chain, "检查答案是否完整回答了用户的问题")

        # 反思2: 检查逻辑一致性
        self.reflect(chain, "检查推理过程是否有逻辑漏洞")

        # 反思3: 检查信息准确性
        self.reflect(chain, "检查引用的信息是否准确")

        # 反思4: 检查是否有遗漏
        self.reflect(chain, "检查是否有重要信息被遗漏")

        return chain

    def create_plan(self, goal: str) -> Plan:
        """创建执行计划"""
        plan_id = f"plan_{int(time.time() * 1000)}"
        return Plan(plan_id=plan_id, goal=goal)


# === 推理提示词模板 ===

COT_PROMPT_TEMPLATE = """请使用思维链方法回答以下问题。

问题：{query}

参考信息：
{context}

请按以下步骤思考：
1. 首先理解问题的核心是什么
2. 分析问题涉及哪些方面
3. 从参考信息中提取相关内容
4. 逐步推理得出答案
5. 验证答案的合理性

请在回答中展示你的思考过程。
"""

MULTI_STEP_PROMPT_TEMPLATE = """请使用多步推理方法回答以下复杂问题。

问题：{query}

参考信息：
{context}

请按以下方式处理：
1. 将问题分解为多个子问题
2. 逐一解决每个子问题
3. 整合各子问题的答案
4. 形成完整的最终答案

子问题：
{sub_questions}

请逐步回答每个子问题，然后给出综合答案。
"""

REFLECTION_PROMPT_TEMPLATE = """请对以下回答进行自我反思和改进。

原始问题：{query}

初始回答：{initial_answer}

请检查：
1. 回答是否完整？是否遗漏了重要信息？
2. 推理是否正确？是否有逻辑错误？
3. 信息是否准确？是否需要修正？
4. 表达是否清晰？是否需要改进？

如果发现问题，请提供改进后的回答。
"""


def get_reasoning_prompt(reasoning_type: ReasoningType, query: str,
                         context: str = "", **kwargs) -> str:
    """获取推理提示词"""
    if reasoning_type == ReasoningType.CHAIN_OF_THOUGHT:
        return COT_PROMPT_TEMPLATE.format(query=query, context=context)
    elif reasoning_type == ReasoningType.MULTI_STEP:
        sub_questions = kwargs.get("sub_questions", [query])
        sub_q_text = "\n".join(f"- {q}" for q in sub_questions)
        return MULTI_STEP_PROMPT_TEMPLATE.format(
            query=query, context=context, sub_questions=sub_q_text
        )
    elif reasoning_type == ReasoningType.SELF_REFLECTION:
        initial_answer = kwargs.get("initial_answer", "")
        return REFLECTION_PROMPT_TEMPLATE.format(
            query=query, initial_answer=initial_answer
        )
    else:
        return f"问题：{query}\n\n参考信息：{context}"


# 全局推理引擎实例
_reasoning_engine: Optional[ReasoningEngine] = None


def get_reasoning_engine() -> ReasoningEngine:
    """获取全局推理引擎"""
    global _reasoning_engine
    if _reasoning_engine is None:
        _reasoning_engine = ReasoningEngine()
    return _reasoning_engine
