"""
多集合知识库管理模块
支持按用户类型（C端/B端）进行差异化检索
"""
import os
import sys
import hashlib
from datetime import datetime
from typing import Optional

# 添加父目录到路径以导入config
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from langchain_chroma import Chroma
from langchain_community.embeddings import DashScopeEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document
import config_data as config

try:
    from PyPDF2 import PdfReader
    PDF_SUPPORT = True
except ImportError:
    PDF_SUPPORT = False


class MultiCollectionKB:
    """多集合知识库管理器"""

    def __init__(self):
        os.makedirs(config.persist_directory, exist_ok=True)
        self.embedding = DashScopeEmbeddings(model=config.embedding_model_name)
        self.splitter = RecursiveCharacterTextSplitter(
            chunk_size=config.chunk_size,
            chunk_overlap=config.chunk_overlap,
            separators=config.separators,
            length_function=len,
        )
        self._collections: dict[str, Chroma] = {}
        self._init_collections()

    def _init_collections(self):
        """初始化所有配置的集合"""
        for name in config.COLLECTIONS:
            self._get_or_create_collection(name)

    def _get_or_create_collection(self, collection_name: str) -> Chroma:
        """获取或创建指定集合"""
        if collection_name not in self._collections:
            self._collections[collection_name] = Chroma(
                collection_name=collection_name,
                embedding_function=self.embedding,
                persist_directory=config.persist_directory,
            )
        return self._collections[collection_name]

    def get_collection(self, collection_name: str) -> Optional[Chroma]:
        """获取指定集合"""
        if collection_name in config.COLLECTIONS:
            return self._get_or_create_collection(collection_name)
        return None

    def list_collections(self) -> list[str]:
        """列出所有可用集合"""
        return list(config.COLLECTIONS.keys())

    def get_collections_for_user_type(self, user_type: str) -> list[str]:
        """根据用户类型获取可访问的集合列表"""
        return config.USER_TYPE_COLLECTIONS.get(user_type, [])

    @staticmethod
    def _get_md5(content: str) -> str:
        """计算内容的MD5哈希"""
        return hashlib.md5(content.encode("utf-8")).hexdigest()

    @staticmethod
    def _check_md5(md5_str: str) -> bool:
        """检查MD5是否已存在"""
        if not os.path.exists(config.md5_path):
            open(config.md5_path, "w", encoding="utf-8").close()
            return False
        with open(config.md5_path, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip() == md5_str:
                    return True
        return False

    @staticmethod
    def _save_md5(md5_str: str):
        """保存MD5记录"""
        with open(config.md5_path, "a", encoding="utf-8") as f:
            f.write(md5_str + "\n")

    def add_text(
        self,
        collection_name: str,
        text: str,
        source: str = "local",
        category: str = "general",
        target_user: str = "both",
        priority: int = 3,
        keywords: Optional[list[str]] = None,
        operator: str = "system",
    ) -> str:
        """
        向指定集合添加文本内容

        Args:
            collection_name: 集合名称
            text: 文本内容
            source: 来源 (local|crawled|uploaded)
            category: 分类 (decoration|subsidy|merchant)
            target_user: 目标用户 (c_end|b_end|both)
            priority: 优先级 (1-5)
            keywords: 关键词列表
            operator: 操作者

        Returns:
            操作结果消息
        """
        if collection_name not in config.COLLECTIONS:
            return f"[错误] 集合 {collection_name} 不存在"

        md5_hex = self._get_md5(text)
        if self._check_md5(md5_hex):
            return "[跳过] 内容已存在于知识库中"

        # 分割文本
        if len(text) > config.max_split_char_number:
            chunks = self.splitter.split_text(text)
        else:
            chunks = [text]

        # 构建元数据
        metadata = {
            "source": source,
            "category": category,
            "target_user": target_user,
            "priority": priority,
            "keywords": ",".join(keywords) if keywords else "",
            "create_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "operator": operator,
        }

        # 添加到集合
        collection = self._get_or_create_collection(collection_name)
        collection.add_texts(
            chunks,
            metadatas=[metadata for _ in chunks],
        )

        self._save_md5(md5_hex)
        return f"[成功] 已添加 {len(chunks)} 个文档块到集合 {collection_name}"

    def add_pdf(
        self,
        collection_name: str,
        pdf_path: str,
        source: str = "uploaded",
        category: str = "general",
        target_user: str = "both",
        priority: int = 3,
        keywords: Optional[list[str]] = None,
        operator: str = "system",
    ) -> str:
        """
        从PDF文件添加内容到指定集合

        Args:
            collection_name: 集合名称
            pdf_path: PDF文件路径
            其他参数同 add_text

        Returns:
            操作结果消息
        """
        if not PDF_SUPPORT:
            return "[错误] PDF支持未安装，请安装 PyPDF2: pip install PyPDF2"

        if not os.path.exists(pdf_path):
            return f"[错误] 文件不存在: {pdf_path}"

        try:
            reader = PdfReader(pdf_path)
            text_parts = []
            for page in reader.pages:
                page_text = page.extract_text()
                if page_text:
                    text_parts.append(page_text)

            if not text_parts:
                return "[错误] PDF文件中未提取到文本内容"

            full_text = "\n\n".join(text_parts)
            filename = os.path.basename(pdf_path)

            return self.add_text(
                collection_name=collection_name,
                text=full_text,
                source=f"pdf:{filename}",
                category=category,
                target_user=target_user,
                priority=priority,
                keywords=keywords,
                operator=operator,
            )
        except Exception as e:
            return f"[错误] PDF解析失败: {str(e)}"

    def search(
        self,
        query: str,
        collection_name: str,
        k: int = 4,
    ) -> list[tuple[Document, float]]:
        """
        在指定集合中搜索

        Args:
            query: 查询文本
            collection_name: 集合名称
            k: 返回结果数量

        Returns:
            (Document, score) 元组列表
        """
        collection = self.get_collection(collection_name)
        if not collection:
            return []

        return collection.similarity_search_with_score(query, k=k)

    def search_by_user_type(
        self,
        query: str,
        user_type: str,
        k: int = 4,
    ) -> list[tuple[Document, float]]:
        """
        根据用户类型在多个集合中搜索

        Args:
            query: 查询文本
            user_type: 用户类型 (c_end|b_end|both)
            k: 每个集合返回的结果数量

        Returns:
            合并后的 (Document, score) 元组列表，按分数排序
        """
        collections = self.get_collections_for_user_type(user_type)
        all_results = []

        for coll_name in collections:
            results = self.search(query, coll_name, k=k)
            # 在文档元数据中添加集合来源
            for doc, score in results:
                doc.metadata["collection"] = coll_name
                all_results.append((doc, score))

        # 按分数排序（L2距离越小越相关）
        all_results.sort(key=lambda x: x[1])

        return all_results[:k * 2]  # 返回前 k*2 个最相关结果

    def get_collection_stats(self, collection_name: str) -> dict:
        """获取集合统计信息"""
        collection = self.get_collection(collection_name)
        if not collection:
            return {"error": f"集合 {collection_name} 不存在"}

        try:
            count = collection._collection.count()
            return {
                "collection_name": collection_name,
                "document_count": count,
                "description": config.COLLECTIONS.get(collection_name, {}).get("description", ""),
                "target_user": config.COLLECTIONS.get(collection_name, {}).get("target_user", ""),
            }
        except Exception as e:
            return {"error": str(e)}

    def get_all_stats(self) -> list[dict]:
        """获取所有集合的统计信息"""
        return [self.get_collection_stats(name) for name in config.COLLECTIONS]


if __name__ == "__main__":
    # 测试代码
    kb = MultiCollectionKB()
    print("可用集合:", kb.list_collections())
    print("C端可访问集合:", kb.get_collections_for_user_type("c_end"))
    print("B端可访问集合:", kb.get_collections_for_user_type("b_end"))
    print("\n集合统计:")
    for stat in kb.get_all_stats():
        print(f"  {stat}")
