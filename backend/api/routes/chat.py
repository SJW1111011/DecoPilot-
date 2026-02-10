"""
聊天API路由
提供通用聊天、C端聊天、B端聊天接口
"""
import os
import sys
import json
import base64
import tempfile
import time
from typing import Optional, List

from fastapi import APIRouter, Request, Depends, UploadFile, File, Form, HTTPException
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
from backend.core.multimodal import (
    get_multimodal_manager, MediaContent, MediaType,
    ImageAnalysisType, ImageAnalysisResult
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
        try:
            async for event in agent.process(request.message, session_id):
                yield event

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


@router.post("/analyze-image")
async def analyze_image(
    file: UploadFile = File(...),
    message: str = Form(""),
    analysis_type: str = Form("style"),
    session_id: Optional[str] = Form(None),
    user_type: str = Form("c_end"),
):
    """
    图片分析接口

    支持装修风格识别、空间布局分析、材质识别等

    analysis_type 可选值:
    - style: 装修风格识别
    - material: 材质识别
    - furniture: 家具识别
    - defect: 缺陷检测
    - general: 通用分析
    """
    # 验证文件类型
    content_type = file.content_type or ""
    if not content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="仅支持图片文件")

    # 读取图片内容
    image_data = await file.read()

    # 获取多模态管理器
    mm_manager = get_multimodal_manager()

    # 映射分析类型
    analysis_type_map = {
        "style": ImageAnalysisType.DECORATION_STYLE,
        "material": ImageAnalysisType.MATERIAL,
        "furniture": ImageAnalysisType.FURNITURE,
        "defect": ImageAnalysisType.DEFECT,
        "measurement": ImageAnalysisType.MEASUREMENT,
        "general": ImageAnalysisType.GENERAL,
    }

    img_analysis_type = analysis_type_map.get(analysis_type, ImageAnalysisType.GENERAL)

    # 创建 MediaContent 对象
    media_content = MediaContent(
        media_type=MediaType.IMAGE,
        content=image_data,
        filename=file.filename,
        mime_type=content_type,
    )

    # 分析图片 - 如果有用户问题，传递给模型
    if message:
        result = mm_manager.image_processor.analyze(
            media_content,
            img_analysis_type,
            custom_prompt=message
        )
    else:
        result = mm_manager.image_processor.analyze(media_content, img_analysis_type)

    # 构建响应
    response_data = {
        "success": True,
        "analysis_type": analysis_type,
        "filename": file.filename,
        "result": {
            "description": result.description,
            "style_tags": result.style_tags,
            "colors": result.colors,
            "detected_objects": result.detected_objects,
            "suggestions": result.suggestions,
            "confidence": result.confidence,
        }
    }

    return response_data


@router.post("/analyze-document")
async def analyze_document(
    file: UploadFile = File(...),
    message: str = Form(""),
    session_id: Optional[str] = Form(None),
    user_type: str = Form("c_end"),
):
    """
    文档分析接口

    支持 PDF 和文本文件的解析和分析
    """
    filename = file.filename.lower() if file.filename else ""

    # 验证文件类型
    if not (filename.endswith(".pdf") or filename.endswith(".txt")):
        raise HTTPException(status_code=400, detail="仅支持 PDF 和 TXT 文件")

    # 读取文件内容
    content = await file.read()

    # 获取多模态管理器
    mm_manager = get_multimodal_manager()

    # 创建 MediaContent 对象
    if filename.endswith(".pdf"):
        media_content = MediaContent(
            media_type=MediaType.PDF,
            content=content,
            filename=file.filename,
            mime_type="application/pdf",
        )
    else:
        media_content = MediaContent(
            media_type=MediaType.DOCUMENT,
            content=content,
            filename=file.filename,
            mime_type="text/plain",
        )

    # 解析文档
    result = mm_manager.document_processor.parse(media_content)
    tables = mm_manager.document_processor.extract_tables(media_content)

    # 如果有用户问题，结合文档内容生成回答
    answer = None
    if message and result.text:
        # 同步获取回答（简化处理）
        answer = f"已解析文档 {file.filename}，共 {result.pages} 页。"
        if message:
            answer += f"\n\n关于您的问题「{message}」，请查看文档内容后进一步咨询。"

    return {
        "success": True,
        "filename": file.filename,
        "pages": result.pages,
        "text_preview": result.text[:500] + "..." if len(result.text) > 500 else result.text,
        "tables_count": len(tables),
        "answer": answer,
    }


