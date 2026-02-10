"""
基础爬虫类
提供爬虫的通用功能
"""
import os
import sys
import time
import random
import asyncio
from abc import ABC, abstractmethod
from typing import Optional, List, Dict
from urllib.parse import urljoin, urlparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

try:
    import aiohttp
    from bs4 import BeautifulSoup
    CRAWLER_DEPS_AVAILABLE = True
except ImportError:
    CRAWLER_DEPS_AVAILABLE = False


class BaseCrawler(ABC):
    """爬虫基类"""

    def __init__(
        self,
        base_url: str,
        delay_range: tuple = (1, 3),
        max_retries: int = 3,
        timeout: int = 30,
    ):
        """
        初始化爬虫

        Args:
            base_url: 基础URL
            delay_range: 请求间隔范围（秒）
            max_retries: 最大重试次数
            timeout: 请求超时时间（秒）
        """
        if not CRAWLER_DEPS_AVAILABLE:
            raise ImportError("爬虫依赖未安装，请安装: pip install aiohttp beautifulsoup4")

        self.base_url = base_url
        self.delay_range = delay_range
        self.max_retries = max_retries
        self.timeout = timeout
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        }
        self.visited_urls = set()
        self.results = []

    def _random_delay(self):
        """随机延迟，避免请求过快"""
        delay = random.uniform(*self.delay_range)
        time.sleep(delay)

    async def _fetch_page(self, url: str, session: aiohttp.ClientSession) -> Optional[str]:
        """
        获取页面内容

        Args:
            url: 页面URL
            session: aiohttp会话

        Returns:
            页面HTML内容，失败返回None
        """
        for attempt in range(self.max_retries):
            try:
                async with session.get(
                    url,
                    headers=self.headers,
                    timeout=aiohttp.ClientTimeout(total=self.timeout)
                ) as response:
                    if response.status == 200:
                        return await response.text()
                    elif response.status == 429:
                        # 请求过多，增加延迟
                        await asyncio.sleep(self.delay_range[1] * 2)
                    else:
                        print(f"请求失败: {url}, 状态码: {response.status}")
            except Exception as e:
                print(f"请求异常: {url}, 错误: {e}")
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(self.delay_range[1])

        return None

    def _parse_html(self, html: str) -> BeautifulSoup:
        """解析HTML"""
        return BeautifulSoup(html, "html.parser")

    def _extract_text(self, soup: BeautifulSoup, selector: str) -> str:
        """提取文本内容"""
        elements = soup.select(selector)
        return "\n".join(el.get_text(strip=True) for el in elements)

    def _extract_links(self, soup: BeautifulSoup, selector: str = "a") -> List[str]:
        """提取链接"""
        links = []
        for a in soup.select(selector):
            href = a.get("href")
            if href:
                full_url = urljoin(self.base_url, href)
                if self._is_valid_url(full_url):
                    links.append(full_url)
        return links

    def _is_valid_url(self, url: str) -> bool:
        """检查URL是否有效"""
        try:
            parsed = urlparse(url)
            return parsed.scheme in ("http", "https") and bool(parsed.netloc)
        except Exception:
            return False

    @abstractmethod
    async def crawl(self) -> List[Dict]:
        """
        执行爬取，子类必须实现

        Returns:
            爬取结果列表
        """
        pass

    @abstractmethod
    def parse_page(self, html: str, url: str) -> Optional[Dict]:
        """
        解析页面，子类必须实现

        Args:
            html: 页面HTML
            url: 页面URL

        Returns:
            解析结果字典
        """
        pass
