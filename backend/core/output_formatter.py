"""
输出格式化器
统一管理智能体的输出格式，支持多种结构化输出类型
"""
import json
import time
from enum import Enum
from typing import Any, Dict, List, Optional, Union
from dataclasses import dataclass, asdict
from datetime import datetime


class OutputType(str, Enum):
    """输出类型枚举"""
    # 基础类型
    TEXT = "text"              # 普通文本
    THINKING = "thinking"      # 思考过程
    ANSWER = "answer"          # 回答内容（流式文本）
    ERROR = "error"            # 错误信息

    # 结构化数据类型
    SOURCES = "sources"        # 引用来源
    SUBSIDY_CALC = "subsidy_calc"      # 补贴计算结果
    MERCHANT_CARD = "merchant_card"    # 商家推荐卡片
    MERCHANT_LIST = "merchant_list"    # 商家列表
    PROCESS_STEPS = "process_steps"    # 流程步骤
    TABLE = "table"            # 表格数据
    CHECKLIST = "checklist"    # 检查清单
    COMPARISON = "comparison"  # 对比数据

    # 交互类型
    QUICK_REPLIES = "quick_replies"    # 快捷回复选项
    ACTION_BUTTONS = "action_buttons"  # 操作按钮

    # 元数据类型
    META = "meta"              # 响应元数据
    STREAM_START = "stream_start"      # 流开始
    STREAM_END = "stream_end"          # 流结束

    # 诊断类型
    EXPERT_DEBUG = "expert_debug"      # 专家系统诊断信息


@dataclass
class Source:
    """引用来源"""
    title: str
    content: str
    collection: str
    relevance_score: float
    url: Optional[str] = None


@dataclass
class SubsidyResult:
    """补贴计算结果"""
    category: str           # 品类
    original_amount: float  # 原始金额
    subsidy_rate: float     # 补贴比例
    calculated_amount: float  # 计算金额
    max_limit: float        # 上限
    final_amount: float     # 最终补贴金额
    explanation: str        # 说明


@dataclass
class MerchantCard:
    """商家卡片"""
    id: str
    name: str
    category: str
    rating: float
    review_count: int
    address: str
    highlights: List[str]
    price_range: str
    subsidy_rate: Optional[float] = None
    image_url: Optional[str] = None
    contact: Optional[str] = None


@dataclass
class ProcessStep:
    """流程步骤"""
    step_number: int
    title: str
    description: str
    duration: Optional[str] = None
    tips: Optional[List[str]] = None
    warnings: Optional[List[str]] = None
    status: str = "pending"  # pending, current, completed


@dataclass
class TableData:
    """表格数据"""
    title: str
    headers: List[str]
    rows: List[List[str]]
    footer: Optional[str] = None


@dataclass
class ChecklistItem:
    """检查清单项"""
    item: str
    checked: bool = False
    category: Optional[str] = None
    priority: str = "normal"  # low, normal, high


@dataclass
class QuickReply:
    """快捷回复"""
    text: str
    payload: Optional[str] = None


@dataclass
class ActionButton:
    """操作按钮"""
    text: str
    action: str  # url, callback, copy
    value: str
    style: str = "default"  # default, primary, danger


@dataclass
class StreamMeta:
    """流元数据"""
    session_id: str
    user_type: str
    request_id: str
    start_time: float
    collections_used: List[str]
    model: str = "qwen"
    end_time: Optional[float] = None
    total_tokens: Optional[int] = None


