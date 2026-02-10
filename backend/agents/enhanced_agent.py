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
from backend.core.memory import get_memory_manager, MemoryType, UserProfile, DecorationJourney
from backend.core.reasoning import (
    get_reasoning_engine, ReasoningType, ReasoningChain,
    TaskAnalyzer, TaskComplexity, get_reasoning_prompt,
    get_adaptive_strategy, ReasoningFormatter
)
from backend.core.tools import get_tool_registry, ToolResult
from backend.core.multimodal import get_multimodal_manager, MediaContent, MediaType
from backend.core.output_formatter import OutputFormatter, OutputType
from backend.core.function_calling import get_function_calling_engine, FunctionCallingEngine
from backend.core.cache import get_knowledge_cache, get_llm_cache
from backend.knowledge.knowledge_graph import get_knowledge_graph
from backend.core.stage_reasoning import (
    get_stage_reasoning, StageAwareReasoning, StageContext, ExpertRole, StageTransition
)
from backend.core.logging_config import get_logger

logger = get_logger("enhanced_agent")


class EnhancedAgent(ABC):
    """增强版智能体基类"""

    def __init__(self, user_type: str = "both", agent_name: str = "assistant"):
        self.user_type = user_type
        self.agent_name = agent_name

        # 核心组件
        self.kb = get_knowledge_base()
        self.memory = get_memory_manager()
        self.reasoning = get_reasoning_engine()
        self.adaptive_strategy = get_adaptive_strategy()
        self.tools = get_tool_registry()
        self.multimodal = get_multimodal_manager()
        self.function_calling = get_function_calling_engine()
        self.knowledge_cache = get_knowledge_cache()
        self.llm_cache = get_llm_cache()
        self.knowledge_graph = get_knowledge_graph()
        # LLM配置
        self.llm = ChatTongyi(
            model="qwen-plus",
            temperature=0.7,
            streaming=True,
        )

        self.stage_reasoning = get_stage_reasoning(llm=self.llm)  # 阶段感知推理引擎（传入LLM启用深度分析）

        # 配置选项
        self.enable_search = True
        self.enable_reasoning = True
        self.enable_memory = True
        self.enable_llm_function_calling = True  # 启用 LLM 智能工具调用
        self.show_thinking = True
        self.max_tool_calls = 5

        # 构建处理链
        self._build_chain()

    def _build_chain(self):
        """构建处理链"""
        prompt = ChatPromptTemplate.from_messages([
            ("system", "{system_prompt}"),
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
        process_success = True

        # 发送流开始
        yield formatter.stream_start()

        try:
            # 1. 获取用户画像和记忆上下文（用于自适应推理）
            context = await self._prepare_context(user_id, session_id, message)

            # 2. 使用自适应策略选择推理类型
            reasoning_type = self.adaptive_strategy.select_strategy(message, context)

            # 3. 创建推理链
            chain = self.reasoning.create_chain(message, reasoning_type)

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

            # 7. 输出专家诊断信息（在思考过程之前）
            if "stage_context" in context:
                yield formatter.expert_debug(context)

            # 8. 输出思考过程（使用格式化器）
            if self.show_thinking:
                thinking_logs = chain.get_thinking_log()
                # 将专家角色信息追加到思考日志
                if "stage_context" in context:
                    stage_ctx = context["stage_context"]
                    expert_role = context.get("expert_role")
                    expert_name = expert_role.name if expert_role else "通用顾问"
                    thinking_logs.append(
                        f"阶段判断: {stage_ctx.stage}（置信度 {stage_ctx.stage_confidence:.0%}）→ 专家角色: {expert_name}"
                    )
                    if stage_ctx.emotional_state and stage_ctx.emotional_state != "平静":
                        thinking_logs.append(f"用户情绪: {stage_ctx.emotional_state}")
                if thinking_logs:
                    yield formatter.thinking(thinking_logs, reasoning_type.value)

            # 9. 生成回答（同时收集完整回复用于保存到记忆）
            full_response = []
            async for chunk in self._generate_response(message, context, chain):
                full_response.append(chunk)
                yield formatter.answer(chunk)

            # 10. 更新记忆（同时保存用户消息和助手回复）
            if self.enable_memory:
                assistant_response = "".join(full_response)
                await self._update_memory(user_id, session_id, message, chain, assistant_response)

            # 11. 发送流结束
            yield formatter.stream_end()

            # 12. 记录推理结果（用于策略优化）
            self.adaptive_strategy.record_result(
                query=message,
                reasoning_type=reasoning_type,
                success=True
            )

        except Exception as e:
            process_success = False
            logger.error("处理流程异常", extra={
                "error": str(e),
                "user_id": user_id,
                "session_id": session_id,
                "query": message[:100],
            }, exc_info=True)
            yield formatter.error(str(e), "PROCESS_ERROR")
            yield formatter.stream_end()

            # 记录失败
            if 'reasoning_type' in locals():
                self.adaptive_strategy.record_result(
                    query=message,
                    reasoning_type=reasoning_type,
                    success=False
                )

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

            # 获取装修阶段信息（新增）
            stage_info = self._get_stage_context(profile)
            if stage_info:
                context["decoration_stage"] = stage_info

            # 获取用户痛点（新增）
            if profile.pain_points:
                context["pain_points"] = profile.pain_points[-3:]  # 最近3个痛点

            # 推断下一个需求（新增）
            next_need = profile.infer_next_need()
            if next_need:
                context["inferred_need"] = next_need

            # 获取记忆上下文
            memory_context = self.memory.get_context_for_query(user_id, session_id, message)
            context["memory"] = memory_context

            # 获取工作记忆
            context["working_memory"] = self.memory.get_all_working_memory(session_id)

            # === 阶段感知专家系统 ===
            # 获取之前的阶段（用于检测阶段转换）
            previous_stage = profile.decoration_stage

            # 获取对话历史
            conversation_history = []
            if "short_term_memory" in memory_context:
                conversation_history = memory_context["short_term_memory"]

            # 深度阶段理解
            try:
                stage_context, expert_role, stage_transition = await self.stage_reasoning.analyze_and_get_expert(
                    query=message,
                    conversation_history=conversation_history,
                    user_profile=context["user_profile"],
                    previous_stage=previous_stage,
                    user_type=self.user_type,
                )

                # 保存阶段上下文
                context["stage_context"] = stage_context
                context["expert_role"] = expert_role

                # 记录阶段分析结果
                logger.info("阶段感知分析完成", extra={
                    "user_id": user_id,
                    "session_id": session_id,
                    "query": message[:100],
                    "detected_stage": stage_context.stage,
                    "stage_confidence": stage_context.stage_confidence,
                    "expert_role": expert_role.name if expert_role else None,
                    "emotional_state": stage_context.emotional_state,
                    "focus_points": stage_context.focus_points,
                    "stage_transition": bool(stage_transition),
                })

                # 处理阶段转换
                if stage_transition:
                    context["stage_transition"] = stage_transition

                    logger.info("检测到阶段转换", extra={
                        "user_id": user_id,
                        "session_id": session_id,
                        "from_stage": stage_transition.from_stage,
                        "to_stage": stage_transition.to_stage,
                        "confidence": stage_transition.confidence,
                        "trigger": stage_transition.trigger,
                    })
                    # 更新用户画像中的阶段
                    profile.update_decoration_stage(
                        stage_transition.to_stage,
                        trigger=stage_transition.trigger,
                        confidence=stage_transition.confidence
                    )
                    # 记录阶段转换事件
                    if profile.decoration_journey:
                        profile.decoration_journey.record_stage_transition(
                            from_stage=stage_transition.from_stage,
                            to_stage=stage_transition.to_stage,
                            trigger=stage_transition.trigger,
                            confidence=stage_transition.confidence
                        )

            except Exception as e:
                # 阶段分析失败时使用默认行为，但记录警告
                logger.warning("阶段感知分析失败", extra={
                    "user_id": user_id,
                    "session_id": session_id,
                    "query": message[:100],
                    "error": str(e),
                })

        return context

    def _get_stage_context(self, profile: UserProfile) -> Optional[Dict]:
        """
        获取装修阶段上下文

        根据用户当前装修阶段，提供相关的上下文信息和建议
        """
        if not profile.decoration_journey:
            # 如果没有装修旅程信息，尝试从decoration_stage推断
            if profile.decoration_stage:
                return {
                    "current_stage": profile.decoration_stage,
                    "stage_tips": self._get_stage_tips(profile.decoration_stage),
                    "recommended_topics": self._get_stage_topics(profile.decoration_stage),
                }
            return None

        journey = profile.decoration_journey
        stage_info = {
            "current_stage": journey.current_stage,
            "completed_stages": journey.completed_stages,
            "progress": journey.actual_progress,
            "stage_tips": self._get_stage_tips(journey.current_stage),
            "recommended_topics": self._get_stage_topics(journey.current_stage),
        }

        # 如果有阶段开始时间，计算已进行天数
        if journey.stage_start_date:
            import time
            days_in_stage = int((time.time() - journey.stage_start_date) / 86400)
            stage_info["days_in_current_stage"] = days_in_stage

        return stage_info

    def _get_stage_tips(self, stage: str) -> List[str]:
        """获取阶段相关提示"""
        stage_tips = {
            "准备": [
                "确定装修预算，建议留10%机动资金",
                "多看装修案例，明确自己喜欢的风格",
                "了解装修流程，做好时间规划",
            ],
            "设计": [
                "仔细审核设计方案，确认每个细节",
                "注意动线设计是否合理",
                "确认收纳空间是否充足",
            ],
            "施工": [
                "定期到现场检查施工质量",
                "水电改造后拍照留存管线走向",
                "防水必须做闭水试验",
            ],
            "软装": [
                "家具尺寸要提前确认",
                "注意家具与整体风格的搭配",
                "软装可以分批购买，不必一次到位",
            ],
            "入住": [
                "入住前做甲醛检测",
                "建议通风3个月以上",
                "保留好各项保修凭证",
            ],
        }
        return stage_tips.get(stage, [])

    def _get_stage_topics(self, stage: str) -> List[str]:
        """获取阶段推荐话题"""
        stage_topics = {
            "准备": ["预算规划", "风格选择", "装修公司选择", "设计师选择"],
            "设计": ["方案优化", "材料选择", "报价审核", "合同注意事项"],
            "施工": ["施工进度", "质量验收", "材料进场", "工艺标准"],
            "软装": ["家具选购", "软装搭配", "灯具选择", "窗帘布艺"],
            "入住": ["甲醛治理", "家电选购", "收纳整理", "维护保养"],
        }
        return stage_topics.get(stage, [])

    async def _retrieve_knowledge(self, query: str, context: Dict) -> List[Dict]:
        """检索知识（带缓存）"""
        try:
            # 尝试从缓存获取
            cached_results = self.knowledge_cache.find_similar(
                query=query,
                user_type=self.user_type,
                k=5
            )
            if cached_results is not None:
                return cached_results

            # 使用正确的 search_by_user_type 方法
            results = self.kb.search_by_user_type(
                query=query,
                user_type=self.user_type,
                k=5,
            )
            formatted_results = [
                {
                    "content": doc.page_content,
                    "source": doc.metadata.get("source", "unknown"),
                    "collection": doc.metadata.get("collection", "unknown"),
                    "score": score,
                }
                for doc, score in results
            ]

            # 缓存结果
            if formatted_results:
                self.knowledge_cache.set(
                    query=query,
                    user_type=self.user_type,
                    k=5,
                    results=formatted_results
                )

            return formatted_results
        except Exception as e:
            return []

    async def _check_and_call_tools(self, message: str, context: Dict,
                                     chain: ReasoningChain) -> Dict:
        """检查并调用工具"""
        results = {}

        # 优先使用 LLM Function Calling（如果启用）
        if self.enable_llm_function_calling:
            try:
                fc_result = await self.function_calling.process_with_tools(
                    message=message,
                    context=context,
                )

                # 记录思考过程
                for thought in fc_result.thinking:
                    self.reasoning.observe(chain, thought)

                # 处理工具调用结果
                for call in fc_result.calls:
                    if call.result:
                        results[call.name] = call.result
                        self.reasoning.act(chain, f"调用工具 {call.name}", tool=call.name)
                        self.reasoning.observe(chain, f"工具结果: {json.dumps(call.result, ensure_ascii=False)[:200]}")

                if results:
                    return results
            except Exception as e:
                self.reasoning.observe(chain, f"LLM Function Calling 失败: {str(e)}")

        # 回退到规则匹配（兼容模式）
        return await self._check_and_call_tools_fallback(message, context, chain)

    async def _check_and_call_tools_fallback(self, message: str, context: Dict,
                                              chain: ReasoningChain) -> Dict:
        """使用规则匹配调用工具（回退方案）"""
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
        # 构建提示词的两个部分
        system_prompt, supplementary_context = self._build_prompt_parts(context)

        # 如果启用推理增强
        if self.enable_reasoning and chain.reasoning_type != ReasoningType.DIRECT:
            reasoning_prompt = get_reasoning_prompt(
                chain.reasoning_type,
                message,
                supplementary_context,
            )
            input_message = reasoning_prompt
            # 推理提示词已包含 supplementary_context，不再重复发送
            context_messages = []
        else:
            input_message = message
            # 非推理模式下，辅助信息作为 context 消息注入
            context_messages = []
            if supplementary_context:
                context_messages.append(SystemMessage(content=supplementary_context))

        # 构建消息历史
        history = self._get_message_history(context)

        chain_input = {
            "input": input_message,
            "system_prompt": system_prompt,
            "history": history,
            "context": context_messages,
        }

        logger.debug("开始生成回答", extra={
            "system_prompt_length": len(system_prompt),
            "context_messages_count": len(context_messages),
            "history_count": len(history),
        })

        # 流式生成（带重试）
        max_retries = 2
        for attempt in range(max_retries + 1):
            try:
                async for chunk in self.chain.astream(chain_input):
                    yield chunk
                return  # 成功完成，退出
            except Exception as e:
                error_msg = str(e)
                if attempt < max_retries and ("prematurely" in error_msg or "ConnectionError" in error_msg or "timeout" in error_msg.lower()):
                    logger.warning(f"流式生成中断，重试 {attempt + 1}/{max_retries}", extra={
                        "error": error_msg,
                    })
                    continue
                else:
                    raise  # 非网络错误或重试耗尽，向上抛出

    def _build_prompt_parts(self, context: Dict) -> tuple:
        """
        构建提示词的两个部分

        Returns:
            (system_prompt, supplementary_context)
            - system_prompt: 专家角色提示词（或回退到子类默认提示词），作为唯一的系统身份
            - supplementary_context: 用户画像、知识检索、工具结果等辅助信息
        """
        # === 确定唯一的系统身份提示词 ===
        if "expert_role" in context and context["expert_role"]:
            expert_role = context["expert_role"]
            system_prompt = expert_role.system_prompt

            # 根据阶段上下文定制专家提示词
            if "stage_context" in context:
                stage_ctx = context["stage_context"]
                system_prompt = self.stage_reasoning.get_expert_system_prompt(
                    stage=stage_ctx.stage,
                    user_type=self.user_type,
                    context=stage_ctx,
                )
        else:
            # 回退到子类的默认系统提示词
            system_prompt = self._get_system_prompt()
            # 清理变量占位符
            if "{current_time}" in system_prompt:
                system_prompt = system_prompt.replace("{current_time}", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
            if "{context}" in system_prompt:
                system_prompt = system_prompt.split("{context}")[0]
            system_prompt = system_prompt.strip()

        # === 构建辅助上下文信息 ===
        parts = []

        # 阶段转换引导
        if "stage_transition" in context:
            transition = context["stage_transition"]
            if transition.transition_guidance:
                parts.append(f"【阶段转换提醒】\n{transition.transition_guidance}")

        # 用户画像
        if "user_profile" in context:
            profile = context["user_profile"]
            if profile.get("interests"):
                parts.append(f"用户兴趣: {', '.join(profile['interests'].keys())}")
            if profile.get("preferred_styles"):
                parts.append(f"偏好风格: {', '.join(profile['preferred_styles'])}")
            if profile.get("budget_range"):
                parts.append(f"预算范围: {profile['budget_range']}")

        # 阶段感知上下文
        if "stage_context" in context:
            stage_ctx = context["stage_context"]
            stage_text = f"当前装修阶段: {stage_ctx.stage}（置信度: {stage_ctx.stage_confidence:.0%}）"
            parts.append(stage_text)

            if stage_ctx.deep_need:
                parts.append(f"用户深层需求: {stage_ctx.deep_need}")
            if stage_ctx.potential_needs:
                parts.append(f"潜在需求: {', '.join(stage_ctx.potential_needs[:3])}")
            if stage_ctx.emotional_state and stage_ctx.emotional_state != "平静":
                parts.append(f"用户情绪: {stage_ctx.emotional_state}")
            if stage_ctx.focus_points:
                parts.append(f"关注重点: {', '.join(stage_ctx.focus_points)}")

        elif "decoration_stage" in context:
            stage_info = context["decoration_stage"]
            stage_text = f"当前装修阶段: {stage_info.get('current_stage', '未知')}"
            if stage_info.get("days_in_current_stage"):
                stage_text += f"（已进行{stage_info['days_in_current_stage']}天）"
            parts.append(stage_text)
            if stage_info.get("stage_tips"):
                parts.append(f"阶段注意事项: {'; '.join(stage_info['stage_tips'][:2])}")

        # 用户痛点
        if "pain_points" in context and context["pain_points"]:
            pain_texts = [f"{p['type']}({p['description'][:20]})" for p in context["pain_points"]]
            parts.append(f"用户关注问题: {', '.join(pain_texts)}")

        # 推断的需求
        if "inferred_need" in context:
            need = context["inferred_need"]
            parts.append(f"可能的需求: {need.get('suggestion', '')}（{need.get('reason', '')}）")

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

        supplementary_context = "\n\n".join(parts)
        return system_prompt, supplementary_context

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
                              message: str, chain: ReasoningChain,
                              assistant_response: str = None):
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

        # 添加用户消息到短期记忆
        self.memory.add_to_short_term(
            session_id=session_id,
            content={"role": "user", "content": message},
            importance=0.5,
        )

        # 添加助手回复到短期记忆（确保对话历史完整）
        if assistant_response:
            self.memory.add_to_short_term(
                session_id=session_id,
                content={"role": "assistant", "content": assistant_response},
                importance=0.5,
            )

        # 提取并更新用户兴趣
        interests = self._extract_interests(message)
        profile = self.memory.get_or_create_profile(user_id, self.user_type)
        for interest in interests:
            profile.update_interest(interest, 0.1)

        # 更新用户上下文（装修阶段、痛点等）
        await self._update_user_context(user_id, message)

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

    def _detect_decoration_stage(self, text: str) -> Optional[str]:
        """
        从用户消息中检测装修阶段

        Args:
            text: 用户消息

        Returns:
            检测到的装修阶段，如果无法检测则返回None
        """
        stage_keywords = {
            "准备": ["准备装修", "打算装修", "想装修", "要装修", "计划装修", "还没开始", "刚买房"],
            "设计": ["设计方案", "设计师", "效果图", "量房", "出图", "设计中", "在设计"],
            "施工": ["施工中", "在装修", "正在装", "水电", "贴砖", "刷漆", "吊顶", "工人"],
            "软装": ["软装", "买家具", "选家具", "窗帘", "灯具", "快完工", "硬装完"],
            "入住": ["入住", "搬家", "通风", "甲醛", "装完了", "已经装好"],
        }

        for stage, keywords in stage_keywords.items():
            for kw in keywords:
                if kw in text:
                    return stage

        return None

    def _detect_pain_points(self, text: str) -> List[Dict]:
        """
        从用户消息中检测痛点

        Args:
            text: 用户消息

        Returns:
            检测到的痛点列表
        """
        pain_patterns = {
            "预算": {
                "keywords": ["超预算", "预算不够", "太贵", "花太多", "控制预算", "省钱"],
                "severity": 0.8
            },
            "质量": {
                "keywords": ["质量差", "有问题", "不满意", "返工", "空鼓", "开裂", "漏水"],
                "severity": 0.9
            },
            "工期": {
                "keywords": ["太慢", "延期", "拖延", "什么时候完", "等太久"],
                "severity": 0.6
            },
            "选择困难": {
                "keywords": ["不知道选", "选哪个", "纠结", "怎么选", "哪个好"],
                "severity": 0.5
            },
            "沟通": {
                "keywords": ["沟通不畅", "不理人", "联系不上", "态度差"],
                "severity": 0.7
            },
        }

        detected = []
        for pain_type, config in pain_patterns.items():
            for kw in config["keywords"]:
                if kw in text:
                    detected.append({
                        "type": pain_type,
                        "description": f"用户提到: {kw}",
                        "severity": config["severity"]
                    })
                    break  # 每种类型只记录一次

        return detected

    async def _update_user_context(self, user_id: str, message: str):
        """
        根据用户消息更新用户上下文

        包括装修阶段、痛点等信息的自动检测和更新
        """
        profile = self.memory.get_or_create_profile(user_id, self.user_type)

        # 检测装修阶段
        detected_stage = self._detect_decoration_stage(message)
        if detected_stage and detected_stage != profile.decoration_stage:
            profile.update_decoration_stage(detected_stage)

        # 检测痛点
        detected_pains = self._detect_pain_points(message)
        for pain in detected_pains:
            profile.record_pain_point(
                pain_type=pain["type"],
                description=pain["description"],
                severity=pain["severity"]
            )

        # 保存更新
        if self.memory._profile_store:
            self.memory._profile_store._dirty = True

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

    # === 推理监控接口 ===

    def get_reasoning_statistics(self) -> Dict:
        """获取推理策略统计"""
        return self.adaptive_strategy.get_statistics()

    def record_user_feedback(self, query: str, reasoning_type: ReasoningType,
                             feedback_score: float):
        """
        记录用户反馈，用于优化推理策略

        Args:
            query: 原始查询
            reasoning_type: 使用的推理类型
            feedback_score: 用户反馈评分 (0-1)
        """
        self.adaptive_strategy.record_result(
            query=query,
            reasoning_type=reasoning_type,
            success=feedback_score >= 0.5,
            user_feedback=feedback_score
        )
