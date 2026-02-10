"""
智能体路由器

根据请求特征将请求路由到合适的智能体
"""

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Pattern
import re
import logging

logger = logging.getLogger(__name__)


@dataclass
class RoutingRule:
    """路由规则"""
    name: str
    agent_name: str
    priority: int = 0  # 优先级，越大越先匹配

    # 匹配条件
    user_types: Optional[List[str]] = None  # 用户类型
    keywords: Optional[List[str]] = None  # 关键词
    patterns: Optional[List[str]] = None  # 正则表达式
    condition: Optional[Callable] = None  # 自定义条件函数

    # 元数据
    description: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def matches(self, request: Any) -> bool:
        """检查请求是否匹配此规则"""
        # 用户类型匹配
        if self.user_types:
            user_type = getattr(request, "user_type", None)
            if user_type not in self.user_types:
                return False

        # 关键词匹配
        if self.keywords:
            message = getattr(request, "message", "")
            if not any(kw in message for kw in self.keywords):
                return False

        # 正则匹配
        if self.patterns:
            message = getattr(request, "message", "")
            if not any(re.search(p, message) for p in self.patterns):
                return False

        # 自定义条件
        if self.condition:
            if not self.condition(request):
                return False

        return True


class AgentRouter:
    """
    智能体路由器

    功能:
    - 基于规则的路由
    - 优先级排序
    - 动态规则管理

    使用示例:
    ```python
    router = AgentRouter()

    # 添加规则
    router.add_rule(RoutingRule(
        name="c_end_subsidy",
        agent_name="c_end",
        user_types=["c_end"],
        keywords=["补贴", "优惠"]
    ))

    # 路由请求
    agent_name = router.route(request)
    ```
    """

    def __init__(self):
        self._rules: List[RoutingRule] = []
        self._default_agent: Optional[str] = None

    def add_rule(self, rule: RoutingRule) -> None:
        """添加路由规则"""
        self._rules.append(rule)
        # 按优先级排序
        self._rules.sort(key=lambda r: r.priority, reverse=True)
        logger.debug(f"Added routing rule: {rule.name}")

    def remove_rule(self, name: str) -> bool:
        """移除路由规则"""
        for i, rule in enumerate(self._rules):
            if rule.name == name:
                self._rules.pop(i)
                return True
        return False

    def remove_rules_for_agent(self, agent_name: str) -> int:
        """移除指定智能体的所有规则"""
        original_count = len(self._rules)
        self._rules = [r for r in self._rules if r.agent_name != agent_name]
        return original_count - len(self._rules)

    def set_default(self, agent_name: str) -> None:
        """设置默认智能体"""
        self._default_agent = agent_name

    def route(self, request: Any) -> Optional[str]:
        """
        路由请求

        Args:
            request: 请求对象

        Returns:
            智能体名称，如果没有匹配则返回默认智能体或 None
        """
        for rule in self._rules:
            if rule.matches(request):
                logger.debug(f"Request matched rule: {rule.name} -> {rule.agent_name}")
                return rule.agent_name

        return self._default_agent

    def get_rules(self) -> List[RoutingRule]:
        """获取所有规则"""
        return list(self._rules)

    def get_rules_for_agent(self, agent_name: str) -> List[RoutingRule]:
        """获取指定智能体的规则"""
        return [r for r in self._rules if r.agent_name == agent_name]


# 预定义的路由规则
DEFAULT_ROUTING_RULES = [
    # C端规则
    RoutingRule(
        name="c_end_by_user_type",
        agent_name="c_end",
        priority=100,
        user_types=["c_end"],
        description="C端用户默认路由到C端智能体"
    ),
    RoutingRule(
        name="c_end_subsidy",
        agent_name="c_end",
        priority=90,
        keywords=["补贴", "优惠", "折扣", "省钱"],
        description="补贴相关问题路由到C端智能体"
    ),
    RoutingRule(
        name="c_end_decoration",
        agent_name="c_end",
        priority=80,
        keywords=["装修", "风格", "设计", "材料", "施工"],
        description="装修相关问题路由到C端智能体"
    ),

    # B端规则
    RoutingRule(
        name="b_end_by_user_type",
        agent_name="b_end",
        priority=100,
        user_types=["b_end"],
        description="B端用户默认路由到B端智能体"
    ),
    RoutingRule(
        name="b_end_merchant",
        agent_name="b_end",
        priority=90,
        keywords=["入驻", "商家", "店铺", "获客", "转化", "ROI"],
        description="商家相关问题路由到B端智能体"
    ),
]


def create_default_router() -> AgentRouter:
    """创建带有默认规则的路由器"""
    router = AgentRouter()
    router.set_default("c_end")

    for rule in DEFAULT_ROUTING_RULES:
        router.add_rule(rule)

    return router
