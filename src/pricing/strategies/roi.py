"""
最佳投产比计算策略模块。
用于计算广告投放的 ROI 指标。
"""
from typing import Dict, Any


def calculate_roi(
    item: Dict[str, Any],
    *,
    shipping: float = 0.0,
    shipping_insurance: float = 0.8,
    refund_rate: float = 0.20,
    fixed_selling_price: float = 0.0,
    target_margin_pct: float = 0.0,
    platform_fee: float = 0.006 # 默认千分之六
) -> Dict[str, Any]:
    """
    计算保本投产、净投产和最佳投产。
    """
    
    # 1. 获取成本数据
    try:
        product_cost = float(item.get("price") or 0.0) # 产品成本
    except (ValueError, TypeError):
        product_cost = 0.0
        
    shipping_cost = float(shipping)
    
    # 综合硬成本: 商品 + 运费 + 运费险 + 退款损耗(退货损失的运费)
    # 假设退货损失 = 运费 * 退款率 (货品退回)
    refund_loss_cost = shipping_cost * refund_rate
    total_hard_cost = product_cost + shipping_cost + shipping_insurance + refund_loss_cost

    # 2. 获取实际成交价
    # 优先级: item自带 > fixed固定 > margin毛利倒推
    actual_selling_price = float(item.get("selling_price") or 0.0)
    
    if actual_selling_price <= 0:
        if fixed_selling_price > 0:
            actual_selling_price = fixed_selling_price
        elif 0 < target_margin_pct < 1.0:
            # 使用倒扣法自动填充计划售价 (包含平台扣点)
            # P = Cost / (1 - Margin - Fee)
            denom = 1 - target_margin_pct - platform_fee
            if denom > 0:
                actual_selling_price = round(total_hard_cost / denom, 2)
            else:
                actual_selling_price = 0.0

    if product_cost <= 0:
         return {"error": "缺少产品成本(price)"}
         
    if actual_selling_price <= 0:
        return {"error": "未设置售价且无法自动计算"}

    # 3. 计算保本投产
    # 真实收入 = 卖价 * (1 - 平台扣点)
    # 单单毛利 = 真实收入 - 综合硬成本
    effective_revenue = actual_selling_price * (1 - platform_fee)
    profit_per_order = effective_revenue - total_hard_cost
    
    if profit_per_order <= 0:
        # 亏损状态
        return {
            "selling_price": actual_selling_price,
            "overall_shipping_cost": shipping_cost,
            "profit_per_order": round(profit_per_order, 2),
            "error": "亏损商品 (利润<=0)"
        }

    breakeven_roi = actual_selling_price / profit_per_order

    # 4. 计算净投产
    # 既然已经把退款损耗算进成本了，净投产公式可以简化，或者保留作为安全系数
    # 传统经验公式: 保本 / (1-退款率) * 1.05
    # 我们这里保留原经验公式，作为双重保险
    if refund_rate >= 1.0:
        net_roi = 0.0
    else:
        net_roi = (breakeven_roi / (1 - refund_rate)) * 1.05

    # 5. 计算最佳投产
    # 最佳投产 = 净投产 * 1.3
    best_roi = net_roi * 1.3

    return {
        # 基础数据回显
        "selling_price": actual_selling_price,
        "overall_shipping_cost": shipping_cost,
        "shipping_insurance": shipping_insurance, 
        "refund_rate": refund_rate,
        "profit_per_order": round(profit_per_order, 2), # 单单毛利
        
        # 核心指标
        "breakeven_roi": round(breakeven_roi, 2), # 保本投产
        "net_roi": round(net_roi, 2),             # 净投产
        "best_roi": round(best_roi, 2),           # 最佳投产
        
        # 兼容导出 (将最佳投产设为 suggested_price 位置，或者新增列)
        # 这里我们不覆盖 suggested_price，而是依靠 Exporter 导出新列
        # 但为了 summary 报告不报错，给个 dummy 值
        "suggested_price": round(actual_selling_price, 2) 
    }
