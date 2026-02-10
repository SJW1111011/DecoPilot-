"""
核心模块 - 提供单例管理、依赖注入、安全等基础设施
"""
from .singleton import SingletonMeta, get_knowledge_base, get_agent
from .container import Container
from .security import (
    InputValidator,
    SensitiveWordFilter,
    InjectionDetector,
    DataMasker,
    InputSanitizer,
    sanitize_input,
    validate_input,
)

__all__ = [
    "SingletonMeta",
    "get_knowledge_base",
    "get_agent",
    "Container",
    "InputValidator",
    "SensitiveWordFilter",
    "InjectionDetector",
    "DataMasker",
    "InputSanitizer",
    "sanitize_input",
    "validate_input",
]
