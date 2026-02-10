# -*- coding: utf-8 -*-
"""
API 适配器

将新框架的智能体适配到现有的 API 接口
"""

import json
import logging
import asyncio
from typing import AsyncGenerator, Dict, Any, Optional
from dataclasses import dataclass

from .agent_factory import get_agent_factory, AgentFactory
from ..runtime import AgentRuntime
from ..capabilities.output import StreamChunk

logger = logging.getLogger(__name__)


@dataclass
class ChatContext:
    """聊天上下文"""
    session_id: str
    user_id: str
    user_type: str
    enable_search: bool = True
    show_thinking: bool = True
    user_context: Optional[Dict[str, Any]] = None


class FrameworkChatAdapter:
    """
    框架聊天适配器

    将新框架的智能体适配到现有的 API 接口格式
    """

    def __init__(self, factory: AgentFactory = None):
        self._factory = factory or get_agent_factory()
        self._initialized = False

    async def initialize(self) -> None:
        """初始化适配器"""
        if self._initialized:
            return

        await self._factory.initialize()
        self._initialized = True
        logger.info("Chat adapter initialized")

    async def chat_stream(
        self,
        message: str,
        context: ChatContext
    ) -> AsyncGenerator[str, None]:
        """
        流式聊天

        Args:
            message: 用户消息
            context: 聊天上下文

        Yields:
            JSON 格式的事件字符串
        """
        # 获取智能体
        agent = await self._get_agent(context.user_type)

        # 发送流开始标记
        yield self._format_event("stream_start", {
            "session_id": context.session_id,
            "user_type": context.user_type,
        })

        try:
            # 处理请求
            result = await agent.process(
                message=message,
                session_id=context.session_id,
                user_id=context.user_id,
                context=context.user_context
            )

            # 输出思考过程
            if context.show_thinking and result.thinking_logs:
                yield self._format_event("thinking", result.thinking_logs)

            # 输出引用来源
            if result.sources:
                yield self._format_event("sources", result.sources)

            # 输出结构化数据
            if result.structured_outputs:
                for output in result.structured_outputs:
                    yield self._format_event("structured", output)

            # 输出工具调用结果
            if result.tool_results:
                for tool_result in result.tool_results:
                    if tool_result.success:
                        yield self._format_event("tool_result", {
                            "tool_name": tool_result.tool_name,
                            "result": tool_result.result,
                        })

            # 流式输出回答
            # 模拟流式输出（将回答分块发送）
            answer = result.answer
            chunk_size = 20  # 每次发送的字符数

            for i in range(0, len(answer), chunk_size):
                chunk = answer[i:i + chunk_size]
                yield self._format_event("answer", chunk)
                await asyncio.sleep(0.01)  # 模拟流式延迟

            # 发送流结束标记
            yield self._format_event("stream_end", {
                "session_id": context.session_id,
            })

        except Exception as e:
            logger.error(f"Chat stream error: {e}", exc_info=True)
            yield self._format_event("error", {
                "message": str(e),
                "code": "STREAM_ERROR",
            })
            yield self._format_event("stream_end", {
                "session_id": context.session_id,
            })

    async def chat_stream_v2(
        self,
        message: str,
        context: ChatContext
    ) -> AsyncGenerator[str, None]:
        """
        流式聊天 V2 - 使用框架的原生流式输出

        Args:
            message: 用户消息
            context: 聊天上下文

        Yields:
            JSON 格式的事件字符串
        """
        # 获取智能体
        agent = await self._get_agent(context.user_type)

        # 发送流开始标记
        yield self._format_event("stream_start", {
            "session_id": context.session_id,
            "user_type": context.user_type,
        })

        try:
            # 使用框架的流式处理
            async for chunk in agent.process_stream(
                message=message,
                session_id=context.session_id,
                user_id=context.user_id,
                context=context.user_context
            ):
                # 转换 chunk 类型到 API 事件
                event_type = self._map_chunk_type(chunk.type)
                yield self._format_event(event_type, chunk.content)

            # 发送流结束标记
            yield self._format_event("stream_end", {
                "session_id": context.session_id,
            })

        except Exception as e:
            logger.error(f"Chat stream v2 error: {e}", exc_info=True)
            yield self._format_event("error", {
                "message": str(e),
                "code": "STREAM_ERROR",
            })
            yield self._format_event("stream_end", {
                "session_id": context.session_id,
            })

    async def chat(
        self,
        message: str,
        context: ChatContext
    ) -> Dict[str, Any]:
        """
        非流式聊天

        Args:
            message: 用户消息
            context: 聊天上下文

        Returns:
            聊天响应
        """
        # 获取智能体
        agent = await self._get_agent(context.user_type)

        try:
            # 处理请求
            result = await agent.process(
                message=message,
                session_id=context.session_id,
                user_id=context.user_id,
                context=context.user_context
            )

            return {
                "success": True,
                "answer": result.answer,
                "thinking_log": result.thinking_logs if context.show_thinking else None,
                "sources": result.sources,
                "structured_outputs": result.structured_outputs,
                "tool_results": [
                    {
                        "tool_name": r.tool_name,
                        "success": r.success,
                        "result": r.result,
                    }
                    for r in result.tool_results
                ],
                "session_id": context.session_id,
            }

        except Exception as e:
            logger.error(f"Chat error: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e),
                "session_id": context.session_id,
            }

    async def call_tool(
        self,
        tool_name: str,
        params: Dict[str, Any],
        user_type: str = "c_end"
    ) -> Dict[str, Any]:
        """
        调用工具

        Args:
            tool_name: 工具名称
            params: 工具参数
            user_type: 用户类型

        Returns:
            工具调用结果
        """
        agent = await self._get_agent(user_type)

        try:
            result = await agent.call_tool(tool_name, params)
            return {
                "success": result.success,
                "tool_name": result.tool_name,
                "result": result.result,
                "error": result.error,
                "execution_time": result.execution_time,
            }
        except Exception as e:
            logger.error(f"Tool call error: {e}", exc_info=True)
            return {
                "success": False,
                "tool_name": tool_name,
                "error": str(e),
            }

    async def _get_agent(self, user_type: str) -> AgentRuntime:
        """获取智能体"""
        if user_type == "c_end":
            return await self._factory.get_or_create("c_end_default", "c_end")
        elif user_type == "b_end":
            return await self._factory.get_or_create("b_end_default", "b_end")
        else:
            return await self._factory.get_or_create("general_default", "general")

    def _format_event(self, event_type: str, content: Any) -> str:
        """格式化事件为 JSON 字符串"""
        return json.dumps({
            "type": event_type,
            "content": content,
        }, ensure_ascii=False) + "\n"

    def _map_chunk_type(self, chunk_type: str) -> str:
        """映射 chunk 类型到 API 事件类型"""
        mapping = {
            "thinking": "thinking",
            "answer": "answer",
            "sources": "sources",
            "structured": "structured",
            "tool_call": "tool_result",
            "error": "error",
            "stream_end": "stream_end",
            "stream_start": "stream_start",
        }
        return mapping.get(chunk_type, chunk_type)

    async def shutdown(self) -> None:
        """关闭适配器"""
        await self._factory.shutdown()
        self._initialized = False


# 全局适配器实例
_adapter: Optional[FrameworkChatAdapter] = None


def get_chat_adapter() -> FrameworkChatAdapter:
    """获取全局适配器实例"""
    global _adapter
    if _adapter is None:
        _adapter = FrameworkChatAdapter()
    return _adapter
