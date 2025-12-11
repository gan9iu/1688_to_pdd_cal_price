"""
业务服务层，遵循单一职责原则拆分为独立服务。
"""
import os
from typing import List, Dict, Callable, Optional, Tuple, Any
from io import BytesIO

from src.models import Product, SKU
from src.crawler import fetch_item, create_driver
from src.pricing.engine import batch_calculate
from src.exporter import export_to_excel, quick_check, generate_excel_bytes


class CrawlerService:
    """
    爬虫服务：专门负责管理浏览器生命周期和执行抓取任务。
    """
    def __init__(self, headless: bool = True, driver_path: Optional[str] = None, use_firefox_profile: bool = False):
        self.headless = headless
        self.driver_path = driver_path
        self.use_profile = use_firefox_profile
        self._driver = None

    def __enter__(self):
        self._driver = create_driver(
            headless=self.headless, 
            driver_path=self.driver_path, 
            use_firefox_profile=self.use_profile
        )
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._driver:
            self._driver.quit()
            self._driver = None

    def fetch_products(
        self, 
        urls: List[str], 
        progress_callback: Optional[Callable[[int, int, str], None]] = None
    ) -> List[Product]:
        """
        批量抓取商品信息。
        """
        if not self._driver:
            raise RuntimeError("Driver not initialized. Use 'with CrawlerService(...) as service:'")

        products = []
        total = len(urls)
        
        for i, url in enumerate(urls):
            if progress_callback:
                progress_callback(i, total, url)
            
            try:
                # 调用 crawler 模块的核心函数
                raw_data = fetch_item(url, driver=self._driver)
                
                # 转换为 Product 模型
                product = Product(
                    url=raw_data["url"],
                    title=raw_data.get("product_title_main", ""),
                    shipping_cost=float(raw_data.get("shipping", 0.0)),
                    fallback_data=raw_data # 保留原始数据以备不时之需
                )
                
                # 转换 SKU
                for raw_sku in raw_data.get("skus", []):
                    sku = SKU(
                        name=raw_sku.get("name", ""),
                        price=raw_sku.get("price"), # 可能为 None
                        stock=raw_sku.get("stock", 0),
                        price_text=raw_sku.get("price_text", ""),
                        stock_text=raw_sku.get("stock_text", "")
                    )
                    product.skus.append(sku)
                
                products.append(product)
                
            except Exception as e:
                print(f"Error fetching {url}: {e}")
                # 即使出错也继续下一个，或者记录错误商品
                continue
                
        return products



class CalculationService:
    """
    计算服务：专门负责定价策略的应用和计算。
    纯内存操作，不依赖 WebDriver。
    """
    def calculate_prices(self, products: List[Product], strategy_func: Callable, strategy_params: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        对所有商品的 SKU 应用定价策略，返回扁平化的数据列表（用于前端展示）。
        """
        flat_data = []
        for product in products:
            for sku in product.skus:
                # 1. 准备基础 item 数据
                item_data = {
                    "product_url": product.url,
                    "product_title_main": product.title,
                    "name": sku.name,           # SKU 名称
                    "price": sku.price,         # 原价/成本
                    "stock": sku.stock,
                    "shipping": product.shipping_cost, # 默认运费
                    # 传入用户已设定的计划卖价 (如果有)
                    "selling_price": sku.selling_price
                }
                # 混合 extra_data
                item_data.update(sku.extra_data)

                # 2. 调用策略计算
                # 策略函数签名: func(item, **kwargs) -> dict
                try:
                    result = strategy_func(item_data, **strategy_params)
                except Exception as e:
                    result = item_data.copy()
                    result["error"] = str(e)

                # 3. 结果整合
                # 确保关键信息存在
                result["product_url"] = product.url
                result["name"] = sku.name
                
                # 回填一些基础信息以防丢失
                if "stock" not in result:
                    result["stock"] = sku.stock
                if "overall_shipping_cost" not in result:
                    result["overall_shipping_cost"] = product.shipping_cost
                
                flat_data.append(result)
        
        return flat_data

    def sync_dataframe_to_products(self, products: List[Product], edited_df: Any) -> int:
        """
        将编辑后的 DataFrame 数据回写到 Product 对象列表中。
        """
        if edited_df.empty:
            return 0
            
        # 建立快速查找索引 (url + sku_name) -> internal SKU object
        sku_map = {}
        for prod in products:
            for sku in prod.skus:
                key = (prod.url, sku.name)
                sku_map[key] = (prod, sku)
        
        count = 0
        import pandas as pd
        
        # 遍历编辑后的数据进行回写
        for idx, row in edited_df.iterrows():
            # product_url 可能在 index (若 hide_index=True 且 set_index) 或 column 中
            p_url = idx if isinstance(idx, str) else row.get("product_url")
            # 如果 idx 不是 url (比如默认 RangeIndex), 再次尝试获取
            if not isinstance(p_url, str) or not p_url.startswith("http"):
                 p_url = row.get("product_url")

            name = row.get("name")
            key = (p_url, name)
            
            if key in sku_map:
                prod, sku = sku_map[key]
                
                # 1. 更新 SKU 级数据 (价格、计划卖价)
                new_selling = row.get("selling_price")
                if pd.notna(new_selling):
                    val = float(new_selling)
                    sku.selling_price = val
                    sku.extra_data["selling_price"] = val
                    
                new_price = row.get("price")
                if pd.notna(new_price):
                    sku.price = float(new_price)
                    
                # 2. 更新 Product 级数据 (运费)
                new_shipping = row.get("overall_shipping_cost")
                if pd.notna(new_shipping):
                    prod.shipping_cost = float(new_shipping)
                    
                count += 1
        return count

    def get_quick_report(self, priced_data: List[Dict]) -> Dict:
        """生成简单的核对报告"""
        return quick_check(priced_data)


from src.importer import parse_excel_to_products

class ImportService:
    """
    导入服务：专门负责将外部数据导入为内部模型。
    纯内存操作。
    """
    def import_from_excel(self, file_content: bytes) -> List[Product]:
        """从 Excel 字节流导入商品数据"""
        return parse_excel_to_products(file_content)


class ExportService:
    """
    导出服务：专门负责将数据导出为文件或字节流。
    纯内存/IO操作，不依赖 WebDriver。
    """
    def export_data(
        self, 
        priced_data: List[Dict], 
        output_path: str = "result.xlsx", 
        first_url: str = "",
        base_name: str = "",
        strategy_name: str = ""
    ) -> str:
        """导出到本地文件"""
        return export_to_excel(priced_data, output_path, first_url, base_name, strategy_name)

    def get_excel_bytes(
        self, 
        priced_data: List[Dict], 
        first_url: str = "",
        base_name: str = "",
        strategy_name: str = ""
    ) -> Tuple[bytes, str]:
        """
        生成 Excel 文件字节流，用于 Web 下载。
        返回: (excel_bytes, suggested_filename)
        """
        return generate_excel_bytes(priced_data, first_url, base_name, strategy_name)
