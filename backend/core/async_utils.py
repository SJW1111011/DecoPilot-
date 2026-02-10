"""
异步工具模块
提供异步执行、线程池管理和并发控制
"""
import asyncio
import functools
import time
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor
from typing import Any, Callable, Coroutine, Optional, TypeVar, ParamSpec
from contextlib import asynccontextmanager
import threading

try:
    from backend.core.logging_config import get_logger
    logger = get_logger("async_utils")
except ImportError:
    import logging
    logger = logging.getLogger(__name__)

T = TypeVar("T")
P = ParamSpec("P")


class AsyncExecutor:
    """
    异步执行器

    管理线程池和进程池，提供同步函数的异步执行能力
    """

    _instance: Optional["AsyncExecutor"] = None
    _lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, max_workers: int = 10, process_workers: int = 4):
        if hasattr(self, "_initialized"):
            return
        self._initialized = True

        self._thread_pool = ThreadPoolExecutor(
            max_workers=max_workers,
            thread_name_prefix="async_worker"
        )
        self._process_pool: Optional[ProcessPoolExecutor] = None
        self._process_workers = process_workers

        # 统计信息
        self._task_count = 0
        self._total_time = 0.0
        self._error_count = 0
        self._stats_lock = threading.Lock()

    @property
    def process_pool(self) -> ProcessPoolExecutor:
        """延迟初始化进程池"""
        if self._process_pool is None:
            self._process_pool = ProcessPoolExecutor(
                max_workers=self._process_workers
            )
        return self._process_pool

    async def run_in_thread(
        self,
        func: Callable[P, T],
        *args: P.args,
        **kwargs: P.kwargs
    ) -> T:
        """
        在线程池中执行同步函数

        Args:
            func: 要执行的同步函数
            *args: 位置参数
            **kwargs: 关键字参数

        Returns:
            函数执行结果
        """
        loop = asyncio.get_event_loop()
        start_time = time.time()

        try:
            if kwargs:
                func_with_kwargs = functools.partial(func, **kwargs)
                result = await loop.run_in_executor(
                    self._thread_pool,
                    func_with_kwargs,
                    *args
                )
            else:
                result = await loop.run_in_executor(
                    self._thread_pool,
                    func,
                    *args
                )

            self._record_success(time.time() - start_time)
            return result

        except Exception as e:
            self._record_error()
            logger.error(f"线程池执行失败: {func.__name__}", extra={"error": str(e)})
            raise

    async def run_in_process(
        self,
        func: Callable[P, T],
        *args: P.args
    ) -> T:
        """
        在进程池中执行CPU密集型函数

        注意：func 必须是可序列化的（pickle）

        Args:
            func: 要执行的函数
            *args: 位置参数

        Returns:
            函数执行结果
        """
        loop = asyncio.get_event_loop()
        start_time = time.time()

        try:
            result = await loop.run_in_executor(
                self.process_pool,
                func,
                *args
            )
            self._record_success(time.time() - start_time)
            return result

        except Exception as e:
            self._record_error()
            logger.error(f"进程池执行失败: {func.__name__}", extra={"error": str(e)})
            raise

    def _record_success(self, duration: float):
        with self._stats_lock:
            self._task_count += 1
            self._total_time += duration

    def _record_error(self):
        with self._stats_lock:
            self._error_count += 1

    def get_stats(self) -> dict:
        """获取统计信息"""
        with self._stats_lock:
            return {
                "task_count": self._task_count,
                "total_time": self._total_time,
                "avg_time": self._total_time / self._task_count if self._task_count > 0 else 0,
                "error_count": self._error_count,
                "error_rate": self._error_count / self._task_count if self._task_count > 0 else 0,
            }

    def shutdown(self, wait: bool = True):
        """关闭执行器"""
        self._thread_pool.shutdown(wait=wait)
        if self._process_pool:
            self._process_pool.shutdown(wait=wait)


def async_wrap(func: Callable[P, T]) -> Callable[P, Coroutine[Any, Any, T]]:
    """
    装饰器：将同步函数包装为异步函数

    使用示例:
        @async_wrap
        def blocking_operation(x):
            time.sleep(1)
            return x * 2

        result = await blocking_operation(5)
    """
    @functools.wraps(func)
    async def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
        executor = get_async_executor()
        return await executor.run_in_thread(func, *args, **kwargs)
    return wrapper


