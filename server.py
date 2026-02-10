"""
DecoPilot API 服务器
家居行业智能体API服务
"""
import uvicorn
import sys
import os
import time
import uuid
from typing import List
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import StreamingResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
import json

# 添加backend目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "backend"))

from rag import RagService

# 导入日志系统
try:
    from backend.core.logging_config import get_logger, log_execution
    logger = get_logger("server")
except ImportError:
    import logging
    logger = logging.getLogger(__name__)
    def log_execution(*args, **kwargs):
        def decorator(func):
            return func
        return decorator

# 导入安全模块
try:
    from backend.core.security import InputSanitizer
    sanitizer = InputSanitizer()
    SECURITY_AVAILABLE = True
except ImportError:
    SECURITY_AVAILABLE = False
    sanitizer = None

# 导入异步工具
try:
    from backend.core.async_utils import get_async_executor
    ASYNC_UTILS_AVAILABLE = True
except ImportError:
    ASYNC_UTILS_AVAILABLE = False

# 导入记忆系统
try:
    from backend.core.memory import get_memory_manager
    MEMORY_AVAILABLE = True
except ImportError:
    MEMORY_AVAILABLE = False

# 导入新的API路由
try:
    from backend.api.routes import chat_router, knowledge_router, merchant_router
    from backend.api.middleware.rate_limit import limiter, get_rate_limit_handler, SLOWAPI_AVAILABLE
    NEW_API_AVAILABLE = True
except ImportError as e:
    logger.warning(f"新API模块导入失败: {e}")
    NEW_API_AVAILABLE = False
    SLOWAPI_AVAILABLE = False


# === 环境配置 ===

# 运行环境
ENV = os.getenv("ENV", "development")  # development / production
DEBUG = os.getenv("DEBUG", "true").lower() == "true"

# CORS 配置
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "*").split(",")
if ENV == "production" and CORS_ORIGINS == ["*"]:
    # 生产环境默认只允许同源
    CORS_ORIGINS = []

# 可信主机
TRUSTED_HOSTS = os.getenv("TRUSTED_HOSTS", "*").split(",")


# === 性能监控 ===

class RequestMetrics:
    """请求性能指标收集器"""

    def __init__(self):
        self._metrics = {
            "total_requests": 0,
            "total_errors": 0,
            "endpoint_stats": {},
            "response_times": [],
            "active_requests": 0,
        }
        self._lock = __import__("threading").Lock()
        self._max_response_times = 1000  # 保留最近1000个响应时间

    def record_request(self, path: str, method: str, duration: float,
                       status_code: int, request_id: str = None):
        """记录请求指标"""
        with self._lock:
            self._metrics["total_requests"] += 1

            if status_code >= 400:
                self._metrics["total_errors"] += 1

            # 端点统计
            endpoint_key = f"{method}:{path}"
            if endpoint_key not in self._metrics["endpoint_stats"]:
                self._metrics["endpoint_stats"][endpoint_key] = {
                    "count": 0,
                    "errors": 0,
                    "total_time": 0,
                    "min_time": float("inf"),
                    "max_time": 0,
                }

            stats = self._metrics["endpoint_stats"][endpoint_key]
            stats["count"] += 1
            stats["total_time"] += duration
            stats["min_time"] = min(stats["min_time"], duration)
            stats["max_time"] = max(stats["max_time"], duration)

            if status_code >= 400:
                stats["errors"] += 1

            # 响应时间记录
            self._metrics["response_times"].append({
                "path": path,
                "duration": duration,
                "status": status_code,
                "timestamp": time.time(),
            })

            # 限制响应时间记录数量
            if len(self._metrics["response_times"]) > self._max_response_times:
                self._metrics["response_times"] = self._metrics["response_times"][-self._max_response_times:]

    def increment_active(self):
        """增加活跃请求数"""
        with self._lock:
            self._metrics["active_requests"] += 1

    def decrement_active(self):
        """减少活跃请求数"""
        with self._lock:
            self._metrics["active_requests"] -= 1

    def get_stats(self) -> dict:
        """获取统计信息"""
        with self._lock:
            # 计算平均响应时间
            recent_times = [r["duration"] for r in self._metrics["response_times"][-100:]]
            avg_response_time = sum(recent_times) / len(recent_times) if recent_times else 0

            # 计算 P95 响应时间
            sorted_times = sorted(recent_times)
            p95_index = int(len(sorted_times) * 0.95)
            p95_response_time = sorted_times[p95_index] if sorted_times else 0

            return {
                "total_requests": self._metrics["total_requests"],
                "total_errors": self._metrics["total_errors"],
                "error_rate": self._metrics["total_errors"] / self._metrics["total_requests"]
                              if self._metrics["total_requests"] > 0 else 0,
                "active_requests": self._metrics["active_requests"],
                "avg_response_time_ms": avg_response_time * 1000,
                "p95_response_time_ms": p95_response_time * 1000,
                "endpoint_stats": {
                    k: {
                        **v,
                        "avg_time_ms": (v["total_time"] / v["count"] * 1000) if v["count"] > 0 else 0,
                        "min_time_ms": v["min_time"] * 1000 if v["min_time"] != float("inf") else 0,
                        "max_time_ms": v["max_time"] * 1000,
                    }
                    for k, v in self._metrics["endpoint_stats"].items()
                },
            }


