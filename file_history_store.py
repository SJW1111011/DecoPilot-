"""
会话历史存储模块
支持文件存储和 Redis 分布式存储
"""
import json
import os
import time
import threading
from typing import Sequence, Optional, Dict
from langchain_core.chat_history import BaseChatMessageHistory
from langchain_core.messages import BaseMessage, message_to_dict, messages_from_dict

# 尝试导入 Redis
try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False


# 存储后端类型
STORAGE_BACKEND = os.getenv("HISTORY_STORAGE_BACKEND", "file")  # file / redis
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
REDIS_DB = int(os.getenv("REDIS_DB", "0"))
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD", None)


def get_history(session_id: str) -> BaseChatMessageHistory:
    """
    获取会话历史存储实例

    根据环境配置自动选择存储后端
    """
    if STORAGE_BACKEND == "redis" and REDIS_AVAILABLE:
        return RedisChatMessageHistory(
            session_id=session_id,
            host=REDIS_HOST,
            port=REDIS_PORT,
            db=REDIS_DB,
            password=REDIS_PASSWORD,
        )
    else:
        return FileChatMessageHistory(session_id, "./chat_history")


class FileChatMessageHistory(BaseChatMessageHistory):
    def __init__(self, session_id, storage_path):
        self.session_id = session_id        # 会话id
        self.storage_path = storage_path    # 不同会话id的存储文件，所在的文件夹路径
        # 完整的文件路径
        self.file_path = os.path.join(self.storage_path, self.session_id)

        # 确保文件夹是存在的
        os.makedirs(os.path.dirname(self.file_path), exist_ok=True)

    def add_messages(self, messages: Sequence[BaseMessage]) -> None:
        # Sequence序列 类似list、tuple
        all_messages = list(self.messages)      # 已有的消息列表
        all_messages.extend(messages)           # 新的和已有的融合成一个list

        # 将数据同步写入到本地文件中
        # 类对象写入文件 -> 一堆二进制
        # 为了方便，可以将BaseMessage消息转为字典（借助json模块以json字符串写入文件）
        # 官方message_to_dict：单个消息对象（BaseMessage类实例） -> 字典
        # new_messages = []
        # for message in all_messages:
        #     d = message_to_dict(message)
        #     new_messages.append(d)

        new_messages = [message_to_dict(message) for message in all_messages]
        # 将数据写入文件
        with open(self.file_path, "w", encoding="utf-8") as f:
            json.dump(new_messages, f)

    @property       # @property装饰器将messages方法变成成员属性用
    def messages(self) -> list[BaseMessage]:
        # 当前文件内： list[字典]
        try:
            with open(self.file_path, "r", encoding="utf-8") as f:
                messages_data = json.load(f)    # 返回值就是：list[字典]
                return messages_from_dict(messages_data)
        except FileNotFoundError:
            return []

    def clear(self) -> None:
        with open(self.file_path, "w", encoding="utf-8") as f:
            json.dump([], f)


