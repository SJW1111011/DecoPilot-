# -*- coding: utf-8 -*-
"""
框架聊天 API 路由

使用新框架的智能体处理聊天请求
"""

import os
import sys
import json
import time
from typing import Optional

from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

from backend.framework.integration import (
    get_chat_adapter,
    FrameworkChatAdapter,
)
from backend.framework.integration.api_adapter import ChatContext

router = APIRouter(prefix="/chat/v2", tags=["聊天V2"])


class ChatRequestV2(BaseModel):
    """聊天请求模型 V2"""
    message: str
    session_id: Optional[str] = None
    user_id: Optional[str] = None
    user_type: Optional[str] = "c_end"
    enable_search: bool = True
    show_thinking: bool = True
    user_context: Optional[dict] = None


class ToolCallRequest(BaseModel):
    """工具调用请求"""
    tool_name: str
    params: dict
    user_type: Optional[str] = "c_end"


# 延迟初始化适配器
_adapter: Optional[FrameworkChatAdapter] = None
_initialized = False


async def get_adapter() -> FrameworkChatAdapter:
    """获取并初始化适配器"""
    global _adapter, _initialized
    if _adapter is None:
        _adapter = get_chat_adapter()
    if not _initialized:
        await _adapter.initialize()
        _initialized = True
    return _adapter


@router.post("/stream")
async def chat_stream_v2(request: ChatRequestV2):
    """
    流式聊天接口 V2

    使用新框架的智能体处理请求
    """
    adapter = await get_adapter()

    # 构建上下文
    context = ChatContext(
        session_id=request.session_id or f"session_{int(time.time())}",
        user_id=request.user_id or f"user_{int(time.time())}",
        user_type=request.user_type or "c_end",
        enable_search=request.enable_search,
        show_thinking=request.show_thinking,
        user_context=request.user_context,
    )

    async def event_generator():
        async for event in adapter.chat_stream(request.message, context):
            yield event

    return StreamingResponse(event_generator(), media_type="application/x-ndjson")


@router.post("/c-end")
async def chat_c_end_v2(request: ChatRequestV2):
    """
    C端专用聊天接口 V2

    面向业主用户，提供装修咨询、补贴政策、商家推荐等服务
    """
    request.user_type = "c_end"
    return await chat_stream_v2(request)


@router.post("/b-end")
async def chat_b_end_v2(request: ChatRequestV2):
    """
    B端专用聊天接口 V2

    面向商家用户，提供入驻指导、数据产品咨询、获客策略等服务
    """
    request.user_type = "b_end"
    return await chat_stream_v2(request)


@router.post("/sync")
async def chat_sync(request: ChatRequestV2):
    """
    非流式聊天接口

    返回完整的响应，适合不需要流式输出的场景
    """
    adapter = await get_adapter()

    # 构建上下文
    context = ChatContext(
        session_id=request.session_id or f"session_{int(time.time())}",
        user_id=request.user_id or f"user_{int(time.time())}",
        user_type=request.user_type or "c_end",
        enable_search=request.enable_search,
        show_thinking=request.show_thinking,
        user_context=request.user_context,
    )

    result = await adapter.chat(request.message, context)
    return result


@router.post("/tool")
async def call_tool(request: ToolCallRequest):
    """
    工具调用接口

    直接调用智能体的工具
    """
    adapter = await get_adapter()

    result = await adapter.call_tool(
        tool_name=request.tool_name,
        params=request.params,
        user_type=request.user_type,
    )

    return result


@router.get("/tools")
async def list_tools(user_type: str = "c_end"):
    """
    列出可用工具

    返回指定用户类型的智能体可用的工具列表
    """
    adapter = await get_adapter()

    # 获取智能体
    agent = await adapter._get_agent(user_type)

    # 获取工具列表
    tools = agent.list_tools()

    return {
        "user_type": user_type,
        "tools": [
            {
                "name": t.name,
                "description": t.description,
                "category": t.category.value,
                "parameters": [
                    {
                        "name": p.name,
                        "type": p.type,
                        "description": p.description,
                        "required": p.required,
                    }
                    for p in t.parameters
                ],
            }
            for t in tools
        ],
    }


@router.get("/health")
async def health_check():
    """
    健康检查

    检查框架组件状态
    """
    try:
        adapter = await get_adapter()

        return {
            "status": "healthy",
            "framework_version": "2.0.0",
            "adapter_initialized": _initialized,
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e),
        }
