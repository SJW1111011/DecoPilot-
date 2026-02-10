"""
装修知识爬虫
爬取装修相关知识文章
"""
import os
import sys
import asyncio
from typing import Optional, List, Dict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

try:
    import aiohttp
    from bs4 import BeautifulSoup
    CRAWLER_DEPS_AVAILABLE = True
except ImportError:
    CRAWLER_DEPS_AVAILABLE = False

from backend.crawlers.base_crawler import BaseCrawler


class DecorationCrawler(BaseCrawler):
    """装修知识爬虫"""

    def __init__(
        self,
        base_url: str = "https://example.com",  # 替换为实际的装修知识网站
        max_pages: int = 50,
        **kwargs
    ):
        """
        初始化装修知识爬虫

        Args:
            base_url: 目标网站URL
            max_pages: 最大爬取页数
        """
        super().__init__(base_url, **kwargs)
        self.max_pages = max_pages
        self.categories = [
            "装修风格",
            "装修材料",
            "施工工艺",
            "装修预算",
            "装修避坑",
        ]

    async def crawl(self) -> List[Dict]:
        """
        执行爬取

        Returns:
            爬取结果列表
        """
        if not CRAWLER_DEPS_AVAILABLE:
            print("爬虫依赖未安装")
            return []

        results = []
        async with aiohttp.ClientSession() as session:
            # 这里是示例逻辑，实际需要根据目标网站调整
            for category in self.categories:
                print(f"正在爬取分类: {category}")
                # 构造分类URL（示例）
                category_url = f"{self.base_url}/category/{category}"

                html = await self._fetch_page(category_url, session)
                if html:
                    # 解析文章列表
                    soup = self._parse_html(html)
                    article_links = self._extract_links(soup, "a.article-link")

                    for link in article_links[:self.max_pages // len(self.categories)]:
                        if link in self.visited_urls:
                            continue

                        self.visited_urls.add(link)
                        self._random_delay()

                        article_html = await self._fetch_page(link, session)
                        if article_html:
                            result = self.parse_page(article_html, link)
                            if result:
                                result["category"] = category
                                results.append(result)

        self.results = results
        return results

    def parse_page(self, html: str, url: str) -> Optional[Dict]:
        """
        解析文章页面

        Args:
            html: 页面HTML
            url: 页面URL

        Returns:
            解析结果
        """
        try:
            soup = self._parse_html(html)

            # 提取标题（根据实际网站调整选择器）
            title_el = soup.select_one("h1.article-title, h1, .title")
            title = title_el.get_text(strip=True) if title_el else "未知标题"

            # 提取正文
            content_el = soup.select_one("article, .article-content, .content, main")
            if content_el:
                # 移除脚本和样式
                for tag in content_el.select("script, style, nav, footer, .ad"):
                    tag.decompose()
                content = content_el.get_text(separator="\n", strip=True)
            else:
                content = ""

            if not content or len(content) < 100:
                return None

            # 提取关键词
            keywords = []
            meta_keywords = soup.select_one('meta[name="keywords"]')
            if meta_keywords:
                keywords = [k.strip() for k in meta_keywords.get("content", "").split(",")]

            return {
                "title": title,
                "content": content,
                "url": url,
                "keywords": keywords,
                "source": "crawled",
            }
        except Exception as e:
            print(f"解析失败: {url}, 错误: {e}")
            return None

    def save_results(self, output_dir: str = "./crawled_data"):
        """
        保存爬取结果到文件

        Args:
            output_dir: 输出目录
        """
        os.makedirs(output_dir, exist_ok=True)

        for i, result in enumerate(self.results):
            filename = f"{output_dir}/article_{i+1}.txt"
            with open(filename, "w", encoding="utf-8") as f:
                f.write(f"标题: {result['title']}\n")
                f.write(f"分类: {result.get('category', '未分类')}\n")
                f.write(f"来源: {result['url']}\n")
                f.write(f"关键词: {', '.join(result.get('keywords', []))}\n")
                f.write("-" * 50 + "\n")
                f.write(result["content"])

        print(f"已保存 {len(self.results)} 篇文章到 {output_dir}")


# 示例：从本地文件创建装修知识
def create_sample_decoration_data() -> List[Dict]:
    """
    创建示例装修知识数据

    Returns:
        装修知识数据列表
    """
    return [
        {
            "title": "现代简约风格装修指南",
            "content": """现代简约风格是当下最流行的装修风格之一，以简洁、实用为主要特点。

设计要点：
1. 色彩搭配：以白色、灰色、米色为主色调，搭配少量亮色点缀
2. 线条设计：强调直线条，减少繁复的装饰
3. 材质选择：玻璃、金属、木材等现代材质
4. 空间布局：开放式设计，注重采光和通风

适合人群：年轻人、追求简洁生活的人群
预算参考：中等偏上""",
            "category": "装修风格",
            "keywords": ["现代简约", "装修风格", "设计要点"],
            "source": "local",
        },
        {
            "title": "装修材料选购避坑指南",
            "content": """装修材料的选择直接影响装修质量和居住体验，以下是常见的选购陷阱和建议。

地板选购：
1. 实木地板：注意含水率，北方选择含水率8-10%
2. 复合地板：查看环保等级，至少E1级
3. 瓷砖：检查平整度和吸水率

墙面材料：
1. 乳胶漆：选择大品牌，注意VOC含量
2. 墙纸：注意防潮性能
3. 硅藻泥：真假辨别，看吸水性

避坑要点：
- 不要贪图便宜，一分钱一分货
- 索要质检报告和环保证书
- 多比较几家，了解市场价格""",
            "category": "装修材料",
            "keywords": ["材料选购", "避坑", "地板", "墙面"],
            "source": "local",
        },
        {
            "title": "水电改造注意事项",
            "content": """水电改造是装修中最重要的隐蔽工程，一旦出问题维修成本很高。

电路改造：
1. 强弱电分开走线，间距至少30cm
2. 插座数量要充足，厨房至少6个
3. 使用国标电线，2.5平方以上
4. 开关高度1.3-1.4米，插座高度30cm

水路改造：
1. 冷热水管分开，间距15cm
2. 使用PPR管材，注意壁厚
3. 水管走顶不走地，便于维修
4. 做好打压测试，0.8MPa保持30分钟

验收要点：
- 拍照留存管线走向
- 测试所有开关插座
- 检查水压和排水""",
            "category": "施工工艺",
            "keywords": ["水电改造", "隐蔽工程", "电路", "水路"],
            "source": "local",
        },
    ]


if __name__ == "__main__":
    # 测试示例数据生成
    data = create_sample_decoration_data()
    for item in data:
        print(f"标题: {item['title']}")
        print(f"分类: {item['category']}")
        print("-" * 30)
