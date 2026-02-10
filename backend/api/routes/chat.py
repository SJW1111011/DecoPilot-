"""
聊天API路由
提供通用聊天、C端聊天、B端聊天接口
"""
import os
import sys
import json
from typing import Optional

from fastapi import APIRouter, Request, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

from backend.agents.c_end_agent import CEndAgent
from backend.agents.b_end_agent import BEndAgent
from backend.api.middleware.auth import get_current_user, require_user_type
from backend.core.output_formatter import (
    OutputFormatter, OutputType, Source,
    QuickReply, create_decoration_process
)
from rag import RagService

router = APIRouter(prefix="/chat", tags=["聊天"])


class ChatRequest(BaseModel):
    """聊天请求模型"""
    message: str
    session_id: Optional[str] = None
    user_type: Optional[str] = "both"
    enable_search: bool = True
    show_thinking: bool = True
    user_context: Optional[dict] = None


class ChatResponse(BaseModel):
    """聊天响应模型"""
    answer: str
    thinking_log: Optional[list] = None
    session_id: str


# 初始化智能体（延迟加载）
_c_end_agent = None
_b_end_agent = None
_rag_service = None


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


def get_rag_service(user_type: str = "both"):
    global _rag_service
    if _rag_service is None or _rag_service.user_type != user_type:
        _rag_service = RagService(user_type=user_type)
    return _rag_service


@router.post("/stream")
async def chat_stream(request: ChatRequest):
    """
    通用聊天流式接口

    根据user_type自动路由到对应的智能体
    """
    user_type = request.user_type or "both"
    session_id = request.session_id or f"user_{user_type}_001"

    # 创建输出格式化器
    formatter = OutputFormatter(session_id, user_type)

    # 根据用户类型选择智能体
    if user_type == "c_end":
        agent = get_c_end_agent()
    elif user_type == "b_end":
        agent = get_b_end_agent()
    else:
        # 使用通用RAG服务
        rag = get_rag_service(user_type)
        rag.enable_search = request.enable_search
        rag.show_thinking = request.show_thinking

        async def event_generator():
            # 发送流开始标记
            yield formatter.stream_start()

            session_config = {"configurable": {"session_id": session_id}}
            input_data = {"input": request.message}

            try:
                async for event in rag.chain.astream_events(input_data, session_config, version="v1"):
                    kind = event["event"]

                    if kind == "on_retriever_end":
                        if "output" in event["data"]:
                            docs = event["data"]["output"]
                            if docs:
                                # 输出思考过程
                                if hasattr(docs[0], "metadata") and "thinking_log" in docs[0].metadata:
                                    logs = docs[0].metadata["thinking_log"]
                                    yield formatter.thinking(logs)

                                # 输出引用来源
                                sources = []
                                for doc in docs[:3]:  # 最多3个来源
                                    if hasattr(doc, "metadata"):
                                        sources.append(Source(
                                            title=doc.metadata.get("source", "未知来源"),
                                            content=doc.page_content[:200] + "..." if len(doc.page_content) > 200 else doc.page_content,
                                            collection=doc.metadata.get("collection", "unknown"),
                                            relevance_score=doc.metadata.get("score", 0.0),
                                        ))
                                if sources:
                                    yield formatter.sources(sources)

                    elif kind == "on_chat_model_stream":
                        chunk = event["data"]["chunk"]
                        if hasattr(chunk, "content") and chunk.content:
                            yield formatter.answer(chunk.content)

                # 发送流结束标记
                yield formatter.stream_end()

            except Exception as e:
                yield formatter.error(str(e), "STREAM_ERROR")
                yield formatter.stream_end()

        return StreamingResponse(event_generator(), media_type="application/x-ndjson")

    # 使用专用智能体
    agent.enable_search = request.enable_search
    agent.show_thinking = request.show_thinking

    async def agent_event_generator():
        # 发送流开始标记
        yield formatter.stream_start()

        try:
            async for event in agent.astream(request.message, session_id):
                kind = event["event"]

                if kind == "on_retriever_end":
                    if "output" in event["data"]:
                        docs = event["data"]["output"]
                        if docs:
                            # 输出思考过程
                            if hasattr(docs[0], "metadata") and "thinking_log" in docs[0].metadata:
                                logs = docs[0].metadata["thinking_log"]
                                yield formatter.thinking(logs)

                            # 输出引用来源
                            sources = []
                            for doc in docs[:3]:
                                if hasattr(doc, "metadata"):
                                    sources.append(Source(
                                        title=doc.metadata.get("source", "未知来源"),
                                        content=doc.page_content[:200] + "..." if len(doc.page_content) > 200 else doc.page_content,
                                        collection=doc.metadata.get("collection", "unknown"),
                                        relevance_score=doc.metadata.get("score", 0.0),
                                    ))
                            if sources:
                                yield formatter.sources(sources)

                elif kind == "on_chat_model_stream":
                    chunk = event["data"]["chunk"]
                    if hasattr(chunk, "content") and chunk.content:
                        yield formatter.answer(chunk.content)

            # 发送流结束标记
            yield formatter.stream_end()

        except Exception as e:
            yield formatter.error(str(e), "AGENT_ERROR")
            yield formatter.stream_end()

    return StreamingResponse(agent_event_generator(), media_type="application/x-ndjson")


@router.post("/c-end")
async def chat_c_end(request: ChatRequest):
    """
    C端专用聊天接口

    面向业主用户，提供装修咨询、补贴政策、商家推荐等服务
    """
    request.user_type = "c_end"
    return await chat_stream(request)


@router.post("/b-end")
async def chat_b_end(request: ChatRequest):
    """
    B端专用聊天接口

    面向商家用户，提供入驻指导、数据产品咨询、获客策略等服务
    """
    request.user_type = "b_end"
    return await chat_stream(request)
