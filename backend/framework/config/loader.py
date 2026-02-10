"""
配置加载器

支持多种配置源:
- YAML 文件
- JSON 文件
- 环境变量
- 远程配置中心
"""

import json
import logging
import os
import threading
from dataclasses import asdict, fields, is_dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Type, TypeVar

from .schema import (
    AgentConfig,
    FrameworkConfig,
    LLMConfig,
    MemoryConfig,
    ReasoningConfig,
    ToolConfig,
    LearningConfig,
    ObservabilityConfig,
    KnowledgeConfig,
    SecurityConfig,
    OrchestrationConfig,
    EmbeddingConfig,
    MultimodalConfig
)

logger = logging.getLogger(__name__)

T = TypeVar("T")


class ConfigError(Exception):
    """配置错误"""
    pass


class ConfigNotFoundError(ConfigError):
    """配置未找到"""
    pass


class ConfigValidationError(ConfigError):
    """配置验证错误"""
    pass


class ConfigCenter:
    """
    配置中心

    功能:
    - 多源配置加载（文件、环境变量）
    - 配置缓存
    - 配置热更新
    - 配置验证
    - 配置合并

    使用示例:
    ```python
    config_center = ConfigCenter("config")

    # 加载框架配置
    framework_config = config_center.load_framework_config()

    # 加载智能体配置
    agent_config = config_center.load_agent_config("c_end")

    # 监听配置变更
    config_center.watch(lambda: print("Config changed!"))
    ```
    """

    # 配置类型映射
    CONFIG_TYPES: Dict[str, Type] = {
        "framework": FrameworkConfig,
        "agent": AgentConfig,
        "llm": LLMConfig,
        "embedding": EmbeddingConfig,
        "memory": MemoryConfig,
        "reasoning": ReasoningConfig,
        "tools": ToolConfig,
        "multimodal": MultimodalConfig,
        "knowledge": KnowledgeConfig,
        "learning": LearningConfig,
        "observability": ObservabilityConfig,
        "security": SecurityConfig,
        "orchestration": OrchestrationConfig,
    }

    def __init__(
        self,
        config_path: str = "config",
        env_prefix: str = "DECOPILOT_"
    ):
        self._config_path = Path(config_path)
        self._env_prefix = env_prefix
        self._cache: Dict[str, Any] = {}
        self._watchers: List[Callable] = []
        self._lock = threading.RLock()

        # 确保配置目录存在
        self._config_path.mkdir(parents=True, exist_ok=True)

    def load(
        self,
        name: str,
        config_type: Optional[Type[T]] = None,
        default: Optional[T] = None
    ) -> T:
        """
        加载配置

        Args:
            name: 配置名称
            config_type: 配置类型
            default: 默认值

        Returns:
            配置对象
        """
        # 检查缓存
        cache_key = f"{name}:{config_type.__name__ if config_type else 'dict'}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        # 加载配置数据
        data = self._load_from_sources(name)

        if data is None:
            if default is not None:
                return default
            raise ConfigNotFoundError(f"Config '{name}' not found")

        # 转换为配置对象
        if config_type:
            config = self._dict_to_dataclass(data, config_type)
        else:
            config = data

        # 缓存
        with self._lock:
            self._cache[cache_key] = config

        return config

    def load_framework_config(self) -> FrameworkConfig:
        """加载框架配置"""
        return self.load("framework", FrameworkConfig, FrameworkConfig())

    def load_agent_config(self, agent_name: str) -> AgentConfig:
        """加载智能体配置"""
        return self.load(f"agents/{agent_name}", AgentConfig, AgentConfig(name=agent_name))

    def _load_from_sources(self, name: str) -> Optional[Dict[str, Any]]:
        """从多个源加载配置"""
        data = {}

        # 1. 从文件加载
        file_data = self._load_from_file(name)
        if file_data:
            data = self._deep_merge(data, file_data)

        # 2. 从环境变量加载
        env_data = self._load_from_env(name)
        if env_data:
            data = self._deep_merge(data, env_data)

        return data if data else None

    def _load_from_file(self, name: str) -> Optional[Dict[str, Any]]:
        """从文件加载配置"""
        # 尝试不同的文件格式
        for ext, loader in [
            (".yaml", self._load_yaml),
            (".yml", self._load_yaml),
            (".json", self._load_json),
        ]:
            path = self._config_path / f"{name}{ext}"
            if path.exists():
                try:
                    return loader(path)
                except Exception as e:
                    logger.error(f"Failed to load config from {path}: {e}")

        return None

    def _load_yaml(self, path: Path) -> Dict[str, Any]:
        """加载 YAML 文件"""
        try:
            import yaml
            with open(path, "r", encoding="utf-8") as f:
                return yaml.safe_load(f) or {}
        except ImportError:
            logger.warning("PyYAML not installed, skipping YAML config")
            return {}

    def _load_json(self, path: Path) -> Dict[str, Any]:
        """加载 JSON 文件"""
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    def _load_from_env(self, name: str) -> Dict[str, Any]:
        """从环境变量加载配置"""
        prefix = f"{self._env_prefix}{name.upper().replace('/', '_')}_"
        data = {}

        for key, value in os.environ.items():
            if key.startswith(prefix):
                # 移除前缀并转换为小写
                config_key = key[len(prefix):].lower()
                # 处理嵌套键（用双下划线分隔）
                keys = config_key.split("__")
                self._set_nested(data, keys, self._parse_env_value(value))

        return data

    def _parse_env_value(self, value: str) -> Any:
        """解析环境变量值"""
        # 尝试解析为 JSON
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            pass

        # 布尔值
        if value.lower() in ("true", "yes", "1"):
            return True
        if value.lower() in ("false", "no", "0"):
            return False

        # 数字
        try:
            if "." in value:
                return float(value)
            return int(value)
        except ValueError:
            pass

        return value

    def _set_nested(self, data: Dict, keys: List[str], value: Any) -> None:
        """设置嵌套字典值"""
        for key in keys[:-1]:
            data = data.setdefault(key, {})
        data[keys[-1]] = value

    def _deep_merge(self, base: Dict, override: Dict) -> Dict:
        """深度合并字典"""
        result = base.copy()
        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._deep_merge(result[key], value)
            else:
                result[key] = value
        return result

    def _dict_to_dataclass(self, data: Dict[str, Any], cls: Type[T]) -> T:
        """将字典转换为 dataclass"""
        if not is_dataclass(cls):
            return data

        field_types = {f.name: f.type for f in fields(cls)}
        kwargs = {}

        for field_name, field_type in field_types.items():
            if field_name in data:
                value = data[field_name]

                # 处理嵌套 dataclass
                if is_dataclass(field_type) and isinstance(value, dict):
                    value = self._dict_to_dataclass(value, field_type)
                # 处理 Optional 类型
                elif hasattr(field_type, "__origin__"):
                    origin = getattr(field_type, "__origin__", None)
                    if origin is type(None) or str(origin) == "typing.Union":
                        args = getattr(field_type, "__args__", ())
                        for arg in args:
                            if is_dataclass(arg) and isinstance(value, dict):
                                value = self._dict_to_dataclass(value, arg)
                                break

                kwargs[field_name] = value

        return cls(**kwargs)

    def save(self, name: str, config: Any, format: str = "yaml") -> None:
        """保存配置到文件"""
        if is_dataclass(config):
            data = asdict(config)
        elif isinstance(config, dict):
            data = config
        else:
            raise ConfigError(f"Cannot save config of type {type(config)}")

        path = self._config_path / f"{name}.{format}"
        path.parent.mkdir(parents=True, exist_ok=True)

        if format == "yaml":
            try:
                import yaml
                with open(path, "w", encoding="utf-8") as f:
                    yaml.dump(data, f, default_flow_style=False, allow_unicode=True)
            except ImportError:
                format = "json"

        if format == "json":
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

        # 清除缓存
        self.invalidate(name)

    def invalidate(self, name: Optional[str] = None) -> None:
        """使缓存失效"""
        with self._lock:
            if name:
                keys_to_remove = [k for k in self._cache if k.startswith(name)]
                for key in keys_to_remove:
                    del self._cache[key]
            else:
                self._cache.clear()

    def watch(self, callback: Callable) -> None:
        """监听配置变更"""
        self._watchers.append(callback)

    def reload(self) -> None:
        """重新加载所有配置"""
        self.invalidate()
        for watcher in self._watchers:
            try:
                watcher()
            except Exception as e:
                logger.error(f"Config watcher error: {e}")

    def get_all_configs(self) -> Dict[str, Any]:
        """获取所有已加载的配置"""
        with self._lock:
            return dict(self._cache)


# 全局配置中心实例
_global_config_center: Optional[ConfigCenter] = None
_config_lock = threading.Lock()


def get_config_center(config_path: str = "config") -> ConfigCenter:
    """获取全局配置中心实例"""
    global _global_config_center
    if _global_config_center is None:
        with _config_lock:
            if _global_config_center is None:
                _global_config_center = ConfigCenter(config_path)
    return _global_config_center


def reset_config_center() -> None:
    """重置全局配置中心（主要用于测试）"""
    global _global_config_center
    with _config_lock:
        _global_config_center = None
