"""
LLM Function Calling 模块
支持 LLM 自动选择和调用工具
增强版：支持智能参数提取、多轮工具调用、结果整合
"""
import json
import re
import asyncio
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, field

from backend.core.tools import get_tool_registry, ToolResult, ToolDefinition
from backend.core.logging_config import get_logger

logger = get_logger("function_calling")

# 尝试导入 LangChain 相关模块
LANGCHAIN_AVAILABLE = False
LANGCHAIN_TOOLS_AVAILABLE = False

try:
    from langchain_community.chat_models import ChatTongyi
    from langchain_core.messages import HumanMessage, AIMessage, SystemMessage, ToolMessage
    LANGCHAIN_AVAILABLE = True
except ImportError:
    logger.warning("LangChain 未安装，Function Calling 功能受限")

try:
    from langchain_core.tools import StructuredTool, tool as langchain_tool
    from langchain_core.utils.function_calling import convert_to_openai_function
    LANGCHAIN_TOOLS_AVAILABLE = True
except ImportError:
    logger.warning("LangChain Tools 未安装，原生 Function Calling 不可用")


@dataclass
class FunctionCall:
    """函数调用结果"""
    name: str
    arguments: Dict[str, Any]
    result: Optional[Any] = None
    error: Optional[str] = None


@dataclass
class FunctionCallingResult:
    """Function Calling 执行结果"""
    calls: List[FunctionCall] = field(default_factory=list)
    final_response: str = ""
    thinking: List[str] = field(default_factory=list)


