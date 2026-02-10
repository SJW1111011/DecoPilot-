"""
多模态处理模块
支持图片理解、文档解析、OCR等能力
增强版：支持异步调用、多模型切换、智能缓存
"""
import os
import io
import base64
import hashlib
import asyncio
from typing import Any, Dict, List, Optional, Tuple, Union
from dataclasses import dataclass, field
from enum import Enum
from abc import ABC, abstractmethod
import threading
from concurrent.futures import ThreadPoolExecutor

from backend.core.cache import LRUCache
from backend.core.logging_config import get_logger

logger = get_logger("multimodal")

# 尝试导入视觉模型依赖
VISION_MODEL_AVAILABLE = False
DASHSCOPE_AVAILABLE = False

try:
    from langchain_community.chat_models import ChatTongyi
    from langchain_core.messages import HumanMessage
    VISION_MODEL_AVAILABLE = True
except ImportError:
    logger.warning("LangChain 未安装，视觉模型功能受限")

try:
    import dashscope
    from dashscope import MultiModalConversation
    DASHSCOPE_AVAILABLE = True
except ImportError:
    logger.warning("DashScope SDK 未安装，无法使用通义千问 VL 原生 API")

# 线程池用于异步执行
_executor = ThreadPoolExecutor(max_workers=4)


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

    def __init__(self, vision_model=None, cache_size: int = 500):
        """
        初始化图片处理器

        Args:
            vision_model: 视觉模型（如GPT-4V、通义千问VL等）
            cache_size: 缓存大小
        """
        self.vision_model = vision_model
        self._cache: LRUCache[str, ImageAnalysisResult] = LRUCache(
            max_size=cache_size,
            ttl=3600  # 1小时过期
        )

    def analyze(self, image: MediaContent,
                analysis_type: ImageAnalysisType = ImageAnalysisType.GENERAL,
                custom_prompt: str = None) -> ImageAnalysisResult:
        """
        分析图片

        Args:
            image: 图片内容
            analysis_type: 分析类型
            custom_prompt: 自定义提示词（用户的问题）

        Returns:
            ImageAnalysisResult 分析结果
        """
        # 如果有自定义提示词，直接调用视觉模型
        if custom_prompt:
            cache_key = f"{image.content_hash}_{hash(custom_prompt)}"
            cached = self._cache.get(cache_key)
            if cached is not None:
                logger.debug(f"图片分析缓存命中: {cache_key[:20]}...")
                return cached

            result = self._analyze_with_prompt(image, custom_prompt)
            self._cache.set(cache_key, result)
            return result

        # 检查缓存
        cache_key = f"{image.content_hash}_{analysis_type.value}"
        cached = self._cache.get(cache_key)
        if cached is not None:
            logger.debug(f"图片分析缓存命中: {cache_key[:20]}...")
            return cached

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
        self._cache.set(cache_key, result)
        return result

    async def analyze_async(self, image: MediaContent,
                            analysis_type: ImageAnalysisType = ImageAnalysisType.GENERAL,
                            custom_prompt: str = None) -> ImageAnalysisResult:
        """
        异步分析图片

        Args:
            image: 图片内容
            analysis_type: 分析类型
            custom_prompt: 自定义提示词

        Returns:
            ImageAnalysisResult 分析结果
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            _executor,
            lambda: self.analyze(image, analysis_type, custom_prompt)
        )

    def analyze_batch(self, images: List[MediaContent],
                      analysis_type: ImageAnalysisType = ImageAnalysisType.GENERAL) -> List[ImageAnalysisResult]:
        """
        批量分析图片

        Args:
            images: 图片列表
            analysis_type: 分析类型

        Returns:
            分析结果列表
        """
        results = []
        for image in images:
            try:
                result = self.analyze(image, analysis_type)
                results.append(result)
            except Exception as e:
                logger.error(f"批量分析图片失败: {e}")
                results.append(ImageAnalysisResult(
                    description=f"分析失败: {str(e)}",
                    analysis_type=analysis_type,
                    confidence=0.0,
                ))
        return results

    async def analyze_batch_async(self, images: List[MediaContent],
                                   analysis_type: ImageAnalysisType = ImageAnalysisType.GENERAL) -> List[ImageAnalysisResult]:
        """
        异步批量分析图片

        Args:
            images: 图片列表
            analysis_type: 分析类型

        Returns:
            分析结果列表
        """
        tasks = [
            self.analyze_async(image, analysis_type)
            for image in images
        ]
        return await asyncio.gather(*tasks, return_exceptions=True)

    def _analyze_with_prompt(self, image: MediaContent, prompt: str) -> ImageAnalysisResult:
        """使用自定义提示词分析图片"""
        if self.vision_model or VISION_MODEL_AVAILABLE or DASHSCOPE_AVAILABLE:
            # 构建包含用户问题的提示词
            full_prompt = f"""请根据这张图片回答用户的问题。

