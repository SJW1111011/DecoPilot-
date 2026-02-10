import os
import datetime
import sys
# Load env for DashScope
from dotenv import load_dotenv
load_dotenv()

# 添加backend目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "backend"))

from langchain_core.documents import Document
from langchain_core.output_parsers import StrOutputParser

from langchain_core.runnables import RunnablePassthrough, RunnableWithMessageHistory, RunnableLambda
from file_history_store import get_history
from vector_stores import VectorStoreService
from langchain_community.embeddings import DashScopeEmbeddings
import config_data as config
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_community.chat_models.tongyi import ChatTongyi
from langchain_community.tools import DuckDuckGoSearchRun

# 尝试导入多集合知识库
try:
    from backend.knowledge.multi_collection_kb import MultiCollectionKB
    MULTI_KB_AVAILABLE = True
except ImportError:
    MULTI_KB_AVAILABLE = False


def print_prompt(prompt):
    print("="*20)

    print(prompt.to_string())
    print("="*20)

    return prompt


class RagService(object):
    def __init__(self, user_type: str = "both"):
        """
        初始化RAG服务

        Args:
            user_type: 用户类型 (c_end|b_end|both)，用于多集合检索
        """
        # Ensure env var is set from config if not already
        if not os.environ.get("DASHSCOPE_API_KEY") and config.dashscope_api_key:
            os.environ["DASHSCOPE_API_KEY"] = config.dashscope_api_key

        self.user_type = user_type

        # 初始化多集合知识库（如果可用）
        if MULTI_KB_AVAILABLE:
            self.multi_kb = MultiCollectionKB()
        else:
            self.multi_kb = None

        # 保留原有的单集合向量服务（向后兼容）
        self.vector_service = VectorStoreService(
            embedding=DashScopeEmbeddings(model=config.embedding_model_name)
        )


        self.prompt_template = ChatPromptTemplate.from_messages(
            [
                ("system", "你是一个专业的装修顾问。请基于以下参考资料回答用户的问题。\n"
                 "当前时间: {current_time}\n"
                 "参考资料包含本地知识库和互联网搜索结果。\n"
                 "如果参考资料中有相关信息，请依据资料回答；如果没有，请说明无法回答。\n"
                 "参考资料:{context}。"),
                ("system", "并且我提供用户的对话历史记录，如下："),
                MessagesPlaceholder("history"),
                ("user", "请回答用户提问：{input}")
            ]
        )

        self.chat_model = ChatTongyi(model=config.chat_model_name)
        self.search_tool = DuckDuckGoSearchRun()
        
        # UI Control Flags
        self.enable_search = True
        self.show_thinking = True

        self.chain = self.__get_chain()

    def __hybrid_retriever(self, query: str) -> list[Document]:
        """混合检索策略：
        1. 优先使用多集合知识库（按用户类型检索）
        2. 回退到单集合检索
        3. 检查匹配分数 (L2距离)
        4. 如果所有文档的分数都高于阈值(search_score_threshold)，则触发联网搜索
        """
        logs = []
        logs.append(f"正在检索: {query}")
        logs.append(f"用户类型: {self.user_type}")
        print(f"正在检索: {query} (用户类型: {self.user_type})")

        relevant_docs = []
        best_score = float('inf')

        # 1. 尝试多集合检索
        if self.multi_kb and self.user_type in ["c_end", "b_end", "both"]:
            logs.append(f"使用多集合检索模式")
            print(f"使用多集合检索模式")

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
        else:
            # 2. 回退到单集合检索
            logs.append("使用单集合检索模式")
            print("使用单集合检索模式")

            local_results = self.vector_service.vector_store.similarity_search_with_score(
                query,
                k=config.similarity_threshold
            )

            for doc, score in local_results:
                best_score = min(best_score, score)
                if score <= config.search_score_threshold:
                    relevant_docs.append(doc)

        log_msg = f"本地检索结果: {len(relevant_docs)} 个相关文档 (最佳分数: {best_score:.4f}, 阈值: {config.search_score_threshold})"
        logs.append(log_msg)
        print(log_msg)

        # 3. 判断是否需要联网
        if not relevant_docs:
            if self.enable_search:
                logs.append("本地知识库无相关内容，触发联网搜索...")
                print("本地知识库无相关内容，触发联网搜索...")
                try:
                    search_result = self.search_tool.invoke(query)
                    logs.append("联网搜索完成")
                    print("联网搜索完成")
                    relevant_docs = [Document(page_content=f"【联网搜索结果】\n{search_result}", metadata={"source": "internet"})]
                except Exception as e:
                    logs.append(f"联网搜索失败: {e}")
                    print(f"联网搜索失败: {e}")
                    relevant_docs = [Document(page_content="无法连接到互联网获取更多信息。", metadata={"source": "error"})]
            else:
                logs.append("本地无相关内容，且联网搜索已禁用。")
                print("本地无相关内容，且联网搜索已禁用。")
                relevant_docs = [Document(page_content="知识库中未找到相关信息，且未启用联网搜索。", metadata={"source": "none"})]

        # 将思考过程（logs）附加到第一个文档的元数据中
        if relevant_docs:
            if "thinking_log" not in relevant_docs[0].metadata:
                relevant_docs[0].metadata["thinking_log"] = []
            relevant_docs[0].metadata["thinking_log"].extend(logs)
        else:
            relevant_docs = [Document(page_content="无相关信息", metadata={"thinking_log": logs, "source": "none"})]

        return relevant_docs

    def __get_chain(self):
        """获取最终的执行链"""
        
        # 使用自定义的混合检索器
        retriever = RunnableLambda(self.__hybrid_retriever)

        def format_document(docs: list[Document]):
            if not docs:
                return "无相关参考资料"

            formatted_str = ""
            for doc in docs:
                source = doc.metadata.get("source", "local")
                formatted_str += f"[{source}] 文档片段：{doc.page_content}\n\n"

            return formatted_str

        def format_for_retriever(value: dict) -> str:
            return value["input"]

        def format_for_prompt_template(value):
            # {input, context, history}
            new_value = {}
            new_value["input"] = value["input"]["input"]
            new_value["context"] = value["context"]
            new_value["history"] = value["input"]["history"]
            new_value["current_time"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            return new_value

        # 生成链 (Answer Generation)
        gen_chain = (
            RunnableLambda(format_for_prompt_template) 
            | self.prompt_template 
            | print_prompt 
            | self.chat_model 
            | StrOutputParser()
        )

        # 主链：同时返回检索到的文档（包含思考过程）和生成的答案
        chain = (
            {
                "input": RunnablePassthrough(),
                "retrieved_docs": RunnableLambda(format_for_retriever) | retriever,
            }
            | RunnablePassthrough.assign(context=lambda x: format_document(x["retrieved_docs"]))
            | RunnablePassthrough.assign(answer=gen_chain)
        )

        conversation_chain = RunnableWithMessageHistory(
            chain,
            get_history,
            input_messages_key="input",
            history_messages_key="history",
            output_messages_key="answer", # 指明历史记录中保存的是 answer 字段
        )

        return conversation_chain


if __name__ == '__main__':
    # session id 配置
    session_config = {
        "configurable": {
            "session_id": "user_001",
        }
    }

    res = RagService().chain.invoke({"input": "针织毛衣如何保养？"}, session_config)
    print(res)

