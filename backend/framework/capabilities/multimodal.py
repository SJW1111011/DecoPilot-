"""
多模态能力

提供智能体的多模态处理能力:
- 图片理解和分析
- 文档解析
- 音频处理（预留）
- 视频处理（预留）
"""

from abc import abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Protocol, runtime_checkable, Union
from enum import Enum
from pathlib import Path
import asyncio
import logging
import base64

from .base import CapabilityMixin, register_capability
from ..events import Event, EventType, get_event_bus
from ..config import MultimodalConfig

logger = logging.getLogger(__name__)


class MediaType(str, Enum):
    """媒体类型"""
    IMAGE = "image"
    DOCUMENT = "document"
    AUDIO = "audio"
    VIDEO = "video"


class ImageAnalysisType(str, Enum):
    """图片分析类型"""
    GENERAL = "general"  # 通用描述
    DECORATION_STYLE = "decoration_style"  # 装修风格识别
    SPACE_LAYOUT = "space_layout"  # 空间布局分析
    MATERIAL = "material"  # 材料识别
    FURNITURE = "furniture"  # 家具识别
    DEFECT = "defect"  # 缺陷检测


@dataclass
class MediaContent:
    """媒体内容"""
    type: MediaType
    data: Union[str, bytes]  # base64 或文件路径
    filename: Optional[str] = None
    mime_type: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_file(cls, file_path: str) -> "MediaContent":
        """从文件创建"""
        path = Path(file_path)
        suffix = path.suffix.lower().lstrip(".")

        # 确定媒体类型
        if suffix in ["jpg", "jpeg", "png", "gif", "webp", "bmp"]:
            media_type = MediaType.IMAGE
            mime_type = f"image/{suffix if suffix != 'jpg' else 'jpeg'}"
        elif suffix in ["pdf", "docx", "xlsx", "txt", "doc", "xls"]:
            media_type = MediaType.DOCUMENT
            mime_type = f"application/{suffix}"
        elif suffix in ["mp3", "wav", "ogg", "m4a"]:
            media_type = MediaType.AUDIO
            mime_type = f"audio/{suffix}"
        elif suffix in ["mp4", "avi", "mov", "webm"]:
            media_type = MediaType.VIDEO
            mime_type = f"video/{suffix}"
        else:
            raise ValueError(f"Unsupported file format: {suffix}")

        return cls(
            type=media_type,
            data=file_path,
            filename=path.name,
            mime_type=mime_type
        )

    @classmethod
    def from_base64(
        cls,
        data: str,
        media_type: MediaType,
        mime_type: str,
        filename: Optional[str] = None
    ) -> "MediaContent":
        """从 base64 创建"""
        return cls(
            type=media_type,
            data=data,
            filename=filename,
            mime_type=mime_type
        )

    def to_base64(self) -> str:
        """转换为 base64"""
        if isinstance(self.data, bytes):
            return base64.b64encode(self.data).decode()
        elif Path(self.data).exists():
            with open(self.data, "rb") as f:
                return base64.b64encode(f.read()).decode()
        return self.data  # 已经是 base64


@dataclass
class AnalysisResult:
    """分析结果"""
    media_type: MediaType
    analysis_type: str
    content: Dict[str, Any]
    confidence: float = 0.0
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)


@runtime_checkable
class MultimodalCapability(Protocol):
    """多模态能力协议"""

    async def analyze_image(
        self,
        image: MediaContent,
        analysis_type: ImageAnalysisType = ImageAnalysisType.GENERAL
    ) -> AnalysisResult:
        """分析图片"""
        ...

    async def parse_document(
        self,
        document: MediaContent
    ) -> AnalysisResult:
        """解析文档"""
        ...

    async def process(
        self,
        media: MediaContent,
        prompt: Optional[str] = None
    ) -> AnalysisResult:
        """通用处理"""
        ...


