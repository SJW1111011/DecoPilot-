"""
数据导入脚本
将各类数据导入到对应的知识库集合中
"""
import os
import sys
import glob
from typing import Optional

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from backend.core.singleton import get_knowledge_base
from backend.crawlers.decoration_crawler import create_sample_decoration_data


def get_project_root():
    """获取项目根目录"""
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def ingest_txt_files(
    kb,
    data_dir: str,
    collection_name: str,
    category: str = "general",
    target_user: str = "both",
):
    """
    导入目录下的所有TXT文件

    Args:
        kb: 知识库实例
        data_dir: 数据目录
        collection_name: 目标集合名称
        category: 分类
        target_user: 目标用户
    """
    txt_files = glob.glob(os.path.join(data_dir, "*.txt"))
    print(f"找到 {len(txt_files)} 个TXT文件")

    for filepath in txt_files:
        filename = os.path.basename(filepath)
        print(f"正在处理: {filename}")

        try:
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()

            result = kb.add_text(
                collection_name=collection_name,
                text=content,
                source=f"local:{filename}",
                category=category,
                target_user=target_user,
                operator="ingest_script",
            )
            print(f"  {result}")
        except Exception as e:
            print(f"  [错误] {e}")


def ingest_pdf_files(
    kb,
    data_dir: str,
    collection_name: str,
    category: str = "general",
    target_user: str = "both",
):
    """
    导入目录下的所有PDF文件

    Args:
        kb: 知识库实例
        data_dir: 数据目录
        collection_name: 目标集合名称
        category: 分类
        target_user: 目标用户
    """
    pdf_files = glob.glob(os.path.join(data_dir, "*.pdf"))
    print(f"找到 {len(pdf_files)} 个PDF文件")

    for filepath in pdf_files:
        filename = os.path.basename(filepath)
        print(f"正在处理: {filename}")

        try:
            result = kb.add_pdf(
                collection_name=collection_name,
                pdf_path=filepath,
                source=f"local:{filename}",
                category=category,
                target_user=target_user,
                operator="ingest_script",
            )
            print(f"  {result}")
        except Exception as e:
            print(f"  [错误] {e}")


def ingest_sample_data(kb):
    """
    导入示例数据

    Args:
        kb: 知识库实例
    """
    print("\n=== 导入示例装修知识 ===")
    sample_data = create_sample_decoration_data()

    for item in sample_data:
        print(f"正在导入: {item['title']}")
        result = kb.add_text(
            collection_name="decoration_general",
            text=f"# {item['title']}\n\n{item['content']}",
            source=item["source"],
            category=item["category"],
            target_user="both",
            keywords=item.get("keywords", []),
            operator="sample_data",
        )
        print(f"  {result}")


def ingest_c_end_data(kb):
    """
    导入C端专用数据（补贴政策等）

    Args:
        kb: 知识库实例
    """
    print("\n=== 导入C端专用数据 ===")

    c_end_data = [
        {
            "title": "洞居平台补贴政策说明",
            "content": """洞居平台为业主提供装修补贴，帮助您节省装修开支。

补贴规则：
1. 家具类：订单金额的5%，最高2000元
2. 建材类：订单金额的3%，最高1500元
3. 家电类：订单金额的4%，最高1000元
4. 软装类：订单金额的6%，最高800元

领取流程：
1. 在洞居平台选择商家并下单
2. 完成支付后，补贴自动计入账户
3. 订单完成后，补贴可提现或抵扣

注意事项：
- 补贴仅限平台内交易
- 退款订单补贴将收回
- 每月补贴上限5000元""",
            "category": "subsidy",
            "keywords": ["补贴", "政策", "领取流程"],
        },
        {
            "title": "洞居平台使用指南",
            "content": """欢迎使用洞居平台，这里是您的装修好帮手。

平台功能：
1. 商家浏览：按品类、评分、距离筛选商家
2. 在线咨询：与商家实时沟通
3. 补贴领取：享受平台专属补贴
4. 订单管理：查看订单状态和进度

逛店指南：
1. 提前预约：节省等待时间
2. 带好户型图：方便商家报价
3. 多家比较：货比三家不吃亏
4. 记录报价：便于后续对比""",
            "category": "guide",
            "keywords": ["使用指南", "逛店", "平台功能"],
        },
    ]

    for item in c_end_data:
        print(f"正在导入: {item['title']}")
        result = kb.add_text(
            collection_name="dongju_c_end",
            text=f"# {item['title']}\n\n{item['content']}",
            source="local",
            category=item["category"],
            target_user="c_end",
            keywords=item.get("keywords", []),
            operator="ingest_script",
        )
        print(f"  {result}")