用户问题：{prompt}

请仔细观察图片内容，结合用户的问题给出详细、准确的回答。如果图片与问题相关，请基于图片内容回答；如果图片与问题不太相关，也请尽量提供有帮助的信息。"""
            return self._call_vision_model(image, full_prompt, ImageAnalysisType.GENERAL)

        return ImageAnalysisResult(
            description="需要视觉模型支持才能分析图片",
            analysis_type=ImageAnalysisType.GENERAL,
            confidence=0.0,
        )

    def _analyze_general(self, image: MediaContent) -> ImageAnalysisResult:
        """通用图片分析"""
        # 如果有视觉模型或 DashScope 可用，使用模型分析
        if self.vision_model or VISION_MODEL_AVAILABLE or DASHSCOPE_AVAILABLE:
            return self._call_vision_model(image, "请描述这张图片的内容，包括场景、物品、颜色、风格等信息。")

        # 否则返回基础结果
        return ImageAnalysisResult(
            description="图片已上传，请描述您想了解的内容",
            analysis_type=ImageAnalysisType.GENERAL,
            confidence=0.5,
        )

    def _analyze_decoration_style(self, image: MediaContent) -> ImageAnalysisResult:
        """装修风格分析"""
        if self.vision_model or VISION_MODEL_AVAILABLE or DASHSCOPE_AVAILABLE:
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
        if self.vision_model or VISION_MODEL_AVAILABLE or DASHSCOPE_AVAILABLE:
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
        if self.vision_model or VISION_MODEL_AVAILABLE or DASHSCOPE_AVAILABLE:
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
        if self.vision_model or VISION_MODEL_AVAILABLE or DASHSCOPE_AVAILABLE:
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
            elif os.path.exists(image.content):
                with open(image.content, "rb") as f:
                    image_data = base64.b64encode(f.read()).decode()
            else:
                return ImageAnalysisResult(
                    description=f"图片文件不存在: {image.content}",
                    analysis_type=analysis_type,
                    confidence=0.0,
                )

            # 确定 MIME 类型
            mime_type = image.mime_type or self._detect_mime_type(image)

            # 如果有视觉模型实例，调用它
            if self.vision_model and hasattr(self.vision_model, 'invoke'):
                return self._call_langchain_vision_model(
                    image_data, mime_type, prompt, analysis_type
                )

            # 尝试使用通义千问 VL 模型
            if VISION_MODEL_AVAILABLE:
                return self._call_qwen_vl(image_data, mime_type, prompt, analysis_type)

            # 无可用模型，返回基础结果
            return ImageAnalysisResult(
                description="视觉模型未配置，无法分析图片内容",
                analysis_type=analysis_type,
                confidence=0.0,
            )

        except Exception as e:
            logger.error(f"视觉模型调用失败: {e}", exc_info=True)
            return ImageAnalysisResult(
                description=f"分析失败: {str(e)}",
                analysis_type=analysis_type,
                confidence=0.0,
            )

    def _detect_mime_type(self, image: MediaContent) -> str:
        """检测图片 MIME 类型"""
        if image.filename:
            ext = os.path.splitext(image.filename)[1].lower()
            mime_map = {
                '.jpg': 'image/jpeg',
                '.jpeg': 'image/jpeg',
                '.png': 'image/png',
                '.gif': 'image/gif',
                '.webp': 'image/webp',
                '.bmp': 'image/bmp',
            }
            return mime_map.get(ext, 'image/jpeg')
        return 'image/jpeg'

    def _call_langchain_vision_model(self, image_data: str, mime_type: str,
                                      prompt: str, analysis_type: ImageAnalysisType) -> ImageAnalysisResult:
        """调用 LangChain 视觉模型"""
        try:
            message = HumanMessage(
                content=[
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:{mime_type};base64,{image_data}"
                        }
                    }
                ]
            )

            response = self.vision_model.invoke([message])
            description = response.content if hasattr(response, 'content') else str(response)

            # 解析响应，提取结构化信息
            result = self._parse_vision_response(description, analysis_type)
            return result

        except Exception as e:
            logger.error(f"LangChain 视觉模型调用失败: {e}")
            return ImageAnalysisResult(
                description=f"模型调用失败: {str(e)}",
                analysis_type=analysis_type,
                confidence=0.0,
            )

    def _call_qwen_vl(self, image_data: str, mime_type: str,
                      prompt: str, analysis_type: ImageAnalysisType) -> ImageAnalysisResult:
        """调用通义千问 VL 模型"""
        # 优先使用 DashScope 原生 API（更稳定）
        if DASHSCOPE_AVAILABLE:
            return self._call_dashscope_vl(image_data, mime_type, prompt, analysis_type)

        # 回退到 LangChain 方式
        if VISION_MODEL_AVAILABLE:
            return self._call_langchain_qwen_vl(image_data, mime_type, prompt, analysis_type)

        return ImageAnalysisResult(
            description="视觉模型未配置，请安装 dashscope 或 langchain",
            analysis_type=analysis_type,
            confidence=0.0,
        )

    def _call_dashscope_vl(self, image_data: str, mime_type: str,
                           prompt: str, analysis_type: ImageAnalysisType) -> ImageAnalysisResult:
        """使用 DashScope 原生 API 调用通义千问 VL"""
        try:
            # 构建消息
            messages = [
                {
                    "role": "user",
                    "content": [
                        {"image": f"data:{mime_type};base64,{image_data}"},
                        {"text": prompt}
                    ]
                }
            ]

            # 调用多模态对话 API
            response = MultiModalConversation.call(
                model="qwen-vl-plus",
                messages=messages,
            )

            if response.status_code == 200:
                # 提取响应内容
                content = response.output.choices[0].message.content
                if isinstance(content, list):
                    # 提取文本部分
                    description = ""
                    for item in content:
                        if isinstance(item, dict) and "text" in item:
                            description += item["text"]
                        elif isinstance(item, str):
                            description += item
                else:
                    description = str(content)

                # 解析响应
                result = self._parse_vision_response(description, analysis_type)
                logger.info(f"DashScope VL 调用成功，分析类型: {analysis_type.value}")
                return result
            else:
                error_msg = f"API 调用失败: {response.code} - {response.message}"
                logger.error(error_msg)
                return ImageAnalysisResult(
                    description=error_msg,
                    analysis_type=analysis_type,
                    confidence=0.0,
                )

        except Exception as e:
            logger.error(f"DashScope VL 调用异常: {e}", exc_info=True)
            return ImageAnalysisResult(
                description=f"模型调用失败: {str(e)}",
                analysis_type=analysis_type,
                confidence=0.0,
            )

    def _call_langchain_qwen_vl(self, image_data: str, mime_type: str,
                                 prompt: str, analysis_type: ImageAnalysisType) -> ImageAnalysisResult:
        """使用 LangChain 调用通义千问 VL"""
        try:
            # 使用通义千问 VL 模型
            model = ChatTongyi(model="qwen-vl-plus", temperature=0.3)

            message = HumanMessage(
                content=[
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:{mime_type};base64,{image_data}"
                        }
                    }
                ]
            )

            response = model.invoke([message])
            description = response.content if hasattr(response, 'content') else str(response)

            # 解析响应
            result = self._parse_vision_response(description, analysis_type)
            logger.info(f"LangChain VL 调用成功，分析类型: {analysis_type.value}")
            return result

        except Exception as e:
            logger.error(f"LangChain VL 调用失败: {e}")
            return ImageAnalysisResult(
                description=f"模型调用失败: {str(e)}",
                analysis_type=analysis_type,
                confidence=0.0,
            )

    def _parse_vision_response(self, response: str,
                                analysis_type: ImageAnalysisType) -> ImageAnalysisResult:
        """解析视觉模型响应"""
        result = ImageAnalysisResult(
            description=response,
            analysis_type=analysis_type,
            confidence=0.8,
        )

        # 根据分析类型提取结构化信息
        if analysis_type == ImageAnalysisType.DECORATION_STYLE:
            # 提取风格标签
            for style in self.STYLE_KEYWORDS.keys():
                if style in response:
                    result.style_tags.append(style)

            # 提取颜色
            colors = ["白色", "灰色", "米色", "原木色", "深色", "浅色", "暖色", "冷色"]
            for color in colors:
                if color in response:
                    result.colors.append(color)

        elif analysis_type == ImageAnalysisType.MATERIAL:
            # 提取材料
            for material in self.MATERIAL_KEYWORDS.keys():
                if material in response:
                    result.detected_objects.append({
                        "type": "material",
                        "name": material,
                    })

        elif analysis_type == ImageAnalysisType.FURNITURE:
            # 提取家具
            furniture_types = ["沙发", "床", "餐桌", "椅子", "衣柜", "书桌", "茶几", "电视柜"]
            for furniture in furniture_types:
                if furniture in response:
                    result.detected_objects.append({
                        "type": "furniture",
                        "name": furniture,
                    })

        return result


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


@dataclass
class QuoteItem:
    """报价单项目"""
    name: str
    specification: str = ""
    unit: str = ""
    quantity: float = 0
    unit_price: float = 0
    total_price: float = 0
    notes: str = ""


@dataclass
class QuoteExtractResult:
    """报价单提取结果"""
    items: List[QuoteItem]
    total_amount: float = 0
    merchant_name: str = ""
    quote_date: str = ""
    validity: str = ""
    notes: List[str] = field(default_factory=list)
    raw_text: str = ""


@dataclass
class ContractTerm:
    """合同条款"""
    category: str  # 付款、工期、质量、违约等
    content: str
    importance: str = "normal"  # high/normal/low
    warnings: List[str] = field(default_factory=list)


@dataclass
class ContractExtractResult:
    """合同提取结果"""
    parties: Dict[str, str] = field(default_factory=dict)  # 甲方、乙方
    project_info: Dict[str, str] = field(default_factory=dict)  # 项目信息
    terms: List[ContractTerm] = field(default_factory=list)
    total_amount: float = 0
    payment_schedule: List[Dict] = field(default_factory=list)
    duration: str = ""
    warnings: List[str] = field(default_factory=list)
    raw_text: str = ""


class OCRProcessor:
    """
    OCR处理器

    用于从图片或PDF中提取文字，特别针对装修报价单和合同
    """

    def __init__(self, vision_model=None):
        """
        初始化OCR处理器

        Args:
            vision_model: 视觉模型（用于图片OCR）
        """
        self.vision_model = vision_model
        self.image_processor = ImageProcessor(vision_model)
        self.document_processor = DocumentProcessor()

    def extract_text_from_image(self, image: MediaContent) -> str:
        """
        从图片中提取文字

        Args:
            image: 图片内容

        Returns:
            提取的文字
        """
        # 使用视觉模型进行OCR
        prompt = """请仔细识别这张图片中的所有文字内容，包括：
