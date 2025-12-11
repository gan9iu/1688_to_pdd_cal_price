import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.pricing.strategies.default import calculate_price

def test_case(name, cost, shipping, platform_fee_pct=0.06, target_margin_pct=0.20, extra_markup=0.0):
    print(f"--- 测试用例: {name} ---")
    print(f"输入: 成本={cost}, 运费={shipping}, 平台费率={platform_fee_pct}, 目标毛利={target_margin_pct}, 加价={extra_markup}")
    
    try:
        # 模拟 item 字典，虽然 calculate_price 主要用 kwargs，但第一个参数是 item
        item = {} 
        result = calculate_price(
            item,
            cost=cost,
            shipping=shipping,
            platform_fee_pct=platform_fee_pct,
            target_margin_pct=target_margin_pct,
            extra_markup=extra_markup
        )
        print(f"输出: 建议售价 = {result['suggested_price']}")
        
        # 手动验证公式
        # 售价 = (成本 + 运费 + 加价) / ((1 - 平台费率) * (1 - 目标毛利))
        denom = (1 - platform_fee_pct) * (1 - target_margin_pct)
        expected = (cost + shipping + extra_markup) / denom
        print(f"验算: ({cost} + {shipping} + {extra_markup}) / ((1 - {platform_fee_pct}) * (1 - {target_margin_pct}))")
        print(f"      = {cost + shipping + extra_markup} / {denom:.4f}")
        print(f"      = {expected:.4f}")
        
        if abs(result['suggested_price'] - round(expected, 2)) < 0.01:
            print("✅ 结果一致")
        else:
            print("❌ 结果不一致 (可能是四舍五入差异)")
            
    except Exception as e:
        print(f"❌ 发生错误: {e}")
    print("\n")

if __name__ == "__main__":
    # 场景 1: 简单商品，无运费
    # 预期: 10 / (0.94 * 0.8) = 10 / 0.752 ≈ 13.30
    test_case("基础款", cost=10.0, shipping=0.0)

    # 场景 2: 含运费
    # 预期: (20 + 5) / 0.752 = 25 / 0.752 ≈ 33.24
    test_case("含运费", cost=20.0, shipping=5.0)

    # 场景 3: 调整利润率 (30% 毛利)
    # 预期: 50 / (0.94 * 0.7) = 50 / 0.658 ≈ 75.99
    test_case("高利润", cost=50.0, shipping=0.0, target_margin_pct=0.30)

    # 场景 4: 包含人工加价
    # 预期: (10 + 0 + 2) / 0.752 = 12 / 0.752 ≈ 15.96
    test_case("人工加价", cost=10.0, shipping=0.0, extra_markup=2.0)
