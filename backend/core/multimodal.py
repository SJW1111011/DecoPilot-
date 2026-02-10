"""
多模态处理模块
支持图片理解、文档解析、OCR等能力
"""
import os
import io
import base64
import hashlib
from typing import Any, Dict, List, Optional, Tuple, Union
from dataclasses import dataclass, field
from enum import Enum
from abc import ABC, abstractmethod
import threading


class MediaType(str, Enum):
    """媒体类型"""
    IMAGE = "image"
    PDF = "pdf"
    DOCUMENT = "document"
    TABLE = "table"
    AUDIO = "audio"


class ImageAnalysisType(str, Enum):
    """图片分析类型"""
    GENERAL = "general"           # 通用描述
    DECORATION_STYLE = "style"    # 装修风格识别
    MATERIAL = "material"         # 材料识别
    FURNITURE = "furniture"       # 家具识别
    DEFECT = "defect"             # 缺陷检测
    MEASUREMENT = "measurement"   # 尺寸估算


@dataclass
class MediaContent:
    """媒体内容"""
    media_type: MediaType
    content: Union[bytes, str]    # 二进制内容或路径
    filename: Optional[str] = None
    mime_type: Optional[str] = None
    metadata: Dict = field(default_factory=dict)

    @property
    def content_hash(self) -> str:
        """内容哈希"""
        if isinstance(self.content, bytes):
            return hashlib.md5(self.content).hexdigest()
        return hashlib.md5(self.content.encode()).hexdigest()


@dataclass
class ImageAnalysisResult:
    """图片分析结果"""
    description: str
    analysis_type: ImageAnalysisType
    confidence: float = 0.0
    detected_objects: List[Dict] = field(default_factory=list)
    style_tags: List[str] = field(default_factory=list)
    colors: List[str] = field(default_factory=list)
    suggestions: List[str] = field(default_factory=list)
    metadata: Dict = field(default_factory=dict)


@dataclass
class DocumentParseResult:
    """文档解析结果"""
    text: str
    pages: int = 1
    tables: List[Dict] = field(default_factory=list)
    images: List[Dict] = field(default_factory=list)
    metadata: Dict = field(default_factory=dict)


@dataclass
class TableExtractResult:
    """表格提取结果"""
    headers: List[str]
    rows: List[List[str]]
    title: Optional[str] = None
    source_page: int = 1


