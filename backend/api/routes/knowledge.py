"""
知识库API路由
提供知识库管理接口
"""
import os
import sys
from typing import Optional, List

from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from pydantic import BaseModel

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

from backend.knowledge.multi_collection_kb import MultiCollectionKB

# 导入异步工具
try:
    from backend.core.async_utils import get_async_executor
    ASYNC_UTILS_AVAILABLE = True
except ImportError:
    ASYNC_UTILS_AVAILABLE = False

router = APIRouter(prefix="/knowledge", tags=["知识库"])


class AddTextRequest(BaseModel):
    """添加文本请求模型"""
    collection_name: str
    text: str
    source: str = "uploaded"
    category: str = "general"
    target_user: str = "both"
    priority: int = 3
    keywords: Optional[List[str]] = None
    operator: str = "api"


class SearchRequest(BaseModel):
    """搜索请求模型"""
    query: str
    collection_name: Optional[str] = None
    user_type: Optional[str] = "both"
    k: int = 4


class CollectionStats(BaseModel):
    """集合统计模型"""
    collection_name: str
    document_count: int
    description: str
    target_user: str


# 延迟加载知识库
_multi_kb = None


def get_multi_kb():
    global _multi_kb
    if _multi_kb is None:
        _multi_kb = MultiCollectionKB()
    return _multi_kb


@router.get("/collections")
async def list_collections():
    """
    列出所有可用集合
    """
    kb = get_multi_kb()

    # 使用线程池执行阻塞操作
    if ASYNC_UTILS_AVAILABLE:
        executor = get_async_executor()
        collections = await executor.run_in_thread(kb.list_collections)
        stats = await executor.run_in_thread(kb.get_all_stats)
    else:
        collections = kb.list_collections()
        stats = kb.get_all_stats()

    return {
        "collections": collections,
        "stats": stats,
    }


@router.get("/collections/{collection_name}/stats")
async def get_collection_stats(collection_name: str):
    """
    获取指定集合的统计信息
    """
    kb = get_multi_kb()

    # 使用线程池执行阻塞操作
    if ASYNC_UTILS_AVAILABLE:
        executor = get_async_executor()
        stats = await executor.run_in_thread(kb.get_collection_stats, collection_name)
    else:
        stats = kb.get_collection_stats(collection_name)

    if "error" in stats:
        raise HTTPException(status_code=404, detail=stats["error"])
    return stats


@router.post("/add-text")
async def add_text(request: AddTextRequest):
    """
    向指定集合添加文本内容
    """
    kb = get_multi_kb()

    # 使用线程池执行阻塞操作（向量化和存储是CPU/IO密集型）
    if ASYNC_UTILS_AVAILABLE:
        executor = get_async_executor()
        result = await executor.run_in_thread(
            kb.add_text,
            collection_name=request.collection_name,
            text=request.text,
            source=request.source,
            category=request.category,
            target_user=request.target_user,
            priority=request.priority,
            keywords=request.keywords,
            operator=request.operator,
        )
    else:
        result = kb.add_text(
            collection_name=request.collection_name,
            text=request.text,
            source=request.source,
            category=request.category,
            target_user=request.target_user,
            priority=request.priority,
            keywords=request.keywords,
            operator=request.operator,
        )

    return {"result": result}


@router.post("/upload-file")
async def upload_file(
    file: UploadFile = File(...),
    collection_name: str = Form(...),
    category: str = Form("general"),
    target_user: str = Form("both"),
    priority: int = Form(3),
    keywords: str = Form(""),
    operator: str = Form("api"),
):
    """
    上传文件到指定集合

    支持 .txt 和 .pdf 文件
    """
    kb = get_multi_kb()

    # 检查文件类型
    filename = file.filename.lower()
    if not (filename.endswith(".txt") or filename.endswith(".pdf")):
        raise HTTPException(status_code=400, detail="仅支持 .txt 和 .pdf 文件")

    # 解析关键词
    keyword_list = [k.strip() for k in keywords.split(",") if k.strip()] if keywords else None

    if filename.endswith(".pdf"):
        # 保存临时文件
        import tempfile
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            content = await file.read()
            tmp.write(content)
            tmp_path = tmp.name

        try:
            # 使用线程池执行阻塞操作
            if ASYNC_UTILS_AVAILABLE:
                executor = get_async_executor()
                result = await executor.run_in_thread(
                    kb.add_pdf,
                    collection_name=collection_name,
                    pdf_path=tmp_path,
                    source=f"uploaded:{file.filename}",
                    category=category,
                    target_user=target_user,
                    priority=priority,
                    keywords=keyword_list,
                    operator=operator,
                )
            else:
                result = kb.add_pdf(
                    collection_name=collection_name,
                    pdf_path=tmp_path,
                    source=f"uploaded:{file.filename}",
                    category=category,
                    target_user=target_user,
                    priority=priority,
                    keywords=keyword_list,
                    operator=operator,
                )
        finally:
            os.unlink(tmp_path)
    else:
        # 处理文本文件
        content = await file.read()
        text = content.decode("utf-8")

        # 使用线程池执行阻塞操作
        if ASYNC_UTILS_AVAILABLE:
            executor = get_async_executor()
            result = await executor.run_in_thread(
                kb.add_text,
                collection_name=collection_name,
                text=text,
                source=f"uploaded:{file.filename}",
                category=category,
                target_user=target_user,
                priority=priority,
                keywords=keyword_list,
                operator=operator,
            )
        else:
            result = kb.add_text(
                collection_name=collection_name,
                text=text,
                source=f"uploaded:{file.filename}",
                category=category,
                target_user=target_user,
                priority=priority,
                keywords=keyword_list,
                operator=operator,
            )

    return {"result": result, "filename": file.filename}


@router.post("/search")
async def search(request: SearchRequest):
    """
    搜索知识库

    可以指定集合名称或按用户类型搜索
    """
    kb = get_multi_kb()

    # 使用线程池执行阻塞操作（向量搜索是IO密集型）
    if ASYNC_UTILS_AVAILABLE:
        executor = get_async_executor()
        if request.collection_name:
            results = await executor.run_in_thread(
                kb.search, request.query, request.collection_name, k=request.k
            )
        else:
            results = await executor.run_in_thread(
                kb.search_by_user_type, request.query, request.user_type, k=request.k
            )
    else:
        if request.collection_name:
            results = kb.search(request.query, request.collection_name, k=request.k)
        else:
            results = kb.search_by_user_type(request.query, request.user_type, k=request.k)

    return {
        "query": request.query,
        "results": [
            {
                "content": doc.page_content,
                "metadata": doc.metadata,
                "score": score,
            }
            for doc, score in results
        ],
    }
