"""
高级推理系统
支持思维链(CoT)、多步推理、自我反思、思维树(ToT)和ReAct模式
"""
import json
import time
import asyncio
from typing import Any, Dict, List, Optional, Callable, Tuple
from dataclasses import dataclass, field
from enum import Enum
from abc import ABC, abstractmethod
import threading


class ReasoningType(str, Enum):
    """推理类型"""
    DIRECT = "direct"              # 直接回答
    CHAIN_OF_THOUGHT = "cot"       # 思维链
    MULTI_STEP = "multi_step"      # 多步推理
    TREE_OF_THOUGHT = "tot"        # 思维树
    SELF_REFLECTION = "reflection" # 自我反思
    REACT = "react"                # ReAct 模式（推理-行动-观察循环）


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


@dataclass
class ThoughtNode:
    """思维树节点"""
    node_id: str
    content: str
    parent_id: Optional[str] = None
    children: List[str] = field(default_factory=list)
    score: float = 0.0  # 评估分数
    depth: int = 0
    is_terminal: bool = False
    metadata: Dict = field(default_factory=dict)


@dataclass
class ThoughtTree:
    """思维树"""
    tree_id: str
    query: str
    root_id: str
    nodes: Dict[str, ThoughtNode] = field(default_factory=dict)
    best_path: List[str] = field(default_factory=list)
    max_depth: int = 3
    branching_factor: int = 3

    def add_node(self, content: str, parent_id: str = None,
                 score: float = 0.0) -> ThoughtNode:
        """添加节点"""
        node_id = f"node_{len(self.nodes)}"
        depth = 0
        if parent_id and parent_id in self.nodes:
            depth = self.nodes[parent_id].depth + 1
            self.nodes[parent_id].children.append(node_id)

        node = ThoughtNode(
            node_id=node_id,
            content=content,
            parent_id=parent_id,
            score=score,
            depth=depth,
        )
        self.nodes[node_id] = node
        return node

    def get_path_to_node(self, node_id: str) -> List[str]:
        """获取从根到指定节点的路径"""
        path = []
        current_id = node_id
        while current_id:
            path.append(current_id)
            node = self.nodes.get(current_id)
            current_id = node.parent_id if node else None
        return list(reversed(path))

    def get_best_leaf(self) -> Optional[ThoughtNode]:
        """获取最佳叶子节点"""
        leaves = [n for n in self.nodes.values() if not n.children]
        if not leaves:
            return None
        return max(leaves, key=lambda n: n.score)

    def get_thinking_log(self) -> List[str]:
        """获取思维树的思考日志"""
        logs = []
        best_leaf = self.get_best_leaf()
        if best_leaf:
            path = self.get_path_to_node(best_leaf.node_id)
            for i, node_id in enumerate(path):
                node = self.nodes[node_id]
                logs.append(f"🌳 思路{i+1} (分数:{node.score:.2f}): {node.content}")
        return logs


@dataclass
class ReActStep:
    """ReAct 步骤"""
    step_id: int
    thought: str  # 思考
    action: Optional[str] = None  # 行动
    action_input: Optional[Dict] = None  # 行动输入
    observation: Optional[str] = None  # 观察结果
    timestamp: float = field(default_factory=time.time)


