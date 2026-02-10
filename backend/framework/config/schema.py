"""
配置模式定义

使用 dataclass 定义所有配置的结构和默认值
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from enum import Enum


class ReasoningStrategy(str, Enum):
    """推理策略"""
    DIRECT = "direct"
    CHAIN_OF_THOUGHT = "cot"
    TREE_OF_THOUGHT = "tot"
    REACT = "react"
    SELF_REFLECTION = "self_reflection"
    ADAPTIVE = "adaptive"


class MemoryBackend(str, Enum):
    """记忆存储后端"""
    MEMORY = "memory"
    SQLITE = "sqlite"
    REDIS = "redis"
    POSTGRESQL = "postgresql"


class LearningMode(str, Enum):
    """学习模式"""
    DISABLED = "disabled"
    PASSIVE = "passive"  # 仅收集反馈
    ACTIVE = "active"    # 主动学习和优化


@dataclass
class LLMConfig:
    """LLM 配置"""
    provider: str = "dashscope"
    model: str = "qwen-plus"
    temperature: float = 0.7
    max_tokens: int = 2000
    top_p: float = 0.9
    timeout: int = 30
    retry_count: int = 3
    retry_delay: float = 1.0
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    extra_params: Dict[str, Any] = field(default_factory=dict)


@dataclass
class EmbeddingConfig:
    """Embedding 配置"""
    provider: str = "dashscope"
    model: str = "text-embedding-v4"
    dimension: int = 1024
    batch_size: int = 32
    api_key: Optional[str] = None


@dataclass
class MemoryConfig:
    """记忆系统配置"""
    backend: MemoryBackend = MemoryBackend.SQLITE

    # 短期记忆配置
    short_term_ttl: int = 3600  # 秒
    short_term_max_items: int = 100

    # 长期记忆配置
    long_term_max_items: int = 10000
    long_term_importance_threshold: float = 0.5

    # 工作记忆配置
    working_memory_size: int = 50

    # 情景记忆配置
    episodic_max_episodes: int = 1000

    # 语义记忆配置
    semantic_enabled: bool = True

    # 持久化配置
    persistence_path: str = "data/memory"
    auto_save_interval: int = 300  # 秒

    # Redis 配置（如果使用 Redis 后端）
    redis_url: Optional[str] = None
    redis_prefix: str = "decopilot:memory:"


@dataclass
class ReasoningConfig:
    """推理引擎配置"""
    default_strategy: ReasoningStrategy = ReasoningStrategy.ADAPTIVE

    # 策略启用开关
    cot_enabled: bool = True
    tot_enabled: bool = True
    react_enabled: bool = True
    self_reflection_enabled: bool = True

    # 推理参数
    max_reasoning_steps: int = 10
    max_tree_depth: int = 3
    max_tree_branches: int = 3

    # 自适应策略参数
    complexity_threshold_simple: float = 0.3
    complexity_threshold_medium: float = 0.6

    # 超时配置
    step_timeout: int = 30
    total_timeout: int = 120


@dataclass
class ToolConfig:
    """工具系统配置"""
    timeout: int = 30
    max_retries: int = 3
    retry_delay: float = 1.0
    rate_limit: int = 60  # 每分钟最大调用次数

    # 并发配置
    max_concurrent_calls: int = 5

    # 缓存配置
    cache_enabled: bool = True
    cache_ttl: int = 300

    # 安全配置
    sandbox_enabled: bool = True
    allowed_tools: Optional[List[str]] = None
    blocked_tools: Optional[List[str]] = None


@dataclass
class MultimodalConfig:
    """多模态配置"""
    enabled: bool = True

    # 图片处理
    max_image_size: int = 10 * 1024 * 1024  # 10MB
    supported_image_formats: List[str] = field(
        default_factory=lambda: ["jpg", "jpeg", "png", "gif", "webp"]
    )

    # 文档处理
    max_document_size: int = 50 * 1024 * 1024  # 50MB
    supported_document_formats: List[str] = field(
        default_factory=lambda: ["pdf", "docx", "xlsx", "txt"]
    )

    # 处理参数
    image_analysis_timeout: int = 60
    document_parse_timeout: int = 120


@dataclass
class KnowledgeConfig:
    """知识库配置"""
    # 向量数据库配置
    vector_db: str = "chromadb"
    persist_directory: str = "data/chroma"

    # 分块配置
    chunk_size: int = 500
    chunk_overlap: int = 50

    # 检索配置
    default_top_k: int = 5
    similarity_threshold: float = 0.7

    # 集合配置
    collections: Dict[str, Dict[str, Any]] = field(default_factory=dict)

    # 缓存配置
    cache_enabled: bool = True
    cache_ttl: int = 600


@dataclass
class LearningConfig:
    """学习层配置"""
    mode: LearningMode = LearningMode.PASSIVE

    # 反馈收集
    feedback_enabled: bool = True
    implicit_feedback: bool = True  # 隐式反馈（如响应时间、重试次数）
    explicit_feedback: bool = True  # 显式反馈（用户评分）

    # 策略优化
    strategy_optimization_enabled: bool = True
    optimization_interval: int = 3600  # 秒
    min_samples_for_optimization: int = 100

    # 知识蒸馏
    knowledge_distillation_enabled: bool = False
    distillation_interval: int = 86400  # 秒

    # 持久化
    learning_data_path: str = "data/learning"

    # A/B 测试
    ab_testing_enabled: bool = False
    ab_test_ratio: float = 0.1


@dataclass
class ObservabilityConfig:
    """可观测性配置"""
    # 日志配置
    log_level: str = "INFO"
    log_format: str = "json"
    log_file: Optional[str] = None

    # 追踪配置
    tracing_enabled: bool = True
    trace_sample_rate: float = 1.0

    # 指标配置
    metrics_enabled: bool = True
    metrics_port: int = 9090
    metrics_path: str = "/metrics"

    # 健康检查
    health_check_enabled: bool = True
    health_check_interval: int = 30


@dataclass
class SecurityConfig:
    """安全配置"""
    # 输入验证
    input_validation_enabled: bool = True
    max_input_length: int = 10000

    # 输出过滤
    output_filtering_enabled: bool = True
    sensitive_patterns: List[str] = field(default_factory=list)

    # 速率限制
    rate_limit_enabled: bool = True
    rate_limit_requests: int = 60
    rate_limit_window: int = 60  # 秒

    # 认证
    auth_enabled: bool = False
    jwt_secret: Optional[str] = None
    jwt_expiry: int = 3600


@dataclass
class OrchestrationConfig:
    """编排层配置"""
    # 路由配置
    default_agent: str = "c_end"
    routing_strategy: str = "rule_based"  # rule_based | ml_based

    # 规划配置
    planning_enabled: bool = True
    max_plan_steps: int = 10

    # 协作配置
    collaboration_enabled: bool = True
    max_collaborating_agents: int = 3

    # 监督配置
    supervision_enabled: bool = True
    max_retries_per_step: int = 2


@dataclass
class AgentConfig:
    """智能体配置"""
    name: str = "default"
    type: str = "general"  # c_end | b_end | general | custom
    description: str = ""

    # 子配置
    llm: LLMConfig = field(default_factory=LLMConfig)
    memory: MemoryConfig = field(default_factory=MemoryConfig)
    reasoning: ReasoningConfig = field(default_factory=ReasoningConfig)
    tools: ToolConfig = field(default_factory=ToolConfig)
    multimodal: MultimodalConfig = field(default_factory=MultimodalConfig)

    # 提示词配置
    system_prompt: str = ""
    prompts: Dict[str, str] = field(default_factory=dict)

    # 能力配置
    capabilities: List[str] = field(
        default_factory=lambda: ["memory", "reasoning", "tools"]
    )

    # 元数据
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class FrameworkConfig:
    """框架总配置"""
    # 基础配置
    name: str = "DecoPilot"
    version: str = "2.0.0"
    environment: str = "development"  # development | staging | production

    # 子配置
    llm: LLMConfig = field(default_factory=LLMConfig)
    embedding: EmbeddingConfig = field(default_factory=EmbeddingConfig)
    memory: MemoryConfig = field(default_factory=MemoryConfig)
    reasoning: ReasoningConfig = field(default_factory=ReasoningConfig)
    tools: ToolConfig = field(default_factory=ToolConfig)
    multimodal: MultimodalConfig = field(default_factory=MultimodalConfig)
    knowledge: KnowledgeConfig = field(default_factory=KnowledgeConfig)
    learning: LearningConfig = field(default_factory=LearningConfig)
    observability: ObservabilityConfig = field(default_factory=ObservabilityConfig)
    security: SecurityConfig = field(default_factory=SecurityConfig)
    orchestration: OrchestrationConfig = field(default_factory=OrchestrationConfig)

    # 智能体配置
    agents: Dict[str, AgentConfig] = field(default_factory=dict)

    # 扩展配置
    extensions: Dict[str, Any] = field(default_factory=dict)
