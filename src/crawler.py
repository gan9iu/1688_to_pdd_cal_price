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
        "css:.discount-price .value"
    ],
    "attributes_table": [
        "css:#productAttributes table",  # 新增：针对 id="productAttributes" 的最强匹配
        "css:.od-collapse-module[data-spm-anchor-id*='productAttributes'] table",
        "css:div[data-spm-anchor-id*='productAttributes'] table",
        "css:.ant-descriptions-view table",
    ],
    "packaging_table": [
        "css:#productPackInfo table",
        "css:[data-module='od_product_pack_info'] table"
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


def _fetch_table_as_dict(driver: webdriver.Firefox, selectors: List[str]) -> Dict[str, str]:
    """通用：抓取指定选择器的表格数据并转为字典。"""
    attrs = {}
    for sel in selectors:
        try:
            by, expr = _parse_selector(sel)
            table = driver.find_element(by, expr)
            
            # 模式A: Ant Design Description (tr -> th, td)
            # 适用于"商品属性"
            rows = table.find_elements(By.CSS_SELECTOR, "tr")
            if not rows: continue

            # 预检：是否有 thead (适用于"包装信息")
            headers = table.find_elements(By.CSS_SELECTOR, "thead th")
            if headers:
                # 模式B: 标准表格 (thead -> th, tbody -> tr -> td)
                col_names = [h.get_attribute('textContent').strip() for h in headers]
                body_rows = table.find_elements(By.CSS_SELECTOR, "tbody tr")
                if body_rows:
                    first_row_tds = body_rows[0].find_elements(By.CSS_SELECTOR, "td")
                    for i, td in enumerate(first_row_tds):
                        if i < len(col_names):
                            key = col_names[i]
                            val = td.get_attribute('textContent').strip()
                            if key and val and key not in attrs:
                                attrs[key] = val
            else:
                 # 模式A: 属性键值对表格
                for row in rows:
                    ths = row.find_elements(By.CSS_SELECTOR, "th")
                    tds = row.find_elements(By.CSS_SELECTOR, "td")
                    limit = min(len(ths), len(tds))
                    for i in range(limit):
                        if i < len(ths) and i < len(tds):
                            key = ths[i].get_attribute('textContent').strip()
                            val = tds[i].get_attribute('textContent').strip()
                            if key and val:
                                attrs[key] = val
            if attrs:
                return attrs
        except Exception:
            continue
    return attrs


def _fetch_all_rows_as_text(driver: webdriver.Firefox, selectors: List[str]) -> str:
    """
    抓取表格的所有行数据，返回格式化的长字符串。
    格式: [行1属性1:值1, 行1属性2:值2]; [行2属性1:值1, ...]; ...
    """
    result_lines = []
    
    for sel in selectors:
        try:
            by, expr = _parse_selector(sel)
            table = driver.find_element(by, expr)
            
            # --- 模式解析 ---
            
            # 模式B: 标准表格 (thead -> th, tbody -> tr -> td) 
            # 这种通常见于 "包装信息"，我们需要抓取所有行
            headers = table.find_elements(By.CSS_SELECTOR, "thead th")
            if headers:
                col_names = [h.get_attribute('textContent').strip() for h in headers]
                body_rows = table.find_elements(By.CSS_SELECTOR, "tbody tr")
                
                for row_idx, row in enumerate(body_rows):
                    tds = row.find_elements(By.CSS_SELECTOR, "td")
                    row_data = []
                    limit = min(len(col_names), len(tds))
                    
                    for i in range(limit):
                        key = col_names[i]
                        val = tds[i].get_attribute('textContent').strip()
                        if key and val:
                             # 清理空格
                            val = re.sub(r'\s+', ' ', val)
                            row_data.append(f"{key}:{val}")
                            
                    if row_data:
                        result_lines.append(f"[{'; '.join(row_data)}]")
                
                if result_lines:
                    return " | ".join(result_lines)
            
            # 模式A: 键值对表格 (tr -> th, td) 
            # 通常不需要"所有行"模式，因为它本身就是平铺的，保持原来的字典逻辑即可，
            # 这里如果不小心匹配到了(概率极低)，暂且返回空
            
        except Exception:
            continue
            
    return ""  


def _fetch_specs(driver: webdriver.Firefox) -> str:
    """抓取商品属性 (对应第一个HTML片段)"""
    # 属性通常是 Key-Value 平铺的，用原来的逻辑
    attrs = _fetch_table_as_dict(driver, COMMON_SELECTORS["attributes_table"])
    specs_list = []
    for k, v in attrs.items():
        c_v = re.sub(r'\s+', ' ', v)
        specs_list.append(f"{k}:{c_v}")
    return "; ".join(specs_list)


def _fetch_packaging(driver: webdriver.Firefox) -> str:
    """抓取包装信息 (对应第二个HTML片段) - 返回所有行"""
    # 使用全量抓取函数
    return _fetch_all_rows_as_text(driver, COMMON_SELECTORS["packaging_table"])


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
    """
    尝试获取 Firefox 配置文件路径。
    优先级: 环境变量 -> Windows 默认路径
    """
    # 1. 优先检查环境变量 (服务器部署推荐)
    env_profile = os.getenv("FIREFOX_PROFILE_PATH")
    if env_profile and os.path.exists(env_profile):
        return env_profile

    # 2. 尝试自动查找 Windows 默认路径
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
    
    # --- Profile 加载逻辑 ---
    
    # 哪怕 headless 也可以加载 profile，不一定强制 headless=False
    # 但如果为了利用本地登录态，通常建议有头模式调试
    
    if use_firefox_profile:
        # 我们可以允许 headless 模式也加载配置，这在服务器上很有用
        # headless = False  <-- 删掉这一行强制
        
        profile_path = _get_default_firefox_profile()
        if profile_path and os.path.exists(profile_path):
            print(f"[Info] 正在加载 Firefox 配置文件: {profile_path}")
            firefox_opts.add_argument("-profile")
            firefox_opts.add_argument(profile_path)
        else:
            print("[Warning] 未找到 Firefox 配置文件，将使用临时配置。")
    
    # --- 强力“静音”配置 (防止弹窗) ---
    # 无论是否加载 profile，都注入这些首选项以屏蔽干扰
    prefs = {
        "browser.startup.homepage": "about:blank",
        "startup.homepage_welcome_url": "about:blank",
        "startup.homepage_welcome_url.additional": "",
        "browser.startup.page": 0,
        "browser.shell.checkDefaultBrowser": False, # 别问我是不是默认浏览器
        "browser.tabs.warnOnClose": False,
        "browser.rights.3.shown": True, # 别弹“您的权利”
        "datareporting.healthreport.uploadEnabled": False,
        "toolkit.telemetry.enabled": False,
        "intl.accept_languages": "zh-CN,zh;q=0.9,en;q=0.8", # 伪装中文环境
    }
    for k, v in prefs.items():
        firefox_opts.set_preference(k, v)

    if headless:
        firefox_opts.add_argument("--headless")
        # [优化] 针对 2G 内存服务器的极限优化
        firefox_opts.add_argument("--no-sandbox")
        firefox_opts.add_argument("--disable-dev-shm-usage")
        firefox_opts.add_argument("--disable-gpu")
        # 限制页面加载策略为 eager (HTML加载完就认为OK，不等所有图片资源，大幅省内存)
        firefox_opts.page_load_strategy = 'eager'

        # [服务器端专用] 极速模式：禁止图片加载以节省带宽和内存
        # 2 = 禁止加载图片
        firefox_opts.set_preference("permissions.default.image", 2)
        # 禁止 Flash 等插件
        firefox_opts.set_preference("plugin.state.flash", 0)
        # 限制缓存
        firefox_opts.set_preference("browser.cache.disk.enable", False)
        firefox_opts.set_preference("browser.cache.memory.enable", False)
        firefox_opts.set_preference("browser.cache.offline.enable", False)
        firefox_opts.set_preference("network.http.use-cache", False)

    # 尝试查找默认安装路径，如果找不到则不设置（让 Selenium 自己找）
    # 优先读取环境变量 FIREFOX_BIN
    binary_path = os.getenv("FIREFOX_BIN")
    if not binary_path:
        # 如果没有环境变量，尝试寻找常见的 Windows 安装路径作为兜底
        possible_paths = [
            r"C:\Program Files\Mozilla Firefox\firefox.exe",
            r"C:\Program Files (x86)\Mozilla Firefox\firefox.exe",
            r"D:\Program Files\Mozilla Firefox\firefox.exe",
        ]
        for path in possible_paths:
            if os.path.exists(path):
                binary_path = path
                break
    
    if binary_path and os.path.exists(binary_path):
        firefox_opts.binary_location = binary_path

    # 反爬虫配置
    firefox_opts.set_preference("dom.webdriver.enabled", False)
    firefox_opts.set_preference("useAutomationExtension", False)
    firefox_opts.add_argument("--disable-blink-features=AutomationControlled")
    firefox_opts.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:141.0) Gecko/20100101 Firefox/141.0"
    )

    # 驱动服务配置
    service = None

    # 1. 优先使用传入的路径
    if driver_path and os.path.exists(driver_path):
        service = Service(driver_path)
    else:
        # 2. 尝试从环境变量获取驱动路径
        env_driver = os.getenv("GECKODRIVER_PATH")
        if env_driver and os.path.exists(env_driver):
             service = Service(env_driver)
        # 3. 自动安装/查找驱动
        else:
            try:
                # 尝试自动管理 (会下载到用户目录的 .wdm 下，Linux下也兼容)
                exe_path = GeckoDriverManager().install()
                service = Service(exe_path)
            except Exception as e:
                print(f"[Warning] 自动下载驱动失败: {e}")
                print("[Info] 尝试直接使用系统 PATH 中的 'geckodriver'...")
                # 只要 geckodriver 在系统 PATH 里 (如 /usr/bin/), 这样写就行
                service = Service("geckodriver")

    driver = webdriver.Firefox(service=service, options=firefox_opts)
    
    # [优化] 无论是否无头，都强制设置大窗口，防止触发移动端布局或风控
    try:
        driver.set_window_size(1920, 1080)
    except Exception:
        pass
        
    # JS 注入隐藏特征
    driver.execute_script("""
        Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
    """)
    
    return driver



