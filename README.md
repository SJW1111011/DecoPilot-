# DecoPilot (智装领航)

**DecoPilot** 是您的智能装修顾问（原名：装修智能顾问）。它基于 RAG (Retrieval-Augmented Generation) 技术，使用 LangChain、ChromaDB 和 DashScope (通义千问) 构建，能够根据本地知识库回答您的装修难题。

## 项目结构

- `app_qa.py`: 主程序，提供 Streamlit 聊天界面，用户在此提问。
- `app_file_uploader.py`: 知识库管理界面，支持上传 TXT 文件更新知识库。
- `rag.py`: RAG 核心逻辑，处理检索和生成。
- `ingest_data.py`: 数据导入脚本，用于初始化知识库。
- `config_data.py`: 配置文件。
- `knowledge_base.py` & `vector_stores.py`: 向量数据库和知识库管理服务。
- `data/`: 存放默认的知识库文件。

## 环境要求

- Python 3.8+
- 阿里云 DashScope API Key

## 安装步骤

1. 克隆项目到本地：
   ```bash
   git clone <your-repo-url>
   cd P4_RAG项目案例
   ```

2. 安装依赖：
   ```bash
   pip install langchain langchain-community langchain-chroma streamlit dashscope
   # 注意：可能还需要安装其他依赖，请根据运行报错补充
   ```

3. 配置环境变量：
   复制 `.env.example` 为 `.env`，并填入您的 API Key：
   ```bash
   cp .env.example .env
   ```
   在 `.env` 文件中修改：
   ```
   DASHSCOPE_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
   ```

## 使用方法

### 1. 初始化知识库
运行以下脚本将默认数据 (`data/装修小知识.txt`) 导入向量数据库：
```bash
python ingest_data.py
```

### 2. 启动问答系统
运行 Streamlit 应用：
```bash
streamlit run app_qa.py
```
访问浏览器显示的地址 (通常是 http://localhost:8501) 开始对话。

### 3. 更新知识库 (可选)
如果您有新的装修知识文档，可以运行上传服务：
```bash
streamlit run app_file_uploader.py
```
在网页中上传 TXT 文件即可自动更新知识库。

## 技术栈

- **LLM**: Qwen (通义千问)
- **Embedding**: DashScope Text Embedding
- **Vector Store**: Chroma
- **Framework**: LangChain
- **UI**: Streamlit

## 注意事项

- 请确保不要将 `.env` 文件提交到版本控制系统（已在 `.gitignore` 中配置）。
- 首次运行时会自动下载并构建向量数据库，可能需要一些时间。
