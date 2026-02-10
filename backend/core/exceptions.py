"""
统一异常处理框架
定义项目中使用的所有自定义异常类
"""
from typing import Any, Dict, Optional
from enum import Enum


class ErrorCode(str, Enum):
    """错误代码枚举"""
    # 通用错误 (1xxx)
    UNKNOWN_ERROR = "E1000"
    VALIDATION_ERROR = "E1001"
    CONFIGURATION_ERROR = "E1002"
    TIMEOUT_ERROR = "E1003"
    RATE_LIMIT_ERROR = "E1004"

    # 记忆系统错误 (2xxx)
    MEMORY_ERROR = "E2000"
    MEMORY_STORE_ERROR = "E2001"
    MEMORY_RETRIEVE_ERROR = "E2002"
    MEMORY_CAPACITY_ERROR = "E2003"
    USER_PROFILE_ERROR = "E2004"

    # 推理引擎错误 (3xxx)
    REASONING_ERROR = "E3000"
    COMPLEXITY_ANALYSIS_ERROR = "E3001"
    CHAIN_CREATION_ERROR = "E3002"
    THOUGHT_TREE_ERROR = "E3003"

    # 工具系统错误 (4xxx)
    TOOL_ERROR = "E4000"
    TOOL_NOT_FOUND = "E4001"
    TOOL_DISABLED = "E4002"
    TOOL_EXECUTION_ERROR = "E4003"
    TOOL_TIMEOUT = "E4004"
    TOOL_PARAMETER_ERROR = "E4005"

    # 多模态错误 (5xxx)
    MULTIMODAL_ERROR = "E5000"
    IMAGE_PROCESSING_ERROR = "E5001"
    DOCUMENT_PARSING_ERROR = "E5002"
    VISION_MODEL_ERROR = "E5003"

    # Function Calling 错误 (6xxx)
    FUNCTION_CALLING_ERROR = "E6000"
    LLM_CALL_ERROR = "E6001"
    TOOL_SELECTION_ERROR = "E6002"

    # 智能体错误 (7xxx)
    AGENT_ERROR = "E7000"
    AGENT_PROCESS_ERROR = "E7001"
    CONTEXT_PREPARATION_ERROR = "E7002"
    RESPONSE_GENERATION_ERROR = "E7003"

    # 知识库错误 (8xxx)
    KNOWLEDGE_ERROR = "E8000"
    KNOWLEDGE_SEARCH_ERROR = "E8001"
    KNOWLEDGE_INDEX_ERROR = "E8002"
    EMBEDDING_ERROR = "E8003"

    # API 错误 (9xxx)
    API_ERROR = "E9000"
    AUTHENTICATION_ERROR = "E9001"
    AUTHORIZATION_ERROR = "E9002"
    REQUEST_VALIDATION_ERROR = "E9003"


class DecoPilotException(Exception):
    """
    DecoPilot 基础异常类

    所有自定义异常都应继承此类
    """

    def __init__(
        self,
        message: str,
        code: ErrorCode = ErrorCode.UNKNOWN_ERROR,
        details: Dict[str, Any] = None,
        cause: Exception = None
    ):
        """
        初始化异常

        Args:
            message: 错误消息
            code: 错误代码
            details: 额外的错误详情
            cause: 原始异常（如果有）
        """
        super().__init__(message)
        self.message = message
        self.code = code
        self.details = details or {}
        self.cause = cause

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        result = {
            "error": True,
            "code": self.code.value,
            "message": self.message,
        }
        if self.details:
            result["details"] = self.details
        if self.cause:
            result["cause"] = str(self.cause)
        return result

    def __str__(self) -> str:
        return f"[{self.code.value}] {self.message}"

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(code={self.code.value}, message={self.message!r})"


# === 记忆系统异常 ===

class MemoryException(DecoPilotException):
    """记忆系统异常基类"""

    def __init__(self, message: str, code: ErrorCode = ErrorCode.MEMORY_ERROR, **kwargs):
        super().__init__(message, code, **kwargs)


class MemoryStoreException(MemoryException):
    """记忆存储异常"""

    def __init__(self, message: str, **kwargs):
        super().__init__(message, ErrorCode.MEMORY_STORE_ERROR, **kwargs)


class MemoryRetrieveException(MemoryException):
    """记忆检索异常"""

    def __init__(self, message: str, **kwargs):
        super().__init__(message, ErrorCode.MEMORY_RETRIEVE_ERROR, **kwargs)


class MemoryCapacityException(MemoryException):
    """记忆容量异常"""

    def __init__(self, message: str, current_size: int = None, max_size: int = None, **kwargs):
        details = kwargs.pop("details", {})
        if current_size is not None:
            details["current_size"] = current_size
        if max_size is not None:
            details["max_size"] = max_size
        super().__init__(message, ErrorCode.MEMORY_CAPACITY_ERROR, details=details, **kwargs)


class UserProfileException(MemoryException):
    """用户画像异常"""

    def __init__(self, message: str, user_id: str = None, **kwargs):
        details = kwargs.pop("details", {})
        if user_id:
            details["user_id"] = user_id
        super().__init__(message, ErrorCode.USER_PROFILE_ERROR, details=details, **kwargs)


