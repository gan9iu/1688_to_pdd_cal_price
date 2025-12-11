"""
数据模型定义模块。
定义了项目中使用的核心数据结构：Product 和 SKU。
"""
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any


@dataclass
class SKU:
    """
    代表商品下的一个 SKU (库存量单位)。
    包含抓取的原始数据（价格、库存）和计算后的定价数据。
    """
    name: str
    price: Optional[float] = None  # 抓取到的原始价格
    stock: int = 0                 # 抓取到的库存数量
    price_text: str = ""           # 原始价格文本
    stock_text: str = ""           # 原始库存文本
    
    # 计算后的字段
    cost: float = 0.0              # 计算用的基础成本
    selling_price: float = 0.0     # 实际售价 (预留)
    suggested_price: float = 0.0   # 建议售价 (计算结果)
    
    # 额外信息
    extra_data: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Product:
    """
    代表一个抓取的商品。
    包含商品的基本信息（标题、运费）和其下的 SKU 列表。
    """
    url: str
    title: str = ""
    shipping_text: str = ""
    shipping_cost: float = 0.0
    category: str = "未知"          # 新增：类目
    specs: str = ""                # 新增：1688规格 (含包装信息)
    packaging: str = ""            # (临时)包装信息片段，用于 api_server 拼接
    skus: List[SKU] = field(default_factory=list)
    
    # 备用字段，用于存储未解析到 SKU 时的通用信息
    fallback_data: Dict[str, Any] = field(default_factory=dict)
