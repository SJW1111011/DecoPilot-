"""
记忆系统单元测试
测试 backend/core/memory.py 的核心功能
"""
import pytest
import os
import sys
import tempfile
import shutil
import time
import uuid

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.core.memory import (
    MemoryItem, MemoryType, UserProfile,
    InMemoryStore, PersistentMemoryStore, SQLiteMemoryStore,
    MemoryManager, get_memory_manager
)


class TestMemoryItem:
    """测试 MemoryItem 类"""

    def test_create_memory_item(self):
        """测试创建记忆项"""
        item = MemoryItem(
            id="test_001",
            content="测试内容",
            memory_type=MemoryType.SHORT_TERM,
            importance=0.8
        )
        assert item.id == "test_001"
        assert item.content == "测试内容"
        assert item.memory_type == MemoryType.SHORT_TERM
        assert item.importance == 0.8

    def test_memory_item_defaults(self):
        """测试记忆项默认值"""
        item = MemoryItem(
            id="test_002",
            content="测试内容",
            memory_type=MemoryType.SHORT_TERM
        )
        assert item.importance == 0.5
        assert item.access_count == 0
        assert item.metadata == {}

    def test_memory_item_to_dict(self):
        """测试转换为字典"""
        item = MemoryItem(
            id="test_003",
            content="测试内容",
            memory_type=MemoryType.LONG_TERM,
            importance=0.5
        )
        data = item.to_dict()
        assert data["id"] == "test_003"
        assert data["content"] == "测试内容"
        assert data["memory_type"] == "long_term"
        assert data["importance"] == 0.5


class TestUserProfile:
    """测试 UserProfile 类"""

    def test_create_user_profile(self):
        """测试创建用户画像"""
        profile = UserProfile(user_id="test_user", user_type="c_end")
        assert profile.user_id == "test_user"
        assert profile.user_type == "c_end"
        assert profile.interests == {}
        assert profile.preferred_styles == []

    def test_update_interest(self):
        """测试更新兴趣"""
        profile = UserProfile(user_id="test_user", user_type="c_end")
        profile.update_interest("现代简约", 0.5)
        assert "现代简约" in profile.interests
        assert profile.interests["现代简约"] == 0.5

        # 再次更新，应该累加
        profile.update_interest("现代简约", 0.3)
        assert profile.interests["现代简约"] == pytest.approx(0.8, rel=0.01)

    def test_interest_decay(self):
        """测试兴趣衰减"""
        profile = UserProfile(user_id="test_user", user_type="c_end")
        profile.update_interest("北欧", 1.0)
        profile.decay_interests(0.1)
        assert profile.interests["北欧"] < 1.0

    def test_preferred_styles(self):
        """测试偏好风格列表"""
        profile = UserProfile(user_id="test_user", user_type="c_end")
        profile.preferred_styles.append("现代简约")
        profile.preferred_styles.append("北欧")
        assert "现代简约" in profile.preferred_styles
        assert "北欧" in profile.preferred_styles
        assert len(profile.preferred_styles) == 2

    def test_b_end_profile(self):
        """测试 B 端用户画像"""
        profile = UserProfile(
            user_id="merchant_001",
            user_type="b_end",
            shop_name="测试店铺",
            shop_category="家具"
        )
        assert profile.user_type == "b_end"
        assert profile.shop_name == "测试店铺"
        assert profile.shop_category == "家具"


