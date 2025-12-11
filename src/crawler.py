"""
Selenium 爬虫模块。
负责页面元素解析、数据提取和浏览器驱动管理。
"""
import os
import re
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.firefox.service import Service
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from webdriver_manager.firefox import GeckoDriverManager

# ==========================================
# 配置常量
# ==========================================

# 页面解析策略 (Schema)
PAGE_SCHEMAS = [
    {
        "name": "Standard_Retail",
        "sku_wrapper": "css:#sku-count-widget-wrapper",
        "sku_item": "css:.sku-item-wrapper",
        "sku_name": "css:.sku-item-name",
        "price": "css:.discountPrice-price",
        "stock": "css:.sku-item-sale-num",
    },
    {
        "name": "Expand_View_Template",
        "sku_wrapper": "css:.expand-view-list",
        "sku_item": "css:.expand-view-item",
        "sku_name": "css:.item-label",
        "price": "css:.item-price-stock",
        "stock": "css:od-text[i18n='sku-stock']",
    },
]

# 通用选择器
COMMON_SELECTORS = {
    "product_title": [
        "css:div.title-content h1",
        "css:div.title-text",
        "css:h1.d-title",
        "css:.mod-detail-title h1"
    ],
    "shipping": [
        "css:em.service-item",
        "css:.logistics-express-price",
        "css:.logistics-cost",
        "css:.postage-cost",
        "css:.freight-cost",
        "css:.service-item"
    ],
    "single_price": [
        "css:.discountPrice-price",
        "css:.price-text",
        "css:.offer-current-price .value",
        "css:span.price",
        "css:.item-price-stock",
        "css:.discount-price .value"
    ],
    "category": [
        "css:.header-breadcrumb",
        "css:.breadcrumb", 
        "css:#box-str-breadcrumb",
        "css:.region-header-breadcrumb"
    ],
    "specs": [
        "css:.mod-detail-attributes",
        "css:.obj-content", 
        "css:.de-description-detail",
        "css:.offer-attr-list"
    ]
}


# ==========================================
# 辅助解析函数
# ==========================================

def _parse_selector(selector: str) -> Tuple[str, str]:
    """解析选择器字符串，返回 (By.XXX, expression)。"""
    if selector.startswith("css:"):
        return By.CSS_SELECTOR, selector[len("css:"):]
    if selector.startswith("xpath:"):
        return By.XPATH, selector[len("xpath:"):]
    return By.CSS_SELECTOR, selector


def _parse_price(text: str) -> Optional[float]:
    """解析价格文本，支持 '包邮' 识别。"""
    if not text:
        return None
    if "包邮" in text:
        return 0.0
    m = re.search(r"(\d+[\.,]?\d*)", text)
    if not m:
        return None
    try:
        return float(m.group(1).replace(',', ''))
    except ValueError:
        return None


def _parse_stock(text: str) -> int:
    """解析库存文本。"""
    if not text:
        return 0
    m = re.search(r"(\d+)", text)
    if not m:
        return 0
    try:
        return int(m.group(1))
    except ValueError:
        return 0


# ==========================================
# 核心抓取逻辑 (拆分为细粒度函数)
# ==========================================

def _fetch_title(driver: webdriver.Firefox) -> str:
    """尝试抓取商品标题。"""
    for sel in COMMON_SELECTORS["product_title"]:
        try:
            by, expr = _parse_selector(sel)
            el = driver.find_element(by, expr)
            text = el.get_attribute('textContent').strip()
            if text:
                return text
        except Exception:
            continue
    return ""


def _fetch_shipping(driver: webdriver.Firefox) -> Tuple[float, str]:
    """尝试抓取运费，返回 (price, text)。"""
    for sel in COMMON_SELECTORS["shipping"]:
        try:
            by, expr = _parse_selector(sel)
            elements = driver.find_elements(by, expr)
            for el in elements:
                txt = el.get_attribute('textContent').strip()
                if not txt:
                    continue
                price = _parse_price(txt)
                if price is not None:
                    return price, txt
        except Exception:
            continue
    return 0.0, ""


def _fetch_category(driver: webdriver.Firefox) -> str:
    """尝试抓取商品类目。"""
    for sel in COMMON_SELECTORS["category"]:
        try:
            by, expr = _parse_selector(sel)
            el = driver.find_element(by, expr)
            text = el.get_attribute('textContent').strip()
            # 清理换行和多余空格
            text = re.sub(r'\s+', ' ', text)
            if text:
                return text
        except Exception:
            continue
    return "未知"