class ParameterExtractor:
    """智能参数提取器"""

    # 金额提取模式
    AMOUNT_PATTERNS = [
        (r'(\d+(?:\.\d+)?)\s*万\s*[元块]?', 10000),  # X万
        (r'(\d+(?:\.\d+)?)\s*[元块]', 1),            # X元/块
        (r'(\d{4,}(?:\.\d+)?)', 1),                   # 4位以上数字
        (r'(\d+(?:,\d{3})+(?:\.\d+)?)', 1),          # 带逗号的数字
    ]

    # 面积提取模式
    AREA_PATTERNS = [
        r'(\d+(?:\.\d+)?)\s*[平㎡]',
        r'(\d+(?:\.\d+)?)\s*平米',
        r'(\d+(?:\.\d+)?)\s*平方',
        r'(\d+(?:\.\d+)?)\s*m2',
    ]

    # 品类映射
    CATEGORY_MAPPING = {
        # 家具类
        "沙发": "家具", "床": "家具", "餐桌": "家具", "椅子": "家具",
        "衣柜": "家具", "书桌": "家具", "茶几": "家具", "电视柜": "家具",
        # 建材类
        "瓷砖": "建材", "地板": "建材", "乳胶漆": "建材", "涂料": "建材",
        "水泥": "建材", "木材": "建材", "石材": "建材", "大理石": "建材",
        # 家电类
        "空调": "家电", "冰箱": "家电", "洗衣机": "家电", "电视": "家电",
        "热水器": "家电", "油烟机": "家电", "燃气灶": "家电",
        # 软装类
        "窗帘": "软装", "地毯": "软装", "灯具": "软装", "装饰画": "软装",
        # 智能家居
        "智能锁": "智能家居", "智能音箱": "智能家居", "智能开关": "智能家居",
    }

    # 装修风格
    STYLES = ["现代简约", "北欧", "新中式", "轻奢", "欧式", "美式", "日式", "工业风", "地中海"]

    @classmethod
    def extract_amount(cls, text: str, context_keyword: str = None) -> Optional[float]:
        """
        智能提取金额

        Args:
            text: 输入文本
            context_keyword: 上下文关键词（如"投入"、"收入"）

        Returns:
            提取的金额（元）
        """
        # 如果有上下文关键词，优先在关键词附近提取
        if context_keyword and context_keyword in text:
            # 在关键词后20个字符内查找
            idx = text.find(context_keyword)
            search_text = text[idx:idx+30]
        else:
            search_text = text

        for pattern, multiplier in cls.AMOUNT_PATTERNS:
            matches = re.findall(pattern, search_text)
            if matches:
                amount_str = matches[0].replace(',', '')
                return float(amount_str) * multiplier

        # 回退到全文搜索
        if context_keyword:
            for pattern, multiplier in cls.AMOUNT_PATTERNS:
                matches = re.findall(pattern, text)
                if matches:
                    amount_str = matches[0].replace(',', '')
                    return float(amount_str) * multiplier

        return None

    @classmethod
    def extract_multiple_amounts(cls, text: str) -> List[float]:
        """提取文本中的所有金额"""
        amounts = []
        for pattern, multiplier in cls.AMOUNT_PATTERNS:
            matches = re.findall(pattern, text)
            for match in matches:
                amount_str = match.replace(',', '')
                amounts.append(float(amount_str) * multiplier)
        return sorted(set(amounts))

    @classmethod
    def extract_area(cls, text: str) -> Optional[float]:
        """提取面积"""
        for pattern in cls.AREA_PATTERNS:
            matches = re.findall(pattern, text, re.IGNORECASE)
            if matches:
                return float(matches[0])
        return None

    @classmethod
    def extract_category(cls, text: str) -> Optional[str]:
        """提取商品品类"""
        # 首先检查具体商品
        for item, category in cls.CATEGORY_MAPPING.items():
            if item in text:
                return category

        # 然后检查大类
        main_categories = ["家具", "建材", "家电", "软装", "智能家居"]
        for cat in main_categories:
            if cat in text:
                return cat

        return None

    @classmethod
    def extract_specific_item(cls, text: str) -> Optional[str]:
        """提取具体商品名称"""
        for item in cls.CATEGORY_MAPPING.keys():
            if item in text:
                return item
        return None

    @classmethod
    def extract_style(cls, text: str) -> Optional[str]:
        """提取装修风格"""
        for style in cls.STYLES:
            if style in text:
                return style
        # 简化匹配
        style_keywords = {
            "现代": "现代简约", "简约": "现代简约",
            "北欧": "北欧", "欧式": "欧式",
            "中式": "新中式", "中国风": "新中式",
            "轻奢": "轻奢", "奢华": "轻奢",
            "日式": "日式", "和风": "日式",
            "工业": "工业风", "loft": "工业风",
        }
        for keyword, style in style_keywords.items():
            if keyword in text.lower():
                return style
        return "现代简约"  # 默认风格

    @classmethod
    def extract_period_days(cls, text: str) -> int:
        """提取统计周期（天数）"""
        patterns = [
            (r'(\d+)\s*天', 1),
            (r'(\d+)\s*周', 7),
            (r'(\d+)\s*[个]?月', 30),
            (r'(\d+)\s*年', 365),
        ]
        for pattern, multiplier in patterns:
            matches = re.findall(pattern, text)
            if matches:
                return int(matches[0]) * multiplier
        return 30  # 默认30天


