"""
装修领域知识图谱

提供结构化的装修知识，支持实体关系查询和复杂推理
"""
import json
import hashlib
from typing import Any, Dict, List, Optional, Set, Tuple
from dataclasses import dataclass, field
from enum import Enum
import threading

from backend.core.logging_config import get_logger

logger = get_logger("knowledge_graph")


class EntityType(str, Enum):
    """实体类型"""
    # 基础类型
    MATERIAL = "material"       # 材料
    STYLE = "style"             # 风格
    SPACE = "space"             # 空间
    BRAND = "brand"             # 品牌
    MERCHANT = "merchant"       # 商家
    PROCESS = "process"         # 工序
    TOOL = "tool"               # 工具
    PROBLEM = "problem"         # 问题
    SOLUTION = "solution"       # 解决方案
    TREND = "trend"             # 行业趋势
    CHANNEL = "channel"         # 销售渠道
    TERMINOLOGY = "terminology" # 行业术语

    # 产品品类 - 基础建材
    CEMENT = "cement"           # 水泥类
    BRICK = "brick"             # 砖石砌块
    STEEL = "steel"             # 钢材
    WOOD = "wood"               # 木材及人造板

    # 产品品类 - 墙面材料
    PAINT = "paint"             # 涂料
    WALLPAPER = "wallpaper"     # 墙纸墙布
    WALL_TILE = "wall_tile"     # 墙砖
    WALL_PANEL = "wall_panel"   # 护墙板

    # 产品品类 - 地面材料
    FLOOR_TILE = "floor_tile"   # 瓷砖
    WOOD_FLOOR = "wood_floor"   # 木地板
    STONE = "stone"             # 石材
    ELASTIC_FLOOR = "elastic_floor"  # 弹性地板
    CARPET = "carpet"           # 地毯

    # 产品品类 - 吊顶材料
    CEILING = "ceiling"         # 吊顶

    # 产品品类 - 门窗系统
    DOOR = "door"               # 门
    WINDOW = "window"           # 窗户
    HARDWARE = "hardware"       # 五金配件

    # 产品品类 - 厨房系统
    CABINET = "cabinet"         # 橱柜
    KITCHEN_APPLIANCE = "kitchen_appliance"  # 厨房电器
    SINK = "sink"               # 水槽

    # 产品品类 - 卫浴系统
    TOILET = "toilet"           # 马桶
    BATHROOM_CABINET = "bathroom_cabinet"  # 浴室柜
    SHOWER = "shower"           # 淋浴系统
    BATHROOM_HARDWARE = "bathroom_hardware"  # 卫浴五金

    # 产品品类 - 定制家具
    WARDROBE = "wardrobe"       # 衣柜
    CUSTOM_CABINET = "custom_cabinet"  # 定制柜体

    # 产品品类 - 成品家具
    SOFA = "sofa"               # 沙发
    TABLE = "table"             # 桌子
    BED = "bed"                 # 床
    MATTRESS = "mattress"       # 床垫
    CHAIR = "chair"             # 椅子
    CHILDREN_FURNITURE = "children_furniture"  # 儿童家具
    STORAGE = "storage"         # 收纳家具

    # 产品品类 - 水电暖通
    ELECTRICAL = "electrical"   # 电气系统
    PLUMBING = "plumbing"       # 给排水
    HVAC = "hvac"               # 暖通系统

    # 产品品类 - 灯具照明
    LIGHTING = "lighting"       # 灯具
    LIGHT_SOURCE = "light_source"  # 光源

    # 产品品类 - 软装配饰
    CURTAIN = "curtain"         # 窗帘
    BEDDING = "bedding"         # 床品布艺
    DECORATION = "decoration"   # 装饰摆件
    PLANT = "plant"             # 绿植花艺

    # 产品品类 - 智能家居
    SMART_HOME = "smart_home"   # 智能家居设备
    SMART_PROTOCOL = "smart_protocol"  # 智能协议

    # 产品品类 - 热水系统
    WATER_HEATER = "water_heater"  # 热水器

    # 参数/规格
    SPECIFICATION = "specification"  # 规格参数
    STANDARD = "standard"       # 标准等级
    LIGHTING_PARAM = "lighting_param"  # 照明参数

    # 区域
    REGION = "region"           # 区域市场


class RelationType(str, Enum):
    """关系类型"""
    SUITABLE_FOR = "适用于"           # 材料适用于空间
    BELONGS_TO_STYLE = "属于风格"     # 材料/家具属于风格
    PRICE_RANGE = "价格区间"          # 实体的价格区间
    PRODUCED_BY = "生产商"            # 材料的生产商
    SOLD_BY = "销售商"                # 材料的销售商
    REQUIRES = "需要"                 # 工序需要材料/工具
    FOLLOWS = "后续是"                # 工序的后续工序
    SOLVES = "解决"                   # 解决方案解决问题
    CAUSES = "导致"                   # 问题导致问题
    COMPATIBLE_WITH = "兼容"          # 材料/风格兼容
    ALTERNATIVE_TO = "可替代"         # 材料可替代
    PART_OF = "属于"                  # 子类属于父类
    HAS_SUBCATEGORY = "包含子类"      # 父类包含子类
    HAS_SPECIFICATION = "规格参数"    # 产品的规格参数
    HAS_STANDARD = "符合标准"         # 产品符合的标准
    MATCHES_BUDGET = "匹配预算"       # 材料匹配预算等级
    RECOMMENDED_FOR = "推荐用于"      # 推荐用于特定场景
    CONFLICTS_WITH = "冲突"           # 材料/风格冲突
    PAIRS_WITH = "搭配"               # 材料/风格搭配
    INSTALLED_BY = "安装方式"         # 安装方式
    MAINTAINED_BY = "维护方式"        # 维护方式
    HAS_FEATURE = "具有特性"          # 产品特性
    BRAND_OF = "品牌归属"             # 品牌归属关系
    HAS_PARAM = "参数指标"            # 产品参数指标
    SUITABLE_SPACE = "适用空间"       # 适用的空间类型
    BUDGET_LEVEL = "预算等级"         # 预算等级关系
    INSTALL_METHOD = "安装方式"       # 安装方式
    MAINTAIN_METHOD = "保养方式"      # 保养方式
    CONNECT_WITH = "连接协议"         # 智能设备连接协议


@dataclass
class Entity:
    """知识图谱实体"""
    id: str
    name: str
    entity_type: EntityType
    properties: Dict[str, Any] = field(default_factory=dict)
    aliases: List[str] = field(default_factory=list)  # 别名

    def __hash__(self):
        return hash(self.id)


@dataclass
class Relation:
    """知识图谱关系"""
    source_id: str
    target_id: str
    relation_type: RelationType
    weight: float = 1.0
    properties: Dict[str, Any] = field(default_factory=dict)