class TestInMemoryStore:
    """测试 InMemoryStore 类"""

    def test_save_and_get(self):
        """测试保存和获取"""
        store = InMemoryStore(max_size=100)
        item = MemoryItem(
            id="item_001",
            content="测试内容",
            memory_type=MemoryType.SHORT_TERM,
            importance=0.8
        )
        store.save(item)

        retrieved = store.get("item_001")
        assert retrieved is not None
        assert retrieved.content == "测试内容"

    def test_get_nonexistent(self):
        """测试获取不存在的项"""
        store = InMemoryStore()
        item = store.get("nonexistent")
        assert item is None

    def test_delete(self):
        """测试删除"""
        store = InMemoryStore()
        item = MemoryItem(
            id="item_002",
            content="测试内容",
            memory_type=MemoryType.SHORT_TERM
        )
        store.save(item)

        result = store.delete("item_002")
        assert result is True
        assert store.get("item_002") is None

    def test_search(self):
        """测试搜索"""
        store = InMemoryStore()
        store.save(MemoryItem(
            id="item_003",
            content="现代简约风格装修",
            memory_type=MemoryType.SHORT_TERM
        ))
        store.save(MemoryItem(
            id="item_004",
            content="北欧风格设计",
            memory_type=MemoryType.SHORT_TERM
        ))

        results = store.search("现代简约")
        assert len(results) >= 1
        assert any("现代简约" in r.content for r in results)

    def test_max_size_eviction(self):
        """测试容量限制和淘汰"""
        store = InMemoryStore(max_size=5)

        for i in range(10):
            store.save(MemoryItem(
                id=f"item_{i}",
                content=f"内容 {i}",
                memory_type=MemoryType.SHORT_TERM,
                importance=0.1 * i
            ))

        # 存储大小不应超过最大值
        stats = store.stats()
        assert stats["size"] <= 5

    def test_clear(self):
        """测试清空"""
        store = InMemoryStore()
        store.save(MemoryItem(
            id="item_005",
            content="测试",
            memory_type=MemoryType.SHORT_TERM
        ))
        store.clear()

        stats = store.stats()
        assert stats["size"] == 0

    def test_stats(self):
        """测试统计信息"""
        store = InMemoryStore(max_size=100)
        store.save(MemoryItem(
            id="item_006",
            content="测试",
            memory_type=MemoryType.SHORT_TERM
        ))

        # 命中
        store.get("item_006")
        # 未命中
        store.get("nonexistent")

        stats = store.stats()
        assert "size" in stats
        assert "hits" in stats
        assert "misses" in stats
        assert stats["hits"] >= 1
        assert stats["misses"] >= 1


class TestPersistentMemoryStore:
    """测试 PersistentMemoryStore 类"""

    @pytest.fixture
    def temp_storage_path(self):
        """创建临时存储路径"""
        temp_dir = tempfile.mkdtemp()
        storage_path = os.path.join(temp_dir, "test_memory.json")
        yield storage_path
        shutil.rmtree(temp_dir, ignore_errors=True)

    def test_save_and_get(self, temp_storage_path):
        """测试保存和获取"""
        store = PersistentMemoryStore(storage_path=temp_storage_path)
        item = MemoryItem(
            id="persist_001",
            content="持久化测试",
            memory_type=MemoryType.LONG_TERM,
            importance=0.9
        )
        store.save(item)

        retrieved = store.get("persist_001")
        assert retrieved is not None
        assert retrieved.content == "持久化测试"

    def test_search(self, temp_storage_path):
        """测试搜索"""
        store = PersistentMemoryStore(storage_path=temp_storage_path)
        store.save(MemoryItem(
            id="persist_002",
            content="装修预算规划",
            memory_type=MemoryType.LONG_TERM
        ))

        results = store.search("预算")
        assert len(results) >= 1


class TestMemoryManager:
    """测试 MemoryManager 类"""

    @pytest.fixture
    def memory_manager(self):
        """创建测试用的记忆管理器"""
        return get_memory_manager()

    def test_working_memory(self, memory_manager):
        """测试工作记忆"""
        session_id = f"test_session_{uuid.uuid4().hex[:8]}"

        memory_manager.set_working_memory(session_id, "current_task", "装修咨询")
        value = memory_manager.get_working_memory(session_id, "current_task")
        assert value == "装修咨询"

    def test_get_or_create_profile(self, memory_manager):
        """测试获取或创建用户画像"""
        user_id = f"test_user_{uuid.uuid4().hex[:8]}"

        profile = memory_manager.get_or_create_profile(user_id, "c_end")
        assert profile is not None
        assert profile.user_id == user_id
        assert profile.user_type == "c_end"

    def test_update_profile(self, memory_manager):
        """测试更新用户画像"""
        user_id = f"test_user_{uuid.uuid4().hex[:8]}"

        profile = memory_manager.get_or_create_profile(user_id, "c_end")
        profile.update_interest("现代简约", 0.5)

        # 重新获取应该保持更新
        profile2 = memory_manager.get_or_create_profile(user_id, "c_end")
        assert "现代简约" in profile2.interests

    def test_short_term_memory(self, memory_manager):
        """测试短期记忆"""
        session_id = f"test_session_{uuid.uuid4().hex[:8]}"

        item = MemoryItem(
            id=f"short_{uuid.uuid4().hex[:8]}",
            content="用户询问了装修风格",
            memory_type=MemoryType.SHORT_TERM,
            importance=0.7
        )
        memory_manager.short_term.save(item)

        retrieved = memory_manager.short_term.get(item.id)
        assert retrieved is not None