class OutputFormatter:
    """输出格式化器"""

    def __init__(self, session_id: str, user_type: str = "both"):
        self.session_id = session_id
        self.user_type = user_type
        self.request_id = f"{session_id}_{int(time.time() * 1000)}"
        self.start_time = time.time()
        self.collections_used: List[str] = []

    def format(self, output_type: OutputType, data: Any) -> str:
        """格式化输出为JSON字符串"""
        output = {
            "type": output_type.value,
            "data": self._serialize(data),
            "timestamp": datetime.now().isoformat(),
        }
        return json.dumps(output, ensure_ascii=False) + "\n"

    def _serialize(self, data: Any) -> Any:
        """序列化数据"""
        if hasattr(data, "__dataclass_fields__"):
            return asdict(data)
        elif isinstance(data, list):
            return [self._serialize(item) for item in data]
        elif isinstance(data, dict):
            return {k: self._serialize(v) for k, v in data.items()}
        return data

    # === 基础输出方法 ===

    def text(self, content: str) -> str:
        """普通文本输出"""
        return self.format(OutputType.TEXT, {"content": content})

    def thinking(self, logs: List[str], reasoning_type: str = None) -> str:
        """思考过程输出（兼容前端格式）"""
        # 前端期望: {"type": "thinking", "content": [...]}
        output = {
            "type": "thinking",
            "content": logs,
        }
        if reasoning_type:
            output["reasoning_type"] = reasoning_type
        return json.dumps(output, ensure_ascii=False) + "\n"

    def answer(self, content: str) -> str:
        """回答内容输出（流式，兼容前端格式）"""
        # 前端期望: {"type": "answer", "content": "..."}
        output = {
            "type": "answer",
            "content": content,
        }
        return json.dumps(output, ensure_ascii=False) + "\n"

    def error(self, message: str, code: str = "UNKNOWN") -> str:
        """错误输出"""
        return self.format(OutputType.ERROR, {
            "message": message,
            "code": code,
        })

    def expert_debug(self, context: dict) -> str:
        """专家系统诊断信息输出"""
        data = {}

        # 阶段上下文
        stage_ctx = context.get("stage_context")
        if stage_ctx:
            data["detected_stage"] = stage_ctx.stage
            data["stage_confidence"] = stage_ctx.stage_confidence
            data["emotional_state"] = stage_ctx.emotional_state
            data["focus_points"] = stage_ctx.focus_points
            data["deep_need"] = stage_ctx.deep_need
            data["potential_needs"] = stage_ctx.potential_needs

        # 专家角色
        expert_role = context.get("expert_role")
        if expert_role:
            data["expert_role"] = expert_role.name
            data["expert_value"] = expert_role.core_value
        else:
            data["expert_role"] = None
            data["expert_value"] = None

        # 阶段转换
        transition = context.get("stage_transition")
        if transition:
            data["stage_transition"] = {
                "from_stage": transition.from_stage,
                "to_stage": transition.to_stage,
                "confidence": transition.confidence,
                "trigger": transition.trigger,
            }
        else:
            data["stage_transition"] = None

        # 前端期望: {"type": "expert_debug", "data": {...}}
        output = {
            "type": "expert_debug",
            "data": data,
        }
        return json.dumps(output, ensure_ascii=False) + "\n"

    # === 结构化数据输出方法 ===

    def sources(self, sources: List[Source]) -> str:
        """引用来源输出"""
        self.collections_used = list(set(
            self.collections_used + [s.collection for s in sources]
        ))
        return self.format(OutputType.SOURCES, sources)

    def subsidy_calc(self, result: SubsidyResult) -> str:
        """补贴计算结果输出"""
        return self.format(OutputType.SUBSIDY_CALC, result)

    def subsidy_calc_batch(self, results: List[SubsidyResult],
                           total: float, monthly_limit: float = 5000) -> str:
        """批量补贴计算结果输出"""
        return self.format(OutputType.SUBSIDY_CALC, {
            "items": [asdict(r) for r in results],
            "total_subsidy": min(total, monthly_limit),
            "monthly_limit": monthly_limit,
            "exceeded_limit": total > monthly_limit,
        })

    def merchant_card(self, merchant: MerchantCard) -> str:
        """商家卡片输出"""
        return self.format(OutputType.MERCHANT_CARD, merchant)

    def merchant_list(self, merchants: List[MerchantCard],
                      title: str = "推荐商家") -> str:
        """商家列表输出"""
        return self.format(OutputType.MERCHANT_LIST, {
            "title": title,
            "count": len(merchants),
            "merchants": [asdict(m) for m in merchants],
        })

    def process_steps(self, steps: List[ProcessStep],
                      title: str = "流程步骤") -> str:
        """流程步骤输出"""
        return self.format(OutputType.PROCESS_STEPS, {
            "title": title,
            "total_steps": len(steps),
            "steps": [asdict(s) for s in steps],
        })

    def table(self, table_data: TableData) -> str:
        """表格数据输出"""
        return self.format(OutputType.TABLE, table_data)

    def table_markdown(self, table_data: TableData) -> str:
        """
        将表格数据转换为格式正确的 Markdown 表格字符串
        用于在回答中嵌入表格
        """
        if not table_data.headers or not table_data.rows:
            return ""

        def escape_cell(cell):
            """转义单元格中的特殊字符"""
            s = str(cell)
            s = s.replace("|", "\\|")   # 转义管道符
            s = s.replace("\n", " ")     # 换行符替换为空格
            return s.strip()

        lines = []

        # 标题
        if table_data.title:
            lines.append(f"\n**{table_data.title}**\n")

        # 表头
        headers = [escape_cell(h) for h in table_data.headers]
        header_line = "| " + " | ".join(headers) + " |"
        lines.append(header_line)

        # 分隔线（根据列数生成）
        separator = "| " + " | ".join("---" for _ in table_data.headers) + " |"
        lines.append(separator)

        # 数据行
        col_count = len(table_data.headers)
        for row in table_data.rows:
            # 确保每行的列数与表头一致，并转义特殊字符
            cells = []
            for i in range(col_count):
                if i < len(row):
                    cells.append(escape_cell(row[i]))
                else:
                    cells.append("")
            row_line = "| " + " | ".join(cells) + " |"
            lines.append(row_line)

        # 脚注
        if table_data.footer:
            lines.append(f"\n*{table_data.footer}*")

        return "\n".join(lines)

    def checklist(self, items: List[ChecklistItem],
                  title: str = "检查清单") -> str:
        """检查清单输出"""
        return self.format(OutputType.CHECKLIST, {
            "title": title,
            "items": [asdict(item) for item in items],
            "completed": sum(1 for item in items if item.checked),
            "total": len(items),
        })

    def comparison(self, items: List[Dict],
                   dimensions: List[str], title: str = "对比") -> str:
        """对比数据输出"""
        return self.format(OutputType.COMPARISON, {
            "title": title,
            "dimensions": dimensions,
            "items": items,
        })

    # === 交互输出方法 ===

    def quick_replies(self, replies: List[QuickReply]) -> str:
        """快捷回复输出"""
        return self.format(OutputType.QUICK_REPLIES, {
            "replies": [asdict(r) for r in replies],
        })

    def action_buttons(self, buttons: List[ActionButton]) -> str:
        """操作按钮输出"""
        return self.format(OutputType.ACTION_BUTTONS, {
            "buttons": [asdict(b) for b in buttons],
        })

    # === 元数据输出方法 ===

    def stream_start(self) -> str:
        """流开始标记"""
        return self.format(OutputType.STREAM_START, {
            "session_id": self.session_id,
            "request_id": self.request_id,
            "user_type": self.user_type,
            "start_time": self.start_time,
        })

    def stream_end(self, total_tokens: Optional[int] = None) -> str:
        """流结束标记"""
        end_time = time.time()
        return self.format(OutputType.STREAM_END, {
            "session_id": self.session_id,
            "request_id": self.request_id,
            "duration_ms": int((end_time - self.start_time) * 1000),
            "collections_used": self.collections_used,
            "total_tokens": total_tokens,
        })

    def meta(self) -> str:
        """响应元数据输出"""
        return self.format(OutputType.META, StreamMeta(
            session_id=self.session_id,
            user_type=self.user_type,
            request_id=self.request_id,
            start_time=self.start_time,
            collections_used=self.collections_used,
        ))


