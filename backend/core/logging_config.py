"""
统一日志系统
提供结构化日志、性能追踪等功能
"""
import os
import sys
import time
import logging
import threading
from typing import Any, Dict, Optional
from datetime import datetime
from functools import wraps
from contextlib import contextmanager
import json


# 日志级别
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
LOG_FORMAT = os.getenv("LOG_FORMAT", "json")  # json or text
LOG_FILE = os.getenv("LOG_FILE", None)


class StructuredFormatter(logging.Formatter):
    """结构化日志格式化器"""

    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        # 添加额外字段
        if hasattr(record, "extra_fields"):
            log_data.update(record.extra_fields)

        # 添加异常信息
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        if LOG_FORMAT == "json":
            return json.dumps(log_data, ensure_ascii=False)
        else:
            extra = ""
            if hasattr(record, "extra_fields") and record.extra_fields:
                extra = " | " + " ".join(f"{k}={v}" for k, v in record.extra_fields.items())
            return f"[{log_data['timestamp']}] {log_data['level']:8} {log_data['logger']} - {log_data['message']}{extra}"


class ContextLogger(logging.LoggerAdapter):
    """带上下文的日志适配器"""

    def __init__(self, logger: logging.Logger, extra: Dict = None):
        super().__init__(logger, extra or {})
        self._context = threading.local()

    def process(self, msg, kwargs):
        # 合并上下文
        extra = dict(self.extra)

        # 添加线程本地上下文
        if hasattr(self._context, "data"):
            extra.update(self._context.data)

        # 添加调用时传入的额外字段
        if "extra" in kwargs:
            extra.update(kwargs.pop("extra"))

        kwargs["extra"] = {"extra_fields": extra}
        return msg, kwargs

    @contextmanager
    def context(self, **kwargs):
        """临时添加上下文"""
        if not hasattr(self._context, "data"):
            self._context.data = {}

        old_data = dict(self._context.data)
        self._context.data.update(kwargs)
        try:
            yield
        finally:
            self._context.data = old_data

    def bind(self, **kwargs):
        """永久绑定上下文"""
        if not hasattr(self._context, "data"):
            self._context.data = {}
        self._context.data.update(kwargs)
        return self


def setup_logging(name: str = "decopilot") -> ContextLogger:
    """
    设置日志系统

    Args:
        name: 日志器名称

    Returns:
        配置好的日志器
    """
    logger = logging.getLogger(name)

    # 避免重复配置
    if logger.handlers:
        return ContextLogger(logger)

    logger.setLevel(getattr(logging, LOG_LEVEL, logging.INFO))

    # 控制台处理器
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(StructuredFormatter())
    logger.addHandler(console_handler)

    # 文件处理器（可选）
    if LOG_FILE:
        file_handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
        file_handler.setFormatter(StructuredFormatter())
        logger.addHandler(file_handler)

    # 禁止传播到根日志器
    logger.propagate = False

    return ContextLogger(logger)


# 全局日志器
_logger: Optional[ContextLogger] = None
_logger_lock = threading.Lock()


def get_logger(name: str = None) -> ContextLogger:
    """获取日志器"""
    global _logger
    if _logger is None:
        with _logger_lock:
            if _logger is None:
                _logger = setup_logging()

    if name:
        child_logger = logging.getLogger(f"decopilot.{name}")
        child_logger.setLevel(_logger.logger.level)
        if not child_logger.handlers:
            for handler in _logger.logger.handlers:
                child_logger.addHandler(handler)
        child_logger.propagate = False
        return ContextLogger(child_logger)

    return _logger


# === 性能追踪 ===

