"""
输出能力

提供智能体的结构化输出能力:
- 多种输出格式支持
- 流式输出
- 结构化数据生成
"""

from abc import abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, AsyncGenerator, Dict, List, Optional, Protocol, runtime_checkable, Union
from enum import Enum
import asyncio
import json
import logging

from .base import CapabilityMixin, register_capability
from ..events import Event, EventType, get_event_bus

logger = logging.getLogger(__name__)


class OutputType(str, Enum):
    """输出类型"""
    TEXT = "text"
    MARKDOWN = "markdown"
    JSON = "json"
    STREAM = "stream"
    STRUCTURED = "structured"


class StructuredOutputType(str, Enum):
    """结构化输出类型"""
    SUBSIDY_CALC = "subsidy_calc"
    MERCHANT_CARD = "merchant_card"
    MERCHANT_LIST = "merchant_list"
    PROCESS_STEPS = "process_steps"
    TABLE = "table"
    CHECKLIST = "checklist"
    COMPARISON = "comparison"
    QUICK_REPLIES = "quick_replies"
    ACTION_BUTTONS = "action_buttons"
    CHART = "chart"
    TIMELINE = "timeline"
    ALERT = "alert"
    CARD = "card"
    LIST = "list"
    FAQ = "faq"


@dataclass
class StreamChunk:
    """流式输出块"""
    type: str  # stream_start | thinking | sources | answer | structured | stream_end
    data: Dict[str, Any]
    timestamp: datetime = field(default_factory=datetime.now)

    def to_ndjson(self) -> str:
        """转换为 NDJSON 格式"""
        return json.dumps({
            "type": self.type,
            "data": self.data,
            "timestamp": self.timestamp.isoformat()
        }, ensure_ascii=False)


@dataclass
class StructuredOutput:
    """结构化输出"""
    type: StructuredOutputType
    data: Dict[str, Any]
    title: Optional[str] = None
    description: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "type": self.type.value,
            "title": self.title,
            "description": self.description,
            "data": self.data,
            "metadata": self.metadata
        }


@runtime_checkable
class OutputCapability(Protocol):
    """输出能力协议"""

    async def format_text(self, content: str) -> str:
        """格式化文本"""
        ...

    async def format_structured(
        self,
        output_type: StructuredOutputType,
        data: Dict[str, Any],
        **kwargs
    ) -> StructuredOutput:
        """格式化结构化输出"""
        ...

    async def stream(
        self,
        content: str,
        thinking: Optional[List[str]] = None,
        sources: Optional[List[Dict]] = None,
        structured: Optional[List[StructuredOutput]] = None
    ) -> AsyncGenerator[StreamChunk, None]:
        """流式输出"""
        ...