1. 表格中的数据
2. 标题和说明文字
3. 数字和金额
4. 日期和签名

请按照原始格式尽可能准确地输出所有文字内容。"""

        result = self.image_processor.analyze(image, ImageAnalysisType.GENERAL, custom_prompt=prompt)
        return result.description

    def extract_quote_items(self, content: MediaContent) -> QuoteExtractResult:
        """
        从报价单中提取明细

        Args:
            content: 报价单内容（图片或PDF）

        Returns:
            报价单提取结果
        """
        # 获取文本内容
        if content.media_type == MediaType.IMAGE:
            text = self._extract_quote_from_image(content)
        else:
            doc_result = self.document_processor.parse(content)
            text = doc_result.text

        # 解析报价单
        return self._parse_quote_text(text)

    def _extract_quote_from_image(self, image: MediaContent) -> str:
        """从图片报价单中提取文字"""
        prompt = """这是一张装修报价单图片，请识别并提取以下信息：
1. 所有报价项目（项目名称、规格、单位、数量、单价、金额）
2. 报价总金额
3. 商家/公司名称
4. 报价日期
5. 其他备注信息

请按照表格格式输出，每行一个项目，用|分隔各列。"""

        result = self.image_processor.analyze(image, ImageAnalysisType.GENERAL, custom_prompt=prompt)
        return result.description

    def _parse_quote_text(self, text: str) -> QuoteExtractResult:
        """解析报价单文本"""
        import re

        result = QuoteExtractResult(items=[], raw_text=text)

        # 提取总金额
        amount_patterns = [
            r'合计[：:]\s*[￥¥]?\s*([\d,]+(?:\.\d+)?)',
            r'总[计价][：:]\s*[￥¥]?\s*([\d,]+(?:\.\d+)?)',
            r'总金额[：:]\s*[￥¥]?\s*([\d,]+(?:\.\d+)?)',
        ]
        for pattern in amount_patterns:
            match = re.search(pattern, text)
            if match:
                try:
                    result.total_amount = float(match.group(1).replace(',', ''))
                    break
                except:
                    pass

        # 提取日期
        date_patterns = [
            r'(\d{4}[-/年]\d{1,2}[-/月]\d{1,2}[日]?)',
            r'日期[：:]\s*(\d{4}[-/]\d{1,2}[-/]\d{1,2})',
        ]
        for pattern in date_patterns:
            match = re.search(pattern, text)
            if match:
                result.quote_date = match.group(1)
                break

        # 提取项目（简单的行解析）
        lines = text.split('\n')
        for line in lines:
            # 尝试解析表格行
            if '|' in line:
                parts = [p.strip() for p in line.split('|') if p.strip()]
                if len(parts) >= 3:
                    item = self._parse_quote_line(parts)
                    if item:
                        result.items.append(item)
            # 尝试解析空格分隔的行
            elif re.search(r'\d+(?:\.\d+)?\s*元', line):
                item = self._parse_quote_line_simple(line)
                if item:
                    result.items.append(item)

        return result

    def _parse_quote_line(self, parts: List[str]) -> Optional[QuoteItem]:
        """解析报价单行（表格格式）"""
        import re

        if len(parts) < 3:
            return None

        item = QuoteItem(name=parts[0])

        # 尝试识别各列
        for i, part in enumerate(parts[1:], 1):
            # 检查是否是金额
            if re.match(r'^[\d,]+(?:\.\d+)?$', part.replace('元', '').replace('￥', '').strip()):
                value = float(part.replace('元', '').replace('￥', '').replace(',', '').strip())
                if item.total_price == 0:
                    item.total_price = value
                elif item.unit_price == 0:
                    item.unit_price = value
            # 检查是否是数量
            elif re.match(r'^[\d.]+$', part):
                if item.quantity == 0:
                    item.quantity = float(part)
            # 检查是否是单位
            elif part in ['平米', '㎡', '米', 'm', '个', '套', '项', '延米']:
                item.unit = part
            else:
                if not item.specification:
                    item.specification = part

        return item if item.name else None

    def _parse_quote_line_simple(self, line: str) -> Optional[QuoteItem]:
        """解析简单格式的报价行"""
        import re

        # 提取项目名称（行首的中文）
        name_match = re.match(r'^([\u4e00-\u9fa5]+)', line)
        if not name_match:
            return None

        item = QuoteItem(name=name_match.group(1))

        # 提取金额
        amount_match = re.search(r'([\d,]+(?:\.\d+)?)\s*元', line)
        if amount_match:
            item.total_price = float(amount_match.group(1).replace(',', ''))

        return item

    def extract_contract_terms(self, content: MediaContent) -> ContractExtractResult:
        """
        从合同中提取关键条款

        Args:
            content: 合同内容（图片或PDF）

        Returns:
            合同提取结果
        """
        # 获取文本内容
        if content.media_type == MediaType.IMAGE:
            text = self._extract_contract_from_image(content)
        else:
            doc_result = self.document_processor.parse(content)
            text = doc_result.text

        # 解析合同
        return self._parse_contract_text(text)

    def _extract_contract_from_image(self, image: MediaContent) -> str:
        """从图片合同中提取文字"""
        prompt = """这是一份装修合同图片，请识别并提取以下关键信息：
