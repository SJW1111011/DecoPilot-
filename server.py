import uvicorn
import sys
import os
from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
import json

# 添加backend目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "backend"))

from rag import RagService

# 导入新的API路由
try:
    from backend.api.routes import chat_router, knowledge_router, merchant_router
    from backend.api.middleware.rate_limit import limiter, get_rate_limit_handler, SLOWAPI_AVAILABLE
    NEW_API_AVAILABLE = True
except ImportError as e:
    print(f"警告: 新API模块导入失败: {e}")
    NEW_API_AVAILABLE = False
    SLOWAPI_AVAILABLE = False

app = FastAPI(
    title="DecoPilot API",
    description="家居行业智能体API服务",
    version="1.0.0",
)

# 配置限流（如果可用）
if NEW_API_AVAILABLE and SLOWAPI_AVAILABLE and limiter:
    from slowapi import _rate_limit_exceeded_handler
    from slowapi.errors import RateLimitExceeded
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# 允许跨域 (方便前端开发时调试)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册新的API路由
if NEW_API_AVAILABLE:
    app.include_router(chat_router, prefix="/api/v1")
    app.include_router(knowledge_router, prefix="/api/v1")
    app.include_router(merchant_router, prefix="/api/v1")

# 初始化 RAG 服务（保留原有接口向后兼容）
rag_service = RagService()

@app.post("/chat_stream")
async def chat_stream(request: Request):
    data = await request.json()
    message = data.get("message")
    
    # 更新 RAG 配置
    rag_service.enable_search = data.get("enable_search", True)
    rag_service.show_thinking = data.get("show_thinking", True)

    async def event_generator():
        session_config = {"configurable": {"session_id": "user_react_001"}}
        input_data = {"input": message}
        
        try:
            # 使用 astream_events 监听所有事件
            async for event in rag_service.chain.astream_events(input_data, session_config, version="v1"):
                kind = event["event"]
                
                # 1. 捕获检索结束事件 (获取思考过程)
                if kind == "on_retriever_end":
                    # event["data"]["output"] 是 Document 列表
                    if "output" in event["data"]:
                        docs = event["data"]["output"]
                        if docs:
                            # 检查是否有 thinking_log
                            first_doc = docs[0]
                            if hasattr(first_doc, "metadata") and "thinking_log" in first_doc.metadata:
                                logs = first_doc.metadata["thinking_log"]
                                yield json.dumps({"type": "thinking", "content": logs}, ensure_ascii=False) + "\n"
                            
                # 2. 捕获模型生成的答案流
                elif kind == "on_chat_model_stream":
                    chunk = event["data"]["chunk"]
                    if hasattr(chunk, "content") and chunk.content:
                        yield json.dumps({"type": "answer", "content": chunk.content}, ensure_ascii=False) + "\n"
        except Exception as e:
            yield json.dumps({"type": "error", "content": str(e)}, ensure_ascii=False) + "\n"

    return StreamingResponse(event_generator(), media_type="application/x-ndjson")


@app.get("/")
async def root():
    """API根路径，返回服务信息"""
    return {
        "service": "DecoPilot API",
        "version": "1.0.0",
        "description": "家居行业智能体API服务",
        "endpoints": {
            "legacy": {
                "/chat_stream": "原有聊天接口（向后兼容）",
            },
            "v1": {
                "/api/v1/chat/stream": "通用聊天流式接口",
                "/api/v1/chat/c-end": "C端专用聊天接口",
                "/api/v1/chat/b-end": "B端专用聊天接口",
                "/api/v1/knowledge/collections": "知识库集合列表",
                "/api/v1/knowledge/search": "知识库搜索",
                "/api/v1/merchant/recommend": "商家推荐",
                "/api/v1/merchant/subsidy/calc": "补贴计算",
                "/api/v1/merchant/roi/analyze": "ROI分析",
            },
        },
        "docs": "/docs",
    }


@app.get("/health")
async def health_check():
    """健康检查接口"""
    return {"status": "healthy", "service": "DecoPilot"}


if __name__ == "__main__":
    print("Server running at http://localhost:8000")
    print("API文档: http://localhost:8000/docs")
    uvicorn.run(app, host="0.0.0.0", port=8000)
