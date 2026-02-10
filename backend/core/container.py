"""
依赖注入容器
管理应用程序的所有依赖
"""
import os
import sys
from typing import Optional, Callable, Any, Dict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


class Container:
    """
    简单的依赖注入容器
    """
    _services: Dict[str, Any] = {}
    _factories: Dict[str, Callable] = {}

    @classmethod
    def register(cls, name: str, factory: Callable) -> None:
        """注册服务工厂"""
        cls._factories[name] = factory

    @classmethod
    def get(cls, name: str) -> Any:
        """获取服务实例（懒加载）"""
        if name not in cls._services:
            if name not in cls._factories:
                raise KeyError(f"服务 '{name}' 未注册")
            cls._services[name] = cls._factories[name]()
        return cls._services[name]

    @classmethod
    def reset(cls) -> None:
        """重置容器（用于测试）"""
        cls._services = {}

    @classmethod
    def register_defaults(cls) -> None:
        """注册默认服务"""
        from backend.core.singleton import get_knowledge_base, get_agent

        cls.register("knowledge_base", get_knowledge_base)
        cls.register("c_end_agent", lambda: get_agent("c_end"))
        cls.register("b_end_agent", lambda: get_agent("b_end"))


# 初始化默认服务
Container.register_defaults()
