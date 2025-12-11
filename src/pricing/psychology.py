import math

def apply_charm_pricing(price: float) -> float:
    """
    应用购物心理学定价策略（尾数定价/魅力定价）。
    将价格调整为以 .9 结尾，以增加消费者的购买欲望，同时确保不亏本（只会向上调整或极小幅度向下）。
    
    策略:
    1. 基础逻辑：取整后 + 0.9 (即 X.9)。
    2. 亏本保护：如果原价本身超过了 X.9 (例如 12.95)，则升级到下一档 (X+1).9。
    
    示例:
    - 12.00 -> 12.90 (增加利润)
    - 12.30 -> 12.90 (增加利润)
    - 12.85 -> 12.90 (微增利润)
    - 12.95 -> 13.90 (避免亏本，升级档位)
    """
    if price <= 0:
        return 0.0
        
    integer_part = int(price)
    target_price = integer_part + 0.9
    
    # 如果目标价格比原价低 (例如 12.95 vs 12.90)，则升级到下一档位
    if target_price < price:
        target_price += 1.0
        
    return round(target_price, 2)
