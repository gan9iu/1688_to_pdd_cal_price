"""
限时限量购定价计算模块。
提供根据卖价、立减券、其他券和限时限量折扣计算最终拼单价的函数。
"""
from typing import Dict, Any


def calculate_limited_time_price(
    selling_price: float,
    instant_discount_coupon_price: float,
    limited_time_discount: float
) -> Dict[str, Any]:
    """
    计算限时限量购下的定价。

    参数:
    - selling_price (float): 卖价 (通常即抓取到的商品原价)
    - instant_discount_coupon_price (float): 立减券价格
    - limited_time_discount (float): 限时限量的折扣 (0.5 - 1.0 之间)

    返回:
    - dict: 包含中间价格和最终拼单价的字典。
    """
    if not (0.5 <= limited_time_discount <= 1.0):
        raise ValueError("限时限量的折扣必须在 0.5 到 1.0 之间。")

    if instant_discount_coupon_price > selling_price / 2:
        raise ValueError("立减券价格不能超过卖价的 1/2。")

    # 其他券的价格比立减券高 1 块
    max_coupon_amount = instant_discount_coupon_price + 1

    # 加完最大优惠券后的价格 = 卖价 + 最大优惠券的金额
    price_after_max_coupon = selling_price + max_coupon_amount

    # 最终拼单价 = 加完最大优惠券后的价格 / 限时限量的折扣
    raw_price = price_after_max_coupon / limited_time_discount
    
    # 应用心理学定价 (尾数 .9)
    from src.pricing.psychology import apply_charm_pricing
    final_group_buy_price = apply_charm_pricing(raw_price)

    return {
        "selling_price": round(selling_price, 2), # UI显示的计划卖价 (含利成本)
        "卖价": selling_price,
        "立减券价格": instant_discount_coupon_price,
        "最大优惠券金额": max_coupon_amount,
        "加完最大优惠券后的价格": price_after_max_coupon,
        "限时限量折扣": limited_time_discount,
        "raw_calculated_price": round(raw_price, 2), # 保留原始计算值参考
        "最终拼单价": final_group_buy_price,
        "限时限量购价格": final_group_buy_price, # 明确中文名
        # 为了兼容 export 模块，我们将最终结果也赋值给 'suggested_price'
        "suggested_price": final_group_buy_price
    }


def limited_time_strategy_adapter(item: Dict[str, Any], **kwargs) -> Dict[str, Any]:
    """
    适配器：将 batch_calculate 的通用调用转换为 calculate_limited_time_price 的具体调用。

    参数:
    - item: 包含商品信息的字典
    - kwargs: 必须包含 'instant_discount_coupon_price', 'limited_time_discount' 和 'shipping'
    """
    # 1. 获取商品原价
    try:
        price = float(item.get("price") or 0.0)
    except (ValueError, TypeError):
        price = 0.0
        
    # 2. 获取运费 (engine 已经处理好了优先级，kwargs['shipping'] 即为最终使用的运费)
    try:
        shipping = float(kwargs.get("shipping", 0.0))
    except (ValueError, TypeError):
        shipping = 0.0

    # 3. 确定基础卖价 (基准含利价)
    # 优先级: 用户手动填写/导入的 selling_price > 根据毛利率自动倒推
    user_selling_price = float(item.get("selling_price") or 0.0)
    
    if user_selling_price > 0:
        base_selling_price = user_selling_price
    else:
        # 自动计算: P = Total_Hard_Cost / (1 - Margin - Fee)
        target_margin = float(kwargs.get("target_margin", 0.0))
        platform_fee = float(kwargs.get("platform_fee_pct", 0.006))
        refund_rate = float(kwargs.get("refund_rate", 0.20))
        
        # 运费险默认 0.8 (目前UI没有传，暂设默认，后续可加)
        insurance = float(kwargs.get("shipping_insurance", 0.8)) 
        
        refund_loss = shipping * refund_rate
        total_hard_cost = price + shipping + insurance + refund_loss

        denom = 1 - target_margin - platform_fee
        if denom <= 0:
             return {"error": "利润率或平台费率设置过高"}
             
        base_selling_price = total_hard_cost / denom
    
    if base_selling_price <= 0:
        # 如果没有有效价格，返回错误信息
        return {"error": "无法获取有效的商品原价(price)或成本"}

    # 从 kwargs 中获取其他参数
    instant_coupon = float(kwargs.get("instant_discount_coupon_price", 0.0))
    discount = float(kwargs.get("limited_time_discount", 1.0))

    # 调用核心计算逻辑
    try:
        return calculate_limited_time_price(
            base_selling_price, instant_coupon, discount
        )
    except ValueError as e:
        return {"error": str(e)}