# === 便捷工厂函数 ===

def create_subsidy_result(
    category: str,
    amount: float,
    rate: float,
    max_limit: float,
) -> SubsidyResult:
    """创建补贴计算结果"""
    calculated = amount * rate
    final = min(calculated, max_limit)
    return SubsidyResult(
        category=category,
        original_amount=amount,
        subsidy_rate=rate,
        calculated_amount=calculated,
        max_limit=max_limit,
        final_amount=final,
        explanation=f"{category}补贴 = {amount:.0f} × {rate*100:.0f}% = {calculated:.0f}元"
                    + (f"，超过上限{max_limit:.0f}元，实际补贴{final:.0f}元"
                       if calculated > max_limit else ""),
    )


def create_decoration_process() -> List[ProcessStep]:
    """创建标准装修流程"""
    return [
        ProcessStep(1, "前期准备", "确定预算、选择风格、找设计师", "1-2周",
                   tips=["多看案例确定喜好", "预算要留10%机动"],
                   warnings=["不要盲目追求低价"]),
        ProcessStep(2, "设计阶段", "量房、方案设计、方案确认", "2-4周",
                   tips=["确认动线设计", "注意收纳空间"],
                   warnings=["方案确认后改动成本高"]),
        ProcessStep(3, "拆改阶段", "墙体拆改、垃圾清运", "1-2周",
                   tips=["拆改需物业审批"],
                   warnings=["承重墙绝对不能拆"]),
        ProcessStep(4, "水电阶段", "水电改造、打压测试", "1-2周",
                   tips=["插座数量要充足", "拍照留存管线走向"],
                   warnings=["强弱电要分开走"]),
        ProcessStep(5, "泥木阶段", "防水、瓷砖、吊顶、木工", "3-4周",
                   tips=["防水必须做闭水试验"],
                   warnings=["瓷砖要检查空鼓"]),
        ProcessStep(6, "油漆阶段", "墙面处理、刮腻子、刷漆", "2-3周",
                   tips=["选择环保涂料"],
                   warnings=["避免阴雨天施工"]),
        ProcessStep(7, "安装阶段", "橱柜、门、地板、灯具安装", "1-2周",
                   tips=["按顺序安装，先橱柜后地板"]),
        ProcessStep(8, "软装入住", "家具进场、保洁、通风", "1-2周",
                   tips=["通风至少3个月"],
                   warnings=["入住前做甲醛检测"]),
    ]


