
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

md5_path = "./md5.text"


# DashScope API Key
dashscope_api_key = os.getenv("DASHSCOPE_API_KEY", "")
if dashscope_api_key:
    os.environ["DASHSCOPE_API_KEY"] = dashscope_api_key

# Chroma - 多集合配置
persist_directory = "./chroma_db"
default_collection_name = "rag"  # 默认集合（向后兼容）
collection_name = default_collection_name  # 别名，供旧代码兼容

# 多集合架构配置
COLLECTIONS = {
    "decoration_general": {
        "name": "decoration_general",
        "description": "装修风格、材料、施工知识",
        "target_user": "both",
    },
    "smart_home": {
        "name": "smart_home",
        "description": "智能家居选购和配置",
        "target_user": "both",
    },
    "dongju_c_end": {
        "name": "dongju_c_end",
        "description": "补贴政策、使用流程、逛店指南",
        "target_user": "c_end",
    },
    "dongju_b_end": {
        "name": "dongju_b_end",
        "description": "入驻指南、数据产品、经营分析",
        "target_user": "b_end",
    },
    "merchant_info": {
        "name": "merchant_info",
        "description": "商家信息、品类、评价",
        "target_user": "both",
    },
}

# 用户类型到集合的映射
USER_TYPE_COLLECTIONS = {
    "c_end": ["decoration_general", "smart_home", "dongju_c_end", "merchant_info"],
    "b_end": ["decoration_general", "smart_home", "dongju_b_end", "merchant_info"],
    "both": list(COLLECTIONS.keys()),
}

# spliter
chunk_size = 1000
chunk_overlap = 100
separators = ["\n\n", "\n", ".", "!", "?", "。", "！", "？", " ", ""]
max_split_char_number = 1000        # 文本分割的阈值

#
similarity_threshold = 4            # 检索返回匹配的文档数量
search_score_threshold = 0.8        # 混合检索阈值 (L2距离)：高于此值视为不相关，将触发联网搜索


embedding_model_name = "text-embedding-v4"
chat_model_name = "qwen3-max"

session_config = {
        "configurable": {
            "session_id": "user_001",
        }
    }

# API配置
API_RATE_LIMIT = "60/minute"  # 限流配置
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "your-secret-key-change-in-production")
JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30
