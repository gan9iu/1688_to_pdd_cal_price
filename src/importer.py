"""
数据导入模块。
负责解析上传的 Excel 文件，将其转换为内部的 Product 和 SKU 模型。
支持智能列名识别和数据分组。
"""
import pandas as pd
from typing import List, Dict, Any, Optional
from io import BytesIO
from src.models import Product, SKU

# 列名映射字典 (目标字段 -> 可能的 Excel 列名列表)
COLUMN_MAPPING = {
    "name": ["SKU名称", "SKU名", "规格", "name", "sku", "sku_name"],
    "price": ["价格", "价格(元)", "成本", "原价", "price", "cost", "base_cost"],
    "selling_price": ["实际成交价", "成交价", "卖价", "售价", "建议售价", "selling_price", "suggested_price"],
    "stock": ["库存", "库存(件数)", "stock", "quantity", "count"],
    "shipping": ["运费", "运费(元)", "快递运费", "shipping", "freight", "shipping_cost"],
    "title": ["商品标题", "标题", "商品名", "title", "product_name", "product_title_main"],
    "url": ["链接", "商品链接", "url", "link", "product_url"]
}

def parse_excel_to_products(file_content: bytes) -> List[Product]:
    """
    解析 Excel 文件内容为 Product 对象列表。
    支持自动探测表头行（不一定在第一行）。
    """
    try:
        # 先读取为非 header 模式，以便探测
        df_raw = pd.read_excel(BytesIO(file_content), header=None)
    except Exception:
        return []

    if df_raw.empty:
        return []

    # 1. 探测表头行
    header_row_index = _detect_header_row(df_raw)
    
    if header_row_index is None:
        # 没找到明显表头，尝试默认第一行
        # 重新读取，使用默认 header=0
        try:
            df = pd.read_excel(BytesIO(file_content))
        except Exception:
            return []
    else:
        # 使用探测到的行作为表头
        # 将该行设为列名
        df = df_raw.iloc[header_row_index + 1:].copy()
        df.columns = df_raw.iloc[header_row_index].astype(str).tolist()
        # 重置索引
        df.reset_index(drop=True, inplace=True)

    # 2. 建立列名映射
    col_map = _build_column_map(df.columns)
    
    # 必须包含至少一个关键字段 (name 或 price) 才认为是商品数据表
    if "name" not in col_map and "price" not in col_map:
        return []

    products_map: Dict[str, Product] = {}
    products_list: List[Product] = []

    # 3. 遍历行数据
    for _, row in df.iterrows():
        # 提取基础数据
        url = str(row.get(col_map.get("url"), "")).strip()
        title = str(row.get(col_map.get("title"), "")).strip()
        
        # 如果没有 URL，尝试用标题作为唯一标识，否则生成一个临时 ID
        product_key = url if url else (title if title else f"TEMP_PROD_{len(products_list)}")
        
        # 获取或创建 Product 对象
        if product_key not in products_map:
            # 尝试获取运费 (优先从当前行获取)
            shipping_val = _parse_float(row.get(col_map.get("shipping")))
            
            product = Product(
                url=url,
                title=title,
                shipping_cost=shipping_val if shipping_val is not None else 0.0,
                shipping_text=str(shipping_val) if shipping_val is not None else ""
            )
            products_map[product_key] = product
            products_list.append(product)
        else:
            product = products_map[product_key]

        # 创建 SKU 对象
        sku_name = str(row.get(col_map.get("name"), "默认规格")).strip()
        price_val = _parse_float(row.get(col_map.get("price")))
        selling_price_val = _parse_float(row.get(col_map.get("selling_price")))
        stock_val = _parse_int(row.get(col_map.get("stock")))
        
        sku = SKU(
            name=sku_name,
            price=price_val,
            selling_price=selling_price_val if selling_price_val is not None else 0.0,
            stock=stock_val if stock_val is not None else 0,
            price_text=str(price_val) if price_val is not None else "",
            stock_text=str(stock_val) if stock_val is not None else ""
        )
        
        product.skus.append(sku)

    return products_list


def _detect_header_row(df: pd.DataFrame, max_scan_rows: int = 20) -> Optional[int]:
    """
    探测哪一行是表头。
    返回行索引，如果没找到返回 None。
    """
    # 扁平化关键词列表用于匹配
    keywords = set()
    for keys in COLUMN_MAPPING.values():
        for k in keys:
            keywords.add(k.lower())

    best_row_idx = None
    max_matches = 0

    # 扫描前 N 行
    scan_limit = min(len(df), max_scan_rows)
    for i in range(scan_limit):
        row_values = [str(v).lower().strip() for v in df.iloc[i] if pd.notna(v)]
        matches = sum(1 for v in row_values if v in keywords)
        
        # 如果这一行包含 "sku" 或 "价格" 这种强特征词，权重增加
        for v in row_values:
            if "sku" in v or "价格" in v or "price" in v:
                matches += 1

        if matches > max_matches:
            max_matches = matches
            best_row_idx = i
    
    # 至少要匹配到 2 个特征才算找到 (例如 "SKU" 和 "价格")
    # 或者如果只有 1 个特征但非常明确 (比如就是 "价格" 和 "库存")
    if max_matches >= 2:
        return best_row_idx
        
    return None


def _build_column_map(columns: List[str]) -> Dict[str, str]:
    """
    根据预定义的映射表，找到 DataFrame 中对应的实际列名。
    返回: { "internal_key": "Actual Column Name" }
    """
    result = {}
    # 将所有列名转为小写以便匹配
    cols_lower = {str(c).lower().strip(): c for c in columns}
    
    for key, candidates in COLUMN_MAPPING.items():
        for cand in candidates:
            cand_lower = cand.lower()
            if cand_lower in cols_lower:
                result[key] = cols_lower[cand_lower]
                break
    return result


def _parse_float(val: Any) -> Optional[float]:
    """安全解析浮点数"""
    if pd.isna(val) or val == "":
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


def _parse_int(val: Any) -> Optional[int]:
    """安全解析整数"""
    if pd.isna(val) or val == "":
        return None
    try:
        return int(float(val))
    except (ValueError, TypeError):
        return None
