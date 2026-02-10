"""
增强版智能体基类
整合记忆系统、推理引擎、工具系统和多模态能力
"""
import os
import sys
import time
import json
from typing import Any, Dict, List, Optional, AsyncGenerator
from datetime import datetime
from abc import ABC, abstractmethod

# 添加路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from langchain_community.chat_models import ChatTongyi
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables import RunnableSequence
from langchain_core.output_parsers import StrOutputParser
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage

from backend.core.singleton import get_knowledge_base
from backend.core.memory import get_memory_manager, MemoryType, UserProfile
from backend.core.reasoning import (
    get_reasoning_engine, ReasoningType, ReasoningChain,
    TaskAnalyzer, TaskComplexity, get_reasoning_prompt
)
from backend.core.tools import get_tool_registry, ToolResult
from backend.core.multimodal import get_multimodal_manager, MediaContent, MediaType
from backend.core.output_formatter import OutputFormatter, OutputType


class EnhancedAgent(ABC):
    """增强版智能体基类"""

    def __init__(self, user_type: str = "both", agent_name: str = "assistant"):
        self.user_type = user_type
        self.agent_name = agent_name

        # 核心组件
        self.kb = get_knowledge_base()
        self.memory = get_memory_manager()
        self.reasoning = get_reasoning_engine()
        self.tools = get_tool_registry()
        self.multimodal = get_multimodal_manager()

        # LLM配置
        self.llm = ChatTongyi(
            model="qwen-plus",
            temperature=0.7,
            streaming=True,
        )

        # 配置选项
        self.enable_search = True
        self.enable_reasoning = True
        self.enable_memory = True
        self.show_thinking = True
        self.max_tool_calls = 5

        # 构建处理链
        self._build_chain()

    def _build_chain(self):
        """构建处理链"""
        prompt = ChatPromptTemplate.from_messages([
            ("system", self._get_system_prompt()),
            MessagesPlaceholder(variable_name="history"),
            MessagesPlaceholder(variable_name="context"),
            ("human", "{input}"),
        ])

        self.chain = prompt | self.llm | StrOutputParser()

    @abstractmethod
    def _get_system_prompt(self) -> str:
        """获取系统提示词（子类实现）"""
        pass

    # === 核心处理流程 ===

    async def process(self, message: str, session_id: str,
                      user_id: str = None, images: List[str] = None) -> AsyncGenerator:
        """
        处理用户消息

        Args:
            message: 用户消息
            session_id: 会话ID
            user_id: 用户ID
            images: 图片路径列表

        Yields:
            输出事件
        """
        user_id = user_id or session_id
        formatter = OutputFormatter(session_id, self.user_type)

        # 发送流开始
        yield formatter.stream_start()

        try:
            # 1. 分析任务复杂度
            complexity = TaskAnalyzer.analyze_complexity(message)
            reasoning_type = TaskAnalyzer.select_reasoning_type(message, complexity)

            # 2. 创建推理链
            chain = self.reasoning.create_chain(message, reasoning_type)

            # 3. 获取用户画像和记忆上下文
            context = await self._prepare_context(user_id, session_id, message)

            # 4. 处理多模态输入
            if images:
                for img_path in images:
                    img_result = await self._process_image(img_path)
                    context["image_analysis"] = img_result
                    self.reasoning.observe(chain, f"图片分析: {img_result.get('description', '')}")

            # 5. 知识检索
            if self.enable_search:
                docs = await self._retrieve_knowledge(message, context)
                if docs:
                    self.reasoning.act(chain, "检索知识库", tool="knowledge_search")
                    self.reasoning.observe(chain, f"找到 {len(docs)} 条相关信息")
                    context["knowledge"] = docs

            # 6. 工具调用判断
            tool_results = await self._check_and_call_tools(message, context, chain)
            if tool_results:
                context["tool_results"] = tool_results

            # 7. 输出思考过程
            if self.show_thinking:
                thinking_logs = chain.get_thinking_log()
                if thinking_logs:
                    yield formatter.thinking(thinking_logs)

            # 8. 生成回答
            async for chunk in self._generate_response(message, context, chain):
                yield formatter.answer(chunk)

            # 9. 更新记忆
            if self.enable_memory:
                await self._update_memory(user_id, session_id, message, chain)

            # 10. 发送流结束
            yield formatter.stream_end()

        except Exception as e:
            yield formatter.error(str(e), "PROCESS_ERROR")
            yield formatter.stream_end()

    async def _prepare_context(self, user_id: str, session_id: str,
                                message: str) -> Dict:
        """准备上下文"""
        context = {
            "user_id": user_id,
            "session_id": session_id,
            "timestamp": datetime.now().isoformat(),
            "user_type": self.user_type,
        }

        if self.enable_memory:
            # 获取用户画像
            profile = self.memory.get_or_create_profile(user_id, self.user_type)
            context["user_profile"] = {
                "interests": profile.interests,
                "preferred_styles": profile.preferred_styles,
                "budget_range": profile.budget_range,
                "communication_style": profile.communication_style,
            }

            # 获取记忆上下文
            memory_context = self.memory.get_context_for_query(user_id, session_id, message)
            context["memory"] = memory_context

            # 获取工作记忆
            context["working_memory"] = self.memory.get_all_working_memory(session_id)

        return context

    async def _retrieve_knowledge(self, query: str, context: Dict) -> List[Dict]:
        """检索知识"""
        try:
            docs = self.kb.search(
                query=query,
                user_type=self.user_type,
                top_k=5,
            )
            return [
                {
                    "content": doc.page_content,
                    "source": doc.metadata.get("source", "unknown"),
                    "collection": doc.metadata.get("collection", "unknown"),
                }
                for doc in docs
            ]
        except Exception as e:
            return []

    async def _check_and_call_tools(self, message: str, context: Dict,
                                     chain: ReasoningChain) -> Dict:
        """检查并调用工具"""
        results = {}

        # 补贴计算检测
        if any(kw in message for kw in ["补贴", "能补多少", "返多少"]):
            # 尝试提取金额和品类
            amount = self._extract_amount(message)
            category = self._extract_category(message)
            if amount and category:
                self.reasoning.act(chain, f"计算{category}补贴", tool="subsidy_calculator")
                result = self.tools.call("subsidy_calculator", amount=amount, category=category)
                if result.success:
                    results["subsidy"] = result.data
                    self.reasoning.observe(chain, f"补贴计算结果: {result.data.get('final_amount', 0)}元")

        # ROI计算检测
        if any(kw in message for kw in ["ROI", "投入产出", "回报率"]):
            investment = self._extract_amount(message, "投入")
            revenue = self._extract_amount(message, "收入")
            if investment and revenue:
                self.reasoning.act(chain, "计算ROI", tool="roi_calculator")
                result = self.tools.call("roi_calculator", investment=investment, revenue=revenue)
                if result.success:
                    results["roi"] = result.data
                    self.reasoning.observe(chain, f"ROI: {result.data.get('roi_percent', 0)}%")

        # 价格评估检测
        if any(kw in message for kw in ["贵不贵", "价格合理", "值不值"]):
            price = self._extract_amount(message)
            category = self._extract_category(message)
            if price and category:
                self.reasoning.act(chain, "评估价格", tool="price_evaluator")
                result = self.tools.call("price_evaluator", category=category, price=price)
                if result.success:
                    results["price_eval"] = result.data

        # 工期估算检测
        if any(kw in message for kw in ["多久", "工期", "多长时间"]):
            area = self._extract_area(message)
            if area:
                self.reasoning.act(chain, "估算工期", tool="decoration_timeline")
                result = self.tools.call("decoration_timeline", house_area=area)
                if result.success:
                    results["timeline"] = result.data

        return results

    async def _process_image(self, image_path: str) -> Dict:
        """处理图片"""
        content = MediaContent(
            media_type=MediaType.IMAGE,
            content=image_path,
        )
        return self.multimodal.process(content)

    async def _generate_response(self, message: str, context: Dict,
                                  chain: ReasoningChain) -> AsyncGenerator[str, None]:
        """生成回答"""
        # 构建提示词
        prompt_context = self._build_prompt_context(context)

        # 如果启用推理增强
        if self.enable_reasoning and chain.reasoning_type != ReasoningType.DIRECT:
            reasoning_prompt = get_reasoning_prompt(
                chain.reasoning_type,
                message,
                prompt_context,
            )
            input_message = reasoning_prompt
        else:
            input_message = message

        # 构建消息历史
        history = self._get_message_history(context)

        # 流式生成
        async for chunk in self.chain.astream({
            "input": input_message,
            "history": history,
            "context": [SystemMessage(content=prompt_context)],
        }):
            yield chunk

    def _build_prompt_context(self, context: Dict) -> str:
        """构建提示词上下文"""
        parts = []

        # 用户画像
        if "user_profile" in context:
            profile = context["user_profile"]
            if profile.get("interests"):
                parts.append(f"用户兴趣: {', '.join(profile['interests'].keys())}")
            if profile.get("preferred_styles"):
                parts.append(f"偏好风格: {', '.join(profile['preferred_styles'])}")
            if profile.get("budget_range"):
                parts.append(f"预算范围: {profile['budget_range']}")

        # 知识检索结果
        if "knowledge" in context:
            knowledge_text = "\n".join([
                f"- {doc['content'][:500]}"
                for doc in context["knowledge"][:3]
            ])
            parts.append(f"参考信息:\n{knowledge_text}")

        # 工具调用结果
        if "tool_results" in context:
            for tool_name, result in context["tool_results"].items():
                parts.append(f"{tool_name}结果: {json.dumps(result, ensure_ascii=False)}")

        # 图片分析结果
        if "image_analysis" in context:
            img = context["image_analysis"]
            if "result" in img:
                parts.append(f"图片分析: {img['result'].get('description', '')}")

        return "\n\n".join(parts)

    def _get_message_history(self, context: Dict) -> List:
        """获取消息历史"""
        history = []
        if "memory" in context and "short_term_memory" in context["memory"]:
            for item in context["memory"]["short_term_memory"][-5:]:
                if isinstance(item, dict):
                    if item.get("role") == "user":
                        history.append(HumanMessage(content=item.get("content", "")))
                    elif item.get("role") == "assistant":
                        history.append(AIMessage(content=item.get("content", "")))
        return history

    async def _update_memory(self, user_id: str, session_id: str,
                              message: str, chain: ReasoningChain):
        """更新记忆"""
        # 记录交互
        self.memory.record_interaction(
            user_id=user_id,
            interaction_type="chat",
            content=message,
            metadata={
                "session_id": session_id,
                "reasoning_type": chain.reasoning_type.value,
            }
        )

        # 添加到短期记忆
        self.memory.add_to_short_term(
            session_id=session_id,
            content={"role": "user", "content": message},
            importance=0.5,
        )

        # 提取并更新用户兴趣
        interests = self._extract_interests(message)
        profile = self.memory.get_or_create_profile(user_id, self.user_type)
        for interest in interests:
            profile.update_interest(interest, 0.1)

    # === 辅助方法 ===

    def _extract_amount(self, text: str, keyword: str = None) -> Optional[float]:
        """提取金额"""
        import re
        patterns = [
            r'(\d+(?:\.\d+)?)\s*[万w]',  # 万
            r'(\d+(?:\.\d+)?)\s*元',      # 元
            r'(\d+(?:\.\d+)?)\s*块',      # 块
            r'(\d+(?:,\d{3})*(?:\.\d+)?)', # 纯数字
        ]

        for pattern in patterns:
            matches = re.findall(pattern, text)
            if matches:
                amount = float(matches[0].replace(',', ''))
                if '万' in text or 'w' in text.lower():
                    amount *= 10000
                return amount
        return None

    def _extract_category(self, text: str) -> Optional[str]:
        """提取品类"""
        categories = ["家具", "建材", "家电", "软装", "智能家居"]
        for cat in categories:
            if cat in text:
                return cat
        return None

    def _extract_area(self, text: str) -> Optional[float]:
        """提取面积"""
        import re
        patterns = [
            r'(\d+(?:\.\d+)?)\s*[平㎡]',
            r'(\d+(?:\.\d+)?)\s*平米',
            r'(\d+(?:\.\d+)?)\s*平方',
        ]
        for pattern in patterns:
            matches = re.findall(pattern, text)
            if matches:
                return float(matches[0])
        return None

    def _extract_interests(self, text: str) -> List[str]:
        """提取兴趣标签"""
        interest_keywords = {
            "装修风格": ["现代", "北欧", "中式", "轻奢", "简约", "工业风"],
            "材料": ["瓷砖", "地板", "乳胶漆", "壁纸", "大理石"],
            "家具": ["沙发", "床", "餐桌", "衣柜", "书桌"],
            "空间": ["客厅", "卧室", "厨房", "卫生间", "阳台"],
        }

        interests = []
        for category, keywords in interest_keywords.items():
            for kw in keywords:
                if kw in text:
                    interests.append(kw)
        return interests

    # === 工具调用接口 ===

    def call_tool(self, tool_name: str, **kwargs) -> ToolResult:
        """调用工具"""
        return self.tools.call(tool_name, **kwargs)

    def get_available_tools(self) -> List[Dict]:
        """获取可用工具列表"""
        return self.tools.get_tools_for_llm()

    # === 记忆操作接口 ===

    def set_working_memory(self, session_id: str, key: str, value: Any):
        """设置工作记忆"""
        self.memory.set_working_memory(session_id, key, value)

    def get_working_memory(self, session_id: str, key: str) -> Any:
        """获取工作记忆"""
        return self.memory.get_working_memory(session_id, key)

    def get_user_profile(self, user_id: str) -> UserProfile:
        """获取用户画像"""
        return self.memory.get_or_create_profile(user_id, self.user_type)

    def update_user_profile(self, user_id: str, **kwargs):
        """更新用户画像"""
        self.memory.update_profile(user_id, **kwargs)
