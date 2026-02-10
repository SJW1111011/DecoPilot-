"""
DecoPilot Framework - 企业级智能体框架

设计原则:
1. 单一职责原则 (SRP) - 每个模块只负责一件事
2. 开闭原则 (OCP) - 对扩展开放，对修改关闭
3. 依赖倒置原则 (DIP) - 依赖抽象而非具体实现
4. 组合优于继承 - 通过组合能力模块构建智能体
5. 事件驱动 - 模块间通过事件通信，降低耦合

架构层次:
- Layer 0: Interface Layer (接口层)
- Layer 1: Orchestration Layer (编排层)
- Layer 2: Agent Layer (智能体层)
- Layer 3: Capability Layer (能力层)
- Layer 4: Infrastructure Layer (基础设施层)
- Layer 5: Learning Layer (学习层)
- Layer 6: External Services (外部服务层)
"""

__version__ = "2.0.0"
__author__ = "DecoPilot Team"

from .events.bus import EventBus, get_event_bus
from .events.types import Event, EventType
from .config.loader import ConfigCenter, get_config_center
from .config.schema import (
    AgentConfig,
    LLMConfig,
    MemoryConfig,
    ReasoningConfig,
    ToolConfig,
    LearningConfig
)
from .runtime import AgentRuntime, create_agent

# 集成层
from .integration import (
    AgentFactory,
    get_agent_factory,
    create_c_end_agent,
    create_b_end_agent,
    FrameworkChatAdapter,
    get_chat_adapter,
)

__all__ = [
    # 事件系统
    "EventBus",
    "get_event_bus",
    "Event",
    "EventType",
    # 配置中心
    "ConfigCenter",
    "get_config_center",
    "AgentConfig",
    "LLMConfig",
    "MemoryConfig",
    "ReasoningConfig",
    "ToolConfig",
    "LearningConfig",
    # 运行时
    "AgentRuntime",
    "create_agent",
    # 集成层
    "AgentFactory",
    "get_agent_factory",
    "create_c_end_agent",
    "create_b_end_agent",
    "FrameworkChatAdapter",
    "get_chat_adapter",
]