1. 甲方（业主）和乙方（装修公司）信息
2. 工程地址和面积
3. 合同金额和付款方式
4. 工期约定
5. 质量标准
6. 违约责任
7. 保修条款

请详细列出每个条款的内容。"""

        result = self.image_processor.analyze(image, ImageAnalysisType.GENERAL, custom_prompt=prompt)
        return result.description

    def _parse_contract_text(self, text: str) -> ContractExtractResult:
        """解析合同文本"""
        import re

        result = ContractExtractResult(raw_text=text)

        # 提取甲乙方信息
        party_patterns = {
            "甲方": [r'甲方[（(]?业主[）)]?[：:]\s*(.+?)(?:\n|$)', r'甲方[：:]\s*(.+?)(?:\n|$)'],
            "乙方": [r'乙方[（(]?承包方[）)]?[：:]\s*(.+?)(?:\n|$)', r'乙方[：:]\s*(.+?)(?:\n|$)'],
        }
        for party, patterns in party_patterns.items():
            for pattern in patterns:
                match = re.search(pattern, text)
                if match:
                    result.parties[party] = match.group(1).strip()
                    break

        # 提取合同金额
        amount_patterns = [
            r'合同[总价金额]+[：:]\s*[￥¥]?\s*([\d,]+(?:\.\d+)?)',
            r'工程[总造价]+[：:]\s*[￥¥]?\s*([\d,]+(?:\.\d+)?)',
        ]
        for pattern in amount_patterns:
            match = re.search(pattern, text)
            if match:
                try:
                    result.total_amount = float(match.group(1).replace(',', ''))
                    break
                except:
                    pass

        # 提取工期
        duration_patterns = [
            r'工期[：:]\s*(\d+)\s*[天日]',
            r'施工期限[：:]\s*(\d+)\s*[天日]',
        ]
        for pattern in duration_patterns:
            match = re.search(pattern, text)
            if match:
                result.duration = f"{match.group(1)}天"
                break

        # 提取关键条款
        term_keywords = {
            "付款": {
                "patterns": [r'付款[方式条款][：:].+?(?=\n\n|\n[一二三四五六七八九十]|$)'],
                "importance": "high",
                "check_warnings": self._check_payment_warnings
            },
            "工期": {
                "patterns": [r'工期[约定条款][：:].+?(?=\n\n|\n[一二三四五六七八九十]|$)'],
                "importance": "high",
                "check_warnings": self._check_duration_warnings
            },
            "质量": {
                "patterns": [r'质量[标准要求][：:].+?(?=\n\n|\n[一二三四五六七八九十]|$)'],
                "importance": "high",
                "check_warnings": self._check_quality_warnings
            },
            "违约": {
                "patterns": [r'违约[责任条款][：:].+?(?=\n\n|\n[一二三四五六七八九十]|$)'],
                "importance": "high",
                "check_warnings": self._check_penalty_warnings
            },
            "保修": {
                "patterns": [r'保修[期条款][：:].+?(?=\n\n|\n[一二三四五六七八九十]|$)'],
                "importance": "normal",
                "check_warnings": self._check_warranty_warnings
            },
        }

        for category, config in term_keywords.items():
            for pattern in config["patterns"]:
                match = re.search(pattern, text, re.DOTALL)
                if match:
                    content = match.group(0).strip()
                    warnings = config["check_warnings"](content) if config.get("check_warnings") else []

                    result.terms.append(ContractTerm(
                        category=category,
                        content=content[:500],  # 限制长度
                        importance=config["importance"],
                        warnings=warnings
                    ))

                    if warnings:
                        result.warnings.extend(warnings)
                    break

        return result

    def _check_payment_warnings(self, content: str) -> List[str]:
        """检查付款条款风险"""
        warnings = []
        if "一次性" in content or "全款" in content:
            warnings.append("注意：要求一次性付全款风险较高，建议分期付款")
        if "50%" in content or "五成" in content:
            if "开工" in content:
                warnings.append("注意：开工前付款比例较高，建议控制在30%以内")
        return warnings

    def _check_duration_warnings(self, content: str) -> List[str]:
        """检查工期条款风险"""
        warnings = []
        if "不可抗力" in content and "延期" in content:
            warnings.append("注意：不可抗力条款可能被滥用，建议明确具体情形")
        return warnings

    def _check_quality_warnings(self, content: str) -> List[str]:
        """检查质量条款风险"""
        warnings = []
        if "验收" not in content:
            warnings.append("注意：未明确验收标准，建议补充验收条款")
        return warnings

    def _check_penalty_warnings(self, content: str) -> List[str]:
        """检查违约条款风险"""
        warnings = []
        if "甲方" in content and "违约金" in content:
            if "乙方" not in content or "违约金" not in content.split("甲方")[0]:
                warnings.append("注意：违约责任可能不对等，建议双方违约责任对等")
        return warnings

    def _check_warranty_warnings(self, content: str) -> List[str]:
        """检查保修条款风险"""
        import re
        warnings = []
        # 检查保修期限
        match = re.search(r'(\d+)\s*年', content)
        if match:
            years = int(match.group(1))
            if years < 2:
                warnings.append(f"注意：保修期{years}年较短，建议争取至少2年保修")
        return warnings


class MultimodalManager:
    """多模态管理器"""

    def __init__(self, vision_model=None):
        self.image_processor = ImageProcessor(vision_model)
        self.document_processor = DocumentProcessor()
        self.ocr_processor = OCRProcessor(vision_model)
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

    async def process_async(self, content: MediaContent) -> Dict:
        """异步处理多模态内容"""
        # 在线程池中执行同步处理
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.process, content)

    def analyze_decoration_image(self, image_path: str) -> ImageAnalysisResult:
        """分析装修图片"""
        content = MediaContent(
            media_type=MediaType.IMAGE,
            content=image_path,
            filename=os.path.basename(image_path),
        )
        return self.image_processor.analyze(content, ImageAnalysisType.DECORATION_STYLE)

    async def analyze_decoration_image_async(self, image_path: str) -> ImageAnalysisResult:
        """异步分析装修图片"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, self.analyze_decoration_image, image_path
        )

    def analyze_image_with_type(self, image_path: str,
                                 analysis_type: ImageAnalysisType) -> ImageAnalysisResult:
        """使用指定类型分析图片"""
        content = MediaContent(
            media_type=MediaType.IMAGE,
            content=image_path,
            filename=os.path.basename(image_path),
        )
        return self.image_processor.analyze(content, analysis_type)

    def analyze_image_bytes(self, image_bytes: bytes, filename: str = "image.jpg",
                            analysis_type: ImageAnalysisType = ImageAnalysisType.GENERAL) -> ImageAnalysisResult:
        """分析图片字节数据"""
        content = MediaContent(
            media_type=MediaType.IMAGE,
            content=image_bytes,
            filename=filename,
        )
        return self.image_processor.analyze(content, analysis_type)

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

    def extract_quote_items(self, file_path: str) -> Dict:
        """
        从报价单中提取明细项目

        Args:
            file_path: 报价单文件路径（支持图片或PDF）

        Returns:
            提取结果字典
        """
        # 判断文件类型
        ext = os.path.splitext(file_path)[1].lower()
        if ext in ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp']:
            media_type = MediaType.IMAGE
        elif ext == '.pdf':
            media_type = MediaType.PDF
        else:
            return {"error": f"不支持的文件类型: {ext}"}

        content = MediaContent(
            media_type=media_type,
            content=file_path,
            filename=os.path.basename(file_path),
        )

        result = self.ocr_processor.extract_quote_items(content)

        return {
            "items": [
                {
                    "name": item.name,
                    "specification": item.specification,
                    "unit": item.unit,
                    "quantity": item.quantity,
                    "unit_price": item.unit_price,
                    "total_price": item.total_price,
                    "notes": item.notes,
                }
                for item in result.items
            ],
            "total_amount": result.total_amount,
            "merchant_name": result.merchant_name,
            "quote_date": result.quote_date,
            "notes": result.notes,
        }

    def extract_contract_terms(self, file_path: str) -> Dict:
        """
        从合同中提取关键条款

        Args:
            file_path: 合同文件路径（支持图片或PDF）

        Returns:
            提取结果字典
        """
        # 判断文件类型
        ext = os.path.splitext(file_path)[1].lower()
        if ext in ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp']:
            media_type = MediaType.IMAGE
        elif ext == '.pdf':
            media_type = MediaType.PDF
        else:
            return {"error": f"不支持的文件类型: {ext}"}

        content = MediaContent(
            media_type=media_type,
            content=file_path,
            filename=os.path.basename(file_path),
        )

        result = self.ocr_processor.extract_contract_terms(content)

        return {
            "parties": result.parties,
            "project_info": result.project_info,
            "terms": [
                {
                    "category": term.category,
                    "content": term.content,
                    "importance": term.importance,
                    "warnings": term.warnings,
                }
                for term in result.terms
            ],
            "total_amount": result.total_amount,
            "payment_schedule": result.payment_schedule,
            "duration": result.duration,
            "warnings": result.warnings,
        }

    def get_stats(self) -> Dict:
        """获取多模态处理统计"""
        return {
            "image_cache_stats": self.image_processor._cache.stats(),
            "vision_model_available": VISION_MODEL_AVAILABLE or DASHSCOPE_AVAILABLE,
            "dashscope_available": DASHSCOPE_AVAILABLE,
            "langchain_available": VISION_MODEL_AVAILABLE,
            "supported_types": [t.value for t in MediaType],
            "supported_analysis_types": [t.value for t in ImageAnalysisType],
        }