def format_markdown_table(
    headers: List[str],
    rows: List[List[str]],
    title: Optional[str] = None,
    footer: Optional[str] = None,
    alignment: Optional[List[str]] = None,
) -> str:
    """
    生成格式正确的 Markdown 表格

    Args:
        headers: 表头列表
        rows: 数据行列表
        title: 可选的表格标题
        footer: 可选的表格脚注
        alignment: 可选的对齐方式列表 ('left', 'center', 'right')

    Returns:
        格式化的 Markdown 表格字符串

    Example:
        >>> table = format_markdown_table(
        ...     headers=["品类", "补贴比例", "上限"],
        ...     rows=[
        ...         ["家具", "5%", "2000元"],
        ...         ["建材", "3%", "1500元"],
        ...     ],
        ...     title="补贴政策一览"
        ... )
    """
    if not headers or not rows:
        return ""

    lines = []

    # 标题
    if title:
        lines.append(f"\n**{title}**\n")

    # 表头（转义特殊字符）
    escaped_headers = [str(h).replace("|", "\\|").replace("\n", " ") for h in headers]
    header_line = "| " + " | ".join(escaped_headers) + " |"
    lines.append(header_line)

    # 分隔线（支持对齐）
    if alignment:
        separators = []
        for i, align in enumerate(alignment):
            if i >= len(headers):
                break
            if align == 'center':
                separators.append(":---:")
            elif align == 'right':
                separators.append("---:")
            else:
                separators.append("---")
        # 补齐剩余列
        separators.extend(["---"] * (len(headers) - len(separators)))
        separator = "| " + " | ".join(separators) + " |"
    else:
        separator = "| " + " | ".join("---" for _ in headers) + " |"
    lines.append(separator)

    # 数据行
    for row in rows:
        # 确保每行的列数与表头一致，并转义特殊字符
        padded_row = []
        for i in range(len(headers)):
            if i < len(row):
                cell = str(row[i]).replace("|", "\\|").replace("\n", " ")
                padded_row.append(cell)
            else:
                padded_row.append("")
        row_line = "| " + " | ".join(padded_row) + " |"
        lines.append(row_line)

    # 脚注
    if footer:
        lines.append(f"\n*{footer}*")

    return "\n".join(lines)


def format_subsidy_table() -> str:
    """生成补贴政策表格"""
    return format_markdown_table(
        headers=["品类", "补贴比例", "单笔上限", "适用商品"],
        rows=[
            ["家具", "5%", "2000元", "沙发、床、餐桌、衣柜、书桌"],
            ["建材", "3%", "1500元", "瓷砖、地板、涂料、门窗"],
            ["家电", "4%", "1000元", "空调、冰箱、洗衣机、热水器"],
            ["软装", "6%", "800元", "窗帘、灯具、地毯、装饰画"],
            ["智能��居", "8%", "1500元", "智能门锁、智能音箱、安防监控"],
        ],
        title="洞居平台补贴政策",
        footer="每月补贴上限5000元",
    )


def format_merchant_fee_table() -> str:
    """生成商家费用表格"""
    return format_markdown_table(
        headers=["项目", "金额/费率", "说明"],
        rows=[
            ["入驻保证金", "5000元", "可退，用于保障消费者权益"],
            ["平台服务费", "3%", "按成交金额收取"],
            ["推广最低充值", "1000元", "按效果付费（CPC/CPA）"],
        ],
        title="商家费用说明",
    )
