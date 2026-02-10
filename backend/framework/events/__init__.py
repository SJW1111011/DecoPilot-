"""
事件系统模块

提供事件驱动架构的核心组件:
- EventBus: 事件总线，负责事件的发布和订阅
- Event: 事件数据结构
- EventType: 预定义的事件类型
"""

from .bus import EventBus, get_event_bus
from .types import Event, EventType, EventPriority

__all__ = [
    "EventBus",
    "get_event_bus",
    "Event",
    "EventType",
    "EventPriority",
]