def _load_cookies(driver: webdriver.Firefox):
    """尝试加载并注入 cookies.json"""
    cookie_file = "cookies.json"
    if not os.path.exists(cookie_file):
        return

    try:
        with open(cookie_file, "r", encoding="utf-8") as f:
            cookies = json.load(f)
        
        # 必须先访问一次目标域名，才能注入 Cookie
        # 访问一个轻量级页面以减少加载时间
        if "1688.com" not in driver.current_url:
            driver.get("https://www.1688.com/robots.txt")
        
        for cookie in cookies:
            # Selenium 对 cookie 字段很挑剔，去掉多余字段
            valid_keys = {'name', 'value', 'domain', 'path', 'expiry', 'secure', 'httpOnly', 'sameSite'}
            cookie_dict = {k: v for k, v in cookie.items() if k in valid_keys}
            try:
                driver.add_cookie(cookie_dict)
            except Exception:
                # 忽略某些无法添加的脏 cookie
                pass
        print(f"[Info] 已注入 {len(cookies)} 个 Cookie")
    except Exception as e:
        print(f"[Warning] 加载 Cookie 失败: {e}")


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
        # [关键] 在访问具体商品前，先注入 Cookie
        _load_cookies(driver)

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
                # 抓取失败时的详细诊断
                curr_title = driver.title
                page_len = len(driver.page_source)
                raise RuntimeError(
                    f"抓取失败：超时未获取到标题。\n"
                    f"当前URL: {driver.current_url}\n"
                    f"当前页面Title: {curr_title}\n"
                    f"页面源码长度: {page_len}\n"
                    f"提示：如果页面Title显示为'登录'或'验证'，请配置 cookie 或检查网络。"
                )

        # 2. 抓取运费
        shipping_price, shipping_text = _fetch_shipping(driver)

        # 3. 抓取类目、属性、包装 (分离抓取)
        category = _fetch_category(driver)
        specs = _fetch_specs(driver)
        packaging = _fetch_packaging(driver)

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
            "category": category,
            "specs": specs,
            "packaging": packaging,    # 分离的包装信息
            "skus": skus
        }

    finally:
        if own_driver and driver:
            driver.quit()
