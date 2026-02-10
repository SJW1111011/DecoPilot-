"""
能力模块

提供可组合的智能体能力:
- MemoryCapability: 记忆能力
- ReasoningCapability: 推理能力
- ToolCapability: 工具能力
- MultimodalCapability: 多模态能力
- OutputCapability: 输出能力
"""

from .base import (
    Capability,
    CapabilityMixin,
    CapabilityRegistry,
    get_capability_registry
)
from .memory import MemoryCapability, MemoryMixin
from .reasoning import ReasoningCapability, ReasoningMixin
from .tools import ToolCapability, ToolMixin
from .multimodal import MultimodalCapability, MultimodalMixin
from .output import OutputCapability, OutputMixin

__all__ = [
    # 基础
    "Capability",
    "CapabilityMixin",
    "CapabilityRegistry",
    "get_capability_registry",
    # 记忆
    "MemoryCapability",
    "MemoryMixin",
    # 推理
    "ReasoningCapability",
    "ReasoningMixin",
    # 工具
    "ToolCapability",
    "ToolMixin",
    # 多模态
    "MultimodalCapability",
    "MultimodalMixin",
    # 输出
    "OutputCapability",
    "OutputMixin",
]