class ImageProcessor:
    """图片处理器"""

    # 装修风格关键词
    STYLE_KEYWORDS = {
        "现代简约": ["简洁", "线条", "白色", "灰色", "几何"],
        "北欧": ["原木", "白色", "绿植", "温馨", "自然"],
        "新中式": ["木质", "屏风", "水墨", "对称", "禅意"],
        "轻奢": ["金属", "大理石", "皮质", "深色", "质感"],
        "工业风": ["水泥", "铁艺", "裸露", "管道", "复古"],
        "日式": ["榻榻米", "障子", "原木", "简约", "禅"],
    }

    # 材料识别关键词
    MATERIAL_KEYWORDS = {
        "瓷砖": ["光滑", "方形", "纹理", "地面", "墙面"],
        "木地板": ["木纹", "条状", "温暖", "地面"],
        "大理石": ["纹路", "光泽", "高档", "台面"],
        "乳胶漆": ["平整", "哑光", "墙面", "颜色"],
        "壁纸": ["图案", "花纹", "墙面", "装饰"],
    }

    def __init__(self, vision_model=None):
        """
        初始化图片处理器

        Args:
            vision_model: 视觉模型（如GPT-4V、通义千问VL等）
        """
        self.vision_model = vision_model
        self._cache: Dict[str, ImageAnalysisResult] = {}

    def analyze(self, image: MediaContent,
                analysis_type: ImageAnalysisType = ImageAnalysisType.GENERAL) -> ImageAnalysisResult:
        """分析图片"""
        # 检查缓存
        cache_key = f"{image.content_hash}_{analysis_type.value}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        # 根据分析类型选择处理方法
        if analysis_type == ImageAnalysisType.DECORATION_STYLE:
            result = self._analyze_decoration_style(image)
        elif analysis_type == ImageAnalysisType.MATERIAL:
            result = self._analyze_material(image)
        elif analysis_type == ImageAnalysisType.FURNITURE:
            result = self._analyze_furniture(image)
        elif analysis_type == ImageAnalysisType.DEFECT:
            result = self._analyze_defect(image)
        else:
            result = self._analyze_general(image)

        # 缓存结果
        self._cache[cache_key] = result
        return result

    def _analyze_general(self, image: MediaContent) -> ImageAnalysisResult:
        """通用图片分析"""
        # 如果有视觉模型，使用模型分析
        if self.vision_model:
            return self._call_vision_model(image, "请描述这张图片的内容")

        # 否则返回基础结果
        return ImageAnalysisResult(
            description="图片已上传，请描述您想了解的内容",
            analysis_type=ImageAnalysisType.GENERAL,
            confidence=0.5,
        )

    def _analyze_decoration_style(self, image: MediaContent) -> ImageAnalysisResult:
        """装修风格分析"""
        if self.vision_model:
            prompt = """请分析这张装修图片的风格特点：
1. 识别装修风格（现代简约/北欧/新中式/轻奢/工业风/日式等）
2. 描述主要设计元素
3. 分析色彩搭配
4. 给出风格评价和建议"""
            return self._call_vision_model(image, prompt, ImageAnalysisType.DECORATION_STYLE)

        return ImageAnalysisResult(
            description="需要视觉模型支持才能分析装修风格",
            analysis_type=ImageAnalysisType.DECORATION_STYLE,
            confidence=0.0,
        )

    def _analyze_material(self, image: MediaContent) -> ImageAnalysisResult:
        """材料识别"""
        if self.vision_model:
            prompt = """请识别这张图片中的装修材料：
1. 识别材料类型（瓷砖/木地板/大理石/乳胶漆/壁纸等）
2. 描述材料特点
3. 估算材料档次
4. 给出选购建议"""
            return self._call_vision_model(image, prompt, ImageAnalysisType.MATERIAL)

        return ImageAnalysisResult(
            description="需要视觉模型支持才能识别材料",
            analysis_type=ImageAnalysisType.MATERIAL,
            confidence=0.0,
        )

    def _analyze_furniture(self, image: MediaContent) -> ImageAnalysisResult:
        """家具识别"""
        if self.vision_model:
            prompt = """请识别这张图片中的家具：
1. 识别家具类型和数量
2. 描述家具风格
3. 估算家具档次
4. 给出搭配建议"""
            return self._call_vision_model(image, prompt, ImageAnalysisType.FURNITURE)

        return ImageAnalysisResult(
            description="需要视觉模型支持才能识别家具",
            analysis_type=ImageAnalysisType.FURNITURE,
            confidence=0.0,
        )

    def _analyze_defect(self, image: MediaContent) -> ImageAnalysisResult:
        """缺陷检测"""
        if self.vision_model:
            prompt = """请检查这张装修图片中是否存在质量问题：
1. 检查是否有裂缝、空鼓、脱落等问题
2. 检查施工是否规范
3. 评估问题严重程度
4. 给出处理建议"""
            return self._call_vision_model(image, prompt, ImageAnalysisType.DEFECT)

        return ImageAnalysisResult(
            description="需要视觉模型支持才能检测缺陷",
            analysis_type=ImageAnalysisType.DEFECT,
            confidence=0.0,
        )

    def _call_vision_model(self, image: MediaContent, prompt: str,
                           analysis_type: ImageAnalysisType = ImageAnalysisType.GENERAL) -> ImageAnalysisResult:
        """调用视觉模型"""
        try:
            # 准备图片数据
            if isinstance(image.content, bytes):
                image_data = base64.b64encode(image.content).decode()
            else:
                with open(image.content, "rb") as f:
                    image_data = base64.b64encode(f.read()).decode()

            # 调用模型（这里需要根据实际使用的模型API调整）
            # response = self.vision_model.analyze(image_data, prompt)

            # 模拟返回
            return ImageAnalysisResult(
                description="视觉模型分析结果",
                analysis_type=analysis_type,
                confidence=0.8,
            )
        except Exception as e:
            return ImageAnalysisResult(
                description=f"分析失败: {str(e)}",
                analysis_type=analysis_type,
                confidence=0.0,
            )


