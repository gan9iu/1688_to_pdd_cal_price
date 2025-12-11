"""
默认定价策略模块。
提供基于成本、运费、平台费率、目标毛利等规则的计算函数。
"""
from typing import Dict, Any, Union


def calculate_price(item: Dict[str, Any], **kwargs) -> Dict[str, Any]:
    """
    默认定价策略：基于成本加成 (统一成本模型)。
    """
    # 1. 提取基础参数
    try:
        base_cost = float(item.get("price") or kwargs.get("cost", 0.0))
    except (ValueError, TypeError):
        base_cost = 0.0
        
    try:
        shipping_cost = float(kwargs.get("shipping", 0.0))
    except (ValueError, TypeError):
        shipping_cost = 0.0
        
    shipping_insurance = float(kwargs.get("shipping_insurance", 0.8)) # 默认为0.8
    platform_fee_pct = float(kwargs.get("platform_fee_pct", 0.06))
    target_margin_pct = float(kwargs.get("target_margin_pct", 0.20))
    extra_markup = float(kwargs.get("extra_markup", 0.0))
    refund_rate = float(kwargs.get("refund_rate", 0.20)) # 新增

    # 2. 计算综合硬成本 (Total Hard Cost)
    # 包含：商品成本 + 运费 + 运费险 + 退款损耗
    refund_loss = shipping_cost * refund_rate
    total_hard_cost = base_cost + shipping_cost + shipping_insurance + refund_loss
    
    if total_hard_cost <= 0:
        return {
            "error": "无法获取有效成本",
            "suggested_price": 0.0,
            "selling_price": 0.0
        }

    # 3. 计算建议售价 (倒扣法)
    # P = Total_Hard_Cost / (1 - Margin - Fee)
    denom = 1 - target_margin_pct - platform_fee_pct
    
    if denom <= 0:
        return {
            "error": "利润率 + 平台费率 过高，无法计算",
            "suggested_price": 0.0, 
            "selling_price": 0.0
        }
    
    raw_price = (total_hard_cost / denom) + extra_markup
    
    # 4. 应用心理学定价
    from src.pricing.psychology import apply_charm_pricing
    suggested_price = apply_charm_pricing(raw_price)
    
    parsed = item.copy()
    parsed.update({
        "raw_calculated_price": round(raw_price, 2),
        "total_hard_cost": round(total_hard_cost, 2), # 方便调试
        "base_cost": base_cost,
        "shipping_cost": shipping_cost,
        "platform_fee_pct": platform_fee_pct,
        "target_margin_pct": target_margin_pct,
        "refund_loss": round(refund_loss, 2),
        "extra_markup": extra_markup,
        "suggested_price": suggested_price,
        "selling_price": round(raw_price, 2) # 计划卖价 = 原始计算值
    })

    return parsed
