"""
定价计算引擎模块。
提供批量计算和策略调度的核心逻辑。
"""
from typing import Callable, Dict, List, Any


def batch_calculate(
    items: List[Dict[str, Any]],
    strategy_func: Callable[..., Dict[str, Any]],
    strategy_params: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """
    批量计算定价。
    
    参数:
    - items: 包含 SKU 信息的字典列表。
    - strategy_func: 定价策略函数。
    - strategy_params: 策略参数。
    """
    processed_skus = []
    
    for item in items:
        # 1. 准备参数
        # 策略参数优先级：传入的 strategy_params > item 自带的数据
        # 但对于运费，如果 strategy_params 中未指定（或为0），则使用 item 中的运费
        current_params = strategy_params.copy()
        
        # 特殊处理运费逻辑：
        # 如果全局配置的运费为 0，则尝试使用 item 自身的运费
        global_shipping = float(current_params.get("shipping", 0.0))
        if global_shipping == 0:
            current_params["shipping"] = float(item.get("shipping", 0.0))
            
        # 2. 执行计算
        try:
            # 策略函数接收 item 和解包后的 params
            calc_results = strategy_func(item, **current_params)
            
            # 3. 合并结果
            # 将计算结果（如 suggested_price）合并回 item
            # 同时记录最终使用的运费，方便导出
            final_sku_data = item.copy()
            final_sku_data.update(calc_results)
            
            # 记录实际使用的运费，用于报表展示
            final_sku_data["overall_shipping_cost"] = current_params["shipping"]
            
            processed_skus.append(final_sku_data)
            
        except Exception as e:
            # 记录错误信息到 item 中，方便排查
            error_item = item.copy()
            error_item["error"] = str(e)
            processed_skus.append(error_item)
            
    return processed_skus