def _fetch_specs(driver: webdriver.Firefox) -> str:
    """尝试抓取商品规格属性。"""
    for sel in COMMON_SELECTORS["specs"]:
        try:
            by, expr = _parse_selector(sel)
            el = driver.find_element(by, expr)
            text = el.get_attribute('textContent').strip()
            # 清理换行和多余空格
            text = re.sub(r'\s+', ' ', text)
            if text:
                return text
        except Exception:
            continue
    return ""


def _fetch_skus_by_schema(driver: webdriver.Firefox) -> List[Dict[str, Any]]:
    """尝试使用预定义的 Schema 抓取 SKU 列表。"""
    for schema in PAGE_SCHEMAS:
        try:
            # 1. 检查 Schema 特征容器
            by_wrap, expr_wrap = _parse_selector(schema["sku_wrapper"])
            
            # [优化] 增加等待时间到 10s，防止动态渲染未完成导致漏抓
            wrapper = WebDriverWait(driver, 2).until(
                EC.presence_of_element_located((by_wrap, expr_wrap))
            )
            
            # 2. 找到 SKU 项
            by_item, expr_item = _parse_selector(schema["sku_item"])
            items = wrapper.find_elements(by_item, expr_item)
            
            if not items:
                continue
                
            print(f"[{datetime.now()}] Success: Matched schema '{schema['name']}' with {len(items)} items")

            parsed_skus = []
            for i, item_el in enumerate(items):
                sku = {}
                # 提取名称
                try:
                    by_n, expr_n = _parse_selector(schema["sku_name"])
                    sku["name"] = item_el.find_element(by_n, expr_n).get_attribute('textContent').strip()
                except Exception:
                    sku["name"] = f"SKU_{i+1}"

                # 提取价格
                try:
                    by_p, expr_p = _parse_selector(schema["price"])
                    p_txt = item_el.find_element(by_p, expr_p).get_attribute('textContent').strip()
                except Exception:
                    p_txt = ""
                sku["price_text"] = p_txt
                sku["price"] = _parse_price(p_txt)

                # 提取库存
                try:
                    by_s, expr_s = _parse_selector(schema["stock"])
                    s_txt = item_el.find_element(by_s, expr_s).get_attribute('textContent').strip()
                except Exception:
                    s_txt = ""
                sku["stock_text"] = s_txt
                sku["stock"] = _parse_stock(s_txt)
                
                # [DEBUG] 打印抓取详情
                print(f"  - SKU: {sku['name'][:10]}... | PriceTxt: '{p_txt}' -> {sku['price']} | StockTxt: '{s_txt}'")

                parsed_skus.append(sku)
            
            return parsed_skus

        except Exception:
            # 当前 Schema 不匹配，尝试下一个
            continue
            
    return []


def _fetch_fallback_sku(driver: webdriver.Firefox) -> List[Dict[str, Any]]:
    """兜底逻辑：尝试抓取单品价格。"""
    price_val = None
    price_txt = ""
    
    for sel in COMMON_SELECTORS["single_price"]:
        try:
            by, expr = _parse_selector(sel)
            el = driver.find_element(by, expr)
            txt = el.get_attribute('textContent').strip()
            val = _parse_price(txt)
            if val is not None:
                price_val = val
                price_txt = txt
                break
        except Exception:
            continue
            
    if price_val is not None:
        return [{
            "name": "默认规格",
            "stock": 9999,
            "stock_text": "默认",
            "price": price_val,
            "price_text": price_txt
        }]
    return []


# ==========================================
# 主入口函数
# ==========================================