@register_capability("multimodal", version="2.0.0", description="多模态处理能力")
class MultimodalMixin(CapabilityMixin):
    """
    多模态能力混入

    提供多模态内容处理功能:
    - 图片分析（装修风格、空间布局等）
    - 文档解析（报价单、合同等）
    """

    _capability_name = "multimodal"
    _capability_version = "2.0.0"

    # 分析提示词模板
    ANALYSIS_PROMPTS = {
        ImageAnalysisType.GENERAL: "请描述这张图片的内容。",
        ImageAnalysisType.DECORATION_STYLE: """
请分析这张装修图片的风格，包括：
1. 主要风格类型（现代简约/北欧/新中式/轻奢/日式等）
2. 色彩搭配特点
3. 主要材质
4. 空间感受
5. 适合人群
""",
        ImageAnalysisType.SPACE_LAYOUT: """
请分析这张图片中的空间布局，包括：
1. 空间类型（客厅/卧室/厨房/卫生间等）
2. 面积估算
3. 功能分区
4. 动线设计
5. 采光情况
6. 改进建议
""",
        ImageAnalysisType.MATERIAL: """
请识别这张图片中的装修材料，包括：
1. 地面材料
2. 墙面材料
3. 天花板材料
4. 门窗材料
5. 材料品质评估
6. 价格区间估算
""",
        ImageAnalysisType.FURNITURE: """
请识别这张图片中的家具，包括：
1. 家具类型和数量
2. 风格特点
3. 材质判断
4. 品质评估
5. 价格区间估算
""",
        ImageAnalysisType.DEFECT: """
请检查这张装修图片中是否存在质量问题，包括：
1. 墙面问题（裂缝、空鼓、不平整等）
2. 地面问题（起翘、缝隙、不平等）
3. 施工问题（接缝、收口等）
4. 安全隐患
5. 整改建议
"""
    }

    def __init__(self, config: MultimodalConfig = None):
        super().__init__()
        self._multimodal_config = config or MultimodalConfig()
        self._event_bus = get_event_bus()
        self._analysis_history: List[AnalysisResult] = []

    async def _do_initialize(self) -> None:
        """初始化多模态系统"""
        logger.info("Multimodal system initialized")

    async def analyze_image(
        self,
        image: MediaContent,
        analysis_type: ImageAnalysisType = ImageAnalysisType.GENERAL
    ) -> AnalysisResult:
        """分析图片"""
        if image.type != MediaType.IMAGE:
            raise ValueError("Expected image content")

        await self._event_bus.emit(Event(
            type=EventType.MEDIA_PROCESSING,
            payload={
                "media_type": "image",
                "analysis_type": analysis_type.value
            },
            source="multimodal"
        ))

        try:
            # 获取分析提示词
            prompt = self.ANALYSIS_PROMPTS.get(analysis_type, self.ANALYSIS_PROMPTS[ImageAnalysisType.GENERAL])

            # 这里应该调用实际的视觉模型
            # 目前返回模拟结果
            result = await self._mock_image_analysis(image, analysis_type, prompt)

            await self._event_bus.emit(Event(
                type=EventType.MEDIA_PROCESSED,
                payload={
                    "media_type": "image",
                    "analysis_type": analysis_type.value,
                    "success": True
                },
                source="multimodal"
            ))

            self._analysis_history.append(result)
            return result

        except Exception as e:
            logger.error(f"Image analysis failed: {e}")
            await self._event_bus.emit(Event(
                type=EventType.MEDIA_FAILED,
                payload={"error": str(e)},
                source="multimodal"
            ))
            raise

    async def parse_document(self, document: MediaContent) -> AnalysisResult:
        """解析文档"""
        if document.type != MediaType.DOCUMENT:
            raise ValueError("Expected document content")

        await self._event_bus.emit(Event(
            type=EventType.MEDIA_PROCESSING,
            payload={"media_type": "document", "filename": document.filename},
            source="multimodal"
        ))

        try:
            # 根据文档类型选择解析方法
            mime_type = document.mime_type or ""

            if "pdf" in mime_type:
                result = await self._parse_pdf(document)
            elif "word" in mime_type or "docx" in mime_type:
                result = await self._parse_word(document)
            elif "excel" in mime_type or "xlsx" in mime_type:
                result = await self._parse_excel(document)
            else:
                result = await self._parse_text(document)

            await self._event_bus.emit(Event(
                type=EventType.MEDIA_PROCESSED,
                payload={"media_type": "document", "success": True},
                source="multimodal"
            ))

            self._analysis_history.append(result)
            return result

        except Exception as e:
            logger.error(f"Document parsing failed: {e}")
            await self._event_bus.emit(Event(
                type=EventType.MEDIA_FAILED,
                payload={"error": str(e)},
                source="multimodal"
            ))
            raise

    async def process(
        self,
        media: MediaContent,
        prompt: Optional[str] = None
    ) -> AnalysisResult:
        """通用处理"""
        if media.type == MediaType.IMAGE:
            return await self.analyze_image(media)
        elif media.type == MediaType.DOCUMENT:
            return await self.parse_document(media)
        else:
            raise ValueError(f"Unsupported media type: {media.type}")

    async def _mock_image_analysis(
        self,
        image: MediaContent,
        analysis_type: ImageAnalysisType,
        prompt: str
    ) -> AnalysisResult:
        """模拟图片分析（实际应调用视觉模型）"""
        # 模拟处理延迟
        await asyncio.sleep(0.5)

        content = {
            "description": "这是一张装修相关的图片",
            "analysis_type": analysis_type.value,
            "details": {
                "style": "现代简约",
                "colors": ["白色", "灰色", "原木色"],
                "materials": ["木地板", "乳胶漆", "玻璃"],
                "suggestions": ["整体风格统一", "采光良好"]
            }
        }

        return AnalysisResult(
            media_type=MediaType.IMAGE,
            analysis_type=analysis_type.value,
            content=content,
            confidence=0.85
        )

    async def _parse_pdf(self, document: MediaContent) -> AnalysisResult:
        """解析 PDF"""
        # 实际应使用 PDF 解析库
        return AnalysisResult(
            media_type=MediaType.DOCUMENT,
            analysis_type="pdf_parse",
            content={
                "filename": document.filename,
                "pages": 1,
                "text": "PDF 内容解析结果",
                "tables": [],
                "images": []
            },
            confidence=0.9
        )

    async def _parse_word(self, document: MediaContent) -> AnalysisResult:
        """解析 Word"""
        return AnalysisResult(
            media_type=MediaType.DOCUMENT,
            analysis_type="word_parse",
            content={
                "filename": document.filename,
                "text": "Word 内容解析结果",
                "tables": []
            },
            confidence=0.9
        )

    async def _parse_excel(self, document: MediaContent) -> AnalysisResult:
        """解析 Excel"""
        return AnalysisResult(
            media_type=MediaType.DOCUMENT,
            analysis_type="excel_parse",
            content={
                "filename": document.filename,
                "sheets": [],
                "data": []
            },
            confidence=0.9
        )

    async def _parse_text(self, document: MediaContent) -> AnalysisResult:
        """解析文本"""
        return AnalysisResult(
            media_type=MediaType.DOCUMENT,
            analysis_type="text_parse",
            content={
                "filename": document.filename,
                "text": "文本内容"
            },
            confidence=0.95
        )

    def get_analysis_history(self, limit: int = 100) -> List[AnalysisResult]:
        """获取分析历史"""
        return self._analysis_history[-limit:]

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            "total_analyses": len(self._analysis_history),
            "by_type": {}
        }
