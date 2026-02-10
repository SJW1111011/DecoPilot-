"""
结构化日志

提供结构化的日志记录能力
"""

import logging
import json
import sys
from datetime import datetime
from typing import Any, Dict, Optional
import threading
from contextvars import ContextVar

# 日志上下文
_log_context: ContextVar[Dict[str, Any]] = ContextVar("log_context", default={})


class StructuredFormatter(logging.Formatter):
    """结构化日志格式化器"""

    def format(self, record: logging.LogRecord) -> str:
        """格式化日志记录"""
        # 基础字段
        log_data = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # 添加位置信息
        if record.pathname:
            log_data["location"] = {
                "file": record.pathname,
                "line": record.lineno,
                "function": record.funcName
            }

        # 添加上下文
        context = _log_context.get()
        if context:
            log_data["context"] = context

        # 添加额外字段
        if hasattr(record, "extra_fields"):
            log_data.update(record.extra_fields)

        # 添加异常信息
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_data, ensure_ascii=False, default=str)


class StructuredLogger:
    """
    结构化日志记录器

    功能:
    - JSON 格式输出
    - 上下文传播
    - 字段扩展

    使用示例:
    ```python
    logger = StructuredLogger("my-service")

    # 基础日志
    logger.info("Request received", user_id="123", action="query")

    # 带上下文
    with logger.context(request_id="req_123"):
        logger.info("Processing request")
        logger.debug("Step 1 completed")
    ```
    """

    def __init__(
        self,
        name: str = "decopilot",
        level: int = logging.INFO,
        json_format: bool = True
    ):
        self._logger = logging.getLogger(name)
        self._logger.setLevel(level)

        # 配置处理器
        if not self._logger.handlers:
            handler = logging.StreamHandler(sys.stdout)
            handler.setLevel(level)

            if json_format:
                handler.setFormatter(StructuredFormatter())
            else:
                handler.setFormatter(logging.Formatter(
                    "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
                ))

            self._logger.addHandler(handler)

    def _log(
        self,
        level: int,
        message: str,
        **kwargs
    ) -> None:
        """记录日志"""
        record = self._logger.makeRecord(
            self._logger.name,
            level,
            "(unknown file)",
            0,
            message,
            (),
            None
        )
        record.extra_fields = kwargs
        self._logger.handle(record)

    def debug(self, message: str, **kwargs) -> None:
        """调试日志"""
        self._log(logging.DEBUG, message, **kwargs)

    def info(self, message: str, **kwargs) -> None:
        """信息日志"""
        self._log(logging.INFO, message, **kwargs)

    def warning(self, message: str, **kwargs) -> None:
        """警告日志"""
        self._log(logging.WARNING, message, **kwargs)

    def error(self, message: str, **kwargs) -> None:
        """错误日志"""
        self._log(logging.ERROR, message, **kwargs)

    def critical(self, message: str, **kwargs) -> None:
        """严重错误日志"""
        self._log(logging.CRITICAL, message, **kwargs)

    def exception(self, message: str, **kwargs) -> None:
        """异常日志"""
        self._logger.exception(message, extra={"extra_fields": kwargs})

    class _ContextManager:
        """上下文管理器"""

        def __init__(self, **kwargs):
            self._kwargs = kwargs
            self._token = None

        def __enter__(self):
            current = _log_context.get()
            new_context = {**current, **self._kwargs}
            self._token = _log_context.set(new_context)
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            _log_context.reset(self._token)

    def context(self, **kwargs) -> _ContextManager:
        """创建日志上下文"""
        return self._ContextManager(**kwargs)

    def bind(self, **kwargs) -> "StructuredLogger":
        """绑定字段（返回新的 logger）"""
        # 这里简化处理，实际可以创建新的 logger 实例
        return self


# 全局日志记录器
_global_logger: Optional[StructuredLogger] = None
_logger_lock = threading.Lock()


def get_logger(name: str = "decopilot") -> StructuredLogger:
    """获取全局日志记录器"""
    global _global_logger
    if _global_logger is None:
        with _logger_lock:
            if _global_logger is None:
                _global_logger = StructuredLogger(name)
    return _global_logger


def configure_logging(
    level: str = "INFO",
    json_format: bool = True
) -> None:
    """配置日志"""
    global _global_logger
    level_int = getattr(logging, level.upper(), logging.INFO)

    with _logger_lock:
        _global_logger = StructuredLogger(
            name="decopilot",
            level=level_int,
            json_format=json_format
        )