class FunctionCallingEngine:
    """
    Function Calling 引擎

    支持 LLM 自动选择和调用工具，替代硬编码的关键词匹配

    支持两种模式：
    1. 原生 Function Calling（如果 LLM 支持）
    2. 提示词引导的工具选择（回退方案）
    """

    # 工具选择系统提示词
    TOOL_SELECTION_PROMPT = """你是一个智能助手，可以使用以下工具来帮助用户：

{tools_description}

当用户的问题需要使用工具时，请按以下 JSON 格式返回工具调用：
```json
{{"tool_calls": [{{"name": "工具名称", "arguments": {{"参数名": "参数值"}}}}]}}
```

如果不需要使用工具，直接回答用户问题即可。

注意：
1. 只有当问题明确需要计算或查询时才使用工具
2. 可以同时调用多个工具
3. 参数值必须从用户输入中提取，不要编造
4. 金额单位默认为元，如果用户说"万"则需要乘以10000
"""

    def __init__(self, llm=None, max_tool_calls: int = 5, max_retries: int = 2):
        """
        初始化 Function Calling 引擎

        Args:
            llm: LLM 模型实例
            max_tool_calls: 单次最大工具调用次数
            max_retries: 最大重试次数
        """
        self.registry = get_tool_registry()
        self.max_tool_calls = max_tool_calls
        self.max_retries = max_retries
        self._langchain_tools = None

        # 初始化 LLM
        if llm:
            self.llm = llm
        elif LANGCHAIN_AVAILABLE:
            try:
                self.llm = ChatTongyi(model="qwen-plus", temperature=0)
            except Exception as e:
                logger.warning(f"LLM 初始化失败（可能缺少 API key）: {e}")
                self.llm = None
        else:
            self.llm = None

    def _get_langchain_tools(self) -> List:
        """获取 LangChain 格式的工具列表"""
        if self._langchain_tools is not None:
            return self._langchain_tools

        if not LANGCHAIN_TOOLS_AVAILABLE:
            return []

        tools = []
        for tool_def in self.registry.list_tools(enabled_only=True):
            # 创建 StructuredTool
            try:
                structured_tool = StructuredTool.from_function(
                    func=tool_def.handler,
                    name=tool_def.name,
                    description=tool_def.description,
                )
                tools.append(structured_tool)
            except Exception as e:
                logger.warning(f"无法转换工具 {tool_def.name}: {e}")

        self._langchain_tools = tools
        return tools

    def get_tools_description(self, categories: List[str] = None) -> str:
        """获取工具描述文本"""
        tools = self.registry.list_tools(enabled_only=True)

        if categories:
            tools = [t for t in tools if t.category.value in categories]

        descriptions = []
        for tool in tools:
            params_desc = []
            for p in tool.parameters:
                param_str = f"  - {p.name} ({p.param_type.__name__}): {p.description}"
                if p.required:
                    param_str += " [必填]"
                if p.enum_values:
                    param_str += f" 可选值: {p.enum_values}"
                params_desc.append(param_str)

            desc = f"""工具名称: {tool.name}
描述: {tool.description}
参数:
{chr(10).join(params_desc)}
"""
            descriptions.append(desc)

        return "\n---\n".join(descriptions)

    def get_tools_for_llm(self) -> List[Dict]:
        """获取 LLM 格式的工具定义"""
        return self.registry.get_tools_for_llm()

    async def process_with_tools(
        self,
        message: str,
        context: Dict = None,
        allowed_tools: List[str] = None,
        use_native_fc: bool = True
    ) -> FunctionCallingResult:
        """
        使用工具处理用户消息

        Args:
            message: 用户消息
            context: 上下文信息
            allowed_tools: 允许使用的工具列表
            use_native_fc: 是否尝试使用原生 Function Calling

        Returns:
            FunctionCallingResult
        """
        result = FunctionCallingResult()

        if not self.llm:
            result.thinking.append("LLM 未配置，使用规则匹配模式")
            # 回退到规则匹配
            return self.process_with_tools_sync(message, context, allowed_tools)

        # 首先尝试规则匹配（快速路径）
        detected_tools = self._detect_tool_intent(message)
        if detected_tools:
            result.thinking.append(f"规则匹配检测到工具: {[t['name'] for t in detected_tools]}")

            for tool_info in detected_tools[:self.max_tool_calls]:
                tool_name = tool_info["name"]
                arguments = tool_info["arguments"]

                if allowed_tools and tool_name not in allowed_tools:
                    result.thinking.append(f"跳过工具 {tool_name}: 不在允许列表中")
                    continue

                # 执行工具（带重试）
                tool_result = await self._execute_tool_with_retry(tool_name, arguments)

                call = FunctionCall(
                    name=tool_name,
                    arguments=arguments,
                    result=tool_result.data if tool_result.success else None,
                    error=tool_result.error,
                )
                result.calls.append(call)

                if tool_result.success:
                    result.thinking.append(f"工具 {tool_name} 执行成功")
                else:
                    result.thinking.append(f"工具 {tool_name} 执行失败: {tool_result.error}")

            if result.calls:
                return result

        # 如果规则匹配没有结果，使用 LLM 判断
        result.thinking.append("规则匹配无结果，使用 LLM 判断")

        # 1. 让 LLM 决定是否需要调用工具
        tools_desc = self.get_tools_description()
        system_prompt = self.TOOL_SELECTION_PROMPT.format(tools_description=tools_desc)

        for attempt in range(self.max_retries + 1):
            try:
                # 调用 LLM
                response = await self._call_llm(system_prompt, message, context)

                if not response:
                    result.thinking.append("LLM 返回空响应")
                    break

                result.thinking.append(f"LLM 响应 (尝试 {attempt + 1}): {response[:200]}...")

                # 2. 解析工具调用
                tool_calls = self._parse_tool_calls(response)

                if tool_calls:
                    result.thinking.append(f"检测到 {len(tool_calls)} 个工具调用")

                    # 3. 执行工具调用
                    for call in tool_calls[:self.max_tool_calls]:
                        if allowed_tools and call.name not in allowed_tools:
                            call.error = f"工具 {call.name} 不在允许列表中"
                            result.thinking.append(f"跳过工具 {call.name}: 不在允许列表中")
                            continue

                        tool_result = await self._execute_tool_with_retry(call.name, call.arguments)
                        call.result = tool_result.data if tool_result.success else None
                        call.error = tool_result.error

                        if tool_result.success:
                            result.thinking.append(f"工具 {call.name} 执行成功")
                        else:
                            result.thinking.append(f"工具 {call.name} 执行失败: {tool_result.error}")

                        result.calls.append(call)

                    # 4. 生成最终响应
                    if result.calls:
                        result.final_response = await self._generate_final_response(
                            message, result.calls, context
                        )
                    break
                else:
                    # 不需要工具，直接使用 LLM 响应
                    result.final_response = response
                    result.thinking.append("无需工具调用，直接返回 LLM 响应")
                    break

            except Exception as e:
                logger.warning(f"Function Calling 尝试 {attempt + 1} 失败: {e}")
                result.thinking.append(f"尝试 {attempt + 1} 失败: {str(e)}")

                if attempt < self.max_retries:
                    await asyncio.sleep(0.5 * (attempt + 1))  # 指数退避
                else:
                    logger.error(f"Function Calling 处理失败，已重试 {self.max_retries} 次", exc_info=True)

        return result

    async def _execute_tool_with_retry(self, tool_name: str, arguments: Dict,
                                        max_retries: int = 2) -> ToolResult:
        """带重试的工具执行"""
        last_error = None

        for attempt in range(max_retries + 1):
            try:
                result = self.registry.call(tool_name, **arguments)
                if result.success:
                    return result
                last_error = result.error
            except Exception as e:
                last_error = str(e)

            if attempt < max_retries:
                await asyncio.sleep(0.2 * (attempt + 1))

        return ToolResult(success=False, error=last_error or "未知错误")

    def process_with_tools_sync(
        self,
        message: str,
        context: Dict = None,
        allowed_tools: List[str] = None
    ) -> FunctionCallingResult:
        """
        同步版本的工具处理

        Args:
            message: 用户消息
            context: 上下文信息
            allowed_tools: 允许使用的工具列表

        Returns:
            FunctionCallingResult
        """
        result = FunctionCallingResult()

        # 1. 使用规则匹配检测工具调用意图
        detected_tools = self._detect_tool_intent(message)

        if detected_tools:
            result.thinking.append(f"检测到工具调用意图: {[t['name'] for t in detected_tools]}")

            for tool_info in detected_tools[:self.max_tool_calls]:
                tool_name = tool_info["name"]
                arguments = tool_info["arguments"]

                if allowed_tools and tool_name not in allowed_tools:
                    result.thinking.append(f"跳过工具 {tool_name}: 不在允许列表中")
                    continue

                # 执行工具
                tool_result = self._execute_tool(tool_name, arguments)

                call = FunctionCall(
                    name=tool_name,
                    arguments=arguments,
                    result=tool_result.data if tool_result.success else None,
                    error=tool_result.error,
                )
                result.calls.append(call)

                if tool_result.success:
                    result.thinking.append(f"工具 {tool_name} 执行成功")
                else:
                    result.thinking.append(f"工具 {tool_name} 执行失败: {tool_result.error}")

        return result

    def _detect_tool_intent(self, message: str) -> List[Dict]:
        """
        使用智能参数提取器检测工具调用意图

        使用 ParameterExtractor 进行更准确的参数提取
        """
        detected = []

        # 补贴计算检测
        subsidy_keywords = ["补贴", "能补多少", "返多少", "优惠", "返现", "补贴金额"]
        if any(kw in message for kw in subsidy_keywords):
            amount = ParameterExtractor.extract_amount(message)
            category = ParameterExtractor.extract_category(message)

            if amount and category:
                detected.append({
                    "name": "subsidy_calculator",
                    "arguments": {"amount": amount, "category": category}
                })

        # ROI 计算检测
        roi_keywords = ["ROI", "投入产出", "回报率", "收益率", "投资回报"]
        if any(kw in message for kw in roi_keywords):
            # 尝试提取投入和收入
            investment = ParameterExtractor.extract_amount(message, "投入")
            if not investment:
                investment = ParameterExtractor.extract_amount(message, "花")
            if not investment:
                investment = ParameterExtractor.extract_amount(message, "成本")

            revenue = ParameterExtractor.extract_amount(message, "收入")
            if not revenue:
                revenue = ParameterExtractor.extract_amount(message, "赚")
            if not revenue:
                revenue = ParameterExtractor.extract_amount(message, "营收")

            # 如果只找到一个金额，尝试提取所有金额
            if not (investment and revenue):
                amounts = ParameterExtractor.extract_multiple_amounts(message)
                if len(amounts) >= 2:
                    investment = amounts[0]
                    revenue = amounts[1]

            if investment and revenue:
                period_days = ParameterExtractor.extract_period_days(message)
                detected.append({
                    "name": "roi_calculator",
                    "arguments": {
                        "investment": investment,
                        "revenue": revenue,
                        "period_days": period_days
                    }
                })

        # 价格评估检测
        price_keywords = ["贵不贵", "价格合理", "值不值", "性价比", "划算", "便宜", "价格怎么样"]
        if any(kw in message for kw in price_keywords):
            price = ParameterExtractor.extract_amount(message)
            item = ParameterExtractor.extract_specific_item(message)

            if price and item:
                area = ParameterExtractor.extract_area(message)
                detected.append({
                    "name": "price_evaluator",
                    "arguments": {
                        "category": item,
                        "price": price,
                        **({"area": area} if area else {})
                    }
                })

        # 工期估算检测
        timeline_keywords = ["多久", "工期", "多长时间", "装修时间", "需要几天", "几个月能装完"]
        if any(kw in message for kw in timeline_keywords):
            area = ParameterExtractor.extract_area(message)

            if area:
                style = ParameterExtractor.extract_style(message)
                detected.append({
                    "name": "decoration_timeline",
                    "arguments": {"house_area": area, "style": style}
                })

        # 预算规划检测
        budget_keywords = ["预算", "怎么分配", "预算规划", "预算分配", "钱怎么花"]
        if any(kw in message for kw in budget_keywords):
            budget = ParameterExtractor.extract_amount(message)
            area = ParameterExtractor.extract_area(message)

            if budget and area:
                style = ParameterExtractor.extract_style(message)
                detected.append({
                    "name": "budget_planner",
                    "arguments": {
                        "total_budget": budget,
                        "house_area": area,
                        "style": style
                    }
                })

        # 材料用量计算检测
        material_keywords = ["需要多少", "用量", "要买多少", "材料计算"]
        material_types = ["瓷砖", "地板", "乳胶漆", "墙纸", "水泥", "沙子", "电线", "水管"]
        if any(kw in message for kw in material_keywords):
            area = ParameterExtractor.extract_area(message)
            material_type = None
            for mt in material_types:
                if mt in message:
                    material_type = mt
                    break

            if area and material_type:
                detected.append({
                    "name": "material_calculator",
                    "arguments": {
                        "material_type": material_type,
                        "area": area
                    }
                })

        # 商家评分计算检测（B端）
        merchant_score_keywords = ["店铺评分", "商家评分", "我的评分", "评分多少"]
        if any(kw in message for kw in merchant_score_keywords):
            # 尝试从消息中提取数据
            amounts = ParameterExtractor.extract_multiple_amounts(message)
            if len(amounts) >= 2:
                detected.append({
                    "name": "merchant_score_calculator",
                    "arguments": {
                        "monthly_orders": int(amounts[0]) if amounts else 50,
                        "good_rate": 0.95,  # 默认值
                        "response_time": 10,  # 默认值
                    }
                })

        # 转化率分析检测（B端）
        conversion_keywords = ["转化率", "转化分析", "成交率", "咨询转化"]
        if any(kw in message for kw in conversion_keywords):
            amounts = ParameterExtractor.extract_multiple_amounts(message)
            if len(amounts) >= 3:
                detected.append({
                    "name": "conversion_rate_analyzer",
                    "arguments": {
                        "visitors": int(amounts[0]),
                        "inquiries": int(amounts[1]),
                        "orders": int(amounts[2])
                    }
                })

        return detected

    def _parse_tool_calls(self, response: str) -> List[FunctionCall]:
        """解析 LLM 响应中的工具调用"""
        calls = []

        # 尝试提取 JSON 格式的工具调用
        json_pattern = r'```json\s*(.*?)\s*```'
        matches = re.findall(json_pattern, response, re.DOTALL)

        for match in matches:
            try:
                data = json.loads(match)
                if "tool_calls" in data:
                    for call_data in data["tool_calls"]:
                        calls.append(FunctionCall(
                            name=call_data.get("name", ""),
                            arguments=call_data.get("arguments", {}),
                        ))
            except json.JSONDecodeError:
                continue

        # 如果没有找到 JSON 格式，尝试其他格式
        if not calls:
            # 尝试直接解析 JSON 对象
            try:
                data = json.loads(response)
                if "tool_calls" in data:
                    for call_data in data["tool_calls"]:
                        calls.append(FunctionCall(
                            name=call_data.get("name", ""),
                            arguments=call_data.get("arguments", {}),
                        ))
            except json.JSONDecodeError:
                pass

        return calls

    def _execute_tool(self, tool_name: str, arguments: Dict) -> ToolResult:
        """执行工具调用"""
        logger.info(f"执行工具: {tool_name}", extra={"arguments": arguments})
        return self.registry.call(tool_name, **arguments)

    async def _call_llm(self, system_prompt: str, message: str, context: Dict = None) -> str:
        """调用 LLM"""
        if not LANGCHAIN_AVAILABLE or not self.llm:
            return ""

        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=message),
        ]

        response = await self.llm.ainvoke(messages)
        return response.content

    async def _generate_final_response(
        self,
        message: str,
        calls: List[FunctionCall],
        context: Dict = None
    ) -> str:
        """根据工具调用结果生成最终响应"""
        if not LANGCHAIN_AVAILABLE or not self.llm:
            # 简单拼接结果
            results = []
            for call in calls:
                if call.result:
                    results.append(f"{call.name}: {json.dumps(call.result, ensure_ascii=False)}")
            return "\n".join(results)

        # 构建包含工具结果的提示
        tool_results = []
        for call in calls:
            if call.result:
                tool_results.append(f"工具 {call.name} 返回: {json.dumps(call.result, ensure_ascii=False)}")
            elif call.error:
                tool_results.append(f"工具 {call.name} 失败: {call.error}")

        prompt = f"""用户问题: {message}

工具调用结果:
{chr(10).join(tool_results)}

请根据以上工具调用结果，用自然语言回答用户的问题。回答要简洁明了，突出关键信息。"""

        messages = [HumanMessage(content=prompt)]
        response = await self.llm.ainvoke(messages)
        return response.content


# 全局 Function Calling 引擎
_fc_engine: Optional[FunctionCallingEngine] = None


def get_function_calling_engine() -> FunctionCallingEngine:
    """获取全局 Function Calling 引擎"""
    global _fc_engine
    if _fc_engine is None:
        _fc_engine = FunctionCallingEngine()
    return _fc_engine