def _get_default_firefox_profile() -> Optional[str]:
    """尝试自动查找默认的 Firefox Profile 路径。"""
    try:
        app_data = os.getenv('APPDATA')
        if not app_data:
            return None
        profiles_ini = os.path.join(app_data, 'Mozilla', 'Firefox', 'profiles.ini')
        if not os.path.exists(profiles_ini):
            return None
            
        # 简单解析 profiles.ini 找 Default
        default_path = None
        base_path = os.path.dirname(profiles_ini)
        
        with open(profiles_ini, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            
        is_release = False
        path_str = None
        
        for line in lines:
            line = line.strip()
            if line == '[Install4F96D1932A9F858E]': # Default Release 标识
                is_release = True
            if line.startswith('Default=') and not default_path:
                # 相对路径
                temp = line.split('=')[1]
                default_path = os.path.join(base_path, temp.replace('/', '\\'))
        
        # 兜底：如果没有找到 Install 节，找任意一个 default-release
        if not default_path:
            profiles_dir = os.path.join(base_path, 'Profiles')
            if os.path.exists(profiles_dir):
                for p in os.listdir(profiles_dir):
                    if p.endswith('.default-release'):
                        default_path = os.path.join(profiles_dir, p)
                        break
                        
        return default_path
    except Exception:
        return None

def create_driver(
    headless: bool = True, 
    driver_path: Optional[str] = None, 
    use_firefox_profile: bool = False
) -> webdriver.Remote:
    """创建并配置 WebDriver (支持 Firefox 无头/有头/加载配置)。"""
    
    firefox_opts = webdriver.FirefoxOptions()
    
    # 加载用户配置模式
    if use_firefox_profile:
        headless = False # 强制有头
        profile_path = _get_default_firefox_profile()
        if profile_path and os.path.exists(profile_path):
            print(f"[Info] 正在加载 Firefox 配置文件: {profile_path}")
            # 方法 A: 使用 -profile 参数 (推荐，更稳定)
            firefox_opts.add_argument("-profile")
            firefox_opts.add_argument(profile_path)
        else:
            print("[Warning] 未找到默认 Firefox 配置文件，将使用临时配置。")

    if headless:
        firefox_opts.add_argument("--headless")

    # 尝试查找默认安装路径，如果找不到则不设置（让 Selenium 自己找）
    default_binary_paths = [
        r"C:\Program Files\Mozilla Firefox\firefox.exe",
        r"D:\Program Files\Mozilla Firefox\firefox.exe",
    ]
    for path in default_binary_paths:
        if os.path.exists(path):
            firefox_opts.binary_location = path
            break

    # 反爬虫配置
    firefox_opts.set_preference("dom.webdriver.enabled", False)
    firefox_opts.set_preference("useAutomationExtension", False)
    firefox_opts.add_argument("--disable-blink-features=AutomationControlled")
    firefox_opts.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:141.0) Gecko/20100101 Firefox/141.0"
    )

    # 驱动服务配置
    user_specified_driver = r"D:\jzc_work\src\geckodriver.exe"
    
    if driver_path and os.path.exists(driver_path):
        service = Service(driver_path)
    elif os.path.exists(user_specified_driver):
        # [Fix] 优先使用用户指定的本地驱动
        print(f"[Info] 使用本地 Geckodriver: {user_specified_driver}")
        service = Service(user_specified_driver)
    else:
        # 自动安装/查找驱动
        # [Fix] 增加异常处理，防止 GitHub API Rate Limit 导致无法启动
        try:
            exe_path = GeckoDriverManager().install()
            service = Service(exe_path)
        except Exception as e:
            print(f"[Warning] 自动下载驱动失败 (可能是网络或API限制): {e}")
            print("[Info] 尝试直接使用系统 PATH 中的 'geckodriver'...")
            service = Service("geckodriver")

    driver = webdriver.Firefox(service=service, options=firefox_opts)
    
    # JS 注入隐藏特征
    driver.execute_script("""
        Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
    """)
    
    return driver


def fetch_item(
    url: str, 
    driver: Optional[webdriver.Firefox] = None, 
    timeout: int = 10
) -> Dict[str, Any]:
    """
    抓取单个商品页面的核心函数。
    """
    own_driver = False
    if driver is None:
        driver = create_driver(headless=False)
        own_driver = True

    try:
        driver.get(url)
        # 检查是否跳转到了登录页
        current_url = driver.current_url
        if "login.1688.com" in current_url or "login.taobao.com" in current_url:
             raise RuntimeError(f"反爬虫拦截：已跳转至登录页面 ({current_url})。请尝试关闭【无头模式】并手动扫码登录。")

        # 1. 抓取标题 (关键：如果标题都抓不到，说明页面大概率被拦截了)
        title = _fetch_title(driver)
        
        # [增强版] 人工介入模式
        if not title:
            print("⚠️ 未找到标题，可能触发了验证码。正在暂停 30 秒等待人工处理...")
            # 简单的重试循环：等待用户手动处理
            import time
            for _ in range(6): # 6 * 5s = 30s
                time.sleep(5)
                title = _fetch_title(driver)
                if title:
                    print("✅ 标题已抓取，人工处理成功！")
                    break
            
            if not title:
                raise RuntimeError(f"抓取失败：超时未获取到标题，URL: {url}")

        # 2. 抓取运费
        shipping_price, shipping_text = _fetch_shipping(driver)

        # 3. 抓取类目和规格 (新增)
        category = _fetch_category(driver)
        specs = _fetch_specs(driver)

        # 4. 抓取 SKU (优先 Schema，失败则兜底)
        skus = _fetch_skus_by_schema(driver)
        if not skus:
            print(f"[{datetime.now()}] Info: No schema matched, trying fallback for {url}")
            skus = _fetch_fallback_sku(driver)

        return {
            "url": url,
            "product_title_main": title,
            "shipping": shipping_price,
            "shipping_text": shipping_text,
            "category": category,      # 新增
            "specs": specs,            # 新增
            "skus": skus
        }

    finally:
        if own_driver and driver:
            driver.quit()
