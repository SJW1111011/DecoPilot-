"""
指标收集

提供应用级别的指标收集能力
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
import threading
import time
import logging

logger = logging.getLogger(__name__)


@dataclass
class Counter:
    """计数器"""
    name: str
    description: str = ""
    labels: Dict[str, str] = field(default_factory=dict)
    _value: float = 0.0
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def inc(self, value: float = 1.0) -> None:
        """增加计数"""
        with self._lock:
            self._value += value

    def get(self) -> float:
        """获取当前值"""
        return self._value


@dataclass
class Gauge:
    """仪表盘"""
    name: str
    description: str = ""
    labels: Dict[str, str] = field(default_factory=dict)
    _value: float = 0.0
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def set(self, value: float) -> None:
        """设置值"""
        with self._lock:
            self._value = value

    def inc(self, value: float = 1.0) -> None:
        """增加"""
        with self._lock:
            self._value += value

    def dec(self, value: float = 1.0) -> None:
        """减少"""
        with self._lock:
            self._value -= value

    def get(self) -> float:
        """获取当前值"""
        return self._value


@dataclass
class Histogram:
    """直方图"""
    name: str
    description: str = ""
    labels: Dict[str, str] = field(default_factory=dict)
    buckets: List[float] = field(default_factory=lambda: [0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10])
    _values: List[float] = field(default_factory=list)
    _sum: float = 0.0
    _count: int = 0
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def observe(self, value: float) -> None:
        """记录观测值"""
        with self._lock:
            self._values.append(value)
            self._sum += value
            self._count += 1

    def get_percentile(self, p: float) -> float:
        """获取百分位数"""
        if not self._values:
            return 0.0
        sorted_values = sorted(self._values)
        index = int(len(sorted_values) * p / 100)
        return sorted_values[min(index, len(sorted_values) - 1)]

    def get_stats(self) -> Dict[str, float]:
        """获取统计信息"""
        if not self._values:
            return {"count": 0, "sum": 0, "avg": 0, "p50": 0, "p95": 0, "p99": 0}

        return {
            "count": self._count,
            "sum": self._sum,
            "avg": self._sum / self._count,
            "p50": self.get_percentile(50),
            "p95": self.get_percentile(95),
            "p99": self.get_percentile(99)
        }


class MetricsCollector:
    """
    指标收集器

    功能:
    - 创建和管理指标
    - 指标聚合
    - Prometheus 格式导出

    使用示例:
    ```python
    metrics = MetricsCollector()

    # 创建指标
    request_count = metrics.counter("requests_total", "Total requests")
    response_time = metrics.histogram("response_time", "Response time")

    # 记录指标
    request_count.inc()
    response_time.observe(0.5)

    # 导出
    print(metrics.export_prometheus())
    ```
    """

    def __init__(self):
        self._counters: Dict[str, Counter] = {}
        self._gauges: Dict[str, Gauge] = {}
        self._histograms: Dict[str, Histogram] = {}
        self._lock = threading.Lock()

    def counter(
        self,
        name: str,
        description: str = "",
        labels: Dict[str, str] = None
    ) -> Counter:
        """创建或获取计数器"""
        key = self._make_key(name, labels)
        with self._lock:
            if key not in self._counters:
                self._counters[key] = Counter(
                    name=name,
                    description=description,
                    labels=labels or {}
                )
            return self._counters[key]

    def gauge(
        self,
        name: str,
        description: str = "",
        labels: Dict[str, str] = None
    ) -> Gauge:
        """创建或获取仪表盘"""
        key = self._make_key(name, labels)
        with self._lock:
            if key not in self._gauges:
                self._gauges[key] = Gauge(
                    name=name,
                    description=description,
                    labels=labels or {}
                )
            return self._gauges[key]

    def histogram(
        self,
        name: str,
        description: str = "",
        labels: Dict[str, str] = None,
        buckets: List[float] = None
    ) -> Histogram:
        """创建或获取直方图"""
        key = self._make_key(name, labels)
        with self._lock:
            if key not in self._histograms:
                self._histograms[key] = Histogram(
                    name=name,
                    description=description,
                    labels=labels or {},
                    buckets=buckets or [0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10]
                )
            return self._histograms[key]

    def _make_key(self, name: str, labels: Dict[str, str] = None) -> str:
        """生成指标键"""
        if not labels:
            return name
        label_str = ",".join(f"{k}={v}" for k, v in sorted(labels.items()))
        return f"{name}{{{label_str}}}"

    def export_prometheus(self) -> str:
        """导出 Prometheus 格式"""
        lines = []

        # 计数器
        for counter in self._counters.values():
            if counter.description:
                lines.append(f"# HELP {counter.name} {counter.description}")
            lines.append(f"# TYPE {counter.name} counter")
            labels = self._format_labels(counter.labels)
            lines.append(f"{counter.name}{labels} {counter.get()}")

        # 仪表盘
        for gauge in self._gauges.values():
            if gauge.description:
                lines.append(f"# HELP {gauge.name} {gauge.description}")
            lines.append(f"# TYPE {gauge.name} gauge")
            labels = self._format_labels(gauge.labels)
            lines.append(f"{gauge.name}{labels} {gauge.get()}")

        # 直方图
        for histogram in self._histograms.values():
            if histogram.description:
                lines.append(f"# HELP {histogram.name} {histogram.description}")
            lines.append(f"# TYPE {histogram.name} histogram")
            stats = histogram.get_stats()
            labels = self._format_labels(histogram.labels)
            lines.append(f"{histogram.name}_sum{labels} {stats['sum']}")
            lines.append(f"{histogram.name}_count{labels} {stats['count']}")

        return "\n".join(lines)

    def _format_labels(self, labels: Dict[str, str]) -> str:
        """格式化标签"""
        if not labels:
            return ""
        label_str = ",".join(f'{k}="{v}"' for k, v in sorted(labels.items()))
        return f"{{{label_str}}}"

    def get_all_metrics(self) -> Dict[str, Any]:
        """获取所有指标"""
        return {
            "counters": {k: v.get() for k, v in self._counters.items()},
            "gauges": {k: v.get() for k, v in self._gauges.items()},
            "histograms": {k: v.get_stats() for k, v in self._histograms.items()}
        }

    def clear(self) -> None:
        """清空所有指标"""
        with self._lock:
            self._counters.clear()
            self._gauges.clear()
            self._histograms.clear()


# 全局指标收集器
_global_metrics: Optional[MetricsCollector] = None
_metrics_lock = threading.Lock()


def get_metrics() -> MetricsCollector:
    """获取全局指标收集器"""
    global _global_metrics
    if _global_metrics is None:
        with _metrics_lock:
            if _global_metrics is None:
                _global_metrics = MetricsCollector()
    return _global_metrics


# 预定义的指标
def setup_default_metrics() -> None:
    """设置默认指标"""
    metrics = get_metrics()

    # 请求指标
    metrics.counter("decopilot_requests_total", "Total number of requests")
    metrics.histogram("decopilot_request_duration_seconds", "Request duration in seconds")

    # 智能体指标
    metrics.counter("decopilot_agent_calls_total", "Total agent calls")
    metrics.histogram("decopilot_agent_duration_seconds", "Agent processing duration")

    # 工具指标
    metrics.counter("decopilot_tool_calls_total", "Total tool calls")
    metrics.histogram("decopilot_tool_duration_seconds", "Tool execution duration")

    # 推理指标
    metrics.counter("decopilot_reasoning_total", "Total reasoning operations")
    metrics.histogram("decopilot_reasoning_steps", "Number of reasoning steps")

    # 记忆指标
    metrics.gauge("decopilot_memory_items", "Number of memory items")

    # 学习指标
    metrics.counter("decopilot_feedback_total", "Total feedback received")
    metrics.gauge("decopilot_avg_rating", "Average user rating")