@router.post("/chat-with-media")
async def chat_with_media(
    file: UploadFile = File(...),
    message: str = Form(""),
    session_id: Optional[str] = Form(None),
    user_type: str = Form("c_end"),
    enable_search: bool = Form(True),
    show_thinking: bool = Form(True),
):
    """
    带媒体文件的聊天接口

    支持图片和文档，自动识别类型并处理

    架构设计：
    1. 视觉模型只负责分析图片/文档，生成描述
    2. 将描述 + 用户问题发送给智能体
    3. 智能体用自然语言回答，结合知识库、记忆系统等
    """
    content_type = file.content_type or ""
    filename = file.filename.lower() if file.filename else ""

    # 判断文件类型
    if content_type.startswith("image/"):
        # 图片分析
        file_content = await file.read()

        # 获取多模态管理器
        mm_manager = get_multimodal_manager()

        # 创建 MediaContent 对象
        media_content = MediaContent(
            media_type=MediaType.IMAGE,
            content=file_content,
            filename=file.filename,
            mime_type=content_type,
        )

        # 第一步：使用视觉模型分析图片，获取图片描述
        image_result = mm_manager.image_processor.analyze(media_content, ImageAnalysisType.GENERAL)
        image_description = image_result.description

        # 第二步：构建发送给智能体的消息
        if message:
            # 有用户问题
            enhanced_message = f"""[用户上传了一张图片]

图片分析结果：
{image_description}

用户问题：{message}

请根据图片内容和用户的问题给出回答。"""
        else:
            # 没有用户问题，让智能体友好地描述图片并给出建议
            enhanced_message = f"""[用户上传了一张图片，请帮助分析]

图片分析结果：
{image_description}

请用友好、自然的语言向用户描述这张图片的内容，并根据图片内容给出一些有用的建议或引导用户可以问什么问题。

注意：
1. 不要直接输出技术性的分析数据
2. 用对话的方式描述图片
3. 如果是装修相关的图片，可以分析风格、给出建议
4. 最后可以引导用户提出具体问题"""

        # 选择智能体
        if user_type == "c_end":
            agent = get_c_end_agent()
        else:
            agent = get_b_end_agent()

        agent.enable_search = enable_search
        agent.show_thinking = show_thinking

        # 使用智能体处理（流式响应）
        active_id = session_id or f"{user_type}_{int(time.time())}"

        async def agent_stream():
            try:
                async for event in agent.process(enhanced_message, active_id):
                    yield event
            except Exception as e:
                yield json.dumps({"type": "error", "content": str(e)}, ensure_ascii=False) + "\n"

        return StreamingResponse(agent_stream(), media_type="application/x-ndjson")
    elif filename.endswith(".pdf") or filename.endswith(".txt"):
        # 文档分析
        file_content = await file.read()

        # 获取多模态管理器
        mm_manager = get_multimodal_manager()

        # 创建 MediaContent 对象
        if filename.endswith(".pdf"):
            media_content = MediaContent(
                media_type=MediaType.PDF,
                content=file_content,
                filename=file.filename,
                mime_type="application/pdf",
            )
        else:
            media_content = MediaContent(
                media_type=MediaType.DOCUMENT,
                content=file_content,
                filename=file.filename,
                mime_type="text/plain",
            )

        # 解析文档
        result = mm_manager.document_processor.parse(media_content)
        tables = mm_manager.document_processor.extract_tables(media_content)

        # 构建发送给智能体的消息
        doc_preview = result.text[:3000]  # 限制文档长度

        if message:
            # 有用户问题
            enhanced_message = f"""[用户上传了一个文档]

文档名称：{file.filename}
文档页数：{result.pages}
表格数量：{len(tables)}

文档内容摘要：
{doc_preview}

用户问题：{message}

请根据文档内容和用户的问题给出回答。"""
        else:
            # 没有用户问题，让智能体友好地总结文档
            enhanced_message = f"""[用户上传了一个文档，请帮助分析]

文档名称：{file.filename}
文档页数：{result.pages}
表格数量：{len(tables)}

文档内容：
{doc_preview}

请用友好、自然的语言向用户总结这个文档的主要内容，并根据文档类型给出一些有用的建议或引导用户可以问什么问题。

注意：
1. 用对话的方式描述文档内容
2. 提取文档中的关键信息
3. 如果是报价单、合同等，可以帮助用户理解重点
4. 最后可以引导用户提出具体问题"""

        # 选择智能体
        if user_type == "c_end":
            agent = get_c_end_agent()
        else:
            agent = get_b_end_agent()

        agent.enable_search = enable_search
        agent.show_thinking = show_thinking

        # 使用智能体处理（流式响应）
        active_id = session_id or f"{user_type}_{int(time.time())}"

        async def agent_stream():
            try:
                async for event in agent.process(enhanced_message, active_id):
                    yield event
            except Exception as e:
                yield json.dumps({"type": "error", "content": str(e)}, ensure_ascii=False) + "\n"

        return StreamingResponse(agent_stream(), media_type="application/x-ndjson")
    else:
        raise HTTPException(
            status_code=400,
            detail="不支持的文件类型，请上传图片（JPG/PNG）或文档（PDF/TXT）"
        )