# 全局指标收集器
request_metrics = RequestMetrics()


# === 应用生命周期 ===

@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动时
    logger.info(f"DecoPilot 服务启动", extra={
        "env": ENV,
        "debug": DEBUG,
        "cors_origins": CORS_ORIGINS,
    })
    yield
    # 关闭时
    logger.info("DecoPilot 服务关闭")

    # 保存记忆系统数据
    if MEMORY_AVAILABLE:
        try:
            memory_manager = get_memory_manager()
            memory_manager.shutdown()
            logger.info("记忆系统数据已保存")
        except Exception as e:
            logger.error(f"保存记忆系统数据失败: {e}")

    # 关闭异步执行器
    if ASYNC_UTILS_AVAILABLE:
        try:
            executor = get_async_executor()
            executor.shutdown(wait=True)
            logger.info("异步执行器已关闭")
        except Exception as e:
            logger.error(f"关闭异步执行器失败: {e}")


# === 创建应用 ===

app = FastAPI(
    title="DecoPilot API",
    description="家居行业智能体API服务",
    version="2.0.0",
    lifespan=lifespan,
    docs_url="/docs" if DEBUG else None,  # 生产环境禁用文档
    redoc_url="/redoc" if DEBUG else None,
)


# === 中间件配置 ===

# 配置限流（如果可用）
if NEW_API_AVAILABLE and SLOWAPI_AVAILABLE and limiter:
    from slowapi import _rate_limit_exceeded_handler
    from slowapi.errors import RateLimitExceeded
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# 可信主机中间件（生产环境）
if ENV == "production" and TRUSTED_HOSTS != ["*"]:
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=TRUSTED_HOSTS,
    )

# CORS 中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS if CORS_ORIGINS != ["*"] else ["*"],
    allow_credentials=True if CORS_ORIGINS != ["*"] else False,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    max_age=600,  # 预检请求缓存10分钟
)


# === 全局异常处理 ===

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """全局异常处理器"""
    logger.error(f"未处理的异常", extra={
        "path": request.url.path,
        "method": request.method,
        "error": str(exc),
    }, exc_info=True)

    # 生产环境不暴露详细错误
    if ENV == "production":
        return JSONResponse(
            status_code=500,
            content={"detail": "服务器内部错误，请稍后重试"}
        )

    return JSONResponse(
        status_code=500,
        content={"detail": str(exc)}
    )


# === 请求验证中间件 ===

@app.middleware("http")
async def validate_request(request: Request, call_next):
    """请求验证中间件"""
    # 记录请求
    logger.debug(f"收到请求", extra={
        "path": request.url.path,
        "method": request.method,
        "client": request.client.host if request.client else "unknown",
    })

    # 对 POST 请求进行输入验证
    if request.method == "POST" and SECURITY_AVAILABLE and sanitizer:
        content_type = request.headers.get("content-type", "")
        if "application/json" in content_type:
            try:
                body = await request.body()
                if body:
                    data = json.loads(body)
                    # 验证 message 字段
                    if "message" in data:
                        result = sanitizer.sanitize(data["message"])
                        if result["blocked"]:
                            logger.warning(f"输入验证失败", extra={
                                "path": request.url.path,
                                "reason": result["block_reason"],
                                "warnings": result["warnings"],
                            })
                            return JSONResponse(
                                status_code=400,
                                content={"detail": result["block_reason"] or "输入内容不合规", "warnings": result["warnings"]}
                            )
            except json.JSONDecodeError:
                pass
            except Exception as e:
                logger.error(f"输入验证异常: {e}")

    response = await call_next(request)
    return response


# === 性能监控中间件 ===

@app.middleware("http")
async def performance_monitoring(request: Request, call_next):
    """性能监控中间件"""
    # 生成请求 ID
    request_id = str(uuid.uuid4())[:8]
    request.state.request_id = request_id

    # 记录开始时间
    start_time = time.time()
    request_metrics.increment_active()

    try:
        response = await call_next(request)
        duration = time.time() - start_time

        # 记录指标
        request_metrics.record_request(
            path=request.url.path,
            method=request.method,
            duration=duration,
            status_code=response.status_code,
            request_id=request_id,
        )

        # 添加响应头
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Response-Time"] = f"{duration * 1000:.2f}ms"

        # 慢请求警告
        if duration > 5.0:
            logger.warning(f"慢请求检测", extra={
                "request_id": request_id,
                "path": request.url.path,
                "duration_ms": duration * 1000,
            })

        return response

    except Exception as e:
        duration = time.time() - start_time
        request_metrics.record_request(
            path=request.url.path,
            method=request.method,
            duration=duration,
            status_code=500,
            request_id=request_id,
        )
        raise
    finally:
        request_metrics.decrement_active()


