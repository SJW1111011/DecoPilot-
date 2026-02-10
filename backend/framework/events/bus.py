"""
事件总线实现

提供事件的发布、订阅、中间件等功能
支持同步和异步处理
"""

import asyncio
import logging
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Set, Union
from functools import wraps
import threading
from concurrent.futures import ThreadPoolExecutor

from .types import Event, EventType, EventPriority, EventFilter

logger = logging.getLogger(__name__)


@dataclass
class Subscription:
    """订阅信息"""
    handler: Callable
    filter: Optional[EventFilter] = None
    is_async: bool = False
    once: bool = False  # 是否只触发一次
    priority: int = 0  # 处理器优先级


class EventBus:
    """
    事件总线

    功能:
    - 事件发布/订阅
    - 中间件支持
    - 异步处理
    - 事件过滤
    - 事件历史记录
    - 死信队列

    使用示例:
    ```python
    bus = EventBus()

    # 订阅事件
    @bus.on(EventType.TOOL_CALLED)
    async def handle_tool_call(event: Event):
        print(f"Tool called: {event.payload}")

    # 发布事件
    await bus.emit(Event(
        type=EventType.TOOL_CALLED,
        payload={"tool_name": "calculator"}
    ))
    ```
    """

    def __init__(
        self,
        max_history: int = 1000,
        enable_dead_letter: bool = True,
        max_workers: int = 4
    ):
        self._subscriptions: Dict[str, List[Subscription]] = defaultdict(list)
        self._middleware: List[Callable] = []
        self._history: List[Event] = []
        self._max_history = max_history
        self._dead_letter_queue: List[tuple] = []
        self._enable_dead_letter = enable_dead_letter
        self._lock = threading.RLock()
        self._executor = ThreadPoolExecutor(max_workers=max_workers)
        self._running = True

    def on(
        self,
        event_type: Union[EventType, str, List[Union[EventType, str]]],
        filter: Optional[EventFilter] = None,
        priority: int = 0,
        once: bool = False
    ) -> Callable:
        """
        装饰器：订阅事件

        Args:
            event_type: 事件类型（可以是单个或列表）
            filter: 事件过滤器
            priority: 处理器优先级（越大越先执行）
            once: 是否只触发一次

        Example:
            @bus.on(EventType.REQUEST_RECEIVED)
            async def handle_request(event):
                pass
        """
        def decorator(handler: Callable) -> Callable:
            is_async = asyncio.iscoroutinefunction(handler)
            types = event_type if isinstance(event_type, list) else [event_type]

            for et in types:
                type_str = et.value if isinstance(et, EventType) else et
                subscription = Subscription(
                    handler=handler,
                    filter=filter,
                    is_async=is_async,
                    once=once,
                    priority=priority
                )
                with self._lock:
                    self._subscriptions[type_str].append(subscription)
                    # 按优先级排序
                    self._subscriptions[type_str].sort(
                        key=lambda s: s.priority, reverse=True
                    )

            @wraps(handler)
            def wrapper(*args, **kwargs):
                return handler(*args, **kwargs)

            return wrapper
        return decorator

    def subscribe(
        self,
        event_type: Union[EventType, str],
        handler: Callable,
        filter: Optional[EventFilter] = None,
        priority: int = 0,
        once: bool = False
    ) -> str:
        """
        编程方式订阅事件

        Returns:
            subscription_id: 订阅ID，用于取消订阅
        """
        type_str = event_type.value if isinstance(event_type, EventType) else event_type
        is_async = asyncio.iscoroutinefunction(handler)

        subscription = Subscription(
            handler=handler,
            filter=filter,
            is_async=is_async,
            once=once,
            priority=priority
        )

        with self._lock:
            self._subscriptions[type_str].append(subscription)
            self._subscriptions[type_str].sort(key=lambda s: s.priority, reverse=True)

        return f"{type_str}:{id(subscription)}"

    def unsubscribe(self, subscription_id: str) -> bool:
        """取消订阅"""
        try:
            type_str, sub_id = subscription_id.rsplit(":", 1)
            sub_id = int(sub_id)

            with self._lock:
                subs = self._subscriptions.get(type_str, [])
                for i, sub in enumerate(subs):
                    if id(sub) == sub_id:
                        subs.pop(i)
                        return True
            return False
        except Exception:
            return False

    def use(self, middleware: Callable) -> None:
        """
        添加中间件

        中间件签名: async def middleware(event: Event, next: Callable) -> Event
        """
        self._middleware.append(middleware)

    async def emit(
        self,
        event: Event,
        wait: bool = True,
        timeout: float = 30.0
    ) -> List[Any]:
        """
        发布事件

        Args:
            event: 事件对象
            wait: 是否等待所有处理器完成
            timeout: 超时时间（秒）

        Returns:
            处理器返回值列表
        """
        if not self._running:
            logger.warning("EventBus is stopped, event ignored")
            return []

        # 执行中间件链
        processed_event = await self._run_middleware(event)
        if processed_event is None:
            return []

        # 记录历史
        self._record_history(processed_event)

        # 获取订阅者
        type_str = processed_event.type
        with self._lock:
            subscriptions = list(self._subscriptions.get(type_str, []))
            # 同时获取通配符订阅
            subscriptions.extend(self._subscriptions.get("*", []))

        if not subscriptions:
            return []

        # 执行处理器
        results = []
        to_remove = []

        for sub in subscriptions:
            # 检查过滤器
            if sub.filter and not sub.filter.matches(processed_event):
                continue

            try:
                if wait:
                    if sub.is_async:
                        result = await asyncio.wait_for(
                            sub.handler(processed_event),
                            timeout=timeout
                        )
                    else:
                        result = await asyncio.get_event_loop().run_in_executor(
                            self._executor,
                            sub.handler,
                            processed_event
                        )
                    results.append(result)
                else:
                    if sub.is_async:
                        asyncio.create_task(sub.handler(processed_event))
                    else:
                        self._executor.submit(sub.handler, processed_event)

                if sub.once:
                    to_remove.append((type_str, sub))

            except asyncio.TimeoutError:
                logger.error(f"Handler timeout for event {type_str}")
                if self._enable_dead_letter:
                    self._dead_letter_queue.append((processed_event, "timeout"))
            except Exception as e:
                logger.error(f"Handler error for event {type_str}: {e}")
                if self._enable_dead_letter:
                    self._dead_letter_queue.append((processed_event, str(e)))

        # 移除一次性订阅
        with self._lock:
            for type_str, sub in to_remove:
                if sub in self._subscriptions[type_str]:
                    self._subscriptions[type_str].remove(sub)

        return results

    def emit_sync(self, event: Event) -> None:
        """同步发布事件（在非异步上下文中使用）"""
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.create_task(self.emit(event, wait=False))
            else:
                loop.run_until_complete(self.emit(event))
        except RuntimeError:
            # 没有事件循环，创建新的
            asyncio.run(self.emit(event, wait=False))

    async def _run_middleware(self, event: Event) -> Optional[Event]:
        """执行中间件链"""
        if not self._middleware:
            return event

        async def create_next(index: int):
            async def next_middleware(evt: Event) -> Event:
                if index >= len(self._middleware):
                    return evt
                mw = self._middleware[index]
                return await mw(evt, await create_next(index + 1))
            return next_middleware

        try:
            next_fn = await create_next(0)
            return await next_fn(event)
        except Exception as e:
            logger.error(f"Middleware error: {e}")
            return None

    def _record_history(self, event: Event) -> None:
        """记录事件历史"""
        with self._lock:
            self._history.append(event)
            if len(self._history) > self._max_history:
                self._history = self._history[-self._max_history:]

    def get_history(
        self,
        filter: Optional[EventFilter] = None,
        limit: int = 100
    ) -> List[Event]:
        """获取事件历史"""
        with self._lock:
            events = list(self._history)

        if filter:
            events = [e for e in events if filter.matches(e)]

        return events[-limit:]

    def get_dead_letters(self, limit: int = 100) -> List[tuple]:
        """获取死信队列"""
        return self._dead_letter_queue[-limit:]

    def clear_dead_letters(self) -> int:
        """清空死信队列"""
        count = len(self._dead_letter_queue)
        self._dead_letter_queue.clear()
        return count

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        with self._lock:
            return {
                "total_subscriptions": sum(
                    len(subs) for subs in self._subscriptions.values()
                ),
                "event_types": list(self._subscriptions.keys()),
                "history_size": len(self._history),
                "dead_letter_size": len(self._dead_letter_queue),
                "middleware_count": len(self._middleware)
            }

    def stop(self) -> None:
        """停止事件总线"""
        self._running = False
        self._executor.shutdown(wait=False)

    def start(self) -> None:
        """启动事件总线"""
        self._running = True
        if self._executor._shutdown:
            self._executor = ThreadPoolExecutor(max_workers=4)


# 全局事件总线实例
_global_event_bus: Optional[EventBus] = None
_bus_lock = threading.Lock()


def get_event_bus() -> EventBus:
    """获取全局事件总线实例"""
    global _global_event_bus
    if _global_event_bus is None:
        with _bus_lock:
            if _global_event_bus is None:
                _global_event_bus = EventBus()
    return _global_event_bus


def reset_event_bus() -> None:
    """重置全局事件总线（主要用于测试）"""
    global _global_event_bus
    with _bus_lock:
        if _global_event_bus:
            _global_event_bus.stop()
        _global_event_bus = None
