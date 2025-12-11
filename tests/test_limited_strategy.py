import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.pricing.strategies.limited import calculate_limited_time_price

def verify_case(selling_price, instant_coupon, discount, expected_price=None):
    print(f"--- 测试用例 ---")
    print(f"输入: 卖价(预期收入)={selling_price}, 立减券={instant_coupon}, 折扣={discount}")
    
    try:
        result = calculate_limited_time_price(selling_price, instant_coupon, discount)
        calculated_price = result["最终拼单价"]
        print(f"计算结果: 最终拼单价 = {calculated_price:.4f}")
        print(f"中间过程: 最大优惠券 = {result['最大优惠券金额']}, 加券后(分子) = {result['加完最大优惠券后的价格']}")
        
        if expected_price is not None:
            diff = abs(calculated_price - expected_price)
            if diff < 0.01:
                print(f"✅ 验证通过 (预期 {expected_price})")
            else:
                print(f"❌ 验证失败 (预期 {expected_price}, 实际 {calculated_price:.4f})")
    except Exception as e:
        print(f"❌ 发生错误: {e}")
    print("\n")

if __name__ == "__main__":
    # 用户提供的测试数据
    # 第一组
    verify_case(selling_price=10.0, instant_coupon=5.0, discount=0.5, expected_price=32.0)
    
    # 第二组
    verify_case(selling_price=20.0, instant_coupon=7.0, discount=0.8, expected_price=35.0) 
