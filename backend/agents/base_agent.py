"""
基础智能体类
提供智能体的通用功能和接口
"""
import os
import sys
import datetime
from abc import ABC, abstractmethod
from typing import Optional, AsyncGenerator

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from langchain_core.documents import Document
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough, RunnableWithMessageHistory, RunnableLambda
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_community.chat_models.tongyi import ChatTongyi
from langchain_community.embeddings import DashScopeEmbeddings
from langchain_community.tools import DuckDuckGoSearchRun

import config_data as config
from file_history_store import get_history
from backend.knowledge.multi_collection_kb import MultiCollectionKB


class BaseAgent(ABC):
    """智能体基类"""

    def __init__(self, user_type: str):
        """
        初始化智能体

        Args:
            user_type: 用户类型 (c_end|b_end)
        """
        if not os.environ.get("DASHSCOPE_API_KEY") and config.dashscope_api_key:
            os.environ["DASHSCOPE_API_KEY"] = config.dashscope_api_key

        self.user_type = user_type
        self.multi_kb = MultiCollectionKB()
        self.chat_model = ChatTongyi(model=config.chat_model_name)
        self.search_tool = DuckDuckGoSearchRun()
        self.enable_search = True
        self.show_thinking = True

        # 子类需要设置的属性
        self.system_prompt = self._get_system_prompt()
        self.prompt_template = self._build_prompt_template()
        self.chain = self._build_chain()

    @abstractmethod
    def _get_system_prompt(self) -> str:
        """获取系统提示词，子类必须实现"""
        pass

    def _build_prompt_template(self) -> ChatPromptTemplate:
        """构建提示词模板"""
        return ChatPromptTemplate.from_messages([
            ("system", self.system_prompt),
            ("system", "用户的对话历史记录如下："),
            MessagesPlaceholder("history"),
            ("user", "请回答用户提问：{input}")
        ])

    def _hybrid_retriever(self, query: str) -> list[Document]:
        """混合检索策略"""
        logs = []
        logs.append(f"正在检索: {query}")
        logs.append(f"用户类型: {self.user_type}")

        relevant_docs = []
        best_score = float('inf')

        # 多集合检索
        multi_results = self.multi_kb.search_by_user_type(
            query,
            self.user_type,
            k=config.similarity_threshold
        )

        for doc, score in multi_results:
            best_score = min(best_score, score)
            if score <= config.search_score_threshold:
                relevant_docs.append(doc)

        collections_searched = self.multi_kb.get_collections_for_user_type(self.user_type)
        logs.append(f"已检索集合: {', '.join(collections_searched)}")
        logs.append(f"检索结果: {len(relevant_docs)} 个相关文档 (最佳分数: {best_score:.4f})")

        # 联网搜索兜底
        if not relevant_docs and self.enable_search:
            logs.append("本地知识库无相关内容，触发联网搜索...")
            try:
                search_result = self.search_tool.invoke(query)
                logs.append("联网搜索完成")
                relevant_docs = [Document(
                    page_content=f"【联网搜索结果】\n{search_result}",
                    metadata={"source": "internet"}
                )]
            except Exception as e:
                logs.append(f"联网搜索失败: {e}")
                relevant_docs = [Document(
                    page_content="无法连接到互联网获取更多信息。",
                    metadata={"source": "error"}
                )]
        elif not relevant_docs:
            logs.append("本地无相关内容，且联网搜索已禁用。")
            relevant_docs = [Document(
                page_content="知识库中未找到相关信息。",
                metadata={"source": "none"}
            )]

        # 附加思考日志
        if relevant_docs:
            if "thinking_log" not in relevant_docs[0].metadata:
                relevant_docs[0].metadata["thinking_log"] = []
            relevant_docs[0].metadata["thinking_log"].extend(logs)

        return relevant_docs

    def _format_documents(self, docs: list[Document]) -> str:
        """格式化文档为上下文字符串"""
        if not docs:
            return "无相关参考资料"

        formatted = ""
        for doc in docs:
            source = doc.metadata.get("source", "local")
            collection = doc.metadata.get("collection", "unknown")
            formatted += f"[{source}|{collection}] {doc.page_content}\n\n"

        return formatted

    def _build_chain(self):
        """构建执行链"""
        retriever = RunnableLambda(self._hybrid_retriever)

        def format_for_retriever(value: dict) -> str:
            return value["input"]

        def format_for_prompt(value):
            return {
                "input": value["input"]["input"],
                "context": value["context"],
                "history": value["input"]["history"],
                "current_time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            }

        gen_chain = (
            RunnableLambda(format_for_prompt)
            | self.prompt_template
            | self.chat_model
            | StrOutputParser()
        )

        chain = (
            {
                "input": RunnablePassthrough(),
                "retrieved_docs": RunnableLambda(format_for_retriever) | retriever,
            }
            | RunnablePassthrough.assign(context=lambda x: self._format_documents(x["retrieved_docs"]))
            | RunnablePassthrough.assign(answer=gen_chain)
        )

        return RunnableWithMessageHistory(
            chain,
            get_history,
            input_messages_key="input",
            history_messages_key="history",
            output_messages_key="answer",
        )

    def invoke(self, message: str, session_id: str) -> dict:
        """同步调用智能体"""
        session_config = {"configurable": {"session_id": session_id}}
        return self.chain.invoke({"input": message}, session_config)

    async def astream(self, message: str, session_id: str) -> AsyncGenerator:
        """异步流式调用智能体"""
        session_config = {"configurable": {"session_id": session_id}}
        input_data = {"input": message}

        async for event in self.chain.astream_events(input_data, session_config, version="v1"):
            yield event
