from fastapi import FastAPI
from pydantic import BaseModel
import uvicorn
from typing import Optional

# ▼▼▼ 直接复用您现有的高质量代码 ▼▼▼
from src.crawler import fetch_item, create_driver 

app = FastAPI()

class FetchRequest(BaseModel):
    url: str

@app.post("/feishu_fetch")
def feishu_fetch(req: FetchRequest):
    # 复用现有的驱动逻辑
    driver = create_driver(headless=True)
    try:
        # 复用现有的抓取逻辑
        data = fetch_item(req.url, driver=driver)
        
        # 尝试从 SKU 中获取成本 (取第一个有价格的 SKU)
        cost = 0.0
        skus = data.get("skus", [])
        if skus:
            # 尝试找到第一个有效的价格
            for sku in skus:
                if sku.get("price"):
                    cost = sku.get("price")
                    break
        
        # 组装成飞书需要的格式
        return {
            "code": 0,
            "data": {
                "采购成本": cost,  # 从 SKU 提取
                "预估运费": data.get("shipping", 0.0),
                "类目": data.get("category", "未知"),  # 新增字段
                "1688规格": data.get("specs", "")      # 新增字段
            }
        }
    finally:
        driver.quit()

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
