"""
DecoPilot Framework 使用示例

展示如何使用新框架创建和运行智能体
"""

import asyncio
from backend.framework import (
    EventBus,
    get_event_bus,
    Event,
    EventType,
    ConfigCenter,
    get_config_center,
    AgentConfig,
)
from backend.framework.runtime import AgentRuntime, create_agent
from backend.framework.orchestration import AgentOrchestrator, get_orchestrator, RoutingRule
from backend.framework.learning import FeedbackCollector, FeedbackType
from backend.framework.observability import get_tracer, get_metrics, get_logger


async def example_basic_usage():
    """基础使用示例"""
    print("=" * 50)
    print("基础使用示例")
    print("=" * 50)

    # 1. 创建智能体
    agent = create_agent(
        name="demo_agent",
        agent_type="c_end"
    )

    # 2. 初始化
    await agent.initialize()

    # 3. 处理请求
    result = await agent.process(
        message="装修补贴怎么计算？",
        session_id="session_001",
        user_id="user_001"
    )

    print(f"回答: {result.answer}")
    print(f"思考过程: {result.thinking_logs}")

    # 4. 关闭
    await agent.shutdown()


async def example_event_driven():
    """事件驱动示例"""
    print("\n" + "=" * 50)
    print("事件驱动示例")
    print("=" * 50)

    # 获取事件总线
    bus = get_event_bus()

    # 订阅事件
    @bus.on(EventType.REQUEST_RECEIVED)
    async def on_request(event: Event):
        print(f"收到请求: {event.payload}")

    @bus.on(EventType.REASONING_COMPLETED)
    async def on_reasoning(event: Event):
        print(f"推理完成: {event.payload}")

    # 发布事件
    await bus.emit(Event(
        type=EventType.REQUEST_RECEIVED,
        payload={"message": "测试消息"},
        source="example"
    ))


async def example_orchestration():
    """编排示例"""
    print("\n" + "=" * 50)
    print("编排示例")
    print("=" * 50)

    # 获取编排器
    orchestrator = get_orchestrator()

    # 创建智能体
    c_end_agent = create_agent("c_end", "c_end")
    b_end_agent = create_agent("b_end", "b_end")

    await c_end_agent.initialize()
    await b_end_agent.initialize()

    # 注册智能体
    orchestrator.register_agent(
        "c_end",
        c_end_agent,
        routing_rules=[
            RoutingRule(
                name="c_end_default",
                agent_name="c_end",
                user_types=["c_end"],
                priority=100
            )
        ]
    )

    orchestrator.register_agent(
        "b_end",
        b_end_agent,
        routing_rules=[
            RoutingRule(
                name="b_end_default",
                agent_name="b_end",
                user_types=["b_end"],
                priority=100
            )
        ]
    )

    # 启动编排器
    await orchestrator.start()

    print(f"已注册智能体: {orchestrator.list_agents()}")

    # 停止
    await orchestrator.stop()


async def example_learning():
    """学习层示例"""
    print("\n" + "=" * 50)
    print("学习层示例")
    print("=" * 50)

    from backend.framework.learning import (
        FeedbackCollector,
        StrategyOptimizer,
        KnowledgeDistiller,
        ExperienceReplay
    )
    from backend.framework.config import LearningConfig

    config = LearningConfig(
        feedback_enabled=True,
        strategy_optimization_enabled=True
    )

    # 1. 反馈收集
    feedback_collector = FeedbackCollector(config)

    await feedback_collector.collect_explicit(
        feedback_type=FeedbackType.RATING,
        value=5,
        request_id="req_001",
        session_id="session_001",
        user_id="user_001",
        agent_name="c_end",
        query="装修补贴怎么算？",
        response="根据您的订单金额..."
    )

    print(f"反馈统计: {feedback_collector.get_stats()}")

    # 2. 策略优化
    optimizer = StrategyOptimizer(feedback_collector, config)

    # 记录策略结果
    from backend.framework.config import ReasoningStrategy
    await optimizer.record_result(
        strategy=ReasoningStrategy.CHAIN_OF_THOUGHT,
        success=True,
        execution_time=2.5,
        rating=5
    )

    print(f"策略统计: {optimizer.get_strategy_stats()}")

    # 3. 经验回放
    replay = ExperienceReplay(config=config)

    await replay.add(
        state={"query": "测试问题"},
        action={"strategy": "cot"},
        reward=0.8
    )

    print(f"经验统计: {replay.get_stats()}")


async def example_observability():
    """可观测性示例"""
    print("\n" + "=" * 50)
    print("可观测性示例")
    print("=" * 50)

    # 1. 追踪
    tracer = get_tracer()

    with tracer.span("example_operation") as span:
        span.set_attribute("user_id", "123")
        span.add_event("processing_started")

        # 模拟处理
        await asyncio.sleep(0.1)

        span.add_event("processing_completed")

    print(f"Span 数量: {len(tracer.get_spans())}")

    # 2. 指标
    metrics = get_metrics()

    request_counter = metrics.counter("example_requests", "Example request counter")
    request_counter.inc()
    request_counter.inc()

    response_time = metrics.histogram("example_response_time", "Response time")
    response_time.observe(0.5)
    response_time.observe(0.3)

    print(f"指标: {metrics.get_all_metrics()}")

    # 3. 日志
    logger = get_logger()

    with logger.context(request_id="req_123"):
        logger.info("Processing request", user_id="user_456")


async def example_streaming():
    """流式输出示例"""
    print("\n" + "=" * 50)
    print("流式输出示例")
    print("=" * 50)

    agent = create_agent("stream_agent", "c_end")
    await agent.initialize()

    print("流式输出:")
    async for chunk in agent.process_stream(
        message="介绍一下装修流程",
        session_id="session_002",
        user_id="user_002"
    ):
        print(f"  [{chunk.type}] {chunk.data}")

    await agent.shutdown()


async def main():
    """运行所有示例"""
    print("\n" + "=" * 60)
    print("DecoPilot Framework 2.0 使用示例")
    print("=" * 60)

    await example_basic_usage()
    await example_event_driven()
    await example_orchestration()
    await example_learning()
    await example_observability()
    await example_streaming()

    print("\n" + "=" * 60)
    print("所有示例运行完成!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
