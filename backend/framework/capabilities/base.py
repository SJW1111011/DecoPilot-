"""
能力基类和协议定义

定义能力的抽象接口和基础实现
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Protocol, Type, runtime_checkable
import threading
import logging

logger = logging.getLogger(__name__)


@runtime_checkable
class Capability(Protocol):
    """
    能力协议

    所有能力必须实现此协议
    """

    @property
    def name(self) -> str:
        """能力名称"""
        ...

    @property
    def version(self) -> str:
        """能力版本"""
        ...

    async def initialize(self) -> None:
        """初始化能力"""
        ...

    async def shutdown(self) -> None:
        """关闭能力"""
        ...

    def is_ready(self) -> bool:
        """检查能力是否就绪"""
        ...


class CapabilityMixin:
    """
    能力混入基类

    提供能力的基础实现，子类通过继承获得能力
    """

    _capability_name: str = "base"
    _capability_version: str = "1.0.0"
    _initialized: bool = False

    @property
    def name(self) -> str:
        return self._capability_name

    @property
    def version(self) -> str:
        return self._capability_version

    async def initialize(self) -> None:
        """初始化能力"""
        if self._initialized:
            return
        await self._do_initialize()
        self._initialized = True
        logger.info(f"Capability {self.name} v{self.version} initialized")

    async def _do_initialize(self) -> None:
        """子类实现具体初始化逻辑"""
        pass

    async def shutdown(self) -> None:
        """关闭能力"""
        if not self._initialized:
            return
        await self._do_shutdown()
        self._initialized = False
        logger.info(f"Capability {self.name} shutdown")

    async def _do_shutdown(self) -> None:
        """子类实现具体关闭逻辑"""
        pass

    def is_ready(self) -> bool:
        return self._initialized


@dataclass
class CapabilityDefinition:
    """能力定义"""
    name: str
    cls: Type[CapabilityMixin]
    version: str = "1.0.0"
    description: str = ""
    dependencies: List[str] = field(default_factory=list)
    config_schema: Optional[Dict[str, Any]] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class CapabilityRegistry:
    """
    能力注册表

    管理所有可用的能力，支持:
    - 能力注册
    - 能力发现
    - 依赖解析
    - 能力实例化
    """

    def __init__(self):
        self._capabilities: Dict[str, CapabilityDefinition] = {}
        self._instances: Dict[str, CapabilityMixin] = {}
        self._lock = threading.RLock()

    def register(
        self,
        name: str,
        cls: Type[CapabilityMixin],
        version: str = "1.0.0",
        description: str = "",
        dependencies: List[str] = None,
        config_schema: Dict[str, Any] = None,
        **metadata
    ) -> None:
        """注册能力"""
        with self._lock:
            if name in self._capabilities:
                logger.warning(f"Capability {name} already registered, overwriting")

            self._capabilities[name] = CapabilityDefinition(
                name=name,
                cls=cls,
                version=version,
                description=description,
                dependencies=dependencies or [],
                config_schema=config_schema,
                metadata=metadata
            )
            logger.info(f"Registered capability: {name} v{version}")

    def unregister(self, name: str) -> bool:
        """注销能力"""
        with self._lock:
            if name in self._capabilities:
                del self._capabilities[name]
                if name in self._instances:
                    del self._instances[name]
                return True
            return False

    def get(self, name: str) -> Optional[CapabilityDefinition]:
        """获取能力定义"""
        return self._capabilities.get(name)

    def list(self) -> List[CapabilityDefinition]:
        """列出所有能力"""
        return list(self._capabilities.values())

    def create_instance(
        self,
        name: str,
        config: Dict[str, Any] = None,
        singleton: bool = True
    ) -> Optional[CapabilityMixin]:
        """
        创建能力实例

        Args:
            name: 能力名称
            config: 配置参数
            singleton: 是否使用单例模式

        Returns:
            能力实例
        """
        definition = self.get(name)
        if not definition:
            logger.error(f"Capability {name} not found")
            return None

        # 检查单例
        if singleton and name in self._instances:
            return self._instances[name]

        # 解析依赖
        for dep in definition.dependencies:
            if dep not in self._capabilities:
                logger.error(f"Dependency {dep} not found for capability {name}")
                return None

        # 创建实例
        try:
            instance = definition.cls(**(config or {}))
            if singleton:
                with self._lock:
                    self._instances[name] = instance
            return instance
        except Exception as e:
            logger.error(f"Failed to create capability {name}: {e}")
            return None

    def get_instance(self, name: str) -> Optional[CapabilityMixin]:
        """获取已创建的实例"""
        return self._instances.get(name)

    def resolve_dependencies(self, names: List[str]) -> List[str]:
        """
        解析依赖顺序

        返回按依赖顺序排列的能力名称列表
        """
        resolved = []
        seen = set()

        def resolve(name: str):
            if name in seen:
                return
            seen.add(name)

            definition = self.get(name)
            if definition:
                for dep in definition.dependencies:
                    resolve(dep)
                resolved.append(name)

        for name in names:
            resolve(name)

        return resolved


# 全局能力注册表
_global_registry: Optional[CapabilityRegistry] = None
_registry_lock = threading.Lock()


def get_capability_registry() -> CapabilityRegistry:
    """获取全局能力注册表"""
    global _global_registry
    if _global_registry is None:
        with _registry_lock:
            if _global_registry is None:
                _global_registry = CapabilityRegistry()
    return _global_registry


def register_capability(
    name: str,
    version: str = "1.0.0",
    description: str = "",
    dependencies: List[str] = None
) -> Callable:
    """
    装饰器：注册能力

    Example:
        @register_capability("memory", version="1.0.0")
        class MemoryMixin(CapabilityMixin):
            pass
    """
    def decorator(cls: Type[CapabilityMixin]) -> Type[CapabilityMixin]:
        registry = get_capability_registry()
        registry.register(
            name=name,
            cls=cls,
            version=version,
            description=description,
            dependencies=dependencies
        )
        return cls
    return decorator