class DecorationKnowledgeGraph:
    """
    装修领域知识图谱

    包含装修相关的实体和关系，支持：
    - 材料推荐
    - 风格匹配
    - 问题诊断
    - 工序指导
    """

    # 预定义的实体数据
    PREDEFINED_ENTITIES = {
        # ==================== 一、基础建材 ====================
        # 水泥类
        EntityType.CEMENT: [
            {"name": "普通硅酸盐水泥", "properties": {
                "code": "P·O", "grades": ["32.5", "42.5", "52.5"],
                "initial_setting": "≥45分钟", "final_setting": "≤10小时"
            }, "aliases": ["硅酸盐水泥", "普通水泥"]},
            {"name": "矿渣硅酸盐水泥", "properties": {"code": "P·S"}, "aliases": []},
            {"name": "白水泥", "properties": {"usage": "装饰用", "type": "特种水泥"}, "aliases": []},
            {"name": "快硬水泥", "properties": {"usage": "抢修工程", "type": "特种水泥"}, "aliases": []},
            {"name": "瓷砖胶", "properties": {"grades": ["C1", "C2"], "category": "砂浆类"}, "aliases": ["瓷砖粘结剂"]},
            {"name": "美缝剂", "properties": {"category": "砂浆类"}, "aliases": ["填缝剂"]},
            {"name": "自流平砂浆", "properties": {"category": "砂浆类"}, "aliases": ["自流平"]},
        ],

        # 砖石砌块
        EntityType.BRICK: [
            {"name": "烧结普通砖", "properties": {
                "grades": ["MU30", "MU25", "MU20", "MU15", "MU10"],
                "size": "240×115×53mm"
            }, "aliases": ["红砖"]},
            {"name": "加气混凝土砌块", "properties": {
                "density": "400-700kg/m³", "size": "600×200×100/150/200mm",
                "features": "保温隔热性能好"
            }, "aliases": ["ALC砌块", "加气块"]},
            {"name": "轻钢龙骨石膏板隔墙", "properties": {"category": "隔墙板"}, "aliases": ["石膏板隔墙"]},
            {"name": "GRC轻质隔墙板", "properties": {"category": "隔墙板"}, "aliases": []},
        ],

        # 钢材
        EntityType.STEEL: [
            {"name": "螺纹钢", "properties": {
                "grades": ["HRB335", "HRB400", "HRB500"],
                "diameters": "6/8/10/12/14/16/18/20/22/25/28/32mm",
                "usage": "混凝土配筋"
            }, "aliases": ["钢筋"]},
            {"name": "角钢", "properties": {"types": ["等边", "不等边"], "category": "型钢"}, "aliases": []},
            {"name": "槽钢", "properties": {"category": "型钢"}, "aliases": []},
            {"name": "H型钢", "properties": {"category": "型钢"}, "aliases": ["工字钢"]},
            {"name": "镀锌钢板", "properties": {"category": "板材"}, "aliases": []},
            {"name": "不锈钢管", "properties": {"category": "管材"}, "aliases": []},
        ],

        # 木材及人造板
        EntityType.WOOD: [
            {"name": "松木", "properties": {
                "types": ["樟子松", "落叶松", "辐射松"], "category": "针叶材"
            }, "aliases": []},
            {"name": "橡木", "properties": {
                "types": ["白橡", "红橡"], "category": "阔叶材", "origin": "进口"
            }, "aliases": ["栎木"]},
            {"name": "胡桃木", "properties": {
                "types": ["黑胡桃", "核桃木"], "category": "阔叶材"
            }, "aliases": ["黑胡桃"]},
            {"name": "胶合板", "properties": {
                "layers": "3/5/7/9/11/13层", "thickness": "3/5/9/12/15/18/25mm",
                "base": "杨木/桉木/松木"
            }, "aliases": ["多层板"]},
            {"name": "刨花板", "properties": {
                "types": ["普通刨花板", "定向刨花板", "均质刨花板"]
            }, "aliases": ["颗粒板"]},
            {"name": "欧松板", "properties": {
                "code": "OSB", "category": "定向刨花板", "env_grade": "ENF"
            }, "aliases": ["OSB板"]},
            {"name": "密度板", "properties": {
                "types": {"HDF": ">880kg/m³", "MDF": "650-880kg/m³", "LDF": "<650kg/m³"}
            }, "aliases": ["纤维板", "中纤板"]},
            {"name": "生态板", "properties": {
                "base": "多层/颗粒/细木工", "surface": "三聚氰胺浸渍纸"
            }, "aliases": ["免漆板"]},
        ],

        # ==================== 二、墙面材料 ====================
        # 涂料
        EntityType.PAINT: [
            {"name": "乳胶漆", "properties": {
                "category": "内墙涂料",
                "gloss_types": {"哑光": "<10", "丝光": "10-35", "半光": "35-70", "高光": ">70"},
                "functions": ["普通", "抗甲醛", "净味", "儿童漆", "抗菌防霉", "弹性"],
                "voc_standard": "<50g/L", "washability": "≥10000次"
            }, "aliases": ["墙漆", "内墙漆"]},
            {"name": "艺术涂料", "properties": {
                "types": ["肌理漆", "马来漆", "威尼斯灰泥", "金属漆", "裂纹漆"]
            }, "aliases": ["艺术漆"]},
            {"name": "肌理漆", "properties": {
                "category": "艺术涂料",
                "features": ["立体纹理", "手工质感", "个性化"],
                "textures": ["砂岩纹", "树皮纹", "布纹", "石纹"],
                "applications": ["背景墙", "玄关", "餐厅"],
                "construction": "滚涂/批刮/喷涂"
            }, "aliases": ["质感漆", "纹理漆"]},
            {"name": "马来漆", "properties": {
                "category": "艺术涂料",
                "origin": "威尼斯",
                "features": ["光滑如镜", "大理石纹理", "高档质感"],
                "applications": ["高端住宅", "酒店", "会所"],
                "construction": "多遍批刮抛光"
            }, "aliases": ["威尼斯灰泥", "仿大理石漆"]},
            {"name": "金属漆", "properties": {
                "category": "艺术涂料",
                "features": ["金属光泽", "现代感", "轻奢风格"],
                "colors": ["金色", "银色", "铜色", "玫瑰金"],
                "applications": ["背景墙", "吊顶", "装饰线条"]
            }, "aliases": ["金属质感漆"]},
            {"name": "硅藻泥", "properties": {
                "types": ["干粉型", "液态型"],
                "functions": ["调湿", "净化", "防火"]
            }, "aliases": []},
            {"name": "微水泥", "properties": {
                "types": ["水性微水泥", "油性微水泥"], "thickness": "2-3mm"
            }, "aliases": []},
            {"name": "真石漆", "properties": {"category": "外墙涂料"}, "aliases": ["仿石漆"]},
            {"name": "防水涂料", "properties": {
                "types": ["聚氨酯防水涂料", "JS聚合物水泥防水涂料", "K11防水涂料"]
            }, "aliases": []},
            {"name": "木器漆", "properties": {
                "types": ["水性木器漆", "油性木器漆", "UV漆"]
            }, "aliases": []},
            # 辅材
            {"name": "腻子", "properties": {
                "types": ["耐水腻子", "普通腻子", "成品腻子"],
                "application": "墙面找平",
                "thickness": "每遍≤1mm",
                "brands": ["美巢", "德高", "立邦"]
            }, "aliases": ["腻子粉"]},
            {"name": "墙固", "properties": {
                "function": "固化基层/增强附着力",
                "application": "墙面处理",
                "brands": ["美巢", "德高"]
            }, "aliases": ["界面剂"]},
            {"name": "地固", "properties": {
                "function": "固化地面/防止起砂",
                "application": "地面处理"
            }, "aliases": []},
            {"name": "瓷砖胶", "properties": {
                "grades": ["C1普通型", "C2增强型"],
                "application": "瓷砖铺贴",
                "features": ["粘结力强", "薄贴法"],
                "brands": ["德高", "马贝", "雨虹"]
            }, "aliases": ["瓷砖粘结剂"]},
            {"name": "美缝剂", "properties": {
                "types": ["水性美缝剂", "油性美缝剂", "环氧彩砂"],
                "features": ["防水防霉", "易清洁", "装饰性"],
                "colors": "多色可选"
            }, "aliases": ["填缝剂"]},
            {"name": "玻璃胶", "properties": {
                "types": ["酸性玻璃胶", "中性玻璃胶", "结构胶"],
                "application": ["门窗密封", "卫浴安装", "台面收边"],
                "brands": ["道康宁", "瓦克", "白云"]
            }, "aliases": ["硅酮胶"]},
            {"name": "发泡胶", "properties": {
                "function": "填充缝隙/固定门窗",
                "features": ["膨胀填充", "隔音保温"]
            }, "aliases": ["聚氨酯发泡剂"]},
            {"name": "石膏", "properties": {
                "types": ["粉刷石膏", "嵌缝石膏", "粘结石膏"],
                "application": "墙面找平/修补"
            }, "aliases": ["石膏粉"]},
            {"name": "水泥砂浆", "properties": {
                "ratio": "水泥:砂=1:3",
                "application": ["砌墙", "抹灰", "找平"]
            }, "aliases": []},
            {"name": "自流平", "properties": {
                "types": ["水泥基自流平", "石膏基自流平"],
                "thickness": "3-10mm",
                "application": "地面找平",
                "features": ["平整度高", "施工快"]
            }, "aliases": ["自流平砂浆"]},
        ],

        # 墙纸墙布
        EntityType.WALLPAPER: [
            {"name": "壁纸", "properties": {
                "types": ["PVC墙纸", "无纺布墙纸", "纯纸墙纸"],
                "features": ["装饰性强", "花色丰富", "施工简便"],
                "applications": ["客厅", "卧室", "书房"]
            }, "aliases": ["墙纸"]},
            {"name": "PVC墙纸", "properties": {
                "types": ["发泡PVC", "印花PVC", "压纹PVC"]
            }, "aliases": []},
            {"name": "无纺布墙纸", "properties": {
                "types": ["纯无纺布", "无纺布底"]
            }, "aliases": []},
            {"name": "纯纸墙纸", "properties": {
                "types": ["木浆纸", "再生纸"]
            }, "aliases": []},
            {"name": "墙布", "properties": {
                "materials": ["化纤", "棉麻", "丝绸", "混纺"],
                "crafts": ["提花", "刺绣", "印花", "素色"],
                "seamless_height": "2.7-3.1m"
            }, "aliases": ["壁布"]},
        ],

        # 护墙板
        EntityType.WALL_PANEL: [
            {"name": "实木护墙板", "properties": {
                "types": ["原木护墙板", "指接实木"]
            }, "aliases": []},
            {"name": "木饰面护墙板", "properties": {
                "base": "多层板/密度板", "surface": "木皮/科技木"
            }, "aliases": ["木饰面"]},
            {"name": "竹木纤维护墙板", "properties": {
                "types": ["空心结构", "实心结构"]
            }, "aliases": ["竹木纤维板"]},
            {"name": "岩板护墙板", "properties": {
                "thickness": "3/6/9/12mm"
            }, "aliases": []},
            {"name": "软包护墙板", "properties": {
                "types": ["皮革软包", "布艺软包", "硬包"]
            }, "aliases": ["软包", "硬包"]},
            # 装饰线条
            {"name": "石膏线", "properties": {
                "types": ["平线", "角线", "花线", "灯盘"],
                "materials": ["石膏", "PU聚氨酯"],
                "applications": ["顶角", "墙面", "背景墙"],
                "styles": ["欧式", "简欧", "法式"],
                "installation": "粘贴+钉固"
            }, "aliases": ["石膏线条", "顶角线"]},
            {"name": "PU线条", "properties": {
                "material": "聚氨酯",
                "features": ["轻便", "防水", "不开裂", "可弯曲"],
                "types": ["平线", "角线", "雕花线"],
                "applications": ["顶角", "墙面", "门框"]
            }, "aliases": ["PU装饰线", "聚氨酯线条"]},
            {"name": "PS线条", "properties": {
                "material": "聚苯乙烯",
                "features": ["轻便", "价格低", "易安装"],
                "applications": ["顶角", "相框线"]
            }, "aliases": ["PS装饰线"]},
            {"name": "金属装饰条", "properties": {
                "materials": ["不锈钢", "铝合金", "铜"],
                "finishes": ["拉丝", "镜面", "哑光", "玫瑰金"],
                "applications": ["收边", "装饰线", "踢脚线"],
                "types": ["T型条", "U型条", "L型条", "平板条"]
            }, "aliases": ["金属线条", "不锈钢装饰条"]},
            {"name": "阳角条", "properties": {
                "materials": ["PVC", "铝合金", "不锈钢"],
                "applications": ["瓷砖阳角", "墙角保护"],
                "features": ["保护墙角", "美观收边"]
            }, "aliases": ["护角条", "阳角线"]},
            {"name": "收边条", "properties": {
                "types": ["T型收边条", "L型收边条", "U型收边条"],
                "materials": ["铝合金", "不锈钢", "PVC"],
                "applications": ["地板收边", "瓷砖收边", "门槛"]
            }, "aliases": ["压边条", "收口条"]},
            {"name": "墙裙", "properties": {
                "types": ["木质墙裙", "瓷砖墙裙", "护墙板墙裙"],
                "height": "90-120cm",
                "applications": ["走廊", "楼梯间", "餐厅"],
                "features": ["保护墙面", "装饰美观"]
            }, "aliases": ["护墙裙", "墙围"]},
        ],

        # ==================== 三、地面材料 ====================
        # 瓷砖类
        EntityType.FLOOR_TILE: [
            {"name": "抛光砖", "properties": {
                "craft": "通体砖坯体表面打磨抛光",
                "features": ["光亮", "硬度高", "耐磨"],
                "cons": ["防滑性差", "易渗污"],
                "applications": ["客厅", "走廊"]
            }, "aliases": ["玻化砖"]},
            {"name": "抛釉砖", "properties": {
                "craft": "底坯+釉面+抛光",
                "features": ["花色丰富", "仿石纹/木纹效果好"],
                "cons": ["耐磨性不如抛光砖"],
                "applications": ["客厅", "卧室", "餐厅"]
            }, "aliases": ["全抛釉"]},
            {"name": "仿古砖", "properties": {
                "features": ["哑光面", "防滑", "复古质感"],
                "styles": ["地中海", "美式", "田园"],
                "applications": ["阳台", "厨房", "卫生间"]
            }, "aliases": []},
            {"name": "微晶石", "properties": {
                "structure": "底坯+微晶玻璃面层",
                "features": ["光泽度高", "质感奢华"],
                "cons": ["易划伤", "价格高"],
                "applications": ["客厅背景墙", "高端空间"]
            }, "aliases": []},
            {"name": "大理石瓷砖", "properties": {
                "craft": "仿天然大理石纹理",
                "features": ["纹理自然", "性价比高于天然石材"],
                "applications": ["客厅", "玄关", "背景墙"]
            }, "aliases": ["仿大理石瓷砖"]},
            {"name": "木纹砖", "properties": {
                "sizes": ["150×600mm", "150×900mm", "200×1000mm", "200×1200mm"],
                "features": ["仿木纹理", "防水防潮", "易打理"],
                "applications": ["卧室", "客厅", "阳台"]
            }, "aliases": []},
            {"name": "岩板", "properties": {
                "composition": "天然石粉+高温烧制",
                "thickness": ["3mm", "6mm", "9mm", "12mm", "15mm", "20mm"],
                "sizes": ["800×2600mm", "1200×2700mm", "1600×3200mm"],
                "features": ["大规格", "耐高温", "耐刮", "零渗透"],
                "applications": ["地面", "墙面", "台面", "家具面板"],
                "brands": ["德赛斯", "拉米娜", "新濠", "蒙娜丽莎"]
            }, "aliases": ["大板"]},
            {"name": "瓷砖", "properties": {
                "specs": {
                    "常规": ["300×300mm", "300×600mm", "600×600mm", "800×800mm"],
                    "大规格": ["750×1500mm", "900×1800mm", "1200×2400mm"]
                },
                "grades": {
                    "优等品": "无明显缺陷",
                    "一等品": "轻微缺陷",
                    "合格品": "有缺陷但不影响使用"
                },
                "key_params": ["吸水率", "硬度", "耐磨度", "防滑系数"],
                "brands": {
                    "一线": ["马可波罗", "东鹏", "诺贝尔", "蒙娜丽莎", "冠珠"],
                    "二线": ["金意陶", "欧神诺", "萨米特", "宏宇"]
                }
            }, "aliases": ["地砖", "墙砖"]},
            # 特殊工艺瓷砖
            {"name": "负离子瓷砖", "properties": {
                "principle": "添加负离子材料，释放负离子",
                "features": ["净化空气", "抗菌", "除甲醛"],
                "applications": ["卧室", "儿童房", "老人房"]
            }, "aliases": ["健康砖"]},
            {"name": "抗菌瓷砖", "properties": {
                "principle": "釉面添加抗菌剂",
                "features": ["抑制细菌生长", "易清洁"],
                "applications": ["厨房", "卫生间", "医院"]
            }, "aliases": []},
            {"name": "防滑瓷砖", "properties": {
                "coefficient": "R9-R13",
                "features": ["表面纹理增加摩擦力"],
                "applications": ["卫生间", "厨房", "阳台", "户外"]
            }, "aliases": []},
            {"name": "发热瓷砖", "properties": {
                "principle": "内置发热层",
                "features": ["地暖功能", "节能"],
                "power": "100-150W/㎡"
            }, "aliases": ["地暖瓷砖"]},
            {"name": "柔光砖", "properties": {
                "gloss": "20-55°",
                "features": ["光线柔和", "不刺眼", "高级感"],
                "applications": ["客厅", "卧室"]
            }, "aliases": ["柔光大理石瓷砖"]},
            {"name": "通体大理石瓷砖", "properties": {
                "craft": "表里如一，坯体与表面纹理一致",
                "features": ["切割后侧面也有纹理", "更逼真"],
                "applications": ["楼梯", "台面", "倒角处"]
            }, "aliases": []},
            # 马赛克
            {"name": "陶瓷马赛克", "properties": {
                "size": "25×25mm / 48×48mm",
                "features": ["色彩丰富", "耐磨"],
                "applications": ["卫生间", "泳池"]
            }, "aliases": []},
            {"name": "玻璃马赛克", "properties": {
                "features": ["透光", "色彩绚丽", "防水"],
                "applications": ["背景墙", "泳池"]
            }, "aliases": []},
            {"name": "石材马赛克", "properties": {
                "materials": ["大理石", "花岗岩"],
                "features": ["天然纹理", "高档"],
                "applications": ["玄关", "背景墙"]
            }, "aliases": []},
            {"name": "金属马赛克", "properties": {
                "materials": ["不锈钢", "铝合金", "铜"],
                "features": ["现代感", "耐用"],
                "applications": ["背景墙", "厨房"]
            }, "aliases": []},
            # 特殊规格砖
            {"name": "大板瓷砖", "properties": {
                "sizes": ["900×1800mm", "1200×2400mm", "1600×3200mm"],
                "thickness": ["9mm", "12mm", "15mm"],
                "features": ["缝隙少", "大气", "整体感强", "高级感"],
                "applications": ["客厅", "背景墙", "商业空间"],
                "installation": "需专业铺贴，建议干挂或瓷砖胶薄贴",
                "note": "搬运安装需专业设备"
            }, "aliases": ["大规格瓷砖", "大板砖"]},
            {"name": "小白砖", "properties": {
                "size": "75×150mm / 100×200mm",
                "style": ["北欧", "日式", "复古"],
                "铺贴方式": ["工字铺", "人字铺", "鱼骨铺"],
                "applications": ["厨房", "卫生间"]
            }, "aliases": ["地铁砖", "面包砖"]},
            {"name": "六角砖", "properties": {
                "size": "200mm / 260mm边长",
                "features": ["造型独特", "艺术感"],
                "applications": ["玄关", "卫生间", "阳台"]
            }, "aliases": ["异形砖"]},
            {"name": "花砖", "properties": {
                "size": "200×200mm / 300×300mm",
                "style": ["摩洛哥", "地中海", "复古"],
                "applications": ["玄关", "厨房", "阳台"]
            }, "aliases": ["艺术砖"]},
            # 瓷砖铺贴方式
            {"name": "工字铺", "properties": {
                "description": "砖缝错开1/2，类似工字",
                "features": ["经典", "稳重"],
                "applications": ["木纹砖", "长条砖"]
            }, "aliases": ["错缝铺", "二分之一铺"]},
            {"name": "人字铺", "properties": {
                "description": "两块砖呈90度人字形排列",
                "features": ["时尚", "动感"],
                "applications": ["木纹砖", "长条砖"]
            }, "aliases": []},
            {"name": "鱼骨铺", "properties": {
                "description": "砖块呈鱼骨状排列，需45度切割",
                "features": ["高级感", "复杂"],
                "applications": ["木纹砖", "实木地板"]
            }, "aliases": ["鱼骨拼"]},
            {"name": "斜铺", "properties": {
                "description": "砖块45度斜向铺贴",
                "features": ["空间延伸感", "损耗大"],
                "applications": ["小空间", "玄关"]
            }, "aliases": ["菱形铺"]},
            {"name": "正铺", "properties": {
                "description": "砖缝对齐，横平竖直",
                "features": ["简洁", "大气", "损耗小"],
                "applications": ["大规格瓷砖", "客厅"]
            }, "aliases": ["直铺", "对缝铺"]},
            {"name": "混铺", "properties": {
                "description": "不同规格或颜色瓷砖混合铺贴",
                "features": ["个性", "艺术感"],
                "applications": ["玄关", "阳台"]
            }, "aliases": []},
        ],

        # 木地板类
        EntityType.WOOD_FLOOR: [
            {"name": "实木地板", "properties": {
                "materials": ["橡木", "胡桃木", "柚木", "番龙眼", "圆盘豆", "二翅豆"],
                "thickness": "18mm",
                "width": "90-125mm",
                "features": ["天然纹理", "脚感好", "可翻新"],
                "cons": ["价格高", "需保养", "易变形"],
                "env_grade": "天然环保",
                "price_range": "300-1000+元/㎡"
            }, "aliases": ["纯实木地板"]},
            {"name": "三层实木复合地板", "properties": {
                "structure": "表层实木+芯层软木+底层实木",
                "thickness": "14-15mm",
                "surface_thickness": "2-4mm",
                "features": ["稳定性好", "可地暖", "性价比高"],
                "env_grade": "E0/ENF级",
                "brands": ["圣象", "大自然", "德尔", "生活家"],
                "price_range": "200-600元/㎡"
            }, "aliases": ["三层实木"]},
            {"name": "多层实木复合地板", "properties": {
                "structure": "表层实木+多层胶合板",
                "thickness": "12-15mm",
                "surface_thickness": "0.6-2mm",
                "features": ["稳定性最好", "适合地暖"],
                "cons": ["表层薄不可翻新"],
                "env_grade": "E0/E1级",
                "price_range": "150-400元/㎡"
            }, "aliases": ["多层实木"]},
            {"name": "强化复合地板", "properties": {
                "structure": "耐磨层+装饰层+基材层+平衡层",
                "thickness": "8-12mm",
                "耐磨转数": {"家用": "≥4000转", "商用": "≥9000转"},
                "features": ["耐磨", "花色多", "价格低", "易安装"],
                "cons": ["脚感硬", "不可翻新", "怕水"],
                "env_grade": "E1/E0级",
                "price_range": "80-200元/㎡"
            }, "aliases": ["强化地板", "复合地板"]},
            {"name": "木地板", "properties": {
                "install_methods": ["悬浮铺装", "龙骨铺装", "直接粘贴"],
                "accessories": ["踢脚线", "扣条", "防潮膜", "地垫"],
                "maintenance": ["定期打蜡", "避免浸水", "软底家具"]
            }, "aliases": ["地板"]},
        ],

        # 石材类
        EntityType.STONE: [
            {"name": "大理石", "properties": {
                "types": {
                    "白色系": ["爵士白", "雅士白", "鱼肚白", "雪花白"],
                    "灰色系": ["意大利灰", "云多拉灰", "法国灰"],
                    "米黄系": ["西班牙米黄", "莎安娜米黄", "金碧辉煌"],
                    "黑色系": ["黑金花", "银白龙", "古堡灰"]
                },
                "features": ["纹理自然", "质感高档"],
                "cons": ["易渗透", "需养护", "有辐射争议"],
                "applications": ["客厅", "玄关", "背景墙", "台面"]
            }, "aliases": ["天然大理石"]},
            # 进口大理石详细品种
            {"name": "卡拉拉白", "properties": {
                "origin": "意大利",
                "color": "白色带灰色纹理",
                "features": ["经典", "纹理细腻"],
                "price_level": "高端"
            }, "aliases": ["Carrara", "卡拉拉"]},
            {"name": "鱼肚白", "properties": {
                "origin": "意大利",
                "color": "白底金色/灰色纹理",
                "features": ["纹理大气", "奢华"],
                "price_level": "顶级"
            }, "aliases": ["Calacatta", "卡拉卡塔"]},
            {"name": "雪花白", "properties": {
                "origin": "意大利",
                "color": "纯白底细腻纹理",
                "features": ["纯净", "高雅"],
                "price_level": "顶级"
            }, "aliases": ["Statuario"]},
            {"name": "爵士白", "properties": {
                "origin": "希腊",
                "color": "白底灰色纹理",
                "features": ["性价比高", "纹理清晰"],
                "price_level": "中高端"
            }, "aliases": ["Jazz White"]},
            {"name": "雅士白", "properties": {
                "origin": "希腊",
                "color": "白底浅灰纹理",
                "features": ["温润", "百搭"],
                "price_level": "中高端"
            }, "aliases": ["Ariston White"]},
            {"name": "索菲特金", "properties": {
                "origin": "土耳其",
                "color": "米黄底金色纹理",
                "features": ["华丽", "暖色调"],
                "price_level": "高端"
            }, "aliases": ["Sofitel Gold"]},
            {"name": "奥特曼", "properties": {
                "origin": "土耳其",
                "color": "米黄色",
                "features": ["纹理均匀", "温馨"],
                "price_level": "中端"
            }, "aliases": ["Ottoman Beige"]},
            {"name": "世纪米黄", "properties": {
                "origin": "土耳其",
                "color": "浅米黄",
                "features": ["色泽均匀", "经典"],
                "price_level": "中端"
            }, "aliases": []},
            {"name": "波斯灰", "properties": {
                "origin": "伊朗",
                "color": "灰色带白色纹理",
                "features": ["现代感", "高级"],
                "price_level": "高端"
            }, "aliases": ["Persian Grey"]},
            {"name": "蓝色巴西亚", "properties": {
                "origin": "巴西",
                "color": "蓝灰色",
                "features": ["稀有", "独特"],
                "price_level": "顶级"
            }, "aliases": ["Blue Bahia"]},
            {"name": "花岗岩", "properties": {
                "features": ["硬度高", "耐磨", "耐酸碱"],
                "applications": ["室外", "台面", "楼梯"],
                "types": ["中国黑", "芝麻白", "芝麻灰", "黄锈石"]
            }, "aliases": []},
            {"name": "人造石", "properties": {
                "types": ["石英石", "岗石", "水磨石"],
                "features": ["无辐射", "可定制", "接缝少"],
                "applications": ["台面", "地面"]
            }, "aliases": []},
            {"name": "水磨石", "properties": {
                "types": ["现浇水磨石", "预制水磨石"],
                "features": ["复古风格", "可定制图案"],
                "applications": ["地面", "台面"]
            }, "aliases": []},
        ],

        # 弹性地板类
        EntityType.ELASTIC_FLOOR: [
            {"name": "PVC地板", "properties": {
                "types": ["卷材", "片材"],
                "thickness": "1.6-3.0mm",
                "features": ["防水", "防滑", "易清洁"],
                "applications": ["医院", "学校", "商场"]
            }, "aliases": ["塑胶地板"]},
            {"name": "SPC地板", "properties": {
                "composition": "石粉+PVC",
                "structure": "UV层+耐磨层+彩膜层+SPC基材+静音垫",
                "thickness": "3.5-6mm",
                "features": ["零甲醛", "防水", "锁扣安装", "适合地暖"],
                "耐磨转数": "≥4000转",
                "price_range": "80-200元/㎡"
            }, "aliases": ["石塑地板"]},
            {"name": "LVT地板", "properties": {
                "composition": "PVC+石粉",
                "features": ["柔软", "静音", "仿真度高"],
                "applications": ["家用", "商用"]
            }, "aliases": []},
            {"name": "橡胶地板", "properties": {
                "features": ["弹性好", "防滑", "耐磨", "吸音"],
                "applications": ["健身房", "幼儿园", "医院"]
            }, "aliases": []},
            {"name": "亚麻地板", "properties": {
                "composition": "亚麻籽油+软木粉+石灰石",
                "features": ["天然环保", "抗菌"],
                "applications": ["医院", "学校"]
            }, "aliases": []},
            {"name": "软木地板", "properties": {
                "material": "栓皮栎树皮",
                "features": ["脚感舒适", "保温隔音", "环保"],
                "cons": ["价格高", "耐磨性一般"],
                "price_range": "300-800元/㎡"
            }, "aliases": []},
        ],

        # ==================== 四、吊顶材料 ====================
        EntityType.CEILING: [
            {"name": "石膏板吊顶", "properties": {
                "types": ["普通纸面石膏板", "耐水纸面石膏板", "耐火纸面石膏板", "穿孔吸音石膏板"],
                "thickness": "9.5/12mm",
                "size": "1200×2400/3000mm",
                "shapes": ["平顶", "跌级吊顶", "悬浮吊顶", "弧形吊顶"]
            }, "aliases": ["石膏板"]},
            {"name": "铝扣板", "properties": {
                "surfaces": ["覆膜板", "滚涂板", "氧化板", "拉丝板", "纳米板"],
                "sizes": ["300×300", "300×600", "450×450", "600×600mm"],
                "thickness": "0.5/0.6/0.7/0.8mm"
            }, "aliases": ["集成吊顶"]},
            {"name": "蜂窝大板", "properties": {
                "structure": "铝蜂窝芯+铝面板",
                "sizes": ["450×900", "600×1200mm"],
                "thickness": "8-15mm",
                "features": "平整度高/无拼缝感"
            }, "aliases": []},
            {"name": "PVC扣板", "properties": {
                "sizes": ["200×3000", "250×3000", "300×3000mm"],
                "thickness": "5-10mm",
                "features": ["防水", "经济"],
                "applications": ["厨卫", "阳台"]
            }, "aliases": []},
            {"name": "桑拿板", "properties": {
                "materials": ["松木", "杉木", "樟子松"],
                "sizes": ["85×10mm", "95×12mm"],
                "applications": ["阳台", "露台"]
            }, "aliases": []},
            {"name": "软膜天花", "properties": {
                "material": "PVC软膜",
                "types": ["透光膜", "哑光膜", "缎光膜", "金属膜", "喷绘膜"],
                "features": ["造型自由", "可透光"],
                "applications": ["商业空间", "造型吊顶"]
            }, "aliases": []},
            # 吊顶造型类型
            {"name": "平顶", "properties": {
                "description": "最简单的吊顶形式",
                "features": ["简洁", "层高损失小"],
                "suitable_height": "≥2.6m",
                "style": ["现代简约", "北欧"]
            }, "aliases": ["平面吊顶"]},
            {"name": "跌级吊顶", "properties": {
                "description": "多层次吊顶，有层次感",
                "features": ["层次分明", "可隐藏灯带"],
                "suitable_height": "≥2.7m",
                "style": ["现代", "轻奢"]
            }, "aliases": ["多级吊顶"]},
            {"name": "边吊", "properties": {
                "description": "只在房间四周做吊顶",
                "features": ["保留层高", "可隐藏管线"],
                "suitable_height": "≥2.5m",
                "width": "30-60cm"
            }, "aliases": ["四周吊顶"]},
            {"name": "双眼皮吊顶", "properties": {
                "description": "两层石膏板叠加的简约吊顶",
                "features": ["简洁", "层高损失小", "造价低"],
                "suitable_height": "≥2.5m",
                "style": ["现代简约", "北欧", "日式"],
                "thickness": "约5cm"
            }, "aliases": ["双层石膏线"]},
            {"name": "无主灯吊顶", "properties": {
                "description": "配合无主灯设计的吊顶",
                "features": ["灯光均匀", "现代感强"],
                "lighting": ["筒灯", "射灯", "磁吸轨道灯", "灯带"],
                "style": ["现代简约", "轻奢"]
            }, "aliases": ["无主灯设计吊顶"]},
            {"name": "悬浮吊顶", "properties": {
                "description": "吊顶与墙面有缝隙，形成悬浮效果",
                "features": ["轻盈", "现代感"],
                "gap": "5-10cm",
                "style": ["现代", "轻奢"]
            }, "aliases": []},
            {"name": "弧形吊顶", "properties": {
                "description": "带有弧形造型的吊顶",
                "features": ["柔和", "艺术感"],
                "craft": "需要专业木工",
                "style": ["欧式", "现代"]
            }, "aliases": ["圆弧吊顶"]},
            {"name": "穹顶", "properties": {
                "description": "圆顶或拱形吊顶",
                "features": ["大气", "空间感强"],
                "suitable": ["别墅", "挑高空间"],
                "style": ["欧式", "美式"]
            }, "aliases": ["圆顶"]},
        ],

        # ==================== 五、门窗系统 ====================
        EntityType.DOOR: [
            {"name": "实木门", "properties": {
                "materials": ["橡木", "胡桃木", "樱桃木", "柚木", "水曲柳"],
                "types": ["原木门", "实木复合门"],
                "price_range": "1500-20000+元/樘"
            }, "aliases": ["原木门"]},
            {"name": "模压门", "properties": {
                "structure": {"门芯": "木龙骨框架", "填充": "蜂窝纸", "面板": "模压板HDF"},
                "features": ["经济实惠", "造型丰富"],
                "price_range": "500-1500元/樘"
            }, "aliases": []},
            {"name": "免漆门", "properties": {
                "surface": "PVC膜/三聚氰胺纸",
                "base": "密度板/刨花板",
                "price_range": "800-2000元/樘"
            }, "aliases": []},
            {"name": "烤漆门", "properties": {
                "craft": "底漆+面漆多道+高温烘烤+打磨抛光",
                "gloss": ["亮光", "哑光"],
                "price_range": "2000-6000元/樘"
            }, "aliases": []},
            {"name": "防盗门", "properties": {
                "grades": {
                    "甲级": {"steel": "门框≥2.0mm，门扇≥1.0mm", "break_time": "≥30分钟"},
                    "乙级": {"steel": "门框≥1.8mm，门扇≥0.8mm", "break_time": "≥15分钟"},
                    "丙级": {"steel": "门框≥1.5mm，门扇≥0.6mm", "break_time": "≥10分钟"}
                },
                "materials": ["钢质", "钢木", "不锈钢", "铜质"],
                "lock_grades": {"A级": "<1分钟", "B级": "<5分钟", "C级": ">10分钟"}
            }, "aliases": ["入户门"]},
            {"name": "智能锁", "properties": {
                "unlock_methods": ["指纹识别", "密码识别", "人脸识别", "刷卡识别", "远程开锁"]
            }, "aliases": ["指纹锁", "电子锁"]},
            # 更多门类型
            {"name": "生态门", "properties": {
                "types": ["铝木生态门", "竹木生态门"],
                "structure": {"框架": "铝合金", "门板": "木质/玻璃"},
                "features": ["环保", "稳定性好"],
                "price_range": "1500-4000元/樘"
            }, "aliases": []},
            {"name": "玻璃门", "properties": {
                "types": ["木框玻璃门", "铝框玻璃门", "无框玻璃门"],
                "glass_types": ["透明玻璃", "磨砂玻璃", "长虹玻璃", "水纹玻璃", "夹丝玻璃"],
                "applications": ["厨房", "书房", "阳台"]
            }, "aliases": []},
            {"name": "长虹玻璃门", "properties": {
                "features": ["透光不透人", "复古感", "艺术感"],
                "applications": ["厨房", "卫生间", "隔断"],
                "style": ["日式", "复古", "现代"]
            }, "aliases": ["条纹玻璃门"]},
            {"name": "推拉门", "properties": {
                "types": ["吊轨推拉门", "地轨推拉门"],
                "features": ["节省空间", "开合方便"],
                "applications": ["厨房", "阳台", "衣帽间"]
            }, "aliases": ["移门"]},
            {"name": "谷仓门", "properties": {
                "style": ["美式", "工业风", "复古"],
                "features": ["装饰性强", "节省空间"],
                "applications": ["卧室", "卫生间", "储物间"]
            }, "aliases": []},
            {"name": "折叠门", "properties": {
                "features": ["开启面积大", "通透"],
                "applications": ["阳台", "厨房", "餐厅"]
            }, "aliases": []},
            {"name": "隐形门", "properties": {
                "types": ["平开隐形门", "推拉隐形门"],
                "features": ["与墙面融为一体", "美观"],
                "applications": ["电视背景墙", "卧室", "储物间"]
            }, "aliases": ["暗门"]},
            {"name": "铸铝门", "properties": {
                "material": "铝合金铸造",
                "features": ["造型丰富", "不生锈", "高端"],
                "applications": ["别墅", "高端住宅入户"]
            }, "aliases": []},
            {"name": "铜门", "properties": {
                "types": ["真铜门", "仿铜门"],
                "materials": ["紫铜", "黄铜"],
                "features": ["尊贵", "耐用"],
                "price_range": "8000-50000+元"
            }, "aliases": []},
            # 特殊门类
            {"name": "电动门", "properties": {
                "types": ["电动平移门", "电动平开门", "电动折叠门"],
                "applications": ["车库", "庭院", "商业入口"],
                "control": ["遥控", "感应", "手机APP"],
                "brands": ["CAME", "FAAC", "捷顺"]
            }, "aliases": ["自动门"]},
            {"name": "感应门", "properties": {
                "types": ["平移感应门", "平开感应门", "旋转感应门"],
                "sensors": ["红外感应", "微波感应", "地埋感应"],
                "applications": ["商场", "酒店", "医院", "办公楼"],
                "brands": ["多玛", "盖泽", "松下"]
            }, "aliases": ["自动感应门"]},
            {"name": "旋转门", "properties": {
                "types": ["手动旋转门", "自动旋转门", "两翼旋转门", "三翼旋转门", "四翼旋转门"],
                "features": ["气密性好", "节能", "高档感"],
                "applications": ["酒店", "写字楼", "商场"],
                "brands": ["多玛", "宝盾", "凯必盛"]
            }, "aliases": []},
        ],

        EntityType.WINDOW: [
            {"name": "断桥铝合金窗", "properties": {
                "structure": ["室外铝型材", "隔热条PA66+GF25", "室内铝型材"],
                "series": ["60系列", "65系列", "70系列", "80系列", "90系列", "108系列", "120系列"],
                "wall_thickness": {"国标": "≥1.4mm", "新国标": "≥1.8mm", "高端": "2.0mm以上"},
                "insulation_width": ["14.8mm", "20mm", "24/27mm", "30/35mm"]
            }, "aliases": ["断桥铝窗"]},
            {"name": "系统窗", "properties": {
                "performance": {
                    "气密性": "≤0.5m³/(m·h)",
                    "水密性": "≥500Pa",
                    "抗风压": "≥5000Pa",
                    "K值": "≤1.5W/(m²·K)"
                },
                "brands": {"进口": ["旭格", "YKK", "阿鲁克", "贝克洛"], "国产": ["森鹰", "墨瑟", "正典", "皇派"]},
                "price_range": "1500-3000+元/㎡"
            }, "aliases": []},
            {"name": "铝包木窗", "properties": {
                "structure": "室内实木+室外铝合金",
                "wood_types": ["橡木", "松木", "柚木"],
                "features": ["美观", "保温", "高端"],
                "price_range": "2000-5000+元/㎡"
            }, "aliases": []},
            {"name": "中空玻璃", "properties": {
                "structure": "玻璃+空气层+玻璃",
                "configs": ["5+9A+5", "5+12A+5", "5+20A+5", "5+27A+5"],
                "gas_fill": ["干燥空气", "氩气"]
            }, "aliases": []},
            {"name": "Low-E玻璃", "properties": {
                "principle": "低辐射镀膜",
                "types": ["高透型", "遮阳型"],
                "functions": ["冬季保温", "夏季隔热"]
            }, "aliases": ["低辐射玻璃"]},
            {"name": "夹胶玻璃", "properties": {
                "structure": "玻璃+PVB膜+玻璃",
                "config": "5+0.76PVB+5",
                "functions": ["安全", "隔音"],
                "applications": ["落地窗", "天窗"]
            }, "aliases": []},
            # 更多窗户类型
            {"name": "塑钢窗", "properties": {
                "material": "UPVC型材",
                "features": ["保温好", "价格低"],
                "cons": ["强度低", "易老化"],
                "price_range": "300-600元/㎡"
            }, "aliases": ["PVC窗"]},
            {"name": "木包铝窗", "properties": {
                "structure": "铝合金主体+室内木饰面",
                "features": ["稳定性好", "美观"],
                "price_range": "1500-3000元/㎡"
            }, "aliases": []},
            {"name": "三玻两腔玻璃", "properties": {
                "structure": "玻璃+空气+玻璃+空气+玻璃",
                "config": "5+12A+5+12A+5",
                "features": ["保温性极佳"],
                "applications": ["严寒地区"]
            }, "aliases": ["三层中空玻璃"]},
            {"name": "钢化玻璃", "properties": {
                "strength": "普通玻璃4-5倍",
                "break_pattern": "颗粒状(安全)",
                "certification": "3C认证标志"
            }, "aliases": []},
            # 窗户开启方式
            {"name": "平开窗", "properties": {
                "types": ["内开内倒", "外开上悬", "单开", "双开"],
                "features": ["密封性好", "通风量大"],
                "applications": ["卧室", "客厅"]
            }, "aliases": []},
            {"name": "推拉窗", "properties": {
                "types": ["双轨推拉", "三轨推拉", "提升推拉"],
                "features": ["不占空间", "操作方便"],
                "cons": ["密封性不如平开窗"]
            }, "aliases": []},
            {"name": "内开内倒窗", "properties": {
                "features": ["通风防雨", "安全", "易清洁"],
                "applications": ["高层住宅", "儿童房"]
            }, "aliases": ["内倒窗"]},
            {"name": "上悬窗", "properties": {
                "features": ["通风防雨", "安全"],
                "applications": ["卫生间", "厨房"]
            }, "aliases": []},
            {"name": "固定窗", "properties": {
                "features": ["不可开启", "采光用"],
                "applications": ["落地窗", "幕墙"]
            }, "aliases": []},
            # 特殊窗户产品
            {"name": "断桥铝门窗", "properties": {
                "types": ["断桥铝窗", "断桥铝门"],
                "series": ["60系列", "70系列", "80系列", "90系列", "108系列"],
                "features": ["隔热保温", "隔音", "密封性好"],
                "glass": ["中空玻璃", "三玻两腔", "夹胶玻璃"],
                "price_range": "600-1500元/㎡"
            }, "aliases": ["断桥铝"]},
            {"name": "阳光房", "properties": {
                "types": ["钢结构阳光房", "铝合金阳光房", "木结构阳光房"],
                "roof_types": ["人字顶", "弧形顶", "平顶", "斜顶"],
                "glass": ["钢化玻璃", "夹胶玻璃", "中空玻璃", "Low-E玻璃"],
                "features": ["采光好", "亲近自然", "扩展空间"],
                "considerations": ["隔热", "遮阳", "通风", "排水"],
                "applications": ["露台", "庭院", "别墅"]
            }, "aliases": ["玻璃房", "阳光屋"]},
        ],

        # ==================== 五金配件 ====================
        EntityType.HARDWARE: [
            # 门窗五金
            {"name": "门窗执手", "properties": {
                "types": ["单点执手", "传动执手"],
                "materials": ["锌合金", "铝合金", "不锈钢"],
                "finishes": ["电镀", "喷涂", "阳极氧化"]
            }, "aliases": ["执手", "把手"]},
            {"name": "门窗合页", "properties": {
                "types": ["普通合页", "隐藏式铰链"],
                "load_capacity": "40-150kg",
                "materials": ["不锈钢", "锌合金"]
            }, "aliases": ["合页", "铰链"]},
            {"name": "传动器", "properties": {
                "types": ["单点锁", "多点锁"],
                "applications": ["平开窗", "推拉窗"]
            }, "aliases": []},
            {"name": "滑撑", "properties": {
                "types": ["二连杆", "四连杆"],
                "applications": ["外开窗"]
            }, "aliases": []},
            {"name": "风撑", "properties": {
                "function": "限制窗户开启角度",
                "types": ["定位风撑", "限位风撑"]
            }, "aliases": []},
            {"name": "滑轮", "properties": {
                "types": ["单轮", "双轮"],
                "load_capacity": "30-200kg",
                "applications": ["推拉门窗"]
            }, "aliases": []},
            {"name": "密封条", "properties": {
                "materials": ["三元乙丙(EPDM)", "硅胶", "毛条"],
                "functions": ["密封", "隔音", "防尘"]
            }, "aliases": []},
            # 橱柜五金
            {"name": "橱柜铰链", "properties": {
                "brands": ["百隆", "海蒂诗", "格拉斯", "DTC"],
                "types": ["阻尼铰链", "普通铰链"],
                "durability": "5万次以上开合",
                "angles": ["95°", "110°", "165°"]
            }, "aliases": ["柜门铰链"]},
            {"name": "抽屉滑轨", "properties": {
                "types": ["托底滑轨", "骑马抽滑轨", "隐藏式滑轨"],
                "load_capacity": "25-80kg",
                "brands": ["百隆", "海蒂诗", "悍高"]
            }, "aliases": ["滑轨"]},
            {"name": "拉篮", "properties": {
                "types": ["调味拉篮", "碗碟拉篮", "转角拉篮", "高柜拉篮"],
                "special_types": ["小怪物", "大怪物"],
                "materials": ["304不锈钢", "铁镀铬"]
            }, "aliases": []},
            {"name": "气撑", "properties": {
                "types": ["普通气撑", "随意停气撑", "电动上翻门"],
                "applications": ["上翻门", "吊柜"]
            }, "aliases": []},
            {"name": "拉手", "properties": {
                "types": ["明装拉手", "隐藏式拉手", "无拉手(反弹器)"],
                "materials": ["铝合金", "不锈钢", "锌合金"]
            }, "aliases": []},
            {"name": "踢脚板", "properties": {
                "materials": ["PVC", "铝合金"],
                "height": "100-150mm"
            }, "aliases": []},
            # 衣柜五金
            {"name": "挂衣杆", "properties": {
                "materials": ["铝合金", "不锈钢"],
                "types": ["普通挂衣杆", "带灯挂衣杆", "升降挂衣杆"]
            }, "aliases": []},
            {"name": "裤架", "properties": {
                "types": ["侧装裤架", "抽拉裤架"],
                "capacity": "10-20条"
            }, "aliases": []},
            {"name": "旋转衣架", "properties": {
                "applications": ["转角衣柜"],
                "features": ["360度旋转", "充分利用空间"]
            }, "aliases": []},
            {"name": "升降衣架", "properties": {
                "applications": ["高柜取物"],
                "operation": ["手动", "电动"]
            }, "aliases": []},
            # 窗帘配件
            {"name": "罗马杆", "properties": {
                "materials": ["实木", "铝合金", "铁艺"],
                "diameters": ["22mm", "25mm", "28mm"],
                "features": "装饰头多种造型"
            }, "aliases": ["窗帘杆"]},
            {"name": "窗帘滑轨", "properties": {
                "types": ["铝合金轨道", "纳米轨道", "弯轨"],
                "shapes": ["直轨", "L型", "弧形"]
            }, "aliases": ["窗帘轨道"]},
            {"name": "电动窗帘轨道", "properties": {
                "brands": ["杜亚", "DOOYA"],
                "control": ["遥控", "APP", "语音", "定时"]
            }, "aliases": ["电动轨道"]},
        ],

        # ==================== 六、厨房系统 ====================
        EntityType.CABINET: [
            {"name": "橱柜", "properties": {
                "components": ["柜体", "门板", "台面", "五金"],
                "types": ["地柜", "吊柜", "高柜", "中岛"],
                "applications": ["厨房"]
            }, "aliases": ["厨柜"]},
            {"name": "实木多层板柜体", "properties": {
                "thickness": "16/18mm",
                "env_grade": "ENF/E0级",
                "features": ["防潮性好", "握钉力强"]
            }, "aliases": ["多层板柜体"]},
            {"name": "实木颗粒板柜体", "properties": {
                "thickness": "16/18mm",
                "env_grade": "E0/E1级",
                "brands": {"进口": ["爱格", "克诺斯邦"], "国产": ["大亚", "露水河"]}
            }, "aliases": ["颗粒板柜体"]},
            {"name": "不锈钢柜体", "properties": {
                "material": "304/201不锈钢",
                "thickness": "0.6-1.2mm",
                "features": ["防水", "防火"]
            }, "aliases": []},
            {"name": "双饰面门板", "properties": {
                "base": "颗粒板/密度板",
                "surface": "三聚氰胺浸渍纸",
                "features": ["经济", "花色多"],
                "price_level": "★☆☆☆☆"
            }, "aliases": ["三聚氰胺板"]},
            {"name": "吸塑门板", "properties": {
                "base": "密度板",
                "surface": "PVC膜",
                "features": ["造型丰富", "防水"],
                "price_level": "★★☆☆☆"
            }, "aliases": ["模压板"]},
            {"name": "烤漆门板", "properties": {
                "base": "密度板",
                "craft": "多道底漆面漆+烘烤",
                "features": ["色彩鲜艳", "易清洁"],
                "price_level": "★★★☆☆"
            }, "aliases": []},
            {"name": "石英石台面", "properties": {
                "composition": "93%石英砂+7%树脂",
                "thickness": "15/20mm",
                "hardness": "莫氏7级",
                "brands": ["赛凯隆", "中迅", "戈兰迪"],
                "price_range": "800-2000元/延米"
            }, "aliases": []},
            {"name": "岩板台面", "properties": {
                "composition": "天然石粉+高温烧制",
                "thickness": "12/20mm",
                "features": ["耐高温", "耐刮", "大板无缝"],
                "brands": ["德赛斯", "拉米娜", "新濠"],
                "price_range": "1500-4000+元/延米"
            }, "aliases": []},
            # 更多门板类型
            {"name": "亚克力门板", "properties": {
                "base": "密度板",
                "surface": "亚克力面板",
                "features": ["高光", "耐刮"],
                "price_level": "★★★☆☆"
            }, "aliases": []},
            {"name": "实木门板", "properties": {
                "types": ["原木门板", "实木贴皮"],
                "features": ["质感好", "高端"],
                "price_level": "★★★★☆"
            }, "aliases": []},
            {"name": "岩板门板", "properties": {
                "thickness": "3-6mm",
                "features": ["耐高温", "耐刮", "现代感"],
                "price_level": "★★★★★"
            }, "aliases": []},
            {"name": "金属门板", "properties": {
                "types": ["不锈钢门板", "铝合金门板"],
                "features": ["现代", "耐用", "工业风"]
            }, "aliases": []},
            {"name": "PET门板", "properties": {
                "base": "密度板/颗粒板",
                "surface": "PET膜",
                "features": ["环保", "肤感", "哑光"],
                "price_level": "★★★☆☆"
            }, "aliases": ["肤感门板"]},
            # 更多台面类型
            {"name": "不锈钢台面", "properties": {
                "material": "304不锈钢",
                "thickness": "1.0-1.5mm",
                "features": ["耐用", "易清洁", "无缝"],
                "price_range": "1000-2000元/延米"
            }, "aliases": []},
            {"name": "亚克力台面", "properties": {
                "types": ["纯亚克力", "复合亚克力"],
                "features": ["可无缝拼接", "可修复"],
                "price_range": "600-1500元/延米"
            }, "aliases": ["人造石台面"]},
            {"name": "实木台面", "properties": {
                "materials": ["橡木", "榉木", "乌金木"],
                "treatment": ["木蜡油", "清漆"],
                "features": ["质感温润", "需保养"],
                "price_range": "800-2000元/延米"
            }, "aliases": []},
            {"name": "大理石台面", "properties": {
                "features": ["天然纹理", "有毛孔"],
                "cons": ["易渗色", "需养护"],
                "price_range": "1000-3000元/延米"
            }, "aliases": []},
        ],

        EntityType.KITCHEN_APPLIANCE: [
            {"name": "油烟机", "properties": {
                "types": {"顶吸式": ["中式深罩", "欧式T型"], "侧吸式": "近吸式", "集成灶": "烟灶联动"},
                "params": {
                    "风量": {"普通": "17-19m³/min", "大风量": "20-23m³/min", "超大": "24m³/min以上"},
                    "风压": {"普通": "300-400Pa", "高层": "≥400Pa", "超高层": "≥500Pa"},
                    "噪音": "≤70dB(A)"
                },
                "brands": {"高端": ["方太", "老板"], "中端": ["华帝", "美的", "海尔"]}
            }, "aliases": ["抽油烟机", "烟机"]},
            {"name": "燃气灶", "properties": {
                "gas_types": {"天然气": "12T", "液化气": "20Y", "人工煤气": "5R"},
                "params": {
                    "热负荷": {"普通": "3.8-4.2kW", "大火力": "4.5-5.0kW", "猛火": "5.2kW以上"},
                    "热效率": {"一级": "≥63%", "二级": "≥59%", "三级": "≥55%"}
                }
            }, "aliases": ["灶具", "煤气灶"]},
            {"name": "洗碗机", "properties": {
                "types": ["嵌入式", "独立式", "台式", "水槽式"],
                "capacity": {"台式": "4-6套", "小型嵌入": "8套", "标准嵌入": "13套", "大容量": "14-16套"},
                "dry_methods": ["余温烘干", "热风烘干", "晶蕾烘干", "自动开门烘干"],
                "brands": {"进口": ["西门子", "博世", "米勒"], "国产": ["方太", "老板", "美的"]}
            }, "aliases": []},
            {"name": "蒸烤箱", "properties": {
                "types": ["纯蒸箱", "纯烤箱", "蒸烤一体机", "微蒸烤一体机"],
                "capacity": "25-70L",
                "temp_range": "30-250℃",
                "brands": ["方太", "老板", "西门子", "博世"]
            }, "aliases": ["蒸箱", "烤箱"]},
            {"name": "净水器", "properties": {
                "types": {
                    "前置过滤器": {"precision": "40-100μm", "function": "过滤泥沙/铁锈"},
                    "RO反渗透": {"precision": "0.0001μm", "flux": "400G/600G/800G/1000G"},
                    "超滤净水器": {"precision": "0.01μm", "feature": "保留矿物质"}
                }
            }, "aliases": ["净水机"]},
            {"name": "垃圾处理器", "properties": {
                "power": "370-750W",
                "grind_level": "1-4级",
                "capacity": "1-1.5L",
                "brands": ["爱适易", "贝克巴斯", "唯斯特姆"]
            }, "aliases": []},
        ],

        EntityType.SINK: [
            {"name": "不锈钢水槽", "properties": {
                "grades": {"304": "标准", "316": "高端", "201": "低端"},
                "thickness": "0.8-1.2mm",
                "surfaces": ["拉丝", "磨砂", "珍珠面", "镜面"],
                "crafts": ["手工槽焊接", "一体拉伸"]
            }, "aliases": []},
            {"name": "石英石水槽", "properties": {
                "composition": "石英砂+树脂",
                "features": ["耐刮", "耐高温"],
                "cons": ["较重", "价格高"]
            }, "aliases": []},
        ],

        # ==================== 七、卫浴系统 ====================
        EntityType.TOILET: [
            {"name": "虹吸式马桶", "properties": {
                "types": ["普通虹吸", "喷射虹吸", "漩涡虹吸"],
                "features": ["静音", "防臭"],
                "water_usage": "4.8-6L"
            }, "aliases": []},
            {"name": "直冲式马桶", "properties": {
                "features": ["冲力强", "不易堵"],
                "cons": ["噪音大", "易溅水"],
                "water_usage": "6L左右"
            }, "aliases": []},
            {"name": "壁挂马桶", "properties": {
                "features": ["易清洁", "节省空间"],
                "requires": "隐藏水箱"
            }, "aliases": ["挂墙马桶"]},
            {"name": "智能马桶", "properties": {
                "functions": {
                    "基础": ["座圈加热", "臀洗", "妇洗", "暖风烘干", "自动冲水"],
                    "进阶": ["自动翻盖", "除臭", "夜灯", "UV杀菌", "泡沫盾"]
                },
                "brands": {"日系": ["TOTO", "松下", "伊奈"], "国产": ["恒洁", "九牧", "箭牌"]}
            }, "aliases": ["智能马桶盖"]},
            {"name": "马桶", "properties": {
                "pit_distance": ["300mm", "350mm", "400mm"],
                "water_efficiency": {"一级": "≤4.0L", "二级": "4.1-5.0L", "三级": "5.1-6.0L"},
                "brands": {"国际": ["TOTO", "科勒", "杜拉维特"], "国内": ["恒洁", "九牧", "箭牌"]}
            }, "aliases": ["坐便器"]},
        ],

        EntityType.BATHROOM_CABINET: [
            {"name": "实木浴室柜", "properties": {
                "materials": ["橡木", "橡胶木"],
                "surface": "烤漆/木蜡油",
                "pros": ["质感好", "环保"],
                "cons": ["需防潮", "价格高"]
            }, "aliases": []},
            {"name": "多层实木浴室柜", "properties": {
                "base": "多层板",
                "surface": "烤漆/贴皮",
                "feature": "性价比高"
            }, "aliases": []},
            {"name": "PVC浴室柜", "properties": {
                "material": "PVC发泡板",
                "pros": ["防水", "经济"],
                "cons": "质感一般"
            }, "aliases": []},
            {"name": "岩板浴室柜", "properties": {
                "cabinet": "多层板",
                "door": "岩板"
            }, "aliases": []},
        ],

        EntityType.SHOWER: [
            {"name": "恒温花洒", "properties": {
                "feature": "恒温阀芯",
                "temp_setting": "38℃",
                "safety": "防烫保护"
            }, "aliases": []},
            {"name": "顶喷花洒", "properties": {
                "sizes": "200-400mm",
                "shapes": ["圆形", "方形"],
                "materials": ["ABS", "不锈钢", "铜"],
                "spray_modes": ["雨淋", "瀑布", "雾化"]
            }, "aliases": ["花洒头"]},
            {"name": "淋浴房", "properties": {
                "shapes": ["一字型", "L型", "弧形", "钻石型"],
                "door_types": ["平开门", "推拉门", "折叠门"],
                "frame_types": ["有框", "无框"],
                "glass": {"thickness": "6/8/10mm", "type": "钢化玻璃3C认证"},
                "brands": {"高端": ["德立", "朗斯", "理想"], "中端": ["玫瑰岛", "福瑞", "凯立"]}
            }, "aliases": []},
            {"name": "浴缸", "properties": {
                "materials": {
                    "亚克力": {"pros": ["轻便", "保温", "造型多"], "price": "1000-5000元"},
                    "铸铁": {"pros": ["耐用", "保温"], "cons": ["重", "造型少"], "price": "3000-10000元"},
                    "人造石": {"pros": ["质感好", "可修复"], "price": "5000-20000元"}
                },
                "functions": ["普通", "按摩", "冲浪", "智能"],
                "sizes": {"长方形": "1500-1800×700-800mm", "圆形": "直径1200-1800mm"}
            }, "aliases": []},
            {"name": "增压花洒", "properties": {
                "principle": "空气增压技术",
                "features": ["节水30%", "水流强劲"],
                "suitable": "低水压环境"
            }, "aliases": []},
            {"name": "智能花洒", "properties": {
                "features": ["温度显示", "水量控制", "音乐播放", "氛围灯"],
                "power": "电池/USB充电",
                "brands": ["科勒", "汉斯格雅", "摩恩"]
            }, "aliases": []},
            {"name": "手持花洒", "properties": {
                "spray_modes": ["雨淋", "按摩", "雾化", "混合"],
                "materials": ["ABS", "不锈钢"],
                "hose_length": "1.5-2m"
            }, "aliases": []},
            {"name": "按摩浴缸", "properties": {
                "jet_types": ["气泡按摩", "水流按摩", "混合按摩"],
                "jet_count": "6-12个",
                "power": "750-1500W",
                "features": ["恒温", "臭氧消毒", "LED灯光"]
            }, "aliases": ["冲浪浴缸"]},
            {"name": "智能浴缸", "properties": {
                "features": ["自动注水", "恒温控制", "自动排水", "按摩功能", "音乐播放"],
                "control": ["触控面板", "遥控器", "APP控制"],
                "brands": ["TOTO", "科勒", "箭牌"]
            }, "aliases": []},
            {"name": "木桶浴缸", "properties": {
                "materials": ["香柏木", "橡木", "云杉"],
                "features": ["天然木香", "保温好", "养生"],
                "maintenance": "需定期保养防开裂"
            }, "aliases": ["泡澡桶"]},
            {"name": "嵌入式浴缸", "properties": {
                "install": "砌筑嵌入",
                "features": ["美观", "节省空间"],
                "note": "需预留检修口"
            }, "aliases": []},
            {"name": "独立式浴缸", "properties": {
                "types": ["经典爪脚", "现代简约", "蛋形"],
                "features": ["造型美观", "安装灵活"],
                "space_requirement": "需较大卫生间"
            }, "aliases": []},
        ],

        EntityType.BATHROOM_HARDWARE: [
            {"name": "全铜龙头", "properties": {
                "grades": {"H59": "标准", "H62": "优质"},
                "valve": "陶瓷阀芯",
                "plating": "三层电镀：铜+镍+铬",
                "plating_thickness": "≥8μm"
            }, "aliases": ["水龙头"]},
            {"name": "不锈钢龙头", "properties": {
                "material": "304不锈钢",
                "pros": ["无铅", "耐腐蚀"]
            }, "aliases": []},
            {"name": "地漏", "properties": {
                "types": {
                    "水封地漏": {"principle": "存水弯防臭", "cons": "易干涸"},
                    "自封地漏": ["T型", "翻板", "弹簧", "磁铁"],
                    "两防地漏": "水封+自封"
                },
                "materials": ["全铜", "304不锈钢", "锌合金"],
                "flow_rate": {"普通": "30-40L/min", "大流量": "≥60L/min"},
                "brands": ["潜水艇", "九牧", "科勒"]
            }, "aliases": []},
            {"name": "角阀", "properties": {
                "function": "控制水流/便于维修",
                "materials": ["全铜", "不锈钢", "锌合金"],
                "specs": ["4分(1/2\")", "6分(3/4\")"]
            }, "aliases": []},
            {"name": "浴霸", "properties": {
                "types": {
                    "灯暖": {"principle": "红外线灯泡", "power": "1100-1200W", "pros": ["升温快", "价格低"]},
                    "风暖": {"principle": "PTC陶瓷加热", "power": "2000-2500W", "pros": ["舒适", "均匀"]},
                    "碳纤维": {"principle": "碳纤维发热", "pros": ["升温快", "寿命长"]}
                },
                "functions": ["换气", "照明", "吹风", "干燥"],
                "brands": {"高端": ["奥普", "松下"], "中端": ["欧普", "雷士", "美的"]}
            }, "aliases": []},
            # 卫浴挂件
            {"name": "毛巾架", "properties": {
                "types": ["单杆", "双杆", "活动", "固定"],
                "length": "400-900mm",
                "materials": ["太空铝", "304不锈钢", "全铜"]
            }, "aliases": ["毛巾杆"]},
            {"name": "浴巾架", "properties": {
                "features": ["多层设计", "可折叠"],
                "materials": ["太空铝", "不锈钢"]
            }, "aliases": []},
            {"name": "置物架", "properties": {
                "types": ["单层", "双层", "三层", "三角置物架"],
                "features": ["带挂钩", "可调节"],
                "materials": ["太空铝", "不锈钢", "玻璃"]
            }, "aliases": []},
            {"name": "纸巾架", "properties": {
                "types": ["卷纸架", "抽纸架"],
                "features": ["防水", "带盖"],
                "materials": ["太空铝", "不锈钢", "ABS"]
            }, "aliases": ["厕纸架"]},
            {"name": "马桶刷架", "properties": {
                "types": ["壁挂式", "落地式"],
                "materials": ["不锈钢", "陶瓷"]
            }, "aliases": []},
            {"name": "衣钩", "properties": {
                "types": ["单钩", "排钩", "隐藏式挂钩"],
                "materials": ["太空铝", "不锈钢", "锌合金"]
            }, "aliases": ["挂钩"]},
            {"name": "长条地漏", "properties": {
                "size": "300-900mm",
                "features": ["排水量大", "美观", "隐形"],
                "applications": ["淋浴区", "干湿分离"]
            }, "aliases": ["隐形地漏", "线性地漏"]},
            {"name": "洗衣机地漏", "properties": {
                "types": ["单用", "两用"],
                "features": ["防返水", "防臭"],
                "applications": ["阳台", "卫生间"]
            }, "aliases": []},
            {"name": "软管", "properties": {
                "types": ["编织软管", "波纹软管", "PVC软管"],
                "materials": ["不锈钢编织", "尼龙编织", "不锈钢波纹"],
                "length": "300/400/500/600/800mm",
                "pressure": "≥1.6MPa"
            }, "aliases": ["进水软管"]},
            {"name": "挡水条", "properties": {
                "materials": ["大理石", "花岗岩", "人造石", "PVC"],
                "height": "40-50mm",
                "install": ["预埋", "粘贴"]
            }, "aliases": []},
        ],

        # ==================== 八、定制家具 ====================
        EntityType.WARDROBE: [
            {"name": "衣柜", "properties": {
                "types": ["推拉门衣柜", "平开门衣柜", "开放式衣柜", "步入式衣帽间"],
                "components": ["柜体", "门板", "五金", "内部配件"],
                "applications": ["卧室", "衣帽间"]
            }, "aliases": ["衣橱"]},
            {"name": "实木多层板衣柜", "properties": {
                "thickness": "18mm",
                "env_grade": "ENF/E0级",
                "pros": ["握钉力强", "防潮好"],
                "price_level": "★★★☆☆"
            }, "aliases": []},
            {"name": "实木颗粒板衣柜", "properties": {
                "thickness": "18mm",
                "env_grade": "E0/E1级",
                "pros": ["平整度好", "经济"],
                "price_level": "★★☆☆☆"
            }, "aliases": []},
            {"name": "欧松板衣柜", "properties": {
                "thickness": "18mm",
                "env_grade": "ENF级",
                "pros": ["承重强", "环保"],
                "price_level": "★★★★☆"
            }, "aliases": ["OSB衣柜"]},
            {"name": "平开门衣柜", "properties": {
                "pros": ["密封好", "全开视野"],
                "cons": "需开门空间",
                "door_width": "400-600mm",
                "hardware": "阻尼铰链"
            }, "aliases": []},
            {"name": "推拉门衣柜", "properties": {
                "pros": "节省空间",
                "cons": "只能开一半",
                "track": ["上轨吊滑", "下轨滑动"],
                "door_width": "700-1000mm"
            }, "aliases": ["移门衣柜"]},
        ],

        EntityType.CUSTOM_CABINET: [
            {"name": "榻榻米", "properties": {
                "structure": {"地台高度": "350-450mm", "床垫": ["椰棕垫", "乳胶垫"]},
                "combinations": ["榻榻米+衣柜", "榻榻米+书柜", "榻榻米+书桌"],
                "applications": ["次卧", "书房", "儿童房"]
            }, "aliases": []},
            {"name": "玄关柜", "properties": {
                "zones": ["换鞋凳", "鞋柜区", "挂衣区", "置物台", "全身镜"],
                "shoe_shelf": {"spacing": "150-200mm", "depth": "300-350mm"},
                "types": ["入墙式", "独立式", "隔断式"]
            }, "aliases": ["鞋柜"]},
            {"name": "酒柜", "properties": {
                "features": ["红酒架斜放", "酒杯架倒挂", "灯光展示", "恒温恒湿"]
            }, "aliases": []},
            {"name": "电视柜", "properties": {
                "types": ["落地式", "悬浮式", "组合式"],
                "functions": ["机顶盒收纳", "路由器收纳", "线缆管理"]
            }, "aliases": ["电视背景墙"]},
            {"name": "阳台柜", "properties": {
                "zones": ["洗衣机位", "烘干机位", "洗手台", "吊柜储物"],
                "material_req": ["防水", "防晒"]
            }, "aliases": ["洗衣机柜"]},
        ],

        # ==================== 九、成品家具 ====================
        EntityType.SOFA: [
            {"name": "真皮沙发", "properties": {
                "leather_types": {
                    "头层牛皮": ["黄牛皮", "水牛皮", "进口皮"],
                    "工艺": ["全青皮", "半青皮", "压纹皮"]
                },
                "brands": {"高端": ["Natuzzi", "Rolf Benz"], "中高端": ["芝华仕", "顾家", "左右"]}
            }, "aliases": ["皮沙发"]},
            {"name": "布艺沙发", "properties": {
                "fabrics": ["棉麻布", "绒布", "雪尼尔", "防水布"]
            }, "aliases": []},
            {"name": "科技布沙发", "properties": {
                "features": ["皮感+布艺优点", "防水", "透气", "易清洁"],
                "brand": "意大利Cleaf"
            }, "aliases": []},
            {"name": "沙发", "properties": {
                "forms": ["一字型", "L型", "U型", "模块沙发"],
                "sizes": {"单人": "800-1000mm", "双人": "1400-1600mm", "三人": "1800-2200mm"},
                "seat_height": "400-450mm",
                "seat_depth": "550-600mm"
            }, "aliases": []},
            {"name": "转角沙发", "properties": {
                "types": ["L型", "贵妃位"],
                "direction": ["左转角", "右转角"],
                "features": ["空间利用", "多人就坐"]
            }, "aliases": ["L型沙发"]},
            {"name": "U型沙发", "properties": {
                "seats": "5-7人",
                "space_requirement": "客厅宽度≥4m",
                "features": ["围合感", "适合大客厅"]
            }, "aliases": []},
            {"name": "功能沙发", "properties": {
                "functions": ["电动躺倒", "手动躺倒", "摇摆", "旋转"],
                "features": ["USB充电", "储物", "杯托"],
                "brands": ["芝华仕", "顾家", "左右"]
            }, "aliases": ["电动沙发", "躺椅沙发"]},
            {"name": "懒人沙发", "properties": {
                "types": ["豆袋沙发", "榻榻米沙发", "落地沙发"],
                "filling": ["EPS颗粒", "海绵", "记忆棉"],
                "features": ["随意造型", "舒适放松"]
            }, "aliases": ["豆袋沙发"]},
            {"name": "模块沙发", "properties": {
                "features": ["自由组合", "灵活布局", "可拆分"],
                "modules": ["单人位", "双人位", "转角位", "脚踏"],
                "brands": ["宜家", "Muji", "造作"]
            }, "aliases": ["组合沙发"]},
            {"name": "沙发床", "properties": {
                "types": ["折叠式", "抽拉式", "翻转式"],
                "features": ["一物两用", "节省空间"],
                "suitable": "小户型/客房"
            }, "aliases": ["两用沙发"]},
        ],

        EntityType.BED: [
            {"name": "实木床", "properties": {
                "materials": ["橡木", "胡桃木", "白蜡木", "榉木", "樱桃木"],
                "craft": ["榫卯结构", "五金连接"],
                "surface": "木蜡油/清漆"
            }, "aliases": []},
            {"name": "软包床", "properties": {
                "types": {
                    "皮床": ["真皮", "超纤皮", "科技皮"],
                    "布艺床": ["棉麻", "绒布", "科技布"]
                },
                "filling": ["海绵", "羽绒"]
            }, "aliases": ["皮床", "布艺床"]},
            {"name": "储物床", "properties": {
                "types": ["高箱床", "抽屉床", "气压杆床"]
            }, "aliases": []},
            {"name": "藤编床", "properties": {
                "materials": ["藤", "竹"],
                "styles": ["东南亚", "田园"],
                "features": ["透气", "自然"]
            }, "aliases": ["竹藤床"]},
            {"name": "金属床", "properties": {
                "types": ["铁艺床", "不锈钢床"],
                "styles": ["工业风", "现代简约"]
            }, "aliases": ["铁艺床"]},
            {"name": "床", "properties": {
                "sizes": {
                    "单人床": ["900×2000mm", "1200×2000mm"],
                    "双人床": ["1500×2000mm", "1800×2000mm", "2000×2000mm"]
                }
            }, "aliases": []},
        ],

        EntityType.MATTRESS: [
            {"name": "独立袋装弹簧床垫", "properties": {
                "features": ["独立支撑", "抗干扰"],
                "spring_count": "500-1200个",
                "zones": ["三区", "五区", "七区"]
            }, "aliases": ["弹簧床垫"]},
            {"name": "乳胶床垫", "properties": {
                "types": ["天然乳胶", "合成乳胶"],
                "latex_content": "≥85%",
                "origins": ["泰国", "马来西亚", "斯里兰卡"],
                "density": "60-95D",
                "features": ["回弹性好", "抗菌防螨", "透气性好"]
            }, "aliases": []},
            {"name": "记忆棉床垫", "properties": {
                "material": "聚氨酯",
                "features": ["慢回弹", "贴合身体"],
                "cons": "透气性一般"
            }, "aliases": []},
            {"name": "棕垫", "properties": {
                "types": {"山棕": "弹性好/价格高", "椰棕": "硬度高/价格低", "3E椰梦维": "环保胶水"},
                "features": ["硬", "透气", "环保"]
            }, "aliases": ["椰棕床垫"]},
            {"name": "床垫", "properties": {
                "firmness": {"软": "1-3级", "中等": "4-6级", "偏硬": "7-8级", "硬": "9-10级"},
                "thickness": {"薄垫": "5-10cm", "标准": "20-25cm", "加厚": "28-35cm"},
                "brands": {"国际高端": ["席梦思", "丝涟", "舒达", "金可儿"], "国内": ["慕思", "喜临门", "梦百合"]}
            }, "aliases": []},
            {"name": "分区弹簧床垫", "properties": {
                "zones": {"三区": "头/腰/脚", "五区": "头/肩/腰/臀/脚", "七区": "更精细分区"},
                "features": ["不同部位不同支撑", "贴合人体曲线"],
                "suitable": ["侧睡者", "腰椎问题者"]
            }, "aliases": ["分区床垫"]},
            {"name": "混合床垫", "properties": {
                "combinations": ["弹簧+乳胶", "弹簧+记忆棉", "弹簧+棕"],
                "features": ["综合优点", "性价比高"],
                "structure": "底层弹簧+顶层舒适层"
            }, "aliases": ["复合床垫"]},
            {"name": "连体弹簧床垫", "properties": {
                "type": "邦尼尔弹簧",
                "features": ["整体联动", "支撑性好"],
                "cons": ["抗干扰差"],
                "price_level": "经济型"
            }, "aliases": ["邦尼尔床垫", "整网弹簧床垫"]},
        ],

        EntityType.TABLE: [
            {"name": "岩板餐桌", "properties": {
                "thickness": "6-12mm",
                "features": ["耐高温", "耐刮", "易清洁"],
                "note": "主流选择"
            }, "aliases": []},
            {"name": "实木餐桌", "properties": {
                "materials": ["橡木", "胡桃木", "白蜡木"],
                "surface": "木蜡油/清漆"
            }, "aliases": []},
            {"name": "餐桌", "properties": {
                "shapes": ["长方形", "正方形", "圆形", "椭圆形"],
                "sizes": {"2人": "800×800mm", "4人": "1200×800mm", "6人": "1400-1600×800mm", "8人": "1800-2000×900mm"},
                "height": "750mm"
            }, "aliases": []},
            {"name": "茶几", "properties": {
                "materials": ["实木", "岩板", "大理石", "玻璃", "金属"],
                "sizes": {"长度": "1000-1400mm", "宽度": "500-800mm", "高度": "400-450mm"}
            }, "aliases": []},
            {"name": "大理石餐桌", "properties": {
                "types": ["天然大理石", "人造大理石"],
                "features": ["质感高档", "纹理自然"],
                "cons": ["易渗透", "需保养", "较重"]
            }, "aliases": []},
            {"name": "伸缩餐桌", "properties": {
                "types": ["拉伸式", "折叠式", "旋转式"],
                "extension": "可延长40-80cm",
                "features": ["灵活调节", "节省空间"]
            }, "aliases": ["可伸缩餐桌"]},
            {"name": "玻璃餐桌", "properties": {
                "glass_type": "钢化玻璃",
                "thickness": "8-12mm",
                "features": ["通透", "现代感", "易清洁"]
            }, "aliases": []},
            {"name": "圆餐桌", "properties": {
                "diameters": {"4人": "900-1000mm", "6人": "1200-1300mm", "8人": "1400-1500mm"},
                "features": ["无主位", "交流方便", "中式传统"]
            }, "aliases": []},
            {"name": "边几", "properties": {
                "sizes": {"直径": "400-600mm", "高度": "500-600mm"},
                "materials": ["实木", "金属", "大理石"],
                "applications": ["沙发旁", "床头"]
            }, "aliases": ["角几"]},
            {"name": "玄关桌", "properties": {
                "depth": "250-400mm",
                "height": "800-900mm",
                "features": ["装饰", "置物"]
            }, "aliases": ["玄关台"]},
            {"name": "梳妆台", "properties": {
                "types": ["带镜", "翻盖镜", "壁挂镜"],
                "features": ["储物抽屉", "灯光镜"],
                "sizes": {"宽度": "800-1200mm", "深度": "400-500mm"}
            }, "aliases": ["化妆台"]},
            {"name": "书桌", "properties": {
                "types": ["直角书桌", "L型书桌", "升降书桌"],
                "sizes": {"宽度": "1000-1600mm", "深度": "500-800mm", "高度": "720-760mm"},
                "features": ["走线孔", "抽屉", "键盘托"]
            }, "aliases": ["办公桌", "电脑桌"]},
            {"name": "床头柜", "properties": {
                "sizes": {"宽度": "400-600mm", "深度": "400-500mm", "高度": "与床垫齐平"},
                "features": ["抽屉", "开放格", "USB充电"]
            }, "aliases": []},
        ],

        # 椅子类
        EntityType.CHAIR: [
            {"name": "餐椅", "properties": {
                "materials": ["实木", "金属", "塑料", "布艺", "皮革"],
                "height": "450mm",
                "seat_height": "430-450mm"
            }, "aliases": []},
            {"name": "办公椅", "properties": {
                "types": ["人体工学椅", "老板椅", "职员椅", "会议椅"],
                "features": ["升降", "扶手", "头枕", "腰托"],
                "brands": ["Herman Miller", "Steelcase", "西昊", "永艺"]
            }, "aliases": ["电脑椅"]},
            {"name": "休闲椅", "properties": {
                "types": ["单人沙发椅", "摇椅", "躺椅", "吊椅"],
                "materials": ["布艺", "皮革", "藤编", "金属"]
            }, "aliases": ["单椅"]},
            {"name": "吧椅", "properties": {
                "height": "650-850mm",
                "features": ["升降", "脚踏"],
                "applications": ["吧台", "岛台"]
            }, "aliases": ["高脚椅"]},
            {"name": "儿童椅", "properties": {
                "types": ["学习椅", "餐椅", "成长椅"],
                "features": ["可调节", "安全设计"],
                "brands": ["护童", "黑白调", "西昊"]
            }, "aliases": []},
            {"name": "梳妆椅", "properties": {
                "materials": ["布艺", "皮革", "实木"],
                "height": "400-450mm"
            }, "aliases": ["化妆椅"]},
            # 经典设计师椅
            {"name": "伊姆斯椅", "properties": {
                "designer": "Charles & Ray Eames",
                "year": "1950",
                "materials": ["塑料", "木腿"],
                "style": "北欧/现代",
                "features": ["人体工学", "经典设计"]
            }, "aliases": ["Eames Chair", "伊姆斯餐椅"]},
            {"name": "Y椅", "properties": {
                "designer": "Hans Wegner",
                "year": "1950",
                "materials": ["实木", "纸绳编织"],
                "style": "北欧",
                "features": ["Y型靠背", "手工编织座面"]
            }, "aliases": ["Wishbone Chair", "叉骨椅"]},
            {"name": "蛋椅", "properties": {
                "designer": "Arne Jacobsen",
                "year": "1958",
                "materials": ["玻璃钢", "皮革/布艺"],
                "style": "现代",
                "features": ["包裹感", "私密空间"]
            }, "aliases": ["Egg Chair"]},
            {"name": "蝴蝶椅", "properties": {
                "designer": "Bonet/Kurchan/Ferrari-Hardoy",
                "year": "1938",
                "materials": ["金属框架", "皮革/帆布"],
                "style": "现代/工业",
                "features": ["轻便", "可折叠"]
            }, "aliases": ["BKF Chair", "Butterfly Chair"]},
        ],

        # 儿童家具
        EntityType.CHILDREN_FURNITURE: [
            {"name": "婴儿床", "properties": {
                "sizes": {"标准": "1200×650mm", "加大": "1400×700mm"},
                "materials": ["实木", "松木", "榉木"],
                "features": ["可调节高度", "护栏", "滚轮"],
                "safety": ["无尖角", "环保漆", "护栏间距<6cm"]
            }, "aliases": ["宝宝床"]},
            {"name": "儿童单人床", "properties": {
                "sizes": ["1200×2000mm", "1350×2000mm", "1500×2000mm"],
                "materials": ["实木", "板材"],
                "features": ["护栏", "储物抽屉"]
            }, "aliases": []},
            {"name": "高低床", "properties": {
                "types": ["上下铺", "L型", "错位式"],
                "materials": ["实木", "金属"],
                "safety": ["护栏高度≥30cm", "梯子防滑"],
                "suitable_age": "6岁以上"
            }, "aliases": ["双层床", "上下床"]},
            {"name": "半高床", "properties": {
                "height": "1000-1200mm",
                "features": ["下方储物空间", "书桌组合"],
                "suitable_age": "4-10岁"
            }, "aliases": []},
            {"name": "子母床", "properties": {
                "structure": "主床+抽拉床",
                "features": ["节省空间", "灵活使用"]
            }, "aliases": ["拖床"]},
            {"name": "成长床", "properties": {
                "features": ["可延长", "可调节高度", "陪伴成长"],
                "length_range": "1200-2000mm",
                "brands": ["芙莱莎", "松堡王国"]
            }, "aliases": ["可延长床"]},
            {"name": "可升降书桌", "properties": {
                "height_range": "530-760mm",
                "features": ["手摇升降", "电动升降", "倾斜桌面"],
                "desktop_size": "1000-1200×600mm",
                "brands": ["护童", "黑白调", "乐歌"]
            }, "aliases": ["学习桌", "儿童书桌"]},
            {"name": "可升降座椅", "properties": {
                "height_range": "380-530mm",
                "features": ["坐深可调", "靠背可调", "脚踏"],
                "brands": ["护童", "西昊", "黑白调"]
            }, "aliases": ["学习椅", "成长椅"]},
            {"name": "儿童衣柜", "properties": {
                "height": "1200-1600mm",
                "features": ["低矮设计", "圆角处理", "分区合理"],
                "materials": ["实木", "环保板材"]
            }, "aliases": []},
            {"name": "玩具收纳柜", "properties": {
                "types": ["开放式", "抽屉式", "组合式"],
                "materials": ["塑料", "布艺", "实木"],
                "features": ["分类收纳", "易取放"]
            }, "aliases": ["玩具柜"]},
            {"name": "绘本架", "properties": {
                "types": ["落地式", "壁挂式", "旋转式"],
                "materials": ["实木", "铁艺", "塑料"],
                "features": ["展示封面", "方便取阅"]
            }, "aliases": ["书架"]},
            {"name": "儿童收纳箱", "properties": {
                "materials": ["塑料", "布艺", "藤编"],
                "features": ["轻便", "可折叠", "带盖"]
            }, "aliases": []},
        ],

        # 收纳家具
        EntityType.STORAGE: [
            {"name": "鞋柜", "properties": {
                "types": ["翻斗式", "平开门", "百叶门", "玄关柜"],
                "depth": "150-350mm",
                "features": ["透气", "分层可调"]
            }, "aliases": []},
            {"name": "餐边柜", "properties": {
                "types": ["矮柜", "高柜", "酒柜组合"],
                "materials": ["实木", "板材", "岩板"],
                "features": ["储物", "展示", "台面操作"]
            }, "aliases": ["备餐柜"]},
            {"name": "电视柜", "properties": {
                "types": ["落地式", "悬挂式", "组合式"],
                "materials": ["实木", "板材", "岩板"],
                "features": ["走线孔", "储物空间"]
            }, "aliases": []},
            {"name": "斗柜", "properties": {
                "drawers": "3-6抽",
                "materials": ["实木", "板材"],
                "applications": ["卧室", "玄关", "客厅"]
            }, "aliases": ["抽屉柜"]},
            {"name": "书柜", "properties": {
                "types": ["开放式", "玻璃门", "组合式"],
                "depth": "250-350mm",
                "materials": ["实木", "板材"]
            }, "aliases": []},
            {"name": "展示柜", "properties": {
                "types": ["玻璃柜", "博古架", "壁龛"],
                "features": ["灯光", "玻璃门", "镜面背板"]
            }, "aliases": []},
        ],

        # ==================== 十、水电暖通 ====================
        EntityType.ELECTRICAL: [
            {"name": "电线", "properties": {
                "types": {"BV线": "单股铜芯硬线", "BVR线": "多股铜芯软线"},
                "specs": {
                    "1.5mm²": "照明回路",
                    "2.5mm²": "普通插座",
                    "4mm²": "空调/厨房",
                    "6mm²": "大功率电器",
                    "10mm²": "入户主线"
                },
                "flame_retardant": ["ZA", "ZB", "ZC", "WDZN"],
                "brands": {"一线": ["远东", "宝胜"], "二线": ["正泰", "德力西"]}
            }, "aliases": ["电缆"]},
            {"name": "开关插座", "properties": {
                "specs": {"86型": "86×86mm主流", "118型": "模块化组合"},
                "switch_types": ["单控", "双控", "多控", "调光", "智能"],
                "socket_types": ["五孔", "七孔", "USB", "Type-C", "16A空调", "防水", "地插"],
                "brands": {"高端": ["西门子", "施耐德", "罗格朗", "ABB"], "中端": ["西蒙", "松下", "公牛"]}
            }, "aliases": []},
            {"name": "配电箱", "properties": {
                "circuits": "12/16/20/24/32路",
                "breakers": {
                    "MCB": {"1P": "单极", "1P+N": "单极+零线", "2P": "双极"},
                    "RCBO": {"漏电电流": "30mA", "动作时间": "≤0.1s"}
                },
                "brands": {"高端": ["ABB", "施耐德", "西门子"], "国产": ["正泰", "德力西"]}
            }, "aliases": ["空开", "断路器"]},
            {"name": "网线", "properties": {
                "grades": {
                    "超五类Cat5e": "100Mbps",
                    "六类Cat6": "1Gbps",
                    "超六类Cat6a": "10Gbps",
                    "七类Cat7": "10Gbps+"
                },
                "types": {"UTP": "非屏蔽", "STP": "屏蔽", "FTP": "铝箔屏蔽"},
                "brands": ["安普", "康普", "泛达"]
            }, "aliases": ["网络线", "双绞线"]},
            {"name": "智能开关", "properties": {
                "protocols": ["WiFi", "Zigbee", "蓝牙Mesh", "有线总线"],
                "features": ["远程控制", "定时开关", "场景联动", "语音控制"],
                "brands": {"高端": ["Aqara", "小米", "涂鸦"], "传统": ["西门子", "施耐德"]}
            }, "aliases": ["智能面板"]},
            {"name": "漏电保护器", "properties": {
                "action_current": "30mA",
                "action_time": "≤0.1s",
                "types": ["1P+N", "2P"],
                "application": ["卫生间", "厨房", "插座回路"]
            }, "aliases": ["漏保", "RCBO"]},
        ],

        EntityType.PLUMBING: [
            {"name": "PPR管", "properties": {
                "material": "无规共聚聚丙烯",
                "specs": {"S5": "冷水", "S4": "冷热水", "S3.2": "热水", "S2.5": "高温"},
                "diameters": "20/25/32/40/50/63mm",
                "common": "20mm(4分)/25mm(6分)",
                "connection": "热熔连接",
                "brands": {"进口": ["德国洁水", "土耳其皮尔萨"], "国产": ["伟星", "日丰", "金德", "联塑"]}
            }, "aliases": ["水管"]},
            {"name": "PVC排水管", "properties": {
                "specs": {"50mm": "洗手盆/地漏", "75mm": "厨房/洗衣机", "110mm": "马桶/主排污", "160mm": "主立管"},
                "wall_thickness": {"普通": "2.0-3.2mm", "加厚": "3.5-4.0mm"},
                "connection": "胶粘",
                "brands": ["联塑", "伟星", "公元"]
            }, "aliases": ["排水管"]},
            {"name": "不锈钢水管", "properties": {
                "material": "304/316不锈钢",
                "connection": ["卡压式", "环压式", "双卡压式"],
                "pros": ["强度高", "耐高温", "卫生"],
                "cons": ["价格高", "施工要求高"]
            }, "aliases": []},
            {"name": "铜管", "properties": {
                "material": ["紫铜", "黄铜"],
                "connection": ["焊接", "卡压"],
                "pros": ["杀菌", "耐用"],
                "cons": ["价格高"]
            }, "aliases": ["铜水管"]},
            {"name": "PEX管", "properties": {
                "full_name": "交联聚乙烯管",
                "types": ["PEX-a", "PEX-b", "PEX-c"],
                "features": ["柔韧性好", "耐高温"],
                "application": "地暖管道"
            }, "aliases": ["交联聚乙烯管"]},
            {"name": "铝塑复合管", "properties": {
                "structure": "塑料+铝+塑料",
                "connection": "卡套式",
                "application": "燃气管道"
            }, "aliases": ["铝塑管"]},
            {"name": "HDPE静音排水管", "properties": {
                "features": ["静音", "柔韧"],
                "connection": ["热熔", "电熔"],
                "application": "高端住宅"
            }, "aliases": ["静音管"]},
            {"name": "角阀", "properties": {
                "function": "控制水流/便于维修",
                "materials": ["全铜", "不锈钢", "锌合金"],
                "specs": ["4分(1/2\")", "6分(3/4\")"]
            }, "aliases": ["三角阀"]},
            {"name": "球阀", "properties": {
                "function": "开关控制",
                "materials": ["铜", "不锈钢", "PPR"],
                "features": ["开关迅速", "密封性好"]
            }, "aliases": []},
            {"name": "止回阀", "properties": {
                "function": "防止水流倒流",
                "types": ["旋启式", "升降式", "蝶式"],
                "application": ["热水器出水口", "水泵出口"]
            }, "aliases": ["单向阀", "逆止阀"]},
            {"name": "减压阀", "properties": {
                "function": "稳定水压",
                "setting_range": "1.5-3.5bar",
                "application": "高层住宅入户"
            }, "aliases": ["稳压阀"]},
        ],

        EntityType.HVAC: [
            {"name": "水地暖", "properties": {
                "components": ["热源壁挂炉", "分集水器", "地暖管", "保温层", "反射膜", "回填层"],
                "pipe_types": ["PE-RT管", "PEX管", "铝塑管"],
                "pipe_spacing": "150-200mm",
                "insulation": {"material": "挤塑板XPS", "thickness": "20-30mm"},
                "pros": ["舒适", "节能"],
                "cons": ["升温慢", "层高占用"]
            }, "aliases": ["地暖"]},
            {"name": "暖气片", "properties": {
                "materials": {
                    "钢制": {"types": ["柱式", "板式"], "note": "需满水保养"},
                    "铜铝复合": {"structure": "铜管+铝翅片", "features": ["耐腐蚀", "散热快"], "note": "主流选择"}
                },
                "install": ["明装", "暗装"],
                "brands": {"进口": ["德美拉得", "意莎普"], "国产": ["森德", "努奥罗"]}
            }, "aliases": ["散热器"]},
            {"name": "壁挂炉", "properties": {
                "types": ["常规壁挂炉", "冷凝壁挂炉", "两用炉"],
                "power_selection": {"18kW": "100㎡以下", "24kW": "100-150㎡", "28kW": "150-200㎡", "35kW": "200㎡以上"},
                "brands": {"进口": ["威能", "博世", "菲斯曼", "阿里斯顿"], "国产": ["万和", "万家乐", "海尔"]}
            }, "aliases": []},
            {"name": "中央空调", "properties": {
                "types": {
                    "多联机": {"principle": "一拖多氟系统", "brands": ["大金", "日立", "三菱电机", "东芝"]},
                    "风管机": {"principle": "一拖一", "brands": ["格力", "美的"]},
                    "水系统": {"principle": "冷热水循环", "brands": ["特灵", "约克", "开利"]}
                },
                "energy_efficiency": {"一级": "≥3.6", "二级": "3.4-3.6", "三级": "3.2-3.4"}
            }, "aliases": []},
            {"name": "新风系统", "properties": {
                "types": ["单向流", "双向流", "全热交换"],
                "heat_recovery": "60-80%",
                "install": ["吊顶式", "柜式", "壁挂式"],
                "airflow_calc": "人数×30或面积×1",
                "filter_grades": {"初效G4": "粗过滤", "中效F7-F9": "细颗粒", "高效H13": "HEPA级"},
                "brands": {"进口": ["松下", "大金", "霍尼韦尔", "兰舍"], "国产": ["远大", "绿岛风"]}
            }, "aliases": ["新风机"]},
            {"name": "电地暖", "properties": {
                "types": ["发热电缆", "电热膜", "碳纤维发热"],
                "pros": ["升温快", "控制精准", "无需锅炉"],
                "cons": ["运行成本高"],
                "application": ["小面积", "局部采暖"]
            }, "aliases": []},
            {"name": "干式地暖", "properties": {
                "features": ["无需回填", "薄"],
                "thickness": "30-40mm",
                "application": "层高受限场合"
            }, "aliases": ["薄型地暖"]},
            {"name": "分集水器", "properties": {
                "function": "地暖水流分配",
                "materials": ["铜", "不锈钢", "PPR"],
                "components": ["分水器", "集水器", "排气阀", "泄水阀"]
            }, "aliases": ["地暖分水器", "分水器"]},
            {"name": "温控器", "properties": {
                "types": ["机械式", "电子式", "智能WiFi"],
                "features": ["定时", "分区控制", "远程控制"],
                "brands": ["海林", "曼瑞德", "西门子"]
            }, "aliases": ["地暖温控"]},
            {"name": "踢脚线暖气", "properties": {
                "principle": "沿墙脚安装的条形散热器",
                "height": "10-15cm",
                "features": ["不占空间", "均匀散热", "美观隐蔽"],
                "types": ["水暖踢脚线", "电暖踢脚线"],
                "applications": ["老房改造", "层高受限", "落地窗"],
                "brands": ["德国银屋", "瑞特格"]
            }, "aliases": ["踢脚线采暖", "踢脚暖"]},
            # 热水系统
            {"name": "燃气热水器", "properties": {
                "types": ["强排式", "平衡式", "冷凝式"],
                "capacity": {"13L": "一厨一卫", "16L": "一厨两卫", "20L+": "大户型"},
                "features": ["恒温", "零冷水", "防冻"],
                "brands": ["林内", "能率", "万和", "万家乐"]
            }, "aliases": []},
            {"name": "电热水器", "properties": {
                "types": {"储水式": {"容量": "40-100L", "功率": "1500-3000W"}, "即热式": {"功率": "6000-8500W"}},
                "inner_tank": ["搪瓷内胆", "不锈钢内胆", "钛金内胆"],
                "brands": ["A.O.史密斯", "海尔", "美的"]
            }, "aliases": []},
            {"name": "空气能热水器", "properties": {
                "principle": "空气源热泵",
                "cop": "3-4",
                "pros": ["节能"],
                "cons": ["初投资高", "占空间"],
                "brands": ["美的", "格力", "纽恩泰"]
            }, "aliases": ["热泵热水器"]},
            {"name": "太阳能热水器", "properties": {
                "types": ["真空管式", "平板式"],
                "suitable": ["别墅", "顶楼"],
                "features": ["节能环保", "依赖天气"]
            }, "aliases": []},
            # 暖气片细分类型
            {"name": "钢制暖气片", "properties": {
                "types": ["钢制柱式", "钢制板式"],
                "features": ["散热快", "价格适中"],
                "cons": ["需满水保养", "易腐蚀"],
                "applications": ["集中供暖", "独立采暖"]
            }, "aliases": ["钢制散热器"]},
            {"name": "铜铝复合暖气片", "properties": {
                "structure": "铜管+铝翅片",
                "features": ["耐腐蚀", "散热快", "寿命长"],
                "pros": ["无需满水保养", "适应性强"],
                "applications": ["独立采暖", "集中供暖"],
                "note": "主流选择"
            }, "aliases": ["铜铝散热器"]},
            # 中央空调细分类型
            {"name": "多联机", "properties": {
                "principle": "一拖多氟系统",
                "features": ["节能", "控制灵活", "安装方便"],
                "cons": ["舒适度一般", "维修成本高"],
                "brands": {"日系": ["大金", "日立", "三菱电机", "东芝"], "国产": ["格力", "美的"]},
                "application": "家用/小型商用"
            }, "aliases": ["VRV", "VRF"]},
            {"name": "风管机", "properties": {
                "principle": "一拖一",
                "features": ["性价比高", "安装简单"],
                "cons": ["每个房间需独立外机"],
                "brands": ["格力", "美的", "海尔"],
                "application": "单个房间/小户型"
            }, "aliases": ["一拖一空调"]},
            {"name": "水系统中央空调", "properties": {
                "principle": "冷热水循环",
                "features": ["舒适度高", "不干燥"],
                "cons": ["造价高", "维护复杂"],
                "brands": ["特灵", "约克", "开利", "麦克维尔"],
                "application": "别墅/大户型"
            }, "aliases": ["水机", "风机盘管"]},
            # 新风系统细分类型
            {"name": "全热交换新风", "properties": {
                "principle": "热回收+湿度回收",
                "heat_recovery": "60-80%",
                "features": ["节能", "舒适", "冬暖夏凉"],
                "applications": ["北方地区", "全年使用"],
                "brands": ["松下", "大金", "霍尼韦尔"]
            }, "aliases": ["全热交换器", "ERV"]},
            {"name": "冷凝壁挂炉", "properties": {
                "principle": "回收烟气余热",
                "efficiency": "≥100%",
                "features": ["节能15-20%", "环保", "低排放"],
                "cons": ["价格较高"],
                "brands": ["威能", "博世", "菲斯曼"]
            }, "aliases": ["冷凝炉"]},
        ],

        # 风格实体
        EntityType.STYLE: [
            {"name": "现代简约", "properties": {
                "keywords": ["简洁", "线条", "功能", "去繁就简"],
                "budget_level": "中等",
                "colors": {"主色": "白/灰/黑", "辅色": "原木色", "点缀": "金属色"},
                "materials": ["乳胶漆", "木饰面", "岩板", "金属"]
            }, "aliases": ["简约风", "现代风"]},
            {"name": "北欧", "properties": {
                "keywords": ["自然", "温馨", "原木", "明亮通透"],
                "budget_level": "中等",
                "colors": {"主色": "白色", "辅色": "原木色/浅灰", "点缀": "莫兰迪色系"},
                "materials": ["白色乳胶漆", "原木", "棉麻布艺", "皮革"],
                "elements": ["大面积白墙", "木质家具", "绿植", "几何图案"]
            }, "aliases": ["北欧风", "斯堪的纳维亚"]},
            {"name": "新中式", "properties": {
                "keywords": ["传统", "文化", "禅意", "东方意境"],
                "budget_level": "中高",
                "colors": {"主色": "黑/白/灰/原木", "辅色": "中国红/靛蓝"},
                "materials": ["木饰面", "大理石", "黄铜", "棉麻"],
                "elements": ["简化格栅", "山水画", "禅意摆件", "茶具"]
            }, "aliases": ["中式", "现代中式"]},
            {"name": "轻奢", "properties": {
                "keywords": ["品质", "金属", "大理石", "低调奢华"],
                "budget_level": "较高",
                "colors": {"主色": "灰/米/驼", "辅色": "黑/白", "点缀": "金/铜/银"},
                "materials": ["大理石/岩板", "皮革", "金属", "玻璃", "绒布"],
                "elements": ["金属线条", "皮质家具", "水晶灯饰"]
            }, "aliases": ["轻奢风", "现代轻奢"]},
            {"name": "工业风", "properties": {
                "keywords": ["水泥", "铁艺", "裸露", "粗犷质感"],
                "budget_level": "中等",
                "colors": {"主色": "灰/黑/棕"},
                "materials": ["水泥/混凝土", "红砖", "金属管道", "做旧木材"],
                "elements": ["裸露管线", "铁艺家具", "复古灯具"]
            }, "aliases": ["工业", "loft"]},
            {"name": "日式", "properties": {
                "keywords": ["原木", "禅意", "收纳", "空间留白"],
                "budget_level": "中等",
                "colors": {"主色": "原木色/米白", "辅色": "浅灰/浅绿"},
                "materials": ["原木", "竹", "藤", "棉麻", "和纸", "榻榻米"],
                "elements": ["障子门", "榻榻米", "地台", "枯山水"]
            }, "aliases": ["日式风", "和风", "muji风"]},
            {"name": "美式", "properties": {
                "keywords": ["复古", "舒适", "大气", "自由随性"],
                "budget_level": "中高",
                "colors": {"主色": "米/棕/蓝/绿"},
                "materials": ["实木", "皮革", "布艺"],
                "elements": ["壁炉", "护墙板", "皮沙发", "实木家具"]
            }, "aliases": ["美式风", "美式乡村"]},
            {"name": "欧式", "properties": {
                "keywords": ["华丽", "雕花", "对称", "宫廷气派"],
                "budget_level": "较高",
                "colors": {"主色": "金色/米白/深棕"},
                "elements": ["罗马柱", "石膏线", "壁炉", "水晶吊灯", "油画"]
            }, "aliases": ["欧式风", "古典欧式"]},
            # 新增风格
            {"name": "法式", "properties": {
                "keywords": ["浪漫", "优雅", "精致", "艺术气息"],
                "budget_level": "较高",
                "colors": {"主色": "白/米/灰蓝"},
                "elements": ["石膏线", "护墙板", "壁炉", "水晶灯", "鲜花"],
                "sub_styles": ["法式宫廷", "法式乡村", "现代法式"]
            }, "aliases": ["法式风", "法式风格"]},
            {"name": "地中海", "properties": {
                "keywords": ["蓝白色调", "拱形元素", "海洋气息"],
                "budget_level": "中等",
                "colors": {"主色": "蓝/白/黄"},
                "elements": ["拱门", "马赛克", "铁艺", "陶罐"]
            }, "aliases": ["地中海风", "地中海风格"]},
            {"name": "东南亚", "properties": {
                "keywords": ["热带风情", "自然材质", "异域情调"],
                "budget_level": "中等",
                "colors": {"主色": "棕/绿/金"},
                "materials": ["藤", "竹", "麻", "柚木", "热带植物"]
            }, "aliases": ["东南亚风", "东南亚风格"]},
            {"name": "混搭", "properties": {
                "keywords": ["多元融合", "个性表达", "打破常规"],
                "budget_level": "中等",
                "principles": ["色彩统一", "材质协调", "主次分明"]
            }, "aliases": ["混搭风", "混搭风格"]},
            {"name": "奶油风", "properties": {
                "keywords": ["柔和温暖", "低饱和度", "治愈系"],
                "budget_level": "中等",
                "colors": {"主色": "奶白/奶咖/奶茶", "辅色": "米/杏/驼"},
                "materials": ["弧形元素", "绒布", "木质"]
            }, "aliases": ["奶油风格"]},
            {"name": "极简主义", "properties": {
                "keywords": ["极度简化", "留白", "隐藏收纳", "无把手设计"],
                "budget_level": "中高",
                "colors": {"主色": "黑白灰"},
                "sub_styles": ["日本极简", "北欧极简"]
            }, "aliases": ["极简风", "极简"]},
            {"name": "中古风", "properties": {
                "keywords": ["1950-1970年代", "有机曲线", "经典家具"],
                "budget_level": "中高",
                "era": "Mid-Century Modern"
            }, "aliases": ["中古风格", "复古风"]},
            {"name": "简欧", "properties": {
                "keywords": ["简化古典", "保留线条", "现代实用"],
                "budget_level": "中高",
                "colors": {"主色": "米白/象牙白"},
                "elements": ["简化石膏线", "护墙板", "欧式家具"]
            }, "aliases": ["简欧风", "简欧风格"]},
            {"name": "侘寂风", "properties": {
                "keywords": ["不完美之美", "自然老化", "朴素材质"],
                "budget_level": "中等",
                "philosophy": "Wabi-sabi"
            }, "aliases": ["侘寂", "wabi-sabi"]},
            {"name": "传统中式", "properties": {
                "keywords": ["对称布局", "雕梁画栋", "红木家具", "文化底蕴"],
                "budget_level": "高",
                "colors": {"主色": "红/棕/黑", "辅色": "金/米"},
                "materials": ["红木", "花梨木", "紫檀", "丝绸/锦缎"],
                "elements": ["屏风", "博古架", "圈椅/官帽椅", "青花瓷", "书画"]
            }, "aliases": ["古典中式", "中式古典"]},
        ],

        # 空间实体
        EntityType.SPACE: [
            {"name": "客厅", "properties": {"function": "会客休闲", "importance": "高"},
             "aliases": ["起居室", "大厅"]},
            {"name": "卧室", "properties": {"function": "休息睡眠", "importance": "高"},
             "aliases": ["主卧", "次卧", "房间"]},
            {"name": "厨房", "properties": {"function": "烹饪", "importance": "高"},
             "aliases": ["厨房间"]},
            {"name": "卫生间", "properties": {"function": "洗漱如厕", "importance": "高"},
             "aliases": ["浴室", "洗手间", "厕所"]},
            {"name": "阳台", "properties": {"function": "晾晒休闲", "importance": "中"},
             "aliases": ["露台", "生活阳台"]},
            {"name": "书房", "properties": {"function": "工作学习", "importance": "中"},
             "aliases": ["办公室", "工作间"]},
            {"name": "餐厅", "properties": {"function": "用餐", "importance": "中"},
             "aliases": ["饭厅"]},
            {"name": "玄关", "properties": {"function": "过渡收纳", "importance": "中"},
             "aliases": ["门厅", "入户"]},
            {"name": "儿童房", "properties": {"function": "儿童起居", "importance": "中"},
             "aliases": ["小孩房"]},
            {"name": "走廊", "properties": {"function": "通行连接", "importance": "低"},
             "aliases": ["过道", "通道"]},
            {"name": "衣帽间", "properties": {
                "function": "衣物收纳",
                "importance": "中",
                "types": ["步入式衣帽间", "开放式衣帽间", "嵌入式衣帽间"],
                "min_area": "4㎡以上",
                "features": ["分区收纳", "试衣镜", "梳妆台"]
            }, "aliases": ["步入式衣柜", "更衣室"]},
            {"name": "储物间", "properties": {
                "function": "杂物收纳",
                "importance": "低",
                "features": ["置物架", "收纳柜"]
            }, "aliases": ["杂物间", "储藏室"]},
            {"name": "茶室", "properties": {
                "function": "品茶休闲",
                "importance": "低",
                "style": ["中式", "日式"],
                "features": ["茶桌", "茶具收纳", "静谧氛围"]
            }, "aliases": ["茶房"]},
        ],

        # 工序实体
        EntityType.PROCESS: [
            {"name": "收房验房", "properties": {
                "order": 0, "stage": "前期准备",
                "check_items": ["墙面空鼓", "门窗密封", "水电通畅", "防水测试", "面积核实"],
                "tools": ["空鼓锤", "水平尺", "卷尺"]
            }, "aliases": ["验房"]},
            {"name": "设计阶段", "properties": {
                "order": 0.5, "stage": "前期准备",
                "outputs": ["平面方案", "效果图", "施工图", "预算报价"]
            }, "aliases": ["设计"]},
            {"name": "拆改", "properties": {
                "order": 1, "duration": "1-2周", "stage": "施工阶段",
                "tasks": ["主体拆除", "新建墙体"],
                "notes": ["承重墙不能拆", "物业报备", "垃圾清运"]
            }, "aliases": ["拆除", "墙体改造"]},
            {"name": "水电改造", "properties": {
                "order": 2, "duration": "5-10天", "stage": "施工阶段",
                "tasks": ["水电定位", "开槽", "布管布线", "封槽"],
                "verification": ["打压测试", "通电测试", "拍照留档"],
                "standards": {"强弱电间距": "≥30cm", "管内穿线": "≤40%"}
            }, "aliases": ["水电", "布线"]},
            {"name": "防水", "properties": {
                "order": 3, "duration": "3-5天", "stage": "施工阶段",
                "areas": ["卫生间", "厨房", "阳台"],
                "height": {"卫生间淋浴区": "1.8m", "其他区域": "0.3m", "厨房": "0.3m"},
                "verification": "闭水试验48小时"
            }, "aliases": ["防水施工", "闭水试验"]},
            {"name": "瓦工", "properties": {
                "order": 4, "duration": "2-3周", "stage": "施工阶段",
                "tasks": ["墙地砖铺贴", "过门石", "窗台石", "地漏安装"],
                "standards": {"空鼓率墙砖": "≤5%", "空鼓率地砖": "≤3%", "平整度": "≤2mm"}
            }, "aliases": ["贴砖", "泥工"]},
            {"name": "木工", "properties": {
                "order": 5, "duration": "1-2周", "stage": "施工阶段",
                "tasks": ["吊顶", "背景墙", "窗套门套"],
                "materials": ["石膏板", "木龙骨", "轻钢龙骨"]
            }, "aliases": ["吊顶", "木作"]},
            {"name": "油漆", "properties": {
                "order": 6, "duration": "2-3周", "stage": "施工阶段",
                "tasks": ["墙面处理", "刮腻子", "打磨", "刷漆"],
                "process": ["基层处理", "刮腻子2-3遍", "打磨", "底漆1遍", "面漆2遍"],
                "standards": {"平整度": "≤3mm", "阴阳角": "垂直方正"}
            }, "aliases": ["刷漆", "墙面处理"]},
            {"name": "安装", "properties": {
                "order": 7, "duration": "1-2周", "stage": "施工阶段",
                "items": ["橱柜", "木门", "地板", "开关插座", "灯具", "洁具", "五金"],
                "sequence": "先上后下，先里后外"
            }, "aliases": ["主材安装", "设备安装"]},
            {"name": "软装", "properties": {
                "order": 8, "duration": "1周", "stage": "收尾阶段",
                "items": ["家具", "窗帘", "灯饰", "地毯", "装饰画", "绿植"],
                "tips": ["通风除醛", "家具进场顺序"]
            }, "aliases": ["软装布置", "家具进场"]},
            {"name": "竣工验收", "properties": {
                "order": 9, "stage": "收尾阶段",
                "check_items": ["水电验收", "防水验收", "瓷砖验收", "墙面验收", "木工验收"],
                "documents": ["竣工图纸", "保修卡", "使用说明"]
            }, "aliases": ["验收", "交付"]},
            # 细分工程
            {"name": "防水工程", "properties": {
                "stage": "施工阶段",
                "areas": {"卫生间": "必做", "厨房": "建议", "阳台": "建议", "地下室": "必做"},
                "materials": ["聚氨酯防水涂料", "JS防水涂料", "K11防水涂料", "丙纶布"],
                "process": ["基层处理", "涂刷防水涂料2-3遍", "闭水试验", "保护层"],
                "standards": {"涂刷厚度": "≥1.5mm", "闭水时间": "48小时", "水深": "≥20mm"},
                "key_points": ["阴阳角圆弧处理", "管道根部加强", "门槛石挡水"]
            }, "aliases": ["做防水"]},
            {"name": "吊顶工程", "properties": {
                "stage": "施工阶段",
                "types": ["平顶", "跌级吊顶", "悬浮吊顶", "造型吊顶"],
                "materials": ["石膏板", "轻钢龙骨", "木龙骨", "铝扣板", "蜂窝大板"],
                "process": ["弹线定位", "安装龙骨", "安装面板", "嵌缝处理"],
                "standards": {"平整度": "≤3mm", "接缝": "V型槽处理", "龙骨间距": "400mm"},
                "key_points": ["预留检修口", "灯具预埋", "新风管道预留"]
            }, "aliases": ["做吊顶", "天花工程"]},
            {"name": "地暖工程", "properties": {
                "stage": "施工阶段",
                "types": ["水地暖", "电地暖", "干式地暖", "湿式地暖"],
                "components": ["保温板", "反射膜", "地暖管/发热电缆", "分集水器", "回填层"],
                "process": ["铺设保温层", "铺设反射膜", "铺设地暖管", "打压测试", "回填找平"],
                "standards": {"管间距": "15-20cm", "打压压力": "0.6MPa", "回填厚度": "3-5cm"}
            }, "aliases": ["铺地暖"]},
            {"name": "中央空调工程", "properties": {
                "stage": "施工阶段",
                "timing": "水电改造后、吊顶前",
                "components": ["室外机", "室内机", "铜管", "冷凝水管", "风口"],
                "process": ["设备定位", "打孔", "安装内机", "铺设管道", "安装外机", "调试"],
                "key_points": ["内机位置", "检修口预留", "冷凝水排放", "风口位置"]
            }, "aliases": ["装中央空调"]},
        ],

        # 工具实体
        EntityType.TOOL: [
            # 验房工具
            {"name": "空鼓锤", "properties": {
                "usage": "检测墙面/地面空鼓",
                "stage": "收房验房"
            }, "aliases": ["空鼓锤子"]},
            {"name": "水平尺", "properties": {
                "usage": "检测水平度/垂直度",
                "types": ["气泡水平尺", "激光水平仪"],
                "stage": "收房验房"
            }, "aliases": ["水平仪"]},
            {"name": "卷尺", "properties": {
                "usage": "测量尺寸",
                "types": ["钢卷尺", "激光测距仪"],
                "stage": "收房验房"
            }, "aliases": ["测距仪"]},
            {"name": "相位检测仪", "properties": {
                "usage": "检测插座接线是否正确",
                "stage": "收房验房"
            }, "aliases": ["验电器"]},
            # 水电工具
            {"name": "开槽机", "properties": {
                "usage": "墙面/地面开槽",
                "stage": "水电改造"
            }, "aliases": ["切割机"]},
            {"name": "热熔机", "properties": {
                "usage": "PPR管热熔连接",
                "stage": "水电改造"
            }, "aliases": ["热熔器"]},
            {"name": "打压泵", "properties": {
                "usage": "水管打压测试",
                "pressure": "0.8MPa",
                "stage": "水电改造"
            }, "aliases": ["试压泵"]},
            {"name": "穿线器", "properties": {
                "usage": "电线穿管",
                "stage": "水电改造"
            }, "aliases": []},
            # 瓦工工具
            {"name": "瓷砖切割机", "properties": {
                "types": ["手动切割机", "电动切割机", "水刀切割"],
                "stage": "瓦工"
            }, "aliases": ["切砖机"]},
            {"name": "抹子", "properties": {
                "usage": "涂抹水泥砂浆",
                "types": ["木抹子", "铁抹子", "塑料抹子"],
                "stage": "瓦工"
            }, "aliases": ["抹刀"]},
            {"name": "橡皮锤", "properties": {
                "usage": "敲击瓷砖找平",
                "stage": "瓦工"
            }, "aliases": ["橡胶锤"]},
            {"name": "十字定位器", "properties": {
                "usage": "控制瓷砖缝隙",
                "sizes": ["1mm", "1.5mm", "2mm", "3mm"],
                "stage": "瓦工"
            }, "aliases": ["找平器"]},
            # 木工工具
            {"name": "电钻", "properties": {
                "types": ["冲击钻", "电锤", "手电钻"],
                "stage": "木工"
            }, "aliases": ["冲击钻"]},
            {"name": "电锯", "properties": {
                "types": ["圆锯", "曲线锯", "往复锯"],
                "stage": "木工"
            }, "aliases": []},
            {"name": "气钉枪", "properties": {
                "usage": "固定石膏板/木板",
                "stage": "木工"
            }, "aliases": ["射钉枪"]},
            # 油漆工具
            {"name": "批刀", "properties": {
                "usage": "批刮腻子",
                "sizes": ["200mm", "300mm", "500mm"],
                "stage": "油漆"
            }, "aliases": ["刮刀"]},
            {"name": "砂纸", "properties": {
                "usage": "打磨墙面",
                "grits": ["80目", "120目", "180目", "240目", "320目"],
                "stage": "油漆"
            }, "aliases": ["砂布"]},
            {"name": "滚筒", "properties": {
                "usage": "涂刷乳胶漆",
                "types": ["短毛滚筒", "中毛滚筒", "长毛滚筒"],
                "stage": "油漆"
            }, "aliases": ["滚刷"]},
            {"name": "喷枪", "properties": {
                "usage": "喷涂乳胶漆/木器漆",
                "types": ["无气喷涂", "有气喷涂"],
                "stage": "油漆"
            }, "aliases": ["喷涂机"]},
        ],

        # 常见问题实体
        EntityType.PROBLEM: [
            {"name": "墙面开裂", "properties": {
                "severity": "中", "stage": "油漆",
                "causes": ["温度裂缝", "沉降裂缝", "施工裂缝", "基层处理不当"],
                "solutions": ["根据类型处理", "铲除重做", "贴网格布"]
            }, "aliases": ["裂缝", "墙裂"]},
            {"name": "瓷砖空鼓", "properties": {
                "severity": "高", "stage": "瓦工",
                "causes": ["基层处理不当", "水泥砂浆配比不当", "瓷砖未泡水"],
                "solutions": ["铲除重贴", "灌浆修补"]
            }, "aliases": ["空鼓", "砖空"]},
            {"name": "漏水", "properties": {
                "severity": "高", "stage": "防水",
                "causes": ["接头松动", "管道破损", "防水失效"],
                "detection": "打压测试",
                "solutions": ["找到漏点修复", "重做防水"]
            }, "aliases": ["渗水", "漏水"]},
            {"name": "甲醛超标", "properties": {
                "severity": "高", "stage": "软装",
                "sources": ["板材", "涂料", "胶水", "家具"],
                "standard": "≤0.08mg/m³",
                "solutions": ["通风", "活性炭", "新风系统", "专业治理"]
            }, "aliases": ["甲醛", "异味"]},
            {"name": "预算超支", "properties": {
                "severity": "中", "stage": "全程",
                "causes": ["增项过多", "材料升级", "设计变更"],
                "prevention": ["详细预算", "合同约定增项上限"]
            }, "aliases": ["超预算", "费用超支"]},
            {"name": "工期延误", "properties": {
                "severity": "中", "stage": "全程",
                "causes": ["材料不到位", "工人调度", "设计变更", "天气因素"],
                "prevention": ["合同约定违约金", "提前备料"]
            }, "aliases": ["延期", "拖延"]},
            {"name": "跳闸", "properties": {
                "severity": "中", "stage": "水电改造",
                "causes": ["线路过载", "短路", "漏电"],
                "solutions": ["排查线路", "增加回路"]
            }, "aliases": ["断电"]},
            {"name": "插座不够", "properties": {
                "severity": "低", "stage": "水电改造",
                "prevention": "前期规划充足",
                "solutions": ["明装插座", "插排"]
            }, "aliases": []},
            {"name": "返潮", "properties": {
                "severity": "中", "stage": "防水",
                "causes": ["地下水", "墙体渗水"],
                "solutions": ["做好防潮处理"]
            }, "aliases": ["潮湿"]},
            {"name": "地板起拱", "properties": {
                "severity": "中", "stage": "安装",
                "causes": ["伸缩缝不足", "受潮膨胀"],
                "solutions": ["重新铺装", "增加伸缩缝"]
            }, "aliases": ["地板变形"]},
            {"name": "门窗漏风", "properties": {
                "severity": "低", "stage": "安装",
                "causes": ["密封条老化", "安装不当"],
                "solutions": ["更换密封条", "调整五金"]
            }, "aliases": ["漏风"]},
            {"name": "瓷砖开裂", "properties": {
                "severity": "高", "stage": "瓦工",
                "causes": ["基层不平", "热胀冷缩", "外力撞击", "瓷砖质量问题"],
                "solutions": ["更换瓷砖", "填缝修补"]
            }, "aliases": ["砖裂"]},
            {"name": "地板响声", "properties": {
                "severity": "低", "stage": "安装",
                "causes": ["地面不平", "龙骨松动", "伸缩缝不足", "防潮膜破损"],
                "solutions": ["重新铺装", "加固龙骨", "注入润滑剂"]
            }, "aliases": ["地板异响", "地板吱吱响"]},
            {"name": "涂料脱落", "properties": {
                "severity": "中", "stage": "油漆",
                "causes": ["基层处理不当", "涂料质量差", "施工环境潮湿"],
                "solutions": ["铲除重做", "做好基层处理"]
            }, "aliases": ["掉漆", "脱皮"]},
            {"name": "墙纸翘边", "properties": {
                "severity": "低", "stage": "油漆",
                "causes": ["胶水质量差", "基层处理不当", "环境潮湿"],
                "solutions": ["重新粘贴", "更换胶水"]
            }, "aliases": ["壁纸翘边", "墙纸起边"]},
            {"name": "护墙板变形", "properties": {
                "severity": "中", "stage": "木工",
                "causes": ["材料含水率高", "安装不当", "环境潮湿"],
                "solutions": ["更换板材", "做好防潮处理"]
            }, "aliases": ["护墙板开裂"]},
            {"name": "吊顶不平", "properties": {
                "severity": "中", "stage": "木工",
                "causes": ["龙骨安装不平", "石膏板变形", "吊杆间距过大"],
                "solutions": ["调整龙骨", "重新安装"]
            }, "aliases": ["吊顶下沉"]},
            {"name": "五金生锈", "properties": {
                "severity": "低", "stage": "安装",
                "causes": ["材质差", "环境潮湿", "电镀层脱落"],
                "solutions": ["更换五金", "做好防潮"]
            }, "aliases": ["五金氧化"]},
            {"name": "橱柜变形", "properties": {
                "severity": "中", "stage": "安装",
                "causes": ["板材质量差", "受潮", "承重过大"],
                "solutions": ["更换板材", "加固结构"]
            }, "aliases": ["柜门变形"]},
            {"name": "水管漏水", "properties": {
                "severity": "高", "stage": "水电改造",
                "causes": ["接头松动", "管道破损", "热熔不到位"],
                "detection": "打压测试0.8MPa保压30分钟",
                "solutions": ["重新热熔", "更换管件"]
            }, "aliases": ["管道漏水"]},
            {"name": "下水堵塞", "properties": {
                "severity": "中", "stage": "安装",
                "causes": ["管道坡度不够", "异物堵塞", "管径过小"],
                "solutions": ["疏通管道", "调整坡度", "更换大管径"]
            }, "aliases": ["排水不畅", "下水慢"]},
            {"name": "地漏返味", "properties": {
                "severity": "低", "stage": "安装",
                "causes": ["地漏水封干涸", "地漏质量差", "安装不当"],
                "solutions": ["更换防臭地漏", "定期补水"]
            }, "aliases": ["下水道臭味"]},
            {"name": "瓷砖色差", "properties": {
                "severity": "低", "stage": "瓦工",
                "causes": ["不同批次", "光线影响", "质量问题"],
                "prevention": "同批次购买、铺贴前检查",
                "solutions": ["更换瓷砖", "调整铺贴位置"]
            }, "aliases": ["砖色不一"]},
            {"name": "乳胶漆开裂", "properties": {
                "severity": "中", "stage": "油漆",
                "causes": ["腻子层开裂", "涂刷过厚", "干燥过快"],
                "solutions": ["铲除重做", "贴网格布"]
            }, "aliases": ["墙漆开裂"]},
            {"name": "木门变形", "properties": {
                "severity": "中", "stage": "安装",
                "causes": ["含水率不达标", "环境潮湿", "安装不当"],
                "solutions": ["调整合页", "更换门扇"]
            }, "aliases": ["门扇变形", "门关不严"]},
            # 使用问题
            {"name": "马桶堵塞", "properties": {
                "severity": "中", "stage": "使用",
                "causes": ["异物堵塞", "管道问题", "冲水力度不足"],
                "solutions": ["皮搋子疏通", "管道疏通剂", "专业疏通"]
            }, "aliases": ["马桶不通"]},
            {"name": "马桶漏水", "properties": {
                "severity": "中", "stage": "使用",
                "causes": ["密封圈老化", "进水阀故障", "排水阀故障"],
                "solutions": ["更换密封圈", "更换配件"]
            }, "aliases": []},
            {"name": "花洒堵塞", "properties": {
                "severity": "低", "stage": "使用",
                "causes": ["水垢堆积", "杂质堵塞"],
                "solutions": ["白醋浸泡", "针头疏通", "更换花洒"]
            }, "aliases": ["花洒水小"]},
            {"name": "台面开裂", "properties": {
                "severity": "中", "stage": "使用",
                "causes": ["热胀冷缩", "外力撞击", "材质问题"],
                "solutions": ["云石胶修补", "更换台面"]
            }, "aliases": ["橱柜台面裂"]},
            {"name": "台面渗色", "properties": {
                "severity": "低", "stage": "使用",
                "causes": ["材质毛孔大", "未做防护"],
                "solutions": ["专业清洁", "抛光处理", "做防护"]
            }, "aliases": []},
            {"name": "铰链松动", "properties": {
                "severity": "低", "stage": "使用",
                "causes": ["使用频繁", "螺丝松动"],
                "solutions": ["调整铰链", "更换铰链"]
            }, "aliases": ["柜门下垂"]},
            {"name": "抽屉滑轨故障", "properties": {
                "severity": "低", "stage": "使用",
                "causes": ["滑轨磨损", "超载使用"],
                "solutions": ["润滑保养", "更换滑轨"]
            }, "aliases": ["抽屉不顺"]},
            {"name": "玻璃起雾", "properties": {
                "severity": "中", "stage": "使用",
                "causes": ["中空玻璃密封失效"],
                "solutions": ["更换玻璃"]
            }, "aliases": ["窗户起雾"]},
            {"name": "地板褪色", "properties": {
                "severity": "低", "stage": "使用",
                "causes": ["阳光暴晒", "紫外线照射"],
                "prevention": "窗帘遮挡",
                "solutions": ["打蜡保养", "更换地板"]
            }, "aliases": []},
            {"name": "墙面发霉", "properties": {
                "severity": "中", "stage": "使用",
                "causes": ["环境潮湿", "通风不良", "渗水"],
                "solutions": ["除霉处理", "防霉涂料重涂", "解决渗水源"]
            }, "aliases": ["墙面长霉"]},
            {"name": "封边开裂", "properties": {
                "severity": "低", "stage": "使用",
                "causes": ["工艺不良", "热胀冷缩", "胶水老化"],
                "solutions": ["重新封边", "更换板材"]
            }, "aliases": ["板材封边脱落"]},
            # 智能家居问题
            {"name": "智能设备离线", "properties": {
                "severity": "低", "stage": "使用",
                "causes": ["网络故障", "设备故障", "信号弱"],
                "solutions": ["重启设备", "重新配对", "优化网络"]
            }, "aliases": ["设备掉线"]},
            {"name": "智能联动失败", "properties": {
                "severity": "低", "stage": "使用",
                "causes": ["设置问题", "兼容性问题", "网关故障"],
                "solutions": ["检查设置", "更新固件", "重置网关"]
            }, "aliases": []},
            # 橱柜问题
            {"name": "台面开裂", "properties": {
                "severity": "中", "stage": "使用",
                "causes": ["热胀冷缩", "撞击", "材质问题"],
                "solutions": ["修补", "更换台面"]
            }, "aliases": ["橱柜台面裂缝"]},
            {"name": "台面渗色", "properties": {
                "severity": "低", "stage": "使用",
                "causes": ["材质吸水", "清洁不及时"],
                "solutions": ["专业清洁", "抛光处理"]
            }, "aliases": []},
            {"name": "铰链松动", "properties": {
                "severity": "低", "stage": "使用",
                "causes": ["使用频繁", "螺丝松动"],
                "solutions": ["调整铰链", "更换铰链"]
            }, "aliases": ["柜门松动"]},
            # 卫浴问题
            {"name": "马桶堵塞", "properties": {
                "severity": "中", "stage": "使用",
                "causes": ["异物堵塞", "管道问题"],
                "solutions": ["疏通", "检查管道"]
            }, "aliases": ["马桶不通"]},
            {"name": "地漏返味", "properties": {
                "severity": "低", "stage": "使用",
                "causes": ["水封干涸", "地漏质量差"],
                "solutions": ["补水", "更换防臭地漏"]
            }, "aliases": ["下水道返味"]},
            {"name": "花洒堵塞", "properties": {
                "severity": "低", "stage": "使用",
                "causes": ["水垢堆积"],
                "solutions": ["醋泡清洁", "更换花洒"]
            }, "aliases": []},
            # 吊顶问题
            {"name": "吊顶开裂", "properties": {
                "severity": "中", "stage": "使用",
                "causes": ["接缝处理不当", "龙骨间距过大", "石膏板受潮"],
                "solutions": ["修补接缝", "重做吊顶"]
            }, "aliases": []},
            {"name": "吊顶下沉", "properties": {
                "severity": "高", "stage": "使用",
                "causes": ["吊筋不足", "吊筋松动"],
                "solutions": ["加固吊筋", "重做吊顶"]
            }, "aliases": []},
            # 电路问题
            {"name": "跳闸", "properties": {
                "severity": "中", "stage": "使用",
                "causes": ["线路过载", "短路", "漏电"],
                "solutions": ["排查线路", "增加回路", "更换电器"]
            }, "aliases": ["空开跳闸"]},
            {"name": "插座不够", "properties": {
                "severity": "低", "stage": "使用",
                "causes": ["前期规划不足"],
                "prevention": "前期充分规划",
                "solutions": ["明装插座", "使用插排"]
            }, "aliases": []},
        ],

        # 解决方案实体
        EntityType.SOLUTION: [
            {"name": "通风除醛", "properties": {
                "target": "甲醛超标",
                "method": "开窗通风",
                "duration": "3-6个月",
                "effectiveness": "高",
                "cost": "低"
            }, "aliases": ["开窗通风"]},
            {"name": "活性炭吸附", "properties": {
                "target": "甲醛超标",
                "method": "放置活性炭包",
                "duration": "需定期更换",
                "effectiveness": "中",
                "cost": "低"
            }, "aliases": ["炭包除醛"]},
            {"name": "光触媒治理", "properties": {
                "target": "甲醛超标",
                "method": "专业喷涂光触媒",
                "effectiveness": "高",
                "cost": "中高"
            }, "aliases": ["光触媒除醛"]},
            {"name": "新风净化", "properties": {
                "target": "甲醛超标",
                "method": "安装新风系统",
                "effectiveness": "高",
                "cost": "高"
            }, "aliases": ["新风除醛"]},
            {"name": "灌浆修补", "properties": {
                "target": "瓷砖空鼓",
                "method": "注入专用灌浆料",
                "applicable": "空鼓面积小于1/3",
                "effectiveness": "中"
            }, "aliases": ["注浆修补"]},
            {"name": "铲除重贴", "properties": {
                "target": "瓷砖空鼓",
                "method": "铲除空鼓瓷砖重新铺贴",
                "applicable": "空鼓面积大",
                "effectiveness": "高"
            }, "aliases": ["重新铺贴"]},
            {"name": "贴网格布", "properties": {
                "target": "墙面开裂",
                "method": "铲除裂缝处涂层，贴网格布后重新批腻子",
                "applicable": "细小裂缝",
                "effectiveness": "高"
            }, "aliases": ["贴布处理"]},
            {"name": "打压测试", "properties": {
                "target": "水管漏水",
                "method": "0.8MPa打压30分钟检测",
                "type": "检测方法",
                "standard": "压力下降≤0.05MPa为合格"
            }, "aliases": ["水压测试"]},
            {"name": "闭水试验", "properties": {
                "target": "漏水",
                "method": "蓄水48小时检测",
                "type": "检测方法",
                "standard": "楼下无渗漏为合格"
            }, "aliases": ["蓄水试验"]},
            {"name": "更换密封条", "properties": {
                "target": "门窗漏风",
                "method": "更换老化密封条",
                "effectiveness": "高",
                "cost": "低"
            }, "aliases": []},
            {"name": "调整五金", "properties": {
                "target": "门窗漏风",
                "method": "调整铰链、执手等五金件",
                "effectiveness": "中",
                "cost": "低"
            }, "aliases": ["五金调整"]},
            {"name": "地板打蜡", "properties": {
                "target": "地板保养",
                "method": "定期打蜡保养",
                "frequency": "3-6个月一次",
                "applicable": "实木地板"
            }, "aliases": ["木地板保养"]},
            {"name": "瓷砖清洁", "properties": {
                "target": "瓷砖保养",
                "method": "中性清洁剂清洗",
                "tips": ["避免酸碱性清洁剂", "及时清理污渍"]
            }, "aliases": []},
            {"name": "防潮处理", "properties": {
                "target": "返潮",
                "method": "涂刷防潮涂料、铺设防潮膜",
                "applicable": "地下室、一楼",
                "effectiveness": "高"
            }, "aliases": ["防潮施工"]},
            # 更多维护保养解决方案
            {"name": "橱柜台面保养", "properties": {
                "target": "橱柜保养",
                "method": "及时清洁、使用砧板、避免高温",
                "tips": ["避免重物撞击", "定期打蜡(天然石材)"]
            }, "aliases": []},
            {"name": "五金润滑", "properties": {
                "target": "五金保养",
                "method": "定期在铰链、滑轨上滴润滑油",
                "frequency": "6个月一次",
                "effectiveness": "高"
            }, "aliases": ["铰链保养"]},
            {"name": "窗帘清洗", "properties": {
                "target": "窗帘保养",
                "method": "根据材质选择清洗方式",
                "tips": {"棉麻": "水洗", "绒布": "干洗", "百叶": "擦拭"}
            }, "aliases": []},
            {"name": "地毯清洁", "properties": {
                "target": "地毯保养",
                "method": "定期吸尘、专业深度清洗",
                "frequency": {"吸尘": "每周", "深度清洗": "每年1-2次"}
            }, "aliases": []},
            {"name": "沙发保养", "properties": {
                "target": "沙发保养",
                "method": "定期除尘、皮质护理",
                "tips": {"布艺": "可拆洗/干洗", "皮质": "皮革护理剂"}
            }, "aliases": []},
            {"name": "智能设备重置", "properties": {
                "target": "智能设备离线",
                "method": "重启设备、重新配对、检查网络",
                "effectiveness": "高"
            }, "aliases": []},
            {"name": "地漏补水", "properties": {
                "target": "地漏返味",
                "method": "定期向地漏注水保持水封",
                "frequency": "每周一次(不常用的地漏)",
                "effectiveness": "高",
                "cost": "低"
            }, "aliases": []},
            {"name": "花洒除垢", "properties": {
                "target": "花洒堵塞",
                "method": "白醋浸泡清洁",
                "duration": "浸泡2-4小时",
                "effectiveness": "高",
                "cost": "低"
            }, "aliases": ["花洒清洁"]},
        ],

        # 行业趋势实体
        EntityType.TREND: [
            {"name": "智能家居普及", "properties": {
                "category": "技术趋势",
                "description": "全屋智能化成为标配",
                "keywords": ["语音控制", "场景联动", "远程控制"],
                "impact": "高"
            }, "aliases": ["智能化"]},
            {"name": "环保健康", "properties": {
                "category": "消费趋势",
                "description": "消费者更关注环保等级和健康材料",
                "keywords": ["ENF级", "零甲醛", "抗菌", "净化"],
                "impact": "高"
            }, "aliases": ["绿色环保"]},
            {"name": "整装一体化", "properties": {
                "category": "服务趋势",
                "description": "从单品到整装的一站式服务",
                "keywords": ["拎包入住", "全屋定制", "整装"],
                "impact": "高"
            }, "aliases": ["一站式装修"]},
            {"name": "适老化设计", "properties": {
                "category": "设计趋势",
                "description": "针对老年人的无障碍设计",
                "keywords": ["扶手", "防滑", "紧急呼叫", "无障碍"],
                "impact": "中"
            }, "aliases": ["适老化"]},
            {"name": "极简风格", "properties": {
                "category": "风格趋势",
                "description": "去繁从简的设计理念",
                "keywords": ["无主灯", "隐藏式收纳", "简约线条"],
                "impact": "高"
            }, "aliases": ["极简主义"]},
            {"name": "国潮新中式", "properties": {
                "category": "风格趋势",
                "description": "传统文化与现代设计的融合",
                "keywords": ["国风", "传统元素", "文化自信"],
                "impact": "中"
            }, "aliases": ["新国潮"]},
            {"name": "可持续发展", "properties": {
                "category": "行业趋势",
                "description": "环保材料和可循环利用",
                "keywords": ["可回收", "低碳", "节能"],
                "impact": "中"
            }, "aliases": ["绿色建材"]},
            {"name": "数字化营销", "properties": {
                "category": "营销趋势",
                "description": "线上线下融合的新零售模式",
                "keywords": ["直播带货", "VR看房", "3D设计"],
                "impact": "高"
            }, "aliases": ["新零售"]},
            # 更多行业趋势
            {"name": "大规格化", "properties": {
                "category": "产品趋势",
                "description": "瓷砖、地板等向大规格发展",
                "keywords": ["大板瓷砖", "岩板", "宽板地板"],
                "examples": ["1200×2400mm瓷砖", "1600×3200mm岩板"],
                "impact": "高"
            }, "aliases": ["大板化"]},
            {"name": "功能集成", "properties": {
                "category": "产品趋势",
                "description": "多功能集成化产品",
                "keywords": ["集成灶", "智能马桶", "多功能家具"],
                "impact": "高"
            }, "aliases": ["一体化"]},
            {"name": "无醛添加", "properties": {
                "category": "环保趋势",
                "description": "使用MDI胶等无醛胶水",
                "keywords": ["MDI胶", "大豆胶", "ENF级"],
                "impact": "高"
            }, "aliases": ["零醛"]},
            {"name": "C2M定制", "properties": {
                "category": "生产趋势",
                "description": "消费者直连工厂的柔性定制",
                "keywords": ["柔性生产", "个性定制", "小批量"],
                "impact": "中"
            }, "aliases": ["柔性定制"]},
            {"name": "VR/AR体验", "properties": {
                "category": "技术趋势",
                "description": "虚拟现实技术在家装中的应用",
                "keywords": ["VR看房", "AR摆放", "沉浸式体验"],
                "impact": "中"
            }, "aliases": ["虚拟体验"]},
            {"name": "AI设计", "properties": {
                "category": "技术趋势",
                "description": "人工智能辅助设计",
                "keywords": ["智能方案生成", "风格迁移", "自动渲染"],
                "impact": "中"
            }, "aliases": ["智能设计"]},
            {"name": "存量房翻新", "properties": {
                "category": "市场趋势",
                "description": "二手房、旧房翻新市场增长",
                "keywords": ["局部改造", "旧房焕新", "精装房改造"],
                "impact": "高"
            }, "aliases": ["旧房改造"]},
            {"name": "银发经济", "properties": {
                "category": "消费趋势",
                "description": "老年人群体的家居消费需求",
                "keywords": ["适老化", "健康功能", "安全设计"],
                "impact": "中"
            }, "aliases": ["适老消费"]},
        ],

        # 销售渠道实体
        EntityType.CHANNEL: [
            {"name": "建材市场", "properties": {
                "type": "线下",
                "examples": ["红星美凯龙", "居然之家", "百安居"],
                "pros": ["品类齐全", "可体验", "售后有保障"],
                "cons": ["价格较高", "需要比价"]
            }, "aliases": ["家居卖场"]},
            {"name": "品牌专卖店", "properties": {
                "type": "线下",
                "pros": ["正品保障", "专业服务", "售后完善"],
                "cons": ["价格固定", "选择有限"]
            }, "aliases": ["专卖店"]},
            {"name": "电商平台", "properties": {
                "type": "线上",
                "examples": ["天猫", "京东", "拼多多"],
                "pros": ["价格透明", "方便比价", "送货上门"],
                "cons": ["无法体验", "退换麻烦"]
            }, "aliases": ["网购"]},
            {"name": "工厂直销", "properties": {
                "type": "线下",
                "pros": ["价格优惠", "可定制"],
                "cons": ["需要一定量", "售后不便"]
            }, "aliases": ["厂家直销"]},
            {"name": "装修公司", "properties": {
                "type": "服务",
                "pros": ["省心省力", "整体把控"],
                "cons": ["价格不透明", "材料加价"]
            }, "aliases": ["装饰公司"]},
            {"name": "设计师渠道", "properties": {
                "type": "服务",
                "pros": ["专业搭配", "资源整合"],
                "cons": ["可能有回扣"]
            }, "aliases": ["设计师带单"]},
            {"name": "社区团购", "properties": {
                "type": "线上",
                "pros": ["价格优惠", "邻里口碑"],
                "cons": ["品类有限"]
            }, "aliases": ["小区团购"]},
            # 装修服务模式
            {"name": "全屋定制", "properties": {
                "type": "服务模式",
                "scope": ["衣柜", "橱柜", "书柜", "鞋柜", "榻榻米", "护墙板"],
                "brands": ["欧派", "索菲亚", "尚品宅配", "好莱客", "志邦"],
                "pros": ["空间利用率高", "风格统一", "一站式服务"],
                "cons": ["价格较高", "周期较长"]
            }, "aliases": ["全屋定制家居", "定制家居"]},
            {"name": "整装", "properties": {
                "type": "服务模式",
                "scope": ["设计", "施工", "主材", "软装"],
                "pros": ["省心省力", "整体把控", "价格打包"],
                "cons": ["选择受限", "个性化不足"]
            }, "aliases": ["整体家装", "一站式装修"]},
            {"name": "拎包入住", "properties": {
                "type": "服务模式",
                "scope": ["硬装", "软装", "家具", "家电", "配饰"],
                "pros": ["最省心", "即装即住"],
                "cons": ["价格最高", "个性化最低"]
            }, "aliases": ["精装交付"]},
            {"name": "软装设计", "properties": {
                "type": "服务模式",
                "scope": ["家具", "窗帘", "灯具", "地毯", "装饰画", "绿植", "饰品"],
                "deliverables": ["软装方案", "产品清单", "摆场指导"],
                "suitable": ["精装房", "二次装修", "样板间"]
            }, "aliases": ["软装搭配", "软装陈设"]},
            {"name": "硬装设计", "properties": {
                "type": "服务模式",
                "scope": ["空间规划", "水电布局", "材料选择", "施工图纸"],
                "deliverables": ["平面方案", "效果图", "施工图", "预算清单"]
            }, "aliases": ["室内设计", "装修设计"]},
        ],

        # 行业术语实体
        EntityType.TERMINOLOGY: [
            {"name": "全包", "properties": {
                "category": "装修模式",
                "definition": "包工包料，装修公司负责所有材料采购和施工",
                "pros": ["省心省力"],
                "cons": ["价格不透明", "材料质量难把控"]
            }, "aliases": ["大包"]},
            {"name": "半包", "properties": {
                "category": "装修模式",
                "definition": "装修公司负责辅材和施工，主材业主自购",
                "pros": ["主材可控", "性价比高"],
                "cons": ["需要花时间选材"]
            }, "aliases": []},
            {"name": "清包", "properties": {
                "category": "装修模式",
                "definition": "业主自购所有材料，只请工人施工",
                "pros": ["最省钱", "材料完全可控"],
                "cons": ["最费心", "需要专业知识"]
            }, "aliases": ["包清工"]},
            {"name": "硬装", "properties": {
                "category": "装修阶段",
                "definition": "水电、瓦工、木工、油漆等基础装修",
                "includes": ["水电改造", "墙面处理", "地面铺装", "吊顶"]
            }, "aliases": []},
            {"name": "软装", "properties": {
                "category": "装修阶段",
                "definition": "家具、窗帘、灯具、装饰品等可移动物品",
                "includes": ["家具", "窗帘", "灯具", "地毯", "挂画"]
            }, "aliases": []},
            {"name": "主材", "properties": {
                "category": "材料分类",
                "definition": "装修中的主要材料",
                "examples": ["瓷砖", "地板", "门", "橱柜", "洁具"]
            }, "aliases": []},
            {"name": "辅材", "properties": {
                "category": "材料分类",
                "definition": "装修中的辅助材料",
                "examples": ["水泥", "沙子", "腻子", "乳胶漆", "电线", "水管"]
            }, "aliases": ["辅料"]},
            {"name": "隐蔽工程", "properties": {
                "category": "工程类型",
                "definition": "完工后被覆盖看不见的工程",
                "examples": ["水电改造", "防水", "地暖"],
                "importance": "极高，出问题维修成本大"
            }, "aliases": []},
            {"name": "闭水试验", "properties": {
                "category": "验收标准",
                "definition": "防水施工后蓄水48小时检测是否渗漏",
                "standard": "楼下无渗漏为合格"
            }, "aliases": ["蓄水试验"]},
            {"name": "打压测试", "properties": {
                "category": "验收标准",
                "definition": "水管安装后加压检测是否漏水",
                "standard": "0.8MPa保压30分钟，压降≤0.05MPa"
            }, "aliases": ["水压测试"]},
            {"name": "空鼓", "properties": {
                "category": "质量问题",
                "definition": "瓷砖与基层之间有空隙，敲击有空洞声",
                "detection": "空鼓锤敲击检测"
            }, "aliases": []},
            {"name": "阴阳角", "properties": {
                "category": "施工术语",
                "definition": "墙面凹进去的角为阴角，凸出来的角为阳角",
                "standard": "垂直度≤3mm"
            }, "aliases": []},
            {"name": "找平", "properties": {
                "category": "施工术语",
                "definition": "使地面或墙面达到水平或垂直的施工工艺",
                "types": ["水泥砂浆找平", "自流平找平"]
            }, "aliases": ["地面找平"]},
            {"name": "腻子", "properties": {
                "category": "材料术语",
                "definition": "墙面基层处理材料，用于填补和找平",
                "types": ["耐水腻子", "普通腻子"]
            }, "aliases": ["批腻子", "刮腻子"]},
            {"name": "底漆", "properties": {
                "category": "材料术语",
                "definition": "涂刷在腻子层上的第一道漆",
                "function": ["封闭基层", "增强附着力", "防止返碱"]
            }, "aliases": []},
            {"name": "面漆", "properties": {
                "category": "材料术语",
                "definition": "涂刷在底漆上的最终涂层",
                "function": ["装饰", "保护"]
            }, "aliases": ["乳胶漆"]},
            {"name": "基材", "properties": {
                "definition": "板材的主体材料",
                "examples": ["刨花板", "密度板", "多层板"],
                "category": "材料术语"
            }, "aliases": []},
            {"name": "饰面", "properties": {
                "definition": "板材表面的装饰层",
                "types": ["三聚氰胺饰面", "PVC饰面", "实木贴皮", "烤漆"],
                "category": "材料术语"
            }, "aliases": ["贴面"]},
            {"name": "封边", "properties": {
                "definition": "板材边缘的封闭处理",
                "types": ["PVC封边", "ABS封边", "实木封边", "激光封边"],
                "category": "材料术语"
            }, "aliases": []},
            {"name": "吸水率", "properties": {
                "definition": "瓷砖吸收水分的能力",
                "grades": {"瓷质砖": "≤0.5%", "炻瓷砖": "0.5-3%", "细炻砖": "3-6%", "炻质砖": "6-10%"},
                "category": "材料术语"
            }, "aliases": []},
            {"name": "莫氏硬度", "properties": {
                "definition": "材料抵抗刻划的能力",
                "scale": "1-10级",
                "reference": {"滑石": 1, "石膏": 2, "方解石": 3, "石英": 7, "金刚石": 10},
                "category": "材料术语"
            }, "aliases": []},
            {"name": "防滑系数", "properties": {
                "definition": "地面材料的防滑性能",
                "grades": {"R9": "一般", "R10": "较好", "R11": "好", "R12": "很好", "R13": "最好"},
                "category": "材料术语"
            }, "aliases": ["R值"]},
            {"name": "横平竖直", "properties": {
                "definition": "水电布线的标准要求",
                "purpose": "便于后期维修和避免打孔损坏",
                "category": "工艺术语"
            }, "aliases": []},
            {"name": "动线", "properties": {
                "definition": "人在空间中的移动路线",
                "types": ["家务动线", "访客动线", "私密动线"],
                "category": "设计术语"
            }, "aliases": []},
            {"name": "投影面积", "properties": {
                "definition": "定制柜体的计价方式，按柜体正面投影面积计算",
                "formula": "宽×高",
                "category": "商业术语"
            }, "aliases": []},
            {"name": "展开面积", "properties": {
                "definition": "定制柜体的计价方式，按所有板材面积之和计算",
                "pros": "更精确",
                "cons": "计算复杂",
                "category": "商业术语"
            }, "aliases": []},
            # 更多设计术语
            {"name": "留白", "properties": {
                "definition": "空间中有意保留的空白区域",
                "purpose": "增加空间感和呼吸感",
                "category": "设计术语"
            }, "aliases": []},
            {"name": "层次感", "properties": {
                "definition": "空间或视觉上的前后深浅变化",
                "methods": ["色彩深浅", "材质对比", "灯光明暗"],
                "category": "设计术语"
            }, "aliases": []},
            {"name": "氛围感", "properties": {
                "definition": "空间给人的整体感觉和情绪",
                "elements": ["灯光", "色彩", "材质", "软装"],
                "category": "设计术语"
            }, "aliases": []},
            {"name": "莫兰迪色", "properties": {
                "definition": "低饱和度、灰调的柔和色彩",
                "origin": "意大利画家乔治·莫兰迪",
                "features": ["高级感", "耐看", "百搭"],
                "category": "色彩术语"
            }, "aliases": ["高级灰"]},
            {"name": "撞色", "properties": {
                "definition": "对比色或互补色的搭配",
                "effect": "视觉冲击力强",
                "category": "色彩术语"
            }, "aliases": ["对比色搭配"]},
            {"name": "奶油风", "properties": {
                "definition": "以奶白色、米色为主的温暖柔和风格",
                "colors": ["奶白", "米色", "浅咖", "木色"],
                "category": "风格术语"
            }, "aliases": ["奶油色系"]},
            {"name": "侘寂风", "properties": {
                "definition": "追求不完美之美的日式美学风格",
                "features": ["自然", "朴素", "残缺美"],
                "origin": "日本",
                "category": "风格术语"
            }, "aliases": ["侘寂", "wabi-sabi"]},
            {"name": "中古风", "properties": {
                "definition": "复古风格，使用中古家具",
                "era": "20世纪中期",
                "features": ["复古", "有年代感", "独特"],
                "category": "风格术语"
            }, "aliases": ["复古风", "vintage"]},
            # 更多工艺术语
            {"name": "薄贴", "properties": {
                "definition": "使用瓷砖胶铺贴瓷砖的工艺",
                "thickness": "3-5mm",
                "pros": ["粘结力强", "不易空鼓"],
                "category": "工艺术语"
            }, "aliases": ["瓷砖胶铺贴"]},
            {"name": "厚贴", "properties": {
                "definition": "使用水泥砂浆铺贴瓷砖的传统工艺",
                "thickness": "15-20mm",
                "cons": ["易空鼓", "厚度大"],
                "category": "工艺术语"
            }, "aliases": ["水泥砂浆铺贴"]},
            {"name": "干铺", "properties": {
                "definition": "使用干性砂浆铺贴地砖的工艺",
                "application": "地砖铺贴",
                "category": "工艺术语"
            }, "aliases": []},
            {"name": "湿铺", "properties": {
                "definition": "使用湿性砂浆铺贴瓷砖的工艺",
                "application": "墙砖铺贴",
                "category": "工艺术语"
            }, "aliases": []},
            {"name": "美缝", "properties": {
                "definition": "瓷砖缝隙的填充美化处理",
                "materials": ["美缝剂", "环氧彩砂"],
                "category": "工艺术语"
            }, "aliases": ["瓷砖美缝"]},
            {"name": "墙固", "properties": {
                "definition": "墙面固化剂，用于加固墙面基层",
                "function": ["固化基层", "增强附着力"],
                "category": "材料术语"
            }, "aliases": ["界面剂"]},
            {"name": "地固", "properties": {
                "definition": "地面固化剂，用于加固地面基层",
                "function": ["固化基层", "防止起砂"],
                "category": "材料术语"
            }, "aliases": []},
            {"name": "挂网", "properties": {
                "definition": "在墙面批腻子前铺设网格布",
                "purpose": "防止墙面开裂",
                "material": "玻纤网格布",
                "category": "工艺术语"
            }, "aliases": ["贴网格布"]},
            # 更多商业术语
            {"name": "延米", "properties": {
                "definition": "按长度计价的方式，常用于橱柜、台面",
                "unit": "元/延米",
                "category": "商业术语"
            }, "aliases": ["延长米"]},
            {"name": "增项", "properties": {
                "definition": "装修过程中增加的额外项目",
                "warning": "需警惕恶意增项",
                "category": "商业术语"
            }, "aliases": []},
            {"name": "漏项", "properties": {
                "definition": "报价中遗漏的必要项目",
                "warning": "低价陷阱常见手段",
                "category": "商业术语"
            }, "aliases": []},
            {"name": "样板间", "properties": {
                "definition": "装修公司或品牌展示的示范空间",
                "purpose": "展示效果、吸引客户",
                "category": "商业术语"
            }, "aliases": ["展厅"]},
            {"name": "工厂团购", "properties": {
                "definition": "组织消费者直接到工厂采购",
                "pros": "价格优惠",
                "cons": "可能有套路",
                "category": "商业术语"
            }, "aliases": ["厂购"]},
            {"name": "整装", "properties": {
                "definition": "包含硬装、软装、家电的一站式装修服务",
                "includes": ["设计", "施工", "主材", "软装", "家电"],
                "category": "装修模式"
            }, "aliases": ["拎包入住"]},
            # 卫浴设计术语
            {"name": "干湿分离", "properties": {
                "definition": "将卫生间的干区（洗漱）和湿区（淋浴）分开",
                "methods": ["玻璃隔断", "浴帘", "半墙隔断"],
                "benefits": ["保持干区干燥", "安全防滑", "易清洁"],
                "category": "设计术语"
            }, "aliases": ["干湿分区"]},
            {"name": "三分离", "properties": {
                "definition": "将卫生间分为洗漱区、马桶区、淋浴区三个独立空间",
                "min_area": "5㎡以上",
                "benefits": ["多人同时使用", "互不干扰", "更卫生"],
                "category": "设计术语"
            }, "aliases": ["三式分离"]},
            {"name": "四分离", "properties": {
                "definition": "将卫生间分为洗漱区、马桶区、淋浴区、洗衣区四个独立空间",
                "min_area": "8㎡以上",
                "origin": "日本",
                "benefits": ["功能完善", "使用效率最高"],
                "category": "设计术语"
            }, "aliases": ["四式分离"]},
            {"name": "见光不见灯", "properties": {
                "definition": "灯具隐藏，只看到光线效果的照明设计",
                "methods": ["灯带", "线性灯", "嵌入式灯具", "反射照明"],
                "effect": "空间更整洁、氛围更柔和",
                "category": "设计术语"
            }, "aliases": ["隐藏式照明"]},
            # 厨电术语
            {"name": "蒸烤一体机", "properties": {
                "definition": "集蒸箱和烤箱功能于一体的厨房电器",
                "functions": ["蒸", "烤", "蒸烤结合"],
                "types": ["嵌入式", "台式"],
                "brands": ["方太", "老板", "西门子", "美的"],
                "category": "厨电术语"
            }, "aliases": ["蒸烤箱"]},
            # 定制家具术语
            {"name": "飘窗柜", "properties": {
                "definition": "利用飘窗空间定制的储物柜",
                "types": ["飘窗柜+书桌", "飘窗柜+衣柜", "飘窗柜+榻榻米"],
                "features": ["增加储物空间", "美观实用"],
                "category": "定制术语"
            }, "aliases": ["飘窗收纳柜"]},
            {"name": "智能镜柜", "properties": {
                "definition": "集镜子、储物、智能功能于一体的浴室柜",
                "features": ["LED照明", "除雾", "时间显示", "蓝牙音箱"],
                "applications": ["卫生间"],
                "category": "卫浴术语"
            }, "aliases": ["智能浴室镜柜"]},
        ],

        # 品牌实体
        EntityType.BRAND: [
            # 瓷砖品牌
            {"name": "马可波罗", "properties": {"category": "瓷砖", "level": "高端", "origin": "国产"}, "aliases": []},
            {"name": "东鹏", "properties": {"category": "瓷砖", "level": "高端", "origin": "国产"}, "aliases": []},
            {"name": "诺贝尔", "properties": {"category": "瓷砖", "level": "高端", "origin": "国产"}, "aliases": []},
            {"name": "蒙娜丽莎", "properties": {"category": "瓷砖", "level": "高端", "origin": "国产"}, "aliases": []},
            # 卫浴品牌
            {"name": "TOTO", "properties": {"category": "卫浴", "level": "高端", "origin": "日本"}, "aliases": ["东陶"]},
            {"name": "科勒", "properties": {"category": "卫浴", "level": "高端", "origin": "美国"}, "aliases": ["Kohler"]},
            {"name": "九牧", "properties": {"category": "卫浴", "level": "中高端", "origin": "国产"}, "aliases": ["JOMOO"]},
            {"name": "箭牌", "properties": {"category": "卫浴", "level": "中端", "origin": "国产"}, "aliases": ["ARROW"]},
            {"name": "恒洁", "properties": {"category": "卫浴", "level": "中高端", "origin": "国产"}, "aliases": ["HeGII"]},
            # 厨电品牌
            {"name": "方太", "properties": {"category": "厨电", "level": "高端", "origin": "国产"}, "aliases": ["FOTILE"]},
            {"name": "老板", "properties": {"category": "厨电", "level": "高端", "origin": "国产"}, "aliases": ["Robam"]},
            {"name": "西门子", "properties": {"category": "厨电/电气", "level": "高端", "origin": "德国"}, "aliases": ["Siemens"]},
            {"name": "博世", "properties": {"category": "厨电", "level": "高端", "origin": "德国"}, "aliases": ["Bosch"]},
            # 定制家具品牌
            {"name": "欧派", "properties": {"category": "定制家具", "level": "高端", "origin": "国产"}, "aliases": ["OPPEIN"]},
            {"name": "索菲亚", "properties": {"category": "定制家具", "level": "高端", "origin": "国产"}, "aliases": ["SOGAL"]},
            {"name": "尚品宅配", "properties": {"category": "定制家具", "level": "中高端", "origin": "国产"}, "aliases": []},
            # 地板品牌
            {"name": "大自然", "properties": {"category": "地板", "level": "高端", "origin": "国产"}, "aliases": ["Nature"]},
            {"name": "圣象", "properties": {"category": "地板", "level": "高端", "origin": "国产"}, "aliases": ["PowerDekor"]},
            {"name": "德尔", "properties": {"category": "地板", "level": "中高端", "origin": "国产"}, "aliases": ["Der"]},
            # 涂料品牌
            {"name": "立邦", "properties": {"category": "涂料", "level": "高端", "origin": "日本"}, "aliases": ["Nippon"]},
            {"name": "多乐士", "properties": {"category": "涂料", "level": "高端", "origin": "荷兰"}, "aliases": ["Dulux"]},
            {"name": "三棵树", "properties": {"category": "涂料", "level": "中高端", "origin": "国产"}, "aliases": []},
            # 五金品牌
            {"name": "百隆", "properties": {"category": "五金", "level": "高端", "origin": "奥地利"}, "aliases": ["Blum"]},
            {"name": "海蒂诗", "properties": {"category": "五金", "level": "高端", "origin": "德国"}, "aliases": ["Hettich"]},
            {"name": "DTC", "properties": {"category": "五金", "level": "中端", "origin": "国产"}, "aliases": ["东泰"]},
            # 门窗品牌
            {"name": "森鹰", "properties": {"category": "门窗", "level": "高端", "origin": "国产"}, "aliases": []},
            {"name": "皇派", "properties": {"category": "门窗", "level": "中高端", "origin": "国产"}, "aliases": []},
            # 暖通品牌
            {"name": "威能", "properties": {"category": "暖通", "level": "高端", "origin": "德国"}, "aliases": ["Vaillant"]},
            {"name": "大金", "properties": {"category": "空调", "level": "高端", "origin": "日本"}, "aliases": ["DAIKIN"]},
            {"name": "格力", "properties": {"category": "空调", "level": "中高端", "origin": "国产"}, "aliases": ["GREE"]},
            # 电气品牌
            {"name": "施耐德", "properties": {"category": "电气", "level": "高端", "origin": "法国"}, "aliases": ["Schneider"]},
            {"name": "ABB", "properties": {"category": "电气", "level": "高端", "origin": "瑞士"}, "aliases": []},
            {"name": "正泰", "properties": {"category": "电气", "level": "中端", "origin": "国产"}, "aliases": ["CHINT"]},
            # 管材品牌
            {"name": "伟星", "properties": {"category": "管材", "level": "高端", "origin": "国产"}, "aliases": []},
            {"name": "日丰", "properties": {"category": "管材", "level": "中高端", "origin": "国产"}, "aliases": ["Rifeng"]},
            {"name": "联塑", "properties": {"category": "管材", "level": "中端", "origin": "国产"}, "aliases": []},
            # 防水材料品牌
            {"name": "德高", "properties": {"category": "防水", "level": "高端", "origin": "法国"}, "aliases": ["Davco"]},
            {"name": "雨虹", "properties": {"category": "防水", "level": "高端", "origin": "国产"}, "aliases": ["东方雨虹"]},
            {"name": "西卡", "properties": {"category": "防水", "level": "高端", "origin": "瑞士"}, "aliases": ["Sika"]},
            {"name": "汉高百得", "properties": {"category": "防水", "level": "中高端", "origin": "德国"}, "aliases": ["Pattex"]},
            {"name": "马贝", "properties": {"category": "防水/瓷砖胶", "level": "高端", "origin": "意大利"}, "aliases": ["Mapei"]},
            # 床垫品牌
            {"name": "席梦思", "properties": {"category": "床垫", "level": "高端", "origin": "美国"}, "aliases": ["Simmons"]},
            {"name": "慕思", "properties": {"category": "床垫", "level": "高端", "origin": "国产"}, "aliases": ["DeRucci"]},
            {"name": "喜临门", "properties": {"category": "床垫", "level": "中高端", "origin": "国产"}, "aliases": ["Sleemon"]},
            # 沙发品牌
            {"name": "顾家", "properties": {"category": "沙发", "level": "中高端", "origin": "国产"}, "aliases": ["KUKA"]},
            {"name": "芝华仕", "properties": {"category": "沙发", "level": "中高端", "origin": "国产"}, "aliases": ["CHEERS"]},
            {"name": "左右", "properties": {"category": "沙发", "level": "中高端", "origin": "国产"}, "aliases": ["ZUOYOU"]},
            # 灯具品牌
            {"name": "飞利浦", "properties": {"category": "灯具", "level": "高端", "origin": "荷兰"}, "aliases": ["Philips"]},
            {"name": "欧司朗", "properties": {"category": "灯具", "level": "高端", "origin": "德国"}, "aliases": ["OSRAM"]},
            {"name": "松下", "properties": {"category": "灯具/电器", "level": "高端", "origin": "日本"}, "aliases": ["Panasonic"]},
            {"name": "欧普", "properties": {"category": "灯具", "level": "中高端", "origin": "国产"}, "aliases": ["OPPLE"]},
            {"name": "雷士", "properties": {"category": "灯具", "level": "中高端", "origin": "国产"}, "aliases": ["NVC"]},
            {"name": "西顿", "properties": {"category": "灯具", "level": "专业", "origin": "国产"}, "aliases": []},
            {"name": "三雄极光", "properties": {"category": "灯具", "level": "专业", "origin": "国产"}, "aliases": []},
            # 窗帘品牌
            {"name": "摩力克", "properties": {"category": "窗帘", "level": "高端", "origin": "国产"}, "aliases": []},
            {"name": "如鱼得水", "properties": {"category": "窗帘", "level": "高端", "origin": "国产"}, "aliases": []},
            {"name": "金蝉", "properties": {"category": "窗帘", "level": "中端", "origin": "国产"}, "aliases": []},
            {"name": "杜亚", "properties": {"category": "电动窗帘", "level": "高端", "origin": "国产"}, "aliases": ["DOOYA"]},
            # 床品品牌
            {"name": "罗莱", "properties": {"category": "床品", "level": "中高端", "origin": "国产"}, "aliases": ["LUOLAI"]},
            {"name": "富安娜", "properties": {"category": "床品", "level": "中高端", "origin": "国产"}, "aliases": []},
            {"name": "水星", "properties": {"category": "床品", "level": "中端", "origin": "国产"}, "aliases": []},
            {"name": "梦洁", "properties": {"category": "床品", "level": "中高端", "origin": "国产"}, "aliases": []},
            # 智能家居品牌
            {"name": "小米", "properties": {"category": "智能家居", "level": "中端", "origin": "国产"}, "aliases": ["MI"]},
            {"name": "Aqara", "properties": {"category": "智能家居", "level": "中高端", "origin": "国产"}, "aliases": ["绿米"]},
            {"name": "欧瑞博", "properties": {"category": "智能家居", "level": "高端", "origin": "国产"}, "aliases": ["ORVIBO"]},
            {"name": "涂鸦", "properties": {"category": "智能家居", "level": "平台", "origin": "国产"}, "aliases": ["Tuya"]},
            # 扫地机器人品牌
            {"name": "石头", "properties": {"category": "扫地机器人", "level": "高端", "origin": "国产"}, "aliases": ["Roborock"]},
            {"name": "科沃斯", "properties": {"category": "扫地机器人", "level": "高端", "origin": "国产"}, "aliases": ["ECOVACS"]},
            {"name": "追觅", "properties": {"category": "扫地机器人", "level": "中高端", "origin": "国产"}, "aliases": ["Dreame"]},
            {"name": "云鲸", "properties": {"category": "扫地机器人", "level": "高端", "origin": "国产"}, "aliases": ["NARWAL"]},
            # 热水器品牌
            {"name": "林内", "properties": {"category": "热水器", "level": "高端", "origin": "日本"}, "aliases": ["Rinnai"]},
            {"name": "能率", "properties": {"category": "热水器", "level": "高端", "origin": "日本"}, "aliases": ["NORITZ"]},
            {"name": "A.O.史密斯", "properties": {"category": "热水器", "level": "高端", "origin": "美国"}, "aliases": ["AO Smith"]},
            # 国际瓷砖品牌
            {"name": "IMOLA", "properties": {"category": "瓷砖", "level": "高端", "origin": "意大利"}, "aliases": ["蜜蜂"]},
            {"name": "MARAZZI", "properties": {"category": "瓷砖", "level": "高端", "origin": "意大利"}, "aliases": ["马拉齐"]},
            {"name": "简一", "properties": {"category": "瓷砖", "level": "高端", "origin": "国产", "specialty": "大理石瓷砖"}, "aliases": []},
            {"name": "冠珠", "properties": {"category": "瓷砖", "level": "中高端", "origin": "国产"}, "aliases": []},
            {"name": "欧神诺", "properties": {"category": "瓷砖", "level": "中高端", "origin": "国产"}, "aliases": ["Oceano"]},
            # 更多定制家具品牌
            {"name": "志邦", "properties": {"category": "定制家具", "level": "高端", "origin": "国产"}, "aliases": ["Zbom"]},
            {"name": "好莱客", "properties": {"category": "定制家具", "level": "中高端", "origin": "国产"}, "aliases": ["Holike"]},
            {"name": "金牌", "properties": {"category": "定制家具", "level": "中高端", "origin": "国产"}, "aliases": ["Goldenhome"]},
            {"name": "我乐", "properties": {"category": "定制家具", "level": "中高端", "origin": "国产"}, "aliases": ["OLO"]},
            # 成品家具品牌
            {"name": "全友", "properties": {"category": "家具", "level": "中端", "origin": "国产"}, "aliases": ["QuanU"]},
            {"name": "曲美", "properties": {"category": "家具", "level": "中高端", "origin": "国产"}, "aliases": ["QM"]},
            {"name": "华日", "properties": {"category": "家具", "level": "中高端", "origin": "国产", "specialty": "实木家具"}, "aliases": []},
            {"name": "光明", "properties": {"category": "家具", "level": "中高端", "origin": "国产", "specialty": "实木家具"}, "aliases": []},
            # 智能门锁品牌
            {"name": "凯迪仕", "properties": {"category": "智能门锁", "level": "高端", "origin": "国产"}, "aliases": ["Kaadas"]},
            {"name": "德施曼", "properties": {"category": "智能门锁", "level": "高端", "origin": "国产"}, "aliases": ["Dessmann"]},
            {"name": "鹿客", "properties": {"category": "智能门锁", "level": "中高端", "origin": "国产"}, "aliases": ["Loock"]},
            # 门窗品牌
            {"name": "梦天", "properties": {"category": "木门", "level": "高端", "origin": "国产"}, "aliases": ["Mengtian"]},
            {"name": "美心", "properties": {"category": "木门", "level": "中高端", "origin": "国产"}, "aliases": ["Mexin"]},
            {"name": "TATA", "properties": {"category": "木门", "level": "中高端", "origin": "国产"}, "aliases": ["TATA木门"]},
            {"name": "新豪轩", "properties": {"category": "门窗", "level": "中高端", "origin": "国产"}, "aliases": []},
            # 国际卫浴品牌
            {"name": "汉斯格雅", "properties": {"category": "卫浴", "level": "高端", "origin": "德国"}, "aliases": ["Hansgrohe"]},
            {"name": "高仪", "properties": {"category": "卫浴", "level": "高端", "origin": "德国"}, "aliases": ["Grohe"]},
            {"name": "杜拉维特", "properties": {"category": "卫浴", "level": "高端", "origin": "德国"}, "aliases": ["Duravit"]},
            {"name": "惠达", "properties": {"category": "卫浴", "level": "中端", "origin": "国产"}, "aliases": ["Huida"]},
            # 涂料品牌
            {"name": "芬琳", "properties": {"category": "涂料", "level": "高端", "origin": "芬兰"}, "aliases": ["Tikkurila"]},
            {"name": "都芳", "properties": {"category": "涂料", "level": "高端", "origin": "德国"}, "aliases": ["Caparol"]},
            {"name": "嘉宝莉", "properties": {"category": "涂料", "level": "中高端", "origin": "国产"}, "aliases": ["Carpoly"]},
            {"name": "华润", "properties": {"category": "涂料", "level": "中高端", "origin": "国产"}, "aliases": []},
            # 地板品牌
            {"name": "菲林格尔", "properties": {"category": "地板", "level": "高端", "origin": "德国"}, "aliases": ["Fillinger"]},
            {"name": "安信", "properties": {"category": "地板", "level": "中高端", "origin": "国产", "specialty": "实木地板"}, "aliases": []},
            {"name": "久盛", "properties": {"category": "地板", "level": "中高端", "origin": "国产", "specialty": "实木地板"}, "aliases": []},
            {"name": "生活家", "properties": {"category": "地板", "level": "中高端", "origin": "国产"}, "aliases": []},
            # 床垫品牌
            {"name": "丝涟", "properties": {"category": "床垫", "level": "高端", "origin": "美国"}, "aliases": ["Sealy"]},
            {"name": "舒达", "properties": {"category": "床垫", "level": "高端", "origin": "美国"}, "aliases": ["Serta"]},
            {"name": "金可儿", "properties": {"category": "床垫", "level": "高端", "origin": "美国"}, "aliases": ["King Koil"]},
            # 厨电品牌
            {"name": "华帝", "properties": {"category": "厨电", "level": "中高端", "origin": "国产"}, "aliases": ["Vatti"]},
            {"name": "美的", "properties": {"category": "厨电/家电", "level": "中端", "origin": "国产"}, "aliases": ["Midea"]},
            {"name": "火星人", "properties": {"category": "集成灶", "level": "高端", "origin": "国产"}, "aliases": []},
            {"name": "亿田", "properties": {"category": "集成灶", "level": "中高端", "origin": "国产"}, "aliases": []},
            # 设计师家具品牌
            {"name": "HAY", "properties": {"category": "设计师家具", "level": "高端", "origin": "丹麦", "style": "北欧"}, "aliases": []},
            {"name": "Muuto", "properties": {"category": "设计师家具", "level": "高端", "origin": "丹麦", "style": "北欧"}, "aliases": []},
            {"name": "Fritz Hansen", "properties": {"category": "设计师家具", "level": "高端", "origin": "丹麦", "style": "北欧"}, "aliases": []},
            {"name": "FLOS", "properties": {"category": "设计师灯具", "level": "高端", "origin": "意大利"}, "aliases": []},
            {"name": "Artemide", "properties": {"category": "设计师灯具", "level": "高端", "origin": "意大利"}, "aliases": []},
            {"name": "Louis Poulsen", "properties": {"category": "设计师灯具", "level": "高端", "origin": "丹麦", "famous": "PH灯"}, "aliases": []},
            {"name": "Tom Dixon", "properties": {"category": "设计师灯具", "level": "高端", "origin": "英国"}, "aliases": []},
            {"name": "宜家", "properties": {"category": "家居", "level": "大众", "origin": "瑞典", "style": "北欧"}, "aliases": ["IKEA"]},
            {"name": "无印良品", "properties": {"category": "家居", "level": "中端", "origin": "日本", "style": "日式"}, "aliases": ["MUJI"]},
            {"name": "造作", "properties": {"category": "设计师家具", "level": "中高端", "origin": "国产"}, "aliases": ["ZAOZUO"]},
            {"name": "吱音", "properties": {"category": "设计师家具", "level": "中高端", "origin": "国产"}, "aliases": ["Ziinlife"]},
            {"name": "半木", "properties": {"category": "设计师家具", "level": "高端", "origin": "国产", "style": "新中式"}, "aliases": ["Banmoo"]},
            # ==================== 建材市场/家居卖场品牌 ====================
            {"name": "红星美凯龙", "properties": {
                "category": "建材市场",
                "level": "中高端",
                "origin": "国产",
                "model": "租赁制",
                "coverage": "全国连锁"
            }, "aliases": ["红星"]},
            {"name": "居然之家", "properties": {
                "category": "建材市场",
                "level": "中高端",
                "origin": "国产",
                "coverage": "全国连锁"
            }, "aliases": ["居然"]},
            {"name": "百安居", "properties": {
                "category": "建材市场",
                "level": "中端",
                "origin": "英国",
                "model": "建材超市"
            }, "aliases": ["B&Q"]},
            {"name": "月星家居", "properties": {
                "category": "建材市场",
                "level": "中高端",
                "origin": "国产"
            }, "aliases": []},
            {"name": "富森美", "properties": {
                "category": "建材市场",
                "level": "中高端",
                "origin": "国产",
                "region": "西南地区"
            }, "aliases": []},
            # ==================== 家装公司品牌 ====================
            {"name": "东易日盛", "properties": {
                "category": "家装公司",
                "level": "高端",
                "origin": "国产",
                "type": "整装公司",
                "listed": True
            }, "aliases": []},
            {"name": "业之峰", "properties": {
                "category": "家装公司",
                "level": "高端",
                "origin": "国产",
                "type": "整装公司"
            }, "aliases": []},
            {"name": "龙发装饰", "properties": {
                "category": "家装公司",
                "level": "高端",
                "origin": "国产",
                "type": "整装公司"
            }, "aliases": ["龙发"]},
            {"name": "金螳螂家", "properties": {
                "category": "家装公司",
                "level": "高端",
                "origin": "国产",
                "type": "整装公司",
                "parent": "金螳螂"
            }, "aliases": []},
            {"name": "星艺装饰", "properties": {
                "category": "家装公司",
                "level": "中高端",
                "origin": "国产",
                "type": "整装公司"
            }, "aliases": []},
            {"name": "名雕装饰", "properties": {
                "category": "家装公司",
                "level": "高端",
                "origin": "国产",
                "type": "整装公司",
                "region": "华南"
            }, "aliases": []},
            # ==================== 互联网家装平台 ====================
            {"name": "土巴兔", "properties": {
                "category": "互联网家装",
                "level": "平台",
                "origin": "国产",
                "model": "装修平台",
                "services": ["装修公司对接", "设计服务", "装修贷款"]
            }, "aliases": []},
            {"name": "齐家网", "properties": {
                "category": "互联网家装",
                "level": "平台",
                "origin": "国产",
                "model": "装修平台",
                "listed": True
            }, "aliases": []},
            {"name": "爱空间", "properties": {
                "category": "互联网家装",
                "level": "中端",
                "origin": "国产",
                "model": "标准化家装",
                "feature": "标准化产品包"
            }, "aliases": []},
            {"name": "好好住", "properties": {
                "category": "家装内容平台",
                "level": "平台",
                "origin": "国产",
                "model": "内容社区",
                "feature": "装修案例分享"
            }, "aliases": []},
            {"name": "住小帮", "properties": {
                "category": "家装内容平台",
                "level": "平台",
                "origin": "国产",
                "parent": "字节跳动",
                "model": "内容社区"
            }, "aliases": []},
            {"name": "一兜糖", "properties": {
                "category": "家装内容平台",
                "level": "平台",
                "origin": "国产",
                "model": "内容社区",
                "feature": "家居好物分享"
            }, "aliases": []},
            # ==================== 安装服务平台 ====================
            {"name": "万师傅", "properties": {
                "category": "安装服务",
                "level": "平台",
                "origin": "国产",
                "services": ["家具安装", "灯具安装", "卫浴安装", "家电维修"]
            }, "aliases": []},
            {"name": "鲁班到家", "properties": {
                "category": "安装服务",
                "level": "平台",
                "origin": "国产",
                "services": ["家具安装", "配送安装一体化"]
            }, "aliases": []},
            {"name": "神工007", "properties": {
                "category": "安装服务",
                "level": "平台",
                "origin": "国产",
                "services": ["家居安装", "维修服务"]
            }, "aliases": []},
            # ==================== 腻子/辅材品牌 ====================
            {"name": "美巢", "properties": {
                "category": "辅材",
                "level": "高端",
                "origin": "国产",
                "products": ["腻子", "界面剂", "瓷砖胶"]
            }, "aliases": []},
            {"name": "立邦腻子", "properties": {
                "category": "辅材",
                "level": "高端",
                "origin": "日本",
                "products": ["腻子", "墙固"]
            }, "aliases": []},
            {"name": "圣戈班", "properties": {
                "category": "辅材/石膏板",
                "level": "高端",
                "origin": "法国",
                "products": ["石膏板", "腻子", "嵌缝膏"]
            }, "aliases": ["Saint-Gobain", "杰科"]},
            {"name": "可耐福", "properties": {
                "category": "石膏板",
                "level": "高端",
                "origin": "德国",
                "products": ["石膏板", "轻钢龙骨"]
            }, "aliases": ["Knauf"]},
            {"name": "龙牌", "properties": {
                "category": "石膏板",
                "level": "中高端",
                "origin": "国产",
                "products": ["石膏板", "矿棉板"]
            }, "aliases": ["北新建材"]},
            {"name": "泰山石膏", "properties": {
                "category": "石膏板",
                "level": "中端",
                "origin": "国产"
            }, "aliases": []},
            # ==================== 3D设计软件品牌 ====================
            {"name": "酷家乐", "properties": {
                "category": "3D设计软件",
                "level": "平台",
                "origin": "国产",
                "features": ["云端渲染", "VR体验", "一键出图"],
                "users": "设计师/装修公司"
            }, "aliases": ["Kujiale"]},
            {"name": "三维家", "properties": {
                "category": "3D设计软件",
                "level": "平台",
                "origin": "国产",
                "features": ["全屋定制设计", "前后端一体化"],
                "users": "定制家居企业"
            }, "aliases": ["3vjia"]},
            {"name": "打扮家", "properties": {
                "category": "3D设计软件",
                "level": "平台",
                "origin": "国产",
                "features": ["BIM技术", "施工图输出"]
            }, "aliases": []},
            {"name": "圆方软件", "properties": {
                "category": "3D设计软件",
                "level": "专业",
                "origin": "国产",
                "features": ["定制家具设计", "拆单生产"]
            }, "aliases": []},
            # ==================== 更多涂料品牌 ====================
            {"name": "大师漆", "properties": {
                "category": "涂料",
                "level": "高端",
                "origin": "美国",
                "parent": "PPG"
            }, "aliases": ["PPG大师漆"]},
            {"name": "宣伟", "properties": {
                "category": "涂料",
                "level": "高端",
                "origin": "美国"
            }, "aliases": ["Sherwin-Williams"]},
            {"name": "本杰明摩尔", "properties": {
                "category": "涂料",
                "level": "高端",
                "origin": "美国",
                "specialty": "色彩"
            }, "aliases": ["Benjamin Moore"]},
            {"name": "紫荆花", "properties": {
                "category": "涂料",
                "level": "中高端",
                "origin": "香港"
            }, "aliases": ["Bauhinia"]},
            {"name": "美涂士", "properties": {
                "category": "涂料",
                "level": "中端",
                "origin": "国产"
            }, "aliases": ["Maydos"]},
            # ==================== 更多地板品牌 ====================
            {"name": "扬子地板", "properties": {
                "category": "地板",
                "level": "中端",
                "origin": "国产"
            }, "aliases": []},
            {"name": "升达地板", "properties": {
                "category": "地板",
                "level": "中端",
                "origin": "国产"
            }, "aliases": []},
            {"name": "世友地板", "properties": {
                "category": "地板",
                "level": "中端",
                "origin": "国产"
            }, "aliases": []},
            {"name": "天格", "properties": {
                "category": "地板",
                "level": "高端",
                "origin": "国产",
                "specialty": "地暖实木地板"
            }, "aliases": ["天格地暖实木地板"]},
            {"name": "柏丽", "properties": {
                "category": "地板",
                "level": "高端",
                "origin": "德国"
            }, "aliases": ["PARADOR"]},
            {"name": "爱格", "properties": {
                "category": "地板/板材",
                "level": "高端",
                "origin": "奥地利"
            }, "aliases": ["EGGER"]},
            {"name": "得高", "properties": {
                "category": "地板",
                "level": "高端",
                "origin": "国产",
                "model": "进口地板代理"
            }, "aliases": []},
            # ==================== 更多卫浴品牌 ====================
            {"name": "唯宝", "properties": {
                "category": "卫浴",
                "level": "高端",
                "origin": "德国"
            }, "aliases": ["Villeroy & Boch"]},
            {"name": "伊奈", "properties": {
                "category": "卫浴",
                "level": "高端",
                "origin": "日本"
            }, "aliases": ["INAX"]},
            {"name": "美标", "properties": {
                "category": "卫浴",
                "level": "中高端",
                "origin": "美国"
            }, "aliases": ["American Standard"]},
            {"name": "浪鲸", "properties": {
                "category": "卫浴",
                "level": "中高端",
                "origin": "国产",
                "specialty": "浴缸"
            }, "aliases": ["SSWW"]},
            {"name": "安华", "properties": {
                "category": "卫浴",
                "level": "中端",
                "origin": "国产"
            }, "aliases": ["Annwa"]},
            {"name": "法恩莎", "properties": {
                "category": "卫浴",
                "level": "中端",
                "origin": "国产"
            }, "aliases": ["FAENZA"]},
            {"name": "德立", "properties": {
                "category": "淋浴房",
                "level": "高端",
                "origin": "国产"
            }, "aliases": ["Deli"]},
            {"name": "朗斯", "properties": {
                "category": "淋浴房",
                "level": "高端",
                "origin": "国产"
            }, "aliases": ["LENS"]},
            {"name": "玫瑰岛", "properties": {
                "category": "淋浴房",
                "level": "中高端",
                "origin": "国产"
            }, "aliases": ["ROSERY"]},
            # ==================== 更多定制家具品牌 ====================
            {"name": "皮阿诺", "properties": {
                "category": "定制家具",
                "level": "中端",
                "origin": "国产"
            }, "aliases": ["PIANO"]},
            {"name": "顶固", "properties": {
                "category": "定制家具",
                "level": "中高端",
                "origin": "国产"
            }, "aliases": ["Topstrong"]},
            {"name": "百得胜", "properties": {
                "category": "定制家具",
                "level": "中高端",
                "origin": "国产"
            }, "aliases": ["Paterson"]},
            {"name": "诗尼曼", "properties": {
                "category": "定制家具",
                "level": "中高端",
                "origin": "国产"
            }, "aliases": ["SNIMAY"]},
            {"name": "卡诺亚", "properties": {
                "category": "定制家具",
                "level": "中端",
                "origin": "国产"
            }, "aliases": ["Knoya"]},
            {"name": "玛格", "properties": {
                "category": "定制家具",
                "level": "高端",
                "origin": "国产"
            }, "aliases": ["MACIO"]},
            # ==================== 板材品牌 ====================
            {"name": "兔宝宝", "properties": {
                "category": "板材",
                "level": "高端",
                "origin": "国产",
                "products": ["生态板", "多层板", "OSB板"]
            }, "aliases": ["Tubao"]},
            {"name": "千年舟", "properties": {
                "category": "板材",
                "level": "高端",
                "origin": "国产",
                "products": ["生态板", "多层板"]
            }, "aliases": []},
            {"name": "莫干山", "properties": {
                "category": "板材",
                "level": "中高端",
                "origin": "国产"
            }, "aliases": []},
            {"name": "大王椰", "properties": {
                "category": "板材",
                "level": "中高端",
                "origin": "国产"
            }, "aliases": []},
            {"name": "克诺斯邦", "properties": {
                "category": "板材",
                "level": "高端",
                "origin": "奥地利",
                "products": ["颗粒板", "OSB板"]
            }, "aliases": ["Kronospan"]},
        ],

        # 环保标准实体
        EntityType.STANDARD: [
            {"name": "ENF级", "properties": {
                "formaldehyde": "≤0.025mg/m³", "standard": "GB/T 39600-2021", "level": "最高"
            }, "aliases": []},
            {"name": "E0级", "properties": {
                "formaldehyde": "≤0.050mg/m³", "standard": "GB/T 39600-2021", "level": "高"
            }, "aliases": []},
            {"name": "E1级", "properties": {
                "formaldehyde": "≤0.124mg/m³", "standard": "GB 18580-2017", "level": "合格"
            }, "aliases": []},
            {"name": "F四星", "properties": {
                "formaldehyde": "≤0.3mg/L", "standard": "日本JIS标准", "level": "高"
            }, "aliases": ["F★★★★"]},
            # 室内空气质量标准
            {"name": "室内空气质量标准", "properties": {
                "standard": "GB/T 18883-2022",
                "limits": {"甲醛": "≤0.08mg/m³", "TVOC": "≤0.60mg/m³", "苯": "≤0.03mg/m³", "氨": "≤0.20mg/m³"}
            }, "aliases": []},
            # 燃烧性能等级
            {"name": "A级不燃", "properties": {
                "standard": "GB 8624-2012",
                "description": "不燃材料",
                "examples": ["石材", "瓷砖", "金属"]
            }, "aliases": []},
            {"name": "B1级难燃", "properties": {
                "standard": "GB 8624-2012",
                "description": "难燃材料",
                "examples": ["阻燃板材", "防火涂料"]
            }, "aliases": []},
            {"name": "B2级可燃", "properties": {
                "standard": "GB 8624-2012",
                "description": "可燃材料",
                "examples": ["普通木材", "塑料"]
            }, "aliases": []},
            # 认证体系
            {"name": "十环认证", "properties": {
                "full_name": "中国环境标志",
                "issuer": "环保部",
                "type": "环保认证"
            }, "aliases": ["中国环境标志"]},
            {"name": "FSC认证", "properties": {
                "full_name": "森林管理委员会认证",
                "description": "木材可持续来源认证",
                "type": "环保认证"
            }, "aliases": ["森林认证"]},
            {"name": "CCC认证", "properties": {
                "full_name": "中国强制性产品认证",
                "description": "电器类产品必须",
                "type": "质量认证"
            }, "aliases": ["3C认证"]},
            {"name": "GREENGUARD认证", "properties": {
                "description": "室内空气质量认证",
                "origin": "美国",
                "type": "环保认证"
            }, "aliases": []},
            {"name": "蓝天使认证", "properties": {
                "description": "德国环保认证",
                "origin": "德国",
                "type": "环保认证"
            }, "aliases": []},
            # 验收标准
            {"name": "瓷砖空鼓率标准", "properties": {
                "wall_tile": "≤5%",
                "floor_tile": "≤3%",
                "detection": "空鼓锤敲击"
            }, "aliases": []},
            {"name": "墙面平整度标准", "properties": {
                "standard": "2m靠尺≤3mm",
                "verticality": "≤3mm"
            }, "aliases": []},
            {"name": "打压测试标准", "properties": {
                "pressure": "0.8MPa",
                "duration": "30分钟",
                "drop": "≤0.05MPa"
            }, "aliases": []},
            # 更多国家标准
            {"name": "GB 50210-2018", "properties": {
                "name": "建筑装饰装修工程质量验收标准",
                "type": "施工标准",
                "scope": "装修工程验收"
            }, "aliases": ["装修验收标准"]},
            {"name": "GB 50327-2001", "properties": {
                "name": "住宅装饰装修工程施工规范",
                "type": "施工标准",
                "scope": "住宅装修施工"
            }, "aliases": ["住宅装修规范"]},
            {"name": "GB 50303-2015", "properties": {
                "name": "建筑电气工程施工质量验收规范",
                "type": "施工标准",
                "scope": "电气工程验收"
            }, "aliases": ["电气验收规范"]},
            {"name": "GB 50242-2002", "properties": {
                "name": "建筑给水排水及采暖工程施工质量验收规范",
                "type": "施工标准",
                "scope": "水暖工程验收"
            }, "aliases": ["水暖验收规范"]},
            {"name": "GB/T 4100-2015", "properties": {
                "name": "陶瓷砖",
                "type": "产品标准",
                "scope": "瓷砖质量标准"
            }, "aliases": ["瓷砖国标"]},
            {"name": "GB/T 18102-2020", "properties": {
                "name": "浸渍纸层压木质地板",
                "type": "产品标准",
                "scope": "强化地板标准"
            }, "aliases": ["强化地板国标"]},
            {"name": "GB/T 18103-2013", "properties": {
                "name": "实木复合地板",
                "type": "产品标准",
                "scope": "实木复合地板标准"
            }, "aliases": ["实木复合地板国标"]},
            {"name": "GB 6952-2015", "properties": {
                "name": "卫生陶瓷",
                "type": "产品标准",
                "scope": "卫浴产品标准"
            }, "aliases": ["卫浴国标"]},
            {"name": "GB/T 8478-2020", "properties": {
                "name": "铝合金门窗",
                "type": "产品标准",
                "scope": "铝合金门窗标准"
            }, "aliases": ["门窗国标"]},
            # 行业标准
            {"name": "JG/T 122-2017", "properties": {
                "name": "建筑木门、木窗",
                "type": "行业标准",
                "scope": "木门窗标准"
            }, "aliases": []},
            {"name": "QB/T 2530-2011", "properties": {
                "name": "木制柜",
                "type": "行业标准",
                "scope": "定制家具标准"
            }, "aliases": []},
            {"name": "JC/T 2219-2014", "properties": {
                "name": "整体厨房",
                "type": "行业标准",
                "scope": "整体厨房标准"
            }, "aliases": []},
            {"name": "GB/T 35136-2017", "properties": {
                "name": "智能家居自动控制设备通用技术要求",
                "type": "产品标准",
                "scope": "智能家居标准"
            }, "aliases": ["智能家居国标"]},
            # 更多认证
            {"name": "ISO 9001", "properties": {
                "name": "质量管理体系认证",
                "type": "质量认证",
                "scope": "企业质量管理"
            }, "aliases": ["质量体系认证"]},
            {"name": "ISO 14001", "properties": {
                "name": "环境管理体系认证",
                "type": "环保认证",
                "scope": "企业环境管理"
            }, "aliases": ["环境体系认证"]},
            {"name": "CE认证", "properties": {
                "description": "欧盟强制性认证",
                "origin": "欧盟",
                "type": "质量认证"
            }, "aliases": []},
            {"name": "中国绿色产品认证", "properties": {
                "description": "国家统一绿色产品认证",
                "type": "环保认证"
            }, "aliases": ["绿色产品认证"]},
            {"name": "SGS认证", "properties": {
                "description": "瑞士通用公证行检测认证",
                "type": "质量认证",
                "scope": "第三方检测"
            }, "aliases": []},
            # 闭水试验标准
            {"name": "闭水试验标准", "properties": {
                "duration": "48小时",
                "water_depth": "3-5cm",
                "requirement": "无渗漏"
            }, "aliases": ["蓄水试验"]},
            # 地板验收标准
            {"name": "地板验收标准", "properties": {
                "flatness": "2m靠尺≤3mm",
                "gap": "≤0.5mm",
                "height_diff": "≤0.5mm",
                "requirement": "无空鼓响声"
            }, "aliases": []},
        ],

        # ==================== 十一、灯具照明系统 ====================
        EntityType.LIGHT_SOURCE: [
            {"name": "LED光源", "properties": {
                "params": {
                    "光效": {"普通": "80-100lm/W", "高效": "120-150lm/W"},
                    "色温": {"暖白光": "2700-3000K", "自然光": "4000-4500K", "冷白光": "5000-6500K"},
                    "显色指数": {"普通": "Ra≥80", "高显色": "Ra≥90", "专业": "Ra≥95"},
                    "蓝光危害": {"RG0": "豁免级", "RG1": "低危险"}
                },
                "chip_brands": {"国际": ["CREE", "欧司朗", "飞利浦", "日亚"], "国产": ["三安", "华灿"]}
            }, "aliases": ["LED"]},
        ],

        EntityType.LIGHTING: [
            {"name": "吊灯", "properties": {
                "types": ["单头吊灯", "多头吊灯", "枝形吊灯", "水晶吊灯", "艺术吊灯"],
                "materials": ["金属", "玻璃", "水晶", "亚克力", "布艺"],
                "install_height": {"客厅": "距地2.2-2.5m", "餐厅": "距桌面0.7-0.9m"}
            }, "aliases": []},
            {"name": "吸顶灯", "properties": {
                "types": ["圆形", "方形", "异形"],
                "functions": ["普通", "调光调色", "智能APP/语音"],
                "applications": ["卧室", "书房", "走廊"]
            }, "aliases": []},
            {"name": "风扇灯", "properties": {
                "types": ["吊扇灯", "隐形扇灯"],
                "blade_materials": ["实木叶", "ABS叶", "铁叶"],
                "sizes": ["42寸", "48寸", "52寸", "56寸"]
            }, "aliases": ["吊扇灯"]},
            {"name": "筒灯", "properties": {
                "types": ["嵌入式", "明装", "防眩"],
                "hole_sizes": ["75mm", "85mm", "100mm"],
                "power": "3W/5W/7W/9W/12W",
                "beam_angle": "60°-120°"
            }, "aliases": []},
            {"name": "射灯", "properties": {
                "types": ["嵌入式", "明装", "轨道射灯", "象鼻灯"],
                "beam_angle": {"窄光束": "15°-24°", "中光束": "36°-45°", "宽光束": "60°"},
                "power": "3W/5W/7W/12W/15W",
                "applications": ["重点照明", "洗墙"]
            }, "aliases": []},
            {"name": "磁吸轨道灯", "properties": {
                "track_types": ["嵌入式", "明装", "吊装"],
                "modules": ["格栅灯", "泛光灯", "射灯", "吊线灯"],
                "voltage": "48V安全电压",
                "brands": ["西顿", "三雄极光", "雷士"]
            }, "aliases": ["磁吸灯"]},
            {"name": "线性灯", "properties": {
                "types": ["嵌入式", "明装", "吊装"],
                "widths": ["20mm", "30mm", "50mm", "75mm"],
                "applications": ["办公", "商业", "家居"]
            }, "aliases": []},
            {"name": "灯带", "properties": {
                "types": ["软灯带", "硬灯条", "霓虹灯带"],
                "specs": {"灯珠密度": "60/120/240珠/米", "电压": "12V/24V/220V", "功率": "5-15W/米"},
                "install": ["灯槽", "铝槽", "硅胶套管"],
                "applications": ["氛围照明", "轮廓照明"]
            }, "aliases": ["LED灯带"]},
            {"name": "壁灯", "properties": {
                "types": ["床头壁灯", "过道壁灯", "户外壁灯"],
                "install_height": "1.8-2.0m"
            }, "aliases": []},
            {"name": "落地灯", "properties": {
                "types": ["阅读落地灯", "氛围落地灯", "钓鱼灯"],
                "height": "1.2-1.8m"
            }, "aliases": []},
            {"name": "台灯", "properties": {
                "types": ["护眼台灯", "装饰台灯", "工作台灯"],
                "eye_protection_params": ["无频闪", "无蓝光危害", "高显色Ra≥95", "照度均匀"],
                "brands": ["明基", "松下", "飞利浦"]
            }, "aliases": ["护眼灯"]},
            {"name": "橱柜灯", "properties": {
                "types": ["柜内感应灯", "层板灯", "吊柜底灯"]
            }, "aliases": []},
            {"name": "镜前灯", "properties": {
                "types": ["壁挂式", "镜柜一体"],
                "light_type": "无影光/柔光",
                "application": "卫生间/化妆台"
            }, "aliases": []},
            {"name": "衣柜灯", "properties": {
                "types": ["感应灯条", "挂衣杆灯", "层板灯"],
                "sensor": "人体感应/门控感应"
            }, "aliases": []},
            {"name": "楼梯灯", "properties": {
                "types": ["踏步灯", "感应灯", "扶手灯"],
                "features": ["人体感应", "渐亮渐灭"]
            }, "aliases": []},
            {"name": "庭院灯", "properties": {
                "types": ["柱头灯", "草坪灯", "路灯"],
                "power_source": ["市电", "太阳能"],
                "protection": "IP65防水"
            }, "aliases": ["花园灯"]},
            {"name": "草坪灯", "properties": {
                "height": "30-80cm",
                "power_source": ["太阳能", "市电"],
                "features": ["低矮", "柔和光线", "装饰性强"],
                "protection": "IP65防水",
                "applications": ["草坪", "花园小径", "庭院"]
            }, "aliases": ["草地灯"]},
            {"name": "地埋灯", "properties": {
                "application": ["庭院", "广场", "景观"],
                "protection": "IP67/IP68",
                "material": "不锈钢外壳"
            }, "aliases": []},
            {"name": "投光灯", "properties": {
                "application": ["建筑外墙", "广告牌", "景观"],
                "power": "10W-200W",
                "beam_angle": ["窄光", "宽光"]
            }, "aliases": ["泛光灯"]},
            {"name": "小夜灯", "properties": {
                "types": ["插电式", "充电式", "感应式"],
                "features": ["光控", "人体感应", "定时"],
                "application": ["卧室", "走廊", "卫生间"]
            }, "aliases": ["夜灯"]},
            {"name": "装饰串灯", "properties": {
                "types": ["星星灯", "铜线灯", "藤球灯"],
                "power_source": ["电池", "USB", "太阳能"],
                "application": "节日装饰/氛围营造"
            }, "aliases": ["串灯", "星星灯"]},
        ],

        EntityType.LIGHTING_PARAM: [
            {"name": "照度标准", "properties": {
                "客厅": "100-300lx",
                "卧室": "75-150lx",
                "书房": "300-500lx",
                "厨房": "150-300lx",
                "卫生间": "100-200lx",
                "餐厅": "150-300lx",
                "走廊": "50-100lx"
            }, "aliases": []},
            {"name": "色温推荐", "properties": {
                "暖色调空间": "2700-3000K",
                "中性空间": "3500-4000K",
                "工作空间": "4000-5000K"
            }, "aliases": []},
            {"name": "无主灯设计", "properties": {
                "灯具间距": "0.8-1.2m",
                "离墙距离": "0.3-0.5m",
                "要点": ["防眩设计", "分区控制"]
            }, "aliases": []},
        ],

        # ==================== 十二、软装配饰系统 ====================
        EntityType.CURTAIN: [
            {"name": "布艺窗帘", "properties": {
                "types": ["棉麻窗帘", "涤纶窗帘", "绒布窗帘", "纱帘"],
                "features": ["柔软", "装饰性强", "隔音保温"],
                "operation": ["手动", "电动"]
            }, "aliases": ["软帘"]},
            {"name": "手动窗帘", "properties": {
                "operation": "手动拉绳/手动轨道",
                "features": ["成本低", "无需电源"],
                "types": ["拉绳式", "手拉式"]
            }, "aliases": []},
            {"name": "电动窗帘", "properties": {
                "operation": "电机驱动",
                "features": ["智能控制", "便捷"],
                "control": ["遥控", "APP", "语音", "定时"]
            }, "aliases": ["智能窗帘"]},
            {"name": "棉麻窗帘", "properties": {
                "features": ["透气", "自然"],
                "cons": ["易皱", "缩水"],
                "category": "布艺窗帘"
            }, "aliases": []},
            {"name": "涤纶窗帘", "properties": {
                "features": ["耐用", "易打理"],
                "note": "主流选择",
                "category": "布艺窗帘"
            }, "aliases": []},
            {"name": "绒布窗帘", "properties": {
                "types": ["天鹅绒", "雪尼尔"],
                "features": ["质感好", "遮光"],
                "category": "布艺窗帘"
            }, "aliases": ["天鹅绒窗帘"]},
            {"name": "纱帘", "properties": {
                "features": ["轻盈", "透光"],
                "usage": "装饰/柔化光线",
                "category": "布艺窗帘"
            }, "aliases": ["雪纺窗帘"]},
            {"name": "遮光窗帘", "properties": {
                "grades": {"一级遮光": "≥99%", "二级遮光": "90-99%", "三级遮光": "70-90%"},
                "types": ["涂层遮光", "物理遮光"]
            }, "aliases": []},
            {"name": "百叶帘", "properties": {
                "materials": ["铝合金", "实木", "仿木", "PVC", "竹"],
                "blade_widths": ["25mm", "35mm", "50mm"],
                "features": ["防水", "易清洁"]
            }, "aliases": ["百叶窗"]},
            {"name": "卷帘", "properties": {
                "types": ["遮光卷帘", "阳光面料卷帘", "蜂巢帘", "斑马帘"],
                "features": {"蜂巢帘": "隔热/保温", "斑马帘": "调光功能"}
            }, "aliases": []},
            {"name": "罗马帘", "properties": {
                "types": ["平面罗马帘", "扇形罗马帘"],
                "features": "造型优雅"
            }, "aliases": []},
            {"name": "竖帘", "properties": {
                "materials": ["PVC", "布艺", "铝合金"],
                "blade_width": "89/127mm",
                "features": ["调光灵活", "适合大窗"],
                "applications": ["办公室", "大落地窗"]
            }, "aliases": ["垂直帘"]},
            {"name": "蜂巢帘", "properties": {
                "structure": "蜂窝状空气层",
                "features": ["隔热保温", "隔音", "节能"],
                "types": ["单层蜂巢", "双层蜂巢"],
                "operation": ["手动", "电动"]
            }, "aliases": ["风琴帘"]},
            {"name": "斑马帘", "properties": {
                "structure": "透光与遮光条纹交替",
                "features": ["调光灵活", "现代简约", "易清洁"],
                "operation": ["手动", "电动"],
                "applications": ["客厅", "书房", "办公室"],
                "light_control": "通过条纹错位调节透光度"
            }, "aliases": ["柔纱帘", "调光帘"]},
            {"name": "隔热帘", "properties": {
                "materials": ["涂银遮光布", "隔热涂层"],
                "features": ["阻挡紫外线", "降低室温"],
                "applications": ["西晒房间", "阳光房"]
            }, "aliases": ["防晒帘"]},
            {"name": "隔音帘", "properties": {
                "materials": ["加厚绒布", "多层复合"],
                "noise_reduction": "降噪10-15dB",
                "applications": ["临街房间", "卧室"]
            }, "aliases": []},
            {"name": "门帘", "properties": {
                "types": ["珠帘", "线帘", "布帘", "磁吸门帘"],
                "applications": ["隔断", "装饰", "防蚊"]
            }, "aliases": []},
            {"name": "真丝窗帘", "properties": {
                "material": "桑蚕丝",
                "features": ["光泽好", "质感高级"],
                "cons": ["需保养", "价格高"],
                "category": "高端窗帘"
            }, "aliases": []},
            {"name": "阻燃窗帘", "properties": {
                "standard": "GB/T 17591",
                "grades": ["B1级难燃", "B2级可燃"],
                "applications": ["公共场所", "酒店", "医院"]
            }, "aliases": ["防火窗帘"]},
            {"name": "窗帘褶皱", "properties": {
                "types": ["韩式褶", "四叉钩褶", "S钩褶", "波浪褶", "平褶"],
                "multiplier": {"1.5倍": "经济", "2倍": "标准", "2.5倍": "饱满"},
                "height": {"定高": "2.8m/3.0m", "定宽": "按需裁剪"}
            }, "aliases": ["打褶工艺"]},
            # 窗帘配件
            {"name": "罗马杆", "properties": {
                "materials": ["实木", "铝合金", "铁艺"],
                "diameters": ["22mm", "25mm", "28mm"],
                "features": ["装饰头多种造型", "安装简单"],
                "suitable": "窗帘较轻/装饰性强"
            }, "aliases": ["窗帘杆"]},
            {"name": "窗帘滑轨", "properties": {
                "types": ["铝合金轨道", "纳米轨道", "弯轨"],
                "shapes": ["直轨", "L型弯轨", "弧形轨"],
                "features": ["承重好", "滑动顺畅"],
                "suitable": "窗帘较重/异形窗"
            }, "aliases": ["滑轨", "轨道"]},
            {"name": "电动窗帘轨道", "properties": {
                "brands": ["杜亚", "DOOYA", "绿米"],
                "control": ["遥控", "APP", "语音", "定时"],
                "power": "电机驱动"
            }, "aliases": ["电动轨道"]},
            {"name": "窗帘挂钩", "properties": {
                "types": ["S钩", "四爪钩", "罗马环", "挂球"],
                "materials": ["塑料", "金属"]
            }, "aliases": ["挂钩"]},
            {"name": "窗帘扣", "properties": {
                "types": ["磁吸扣", "绑带", "挂钩扣", "U型扣"],
                "materials": ["金属", "布艺", "树脂"]
            }, "aliases": ["窗帘绑带"]},
            {"name": "窗帘铅坠", "properties": {
                "function": "增加窗帘垂感",
                "types": ["铅绳", "铅块", "链条"],
                "weight": "40-100g/米"
            }, "aliases": ["铅绳"]},
        ],

        EntityType.CARPET: [
            {"name": "羊毛地毯", "properties": {
                "origins": ["新西兰羊毛", "澳洲羊毛"],
                "features": ["柔软", "保暖", "弹性好"],
                "price_level": "高",
                "category": "天然纤维"
            }, "aliases": []},
            {"name": "真丝地毯", "properties": {
                "craft": "手工编织",
                "level": "奢侈品级",
                "category": "天然纤维"
            }, "aliases": []},
            {"name": "尼龙地毯", "properties": {
                "features": "耐磨性最好",
                "usage": "商用首选",
                "category": "化学纤维"
            }, "aliases": ["锦纶地毯"]},
            {"name": "涤纶地毯", "properties": {
                "features": "性价比高",
                "usage": "家用主流",
                "category": "化学纤维"
            }, "aliases": ["聚酯地毯"]},
            {"name": "手工地毯", "properties": {
                "types": ["波斯地毯", "土耳其地毯", "中国手工毯"],
                "crafts": ["手工打结", "手工枪刺", "手工编织"]
            }, "aliases": []},
            {"name": "方块地毯", "properties": {
                "size": "50×50cm",
                "category": "满铺地毯"
            }, "aliases": []},
            {"name": "客厅地毯", "properties": {
                "sizes": ["1.6×2.3m", "2×3m"],
                "category": "块毯"
            }, "aliases": []},
            {"name": "卧室地毯", "properties": {
                "sizes": ["1.4×2m", "1.6×2.3m"],
                "placement": ["床尾", "床侧", "全铺"],
                "category": "块毯"
            }, "aliases": []},
            {"name": "入户地垫", "properties": {
                "sizes": ["40×60cm", "50×80cm", "60×90cm"],
                "features": ["防滑", "吸水", "耐磨"],
                "materials": ["橡胶底", "PVC底"]
            }, "aliases": ["门垫", "脚垫"]},
            {"name": "走廊地毯", "properties": {
                "widths": ["60cm", "80cm", "100cm"],
                "features": ["长条形", "防滑"],
                "category": "块毯"
            }, "aliases": ["过道地毯"]},
            {"name": "剑麻地毯", "properties": {
                "material": "剑麻纤维",
                "features": ["天然环保", "耐磨", "防静电"],
                "category": "天然纤维"
            }, "aliases": []},
            {"name": "黄麻地毯", "properties": {
                "material": "黄麻纤维",
                "features": ["天然质感", "透气", "环保"],
                "styles": ["北欧", "日式", "田园"],
                "category": "天然纤维"
            }, "aliases": []},
            {"name": "竹编地毯", "properties": {
                "material": "竹纤维",
                "features": ["凉爽", "防滑", "易清洁"],
                "applications": ["夏季使用", "阳台"]
            }, "aliases": ["竹地毯"]},
            {"name": "浴室地垫", "properties": {
                "materials": ["硅藻土", "珊瑚绒", "PVC"],
                "features": ["吸水", "防滑", "速干"]
            }, "aliases": ["浴室防滑垫"]},
            {"name": "厨房地垫", "properties": {
                "materials": ["PVC", "橡胶", "棉麻"],
                "features": ["防滑", "防油", "易清洁"],
                "sizes": ["40×60cm", "40×120cm", "50×180cm"]
            }, "aliases": ["厨房防滑垫"]},
            {"name": "机织地毯", "properties": {
                "types": ["威尔顿机织", "阿克明斯特机织"],
                "features": {"威尔顿": "高密度/耐用", "阿克明斯特": "图案丰富"},
                "category": "工业地毯"
            }, "aliases": []},
            {"name": "簇绒地毯", "properties": {
                "types": ["圈绒", "割绒", "圈割绒"],
                "features": ["生产效率高", "性价比好"],
                "category": "工业地毯"
            }, "aliases": []},
            {"name": "丙纶地毯", "properties": {
                "material": "聚丙烯",
                "features": ["防水防污", "耐腐蚀", "价格低"],
                "applications": ["户外", "商用"],
                "category": "化学纤维"
            }, "aliases": ["PP地毯"]},
            # 经典手工地毯
            {"name": "波斯地毯", "properties": {
                "origin": "伊朗",
                "craft": "手工打结",
                "features": ["图案精美", "工艺复杂", "收藏价值"],
                "knot_density": "100-1000结/平方英寸",
                "materials": ["羊毛", "真丝", "棉"],
                "price_level": "奢侈品级"
            }, "aliases": ["伊朗地毯"]},
            {"name": "土耳其地毯", "properties": {
                "origin": "土耳其",
                "craft": "手工打结",
                "features": ["几何图案", "色彩鲜艳"],
                "knot_type": "土耳其结(对称结)"
            }, "aliases": []},
            {"name": "威尔顿地毯", "properties": {
                "craft": "威尔顿机织",
                "features": ["高密度", "耐用", "图案精细"],
                "applications": ["酒店", "高端住宅", "商业空间"],
                "category": "机织地毯"
            }, "aliases": []},
            {"name": "阿克明斯特地毯", "properties": {
                "craft": "阿克明斯特机织",
                "features": ["图案丰富", "色彩多样", "定制性强"],
                "applications": ["酒店", "剧院", "会议室"],
                "category": "机织地毯"
            }, "aliases": []},
        ],

        EntityType.BEDDING: [
            {"name": "纯棉四件套", "properties": {
                "types": ["普通纯棉", "精梳棉", "长绒棉", "有机棉"],
                "long_staple": ["埃及长绒棉", "匹马棉", "新疆长绒棉"],
                "count": {"40支": "普通", "60支": "中档", "80支": "高档", "100支+": "奢华"}
            }, "aliases": ["棉床品"]},
            {"name": "真丝床品", "properties": {
                "material": "桑蚕丝",
                "momme": ["16姆米", "19姆米", "22姆米", "25姆米"]
            }, "aliases": ["丝绸床品"]},
            {"name": "天丝床品", "properties": {
                "material": "莱赛尔",
                "features": ["丝滑", "环保"]
            }, "aliases": []},
            {"name": "羽绒被", "properties": {
                "types": {"鹅绒": ["白鹅绒", "灰鹅绒"], "鸭绒": ["白鸭绒", "灰鸭绒"]},
                "down_content": ["90%白鹅绒", "95%白鹅绒"],
                "fill_power": {"600+": "普通", "700+": "中档", "800+": "高档"}
            }, "aliases": []},
            {"name": "蚕丝被", "properties": {
                "types": ["桑蚕丝", "柞蚕丝"],
                "grades": ["优等品", "一等品"]
            }, "aliases": []},
            {"name": "乳胶枕", "properties": {
                "material": "天然乳胶",
                "shapes": ["波浪", "颗粒", "平面"]
            }, "aliases": []},
            {"name": "记忆棉枕", "properties": {
                "features": ["慢回弹", "贴合颈椎"]
            }, "aliases": []},
            {"name": "抱枕", "properties": {
                "types": ["沙发抱枕", "床头靠枕", "腰枕"]
            }, "aliases": []},
            {"name": "毛毯", "properties": {
                "types": ["羊毛毯", "珊瑚绒毯", "法兰绒毯", "针织毯"]
            }, "aliases": []},
            {"name": "羊毛被", "properties": {
                "origins": ["澳洲羊毛", "新西兰羊毛"],
                "features": ["保暖", "吸湿", "透气"],
                "seasons": ["秋冬"]
            }, "aliases": []},
            {"name": "棉花被", "properties": {
                "types": ["新疆棉", "普通棉"],
                "features": ["天然", "保暖", "透气"],
                "weight": {"春秋": "2-3斤", "冬季": "4-6斤"}
            }, "aliases": ["棉被"]},
            {"name": "纤维被", "properties": {
                "types": ["大豆纤维", "玉米纤维", "化纤被"],
                "features": ["轻便", "易清洗", "价格低"]
            }, "aliases": ["化纤被"]},
            {"name": "夏凉被", "properties": {
                "materials": ["天丝", "竹纤维", "冰丝"],
                "features": ["轻薄", "透气", "凉爽"],
                "seasons": ["夏季"]
            }, "aliases": ["空调被"]},
            {"name": "荞麦枕", "properties": {
                "filling": "荞麦壳",
                "features": ["透气", "支撑好", "天然"],
                "suitable": "喜欢硬枕者"
            }, "aliases": []},
            {"name": "羽绒枕", "properties": {
                "filling": ["鹅绒", "鸭绒"],
                "features": ["柔软", "蓬松", "保暖"],
                "suitable": "喜欢软枕者"
            }, "aliases": []},
            {"name": "桌布", "properties": {
                "types": ["餐桌布", "茶几布", "桌旗"],
                "materials": ["棉麻", "PVC", "蕾丝", "绒布"]
            }, "aliases": ["台布"]},
            {"name": "坐垫", "properties": {
                "types": ["餐椅坐垫", "飘窗垫", "榻榻米垫", "沙发坐垫"],
                "materials": ["棉麻", "绒布", "皮革", "记忆棉"]
            }, "aliases": ["椅垫"]},
            {"name": "亚麻床品", "properties": {
                "material": "亚麻纤维",
                "features": ["透气", "凉爽", "天然抗菌"],
                "suitable": "夏季使用"
            }, "aliases": []},
            {"name": "竹纤维床品", "properties": {
                "material": "竹纤维",
                "features": ["抗菌抑菌", "吸湿透气", "凉爽舒适", "环保可降解"],
                "types": ["竹纤维四件套", "竹纤维凉席", "竹纤维毛巾被"],
                "suitable": "夏季使用",
                "care": "温和洗涤，避免暴晒"
            }, "aliases": ["竹纤维寝具"]},
            {"name": "桌旗", "properties": {
                "types": ["中式桌旗", "欧式桌旗", "现代简约桌旗"],
                "materials": ["棉麻", "丝绸", "绒布", "刺绣"],
                "sizes": {"标准": "30x180cm", "长款": "30x210cm"},
                "applications": ["餐桌", "茶几", "玄关柜", "电视柜"],
                "styles": ["中式", "日式", "北欧", "轻奢"]
            }, "aliases": ["桌条", "桌带"]},
            {"name": "飘窗垫", "properties": {
                "types": ["定制飘窗垫", "成品飘窗垫"],
                "materials": ["海绵", "记忆棉", "乳胶", "棕垫"],
                "covers": ["棉麻", "绒布", "皮革"],
                "features": ["防滑", "可拆洗", "定制尺寸"],
                "thickness": {"薄款": "3-5cm", "标准": "5-8cm", "加厚": "8-10cm"}
            }, "aliases": ["飘窗坐垫", "窗台垫"]},
        ],

        EntityType.DECORATION: [
            {"name": "装饰画", "properties": {
                "types": ["油画", "版画", "摄影作品", "国画", "抽象画"],
                "frames": ["实木框", "PS发泡框", "铝合金框", "无框画"],
                "hanging": ["单幅", "组合画", "照片墙"]
            }, "aliases": []},
            {"name": "挂钟", "properties": {
                "types": ["机械钟", "石英钟", "智能钟"]
            }, "aliases": []},
            {"name": "装饰镜", "properties": {
                "types": ["装饰镜", "全身镜", "玄关镜"]
            }, "aliases": []},
            {"name": "香薰", "properties": {
                "types": ["香薰蜡烛", "香薰机", "藤条香薰", "香炉"]
            }, "aliases": ["香薰蜡烛"]},
            {"name": "陶瓷摆件", "properties": {
                "types": ["花瓶", "雕塑", "器皿"]
            }, "aliases": []},
            {"name": "金属摆件", "properties": {
                "materials": ["铜器", "铁艺", "不锈钢"]
            }, "aliases": []},
            {"name": "木质摆件", "properties": {
                "types": ["木雕", "根雕", "木质工艺品"],
                "materials": ["黑檀", "紫檀", "花梨木", "崖柏"]
            }, "aliases": []},
            {"name": "玻璃摆件", "properties": {
                "types": ["琉璃", "水晶", "艺术玻璃"],
                "features": ["通透", "折射光线"]
            }, "aliases": []},
            {"name": "布艺摆件", "properties": {
                "types": ["布艺玩偶", "刺绣摆件", "编织摆件"]
            }, "aliases": []},
            {"name": "相框", "properties": {
                "materials": ["实木", "金属", "亚克力", "皮革"],
                "sizes": ["4寸", "6寸", "7寸", "8寸", "10寸", "A4"],
                "types": ["单框", "组合框", "连体框"]
            }, "aliases": ["照片框"]},
            {"name": "托盘", "properties": {
                "materials": ["实木", "金属", "大理石", "皮革"],
                "applications": ["茶几", "餐桌", "玄关", "浴室"]
            }, "aliases": []},
            {"name": "收纳盒", "properties": {
                "materials": ["皮革", "布艺", "藤编", "亚克力"],
                "applications": ["首饰", "遥控器", "杂物"]
            }, "aliases": ["收纳篮"]},
            {"name": "烛台", "properties": {
                "materials": ["金属", "玻璃", "陶瓷", "水晶"],
                "types": ["单头", "多头", "落地式", "壁挂式"]
            }, "aliases": []},
            {"name": "书立", "properties": {
                "materials": ["金属", "实木", "亚克力", "石材"],
                "styles": ["简约", "创意", "复古"]
            }, "aliases": ["书档"]},
            {"name": "纸巾盒", "properties": {
                "materials": ["皮革", "实木", "金属", "陶瓷"],
                "applications": ["客厅", "卧室", "餐厅", "卫生间"]
            }, "aliases": []},
            {"name": "果盘", "properties": {
                "materials": ["陶瓷", "玻璃", "金属", "实木"],
                "types": ["单层", "多层", "旋转式"]
            }, "aliases": ["水果盘"]},
            {"name": "花艺", "properties": {
                "types": ["鲜花", "干花", "永生花", "仿真花"],
                "styles": ["欧式", "日式", "中式", "现代"]
            }, "aliases": ["插花"]},
            {"name": "壁挂装饰", "properties": {
                "types": ["金属壁挂", "木质壁挂", "编织壁挂", "镜面壁挂"],
                "styles": ["现代", "波西米亚", "北欧", "中式"]
            }, "aliases": []},
            {"name": "置物架", "properties": {
                "types": ["隔板", "壁龛", "悬浮架"],
                "materials": ["实木", "金属", "亚克力"],
                "applications": ["客厅", "卧室", "书房", "卫生间"]
            }, "aliases": ["墙上置物架"]},
            {"name": "软木板", "properties": {
                "types": ["软木板", "毛毡板", "磁性板"],
                "applications": ["留言", "照片展示", "备忘"],
                "sizes": ["30×40cm", "40×60cm", "60×90cm"]
            }, "aliases": ["留言板"]},
            {"name": "石材摆件", "properties": {
                "types": ["玉石摆件", "大理石摆件", "水晶摆件"],
                "styles": ["中式", "现代", "轻奢"]
            }, "aliases": []},
            {"name": "树脂摆件", "properties": {
                "types": ["人物雕塑", "动物摆件", "抽象艺术"],
                "features": ["造型丰富", "价格适中", "轻便"]
            }, "aliases": []},
            {"name": "挂毯", "properties": {
                "types": ["编织挂毯", "刺绣挂毯", "印花挂毯", "波西米亚挂毯"],
                "materials": ["棉麻", "羊毛", "丝绸", "混纺"],
                "styles": ["波西米亚", "北欧", "民族风", "现代简约"],
                "applications": ["客厅", "卧室", "玄关"],
                "sizes": ["小型(50x70cm)", "中型(100x150cm)", "大型(150x200cm)"]
            }, "aliases": ["壁毯", "墙毯"]},
        ],

        EntityType.PLANT: [
            {"name": "大型绿植", "properties": {
                "types": ["琴叶榕", "龟背竹", "天堂鸟", "散尾葵", "橡皮树", "发财树", "幸福树", "龙血树"]
            }, "aliases": []},
            {"name": "中型绿植", "properties": {
                "types": ["虎皮兰", "绿萝", "吊兰", "常春藤", "文竹", "富贵竹"]
            }, "aliases": []},
            {"name": "小型绿植", "properties": {
                "types": ["多肉植物", "仙人掌", "空气凤梨", "苔藓微景观"]
            }, "aliases": ["多肉"]},
            {"name": "水培植物", "properties": {
                "types": ["绿萝", "铜钱草", "水仙"]
            }, "aliases": []},
            {"name": "仿真植物", "properties": {
                "types": ["仿真树", "仿真花", "仿真绿植", "永生花"]
            }, "aliases": []},
            {"name": "花瓶", "properties": {
                "materials": ["陶瓷", "玻璃", "金属", "藤编"]
            }, "aliases": []},
            {"name": "花盆", "properties": {
                "materials": ["陶土盆", "水泥盆", "塑料盆", "金属盆"]
            }, "aliases": []},
            {"name": "花架", "properties": {
                "types": ["落地花架", "壁挂花架", "悬挂花架", "阶梯花架"],
                "materials": ["铁艺", "实木", "竹制"],
                "applications": ["阳台", "客厅", "庭院"]
            }, "aliases": []},
            {"name": "干花", "properties": {
                "types": ["尤加利", "棉花", "蒲苇", "满天星", "薰衣草"],
                "features": ["无需养护", "持久", "装饰性强"],
                "applications": ["花瓶插花", "花环", "壁挂"]
            }, "aliases": []},
            {"name": "鲜花", "properties": {
                "types": ["玫瑰", "百合", "郁金香", "向日葵", "绣球", "芍药"],
                "care": ["换水", "修剪", "保鲜剂"],
                "lifespan": "7-14天"
            }, "aliases": []},
            {"name": "永生花", "properties": {
                "process": "脱水脱色+染色",
                "lifespan": "3-5年",
                "features": ["保持鲜花形态", "无需养护"]
            }, "aliases": ["保鲜花"]},
            {"name": "净化空气植物", "properties": {
                "types": ["绿萝", "吊兰", "虎皮兰", "芦荟", "常春藤"],
                "function": "吸收甲醛/净化空气",
                "applications": ["新装修房", "卧室", "办公室"]
            }, "aliases": []},
        ],

        # ==================== 十三、智能家居系统 ====================
        EntityType.SMART_PROTOCOL: [
            {"name": "WiFi", "properties": {
                "frequency": "2.4GHz/5GHz",
                "pros": ["带宽大", "普及"],
                "cons": ["功耗高", "设备数限制"],
                "applications": ["摄像头", "音箱"]
            }, "aliases": []},
            {"name": "Zigbee", "properties": {
                "frequency": "2.4GHz",
                "features": ["低功耗", "自组网", "mesh"],
                "device_count": "理论65000+",
                "requires": "网关",
                "applications": ["传感器", "开关"]
            }, "aliases": []},
            {"name": "Z-Wave", "properties": {
                "frequency": "908MHz(美)/868MHz(欧)",
                "features": ["干扰少", "穿墙强"],
                "device_count": "232个"
            }, "aliases": []},
            {"name": "蓝牙Mesh", "properties": {
                "features": ["低功耗", "直连"],
                "applications": ["门锁", "灯具"]
            }, "aliases": ["蓝牙"]},
            {"name": "Thread", "properties": {
                "features": ["IPv6", "低功耗", "mesh"],
                "note": "Matter协议基础"
            }, "aliases": []},
            {"name": "Matter", "properties": {
                "features": ["跨平台", "统一标准"],
                "supporters": ["苹果", "谷歌", "亚马逊", "三星"]
            }, "aliases": []},
            # 有线协议
            {"name": "KNX", "properties": {
                "type": "有线总线协议",
                "origin": "欧洲标准",
                "features": ["稳定可靠", "抗干扰强", "适合大型项目"],
                "applications": ["高端别墅", "商业建筑", "酒店"],
                "cons": ["布线复杂", "成本高"]
            }, "aliases": ["KNX总线"]},
            {"name": "RS-485", "properties": {
                "type": "有线总线协议",
                "features": ["工业级稳定", "传输距离远", "抗干扰"],
                "max_distance": "1200m",
                "applications": ["工业控制", "智能家居"]
            }, "aliases": ["485总线"]},
        ],

        EntityType.SMART_HOME: [
            {"name": "智能音箱", "properties": {
                "brands": {"国际": ["Amazon Echo", "Google Home", "Apple HomePod"], "国产": ["小爱同学", "天猫精灵", "小度"]},
                "functions": ["语音控制", "智能家居中枢", "音乐播放"]
            }, "aliases": ["智能助手"]},
            {"name": "智能门锁", "properties": {
                "unlock_methods": ["指纹", "密码", "人脸", "刷卡", "钥匙", "远程"],
                "brands": ["小米", "德施曼", "凯迪仕", "鹿客"],
                "features": ["临时密码", "开门记录", "防撬报警"]
            }, "aliases": ["指纹锁", "电子锁"]},
            {"name": "智能摄像头", "properties": {
                "types": ["室内摄像头", "室外摄像头", "门铃摄像头"],
                "features": ["移动侦测", "双向语音", "云存储", "本地存储"],
                "brands": ["海康威视", "大华", "小米", "萤石"]
            }, "aliases": ["监控摄像头"]},
            {"name": "智能开关", "properties": {
                "types": ["单火线开关", "零火线开关", "场景开关"],
                "protocols": ["WiFi", "Zigbee", "蓝牙Mesh"],
                "brands": ["Aqara", "小米", "欧瑞博"]
            }, "aliases": []},
            {"name": "智能窗帘", "properties": {
                "types": ["电动窗帘", "电动卷帘", "电动百叶"],
                "brands": ["杜亚", "绿米", "欧瑞博"],
                "control": ["APP", "语音", "定时", "光感"]
            }, "aliases": ["电动窗帘"]},
            {"name": "智能传感器", "properties": {
                "types": ["人体传感器", "门窗传感器", "温湿度传感器", "烟雾传感器", "水浸传感器"],
                "brands": ["Aqara", "小米", "涂鸦"]
            }, "aliases": []},
            {"name": "智能网关", "properties": {
                "function": "连接Zigbee/蓝牙设备",
                "brands": ["Aqara", "小米", "华为"]
            }, "aliases": []},
            {"name": "扫地机器人", "properties": {
                "functions": ["扫地", "拖地", "自动集尘", "自动洗拖布"],
                "navigation": ["激光导航", "视觉导航"],
                "brands": ["石头", "科沃斯", "追觅", "云鲸", "iRobot"]
            }, "aliases": ["扫拖机器人"]},
            {"name": "智能灯泡", "properties": {
                "features": ["调光调色", "远程控制", "定时开关", "场景模式"],
                "protocols": ["WiFi", "Zigbee", "蓝牙"],
                "brands": ["飞利浦Hue", "Yeelight", "小米"]
            }, "aliases": ["智能灯"]},
            {"name": "智能插座", "properties": {
                "features": ["远程控制", "定时开关", "电量统计", "过载保护"],
                "types": ["墙插", "排插", "转换插"],
                "brands": ["小米", "公牛", "Aqara"]
            }, "aliases": []},
            {"name": "智能温控器", "properties": {
                "functions": ["温度控制", "定时调节", "远程控制", "学习习惯"],
                "applications": ["地暖", "空调", "壁挂炉"],
                "brands": ["Nest", "Ecobee", "小米"]
            }, "aliases": ["智能恒温器"]},
            {"name": "智能晾衣架", "properties": {
                "functions": ["升降", "照明", "风干", "消毒", "烘干"],
                "control": ["遥控", "APP", "语音"],
                "brands": ["好太太", "晾霸", "邦先生"]
            }, "aliases": ["电动晾衣架"]},
            {"name": "智能马桶盖", "properties": {
                "functions": ["座圈加热", "臀洗", "妇洗", "暖风烘干", "除臭"],
                "brands": ["TOTO", "松下", "海尔"],
                "note": "可加装普通马桶"
            }, "aliases": ["智能坐便盖"]},
            {"name": "智能新风机", "properties": {
                "functions": ["空气净化", "PM2.5监测", "CO2监测", "自动调节"],
                "types": ["壁挂式", "柜式"],
                "brands": ["松下", "远大", "造梦者"]
            }, "aliases": []},
            {"name": "智能空气净化器", "properties": {
                "functions": ["PM2.5过滤", "甲醛净化", "杀菌消毒", "智能联动"],
                "brands": ["小米", "戴森", "IQAir", "布鲁雅尔"]
            }, "aliases": []},
            {"name": "智能门铃", "properties": {
                "features": ["可视对讲", "移动侦测", "远程查看", "云存储"],
                "brands": ["小米", "萤石", "Ring"]
            }, "aliases": ["可视门铃"]},
            {"name": "智能中控屏", "properties": {
                "types": ["墙面中控", "桌面中控"],
                "features": ["场景控制", "可视对讲", "背景音乐", "安防监控"],
                "brands": ["欧瑞博", "Aqara", "华为"]
            }, "aliases": ["智能面板"]},
            {"name": "洗地机", "properties": {
                "functions": ["吸尘", "洗地", "拖地", "自清洁"],
                "features": ["干湿两用", "边角清洁"],
                "brands": ["添可", "必胜", "追觅", "石头"]
            }, "aliases": []},
            {"name": "擦窗机器人", "properties": {
                "types": ["真空吸附", "风机吸附"],
                "features": ["自动规划", "边框检测", "防跌落"],
                "brands": ["科沃斯", "玻妞"]
            }, "aliases": []},
            {"name": "智能浴室镜", "properties": {
                "features": ["防雾", "LED照明", "时间显示", "触控操作"],
                "extras": ["蓝牙音箱", "智能联动"]
            }, "aliases": ["智能镜"]},
            {"name": "智能加湿器", "properties": {
                "types": ["超声波", "蒸发式", "混合式"],
                "features": ["智能恒湿", "APP控制", "水质净化"],
                "brands": ["小米", "戴森", "飞利浦"]
            }, "aliases": []},
            {"name": "背景音乐系统", "properties": {
                "types": ["分区系统", "全宅系统"],
                "components": ["主机", "音箱", "控制面板"],
                "brands": ["泊声", "向往", "悠达"]
            }, "aliases": ["全宅音乐"]},
            {"name": "智能投影仪", "properties": {
                "types": ["激光投影", "LED投影", "超短焦"],
                "features": ["自动对焦", "梯形校正", "智能系统"],
                "brands": ["极米", "坚果", "当贝", "爱普生"]
            }, "aliases": ["家用投影"]},
            # 智能家居平台
            {"name": "Apple HomeKit", "properties": {
                "company": "Apple",
                "features": ["Siri语音控制", "家庭APP", "自动化场景", "安全加密"],
                "protocols": ["WiFi", "蓝牙", "Thread"],
                "ecosystem": "苹果生态",
                "pros": ["隐私保护好", "稳定性高", "界面美观"],
                "cons": ["设备选择少", "价格较高"]
            }, "aliases": ["HomeKit", "苹果智能家居"]},
            {"name": "小米米家", "properties": {
                "company": "小米",
                "features": ["小爱同学语音控制", "米家APP", "场景联动", "设备丰富"],
                "protocols": ["WiFi", "蓝牙", "Zigbee"],
                "ecosystem": "小米生态链",
                "pros": ["设备丰富", "性价比高", "生态完善"],
                "cons": ["部分设备需网关"]
            }, "aliases": ["米家", "小米智能家居"]},
            {"name": "华为HiLink", "properties": {
                "company": "华为",
                "features": ["小艺语音控制", "智慧生活APP", "超级终端", "鸿蒙智联"],
                "protocols": ["WiFi", "蓝牙", "Zigbee"],
                "ecosystem": "华为生态",
                "pros": ["连接稳定", "品牌背书", "鸿蒙系统"],
                "cons": ["设备相对较少"]
            }, "aliases": ["HiLink", "华为智能家居", "鸿蒙智联"]},
            {"name": "天猫精灵平台", "properties": {
                "company": "阿里巴巴",
                "features": ["天猫精灵语音控制", "精灵APP", "场景模式", "购物联动"],
                "protocols": ["WiFi", "蓝牙", "Zigbee"],
                "ecosystem": "阿里生态",
                "pros": ["设备接入多", "购物方便"],
                "cons": ["稳定性一般"]
            }, "aliases": ["天猫精灵", "AliGenie"]},
            {"name": "涂鸦智能平台", "properties": {
                "company": "涂鸦智能",
                "type": "IoT开发平台",
                "features": ["涂鸦APP", "白标方案", "全球化部署", "多品牌兼容"],
                "protocols": ["WiFi", "蓝牙", "Zigbee", "NB-IoT"],
                "pros": ["品牌兼容性强", "全球化", "开发者友好"],
                "cons": ["用户认知度低"]
            }, "aliases": ["涂鸦", "Tuya Smart"]},
            # 智能场景模式
            {"name": "回家模式", "properties": {
                "type": "智能场景",
                "triggers": ["开门", "地理围栏", "手动触发"],
                "actions": ["开灯", "开空调", "播放音乐", "打开窗帘"],
                "description": "回家时自动执行的场景联动"
            }, "aliases": ["到家模式"]},
            {"name": "离家模式", "properties": {
                "type": "智能场景",
                "triggers": ["关门", "地理围栏", "手动触发"],
                "actions": ["关灯", "关空调", "关闭窗帘", "开启安防"],
                "description": "离家时自动执行的场景联动"
            }, "aliases": ["外出模式"]},
            {"name": "睡眠模式", "properties": {
                "type": "智能场景",
                "triggers": ["定时", "语音指令", "手动触发"],
                "actions": ["关灯", "调暗夜灯", "关闭窗帘", "调低空调温度", "开启勿扰"],
                "description": "睡前自动执行的场景联动"
            }, "aliases": ["晚安模式", "就寝模式"]},
            {"name": "观影模式", "properties": {
                "type": "智能场景",
                "triggers": ["语音指令", "手动触发", "遥控器"],
                "actions": ["关闭主灯", "打开氛围灯", "关闭窗帘", "打开投影/电视"],
                "description": "观看电影时的场景联动"
            }, "aliases": ["影院模式", "电影模式"]},
            {"name": "会客模式", "properties": {
                "type": "智能场景",
                "triggers": ["语音指令", "手动触发"],
                "actions": ["调亮灯光", "播放背景音乐", "调节空调温度"],
                "description": "接待客人时的场景联动"
            }, "aliases": ["待客模式"]},
            {"name": "阅读模式", "properties": {
                "type": "智能场景",
                "triggers": ["语音指令", "手动触发"],
                "actions": ["打开阅读灯", "调暗其他灯光", "关闭电视"],
                "description": "阅读时的场景联动"
            }, "aliases": ["读书模式"]},
            {"name": "用餐模式", "properties": {
                "type": "智能场景",
                "triggers": ["语音指令", "手动触发", "定时"],
                "actions": ["打开餐厅灯", "播放轻音乐", "调节空调"],
                "description": "用餐时的场景联动"
            }, "aliases": ["就餐模式"]},
            # 补充智能设备
            {"name": "智能猫眼", "properties": {
                "features": ["可视对讲", "移动侦测", "远程查看", "人脸识别"],
                "types": ["电池供电", "有线供电"],
                "brands": ["小米", "萤石", "德施曼"]
            }, "aliases": ["电子猫眼", "可视猫眼"]},
            {"name": "智能门禁", "properties": {
                "types": ["人脸识别门禁", "刷卡门禁", "密码门禁", "指纹门禁"],
                "applications": ["小区", "办公楼", "别墅"],
                "features": ["远程开门", "访客记录", "临时授权"]
            }, "aliases": ["门禁系统"]},
            {"name": "电动窗", "properties": {
                "types": ["电动平开窗", "电动推拉窗", "电动天窗"],
                "control": ["遥控", "APP", "语音", "雨感自动关闭"],
                "applications": ["高层住宅", "别墅", "阳光房"]
            }, "aliases": ["智能窗户", "自动窗"]},
        ],

        # ==================== 热水系统 ====================
        EntityType.WATER_HEATER: [
            {"name": "燃气热水器", "properties": {
                "types": ["强排式", "平衡式", "冷凝式"],
                "capacity": {"13L": "一厨一卫", "16L": "一厨两卫", "20L+": "大户型"},
                "functions": ["恒温", "零冷水", "防冻"],
                "brands": ["林内", "能率", "万和", "万家乐"]
            }, "aliases": []},
            {"name": "电热水器", "properties": {
                "types": {"储水式": {"容量": "40-100L", "功率": "1500-3000W"}, "即热式": {"功率": "6000-8500W"}},
                "inner_tank": ["搪瓷内胆", "不锈钢内胆", "钛金内胆"],
                "brands": ["A.O.史密斯", "海尔", "美的"]
            }, "aliases": []},
            {"name": "空气能热水器", "properties": {
                "principle": "空气源热泵",
                "cop": "3-4",
                "pros": "节能",
                "cons": ["初投资高", "占空间"],
                "brands": ["美的", "格力", "纽恩泰"]
            }, "aliases": ["空气源热泵热水器"]},
            {"name": "太阳能热水器", "properties": {
                "types": ["真空管式", "平板式"],
                "applications": ["别墅", "顶楼"]
            }, "aliases": []},
        ],

        # 区域市场实体
        EntityType.REGION: [
            # 产业集群
            {"name": "佛山陶瓷产区", "properties": {
                "location": "广东佛山",
                "specialty": "瓷砖",
                "status": "中国建陶第一镇",
                "brands": ["东鹏", "马可波罗", "蒙娜丽莎", "冠珠"]
            }, "aliases": ["佛山"]},
            {"name": "顺德家具产区", "properties": {
                "location": "广东顺德",
                "specialty": "家具",
                "status": "中国家具制造重镇",
                "brands": ["联邦", "皇朝"]
            }, "aliases": ["顺德"]},
            {"name": "湖州地板产区", "properties": {
                "location": "浙江湖州",
                "specialty": "木地板",
                "status": "中国木地板之都",
                "brands": ["圣象", "大自然"]
            }, "aliases": ["南浔"]},
            {"name": "南安卫浴产区", "properties": {
                "location": "福建南安",
                "specialty": "卫浴五金",
                "brands": ["九牧", "辉煌"]
            }, "aliases": ["南安"]},
            {"name": "广州定制产区", "properties": {
                "location": "广东广州",
                "specialty": "定制家具",
                "brands": ["欧派", "索菲亚", "尚品宅配"]
            }, "aliases": []},
            # 消费区域
            {"name": "华南市场", "properties": {
                "regions": ["广东", "福建", "海南"],
                "features": ["品牌意识强", "追求品质", "防潮需求高"],
                "style_preference": ["现代简约", "轻奢", "新中式"]
            }, "aliases": []},
            {"name": "华东市场", "properties": {
                "regions": ["上海", "江苏", "浙江", "安徽"],
                "features": ["国际视野", "设计导向", "品质要求高"],
                "style_preference": ["现代简约", "北欧", "日式"]
            }, "aliases": []},
            {"name": "华北市场", "properties": {
                "regions": ["北京", "天津", "河北", "山西"],
                "features": ["文化底蕴", "环保意识强", "采暖需求"],
                "style_preference": ["新中式", "现代简约"]
            }, "aliases": []},
            {"name": "西南市场", "properties": {
                "regions": ["四川", "重庆", "云南", "贵州"],
                "features": ["性价比导向", "本土品牌接受度高"],
                "style_preference": ["现代简约", "新中式"]
            }, "aliases": []},
            # 更多产业集群
            {"name": "晋江陶瓷产区", "properties": {
                "location": "福建晋江",
                "specialty": "外墙砖",
                "brands": ["协进", "华泰"]
            }, "aliases": ["晋江"]},
            {"name": "淄博陶瓷产区", "properties": {
                "location": "山东淄博",
                "specialty": "内墙砖",
                "features": "性价比高"
            }, "aliases": ["淄博"]},
            {"name": "高安陶瓷产区", "properties": {
                "location": "江西高安",
                "specialty": "瓷砖",
                "features": ["产能大", "中低端为主"]
            }, "aliases": ["高安"]},
            {"name": "东莞家具产区", "properties": {
                "location": "广东东莞",
                "specialty": "出口家具",
                "features": ["台资/港资企业"]
            }, "aliases": ["东莞"]},
            {"name": "安吉椅业产区", "properties": {
                "location": "浙江安吉",
                "specialty": "办公椅",
                "status": "全球最大办公椅产区"
            }, "aliases": ["安吉"]},
            {"name": "成都家具产区", "properties": {
                "location": "四川成都",
                "specialty": "板式家具",
                "brands": ["全友", "掌上明珠"]
            }, "aliases": []},
            {"name": "嘉善木门产区", "properties": {
                "location": "浙江嘉善",
                "specialty": "木门",
                "brands": ["梦天", "TATA"]
            }, "aliases": ["嘉善"]},
            {"name": "常州地板产区", "properties": {
                "location": "江苏常州",
                "specialty": "强化地板",
                "features": "出口基地"
            }, "aliases": ["常州"]},
            {"name": "顺德涂料产区", "properties": {
                "location": "广东顺德",
                "specialty": "涂料",
                "brands": ["华润", "嘉宝莉"]
            }, "aliases": []},
            {"name": "临朐门窗产区", "properties": {
                "location": "山东临朐",
                "specialty": "铝型材/门窗"
            }, "aliases": ["临朐"]},
        ],

        # 销售渠道实体
        EntityType.CHANNEL: [
            {"name": "红星美凯龙", "properties": {
                "type": "家居卖场",
                "positioning": "中高端",
                "coverage": "全国连锁"
            }, "aliases": []},
            {"name": "居然之家", "properties": {
                "type": "家居卖场",
                "positioning": "中高端",
                "coverage": "全国连锁"
            }, "aliases": []},
            {"name": "百安居", "properties": {
                "type": "建材超市",
                "positioning": "中端",
                "origin": "英国"
            }, "aliases": ["B&Q"]},
            {"name": "天猫家装", "properties": {
                "type": "电商平台",
                "features": ["品牌旗舰店", "官方直营"]
            }, "aliases": []},
            {"name": "京东家装", "properties": {
                "type": "电商平台",
                "features": ["自营", "物流快"]
            }, "aliases": []},
            {"name": "装修公司", "properties": {
                "types": ["全国连锁", "本地公司", "工作室"],
                "services": ["设计", "施工", "主材代购"]
            }, "aliases": []},
        ],
    }

    # 预定义的关系数据
    PREDEFINED_RELATIONS = [
        # ==================== 材料适用于空间 ====================
        ("瓷砖", "客厅", RelationType.SUITABLE_FOR, {"recommendation": "高"}),
        ("瓷砖", "厨房", RelationType.SUITABLE_FOR, {"recommendation": "高"}),
        ("瓷砖", "卫生间", RelationType.SUITABLE_FOR, {"recommendation": "高"}),
        ("瓷砖", "阳台", RelationType.SUITABLE_FOR, {"recommendation": "高"}),
        ("木地板", "客厅", RelationType.SUITABLE_FOR, {"recommendation": "高"}),
        ("木地板", "卧室", RelationType.SUITABLE_FOR, {"recommendation": "高"}),
        ("木地板", "书房", RelationType.SUITABLE_FOR, {"recommendation": "高"}),
        ("大理石", "客厅", RelationType.SUITABLE_FOR, {"recommendation": "中"}),
        ("大理石", "玄关", RelationType.SUITABLE_FOR, {"recommendation": "高"}),
        ("岩板", "客厅", RelationType.SUITABLE_FOR, {"recommendation": "高"}),
        ("岩板", "厨房", RelationType.SUITABLE_FOR, {"recommendation": "高", "usage": "台面/墙面"}),
        ("SPC地板", "厨房", RelationType.SUITABLE_FOR, {"recommendation": "高"}),
        ("SPC地板", "卫生间", RelationType.SUITABLE_FOR, {"recommendation": "中"}),
        ("乳胶漆", "客厅", RelationType.SUITABLE_FOR, {"recommendation": "高"}),
        ("乳胶漆", "卧室", RelationType.SUITABLE_FOR, {"recommendation": "高"}),
        ("墙布", "客厅", RelationType.SUITABLE_FOR, {"recommendation": "高"}),
        ("墙布", "卧室", RelationType.SUITABLE_FOR, {"recommendation": "高"}),
        ("硅藻泥", "卧室", RelationType.SUITABLE_FOR, {"recommendation": "高", "reason": "调湿净化"}),
        ("硅藻泥", "儿童房", RelationType.SUITABLE_FOR, {"recommendation": "高", "reason": "环保"}),
        ("微水泥", "客厅", RelationType.SUITABLE_FOR, {"recommendation": "中"}),
        ("石膏板吊顶", "客厅", RelationType.SUITABLE_FOR, {"recommendation": "高"}),
        ("石膏板吊顶", "卧室", RelationType.SUITABLE_FOR, {"recommendation": "高"}),
        ("铝扣板", "厨房", RelationType.SUITABLE_FOR, {"recommendation": "高"}),
        ("铝扣板", "卫生间", RelationType.SUITABLE_FOR, {"recommendation": "高"}),
        ("桑拿板", "阳台", RelationType.SUITABLE_FOR, {"recommendation": "高"}),

        # ==================== 材料属于风格 ====================
        ("木地板", "北欧", RelationType.BELONGS_TO_STYLE, {"match_score": 0.9}),
        ("木地板", "日式", RelationType.BELONGS_TO_STYLE, {"match_score": 0.9}),
        ("实木地板", "新中式", RelationType.BELONGS_TO_STYLE, {"match_score": 0.85}),
        ("大理石", "轻奢", RelationType.BELONGS_TO_STYLE, {"match_score": 0.9}),
        ("大理石", "欧式", RelationType.BELONGS_TO_STYLE, {"match_score": 0.8}),
        ("岩板", "现代简约", RelationType.BELONGS_TO_STYLE, {"match_score": 0.9}),
        ("岩板", "轻奢", RelationType.BELONGS_TO_STYLE, {"match_score": 0.85}),
        ("瓷砖", "现代简约", RelationType.BELONGS_TO_STYLE, {"match_score": 0.8}),
        ("微水泥", "工业风", RelationType.BELONGS_TO_STYLE, {"match_score": 0.9}),
        ("微水泥", "现代简约", RelationType.BELONGS_TO_STYLE, {"match_score": 0.8}),
        ("木饰面护墙板", "新中式", RelationType.BELONGS_TO_STYLE, {"match_score": 0.85}),
        ("木饰面护墙板", "日式", RelationType.BELONGS_TO_STYLE, {"match_score": 0.8}),
        ("真皮沙发", "轻奢", RelationType.BELONGS_TO_STYLE, {"match_score": 0.85}),
        ("布艺沙发", "北欧", RelationType.BELONGS_TO_STYLE, {"match_score": 0.85}),
        ("实木床", "新中式", RelationType.BELONGS_TO_STYLE, {"match_score": 0.9}),
        ("实木床", "日式", RelationType.BELONGS_TO_STYLE, {"match_score": 0.85}),

        # ==================== 工序顺序 ====================
        ("拆改", "水电改造", RelationType.FOLLOWS, {}),
        ("水电改造", "防水", RelationType.FOLLOWS, {}),
        ("防水", "瓦工", RelationType.FOLLOWS, {}),
        ("瓦工", "木工", RelationType.FOLLOWS, {}),
        ("木工", "油漆", RelationType.FOLLOWS, {}),
        ("油漆", "安装", RelationType.FOLLOWS, {}),
        ("安装", "软装", RelationType.FOLLOWS, {}),

        # ==================== 材料可替代关系 ====================
        ("木地板", "瓷砖", RelationType.ALTERNATIVE_TO, {"场景": "地面"}),
        ("SPC地板", "木地板", RelationType.ALTERNATIVE_TO, {"场景": "地面", "优势": "防水"}),
        ("SPC地板", "瓷砖", RelationType.ALTERNATIVE_TO, {"场景": "地面", "优势": "脚感好"}),
        ("乳胶漆", "壁纸", RelationType.ALTERNATIVE_TO, {"场景": "墙面"}),
        ("乳胶漆", "硅藻泥", RelationType.ALTERNATIVE_TO, {"场景": "墙面"}),
        ("乳胶漆", "墙布", RelationType.ALTERNATIVE_TO, {"场景": "墙面"}),
        ("岩板台面", "石英石台面", RelationType.ALTERNATIVE_TO, {"场景": "厨房台面"}),
        ("实木地板", "三层实木复合地板", RelationType.ALTERNATIVE_TO, {"场景": "地面", "优势": "稳定性"}),
        ("三层实木复合地板", "多层实木复合地板", RelationType.ALTERNATIVE_TO, {"场景": "地面", "优势": "性价比"}),
        ("强化复合地板", "多层实木复合地板", RelationType.ALTERNATIVE_TO, {"场景": "地面", "优势": "耐磨"}),

        # ==================== 风格兼容 ====================
        ("现代简约", "北欧", RelationType.COMPATIBLE_WITH, {"compatibility": 0.8}),
        ("北欧", "日式", RelationType.COMPATIBLE_WITH, {"compatibility": 0.7}),
        ("轻奢", "现代简约", RelationType.COMPATIBLE_WITH, {"compatibility": 0.6}),
        ("新中式", "日式", RelationType.COMPATIBLE_WITH, {"compatibility": 0.5}),
        ("工业风", "现代简约", RelationType.COMPATIBLE_WITH, {"compatibility": 0.6}),

        # ==================== 材料搭配关系 ====================
        ("岩板餐桌", "真皮沙发", RelationType.PAIRS_WITH, {"style": "轻奢"}),
        ("实木餐桌", "布艺沙发", RelationType.PAIRS_WITH, {"style": "北欧"}),
        ("木地板", "木饰面护墙板", RelationType.PAIRS_WITH, {"style": "日式/新中式"}),
        ("大理石", "岩板", RelationType.PAIRS_WITH, {"style": "轻奢"}),
        ("乳胶漆", "石膏板吊顶", RelationType.PAIRS_WITH, {"场景": "客厅/卧室"}),

        # ==================== 产品推荐用于场景 ====================
        ("智能马桶", "卫生间", RelationType.RECOMMENDED_FOR, {"reason": "舒适便捷"}),
        ("恒温花洒", "卫生间", RelationType.RECOMMENDED_FOR, {"reason": "安全舒适"}),
        ("洗碗机", "厨房", RelationType.RECOMMENDED_FOR, {"reason": "解放双手"}),
        ("净水器", "厨房", RelationType.RECOMMENDED_FOR, {"reason": "饮水健康"}),
        ("新风系统", "客厅", RelationType.RECOMMENDED_FOR, {"reason": "空气质量"}),
        ("中央空调", "客厅", RelationType.RECOMMENDED_FOR, {"reason": "舒适美观"}),
        ("地暖", "卧室", RelationType.RECOMMENDED_FOR, {"reason": "舒适健康"}),
        ("扫地机器人", "客厅", RelationType.RECOMMENDED_FOR, {"reason": "解放双手"}),
        ("智能门锁", "玄关", RelationType.RECOMMENDED_FOR, {"reason": "安全便捷"}),
        ("燃气热水器", "卫生间", RelationType.RECOMMENDED_FOR, {"reason": "即热恒温"}),

        # ==================== 灯具适用空间 ====================
        ("吊灯", "客厅", RelationType.SUITABLE_FOR, {"recommendation": "高", "height": "距地2.2-2.5m"}),
        ("吊灯", "餐厅", RelationType.SUITABLE_FOR, {"recommendation": "高", "height": "距桌面0.7-0.9m"}),
        ("吸顶灯", "卧室", RelationType.SUITABLE_FOR, {"recommendation": "高"}),
        ("吸顶灯", "书房", RelationType.SUITABLE_FOR, {"recommendation": "高"}),
        ("吸顶灯", "走廊", RelationType.SUITABLE_FOR, {"recommendation": "高"}),
        ("筒灯", "客厅", RelationType.SUITABLE_FOR, {"recommendation": "高", "usage": "无主灯设计"}),
        ("筒灯", "走廊", RelationType.SUITABLE_FOR, {"recommendation": "高"}),
        ("射灯", "客厅", RelationType.SUITABLE_FOR, {"recommendation": "高", "usage": "重点照明"}),
        ("射灯", "玄关", RelationType.SUITABLE_FOR, {"recommendation": "高"}),
        ("磁吸轨道灯", "客厅", RelationType.SUITABLE_FOR, {"recommendation": "高", "usage": "无主灯设计"}),
        ("灯带", "客厅", RelationType.SUITABLE_FOR, {"recommendation": "高", "usage": "氛围照明"}),
        ("灯带", "卧室", RelationType.SUITABLE_FOR, {"recommendation": "中", "usage": "氛围照明"}),
        ("壁灯", "卧室", RelationType.SUITABLE_FOR, {"recommendation": "高", "usage": "床头照明"}),
        ("壁灯", "走廊", RelationType.SUITABLE_FOR, {"recommendation": "中"}),
        ("落地灯", "客厅", RelationType.SUITABLE_FOR, {"recommendation": "高", "usage": "阅读/氛围"}),
        ("台灯", "书房", RelationType.SUITABLE_FOR, {"recommendation": "高", "usage": "工作照明"}),
        ("台灯", "卧室", RelationType.SUITABLE_FOR, {"recommendation": "高", "usage": "床头阅读"}),
        ("橱柜灯", "厨房", RelationType.SUITABLE_FOR, {"recommendation": "高"}),

        # ==================== 灯具属于风格 ====================
        ("吊灯", "欧式", RelationType.BELONGS_TO_STYLE, {"match_score": 0.9, "type": "水晶吊灯"}),
        ("吊灯", "现代简约", RelationType.BELONGS_TO_STYLE, {"match_score": 0.8, "type": "艺术吊灯"}),
        ("磁吸轨道灯", "现代简约", RelationType.BELONGS_TO_STYLE, {"match_score": 0.9}),
        ("磁吸轨道灯", "工业风", RelationType.BELONGS_TO_STYLE, {"match_score": 0.85}),
        ("线性灯", "现代简约", RelationType.BELONGS_TO_STYLE, {"match_score": 0.9}),

        # ==================== 软装适用空间 ====================
        ("遮光窗帘", "卧室", RelationType.SUITABLE_FOR, {"recommendation": "高", "reason": "睡眠需要"}),
        ("纱帘", "客厅", RelationType.SUITABLE_FOR, {"recommendation": "高", "reason": "柔化光线"}),
        ("百叶帘", "书房", RelationType.SUITABLE_FOR, {"recommendation": "高", "reason": "调节光线"}),
        ("百叶帘", "卫生间", RelationType.SUITABLE_FOR, {"recommendation": "高", "reason": "防水"}),
        ("卷帘", "书房", RelationType.SUITABLE_FOR, {"recommendation": "中"}),
        ("客厅地毯", "客厅", RelationType.SUITABLE_FOR, {"recommendation": "高"}),
        ("羊毛地毯", "卧室", RelationType.SUITABLE_FOR, {"recommendation": "高", "reason": "保暖舒适"}),
        ("大型绿植", "客厅", RelationType.SUITABLE_FOR, {"recommendation": "高"}),
        ("中型绿植", "书房", RelationType.SUITABLE_FOR, {"recommendation": "高"}),
        ("小型绿植", "书房", RelationType.SUITABLE_FOR, {"recommendation": "高"}),
        ("装饰画", "客厅", RelationType.SUITABLE_FOR, {"recommendation": "高"}),
        ("装饰画", "卧室", RelationType.SUITABLE_FOR, {"recommendation": "中"}),
        ("香薰", "卧室", RelationType.SUITABLE_FOR, {"recommendation": "高", "reason": "助眠"}),

        # ==================== 软装属于风格 ====================
        ("棉麻窗帘", "北欧", RelationType.BELONGS_TO_STYLE, {"match_score": 0.9}),
        ("棉麻窗帘", "日式", RelationType.BELONGS_TO_STYLE, {"match_score": 0.85}),
        ("绒布窗帘", "轻奢", RelationType.BELONGS_TO_STYLE, {"match_score": 0.9}),
        ("绒布窗帘", "欧式", RelationType.BELONGS_TO_STYLE, {"match_score": 0.85}),
        ("羊毛地毯", "北欧", RelationType.BELONGS_TO_STYLE, {"match_score": 0.85}),
        ("手工地毯", "新中式", RelationType.BELONGS_TO_STYLE, {"match_score": 0.9}),
        ("纯棉四件套", "北欧", RelationType.BELONGS_TO_STYLE, {"match_score": 0.8}),
        ("真丝床品", "轻奢", RelationType.BELONGS_TO_STYLE, {"match_score": 0.9}),

        # ==================== 智能设备连接协议 ====================
        ("智能开关", "Zigbee", RelationType.CONNECT_WITH, {}),
        ("智能传感器", "Zigbee", RelationType.CONNECT_WITH, {}),
        ("智能音箱", "WiFi", RelationType.CONNECT_WITH, {}),
        ("智能摄像头", "WiFi", RelationType.CONNECT_WITH, {}),
        ("智能门锁", "蓝牙Mesh", RelationType.CONNECT_WITH, {}),

        # ==================== 窗帘可替代关系 ====================
        ("百叶帘", "布艺窗帘", RelationType.ALTERNATIVE_TO, {"场景": "窗户遮挡"}),
        ("卷帘", "布艺窗帘", RelationType.ALTERNATIVE_TO, {"场景": "窗户遮挡", "优势": "节省空间"}),
        ("电动窗帘", "手动窗帘", RelationType.ALTERNATIVE_TO, {"场景": "窗户遮挡", "优势": "智能便捷"}),

        # ==================== 热水器可替代关系 ====================
        ("燃气热水器", "电热水器", RelationType.ALTERNATIVE_TO, {"场景": "热水供应"}),
        ("空气能热水器", "电热水器", RelationType.ALTERNATIVE_TO, {"场景": "热水供应", "优势": "节能"}),

        # ==================== 地面材料关系 ====================
        # 瓷砖类型适用空间
        ("抛光砖", "客厅", RelationType.SUITABLE_FOR, {"recommendation": "高"}),
        ("抛光砖", "走廊", RelationType.SUITABLE_FOR, {"recommendation": "高"}),
        ("抛釉砖", "客厅", RelationType.SUITABLE_FOR, {"recommendation": "高"}),
        ("抛釉砖", "卧室", RelationType.SUITABLE_FOR, {"recommendation": "中"}),
        ("仿古砖", "阳台", RelationType.SUITABLE_FOR, {"recommendation": "高"}),
        ("仿古砖", "厨房", RelationType.SUITABLE_FOR, {"recommendation": "高"}),
        ("仿古砖", "卫生间", RelationType.SUITABLE_FOR, {"recommendation": "高"}),
        ("木纹砖", "卧室", RelationType.SUITABLE_FOR, {"recommendation": "高"}),
        ("木纹砖", "客厅", RelationType.SUITABLE_FOR, {"recommendation": "中"}),
        ("岩板", "客厅", RelationType.SUITABLE_FOR, {"recommendation": "高"}),
        ("岩板", "厨房", RelationType.SUITABLE_FOR, {"recommendation": "高", "用途": "台面"}),

        # 木地板类型适用空间
        ("实木地板", "卧室", RelationType.SUITABLE_FOR, {"recommendation": "高"}),
        ("实木地板", "客厅", RelationType.SUITABLE_FOR, {"recommendation": "高"}),
        ("三层实木复合地板", "卧室", RelationType.SUITABLE_FOR, {"recommendation": "高"}),
        ("三层实木复合地板", "客厅", RelationType.SUITABLE_FOR, {"recommendation": "高"}),
        ("多层实木复合地板", "卧室", RelationType.SUITABLE_FOR, {"recommendation": "高", "note": "适合地暖"}),
        ("强化复合地板", "客厅", RelationType.SUITABLE_FOR, {"recommendation": "中"}),
        ("强化复合地板", "卧室", RelationType.SUITABLE_FOR, {"recommendation": "中"}),

        # 弹性地板适用空间
        ("SPC地板", "卧室", RelationType.SUITABLE_FOR, {"recommendation": "中"}),
        ("SPC地板", "客厅", RelationType.SUITABLE_FOR, {"recommendation": "中"}),
        ("软木地板", "卧室", RelationType.SUITABLE_FOR, {"recommendation": "高"}),
        ("软木地板", "儿童房", RelationType.SUITABLE_FOR, {"recommendation": "高"}),

        # 地面材料可替代关系
        ("木纹砖", "木地板", RelationType.ALTERNATIVE_TO, {"场景": "地面", "优势": "防水易打理"}),
        ("SPC地板", "木地板", RelationType.ALTERNATIVE_TO, {"场景": "地面", "优势": "防水环保"}),
        ("实木地板", "强化复合地板", RelationType.ALTERNATIVE_TO, {"场景": "地面", "差异": "价格/脚感"}),
        ("三层实木复合地板", "多层实木复合地板", RelationType.ALTERNATIVE_TO, {"场景": "地面"}),
        ("抛光砖", "抛釉砖", RelationType.ALTERNATIVE_TO, {"场景": "地面", "差异": "耐磨性/花色"}),

        # 五金配件关系
        ("橱柜铰链", "实木多层板柜体", RelationType.PART_OF, {}),
        ("抽屉滑轨", "实木多层板柜体", RelationType.PART_OF, {}),
        ("拉篮", "实木多层板柜体", RelationType.PART_OF, {}),
        ("门窗执手", "断桥铝合金窗", RelationType.PART_OF, {}),
        ("门窗合页", "实木门", RelationType.PART_OF, {}),
        ("密封条", "断桥铝合金窗", RelationType.PART_OF, {}),

        # ==================== 装修工序流程 ====================
        ("收房验房", "设计阶段", RelationType.FOLLOWS, {}),
        ("设计阶段", "拆改", RelationType.FOLLOWS, {}),
        ("拆改", "水电改造", RelationType.FOLLOWS, {}),
        ("水电改造", "防水", RelationType.FOLLOWS, {}),
        ("防水", "瓦工", RelationType.FOLLOWS, {}),
        ("瓦工", "木工", RelationType.FOLLOWS, {}),
        ("木工", "油漆", RelationType.FOLLOWS, {}),
        ("油漆", "安装", RelationType.FOLLOWS, {}),
        ("安装", "软装", RelationType.FOLLOWS, {}),
        ("软装", "竣工验收", RelationType.FOLLOWS, {}),

        # ==================== 工序需要材料 ====================
        ("水电改造", "电线", RelationType.REQUIRES, {}),
        ("水电改造", "PPR管", RelationType.REQUIRES, {}),
        ("水电改造", "开关插座", RelationType.REQUIRES, {}),
        ("防水", "防水涂料", RelationType.REQUIRES, {}),
        ("瓦工", "瓷砖", RelationType.REQUIRES, {}),
        ("瓦工", "瓷砖胶", RelationType.REQUIRES, {}),
        ("木工", "石膏板吊顶", RelationType.REQUIRES, {}),
        ("油漆", "乳胶漆", RelationType.REQUIRES, {}),

        # ==================== 新增风格材料关系 ====================
        ("岩板", "极简主义", RelationType.BELONGS_TO_STYLE, {"match_score": 0.9}),
        ("微水泥", "侘寂风", RelationType.BELONGS_TO_STYLE, {"match_score": 0.9}),
        ("微水泥", "极简主义", RelationType.BELONGS_TO_STYLE, {"match_score": 0.85}),
        ("实木地板", "传统中式", RelationType.BELONGS_TO_STYLE, {"match_score": 0.9}),
        ("木饰面护墙板", "轻奢", RelationType.BELONGS_TO_STYLE, {"match_score": 0.8}),
        ("大理石", "法式", RelationType.BELONGS_TO_STYLE, {"match_score": 0.85}),
        ("仿古砖", "地中海", RelationType.BELONGS_TO_STYLE, {"match_score": 0.9}),
        ("仿古砖", "美式", RelationType.BELONGS_TO_STYLE, {"match_score": 0.85}),
        ("藤编床", "东南亚", RelationType.BELONGS_TO_STYLE, {"match_score": 0.9}),

        # ==================== 问题解决关系 ====================
        ("墙面开裂", "油漆", RelationType.CAUSES, {"stage": "施工"}),
        ("瓷砖空鼓", "瓦工", RelationType.CAUSES, {"stage": "施工"}),
        ("漏水", "防水", RelationType.CAUSES, {"stage": "施工"}),

        # ==================== 更多风格材料关系 ====================
        # 现代简约风格
        ("乳胶漆", "现代简约", RelationType.BELONGS_TO_STYLE, {"match_score": 0.9}),
        ("木饰面护墙板", "现代简约", RelationType.BELONGS_TO_STYLE, {"match_score": 0.85}),
        ("抛釉砖", "现代简约", RelationType.BELONGS_TO_STYLE, {"match_score": 0.8}),
        # 北欧风格
        ("实木地板", "北欧", RelationType.BELONGS_TO_STYLE, {"match_score": 0.9}),
        ("乳胶漆", "北欧", RelationType.BELONGS_TO_STYLE, {"match_score": 0.9}),
        # 日式风格
        ("木纹砖", "日式", RelationType.BELONGS_TO_STYLE, {"match_score": 0.85}),
        ("实木地板", "日式", RelationType.BELONGS_TO_STYLE, {"match_score": 0.9}),
        # 新中式风格
        ("实木地板", "新中式", RelationType.BELONGS_TO_STYLE, {"match_score": 0.9}),
        ("大理石", "新中式", RelationType.BELONGS_TO_STYLE, {"match_score": 0.8}),
        ("木饰面护墙板", "新中式", RelationType.BELONGS_TO_STYLE, {"match_score": 0.85}),
        # 欧式风格
        ("大理石", "欧式", RelationType.BELONGS_TO_STYLE, {"match_score": 0.9}),
        ("实木地板", "欧式", RelationType.BELONGS_TO_STYLE, {"match_score": 0.85}),
        # 轻奢风格
        ("岩板", "轻奢", RelationType.BELONGS_TO_STYLE, {"match_score": 0.9}),
        ("大理石", "轻奢", RelationType.BELONGS_TO_STYLE, {"match_score": 0.9}),
        # 工业风
        ("微水泥", "工业风", RelationType.BELONGS_TO_STYLE, {"match_score": 0.9}),
        ("金属床", "工业风", RelationType.BELONGS_TO_STYLE, {"match_score": 0.85}),
        # 美式风格
        ("实木地板", "美式", RelationType.BELONGS_TO_STYLE, {"match_score": 0.9}),
        # 奶油风
        ("乳胶漆", "奶油风", RelationType.BELONGS_TO_STYLE, {"match_score": 0.9}),
        ("木纹砖", "奶油风", RelationType.BELONGS_TO_STYLE, {"match_score": 0.8}),

        # ==================== 工具与工序关系 ====================
        ("收房验房", "空鼓锤", RelationType.REQUIRES, {}),
        ("收房验房", "水平尺", RelationType.REQUIRES, {}),
        ("收房验房", "卷尺", RelationType.REQUIRES, {}),
        ("水电改造", "开槽机", RelationType.REQUIRES, {}),
        ("水电改造", "热熔机", RelationType.REQUIRES, {}),
        ("水电改造", "打压泵", RelationType.REQUIRES, {}),
        ("瓦工", "瓷砖切割机", RelationType.REQUIRES, {}),
        ("瓦工", "抹子", RelationType.REQUIRES, {}),
        ("瓦工", "橡皮锤", RelationType.REQUIRES, {}),
        ("木工", "电钻", RelationType.REQUIRES, {}),
        ("木工", "气钉枪", RelationType.REQUIRES, {}),
        ("油漆", "批刀", RelationType.REQUIRES, {}),
        ("油漆", "砂纸", RelationType.REQUIRES, {}),
        ("油漆", "滚筒", RelationType.REQUIRES, {}),

        # ==================== 椅子适用空间 ====================
        ("餐椅", "餐厅", RelationType.SUITABLE_FOR, {"recommendation": "高"}),
        ("办公椅", "书房", RelationType.SUITABLE_FOR, {"recommendation": "高"}),
        ("休闲椅", "客厅", RelationType.SUITABLE_FOR, {"recommendation": "高"}),
        ("休闲椅", "阳台", RelationType.SUITABLE_FOR, {"recommendation": "中"}),
        ("吧椅", "厨房", RelationType.SUITABLE_FOR, {"recommendation": "中", "note": "岛台配套"}),
        ("儿童椅", "儿童房", RelationType.SUITABLE_FOR, {"recommendation": "高"}),
        ("梳妆椅", "卧室", RelationType.SUITABLE_FOR, {"recommendation": "高"}),

        # ==================== 品牌生产关系 ====================
        ("马可波罗", "瓷砖", RelationType.PRODUCED_BY, {}),
        ("东鹏", "瓷砖", RelationType.PRODUCED_BY, {}),
        ("圣象", "木地板", RelationType.PRODUCED_BY, {}),
        ("大自然", "木地板", RelationType.PRODUCED_BY, {}),
        ("欧派", "橱柜", RelationType.PRODUCED_BY, {}),
        ("索菲亚", "衣柜", RelationType.PRODUCED_BY, {}),
        ("立邦", "乳胶漆", RelationType.PRODUCED_BY, {}),
        ("多乐士", "乳胶漆", RelationType.PRODUCED_BY, {}),
        ("TOTO", "马桶", RelationType.PRODUCED_BY, {}),
        ("科勒", "马桶", RelationType.PRODUCED_BY, {}),

        # ==================== 儿童家具适用空间 ====================
        ("婴儿床", "儿童房", RelationType.SUITABLE_FOR, {"recommendation": "高", "age": "0-3岁"}),
        ("儿童单人床", "儿童房", RelationType.SUITABLE_FOR, {"recommendation": "高", "age": "3-12岁"}),
        ("高低床", "儿童房", RelationType.SUITABLE_FOR, {"recommendation": "高", "note": "二孩家庭"}),
        ("半高床", "儿童房", RelationType.SUITABLE_FOR, {"recommendation": "中", "note": "空间利用"}),
        ("子母床", "儿童房", RelationType.SUITABLE_FOR, {"recommendation": "中"}),
        ("成长床", "儿童房", RelationType.SUITABLE_FOR, {"recommendation": "高", "note": "长期使用"}),
        ("可升降书桌", "儿童房", RelationType.SUITABLE_FOR, {"recommendation": "高"}),
        ("可升降书桌", "书房", RelationType.SUITABLE_FOR, {"recommendation": "高"}),
        ("可升降座椅", "儿童房", RelationType.SUITABLE_FOR, {"recommendation": "高"}),
        ("儿童衣柜", "儿童房", RelationType.SUITABLE_FOR, {"recommendation": "高"}),
        ("玩具收纳柜", "儿童房", RelationType.SUITABLE_FOR, {"recommendation": "高"}),
        ("绘本架", "儿童房", RelationType.SUITABLE_FOR, {"recommendation": "高"}),
        ("儿童收纳箱", "儿童房", RelationType.SUITABLE_FOR, {"recommendation": "高"}),

        # ==================== 收纳家具适用空间 ====================
        ("鞋柜", "玄关", RelationType.SUITABLE_FOR, {"recommendation": "高"}),
        ("餐边柜", "餐厅", RelationType.SUITABLE_FOR, {"recommendation": "高"}),
        ("电视柜", "客厅", RelationType.SUITABLE_FOR, {"recommendation": "高"}),
        ("斗柜", "卧室", RelationType.SUITABLE_FOR, {"recommendation": "中"}),
        ("斗柜", "玄关", RelationType.SUITABLE_FOR, {"recommendation": "中"}),
        ("书柜", "书房", RelationType.SUITABLE_FOR, {"recommendation": "高"}),
        ("书柜", "客厅", RelationType.SUITABLE_FOR, {"recommendation": "中"}),
        ("展示柜", "客厅", RelationType.SUITABLE_FOR, {"recommendation": "中"}),

        # ==================== 新增沙发类型风格 ====================
        ("转角沙发", "现代简约", RelationType.BELONGS_TO_STYLE, {"match_score": 0.8}),
        ("U型沙发", "现代简约", RelationType.BELONGS_TO_STYLE, {"match_score": 0.75}),
        ("功能沙发", "现代简约", RelationType.BELONGS_TO_STYLE, {"match_score": 0.8}),
        ("懒人沙发", "北欧", RelationType.BELONGS_TO_STYLE, {"match_score": 0.7}),
        ("模块沙发", "现代简约", RelationType.BELONGS_TO_STYLE, {"match_score": 0.85}),
        ("沙发床", "现代简约", RelationType.BELONGS_TO_STYLE, {"match_score": 0.7}),

        # ==================== 新增餐桌类型适用空间 ====================
        ("大理石餐桌", "餐厅", RelationType.SUITABLE_FOR, {"recommendation": "高"}),
        ("伸缩餐桌", "餐厅", RelationType.SUITABLE_FOR, {"recommendation": "高", "note": "小户型推荐"}),
        ("玻璃餐桌", "餐厅", RelationType.SUITABLE_FOR, {"recommendation": "中"}),
        ("圆餐桌", "餐厅", RelationType.SUITABLE_FOR, {"recommendation": "高", "note": "中式家庭"}),
        ("边几", "客厅", RelationType.SUITABLE_FOR, {"recommendation": "高"}),
        ("边几", "卧室", RelationType.SUITABLE_FOR, {"recommendation": "中"}),
        ("玄关桌", "玄关", RelationType.SUITABLE_FOR, {"recommendation": "高"}),
        ("梳妆台", "卧室", RelationType.SUITABLE_FOR, {"recommendation": "高"}),
        ("书桌", "书房", RelationType.SUITABLE_FOR, {"recommendation": "高"}),
        ("书桌", "卧室", RelationType.SUITABLE_FOR, {"recommendation": "中"}),
        ("床头柜", "卧室", RelationType.SUITABLE_FOR, {"recommendation": "高"}),

        # ==================== 新增浴室设备适用空间 ====================
        ("增压花洒", "卫生间", RelationType.SUITABLE_FOR, {"recommendation": "高", "note": "低水压环境"}),
        ("智能花洒", "卫生间", RelationType.SUITABLE_FOR, {"recommendation": "中"}),
        ("手持花洒", "卫生间", RelationType.SUITABLE_FOR, {"recommendation": "高"}),
        ("按摩浴缸", "卫生间", RelationType.SUITABLE_FOR, {"recommendation": "中", "note": "大卫生间"}),
        ("智能浴缸", "卫生间", RelationType.SUITABLE_FOR, {"recommendation": "中"}),
        ("木桶浴缸", "卫生间", RelationType.SUITABLE_FOR, {"recommendation": "低", "note": "养生需求"}),
        ("嵌入式浴缸", "卫生间", RelationType.SUITABLE_FOR, {"recommendation": "高"}),
        ("独立式浴缸", "卫生间", RelationType.SUITABLE_FOR, {"recommendation": "中", "note": "大空间"}),

        # ==================== 新增餐桌风格关系 ====================
        ("大理石餐桌", "轻奢", RelationType.BELONGS_TO_STYLE, {"match_score": 0.9}),
        ("玻璃餐桌", "现代简约", RelationType.BELONGS_TO_STYLE, {"match_score": 0.8}),
        ("圆餐桌", "新中式", RelationType.BELONGS_TO_STYLE, {"match_score": 0.85}),
        ("伸缩餐桌", "现代简约", RelationType.BELONGS_TO_STYLE, {"match_score": 0.75}),

        # ==================== 装饰品适用空间 ====================
        ("木质摆件", "客厅", RelationType.SUITABLE_FOR, {"recommendation": "中"}),
        ("木质摆件", "书房", RelationType.SUITABLE_FOR, {"recommendation": "高"}),
        ("玻璃摆件", "客厅", RelationType.SUITABLE_FOR, {"recommendation": "中"}),
        ("相框", "客厅", RelationType.SUITABLE_FOR, {"recommendation": "高"}),
        ("相框", "卧室", RelationType.SUITABLE_FOR, {"recommendation": "高"}),
        ("托盘", "客厅", RelationType.SUITABLE_FOR, {"recommendation": "中"}),
        ("托盘", "卧室", RelationType.SUITABLE_FOR, {"recommendation": "中"}),
        ("收纳盒", "卧室", RelationType.SUITABLE_FOR, {"recommendation": "高"}),
        ("收纳盒", "书房", RelationType.SUITABLE_FOR, {"recommendation": "高"}),
        ("烛台", "餐厅", RelationType.SUITABLE_FOR, {"recommendation": "高"}),
        ("烛台", "卧室", RelationType.SUITABLE_FOR, {"recommendation": "中"}),
        ("书立", "书房", RelationType.SUITABLE_FOR, {"recommendation": "高"}),
        ("纸巾盒", "客厅", RelationType.SUITABLE_FOR, {"recommendation": "高"}),
        ("果盘", "客厅", RelationType.SUITABLE_FOR, {"recommendation": "高"}),
        ("果盘", "餐厅", RelationType.SUITABLE_FOR, {"recommendation": "高"}),
        ("花艺", "客厅", RelationType.SUITABLE_FOR, {"recommendation": "高"}),
        ("花艺", "餐厅", RelationType.SUITABLE_FOR, {"recommendation": "高"}),
        ("花艺", "玄关", RelationType.SUITABLE_FOR, {"recommendation": "高"}),

        # ==================== 问题-解决方案关系 ====================
        ("通风除醛", "甲醛超标", RelationType.SOLVES, {"effectiveness": "高", "cost": "低"}),
        ("活性炭吸附", "甲醛超标", RelationType.SOLVES, {"effectiveness": "中", "cost": "低"}),
        ("光触媒治理", "甲醛超标", RelationType.SOLVES, {"effectiveness": "高", "cost": "中高"}),
        ("新风净化", "甲醛超标", RelationType.SOLVES, {"effectiveness": "高", "cost": "高"}),
        ("灌浆修补", "瓷砖空鼓", RelationType.SOLVES, {"effectiveness": "中", "applicable": "小面积"}),
        ("铲除重贴", "瓷砖空鼓", RelationType.SOLVES, {"effectiveness": "高", "applicable": "大面积"}),
        ("贴网格布", "墙面开裂", RelationType.SOLVES, {"effectiveness": "高"}),
        ("贴网格布", "乳胶漆开裂", RelationType.SOLVES, {"effectiveness": "高"}),
        ("更换密封条", "门窗漏风", RelationType.SOLVES, {"effectiveness": "高", "cost": "低"}),
        ("调整五金", "门窗漏风", RelationType.SOLVES, {"effectiveness": "中", "cost": "低"}),
        ("防潮处理", "返潮", RelationType.SOLVES, {"effectiveness": "高"}),
        ("闭水试验", "漏水", RelationType.SOLVES, {"type": "检测方法"}),
        ("打压测试", "水管漏水", RelationType.SOLVES, {"type": "检测方法"}),

        # ==================== 吊顶造型适用空间和风格 ====================
        ("双眼皮吊顶", "客厅", RelationType.SUITABLE_FOR, {"recommendation": "高", "reason": "简洁大方"}),
        ("双眼皮吊顶", "卧室", RelationType.SUITABLE_FOR, {"recommendation": "高", "reason": "层高损失小"}),
        ("双眼皮吊顶", "现代简约", RelationType.BELONGS_TO_STYLE, {"match_score": 0.9}),
        ("双眼皮吊顶", "北欧", RelationType.BELONGS_TO_STYLE, {"match_score": 0.85}),
        ("双眼皮吊顶", "日式", RelationType.BELONGS_TO_STYLE, {"match_score": 0.8}),
        ("无主灯吊顶", "客厅", RelationType.SUITABLE_FOR, {"recommendation": "高", "reason": "灯光均匀"}),
        ("无主灯吊顶", "现代简约", RelationType.BELONGS_TO_STYLE, {"match_score": 0.9}),
        ("无主灯吊顶", "轻奢", RelationType.BELONGS_TO_STYLE, {"match_score": 0.85}),
        ("跌级吊顶", "客厅", RelationType.SUITABLE_FOR, {"recommendation": "高", "reason": "层次感强"}),
        ("跌级吊顶", "轻奢", RelationType.BELONGS_TO_STYLE, {"match_score": 0.85}),
        ("边吊", "客厅", RelationType.SUITABLE_FOR, {"recommendation": "高", "reason": "保留层高"}),
        ("边吊", "卧室", RelationType.SUITABLE_FOR, {"recommendation": "中"}),
        ("悬浮吊顶", "客厅", RelationType.SUITABLE_FOR, {"recommendation": "高", "reason": "现代感强"}),
        ("悬浮吊顶", "现代简约", RelationType.BELONGS_TO_STYLE, {"match_score": 0.9}),
        ("弧形吊顶", "欧式", RelationType.BELONGS_TO_STYLE, {"match_score": 0.85}),
        ("穹顶", "欧式", RelationType.BELONGS_TO_STYLE, {"match_score": 0.9}),
        ("穹顶", "美式", RelationType.BELONGS_TO_STYLE, {"match_score": 0.8}),

        # ==================== 吊顶造型可替代关系 ====================
        ("双眼皮吊顶", "跌级吊顶", RelationType.ALTERNATIVE_TO, {"场景": "客厅吊顶", "优势": "造价低/层高损失小"}),
        ("边吊", "跌级吊顶", RelationType.ALTERNATIVE_TO, {"场景": "客厅吊顶", "优势": "保留中间层高"}),
        ("无主灯吊顶", "平顶", RelationType.ALTERNATIVE_TO, {"场景": "客厅照明", "优势": "灯光均匀"}),
    ]

    def __init__(self):
        """初始化知识图谱"""
        self.entities: Dict[str, Entity] = {}
        self.relations: List[Relation] = []
        self._name_to_id: Dict[str, str] = {}  # 名称到ID的映射
        self._alias_to_id: Dict[str, str] = {}  # 别名到ID的映射
        self._lock = threading.RLock()

        # 加载预定义数据
        self._load_predefined_data()

        logger.info(f"知识图谱初始化完成: {len(self.entities)} 实体, {len(self.relations)} 关系")

    def _generate_id(self, entity_type: EntityType, name: str) -> str:
        """生成实体ID"""
        return hashlib.md5(f"{entity_type.value}:{name}".encode()).hexdigest()[:12]

    def _load_predefined_data(self):
        """加载预定义数据"""
        # 加载实体
        for entity_type, entities in self.PREDEFINED_ENTITIES.items():
            for entity_data in entities:
                self.add_entity(
                    name=entity_data["name"],
                    entity_type=entity_type,
                    properties=entity_data.get("properties", {}),
                    aliases=entity_data.get("aliases", [])
                )

        # 加载关系
        for source_name, target_name, relation_type, properties in self.PREDEFINED_RELATIONS:
            self.add_relation(source_name, target_name, relation_type, properties=properties)

    def add_entity(self, name: str, entity_type: EntityType,
                   properties: Dict = None, aliases: List[str] = None) -> str:
        """
        添加实体

        Args:
            name: 实体名称
            entity_type: 实体类型
            properties: 属性字典
            aliases: 别名列表

        Returns:
            实体ID
        """
        with self._lock:
            entity_id = self._generate_id(entity_type, name)

            if entity_id in self.entities:
                # 更新已有实体
                entity = self.entities[entity_id]
                if properties:
                    entity.properties.update(properties)
                if aliases:
                    entity.aliases.extend([a for a in aliases if a not in entity.aliases])
            else:
                # 创建新实体
                entity = Entity(
                    id=entity_id,
                    name=name,
                    entity_type=entity_type,
                    properties=properties or {},
                    aliases=aliases or []
                )
                self.entities[entity_id] = entity

            # 更新名称映射
            self._name_to_id[name.lower()] = entity_id
            for alias in (aliases or []):
                self._alias_to_id[alias.lower()] = entity_id

            return entity_id

    def add_relation(self, source_name: str, target_name: str,
                     relation_type: RelationType, weight: float = 1.0,
                     properties: Dict = None) -> bool:
        """
        添加关系

        Args:
            source_name: 源实体名称
            target_name: 目标实体名称
            relation_type: 关系类型
            weight: 关系权重
            properties: 关系属性

        Returns:
            是否添加成功
        """
        with self._lock:
            source_id = self._resolve_entity_id(source_name)
            target_id = self._resolve_entity_id(target_name)

            if not source_id or not target_id:
                logger.warning(f"无法添加关系: {source_name} -> {target_name}, 实体不存在")
                return False

            relation = Relation(
                source_id=source_id,
                target_id=target_id,
                relation_type=relation_type,
                weight=weight,
                properties=properties or {}
            )
            self.relations.append(relation)
            return True

    def _resolve_entity_id(self, name: str) -> Optional[str]:
        """解析实体名称为ID"""
        name_lower = name.lower()

        # 先查找精确匹配
        if name_lower in self._name_to_id:
            return self._name_to_id[name_lower]

        # 再查找别名
        if name_lower in self._alias_to_id:
            return self._alias_to_id[name_lower]

        return None

    def get_entity(self, name: str) -> Optional[Entity]:
        """
        获取实体

        Args:
            name: 实体名称或别名

        Returns:
            实体对象
        """
        entity_id = self._resolve_entity_id(name)
        if entity_id:
            return self.entities.get(entity_id)
        return None

    def get_entity_by_id(self, entity_id: str) -> Optional[Entity]:
        """通过ID获取实体"""
        return self.entities.get(entity_id)

    def query_relations(self, entity_name: str,
                        relation_type: RelationType = None,
                        direction: str = "both") -> List[Tuple[Entity, Relation]]:
        """
        查询实体的关系

        Args:
            entity_name: 实体名称
            relation_type: 关系类型（可选）
            direction: 查询方向 ("outgoing", "incoming", "both")

        Returns:
            (相关实体, 关系) 列表
        """
        entity_id = self._resolve_entity_id(entity_name)
        if not entity_id:
            return []

        results = []
        for relation in self.relations:
            # 检查关系类型
            if relation_type and relation.relation_type != relation_type:
                continue

            # 检查方向
            if direction in ("outgoing", "both") and relation.source_id == entity_id:
                target = self.entities.get(relation.target_id)
                if target:
                    results.append((target, relation))

            if direction in ("incoming", "both") and relation.target_id == entity_id:
                source = self.entities.get(relation.source_id)
                if source:
                    results.append((source, relation))

        return results

    def find_suitable_materials(self, space: str, style: str = None) -> List[Dict]:
        """
        查找适合特定空间和风格的材料

        Args:
            space: 空间名称
            style: 风格名称（可选）

        Returns:
            推荐材料列表
        """
        results = []

        # 查找适用于该空间的材料
        space_relations = self.query_relations(
            space, RelationType.SUITABLE_FOR, direction="incoming"
        )

        for entity, relation in space_relations:
            if entity.entity_type != EntityType.MATERIAL:
                continue

            material_info = {
                "name": entity.name,
                "properties": entity.properties,
                "space_recommendation": relation.properties.get("recommendation", "中"),
                "style_match": None
            }

            # 如果指定了风格，检查材料是否匹配
            if style:
                style_relations = self.query_relations(
                    entity.name, RelationType.BELONGS_TO_STYLE, direction="outgoing"
                )
                for style_entity, style_rel in style_relations:
                    if style_entity.name == style:
                        material_info["style_match"] = style_rel.properties.get("match_score", 0.5)
                        break

            results.append(material_info)

        # 按推荐度排序
        results.sort(key=lambda x: (
            x.get("style_match") or 0,
            {"高": 3, "中": 2, "低": 1}.get(x["space_recommendation"], 0)
        ), reverse=True)

        return results

    def find_style_materials(self, style: str) -> List[Dict]:
        """
        查找特定风格的推荐材料

        Args:
            style: 风格名称

        Returns:
            推荐材料列表
        """
        results = []

        style_relations = self.query_relations(
            style, RelationType.BELONGS_TO_STYLE, direction="incoming"
        )

        for entity, relation in style_relations:
            if entity.entity_type == EntityType.MATERIAL:
                results.append({
                    "name": entity.name,
                    "properties": entity.properties,
                    "match_score": relation.properties.get("match_score", 0.5)
                })

        results.sort(key=lambda x: x["match_score"], reverse=True)
        return results

    def get_process_sequence(self) -> List[Dict]:
        """
        获取装修工序顺序

        Returns:
            工序列表（按顺序）
        """
        # 获取所有工序实体
        processes = [
            e for e in self.entities.values()
            if e.entity_type == EntityType.PROCESS
        ]

        # 按order属性排序
        processes.sort(key=lambda x: x.properties.get("order", 99))

        return [
            {
                "name": p.name,
                "order": p.properties.get("order"),
                "duration": p.properties.get("duration"),
                "aliases": p.aliases
            }
            for p in processes
        ]

    def find_alternatives(self, material: str) -> List[Dict]:
        """
        查找材料的替代品

        Args:
            material: 材料名称

        Returns:
            替代材料列表
        """
        results = []

        relations = self.query_relations(
            material, RelationType.ALTERNATIVE_TO, direction="both"
        )

        for entity, relation in relations:
            if entity.entity_type == EntityType.MATERIAL:
                results.append({
                    "name": entity.name,
                    "properties": entity.properties,
                    "scenario": relation.properties.get("场景", "通用")
                })

        return results

    def find_compatible_styles(self, style: str) -> List[Dict]:
        """
        查找兼容的风格

        Args:
            style: 风格名称

        Returns:
            兼容风格列表
        """
        results = []

        relations = self.query_relations(
            style, RelationType.COMPATIBLE_WITH, direction="both"
        )

        for entity, relation in relations:
            if entity.entity_type == EntityType.STYLE:
                results.append({
                    "name": entity.name,
                    "properties": entity.properties,
                    "compatibility": relation.properties.get("compatibility", 0.5)
                })

        results.sort(key=lambda x: x["compatibility"], reverse=True)
        return results

    def search_entities(self, query: str, entity_type: EntityType = None,
                        limit: int = 10) -> List[Entity]:
        """
        搜索实体

        Args:
            query: 搜索关键词
            entity_type: 实体类型（可选）
            limit: 返回数量限制

        Returns:
            匹配的实体列表
        """
        query_lower = query.lower()
        results = []

        for entity in self.entities.values():
            # 类型过滤
            if entity_type and entity.entity_type != entity_type:
                continue

            # 名称匹配
            if query_lower in entity.name.lower():
                results.append(entity)
                continue

            # 别名匹配
            for alias in entity.aliases:
                if query_lower in alias.lower():
                    results.append(entity)
                    break

        return results[:limit]

    def get_stats(self) -> Dict:
        """获取知识图谱统计信息"""
        type_counts = {}
        for entity in self.entities.values():
            type_name = entity.entity_type.value
            type_counts[type_name] = type_counts.get(type_name, 0) + 1

        relation_counts = {}
        for relation in self.relations:
            rel_name = relation.relation_type.value
            relation_counts[rel_name] = relation_counts.get(rel_name, 0) + 1

        return {
            "total_entities": len(self.entities),
            "total_relations": len(self.relations),
            "entity_types": type_counts,
            "relation_types": relation_counts
        }

    def get_space_solution(self, space: str, style: str = None, budget: str = None) -> Dict:
        """
        获取空间完整解决方案

        Args:
            space: 空间名称（如"客厅"、"卧室"）
            style: 风格名称（可选）
            budget: 预算等级（"经济"、"中等"、"高端"）（可选）

        Returns:
            包含地面、墙面、吊顶、家具、灯具等完整方案
        """
        solution = {
            "space": space,
            "style": style,
            "budget": budget,
            "floor": [],      # 地面材料
            "wall": [],       # 墙面材料
            "ceiling": [],    # 吊顶材料
            "furniture": [],  # 家具
            "lighting": [],   # 灯具
            "soft_decoration": [],  # 软装
            "smart_home": []  # 智能家居推荐
        }

        # 查找适用于该空间的所有产品
        space_relations = self.query_relations(
            space, RelationType.SUITABLE_FOR, direction="incoming"
        )

        for entity, relation in space_relations:
            item = {
                "name": entity.name,
                "type": entity.entity_type.value,
                "properties": entity.properties,
                "recommendation": relation.properties.get("recommendation", "中"),
                "usage": relation.properties.get("usage", ""),
                "reason": relation.properties.get("reason", "")
            }

            # 如果指定了风格，检查匹配度
            if style:
                style_relations = self.query_relations(
                    entity.name, RelationType.BELONGS_TO_STYLE, direction="outgoing"
                )
                for style_entity, style_rel in style_relations:
                    if style_entity.name == style:
                        item["style_match"] = style_rel.properties.get("match_score", 0.5)
                        break

            # 按类型分类
            entity_type = entity.entity_type
            if entity_type in [EntityType.FLOOR_TILE, EntityType.WOOD_FLOOR, EntityType.STONE]:
                solution["floor"].append(item)
            elif entity_type in [EntityType.PAINT, EntityType.WALLPAPER, EntityType.WALL_PANEL]:
                solution["wall"].append(item)
            elif entity_type == EntityType.CEILING:
                solution["ceiling"].append(item)
            elif entity_type in [EntityType.SOFA, EntityType.BED, EntityType.TABLE, EntityType.WARDROBE,
                                 EntityType.CHAIR, EntityType.CHILDREN_FURNITURE, EntityType.STORAGE]:
                solution["furniture"].append(item)
            elif entity_type == EntityType.LIGHTING:
                solution["lighting"].append(item)
            elif entity_type in [EntityType.CURTAIN, EntityType.CARPET, EntityType.PLANT, EntityType.DECORATION]:
                solution["soft_decoration"].append(item)

        # 查找推荐的智能家居
        smart_relations = self.query_relations(
            space, RelationType.RECOMMENDED_FOR, direction="incoming"
        )
        for entity, relation in smart_relations:
            solution["smart_home"].append({
                "name": entity.name,
                "reason": relation.properties.get("reason", "")
            })

        return solution

    def get_style_solution(self, style: str) -> Dict:
        """
        获取风格完整解决方案

        Args:
            style: 风格名称

        Returns:
            该风格推荐的所有材料和产品
        """
        solution = {
            "style": style,
            "keywords": [],
            "materials": [],
            "furniture": [],
            "lighting": [],
            "soft_decoration": [],
            "colors": []
        }

        # 获取风格实体信息
        style_entity = self.get_entity(style)
        if style_entity:
            solution["keywords"] = style_entity.properties.get("keywords", [])

        # 查找属于该风格的所有产品
        style_relations = self.query_relations(
            style, RelationType.BELONGS_TO_STYLE, direction="incoming"
        )

        for entity, relation in style_relations:
            item = {
                "name": entity.name,
                "type": entity.entity_type.value,
                "match_score": relation.properties.get("match_score", 0.5),
                "properties": entity.properties
            }

            entity_type = entity.entity_type
            if entity_type in [EntityType.MATERIAL, EntityType.FLOOR_TILE, EntityType.WOOD_FLOOR,
                               EntityType.STONE, EntityType.PAINT, EntityType.WALLPAPER]:
                solution["materials"].append(item)
            elif entity_type in [EntityType.SOFA, EntityType.BED, EntityType.TABLE, EntityType.CHAIR,
                                 EntityType.CHILDREN_FURNITURE, EntityType.STORAGE]:
                solution["furniture"].append(item)
            elif entity_type == EntityType.LIGHTING:
                solution["lighting"].append(item)
            elif entity_type in [EntityType.CURTAIN, EntityType.CARPET, EntityType.BEDDING]:
                solution["soft_decoration"].append(item)

        # 按匹配度排序
        for key in ["materials", "furniture", "lighting", "soft_decoration"]:
            solution[key].sort(key=lambda x: x.get("match_score", 0), reverse=True)

        return solution

    def get_product_comparison(self, product1: str, product2: str) -> Dict:
        """
        产品对比

        Args:
            product1: 第一个产品名称
            product2: 第二个产品名称

        Returns:
            两个产品的对比信息
        """
        entity1 = self.get_entity(product1)
        entity2 = self.get_entity(product2)

        if not entity1 or not entity2:
            return {"error": "产品不存在"}

        comparison = {
            "product1": {
                "name": entity1.name,
                "type": entity1.entity_type.value,
                "properties": entity1.properties,
                "suitable_spaces": [],
                "suitable_styles": []
            },
            "product2": {
                "name": entity2.name,
                "type": entity2.entity_type.value,
                "properties": entity2.properties,
                "suitable_spaces": [],
                "suitable_styles": []
            },
            "is_alternative": False,
            "common_spaces": [],
            "common_styles": []
        }

        # 获取适用空间
        for entity, key in [(entity1, "product1"), (entity2, "product2")]:
            space_relations = self.query_relations(
                entity.name, RelationType.SUITABLE_FOR, direction="outgoing"
            )
            for space_entity, rel in space_relations:
                comparison[key]["suitable_spaces"].append(space_entity.name)

            style_relations = self.query_relations(
                entity.name, RelationType.BELONGS_TO_STYLE, direction="outgoing"
            )
            for style_entity, rel in style_relations:
                comparison[key]["suitable_styles"].append({
                    "name": style_entity.name,
                    "match_score": rel.properties.get("match_score", 0.5)
                })

        # 检查是否可替代
        alt_relations = self.query_relations(
            product1, RelationType.ALTERNATIVE_TO, direction="both"
        )
        for entity, rel in alt_relations:
            if entity.name == product2:
                comparison["is_alternative"] = True
                comparison["alternative_scenario"] = rel.properties.get("场景", "")
                break

        # 找出共同适用的空间和风格
        spaces1 = set(comparison["product1"]["suitable_spaces"])
        spaces2 = set(comparison["product2"]["suitable_spaces"])
        comparison["common_spaces"] = list(spaces1 & spaces2)

        styles1 = set(s["name"] for s in comparison["product1"]["suitable_styles"])
        styles2 = set(s["name"] for s in comparison["product2"]["suitable_styles"])
        comparison["common_styles"] = list(styles1 & styles2)

        return comparison

    def get_brands_by_category(self, category: str, level: str = None) -> List[Dict]:
        """
        按品类获取品牌

        Args:
            category: 品类名称（如"瓷砖"、"卫浴"、"厨电"）
            level: 品牌等级（"高端"、"中高端"、"中端"）（可选）

        Returns:
            品牌列表
        """
        results = []

        for entity in self.entities.values():
            if entity.entity_type != EntityType.BRAND:
                continue

            props = entity.properties
            if category.lower() in props.get("category", "").lower():
                if level and props.get("level") != level:
                    continue
                results.append({
                    "name": entity.name,
                    "level": props.get("level", ""),
                    "origin": props.get("origin", ""),
                    "aliases": entity.aliases
                })

        # 按等级排序
        level_order = {"高端": 0, "中高端": 1, "中端": 2, "性价比": 3}
        results.sort(key=lambda x: level_order.get(x["level"], 99))

        return results

    def get_lighting_recommendation(self, space: str) -> Dict:
        """
        获取空间照明推荐方案

        Args:
            space: 空间名称

        Returns:
            照明方案，包括照度标准、推荐灯具、色温建议
        """
        recommendation = {
            "space": space,
            "illuminance": "",
            "color_temp": "",
            "recommended_lights": [],
            "design_tips": []
        }

        # 获取照度标准
        illuminance_entity = self.get_entity("照度标准")
        if illuminance_entity:
            recommendation["illuminance"] = illuminance_entity.properties.get(space, "100-300lx")

        # 获取色温推荐
        color_temp_entity = self.get_entity("色温推荐")
        if color_temp_entity:
            if space in ["卧室", "餐厅"]:
                recommendation["color_temp"] = color_temp_entity.properties.get("暖色调空间", "2700-3000K")
            elif space in ["书房", "厨房"]:
                recommendation["color_temp"] = color_temp_entity.properties.get("工作空间", "4000-5000K")
            else:
                recommendation["color_temp"] = color_temp_entity.properties.get("中性空间", "3500-4000K")

        # 获取推荐灯具
        light_relations = self.query_relations(
            space, RelationType.SUITABLE_FOR, direction="incoming"
        )
        for entity, relation in light_relations:
            if entity.entity_type == EntityType.LIGHTING:
                recommendation["recommended_lights"].append({
                    "name": entity.name,
                    "usage": relation.properties.get("usage", ""),
                    "recommendation": relation.properties.get("recommendation", "中")
                })

        # 无主灯设计建议
        no_main_light = self.get_entity("无主灯设计")
        if no_main_light:
            recommendation["design_tips"] = [
                f"灯具间距: {no_main_light.properties.get('灯具间距', '0.8-1.2m')}",
                f"离墙距离: {no_main_light.properties.get('离墙距离', '0.3-0.5m')}",
            ] + no_main_light.properties.get("要点", [])

        return recommendation

    def get_smart_home_solution(self, spaces: List[str] = None) -> Dict:
        """
        获取智能家居解决方案

        Args:
            spaces: 空间列表（可选，默认全屋）

        Returns:
            智能家居方案
        """
        solution = {
            "protocols": [],
            "gateway": [],
            "devices": {
                "lighting": [],
                "security": [],
                "comfort": [],
                "convenience": []
            },
            "brands": []
        }

        # 获取协议信息
        for entity in self.entities.values():
            if entity.entity_type == EntityType.SMART_PROTOCOL:
                solution["protocols"].append({
                    "name": entity.name,
                    "features": entity.properties.get("features", []),
                    "applications": entity.properties.get("applications", [])
                })

        # 获取智能设备
        for entity in self.entities.values():
            if entity.entity_type == EntityType.SMART_HOME:
                device = {
                    "name": entity.name,
                    "functions": entity.properties.get("functions", []),
                    "brands": entity.properties.get("brands", {})
                }

                # 分类
                name = entity.name
                if "灯" in name or "开关" in name:
                    solution["devices"]["lighting"].append(device)
                elif "门锁" in name or "摄像头" in name or "传感器" in name:
                    solution["devices"]["security"].append(device)
                elif "空调" in name or "窗帘" in name:
                    solution["devices"]["comfort"].append(device)
                elif "扫地" in name or "音箱" in name:
                    solution["devices"]["convenience"].append(device)
                elif "网关" in name:
                    solution["gateway"].append(device)

        # 获取智能家居品牌
        solution["brands"] = self.get_brands_by_category("智能家居")

        return solution

    def get_decoration_process(self) -> List[Dict]:
        """
        获取装修工序流程

        Returns:
            装修工序列表（按顺序）
        """
        processes = self.get_process_sequence()

        # 为每个工序添加所需材料和注意事项
        for process in processes:
            name = process["name"]

            # 查找该工序需要的材料
            requires_relations = self.query_relations(
                name, RelationType.REQUIRES, direction="outgoing"
            )
            process["required_materials"] = [
                entity.name for entity, rel in requires_relations
            ]

            # 查找相关问题
            process["common_problems"] = []
            for entity in self.entities.values():
                if entity.entity_type == EntityType.PROBLEM:
                    if entity.properties.get("stage") == name:
                        process["common_problems"].append({
                            "name": entity.name,
                            "severity": entity.properties.get("severity", "中")
                        })

        return processes

    def get_env_standard_info(self, standard: str = None) -> List[Dict]:
        """
        获取环保标准信息

        Args:
            standard: 标准名称（可选，不指定则返回所有）

        Returns:
            环保标准列表
        """
        results = []

        for entity in self.entities.values():
            if entity.entity_type != EntityType.STANDARD:
                continue

            if standard and standard not in entity.name:
                continue

            results.append({
                "name": entity.name,
                "formaldehyde": entity.properties.get("formaldehyde", ""),
                "standard": entity.properties.get("standard", ""),
                "level": entity.properties.get("level", "")
            })

        # 按等级排序
        level_order = {"最高": 0, "高": 1, "合格": 2}
        results.sort(key=lambda x: level_order.get(x["level"], 99))

        return results


# 全局知识图谱实例
_knowledge_graph: Optional[DecorationKnowledgeGraph] = None
_kg_lock = threading.Lock()


def get_knowledge_graph() -> DecorationKnowledgeGraph:
    """获取全局知识图谱实例"""
    global _knowledge_graph
    if _knowledge_graph is None:
        with _kg_lock:
            if _knowledge_graph is None:
                _knowledge_graph = DecorationKnowledgeGraph()
    return _knowledge_graph
