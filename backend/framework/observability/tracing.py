"""
分布式追踪

提供请求级别的追踪能力
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional
from contextlib import contextmanager
from contextvars import ContextVar
import threading
import logging
import time
from uuid import uuid4

logger = logging.getLogger(__name__)

# 当前追踪上下文
_current_span: ContextVar[Optional["Span"]] = ContextVar("current_span", default=None)


@dataclass
class Span:
    """追踪 Span"""
    name: str
    trace_id: str
    span_id: str
    parent_span_id: Optional[str] = None
    start_time: float = field(default_factory=time.time)
    end_time: Optional[float] = None
    status: str = "ok"  # ok | error
    attributes: Dict[str, Any] = field(default_factory=dict)
    events: List[Dict[str, Any]] = field(default_factory=list)

    @property
    def duration(self) -> float:
        """持续时间（秒）"""
        if self.end_time:
            return self.end_time - self.start_time
        return time.time() - self.start_time

    def set_attribute(self, key: str, value: Any) -> None:
        """设置属性"""
        self.attributes[key] = value

    def add_event(self, name: str, attributes: Dict[str, Any] = None) -> None:
        """添加事件"""
        self.events.append({
            "name": name,
            "timestamp": time.time(),
            "attributes": attributes or {}
        })

    def set_error(self, error: Exception) -> None:
        """设置错误"""
        self.status = "error"
        self.set_attribute("error.type", type(error).__name__)
        self.set_attribute("error.message", str(error))

    def end(self) -> None:
        """结束 Span"""
        self.end_time = time.time()

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "name": self.name,
            "trace_id": self.trace_id,
            "span_id": self.span_id,
            "parent_span_id": self.parent_span_id,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "duration": self.duration,
            "status": self.status,
            "attributes": self.attributes,
            "events": self.events
        }


class Tracer:
    """
    追踪器

    功能:
    - 创建和管理 Span
    - 上下文传播
    - Span 导出

    使用示例:
    ```python
    tracer = Tracer("my-service")

    with tracer.span("process_request") as span:
        span.set_attribute("user_id", "123")
        # 处理请求
        with tracer.span("call_llm") as child_span:
            # 调用 LLM
            pass
    ```
    """

    def __init__(
        self,
        service_name: str = "decopilot",
        sample_rate: float = 1.0
    ):
        self._service_name = service_name
        self._sample_rate = sample_rate
        self._spans: List[Span] = []
        self._lock = threading.Lock()

    @contextmanager
    def span(
        self,
        name: str,
        attributes: Dict[str, Any] = None,
        **kwargs
    ):
        """
        创建 Span 上下文

        Args:
            name: Span 名称
            attributes: 初始属性
            **kwargs: 额外属性
        """
        # 合并属性
        all_attributes = {**(attributes or {}), **kwargs}

        # 获取父 Span
        parent_span = _current_span.get()

        # 创建新 Span
        span = Span(
            name=name,
            trace_id=parent_span.trace_id if parent_span else str(uuid4()),
            span_id=str(uuid4())[:16],
            parent_span_id=parent_span.span_id if parent_span else None,
            attributes={"service": self._service_name, **all_attributes}
        )

        # 设置当前 Span
        token = _current_span.set(span)

        try:
            yield span
        except Exception as e:
            span.set_error(e)
            raise
        finally:
            span.end()
            _current_span.reset(token)

            # 存储 Span
            with self._lock:
                self._spans.append(span)

            # 导出
            self._export(span)

    def _export(self, span: Span) -> None:
        """导出 Span"""
        # 这里可以集成 Jaeger、Zipkin 等追踪系统
        logger.debug(f"Span: {span.name} ({span.duration:.3f}s)")

    def get_current_span(self) -> Optional[Span]:
        """获取当前 Span"""
        return _current_span.get()

    def get_current_trace_id(self) -> Optional[str]:
        """获取当前 Trace ID"""
        span = _current_span.get()
        return span.trace_id if span else None

    def get_spans(self, trace_id: str = None, limit: int = 100) -> List[Span]:
        """获取 Span 列表"""
        with self._lock:
            spans = list(self._spans)

        if trace_id:
            spans = [s for s in spans if s.trace_id == trace_id]

        return spans[-limit:]

    def clear(self) -> None:
        """清空 Span"""
        with self._lock:
            self._spans.clear()


# 全局追踪器
_global_tracer: Optional[Tracer] = None
_tracer_lock = threading.Lock()


def get_tracer(service_name: str = "decopilot") -> Tracer:
    """获取全局追踪器"""
    global _global_tracer
    if _global_tracer is None:
        with _tracer_lock:
            if _global_tracer is None:
                _global_tracer = Tracer(service_name)
    return _global_tracer


def get_current_trace_id() -> Optional[str]:
    """获取当前 Trace ID"""
    tracer = get_tracer()
    return tracer.get_current_trace_id()
