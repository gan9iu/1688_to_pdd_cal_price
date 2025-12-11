"""
简单的命令行入口：读取 URL 列表，抓取、计算定价并导出 Excel。
用法示例：
    python cli.py --input urls.txt --out result.xlsx
"""
import argparse
import time

from src.pricing.strategies.default import calculate_price
from src.pricing.strategies.limited import limited_time_strategy_adapter
from src.service import CrawlerService, CalculationService, ExportService


def read_urls(path: str):
    with open(path, "r", encoding="utf-8") as f:
        return [l.strip() for l in f if l.strip()]


def main():
    parser = argparse.ArgumentParser(description="1688 -> PDD 定价流程")
    parser.add_argument(
        "--input", required=True, help="包含商品链接的文本文件，每行一个链接"
    )
    parser.add_argument("--out", default="result.xlsx", help="导出文件名")
    parser.add_argument(
        "--headless", action="store_true", help="是否使用无头浏览器"
    )
    parser.add_argument(
        "--driver-path", dest="driver_path", help="可选：指定本地浏览器驱动路径"
    )

    # 定价策略选择
    parser.add_argument(
        "--strategy",
        choices=["default", "limited"],
        default="default",
        help="选择定价策略：default(默认毛利定价), limited(限时限量定价)"
    )

    # 限时限量策略参数
    parser.add_argument(
        "--instant-coupon", type=float, default=5.0, help="[限时限量] 立减券金额"
    )
    parser.add_argument(
        "--discount", type=float, default=0.9, help="[限时限量] 限时折扣 (0.5-1.0)"
    )

    args = parser.parse_args()

    urls = read_urls(args.input)
    if not urls:
        print("未找到有效的 URL。")
        return

    # 准备策略
    if args.strategy == "limited":
        print(
            f"--- 使用限时限量定价策略 "
            f"(立减券={args.instant_coupon}, 折扣={args.discount}) ---"
        )
        strategy_func = limited_time_strategy_adapter
        strategy_params = {
            "instant_discount_coupon_price": args.instant_coupon,
            "limited_time_discount": args.discount
        }
    else:
        print("--- 使用默认毛利定价策略 ---")

        def default_adapter(item, **kwargs):
            return calculate_price(item, **kwargs)

        strategy_func = default_adapter
        strategy_params = {
            "cost": 0.0,
            "platform_fee_pct": 0.06,
            "target_margin_pct": 0.20,
            "extra_markup": 0.0
        }

    start = time.time()
    
    # 1. 抓取 (使用 CrawlerService)
    print("正在启动浏览器并抓取数据...")
    products = []
    try:
        with CrawlerService(headless=args.headless, driver_path=args.driver_path) as crawler:
            products = crawler.fetch_products(
                urls, 
                progress_callback=lambda i, total, url: print(f"[{i+1}/{total}] 正在抓取: {url}")
            )
    except Exception as e:
        print(f"抓取过程发生错误: {e}")
        return

    if not products:
        print("未抓取到任何商品数据。")
        return

    # 2. 计算 (使用 CalculationService)
    print("正在计算定价...")
    calc_service = CalculationService()
    priced_data = calc_service.calculate_prices(products, strategy_func, strategy_params)
    
    # 3. 导出 (使用 ExportService)
    first_url = urls[0] if urls else ""
    export_service = ExportService()
    out_path = export_service.export_data(priced_data, args.out, first_url)
    print(f"结果已导出至: {out_path}")
    
    # 4. 核对
    report = calc_service.get_quick_report(priced_data)
    print("核对报告:", report)

    duration = time.time() - start
    print(f"总耗时: {duration:.2f} 秒")


if __name__ == "__main__":
    main()
