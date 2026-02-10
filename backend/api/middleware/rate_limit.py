"""
限流中间件
基于slowapi实现请求限流
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
import config_data as config

try:
    from slowapi import Limiter
    from slowapi.util import get_remote_address
    from slowapi.errors import RateLimitExceeded
    from slowapi.middleware import SlowAPIMiddleware
    SLOWAPI_AVAILABLE = True
except ImportError:
    SLOWAPI_AVAILABLE = False


def get_limiter():
    """获取限流器实例"""
    if not SLOWAPI_AVAILABLE:
        return None

    return Limiter(key_func=get_remote_address, default_limits=[config.API_RATE_LIMIT])


def get_rate_limit_handler():
    """获取限流异常处理器"""
    if not SLOWAPI_AVAILABLE:
        return None

    from fastapi import Request
    from fastapi.responses import JSONResponse

    async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
        return JSONResponse(
            status_code=429,
            content={
                "error": "请求过于频繁",
                "detail": f"请求限制: {exc.detail}",
                "retry_after": getattr(exc, "retry_after", 60),
            }
        )

    return rate_limit_handler


limiter = get_limiter()