class TestMemoryIntegration:
    """集成测试"""

    def test_full_workflow(self):
        """测试完整工作流程"""
        manager = get_memory_manager()
        user_id = f"integration_user_{uuid.uuid4().hex[:8]}"
        session_id = f"integration_session_{uuid.uuid4().hex[:8]}"

        # 1. 创建用户画像
        profile = manager.get_or_create_profile(user_id, "c_end")
        profile.update_interest("现代简约", 0.8)
        profile.preferred_styles.append("现代简约")

        # 2. 设置工作记忆
        manager.set_working_memory(session_id, "user_id", user_id)
        manager.set_working_memory(session_id, "topic", "装修咨询")

        # 3. 添加短期记忆
        item = MemoryItem(
            id=f"msg_{uuid.uuid4().hex[:8]}",
            content="用户想了解现代简约风格的装修方案",
            memory_type=MemoryType.SHORT_TERM,
            importance=0.8
        )
        manager.short_term.save(item)

        # 4. 验证数据
        assert manager.get_working_memory(session_id, "topic") == "装修咨询"
        assert "现代简约" in profile.interests


class TestSQLiteMemoryStore:
    """测试 SQLiteMemoryStore 类"""

    @pytest.fixture
    def temp_db_path(self):
        """创建临时数据库路径"""
        temp_dir = tempfile.mkdtemp()
        db_path = os.path.join(temp_dir, "test_memory.db")
        yield db_path
        shutil.rmtree(temp_dir, ignore_errors=True)

    def test_save_and_get(self, temp_db_path):
        """测试保存和获取"""
        store = SQLiteMemoryStore(db_path=temp_db_path)
        item = MemoryItem(
            id="sqlite_001",
            content="SQLite 测试内容",
            memory_type=MemoryType.LONG_TERM,
            importance=0.9
        )
        result = store.save(item)
        assert result is True

        retrieved = store.get("sqlite_001")
        assert retrieved is not None
        assert retrieved.content == "SQLite 测试内容"
        assert retrieved.importance == 0.9

    def test_get_nonexistent(self, temp_db_path):
        """测试获取不存在的项"""
        store = SQLiteMemoryStore(db_path=temp_db_path)
        item = store.get("nonexistent")
        assert item is None

    def test_delete(self, temp_db_path):
        """测试删除"""
        store = SQLiteMemoryStore(db_path=temp_db_path)
        item = MemoryItem(
            id="sqlite_002",
            content="待删除内容",
            memory_type=MemoryType.LONG_TERM
        )
        store.save(item)

        result = store.delete("sqlite_002")
        assert result is True
        assert store.get("sqlite_002") is None

    def test_search(self, temp_db_path):
        """测试搜索"""
        store = SQLiteMemoryStore(db_path=temp_db_path)
        store.save(MemoryItem(
            id="sqlite_003",
            content="现代简约风格装修方案",
            memory_type=MemoryType.LONG_TERM
        ))
        store.save(MemoryItem(
            id="sqlite_004",
            content="北欧风格设计理念",
            memory_type=MemoryType.LONG_TERM
        ))

        results = store.search("现代简约")
        assert len(results) >= 1
        assert any("现代简约" in r.content for r in results)

    def test_search_by_user(self, temp_db_path):
        """测试按用户搜索"""
        store = SQLiteMemoryStore(db_path=temp_db_path)
        store.save(MemoryItem(
            id="sqlite_005",
            content="用户A的装修偏好",
            memory_type=MemoryType.LONG_TERM,
            metadata={"user_id": "user_a"}
        ))
        store.save(MemoryItem(
            id="sqlite_006",
            content="用户B的装修偏好",
            memory_type=MemoryType.LONG_TERM,
            metadata={"user_id": "user_b"}
        ))

        results = store.search_by_user("user_a")
        assert len(results) >= 1
        assert all(r.metadata.get("user_id") == "user_a" for r in results)

    def test_search_by_session(self, temp_db_path):
        """测试按会话搜索"""
        store = SQLiteMemoryStore(db_path=temp_db_path)
        session_id = f"session_{uuid.uuid4().hex[:8]}"

        store.save(MemoryItem(
            id="sqlite_007",
            content="会话消息1",
            memory_type=MemoryType.SHORT_TERM,
            metadata={"session_id": session_id}
        ))
        store.save(MemoryItem(
            id="sqlite_008",
            content="会话消息2",
            memory_type=MemoryType.SHORT_TERM,
            metadata={"session_id": session_id}
        ))

        results = store.search_by_session(session_id)
        assert len(results) == 2

    def test_delete_by_session(self, temp_db_path):
        """测试按会话删除"""
        store = SQLiteMemoryStore(db_path=temp_db_path)
        session_id = f"session_{uuid.uuid4().hex[:8]}"

        store.save(MemoryItem(
            id="sqlite_009",
            content="待删除消息1",
            memory_type=MemoryType.SHORT_TERM,
            metadata={"session_id": session_id}
        ))
        store.save(MemoryItem(
            id="sqlite_010",
            content="待删除消息2",
            memory_type=MemoryType.SHORT_TERM,
            metadata={"session_id": session_id}
        ))

        deleted_count = store.delete_by_session(session_id)
        assert deleted_count == 2
        assert len(store.search_by_session(session_id)) == 0

    def test_max_size_eviction(self, temp_db_path):
        """测试容量限制和淘汰"""
        store = SQLiteMemoryStore(db_path=temp_db_path, max_size=10)

        for i in range(20):
            store.save(MemoryItem(
                id=f"sqlite_evict_{i}",
                content=f"内容 {i}",
                memory_type=MemoryType.LONG_TERM,
                importance=0.1 * (i % 10)
            ))

        stats = store.stats()
        assert stats["size"] <= 10

    def test_stats(self, temp_db_path):
        """测试统计信息"""
        store = SQLiteMemoryStore(db_path=temp_db_path)
        store.save(MemoryItem(
            id="sqlite_stats_001",
            content="测试",
            memory_type=MemoryType.LONG_TERM
        ))

        # 命中
        store.get("sqlite_stats_001")
        # 未命中
        store.get("nonexistent")

        stats = store.stats()
        assert stats["storage_type"] == "sqlite"
        assert stats["size"] >= 1
        assert stats["hits"] >= 1
        assert stats["misses"] >= 1

    def test_concurrent_access(self, temp_db_path):
        """测试并发访问"""
        import threading

        store = SQLiteMemoryStore(db_path=temp_db_path)
        errors = []

        def writer(thread_id):
            try:
                for i in range(10):
                    store.save(MemoryItem(
                        id=f"concurrent_{thread_id}_{i}",
                        content=f"线程 {thread_id} 消息 {i}",
                        memory_type=MemoryType.LONG_TERM
                    ))
            except Exception as e:
                errors.append(e)

        def reader(thread_id):
            try:
                for i in range(10):
                    store.search(f"线程")
            except Exception as e:
                errors.append(e)

        threads = []
        for i in range(3):
            threads.append(threading.Thread(target=writer, args=(i,)))
            threads.append(threading.Thread(target=reader, args=(i,)))

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0, f"并发访问出错: {errors}"


