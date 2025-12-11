import json
import time
from src.crawler import create_driver

def save_cookies():
    print("正在启动浏览器...")
    # 这里强制使用有头模式 + 本地 Profile (如果有)
    driver = create_driver(headless=False)
    
    try:
        print("正在打开 1688 登录页...")
        driver.get("https://login.1688.com/member/signin.htm")
        
        print(">>> 请在弹出的浏览器中扫码登录... (完成登录页面跳转后再继续)")
        input(">>> 登录成功并看到首页后，请在这里按回车键继续...")
        
        # 获取 Cookies
        cookies = driver.get_cookies()
        
        # 保存到文件
        with open("cookies.json", "w", encoding="utf-8") as f:
            json.dump(cookies, f, ensure_ascii=False, indent=2)
            
        print(f"✅ 成功保存 {len(cookies)} 个 Cookie 到 cookies.json！")
        print(">>> 下一步：请将生成的 cookies.json 文件上传到服务器项目根目录。")
        
    except Exception as e:
        print(f"❌ 发生错误: {e}")
    finally:
        if driver:
            driver.quit()

if __name__ == "__main__":
    save_cookies()