def ingest_b_end_data(kb):
    """
    导入B端专用数据（商家指南等）

    Args:
        kb: 知识库实例
    """
    print("\n=== 导入B端专用数据 ===")

    b_end_data = [
        {
            "title": "洞居平台商家入驻指南",
            "content": """欢迎入驻洞居平台，开启您的线上获客之旅。

入驻条件：
1. 具有合法经营资质
2. 实体店铺正常运营
3. 产品质量符合国家标准
4. 具备售后服务能力

入驻流程：
1. 提交入驻申请
2. 上传资质材料
3. 平台审核（3-5个工作日）
4. 签署合作协议
5. 开通店铺，开始运营

费用说明：
- 入驻保证金：5000元（可退）
- 平台服务费：成交金额的3%
- 推广费用：按效果付费""",
            "category": "onboarding",
            "keywords": ["入驻", "流程", "费用"],
        },
        {
            "title": "商家数据产品介绍",
            "content": """洞居平台为商家提供多种数据产品，助力精准获客。

数据产品：
1. 选品推荐
   - 基于市场趋势推荐热销品类
   - 分析竞品定价策略
   - 预测季节性需求

2. 客户画像
   - 了解目标客户特征
   - 分析消费偏好
   - 精准定向投放

3. 经营分析
   - 店铺流量分析
   - 转化率统计
   - ROI评估报告

使用方法：
登录商家后台 -> 数据中心 -> 选择对应产品""",
            "category": "data_product",
            "keywords": ["数据产品", "选品", "客户画像"],
        },
    ]

    for item in b_end_data:
        print(f"正在导入: {item['title']}")
        result = kb.add_text(
            collection_name="dongju_b_end",
            text=f"# {item['title']}\n\n{item['content']}",
            source="local",
            category=item["category"],
            target_user="b_end",
            keywords=item.get("keywords", []),
            operator="ingest_script",
        )
        print(f"  {result}")


def ingest_all(data_dir: str = "./data"):
    """
    执行全量数据导入

    Args:
        data_dir: 数据目录
    """
    print("=" * 50)
    print("DecoPilot 数据导入脚本")
    print("=" * 50)

    kb = get_knowledge_base()

    # 显示当前集合状态
    print("\n当前集合状态:")
    for stat in kb.get_all_stats():
        print(f"  {stat['collection_name']}: {stat.get('document_count', 0)} 个文档")

    # 导入现有数据目录的文件
    if os.path.exists(data_dir):
        print(f"\n=== 导入 {data_dir} 目录文件 ===")
        ingest_txt_files(kb, data_dir, "decoration_general", "decoration", "both")
        ingest_pdf_files(kb, data_dir, "decoration_general", "decoration", "both")

    # 导入C端数据目录
    c_end_dir = os.path.join(data_dir, "c_end")
    if os.path.exists(c_end_dir):
        print(f"\n=== 导入 {c_end_dir} 目录文件 ===")
        ingest_txt_files(kb, c_end_dir, "dongju_c_end", "guide", "c_end")
        ingest_pdf_files(kb, c_end_dir, "dongju_c_end", "guide", "c_end")

    # 导入B端数据目录
    b_end_dir = os.path.join(data_dir, "b_end")
    if os.path.exists(b_end_dir):
        print(f"\n=== 导入 {b_end_dir} 目录文件 ===")
        ingest_txt_files(kb, b_end_dir, "dongju_b_end", "guide", "b_end")
        ingest_pdf_files(kb, b_end_dir, "dongju_b_end", "guide", "b_end")

    # 导入示例数据
    ingest_sample_data(kb)

    # 导入C端数据
    ingest_c_end_data(kb)

    # 导入B端数据
    ingest_b_end_data(kb)

    # 显示导入后状态
    print("\n" + "=" * 50)
    print("导入完成，当前集合状态:")
    for stat in kb.get_all_stats():
        print(f"  {stat['collection_name']}: {stat.get('document_count', 0)} 个文档")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="DecoPilot 数据导入脚本")
    parser.add_argument("--data-dir", default="./data", help="数据目录路径")
    args = parser.parse_args()

    ingest_all(args.data_dir)