class TestMemoryManagerBackends:
    """测试 MemoryManager 不同后端"""

    @pytest.fixture
    def temp_storage_dir(self):
        """创建临时存储目录"""
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        shutil.rmtree(temp_dir, ignore_errors=True)

    def test_sqlite_backend(self, temp_storage_dir):
        """测试 SQLite 后端"""
        manager = MemoryManager(
            storage_dir=temp_storage_dir,
            use_persistence=True,
            backend="sqlite"
        )
        assert manager.backend == "sqlite"
        assert isinstance(manager.long_term, SQLiteMemoryStore)

    def test_file_backend(self, temp_storage_dir):
        """测试文件后端"""
        manager = MemoryManager(
            storage_dir=temp_storage_dir,
            use_persistence=True,
            backend="file"
        )
        assert manager.backend == "file"
        assert isinstance(manager.long_term, PersistentMemoryStore)

    def test_memory_backend(self, temp_storage_dir):
        """测试内存后端"""
        manager = MemoryManager(
            storage_dir=temp_storage_dir,
            use_persistence=False,
            backend="memory"
        )
        assert isinstance(manager.long_term, InMemoryStore)

    def test_add_and_retrieve_long_term(self, temp_storage_dir):
        """测试添加和检索长期记忆"""
        manager = MemoryManager(
            storage_dir=temp_storage_dir,
            use_persistence=True,
            backend="sqlite"
        )
        user_id = f"test_user_{uuid.uuid4().hex[:8]}"

        # 添加长期记忆
        item_id = manager.add_to_long_term(
            user_id=user_id,
            content="用户喜欢现代简约风格",
            importance=0.8,
            metadata={"topic": "装修偏好"}
        )

        # 搜索长期记忆
        results = manager.search_long_term(user_id, "现代简约")
        assert len(results) >= 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