class TaskAnalyzer:
    """任务分析器"""

    # 复杂任务关键词（带权重）
    COMPLEX_KEYWORDS = {
        # 分析类（权重2）
        "比较": 2, "对比": 2, "分析": 2, "评估": 2, "评价": 2,
        # 规划类（权重3）
        "规划": 3, "设计": 3, "方案": 3, "计划": 2,
        # 推理类（权重2）
        "如何": 2, "为什么": 2, "怎么办": 2, "应该": 1,
        # 计算类（权重2）
        "多少钱": 2, "预算": 2, "报价": 2, "计算": 2, "花费": 2,
        # 推荐类（权重2）
        "推荐": 2, "建议": 2, "选择": 2, "哪个好": 2,
        # 多步骤类（权重3）
        "步骤": 3, "流程": 3, "过程": 2, "顺序": 2,
        # 专业类（权重3）
        "优缺点": 3, "利弊": 3, "风险": 2, "注意事项": 2,
    }

    # 简单任务关键词（带权重）
    SIMPLE_KEYWORDS = {
        # 定义类（权重-2）
        "是什么": -2, "什么是": -2, "定义": -2, "解释": -1,
        # 位置类（权重-2）
        "在哪": -2, "哪里": -2, "地址": -2, "位置": -2,
        # 联系类（权重-2）
        "电话": -2, "联系方式": -2, "客服": -1,
        # 时间类（权重-1）
        "营业时间": -1, "开放时间": -1, "几点": -1,
        # 简单查询（权重-1）
        "有没有": -1, "是否": -1, "能不能": -1,
    }

    # 需要工具的关键词
    TOOL_KEYWORDS = {
        "subsidy_calculator": ["补贴", "能补多少", "返多少", "优惠", "返现", "补贴金额"],
        "roi_calculator": ["ROI", "投入产出", "回报率", "收益", "投资回报", "盈利"],
        "price_evaluator": ["贵不贵", "价格合理", "值不值", "性价比", "划算", "便宜"],
        "decoration_timeline": ["多久", "工期", "多长时间", "装修时间", "需要几天", "几个月"],
    }

    # 领域复杂度指标
    DOMAIN_COMPLEXITY = {
        # 装修相关（通常较复杂）
        "装修": 1, "翻新": 1, "改造": 1,
        # 材料相关（中等复杂）
        "材料": 0.5, "瓷砖": 0.5, "地板": 0.5, "涂料": 0.5,
        # 风格相关（中等复杂）
        "风格": 0.5, "现代": 0.3, "北欧": 0.3, "中式": 0.3,
        # 预算相关（较复杂）
        "预算": 1, "费用": 1, "成本": 1,
    }

    @classmethod
    def analyze_complexity(cls, query: str) -> TaskComplexity:
        """
        分析任务复杂度

        使用多维度评分系统：
        1. 关键词权重匹配
        2. 问题结构分析
        3. 领域复杂度评估
        4. 语义特征提取

        Args:
            query: 用户查询

        Returns:
            TaskComplexity: 任务复杂度等级
        """
        score = 0.0

        # 1. 复杂关键词匹配（带权重）
        for keyword, weight in cls.COMPLEX_KEYWORDS.items():
            if keyword in query:
                score += weight

        # 2. 简单关键词匹配（负权重）
        for keyword, weight in cls.SIMPLE_KEYWORDS.items():
            if keyword in query:
                score += weight  # weight 已经是负数

        # 3. 问题结构分析
        # 3.1 问题长度因子（长问题通常更复杂）
        length = len(query)
        if length > 100:
            score += 2
        elif length > 50:
            score += 1
        elif length < 15:
            score -= 1

        # 3.2 多问题检测（包含多个问号）
        question_marks = query.count("？") + query.count("?")
        if question_marks > 2:
            score += 2
        elif question_marks > 1:
            score += 1

        # 3.3 并列结构检测（包含"和"、"以及"、"还有"等）
        conjunctions = ["和", "以及", "还有", "另外", "同时", "并且"]
        conjunction_count = sum(1 for c in conjunctions if c in query)
        score += conjunction_count * 0.5

        # 3.4 条件结构检测（包含"如果"、"假设"等）
        conditionals = ["如果", "假设", "假如", "要是", "万一"]
        if any(c in query for c in conditionals):
            score += 1.5

        # 4. 领域复杂度评估
        for domain, weight in cls.DOMAIN_COMPLEXITY.items():
            if domain in query:
                score += weight

        # 5. 数字和金额检测（通常需要计算）
        import re
        numbers = re.findall(r'\d+(?:\.\d+)?', query)
        if len(numbers) >= 2:
            score += 1  # 多个数字可能需要比较或计算
        if any(unit in query for unit in ["万", "元", "块", "平米", "㎡"]):
            score += 0.5

        # 6. 时间范围检测（涉及规划）
        time_words = ["多久", "什么时候", "几天", "几个月", "多长时间"]
        if any(tw in query for tw in time_words):
            score += 0.5

        # 根据综合评分确定复杂度
        if score <= 0:
            return TaskComplexity.SIMPLE
        elif score <= 3:
            return TaskComplexity.MODERATE
        elif score <= 6:
            return TaskComplexity.COMPLEX
        else:
            return TaskComplexity.EXPERT

    @classmethod
    def get_complexity_details(cls, query: str) -> Dict[str, Any]:
        """
        获取复杂度分析详情（用于调试和解释）

        Args:
            query: 用户查询

        Returns:
            包含各维度评分的详细信息
        """
        details = {
            "query": query,
            "scores": {
                "complex_keywords": 0,
                "simple_keywords": 0,
                "length": 0,
                "questions": 0,
                "conjunctions": 0,
                "conditionals": 0,
                "domain": 0,
                "numbers": 0,
            },
            "matched_keywords": [],
            "total_score": 0,
            "complexity": None,
        }

        # 复杂关键词
        for keyword, weight in cls.COMPLEX_KEYWORDS.items():
            if keyword in query:
                details["scores"]["complex_keywords"] += weight
                details["matched_keywords"].append(f"+{keyword}({weight})")

        # 简单关键词
        for keyword, weight in cls.SIMPLE_KEYWORDS.items():
            if keyword in query:
                details["scores"]["simple_keywords"] += weight
                details["matched_keywords"].append(f"{keyword}({weight})")

        # 长度
        length = len(query)
        if length > 100:
            details["scores"]["length"] = 2
        elif length > 50:
            details["scores"]["length"] = 1
        elif length < 15:
            details["scores"]["length"] = -1

        # 问号
        question_marks = query.count("？") + query.count("?")
        if question_marks > 2:
            details["scores"]["questions"] = 2
        elif question_marks > 1:
            details["scores"]["questions"] = 1

        # 并列结构
        conjunctions = ["和", "以及", "还有", "另外", "同时", "并且"]
        details["scores"]["conjunctions"] = sum(0.5 for c in conjunctions if c in query)

        # 条件结构
        conditionals = ["如果", "假设", "假如", "要是", "万一"]
        if any(c in query for c in conditionals):
            details["scores"]["conditionals"] = 1.5

        # 领域复杂度
        for domain, weight in cls.DOMAIN_COMPLEXITY.items():
            if domain in query:
                details["scores"]["domain"] += weight

        # 数字
        import re
        numbers = re.findall(r'\d+(?:\.\d+)?', query)
        if len(numbers) >= 2:
            details["scores"]["numbers"] += 1
        if any(unit in query for unit in ["万", "元", "块", "平米", "㎡"]):
            details["scores"]["numbers"] += 0.5

        # 计算总分
        details["total_score"] = sum(details["scores"].values())
        details["complexity"] = cls.analyze_complexity(query).value

        return details

    @classmethod
    async def analyze_complexity_with_llm(cls, query: str,
                                          llm_caller: Callable) -> TaskComplexity:
        """使用 LLM 分析任务复杂度"""
        if not llm_caller:
            return cls.analyze_complexity(query)

        prompt = f"""请分析以下问题的复杂度，返回一个 JSON 对象。

问题：{query}

请评估：
1. 问题是否需要多步推理？
2. 问题是否涉及多个方面？
3. 问题是否需要专业知识？
4. 问题是否需要计算或工具？

返回格式：
{{"complexity": "simple|moderate|complex|expert", "reason": "简短说明"}}

只返回 JSON，不要其他内容。"""

        try:
            response = await llm_caller(prompt)
            # 解析 JSON
            import re
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group())
                complexity_str = data.get("complexity", "moderate")
                return TaskComplexity(complexity_str)
        except Exception:
            pass

        return cls.analyze_complexity(query)

    @classmethod
    def select_reasoning_type(cls, query: str,
                               complexity: TaskComplexity) -> ReasoningType:
        """选择推理类型"""
        # 检查是否需要工具（使用 ReAct 模式）
        for tool, keywords in cls.TOOL_KEYWORDS.items():
            if any(kw in query for kw in keywords):
                return ReasoningType.REACT

        if complexity == TaskComplexity.SIMPLE:
            return ReasoningType.DIRECT
        elif complexity == TaskComplexity.MODERATE:
            return ReasoningType.CHAIN_OF_THOUGHT
        elif complexity == TaskComplexity.COMPLEX:
            return ReasoningType.MULTI_STEP
        else:
            return ReasoningType.TREE_OF_THOUGHT

    @classmethod
    def detect_required_tools(cls, query: str) -> List[str]:
        """检测问题需要的工具"""
        required_tools = []
        for tool, keywords in cls.TOOL_KEYWORDS.items():
            if any(kw in query for kw in keywords):
                required_tools.append(tool)
        return required_tools

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
        self.trees: Dict[str, ThoughtTree] = {}
        self._lock = threading.Lock()

    def set_llm_caller(self, llm_caller: Callable):
        """设置 LLM 调用函数"""
        self.llm_caller = llm_caller

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
        with self._lock:
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

    # === Tree of Thought 实现 ===

    def create_thought_tree(self, query: str, max_depth: int = 3,
                            branching_factor: int = 3) -> ThoughtTree:
        """创建思维树"""
        tree_id = f"tree_{int(time.time() * 1000)}"
        root_id = "node_0"

        tree = ThoughtTree(
            tree_id=tree_id,
            query=query,
            root_id=root_id,
            max_depth=max_depth,
            branching_factor=branching_factor,
        )

        # 创建根节点
        tree.add_node(f"分析问题: {query}", score=0.5)

        with self._lock:
            self.trees[tree_id] = tree

        return tree

    async def expand_thought_tree(self, tree: ThoughtTree,
                                   node_id: str = None) -> List[ThoughtNode]:
        """扩展思维树节点"""
        if node_id is None:
            node_id = tree.root_id

        node = tree.nodes.get(node_id)
        if not node or node.depth >= tree.max_depth:
            return []

        if not self.llm_caller:
            # 没有 LLM，使用规则生成子节点
            return self._expand_with_rules(tree, node)

        # 使用 LLM 生成多个思路
        prompt = f"""针对以下问题，请提供 {tree.branching_factor} 个不同的思考方向。

问题：{tree.query}
当前思路：{node.content}

请返回 JSON 格式：
{{"thoughts": ["思路1", "思路2", "思路3"]}}

只返回 JSON，不要其他内容。"""

        try:
            response = await self.llm_caller(prompt)
            import re
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group())
                thoughts = data.get("thoughts", [])

                new_nodes = []
                for thought in thoughts[:tree.branching_factor]:
                    new_node = tree.add_node(thought, parent_id=node_id, score=0.5)
                    new_nodes.append(new_node)
                return new_nodes
        except Exception:
            pass

        return self._expand_with_rules(tree, node)

    def _expand_with_rules(self, tree: ThoughtTree,
                           node: ThoughtNode) -> List[ThoughtNode]:
        """使用规则扩展节点"""
        templates = [
            f"从用户需求角度分析: {tree.query}",
            f"从专业知识角度分析: {tree.query}",
            f"从实际操作角度分析: {tree.query}",
        ]

        new_nodes = []
        for template in templates[:tree.branching_factor]:
            new_node = tree.add_node(template, parent_id=node.node_id, score=0.5)
            new_nodes.append(new_node)
        return new_nodes

    async def evaluate_thought_node(self, tree: ThoughtTree,
                                     node_id: str) -> float:
        """评估思维节点的质量"""
        node = tree.nodes.get(node_id)
        if not node:
            return 0.0

        if not self.llm_caller:
            # 简单评估：基于深度和内容长度
            return 0.5 + (node.depth * 0.1) + (len(node.content) / 200)

        prompt = f"""请评估以下思路对于解决问题的帮助程度。

问题：{tree.query}
思路：{node.content}

请返回 0-1 之间的分数，格式：{{"score": 0.8, "reason": "简短说明"}}
只返回 JSON。"""

        try:
            response = await self.llm_caller(prompt)
            import re
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group())
                score = float(data.get("score", 0.5))
                node.score = score
                return score
        except Exception:
            pass

        return 0.5

    def tree_of_thought(self, query: str, context: str = "") -> ReasoningChain:
        """思维树推理（同步版本）"""
        chain = self.create_chain(query, ReasoningType.TREE_OF_THOUGHT)
        tree = self.create_thought_tree(query)

        # 记录思维树创建
        self.think(chain, f"创建思维树分析复杂问题")

        # 使用规则扩展
        root_node = tree.nodes[tree.root_id]
        child_nodes = self._expand_with_rules(tree, root_node)

        for node in child_nodes:
            self.think(chain, f"探索思路: {node.content}", confidence=node.score)

        # 选择最佳路径
        best_leaf = tree.get_best_leaf()
        if best_leaf:
            self.think(chain, f"选择最佳思路: {best_leaf.content}")

        return chain

    # === ReAct 模式实现 ===

    def react_reasoning(self, query: str, context: str = "",
                        available_tools: List[str] = None) -> ReasoningChain:
        """ReAct 推理模式"""
        chain = self.create_chain(query, ReasoningType.REACT)

        # 检测需要的工具
        required_tools = TaskAnalyzer.detect_required_tools(query)

        # 步骤1: 思考
        self.think(chain, f"分析问题，确定需要的信息和工具")

        if required_tools:
            self.think(chain, f"检测到需要使用工具: {', '.join(required_tools)}")

        # 步骤2: 行动
        for tool in required_tools:
            self.act(chain, f"调用工具 {tool}", tool=tool)

        # 步骤3: 观察
        self.observe(chain, "等待工具返回结果")

        # 步骤4: 继续思考
        self.think(chain, "根据工具结果进行推理")

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

