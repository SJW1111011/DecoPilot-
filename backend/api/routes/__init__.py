"""
API路由模块
"""
from .chat import router as chat_router
from .knowledge import router as knowledge_router
from .merchant import router as merchant_router
from .chat_v2 import router as chat_v2_router

__all__ = ["chat_router", "knowledge_router", "merchant_router", "chat_v2_router"]