# === 推理引擎异常 ===

class ReasoningException(DecoPilotException):
    """推理引擎异常基类"""

    def __init__(self, message: str, code: ErrorCode = ErrorCode.REASONING_ERROR, **kwargs):
        super().__init__(message, code, **kwargs)


class ComplexityAnalysisException(ReasoningException):
    """复杂度分析异常"""

    def __init__(self, message: str, query: str = None, **kwargs):
        details = kwargs.pop("details", {})
        if query:
            details["query"] = query[:100]  # 截断长查询
        super().__init__(message, ErrorCode.COMPLEXITY_ANALYSIS_ERROR, details=details, **kwargs)


class ChainCreationException(ReasoningException):
    """推理链创建异常"""

    def __init__(self, message: str, **kwargs):
        super().__init__(message, ErrorCode.CHAIN_CREATION_ERROR, **kwargs)


class ThoughtTreeException(ReasoningException):
    """思维树异常"""

    def __init__(self, message: str, tree_id: str = None, **kwargs):
        details = kwargs.pop("details", {})
        if tree_id:
            details["tree_id"] = tree_id
        super().__init__(message, ErrorCode.THOUGHT_TREE_ERROR, details=details, **kwargs)


# === 工具系统异常 ===

class ToolException(DecoPilotException):
    """工具系统异常基类"""

    def __init__(self, message: str, code: ErrorCode = ErrorCode.TOOL_ERROR,
                 tool_name: str = None, **kwargs):
        details = kwargs.pop("details", {})
        if tool_name:
            details["tool_name"] = tool_name
        super().__init__(message, code, details=details, **kwargs)


class ToolNotFoundException(ToolException):
    """工具不存在异常"""

    def __init__(self, tool_name: str, **kwargs):
        super().__init__(
            f"工具 '{tool_name}' 不存在",
            ErrorCode.TOOL_NOT_FOUND,
            tool_name=tool_name,
            **kwargs
        )


class ToolDisabledException(ToolException):
    """工具已禁用异常"""

    def __init__(self, tool_name: str, **kwargs):
        super().__init__(
            f"工具 '{tool_name}' 已禁用",
            ErrorCode.TOOL_DISABLED,
            tool_name=tool_name,
            **kwargs
        )


class ToolExecutionException(ToolException):
    """工具执行异常"""

    def __init__(self, message: str, tool_name: str = None, **kwargs):
        super().__init__(message, ErrorCode.TOOL_EXECUTION_ERROR, tool_name=tool_name, **kwargs)


class ToolTimeoutException(ToolException):
    """工具超时异常"""

    def __init__(self, tool_name: str, timeout: float, **kwargs):
        details = kwargs.pop("details", {})
        details["timeout_seconds"] = timeout
        super().__init__(
            f"工具 '{tool_name}' 执行超时（{timeout}秒）",
            ErrorCode.TOOL_TIMEOUT,
            tool_name=tool_name,
            details=details,
            **kwargs
        )


class ToolParameterException(ToolException):
    """工具参数异常"""

    def __init__(self, message: str, tool_name: str = None,
                 parameter_name: str = None, **kwargs):
        details = kwargs.pop("details", {})
        if parameter_name:
            details["parameter_name"] = parameter_name
        super().__init__(message, ErrorCode.TOOL_PARAMETER_ERROR, tool_name=tool_name,
                        details=details, **kwargs)


# === 多模态异常 ===

class MultimodalException(DecoPilotException):
    """多模态处理异常基类"""

    def __init__(self, message: str, code: ErrorCode = ErrorCode.MULTIMODAL_ERROR, **kwargs):
        super().__init__(message, code, **kwargs)


class ImageProcessingException(MultimodalException):
    """图片处理异常"""

    def __init__(self, message: str, image_path: str = None, **kwargs):
        details = kwargs.pop("details", {})
        if image_path:
            details["image_path"] = image_path
        super().__init__(message, ErrorCode.IMAGE_PROCESSING_ERROR, details=details, **kwargs)


class DocumentParsingException(MultimodalException):
    """文档解析异常"""

    def __init__(self, message: str, document_path: str = None, **kwargs):
        details = kwargs.pop("details", {})
        if document_path:
            details["document_path"] = document_path
        super().__init__(message, ErrorCode.DOCUMENT_PARSING_ERROR, details=details, **kwargs)


class VisionModelException(MultimodalException):
    """视觉模型异常"""

    def __init__(self, message: str, model_name: str = None, **kwargs):
        details = kwargs.pop("details", {})
        if model_name:
            details["model_name"] = model_name
        super().__init__(message, ErrorCode.VISION_MODEL_ERROR, details=details, **kwargs)


# === Function Calling 异常 ===

class FunctionCallingException(DecoPilotException):
    """Function Calling 异常基类"""

    def __init__(self, message: str, code: ErrorCode = ErrorCode.FUNCTION_CALLING_ERROR, **kwargs):
        super().__init__(message, code, **kwargs)