REACT_PROMPT_TEMPLATE = """你是一个智能助手，使用 ReAct（推理-行动-观察）模式来解决问题。

问题：{query}

可用工具：
{tools_description}

请按以下格式思考和行动：

思考：分析问题，决定下一步行动
行动：选择要使用的工具和参数
观察：查看工具返回的结果
... (重复直到得出答案)
答案：最终答案

参考信息：
{context}

请开始你的推理过程。
"""

TOT_PROMPT_TEMPLATE = """你是一个智能助手，使用思维树（Tree of Thought）方法来解决复杂问题。

问题：{query}

请按以下步骤思考：

1. 生成多个可能的思路方向
2. 评估每个思路的可行性和潜在价值
3. 选择最有前景的思路深入探索
4. 如果遇到死胡同，回溯并尝试其他思路
5. 综合最佳路径得出答案

参考信息：
{context}

请展示你的思维树探索过程。
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
    elif reasoning_type == ReasoningType.REACT:
        tools_description = kwargs.get("tools_description", "无可用工具")
        return REACT_PROMPT_TEMPLATE.format(
            query=query, context=context, tools_description=tools_description
        )
    elif reasoning_type == ReasoningType.TREE_OF_THOUGHT:
        return TOT_PROMPT_TEMPLATE.format(query=query, context=context)
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


# === 推理结果格式化 ===

class ReasoningFormatter:
    """推理过程格式化器"""

    @staticmethod
    def format_chain_for_display(chain: ReasoningChain) -> Dict:
        """
        将推理链格式化为可展示的结构

        Returns:
            包含推理过程的结构化数据
        """
        return {
            "chain_id": chain.chain_id,
            "query": chain.query,
            "reasoning_type": chain.reasoning_type.value,
            "reasoning_type_name": {
                "direct": "直接回答",
                "cot": "思维链推理",
                "multi_step": "多步推理",
                "tot": "思维树探索",
                "reflection": "自我反思",
                "react": "推理-行动循环",
            }.get(chain.reasoning_type.value, chain.reasoning_type.value),
            "steps": [
                {
                    "step_id": step.step_id,
                    "type": step.step_type,
                    "type_icon": {
                        "think": "💭",
                        "act": "🔧",
                        "observe": "👁️",
                        "reflect": "🔄",
                        "plan": "📋",
                        "verify": "✅",
                    }.get(step.step_type, "📝"),
                    "content": step.content,
                    "confidence": step.confidence,
                }
                for step in chain.steps
            ],
            "final_answer": chain.final_answer,
            "confidence": chain.confidence,
            "duration": (chain.end_time - chain.start_time) if chain.end_time else None,
        }

    @staticmethod
    def format_chain_as_markdown(chain: ReasoningChain) -> str:
        """
        将推理链格式化为 Markdown 文本

        Returns:
            Markdown 格式的推理过程
        """
        lines = []
        lines.append(f"## 推理过程")
        lines.append(f"**推理类型**: {chain.reasoning_type.value}")
        lines.append("")

        for step in chain.steps:
            icon = {
                "think": "💭",
                "act": "🔧",
                "observe": "👁️",
                "reflect": "🔄",
                "plan": "📋",
                "verify": "✅",
            }.get(step.step_type, "📝")

            lines.append(f"{icon} **{step.step_type}**: {step.content}")

        if chain.final_answer:
            lines.append("")
            lines.append(f"**结论**: {chain.final_answer}")

        if chain.confidence > 0:
            lines.append(f"**置信度**: {chain.confidence:.0%}")

        return "\n".join(lines)

    @staticmethod
    def get_reasoning_summary(chain: ReasoningChain) -> str:
        """
        获取推理过程的简短摘要

        Returns:
            推理摘要文本
        """
        type_names = {
            "direct": "直接回答",
            "cot": "思维链分析",
            "multi_step": "多步推理",
            "tot": "多路径探索",
            "reflection": "反思优化",
            "react": "工具辅助推理",
        }

        type_name = type_names.get(chain.reasoning_type.value, "推理")
        step_count = len(chain.steps)

        if step_count == 0:
            return f"使用{type_name}模式"
        elif step_count <= 3:
            return f"经过{step_count}步{type_name}"
        else:
            return f"经过{step_count}步深度{type_name}"


class AdaptiveReasoningStrategy:
    """自适应推理策略"""

    def __init__(self, engine: ReasoningEngine):
        self.engine = engine
        self._history: List[Dict] = []
        self._max_history = 100

    def select_strategy(self, query: str, context: Dict = None) -> ReasoningType:
        """
        根据查询和上下文自适应选择推理策略

        Args:
            query: 用户查询
            context: 上下文信息（用户画像、历史等）

        Returns:
            推荐的推理类型
        """
        # 基础复杂度分析
        complexity = TaskAnalyzer.analyze_complexity(query)
        base_type = TaskAnalyzer.select_reasoning_type(query, complexity)

        # 根据上下文调整
        if context:
            # 如果用户偏好详细解释，提升推理复杂度
            if context.get("user_profile", {}).get("response_detail_level") == "detailed":
                if base_type == ReasoningType.DIRECT:
                    base_type = ReasoningType.CHAIN_OF_THOUGHT
                elif base_type == ReasoningType.CHAIN_OF_THOUGHT:
                    base_type = ReasoningType.MULTI_STEP

            # 如果有工具结果，使用 ReAct 模式
            if context.get("tool_results"):
                base_type = ReasoningType.REACT

            # 如果是复杂的多方面问题，使用思维树
            if context.get("is_multi_aspect"):
                base_type = ReasoningType.TREE_OF_THOUGHT

        return base_type

    def record_result(self, query: str, reasoning_type: ReasoningType,
                      success: bool, user_feedback: float = None):
        """
        记录推理结果，用于策略优化

        Args:
            query: 查询
            reasoning_type: 使用的推理类型
            success: 是否成功
            user_feedback: 用户反馈评分 (0-1)
        """
        self._history.append({
            "query": query,
            "reasoning_type": reasoning_type.value,
            "success": success,
            "feedback": user_feedback,
            "timestamp": time.time(),
        })

        # 限制历史记录大小
        if len(self._history) > self._max_history:
            self._history = self._history[-self._max_history:]

    def get_statistics(self) -> Dict:
        """获取推理策略统计"""
        if not self._history:
            return {"total": 0}

        stats = {
            "total": len(self._history),
            "by_type": {},
            "success_rate": 0,
            "avg_feedback": 0,
        }

        success_count = 0
        feedback_sum = 0
        feedback_count = 0

        for record in self._history:
            rt = record["reasoning_type"]
            if rt not in stats["by_type"]:
                stats["by_type"][rt] = {"count": 0, "success": 0}
            stats["by_type"][rt]["count"] += 1
            if record["success"]:
                stats["by_type"][rt]["success"] += 1
                success_count += 1
            if record["feedback"] is not None:
                feedback_sum += record["feedback"]
                feedback_count += 1

        stats["success_rate"] = success_count / len(self._history)
        if feedback_count > 0:
            stats["avg_feedback"] = feedback_sum / feedback_count

        return stats


# 全局自适应策略实例
_adaptive_strategy: Optional[AdaptiveReasoningStrategy] = None


def get_adaptive_strategy() -> AdaptiveReasoningStrategy:
    """获取全局自适应推理策略"""
    global _adaptive_strategy
    if _adaptive_strategy is None:
        _adaptive_strategy = AdaptiveReasoningStrategy(get_reasoning_engine())
    return _adaptive_strategy