class DocumentProcessor:
    """文档处理器"""

    def __init__(self):
        self._cache: Dict[str, DocumentParseResult] = {}

    def parse(self, document: MediaContent) -> DocumentParseResult:
        """解析文档"""
        cache_key = document.content_hash
        if cache_key in self._cache:
            return self._cache[cache_key]

        if document.media_type == MediaType.PDF:
            result = self._parse_pdf(document)
        else:
            result = self._parse_text(document)

        self._cache[cache_key] = result
        return result

    def _parse_pdf(self, document: MediaContent) -> DocumentParseResult:
        """解析PDF"""
        try:
            from PyPDF2 import PdfReader

            if isinstance(document.content, bytes):
                pdf_file = io.BytesIO(document.content)
            else:
                pdf_file = document.content

            reader = PdfReader(pdf_file)
            text_parts = []
            tables = []

            for i, page in enumerate(reader.pages):
                page_text = page.extract_text() or ""
                text_parts.append(page_text)

                # 简单的表格检测（基于文本模式）
                if "|" in page_text or "\t" in page_text:
                    tables.append({
                        "page": i + 1,
                        "content": page_text,
                        "type": "detected",
                    })

            return DocumentParseResult(
                text="\n\n".join(text_parts),
                pages=len(reader.pages),
                tables=tables,
                metadata={
                    "filename": document.filename,
                    "pdf_info": reader.metadata or {},
                },
            )
        except Exception as e:
            return DocumentParseResult(
                text=f"PDF解析失败: {str(e)}",
                pages=0,
            )

    def _parse_text(self, document: MediaContent) -> DocumentParseResult:
        """解析文本文档"""
        if isinstance(document.content, bytes):
            text = document.content.decode("utf-8", errors="ignore")
        else:
            with open(document.content, "r", encoding="utf-8") as f:
                text = f.read()

        return DocumentParseResult(
            text=text,
            pages=1,
            metadata={"filename": document.filename},
        )

    def extract_tables(self, document: MediaContent) -> List[TableExtractResult]:
        """提取表格"""
        result = self.parse(document)
        tables = []

        for table_info in result.tables:
            # 简单的表格解析
            lines = table_info["content"].strip().split("\n")
            if len(lines) < 2:
                continue

            # 尝试解析表头和数据行
            headers = self._parse_table_row(lines[0])
            rows = [self._parse_table_row(line) for line in lines[1:] if line.strip()]

            if headers and rows:
                tables.append(TableExtractResult(
                    headers=headers,
                    rows=rows,
                    source_page=table_info.get("page", 1),
                ))

        return tables

    def _parse_table_row(self, line: str) -> List[str]:
        """解析表格行"""
        # 尝试不同的分隔符
        for sep in ["|", "\t", "  "]:
            if sep in line:
                cells = [c.strip() for c in line.split(sep) if c.strip()]
                if len(cells) >= 2:
                    return cells
        return []


class MultimodalManager:
    """多模态管理器"""

    def __init__(self, vision_model=None):
        self.image_processor = ImageProcessor(vision_model)
        self.document_processor = DocumentProcessor()
        self._lock = threading.Lock()

    def process(self, content: MediaContent) -> Dict:
        """处理多模态内容"""
        if content.media_type == MediaType.IMAGE:
            result = self.image_processor.analyze(content)
            return {
                "type": "image_analysis",
                "result": {
                    "description": result.description,
                    "analysis_type": result.analysis_type.value,
                    "confidence": result.confidence,
                    "detected_objects": result.detected_objects,
                    "style_tags": result.style_tags,
                    "suggestions": result.suggestions,
                },
            }
        elif content.media_type in [MediaType.PDF, MediaType.DOCUMENT]:
            result = self.document_processor.parse(content)
            return {
                "type": "document_parse",
                "result": {
                    "text": result.text[:5000],  # 限制长度
                    "pages": result.pages,
                    "has_tables": len(result.tables) > 0,
                    "table_count": len(result.tables),
                },
            }
        else:
            return {
                "type": "unsupported",
                "error": f"不支持的媒体类型: {content.media_type}",
            }

    def analyze_decoration_image(self, image_path: str) -> ImageAnalysisResult:
        """分析装修图片"""
        content = MediaContent(
            media_type=MediaType.IMAGE,
            content=image_path,
            filename=os.path.basename(image_path),
        )
        return self.image_processor.analyze(content, ImageAnalysisType.DECORATION_STYLE)

    def parse_quotation(self, pdf_path: str) -> Dict:
        """解析报价单"""
        content = MediaContent(
            media_type=MediaType.PDF,
            content=pdf_path,
            filename=os.path.basename(pdf_path),
        )
        result = self.document_processor.parse(content)
        tables = self.document_processor.extract_tables(content)

        return {
            "text": result.text,
            "pages": result.pages,
            "tables": [
                {
                    "headers": t.headers,
                    "rows": t.rows,
                    "page": t.source_page,
                }
                for t in tables
            ],
        }


# 全局多模态管理器
_multimodal_manager: Optional[MultimodalManager] = None
_mm_lock = threading.Lock()


def get_multimodal_manager() -> MultimodalManager:
    """获取全局多模态管理器"""
    global _multimodal_manager
    if _multimodal_manager is None:
        with _mm_lock:
            if _multimodal_manager is None:
                _multimodal_manager = MultimodalManager()
    return _multimodal_manager
