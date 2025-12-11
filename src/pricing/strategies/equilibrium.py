"""
平衡点智能定价策略模块。
基于预期的广告 ROI，反推建议售价。
解决“定价-推广费-利润”的死循环问题。
"""
from typing import Dict, Any


def calculate_equilibrium_price(
    item: Dict[str, Any],
    *,
    shipping: float = 0.0,
    shipping_insurance: float = 0.8,
    platform_fee_pct: float = 0.006,  # 默认千分之六
    expected_roi: float = 3.0,        # 预期的广告投产比
    target_profit: float = 2.0,       # 目标单单毛利 (元)
    refund_rate: float = 0.20         # 新增
) -> Dict[str, Any]:
    """
    根据预期 ROI 反推建议售价。

    公式:
    售价 = (固定成本 + 目标利润) / (1 - 平台费率 - (1/预期ROI))
    """
    
    # 1. 获取固定成本
    try:
        product_cost = float(item.get("price") or 0.0)
    except (ValueError, TypeError):
        product_cost = 0.0
        
    shipping_cost = float(shipping)
    insurance_cost = float(shipping_insurance)
    
    # 综合硬成本: 商品 + 运费 + 运费险 + 退款损耗
    refund_loss = shipping_cost * refund_rate
    fixed_costs = product_cost + shipping_cost + insurance_cost + refund_loss
    
    if product_cost <= 0:
        return {"error": "缺少产品成本(price)"}

    # 2. 计算变动成本比例
    # 广告费占比 = 1 / ROI
    if expected_roi <= 0:
        return {"error": "预期 ROI 必须大于 0"}
    
    ad_cost_pct = 1 / expected_roi
    
    # 总扣点比例 = 平台费率 + 广告费占比
    total_deduction_pct = platform_fee_pct + ad_cost_pct
    
    # 3. 计算分母 (剩余价值比例)
    denominator = 1 - total_deduction_pct
    
    if denominator <= 0:
        return {
            "error": f"参数配置不合理：广告费({ad_cost_pct:.1%}) + 平台费({platform_fee_pct:.1%}) ≥ 100%，卖得越贵亏得越多！请提高预期 ROI。"
        }

    # 4. 计算建议售价
    # 盈亏平衡价 (利润为0)
    breakeven_price = fixed_costs / denominator
    
    # 目标盈利价
    raw_suggested = (fixed_costs + target_profit) / denominator
    
    from src.pricing.psychology import apply_charm_pricing
    suggested_price = apply_charm_pricing(raw_suggested)

    return {
        "base_cost": product_cost,
        "overall_shipping_cost": shipping_cost, # 回显给 exporter
        "shipping_insurance": insurance_cost,
        
        # 核心结果
        "suggested_price": round(suggested_price, 2), # 建议售价
        "breakeven_price": round(breakeven_price, 2), # 保本底价
        
        # 辅助信息
        "expected_roi": expected_roi,
        "target_profit": target_profit,
        "ad_cost_limit": round(suggested_price * ad_cost_pct, 2) # 此价格下的广告费上限
    }