# 全局多模态管理器
_multimodal_manager: Optional[MultimodalManager] = None
_mm_lock = threading.Lock()


def get_multimodal_manager(vision_model=None) -> MultimodalManager:
    """
    获取全局多模态管理器

    Args:
        vision_model: 可选的视觉模型实例，如果不提供则使用默认配置

    Returns:
        MultimodalManager 实例
    """
    global _multimodal_manager
    if _multimodal_manager is None:
        with _mm_lock:
            if _multimodal_manager is None:
                _multimodal_manager = MultimodalManager(vision_model)
                logger.info(
                    f"多模态管理器初始化完成 - "
                    f"DashScope: {DASHSCOPE_AVAILABLE}, "
                    f"LangChain: {VISION_MODEL_AVAILABLE}"
                )
    return _multimodal_manager


def analyze_image(image_path: str,
                  analysis_type: ImageAnalysisType = ImageAnalysisType.GENERAL) -> ImageAnalysisResult:
    """
    便捷函数：分析图片

    Args:
        image_path: 图片路径
        analysis_type: 分析类型

    Returns:
        ImageAnalysisResult 分析结果
    """
    manager = get_multimodal_manager()
    return manager.analyze_image_with_type(image_path, analysis_type)


async def analyze_image_async(image_path: str,
                               analysis_type: ImageAnalysisType = ImageAnalysisType.GENERAL) -> ImageAnalysisResult:
    """
    便捷函数：异步分析图片

    Args:
        image_path: 图片路径
        analysis_type: 分析类型

    Returns:
        ImageAnalysisResult 分析结果
    """
    manager = get_multimodal_manager()
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        None, manager.analyze_image_with_type, image_path, analysis_type
    )
