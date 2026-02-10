"""
知识蒸馏器

从交互历史中提取和蒸馏知识，用于改进智能体
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
from enum import Enum
import asyncio
import logging
import json
from pathlib import Path
from collections import defaultdict

from ..events import Event, EventType, get_event_bus
from ..config import LearningConfig
from .feedback import FeedbackCollector, Feedback, FeedbackType

logger = logging.getLogger(__name__)


class KnowledgeType(str, Enum):
    """知识类型"""
    FAQ = "faq"  # 常见问答
    PATTERN = "pattern"  # 问题模式
    ENTITY = "entity"  # 实体知识
    RELATION = "relation"  # 关系知识
    RULE = "rule"  # 业务规则
    PREFERENCE = "preference"  # 用户偏好


@dataclass
class DistilledKnowledge:
    """蒸馏的知识"""
    id: str
    type: KnowledgeType
    content: Dict[str, Any]
    confidence: float
    source_count: int  # 来源数量
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "id": self.id,
            "type": self.type.value,
            "content": self.content,
            "confidence": self.confidence,
            "source_count": self.source_count,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "metadata": self.metadata
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DistilledKnowledge":
        """从字典创建"""
        data = data.copy()
        data["type"] = KnowledgeType(data["type"])
        if isinstance(data["created_at"], str):
            data["created_at"] = datetime.fromisoformat(data["created_at"])
        if isinstance(data["updated_at"], str):
            data["updated_at"] = datetime.fromisoformat(data["updated_at"])
        return cls(**data)


class KnowledgeDistiller:
    """
    知识蒸馏器

    功能:
    - 从交互历史中提取常见问答
    - 识别问题模式
    - 提取实体和关系
    - 发现业务规则
    - 学习用户偏好

    使用示例:
    ```python
    distiller = KnowledgeDistiller()

    # 添加交互记录
    await distiller.add_interaction(query, response, feedback)

    # 运行蒸馏
    knowledge = await distiller.distill()

    # 获取蒸馏的知识
    faqs = distiller.get_knowledge(KnowledgeType.FAQ)
    ```
    """

    def __init__(self, config: LearningConfig = None):
        self._config = config or LearningConfig()
        self._event_bus = get_event_bus()

        # 交互历史
        self._interactions: List[Dict[str, Any]] = []

        # 蒸馏的知识
        self._knowledge: Dict[str, DistilledKnowledge] = {}

        # 问题聚类
        self._question_clusters: Dict[str, List[Dict[str, Any]]] = defaultdict(list)

        # 知识计数器
        self._knowledge_counter = 0

        # 持久化路径
        self._persistence_path = Path(self._config.learning_data_path) / "knowledge"
        self._persistence_path.mkdir(parents=True, exist_ok=True)

        # 加载历史知识
        self._load_knowledge()

    def _load_knowledge(self) -> None:
        """加载历史知识"""
        knowledge_file = self._persistence_path / "distilled_knowledge.json"
        if knowledge_file.exists():
            try:
                with open(knowledge_file, "r", encoding="utf-8") as f:
                    data = json.load(f)

                for k_data in data.get("knowledge", []):
                    knowledge = DistilledKnowledge.from_dict(k_data)
                    self._knowledge[knowledge.id] = knowledge

                self._knowledge_counter = data.get("counter", 0)
                logger.info(f"Loaded {len(self._knowledge)} distilled knowledge items")
            except Exception as e:
                logger.error(f"Failed to load knowledge: {e}")

    def _save_knowledge(self) -> None:
        """保存知识"""
        knowledge_file = self._persistence_path / "distilled_knowledge.json"
        try:
            data = {
                "counter": self._knowledge_counter,
                "knowledge": [k.to_dict() for k in self._knowledge.values()]
            }
            with open(knowledge_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Failed to save knowledge: {e}")

    async def add_interaction(
        self,
        query: str,
        response: str,
        feedback: Optional[Feedback] = None,
        metadata: Dict[str, Any] = None
    ) -> None:
        """
        添加交互记录

        Args:
            query: 用户查询
            response: 智能体响应
            feedback: 用户反馈
            metadata: 额外元数据
        """
        interaction = {
            "query": query,
            "response": response,
            "feedback": feedback.to_dict() if feedback else None,
            "timestamp": datetime.now().isoformat(),
            "metadata": metadata or {}
        }

        self._interactions.append(interaction)

        # 简单的问题聚类（基于关键词）
        cluster_key = self._get_cluster_key(query)
        self._question_clusters[cluster_key].append(interaction)

    def _get_cluster_key(self, query: str) -> str:
        """获取问题的聚类键"""
        # 简单的关键词提取
        keywords = []

        # 装修相关关键词
        decoration_keywords = ["装修", "风格", "材料", "施工", "设计", "预算", "报价"]
        for kw in decoration_keywords:
            if kw in query:
                keywords.append(kw)

        # 补贴相关关键词
        subsidy_keywords = ["补贴", "优惠", "折扣", "省钱", "活动"]
        for kw in subsidy_keywords:
            if kw in query:
                keywords.append(kw)

        # 商家相关关键词
        merchant_keywords = ["商家", "入驻", "店铺", "获客", "转化"]
        for kw in merchant_keywords:
            if kw in query:
                keywords.append(kw)

        return "_".join(sorted(keywords)) if keywords else "general"

    async def distill(self) -> List[DistilledKnowledge]:
        """
        运行知识蒸馏

        Returns:
            新蒸馏的知识列表
        """
        if not self._config.knowledge_distillation_enabled:
            return []

        await self._event_bus.emit(Event(
            type=EventType.LEARNING_STARTED,
            payload={"type": "knowledge_distillation"},
            source="distiller"
        ))

        new_knowledge = []

        # 1. 提取常见问答
        faqs = await self._extract_faqs()
        new_knowledge.extend(faqs)

        # 2. 识别问题模式
        patterns = await self._extract_patterns()
        new_knowledge.extend(patterns)

        # 3. 提取用户偏好
        preferences = await self._extract_preferences()
        new_knowledge.extend(preferences)

        # 保存知识
        self._save_knowledge()

        await self._event_bus.emit(Event(
            type=EventType.KNOWLEDGE_DISTILLED,
            payload={"count": len(new_knowledge)},
            source="distiller"
        ))

        return new_knowledge

    async def _extract_faqs(self) -> List[DistilledKnowledge]:
        """提取常见问答"""
        faqs = []

        for cluster_key, interactions in self._question_clusters.items():
            if len(interactions) < 3:  # 至少3次相似问题
                continue

            # 找出评分最高的回答
            best_interaction = None
            best_score = -1

            for interaction in interactions:
                feedback = interaction.get("feedback")
                if feedback:
                    score = feedback.get("value", 0) if feedback.get("type") == "rating" else 0
                    if score > best_score:
                        best_score = score
                        best_interaction = interaction

            if best_interaction and best_score >= 4:  # 评分4分以上
                self._knowledge_counter += 1
                knowledge = DistilledKnowledge(
                    id=f"faq_{self._knowledge_counter}",
                    type=KnowledgeType.FAQ,
                    content={
                        "cluster_key": cluster_key,
                        "sample_query": best_interaction["query"],
                        "best_response": best_interaction["response"],
                        "frequency": len(interactions)
                    },
                    confidence=min(1.0, len(interactions) / 10),
                    source_count=len(interactions)
                )

                self._knowledge[knowledge.id] = knowledge
                faqs.append(knowledge)

        return faqs

    async def _extract_patterns(self) -> List[DistilledKnowledge]:
        """提取问题模式"""
        patterns = []

        # 分析问题的结构模式
        pattern_counts = defaultdict(int)

        for interaction in self._interactions:
            query = interaction["query"]

            # 简单的模式识别
            if "多少" in query or "几" in query:
                pattern_counts["quantity_question"] += 1
            if "怎么" in query or "如何" in query:
                pattern_counts["how_question"] += 1
            if "为什么" in query:
                pattern_counts["why_question"] += 1
            if "什么" in query:
                pattern_counts["what_question"] += 1
            if "哪" in query:
                pattern_counts["which_question"] += 1

        # 创建模式知识
        for pattern, count in pattern_counts.items():
            if count >= 5:  # 至少5次出现
                self._knowledge_counter += 1
                knowledge = DistilledKnowledge(
                    id=f"pattern_{self._knowledge_counter}",
                    type=KnowledgeType.PATTERN,
                    content={
                        "pattern": pattern,
                        "frequency": count
                    },
                    confidence=min(1.0, count / 20),
                    source_count=count
                )

                self._knowledge[knowledge.id] = knowledge
                patterns.append(knowledge)

        return patterns

    async def _extract_preferences(self) -> List[DistilledKnowledge]:
        """提取用户偏好"""
        preferences = []

        # 分析用户偏好
        style_mentions = defaultdict(int)
        budget_mentions = defaultdict(int)

        for interaction in self._interactions:
            query = interaction["query"]

            # 风格偏好
            styles = ["现代简约", "北欧", "新中式", "轻奢", "日式"]
            for style in styles:
                if style in query:
                    style_mentions[style] += 1

            # 预算偏好
            if "便宜" in query or "省钱" in query:
                budget_mentions["budget_conscious"] += 1
            if "高端" in query or "品质" in query:
                budget_mentions["quality_focused"] += 1

        # 创建偏好知识
        if style_mentions:
            self._knowledge_counter += 1
            knowledge = DistilledKnowledge(
                id=f"pref_{self._knowledge_counter}",
                type=KnowledgeType.PREFERENCE,
                content={
                    "category": "style",
                    "distribution": dict(style_mentions)
                },
                confidence=0.7,
                source_count=sum(style_mentions.values())
            )
            self._knowledge[knowledge.id] = knowledge
            preferences.append(knowledge)

        if budget_mentions:
            self._knowledge_counter += 1
            knowledge = DistilledKnowledge(
                id=f"pref_{self._knowledge_counter}",
                type=KnowledgeType.PREFERENCE,
                content={
                    "category": "budget",
                    "distribution": dict(budget_mentions)
                },
                confidence=0.7,
                source_count=sum(budget_mentions.values())
            )
            self._knowledge[knowledge.id] = knowledge
            preferences.append(knowledge)

        return preferences

    def get_knowledge(
        self,
        knowledge_type: KnowledgeType = None,
        min_confidence: float = 0.0
    ) -> List[DistilledKnowledge]:
        """获取蒸馏的知识"""
        knowledge = list(self._knowledge.values())

        if knowledge_type:
            knowledge = [k for k in knowledge if k.type == knowledge_type]

        if min_confidence > 0:
            knowledge = [k for k in knowledge if k.confidence >= min_confidence]

        return sorted(knowledge, key=lambda k: k.confidence, reverse=True)

    def get_faq_for_query(self, query: str) -> Optional[DistilledKnowledge]:
        """根据查询获取相关FAQ"""
        cluster_key = self._get_cluster_key(query)

        for knowledge in self._knowledge.values():
            if knowledge.type == KnowledgeType.FAQ:
                if knowledge.content.get("cluster_key") == cluster_key:
                    return knowledge

        return None

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            "total_interactions": len(self._interactions),
            "total_knowledge": len(self._knowledge),
            "by_type": {
                kt.value: len([k for k in self._knowledge.values() if k.type == kt])
                for kt in KnowledgeType
            },
            "cluster_count": len(self._question_clusters)
        }
