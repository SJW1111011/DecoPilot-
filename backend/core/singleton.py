"""
单例模式实现
确保知识库、智能体等资源只创建一次
"""
import threading
from typing import TypeVar, Type, Dict, Any

T = TypeVar('T')


class SingletonMeta(type):
    """
    线程安全的单例元类
    """
    _instances: Dict[Type, Any] = {}
    _lock: threading.Lock = threading.Lock()

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            with cls._lock:
                if cls not in cls._instances:
                    instance = super().__call__(*args, **kwargs)
                    cls._instances[cls] = instance
        return cls._instances[cls]

    @classmethod
    def clear_instance(mcs, cls: Type) -> None:
        """清除指定类的单例实例（用于测试）"""
        with mcs._lock:
            if cls in mcs._instances:
                del mcs._instances[cls]


# 全局实例缓存
_knowledge_base = None
_agents: Dict[str, Any] = {}
_lock = threading.Lock()


def get_knowledge_base():
    """
    获取知识库单例
    """
    global _knowledge_base
    if _knowledge_base is None:
        with _lock:
            if _knowledge_base is None:
                from backend.knowledge.multi_collection_kb import MultiCollectionKB
                _knowledge_base = MultiCollectionKB()
    return _knowledge_base


def get_agent(agent_type: str):
    """
    获取智能体单例

    Args:
        agent_type: 智能体类型 (c_end|b_end)

    Returns:
        对应的智能体实例
    """
    global _agents
    if agent_type not in _agents:
        with _lock:
            if agent_type not in _agents:
                if agent_type == "c_end":
                    from backend.agents.c_end_agent import CEndAgent
                    _agents[agent_type] = CEndAgent()
                elif agent_type == "b_end":
                    from backend.agents.b_end_agent import BEndAgent
                    _agents[agent_type] = BEndAgent()
                else:
                    raise ValueError(f"未知的智能体类型: {agent_type}")
    return _agents[agent_type]


def reset_instances():
    """重置所有单例实例（用于测试）"""
    global _knowledge_base, _agents
    with _lock:
        _knowledge_base = None
        _agents = {}