@register_capability("output", version="2.0.0", description="输出格式化能力")
class OutputMixin(CapabilityMixin):
    """
    输出能力混入

    提供多种输出格式支持:
    - 文本格式化
    - 结构化输出
    - 流式输出
    """

    _capability_name = "output"
    _capability_version = "2.0.0"

    def __init__(self):
        super().__init__()
        self._event_bus = get_event_bus()

    async def _do_initialize(self) -> None:
        """初始化输出系统"""
        logger.info("Output system initialized")

    async def format_text(self, content: str) -> str:
        """格式化文本"""
        # 基本的文本清理
        content = content.strip()
        return content

    async def format_structured(
        self,
        output_type: StructuredOutputType,
        data: Dict[str, Any],
        title: Optional[str] = None,
        description: Optional[str] = None,
        **metadata
    ) -> StructuredOutput:
        """格式化结构化输出"""
        # 根据类型进行特定处理
        if output_type == StructuredOutputType.SUBSIDY_CALC:
            data = self._format_subsidy_calc(data)
        elif output_type == StructuredOutputType.MERCHANT_CARD:
            data = self._format_merchant_card(data)
        elif output_type == StructuredOutputType.PROCESS_STEPS:
            data = self._format_process_steps(data)
        elif output_type == StructuredOutputType.TABLE:
            data = self._format_table(data)
        elif output_type == StructuredOutputType.CHECKLIST:
            data = self._format_checklist(data)

        output = StructuredOutput(
            type=output_type,
            data=data,
            title=title,
            description=description,
            metadata=metadata
        )

        await self._event_bus.emit(Event(
            type=EventType.STRUCTURED_OUTPUT,
            payload={"output_type": output_type.value},
            source="output"
        ))

        return output

    async def stream(
        self,
        content: str,
        thinking: Optional[List[str]] = None,
        sources: Optional[List[Dict]] = None,
        structured: Optional[List[StructuredOutput]] = None,
        chunk_size: int = 50
    ) -> AsyncGenerator[StreamChunk, None]:
        """流式输出"""
        # 开始
        yield StreamChunk(
            type="stream_start",
            data={"message": "开始生成回答"}
        )

        # 思考过程
        if thinking:
            yield StreamChunk(
                type="thinking",
                data={"logs": thinking}
            )

        # 来源
        if sources:
            yield StreamChunk(
                type="sources",
                data=sources
            )

        # 主要内容（分块输出）
        for i in range(0, len(content), chunk_size):
            chunk = content[i:i + chunk_size]
            yield StreamChunk(
                type="answer",
                data={"content": chunk, "done": i + chunk_size >= len(content)}
            )
            await asyncio.sleep(0.01)  # 模拟流式延迟

        # 结构化输出
        if structured:
            for output in structured:
                yield StreamChunk(
                    type=output.type.value,
                    data=output.to_dict()
                )

        # 结束
        yield StreamChunk(
            type="stream_end",
            data={"message": "回答完成"}
        )

    def _format_subsidy_calc(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """格式化补贴计算结果"""
        return {
            "original_amount": data.get("original_amount", 0),
            "subsidy_amount": data.get("subsidy_amount", 0),
            "final_amount": data.get("final_amount", 0),
            "subsidy_rate": data.get("subsidy_rate", "0%"),
            "category": data.get("category", ""),
            "breakdown": data.get("breakdown", [])
        }

    def _format_merchant_card(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """格式化商家卡片"""
        return {
            "id": data.get("id"),
            "name": data.get("name", ""),
            "category": data.get("category", ""),
            "rating": data.get("rating", 0),
            "review_count": data.get("review_count", 0),
            "price_range": data.get("price_range", ""),
            "tags": data.get("tags", []),
            "highlights": data.get("highlights", []),
            "contact": data.get("contact", {})
        }

    def _format_process_steps(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """格式化流程步骤"""
        steps = data.get("steps", [])
        formatted_steps = []

        for i, step in enumerate(steps):
            formatted_steps.append({
                "index": i + 1,
                "title": step.get("title", ""),
                "description": step.get("description", ""),
                "duration": step.get("duration", ""),
                "tips": step.get("tips", []),
                "status": step.get("status", "pending")
            })

        return {
            "title": data.get("title", "流程步骤"),
            "total_steps": len(formatted_steps),
            "steps": formatted_steps
        }

    def _format_table(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """格式化表格"""
        return {
            "headers": data.get("headers", []),
            "rows": data.get("rows", []),
            "footer": data.get("footer"),
            "sortable": data.get("sortable", False)
        }

    def _format_checklist(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """格式化检查清单"""
        items = data.get("items", [])
        formatted_items = []

        for item in items:
            formatted_items.append({
                "text": item.get("text", ""),
                "checked": item.get("checked", False),
                "required": item.get("required", False),
                "note": item.get("note")
            })

        return {
            "title": data.get("title", "检查清单"),
            "items": formatted_items,
            "progress": sum(1 for i in formatted_items if i["checked"]) / len(formatted_items) if formatted_items else 0
        }

    # ==================== 便捷方法 ====================

    async def subsidy_card(
        self,
        original_amount: float,
        subsidy_amount: float,
        category: str,
        **kwargs
    ) -> StructuredOutput:
        """生成补贴计算卡片"""
        return await self.format_structured(
            StructuredOutputType.SUBSIDY_CALC,
            {
                "original_amount": original_amount,
                "subsidy_amount": subsidy_amount,
                "final_amount": original_amount - subsidy_amount,
                "category": category,
                **kwargs
            },
            title="补贴计算结果"
        )

    async def merchant_card(
        self,
        name: str,
        category: str,
        rating: float,
        **kwargs
    ) -> StructuredOutput:
        """生成商家卡片"""
        return await self.format_structured(
            StructuredOutputType.MERCHANT_CARD,
            {
                "name": name,
                "category": category,
                "rating": rating,
                **kwargs
            },
            title=name
        )

    async def process_steps(
        self,
        steps: List[Dict[str, Any]],
        title: str = "流程步骤"
    ) -> StructuredOutput:
        """生成流程步骤"""
        return await self.format_structured(
            StructuredOutputType.PROCESS_STEPS,
            {"steps": steps, "title": title},
            title=title
        )

    async def quick_replies(
        self,
        options: List[str],
        title: str = "您可能还想问"
    ) -> StructuredOutput:
        """生成快捷回复"""
        return await self.format_structured(
            StructuredOutputType.QUICK_REPLIES,
            {"options": options},
            title=title
        )

    async def alert(
        self,
        message: str,
        level: str = "info",  # info | warning | error | success
        **kwargs
    ) -> StructuredOutput:
        """生成提醒"""
        return await self.format_structured(
            StructuredOutputType.ALERT,
            {"message": message, "level": level, **kwargs},
            title="提醒"
        )