class LLMCallException(FunctionCallingException):
    """LLM 调用异常"""

    def __init__(self, message: str, **kwargs):
        super().__init__(message, ErrorCode.LLM_CALL_ERROR, **kwargs)


class ToolSelectionException(FunctionCallingException):
    """工具选择异常"""

    def __init__(self, message: str, **kwargs):
        super().__init__(message, ErrorCode.TOOL_SELECTION_ERROR, **kwargs)


# === 智能体异常 ===

class AgentException(DecoPilotException):
    """智能体异常基类"""

    def __init__(self, message: str, code: ErrorCode = ErrorCode.AGENT_ERROR,
                 agent_name: str = None, **kwargs):
        details = kwargs.pop("details", {})
        if agent_name:
            details["agent_name"] = agent_name
        super().__init__(message, code, details=details, **kwargs)


class AgentProcessException(AgentException):
    """智能体处理异常"""

    def __init__(self, message: str, agent_name: str = None, **kwargs):
        super().__init__(message, ErrorCode.AGENT_PROCESS_ERROR, agent_name=agent_name, **kwargs)


class ContextPreparationException(AgentException):
    """上下文准备异常"""

    def __init__(self, message: str, **kwargs):
        super().__init__(message, ErrorCode.CONTEXT_PREPARATION_ERROR, **kwargs)


class ResponseGenerationException(AgentException):
    """响应生成异常"""

    def __init__(self, message: str, **kwargs):
        super().__init__(message, ErrorCode.RESPONSE_GENERATION_ERROR, **kwargs)


# === 知识库异常 ===

class KnowledgeException(DecoPilotException):
    """知识库异常基类"""

    def __init__(self, message: str, code: ErrorCode = ErrorCode.KNOWLEDGE_ERROR, **kwargs):
        super().__init__(message, code, **kwargs)


class KnowledgeSearchException(KnowledgeException):
    """知识库搜索异常"""

    def __init__(self, message: str, query: str = None, **kwargs):
        details = kwargs.pop("details", {})
        if query:
            details["query"] = query[:100]
        super().__init__(message, ErrorCode.KNOWLEDGE_SEARCH_ERROR, details=details, **kwargs)


class KnowledgeIndexException(KnowledgeException):
    """知识库索引异常"""

    def __init__(self, message: str, collection: str = None, **kwargs):
        details = kwargs.pop("details", {})
        if collection:
            details["collection"] = collection
        super().__init__(message, ErrorCode.KNOWLEDGE_INDEX_ERROR, details=details, **kwargs)


class EmbeddingException(KnowledgeException):
    """向量嵌入异常"""

    def __init__(self, message: str, **kwargs):
        super().__init__(message, ErrorCode.EMBEDDING_ERROR, **kwargs)


# === API 异常 ===

class APIException(DecoPilotException):
    """API 异常基类"""

    def __init__(self, message: str, code: ErrorCode = ErrorCode.API_ERROR,
                 status_code: int = 500, **kwargs):
        details = kwargs.pop("details", {})
        details["status_code"] = status_code
        super().__init__(message, code, details=details, **kwargs)
        self.status_code = status_code


class AuthenticationException(APIException):
    """认证异常"""

    def __init__(self, message: str = "认证失败", **kwargs):
        super().__init__(message, ErrorCode.AUTHENTICATION_ERROR, status_code=401, **kwargs)


class AuthorizationException(APIException):
    """授权异常"""

    def __init__(self, message: str = "权限不足", **kwargs):
        super().__init__(message, ErrorCode.AUTHORIZATION_ERROR, status_code=403, **kwargs)


class RequestValidationException(APIException):
    """请求验证异常"""

    def __init__(self, message: str, field: str = None, **kwargs):
        details = kwargs.pop("details", {})
        if field:
            details["field"] = field
        super().__init__(message, ErrorCode.REQUEST_VALIDATION_ERROR, status_code=400,
                        details=details, **kwargs)


# === 异常处理工具函数 ===

def wrap_exception(exc: Exception, wrapper_class: type = DecoPilotException,
                   message: str = None) -> DecoPilotException:
    """
    将普通异常包装为 DecoPilot 异常

    Args:
        exc: 原始异常
        wrapper_class: 包装类
        message: 自定义消息（可选）

    Returns:
        DecoPilotException 实例
    """
    if isinstance(exc, DecoPilotException):
        return exc

    return wrapper_class(
        message=message or str(exc),
        cause=exc
    )


def safe_execute(func, *args, default=None, exception_class: type = DecoPilotException,
                 **kwargs):
    """
    安全执行函数，捕获异常并返回默认值

    Args:
        func: 要执行的函数
        *args: 位置参数
        default: 异常时的默认返回值
        exception_class: 要捕获的异常类
        **kwargs: 关键字参数

    Returns:
        函数返回值或默认值
    """
    try:
        return func(*args, **kwargs)
    except exception_class:
        return default
    except Exception as e:
        # 记录未预期的异常
        from backend.core.logging_config import get_logger
        logger = get_logger("exceptions")
        logger.warning(f"safe_execute 捕获未预期异常: {e}")
        return default