def cpu_bound(func: Callable[P, T]) -> Callable[P, Coroutine[Any, Any, T]]:
    """
    装饰器：将CPU密集型函数包装为异步函数（使用进程池）

    使用示例:
        @cpu_bound
        def heavy_computation(data):
            # CPU密集型计算
            return result

        result = await heavy_computation(data)
    """
    @functools.wraps(func)
    async def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
        executor = get_async_executor()
        if kwargs:
            func_with_kwargs = functools.partial(func, **kwargs)
            return await executor.run_in_process(func_with_kwargs, *args)
        return await executor.run_in_process(func, *args)
    return wrapper


class AsyncSemaphore:
    """
    异步信号量

    用于限制并发数量
    """

    def __init__(self, value: int = 10):
        self._semaphore = asyncio.Semaphore(value)
        self._waiting = 0
        self._lock = asyncio.Lock()

    @asynccontextmanager
    async def acquire(self):
        """获取信号量"""
        async with self._lock:
            self._waiting += 1

        try:
            async with self._semaphore:
                async with self._lock:
                    self._waiting -= 1
                yield
        except Exception:
            async with self._lock:
                self._waiting -= 1
            raise

    @property
    def waiting(self) -> int:
        """等待中的任务数"""
        return self._waiting


class AsyncRateLimiter:
    """
    异步速率限制器

    基于令牌桶算法
    """

    def __init__(self, rate: float, burst: int = 1):
        """
        Args:
            rate: 每秒允许的请求数
            burst: 突发容量
        """
        self._rate = rate
        self._burst = burst
        self._tokens = float(burst)
        self._last_update = time.time()
        self._lock = asyncio.Lock()

    async def acquire(self, tokens: int = 1) -> float:
        """
        获取令牌

        Args:
            tokens: 需要的令牌数

        Returns:
            等待时间（秒）
        """
        async with self._lock:
            now = time.time()
            elapsed = now - self._last_update
            self._tokens = min(self._burst, self._tokens + elapsed * self._rate)
            self._last_update = now

            if self._tokens >= tokens:
                self._tokens -= tokens
                return 0.0

            wait_time = (tokens - self._tokens) / self._rate
            await asyncio.sleep(wait_time)
            self._tokens = 0
            self._last_update = time.time()
            return wait_time


async def gather_with_concurrency(
    n: int,
    *coros: Coroutine
) -> list:
    """
    带并发限制的 gather

    Args:
        n: 最大并发数
        *coros: 协程列表

    Returns:
        结果列表
    """
    semaphore = asyncio.Semaphore(n)

    async def sem_coro(coro):
        async with semaphore:
            return await coro

    return await asyncio.gather(*(sem_coro(c) for c in coros))


async def timeout_wrapper(
    coro: Coroutine[Any, Any, T],
    timeout: float,
    default: T = None
) -> T:
    """
    带超时的协程执行

    Args:
        coro: 协程
        timeout: 超时时间（秒）
        default: 超时时返回的默认值

    Returns:
        协程结果或默认值
    """
    try:
        return await asyncio.wait_for(coro, timeout=timeout)
    except asyncio.TimeoutError:
        logger.warning(f"协程执行超时: {timeout}s")
        return default


async def retry_async(
    coro_func: Callable[[], Coroutine[Any, Any, T]],
    max_retries: int = 3,
    delay: float = 1.0,
    backoff: float = 2.0,
    exceptions: tuple = (Exception,)
) -> T:
    """
    异步重试

    Args:
        coro_func: 返回协程的函数
        max_retries: 最大重试次数
        delay: 初始延迟（秒）
        backoff: 退避系数
        exceptions: 需要重试的异常类型

    Returns:
        协程结果
    """
    last_exception = None
    current_delay = delay

    for attempt in range(max_retries + 1):
        try:
            return await coro_func()
        except exceptions as e:
            last_exception = e
            if attempt < max_retries:
                logger.warning(f"重试 {attempt + 1}/{max_retries}: {e}")
                await asyncio.sleep(current_delay)
                current_delay *= backoff
            else:
                logger.error(f"重试耗尽: {e}")

    raise last_exception


# 全局异步执行器
_async_executor: Optional[AsyncExecutor] = None
_executor_lock = threading.Lock()


def get_async_executor() -> AsyncExecutor:
    """获取全局异步执行器"""
    global _async_executor
    if _async_executor is None:
        with _executor_lock:
            if _async_executor is None:
                _async_executor = AsyncExecutor()
    return _async_executor