# === 注册路由 ===

if NEW_API_AVAILABLE:
    app.include_router(chat_router, prefix="/api/v1")
    app.include_router(knowledge_router, prefix="/api/v1")
    app.include_router(merchant_router, prefix="/api/v1")


# === 初始化 RAG 服务 ===

# 延迟初始化，避免启动时阻塞
_rag_service = None

def get_rag_service():
    global _rag_service
    if _rag_service is None:
        _rag_service = RagService()
    return _rag_service


# === 原有接口（向后兼容） ===

@app.post("/chat_stream")
@log_execution("chat_stream")
async def chat_stream(request: Request):
    """原有聊天接口（向后兼容）"""
    data = await request.json()
    message = data.get("message")

    if not message:
        raise HTTPException(status_code=400, detail="message 字段不能为空")

    rag_service = get_rag_service()
    rag_service.enable_search = data.get("enable_search", True)
    rag_service.show_thinking = data.get("show_thinking", True)

    async def event_generator():
        session_config = {"configurable": {"session_id": "user_react_001"}}
        input_data = {"input": message}

        try:
            async for event in rag_service.chain.astream_events(input_data, session_config, version="v1"):
                kind = event["event"]

                if kind == "on_retriever_end":
                    if "output" in event["data"]:
                        docs = event["data"]["output"]
                        if docs:
                            first_doc = docs[0]
                            if hasattr(first_doc, "metadata") and "thinking_log" in first_doc.metadata:
                                logs = first_doc.metadata["thinking_log"]
                                yield json.dumps({"type": "thinking", "content": logs}, ensure_ascii=False) + "\n"

                elif kind == "on_chat_model_stream":
                    chunk = event["data"]["chunk"]
                    if hasattr(chunk, "content") and chunk.content:
                        yield json.dumps({"type": "answer", "content": chunk.content}, ensure_ascii=False) + "\n"

        except Exception as e:
            logger.error(f"聊天流异常: {e}", exc_info=True)
            yield json.dumps({"type": "error", "content": str(e)}, ensure_ascii=False) + "\n"

    return StreamingResponse(event_generator(), media_type="application/x-ndjson")


# === 系统接口 ===

@app.get("/")
async def root():
    """API根路径，返回服务信息"""
    return {
        "service": "DecoPilot API",
        "version": "2.0.0",
        "env": ENV,
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
        "docs": "/docs" if DEBUG else None,
    }


@app.get("/health")
async def health_check():
    """健康检查接口"""
    return {
        "status": "healthy",
        "service": "DecoPilot",
        "version": "2.0.0",
        "env": ENV,
    }


@app.get("/metrics")
async def metrics():
    """性能指标接口（仅开发环境）"""
    if ENV == "production":
        raise HTTPException(status_code=404, detail="Not Found")

    result = {
        "request_metrics": request_metrics.get_stats(),
    }

    try:
        from backend.core.logging_config import get_perf_tracker
        result["performance"] = get_perf_tracker().get_all_stats()
    except ImportError:
        pass

    try:
        from backend.core.cache import get_cache_manager
        result["cache"] = get_cache_manager().get_all_stats()
    except ImportError:
        pass

    # 添加记忆系统统计
    if MEMORY_AVAILABLE:
        try:
            memory_manager = get_memory_manager()
            result["memory"] = memory_manager.get_stats()
        except Exception:
            pass

    # 添加异步执行器统计
    if ASYNC_UTILS_AVAILABLE:
        try:
            executor = get_async_executor()
            result["async_executor"] = executor.get_stats()
        except Exception:
            pass

    # 添加多模态处理统计
    try:
        from backend.core.multimodal import get_multimodal_manager
        result["multimodal"] = get_multimodal_manager().get_stats()
    except ImportError:
        pass

    if not result:
        return {"message": "指标模块未加载"}

    return result


@app.get("/metrics/requests")
async def request_metrics_endpoint():
    """请求指标接口"""
    if ENV == "production":
        raise HTTPException(status_code=404, detail="Not Found")

    return request_metrics.get_stats()


# === 启动入口 ===

if __name__ == "__main__":
    logger.info(f"Server running at http://localhost:8000")
    logger.info(f"API文档: http://localhost:8000/docs")
    uvicorn.run(
        "server:app",
        host="0.0.0.0",
        port=8000,
        reload=DEBUG,
        log_level="info" if DEBUG else "warning",
    )