class RedisChatMessageHistory(BaseChatMessageHistory):
    """
    Redis 分布式会话历史存储

    支持多实例部署，会话数据在 Redis 中共享
    """

    def __init__(self, session_id: str, host: str = "localhost",
                 port: int = 6379, db: int = 0, password: str = None,
                 ttl: int = 86400 * 7, key_prefix: str = "chat_history:"):
        """
        初始化 Redis 会话存储

        Args:
            session_id: 会话 ID
            host: Redis 主机
            port: Redis 端口
            db: Redis 数据库编号
            password: Redis 密码
            ttl: 会话过期时间（秒），默认7天
            key_prefix: Redis 键前缀
        """
        self.session_id = session_id
        self.ttl = ttl
        self.key = f"{key_prefix}{session_id}"

        if not REDIS_AVAILABLE:
            raise ImportError("Redis 未安装，请运行: pip install redis")

        self._redis = redis.Redis(
            host=host,
            port=port,
            db=db,
            password=password,
            decode_responses=True,
        )

        # 测试连接
        try:
            self._redis.ping()
        except redis.ConnectionError as e:
            raise ConnectionError(f"无法连接到 Redis: {e}")

    def add_messages(self, messages: Sequence[BaseMessage]) -> None:
        """添加消息到历史"""
        # 获取现有消息
        all_messages = list(self.messages)
        all_messages.extend(messages)

        # 转换为字典列表
        messages_data = [message_to_dict(msg) for msg in all_messages]

        # 存储到 Redis
        self._redis.set(
            self.key,
            json.dumps(messages_data, ensure_ascii=False),
            ex=self.ttl
        )

    @property
    def messages(self) -> list[BaseMessage]:
        """获取所有消息"""
        try:
            data = self._redis.get(self.key)
            if data:
                messages_data = json.loads(data)
                return messages_from_dict(messages_data)
            return []
        except Exception:
            return []

    def clear(self) -> None:
        """清空会话历史"""
        self._redis.delete(self.key)

    def get_session_info(self) -> Dict:
        """获取会话信息"""
        ttl = self._redis.ttl(self.key)
        msg_count = len(self.messages)
        return {
            "session_id": self.session_id,
            "message_count": msg_count,
            "ttl_seconds": ttl,
            "storage_type": "redis",
        }


class SessionManager:
    """
    会话管理器

    统一管理所有会话，支持会话列表、清理过期会话等
    """

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._sessions: Dict[str, BaseChatMessageHistory] = {}
                    cls._instance._redis = None
                    cls._instance._init_redis()
        return cls._instance

    def _init_redis(self):
        """初始化 Redis 连接（如果可用）"""
        if STORAGE_BACKEND == "redis" and REDIS_AVAILABLE:
            try:
                self._redis = redis.Redis(
                    host=REDIS_HOST,
                    port=REDIS_PORT,
                    db=REDIS_DB,
                    password=REDIS_PASSWORD,
                    decode_responses=True,
                )
                self._redis.ping()
            except Exception:
                self._redis = None

    def get_session(self, session_id: str) -> BaseChatMessageHistory:
        """获取或创建会话"""
        if session_id not in self._sessions:
            self._sessions[session_id] = get_history(session_id)
        return self._sessions[session_id]

    def list_sessions(self) -> list[str]:
        """列出所有会话 ID"""
        if self._redis:
            # 从 Redis 获取所有会话键
            keys = self._redis.keys("chat_history:*")
            return [k.replace("chat_history:", "") for k in keys]
        else:
            # 从文件系统获取
            storage_path = "./chat_history"
            if os.path.exists(storage_path):
                return os.listdir(storage_path)
            return []

    def delete_session(self, session_id: str) -> bool:
        """删除会话"""
        try:
            session = self.get_session(session_id)
            session.clear()
            if session_id in self._sessions:
                del self._sessions[session_id]
            return True
        except Exception:
            return False

    def cleanup_expired(self, max_age_days: int = 7) -> int:
        """清理过期会话（仅文件存储）"""
        if self._redis:
            # Redis 自动处理过期
            return 0

        storage_path = "./chat_history"
        if not os.path.exists(storage_path):
            return 0

        count = 0
        max_age_seconds = max_age_days * 86400
        now = time.time()

        for filename in os.listdir(storage_path):
            filepath = os.path.join(storage_path, filename)
            if os.path.isfile(filepath):
                mtime = os.path.getmtime(filepath)
                if now - mtime > max_age_seconds:
                    os.remove(filepath)
                    count += 1

        return count

    def get_stats(self) -> Dict:
        """获取会话统计"""
        sessions = self.list_sessions()
        return {
            "total_sessions": len(sessions),
            "storage_backend": STORAGE_BACKEND,
            "redis_available": self._redis is not None,
        }


def get_session_manager() -> SessionManager:
    """获取会话管理器单例"""
    return SessionManager()
