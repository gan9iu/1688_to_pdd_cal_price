from fastapi import FastAPI
from pydantic import BaseModel
import uvicorn
# 引用现有的爬虫逻辑
from src.crawler import fetch_item, create_driver 

app = FastAPI()

class FetchRequest(BaseModel):
    url: str

@app.post("/feishu_fetch")
def feishu_fetch(req: FetchRequest):
    driver = create_driver(headless=True)
    try:
        data = fetch_item(req.url, driver=driver)
        
        # 1. 提取成本 (取第一个有效 SKU 价格)
        cost = 0.0
        skus = data.get("skus", [])
        if skus:
            for sku in skus:
                if sku.get("price"):
                    cost = sku.get("price")
                    break
        
        # 2. 【关键修改】智能合并规格与包装信息
        specs_text = data.get("specs", "")
        packaging_text = data.get("packaging", "")
        
        # 构造一个分段清晰的文本，方便 AI 阅读，也方便人类查阅
        # 格式示例：
        # 【基本属性】
        # 材质:PP; 风格:日式...
        # 
        # 【物流包装】
        # [单件重量: 0.5kg]; [外箱尺寸: 50x40x30cm]
        full_specs = ""
        if specs_text:
            full_specs += f"【基本属性】\n{specs_text}\n"
        if packaging_text:
            full_specs += f"\n【物流包装】\n{packaging_text}"
            
        # 如果两者都空，给个默认值
        if not full_specs:
            full_specs = "暂无详细规格数据"

        return {
            "code": 0,
            "data": {
                # 飞书字段映射
                "采购成本": cost,
                "预估运费": data.get("shipping", 0.0),
                "类目": data.get("category", "未知"), 
                
                # 这里只返回一个“1688规格”字段，包含了所有物理信息
                "1688规格": full_specs.strip()
            }
        }
    finally:
        driver.quit()

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)