class PerformanceTracker:
    """性能追踪器"""

    def __init__(self):
        self._metrics: Dict[str, list] = {}
        self._lock = threading.Lock()

    def record(self, name: str, duration: float, metadata: Dict = None):
        """记录性能指标"""
        with self._lock:
            if name not in self._metrics:
                self._metrics[name] = []

            self._metrics[name].append({
                "duration": duration,
                "timestamp": time.time(),
                "metadata": metadata or {},
            })

            # 保留最近1000条
            if len(self._metrics[name]) > 1000:
                self._metrics[name] = self._metrics[name][-1000:]

    def get_stats(self, name: str) -> Dict:
        """获取统计信息"""
        with self._lock:
            if name not in self._metrics or not self._metrics[name]:
                return {}

            durations = [m["duration"] for m in self._metrics[name]]
            return {
                "count": len(durations),
                "total": sum(durations),
                "avg": sum(durations) / len(durations),
                "min": min(durations),
                "max": max(durations),
                "p50": sorted(durations)[len(durations) // 2],
                "p99": sorted(durations)[int(len(durations) * 0.99)] if len(durations) >= 100 else max(durations),
            }

    def get_all_stats(self) -> Dict[str, Dict]:
        """获取所有统计信息"""
        return {name: self.get_stats(name) for name in self._metrics}


_perf_tracker: Optional[PerformanceTracker] = None


def get_perf_tracker() -> PerformanceTracker:
    """获取性能追踪器"""
    global _perf_tracker
    if _perf_tracker is None:
        _perf_tracker = PerformanceTracker()
    return _perf_tracker


# === 装饰器 ===

def log_execution(name: str = None, log_args: bool = False, log_result: bool = False):
    """
    执行日志装饰器

    记录函数执行时间和结果
    """
    def decorator(func):
        func_name = name or f"{func.__module__}.{func.__name__}"
        logger = get_logger()

        @wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.time()

            extra = {"function": func_name}
            if log_args:
                extra["args"] = str(args)[:200]
                extra["kwargs"] = str(kwargs)[:200]

            logger.debug(f"开始执行 {func_name}", extra=extra)

            try:
                result = func(*args, **kwargs)
                duration = time.time() - start_time

                extra["duration_ms"] = int(duration * 1000)
                if log_result:
                    extra["result"] = str(result)[:200]

                logger.debug(f"执行完成 {func_name}", extra=extra)

                # 记录性能
                get_perf_tracker().record(func_name, duration)

                return result
            except Exception as e:
                duration = time.time() - start_time
                extra["duration_ms"] = int(duration * 1000)
                extra["error"] = str(e)

                logger.error(f"执行失败 {func_name}", extra=extra, exc_info=True)
                raise

        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            start_time = time.time()

            extra = {"function": func_name}
            if log_args:
                extra["args"] = str(args)[:200]
                extra["kwargs"] = str(kwargs)[:200]

            logger.debug(f"开始执行 {func_name}", extra=extra)

            try:
                result = await func(*args, **kwargs)
                duration = time.time() - start_time

                extra["duration_ms"] = int(duration * 1000)
                if log_result:
                    extra["result"] = str(result)[:200]

                logger.debug(f"执行完成 {func_name}", extra=extra)

                # 记录性能
                get_perf_tracker().record(func_name, duration)

                return result
            except Exception as e:
                duration = time.time() - start_time
                extra["duration_ms"] = int(duration * 1000)
                extra["error"] = str(e)

                logger.error(f"执行失败 {func_name}", extra=extra, exc_info=True)
                raise

        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return wrapper

    return decorator


@contextmanager
def log_block(name: str, **extra):
    """
    代码块日志上下文管理器

    用于记录代码块的执行时间
    """
    logger = get_logger()
    start_time = time.time()

    logger.debug(f"开始 {name}", extra=extra)

    try:
        yield
        duration = time.time() - start_time
        logger.debug(f"完成 {name}", extra={**extra, "duration_ms": int(duration * 1000)})
        get_perf_tracker().record(name, duration)
    except Exception as e:
        duration = time.time() - start_time
        logger.error(f"失败 {name}", extra={**extra, "duration_ms": int(duration * 1000), "error": str(e)})
        raise
