# -*- coding: utf-8 -*-
"""
框架集成层

将新框架与现有系统集成
"""

from .agent_factory import (
    AgentFactory,
    get_agent_factory,
    create_c_end_agent,
    create_b_end_agent,
)
from .api_adapter import (
    FrameworkChatAdapter,
    get_chat_adapter,
)

__all__ = [
    "AgentFactory",
    "get_agent_factory",
    "create_c_end_agent",
    "create_b_end_agent",
    "FrameworkChatAdapter",
    "get_chat_adapter",
]
