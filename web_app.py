"""
Streamlit Web 应用程序入口。
负责 UI 渲染和用户交互，调用底层服务进行业务处理。
"""
import os
import pandas as pd
import streamlit as st
from typing import Dict, Any, Tuple, Optional, Callable

from src.pricing.strategies.default import calculate_price
from src.pricing.strategies.limited import limited_time_strategy_adapter
from src.service import CrawlerService, CalculationService, ExportService, ImportService

# ==========================================
# UI 辅助函数
# ==========================================

def init_session_state():
    """初始化 Session State 变量。"""
    if 'products' not in st.session_state:
        st.session_state.products = []
    if 'priced_data' not in st.session_state:
        st.session_state.priced_data = []
    if 'first_url' not in st.session_state:
        st.session_state.first_url = ""


def render_sidebar() -> Dict[str, Any]:
    """渲染侧边栏并返回配置字典。"""
    config = {}
    with st.sidebar:
        st.header("⚙️ 全局设置")
        config["headless"] = st.checkbox(
            "无头模式 (后台运行)",
            value=False, # 默认关闭无头模式，以便默认启用 Profile 加载
            help="勾选后浏览器将在后台运行，速度更快但无法看到操作过程。"
        )
        config["use_profile"] = st.checkbox(
            "🦊 加载本机 Firefox 配置 (推荐)",
            value=True, # 默认勾选
            help="包含登录状态和历史记录，可轻松绕过反爬虫。需先关闭所有 Firefox 窗口！"
        )
        
        st.markdown("---")
        st.header("🧮 定价参数配置")
        
        strategy = st.selectbox(
            "选择定价策略",
            ("default", "limited", "roi", "equilibrium"),
            format_func=lambda x: {
                "default": "默认毛利定价",
                "limited": "限时限量活动定价",
                "roi": "最佳投产比计算 (广告投放)",
                "equilibrium": "智能平衡定价 (ROI反推)"
            }[x]
        )
        
        strategy_params = {}
        strategy_func = None

        if strategy == "default":
            st.caption("📝 基于成本、运费和目标毛利率计算建议售价。")
            # 基础输入
            cost_input = st.number_input("基础成本 (若抓取不到价格时使用)", value=0.0, step=1.0)
            shipping_input = st.number_input("快递运费 (0表示使用抓取值)", value=0.0, step=1.0)
            
            # 统一成本参数
            platform_fee = st.number_input("平台费率 (例如 0.006)", value=0.006, step=0.001, format="%.3f")
            refund_rate = st.number_input("预计退款率 (用于计算损耗)", value=0.20, step=0.05, max_value=1.0)
            target_margin = st.number_input("目标毛利率 (例如 0.20)", value=0.20, step=0.01)
            
            extra_markup = st.number_input("额外固定加价 (元)", value=0.0, step=0.5, help="在计算结果基础上额外增加的金额")
            
            # 额外保险费(默认为0.8，这里没开放输入，暂时hardcode或复用)
            insurance = 0.8 

            strategy_params = {
                "cost": cost_input, # 需要 default.py 支持
                "shipping": shipping_input,
                "platform_fee_pct": platform_fee,
                "refund_rate": refund_rate,        # New
                "target_margin_pct": target_margin,
                "extra_markup": extra_markup,
                "shipping_insurance": insurance
            }
            strategy_func = lambda item, **kwargs: calculate_price(item, **kwargs)

        elif strategy == "limited":
            st.caption("⚡ 基于 [成本+利润]、立减券和限时折扣计算拼单价。")
            shipping_input = st.number_input("快递运费 (0表示使用抓取值)", value=0.0, step=1.0, key="ship_limit")
            target_margin = st.number_input("基础利润率 (加价率, 例如 0.2=20%)", value=0.20, step=0.01, format="%.2f", key="margin_limit")
            
            st.caption("--- 营销参数 ---")
            instant_coupon = st.number_input("立减券金额 (元)", value=5.0, step=1.0)
            discount = st.number_input("限时折扣 (0.5 - 1.0)", value=0.5, step=0.05, min_value=0.5, max_value=1.0)

            # 统一成本参数
            st.caption("--- 成本修正 ---")
            platform_fee_lim = st.number_input("平台费率 (例如 0.006)", value=0.006, step=0.001, format="%.3f", key="lim_fee")
            refund_rate_lim = st.number_input("预计退款率", value=0.20, step=0.05, max_value=1.0, key="lim_refund")

            strategy_params = {
                "shipping": shipping_input,
                "target_margin": target_margin,
                "instant_discount_coupon_price": instant_coupon,
                "limited_time_discount": discount,
                "platform_fee_pct": platform_fee_lim,
                "refund_rate": refund_rate_lim
            }
            strategy_func = limited_time_strategy_adapter

        elif strategy == "roi":
            # ... (roi inputs) ...
            from src.pricing.strategies.roi import calculate_roi
            st.caption("📈 计算保本、净投产和最佳投产比。需有【实际成交价】。")
            
            shipping_input = st.number_input("快递运费 (包裹+快递费)", value=0.0, step=1.0, key="ship_roi")
            insurance = st.number_input("运费险 (元)", value=0.8, step=0.1)
            refund_rate = st.number_input("退款率 (0.0 - 1.0)", value=0.20, step=0.05, max_value=1.0)
            
            st.markdown("---")
            fixed_price = st.number_input(
                "预设实际成交价 (元)", 
                value=0.0, 
                step=1.0, 
                help="优先级高于自动计算，但低于表格中的单独设置。"
            )
            target_margin = st.number_input(
                "基础毛利率 (用于自动计算计划卖价)", 
                value=0.20, 
                step=0.01, 
                format="%.2f",
                help="当实际成交价为0时，将使用 [总成本 / (1-毛利率)] 自动计算一个初始卖价。"
            )
            platform_fee_roi = st.number_input(
                "平台扣点费率 (ROI)", 
                value=0.006, 
                step=0.001, 
                format="%.3f",
                help="通常为 0.6% (0.006)。计算毛利时会自动扣除。"
            )

            strategy_params = {
                "shipping": shipping_input,
                "shipping_insurance": insurance,
                "refund_rate": refund_rate,
                "fixed_selling_price": fixed_price,
                "target_margin_pct": target_margin,
                "platform_fee": platform_fee_roi
            }
            strategy_func = calculate_roi
            
        elif strategy == "equilibrium":
            from src.pricing.strategies.equilibrium import calculate_equilibrium_price
            st.caption("⚖️ 设定预期 ROI，自动反推不亏本的售价。")
            
            shipping_input = st.number_input("快递运费 (包裹+快递费)", value=0.0, step=1.0, key="ship_eq")
            insurance = st.number_input("运费险 (元)", value=0.8, step=0.1, key="ins_eq")
            platform_fee = st.number_input("平台费率 (例如 0.006)", value=0.006, step=0.001, format="%.3f", key="fee_eq")
            refund_rate = st.number_input("退款率 (0.0 - 1.0)", value=0.20, step=0.05, max_value=1.0, key="ref_eq")
            
            st.markdown("---")
            expected_roi = st.number_input("预期广告 ROI (例如 3.0)", value=3.0, step=0.1)
            target_profit = st.number_input("目标单单毛利 (元)", value=2.0, step=0.5)
            
            strategy_params = {
                "shipping": shipping_input,
                "shipping_insurance": insurance,
                "platform_fee_pct": platform_fee,
                "refund_rate": refund_rate, # New
                "expected_roi": expected_roi,
                "target_profit": target_profit
            }
            strategy_func = calculate_equilibrium_price

        config["strategy_func"] = strategy_func
        config["strategy_params"] = strategy_params

        # === 实时计算 (Auto-Calc) ===
        # 只要侧边栏参数变化，且内存中有商品数据，就立即重算
        if st.session_state.products:
            calc_service = CalculationService()
            st.session_state.priced_data = calc_service.calculate_prices(
                st.session_state.products, strategy_func, strategy_params
            )
            
        st.markdown("---")
        if st.button("🗑️ 重置所有卖价 (强制重算)", help="点击此按钮将清除表格中现有的【计划卖价】，强制系统根据最新的运费和毛利率设定重新计算所有价格。", type="secondary"):
            for p in st.session_state.products:
                for s in p.skus:
                    s.selling_price = 0.0
                    s.extra_data["selling_price"] = 0.0
            st.toast("已重置所有价格！系统将按新成本重新计算。")
            st.rerun()
    
    return config


def render_fetch_area(config: Dict[str, Any]):
    """渲染数据抓取区域。"""
    st.subheader("1. 获取商品数据")
    
    tab1, tab2 = st.tabs(["📝 输入链接抓取", "📂 上传文件 (抓取/导入)"])
    with tab1:
        urls_text = st.text_area(
            "请输入 1688 商品链接 (每行一个)",
            height=150,
            placeholder="https://detail.1688.com/offer/...\n...",
            key="url_input_area"
        )
    with tab2:
        uploaded_file = st.file_uploader(
            "支持上传：\n1. 包含链接的文件 (用于抓取)\n2. 包含商品数据的 Excel (直接计算)", 
            type=['txt', 'xlsx']
        )

    col_act1, col_act2 = st.columns([1, 4])
    with col_act1:
        start_fetch_btn = st.button("🚀 开始抓取 / 导入", type="primary", use_container_width=True)
    with col_act2:
        auto_calc = st.checkbox("抓取完成后自动计算定价", value=True)

    if start_fetch_btn:
        _handle_fetch(urls_text, uploaded_file, config, auto_calc)
    elif not st.session_state.products:
        st.info("👈 请在上方输入链接并点击“开始抓取”。")


def _handle_fetch(urls_text, uploaded_file, config, auto_calc):
    """处理抓取或导入逻辑。"""
    
    # 1. 尝试从 Excel 直接导入完整数据
    if uploaded_file and uploaded_file.name.endswith('.xlsx'):
        try:
            # 使用 ImportService 进行导入
            import_service = ImportService()
            file_content = uploaded_file.getvalue()
            imported_products = import_service.import_from_excel(file_content)
            
            if imported_products:
                st.success(f"📂 成功从 Excel 导入 {len(imported_products)} 个商品数据，已跳过抓取步骤。")
                st.session_state.products = imported_products
                st.session_state.first_url = imported_products[0].url if imported_products else ""
                st.session_state.import_filename = uploaded_file.name
                
                # 自动计算
                if auto_calc:
                    calc_service = CalculationService()
                    st.session_state.priced_data = calc_service.calculate_prices(
                        st.session_state.products, config["strategy_func"], config["strategy_params"]
                    )
                else:
                    st.session_state.priced_data = []
                return
        except Exception as e:
            st.warning(f"尝试导入 Excel 数据失败，将尝试提取链接进行抓取: {e}")

    # 2. 提取 URL 进行抓取 (原有逻辑)
    urls = []
    if urls_text:
        urls.extend([u.strip() for u in urls_text.split('\n') if u.strip()])
    
    if uploaded_file:
        try:
            if uploaded_file.name.endswith('.txt'):
                from io import StringIO
                stringio = StringIO(uploaded_file.getvalue().decode("utf-8"))
                urls.extend([l.strip() for l in stringio if l.strip()])
            elif uploaded_file.name.endswith('.xlsx'):
                # 如果前面的导入失败了，这里只提取第一列的 URL
                df = pd.read_excel(uploaded_file)
                if not df.empty:
                    # 假设 URL 在第一列，或者寻找名为 '链接'/'url' 的列
                    url_col = None
                    for col in df.columns:
                        if str(col).lower() in ['url', 'link', '链接', '商品链接']:
                            url_col = col
                            break
                    
                    if url_col:
                        urls.extend([str(u).strip() for u in df[url_col] if str(u).strip().startswith('http')])
                    else:
                        # 兜底：使用第一列
                        first_col = df.iloc[:, 0].astype(str)
                        urls.extend([u.strip() for u in first_col if u.strip().startswith('http')])
        except Exception as e:
            st.error(f"读取文件失败: {e}")
            return

    urls = list(dict.fromkeys(urls)) # 去重

    if not urls:
        st.warning("⚠️ 未识别到有效的商品数据或链接。请上传包含数据的 Excel 或输入链接。")
        return

    st.session_state.first_url = urls[0]
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    try:
        status_text.info("正在启动浏览器...")
        status_text.info("正在启动浏览器...")
        with CrawlerService(
            headless=config["headless"],
            use_firefox_profile=config.get("use_profile", False)
        ) as crawler:
            def update_progress(i, total, url):
                status_text.info(f"正在抓取 ({i+1}/{total}): {url}")
                progress_bar.progress((i + 1) / total)
            
            st.session_state.products = crawler.fetch_products(urls, progress_callback=update_progress)
            
            if not st.session_state.products:
                st.error("未能抓取到任何有效数据。")
            else:
                status_text.success(f"✅ 成功抓取 {len(st.session_state.products)} 个商品！")
                if auto_calc:
                    calc_service = CalculationService()
                    st.session_state.priced_data = calc_service.calculate_prices(
                        st.session_state.products, config["strategy_func"], config["strategy_params"]
                    )
                else:
                    st.session_state.priced_data = []
    except Exception as e:
        st.error(f"发生错误: {e}")


def render_results_area(config: Dict[str, Any]):
    """渲染结果展示与导出区域。"""
    if not st.session_state.products:
        return

    st.markdown("---")
    st.subheader("2. 定价计算与导出")
    
    # 顶部：导出与统计
    if st.session_state.priced_data:
        export_service = ExportService()
        
        # 获取当前策略名称
        current_strategy = "default"
        if config.get("strategy_func") == limited_time_strategy_adapter:
            current_strategy = "limited"
        elif "equilibrium" in str(config.get("strategy_func")):
            current_strategy = "equilibrium"
        elif "roi" in str(config.get("strategy_func")):
            current_strategy = "roi"
            
        # 获取导入文件名 (如果存在)
        import_filename = st.session_state.get("import_filename", "")

        excel_bytes, file_name = export_service.get_excel_bytes(
            st.session_state.priced_data, 
            st.session_state.first_url,
            base_name=import_filename,
            strategy_name=current_strategy
        )
        
        col_dl, col_recalc, col_info = st.columns([1, 1, 2])
        with col_dl:
            st.download_button(
                label="📥 下载 Excel 报表",
                data=excel_bytes,
                file_name=file_name,
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                type="primary",
                use_container_width=True
            )
        with col_recalc:
            if st.button("🔄 仅重新计算 (不保存表格)", use_container_width=True):
                _recalculate(config)
        with col_info:
            calc_service = CalculationService()
            report = calc_service.get_quick_report(st.session_state.priced_data)
            st.caption(f"📊 统计: 总SKU {report['总SKU数']} | 异常 {report['建议售价为0的SKU数']}")

    st.markdown("---")
    
    # --- 视图切换 ---
    # tab_view, tab_edit = st.tabs(["👀 分组预览", "✏️ 全局表格编辑 (实时运算)"])
    
    # === 自动填充优化 ===
    # (已移除: 策略层已返回正确的 selling_price，无需前端覆盖)
            
    df_all = pd.DataFrame(st.session_state.priced_data)
    
    # 动态调整列名
    price_label = "建议售价"
    if current_strategy == "limited":
        price_label = "☁️ 限时限量购价格"
    elif current_strategy == "equilibrium":
        price_label = "⚖️ 智能平衡建议价"
    elif current_strategy == "default":
        price_label = "💰 默认毛利建议价"

    # 定义列展示配置 (共用)
    column_config = {
        "price": st.column_config.NumberColumn("原价/成本", format="%.2f", min_value=0.0),
        "selling_price": st.column_config.NumberColumn(
            "★计划卖价 (含利润)", 
            format="%.2f", 
            min_value=0.0, 
            step=0.5, 
            help="即您计划在 PDD 填写的初始标价（即基础含利成本）。此价格通过折扣计算得出最终建议价。"
        ),
        "stock": st.column_config.NumberColumn("库存", format="%d"),
        
        "raw_calculated_price": st.column_config.NumberColumn("🧮 原始计算价 (未取整)", format="%.2f", help="应用心理学定价之前的精确计算值"),
        "suggested_price": st.column_config.NumberColumn(price_label, format="%.2f"), # 动态列名
        "breakeven_price": st.column_config.NumberColumn("🛡️ 保本底价", format="%.2f"),
        "ad_cost_limit": st.column_config.NumberColumn("📢 广告费上限", format="%.2f"),
        "profit_per_order": st.column_config.NumberColumn("💰 预计利润/单", format="%.2f", help="实际成交价 - 总成本"),
        
        "overall_shipping_cost": st.column_config.NumberColumn("运费", format="%.2f", min_value=0.0),
        "breakeven_roi": st.column_config.NumberColumn("保本投产", format="%.2f"),
        "net_roi": st.column_config.NumberColumn("净投产", format="%.2f"),
        "best_roi": st.column_config.NumberColumn("★最佳投产比", format="%.2f"),
        "product_url": st.column_config.TextColumn("商品链接", disabled=True),
        "name": "SKU名称"
    }
    
    rename_map = {
        "name": "SKU名称",
        "stock": "库存",
        "error": "错误信息"
    }

    # === Tab 1: 分组预览 (只读) ===
    if False: # with tab_view:
        if "product_url" in df_all.columns:
            grouped = df_all.groupby("product_url", sort=False)
            for url, group_df in grouped:
                first_row = group_df.iloc[0]
                title = first_row.get("product_title_main", "未知商品标题")
                shipping = first_row.get("overall_shipping_cost", 0.0)
                
                st.markdown(f"### 🛍️ {title}")
                st.markdown(f"**🚚 运费:** `{shipping} 元`")
                
                # --- 投放指南注解 (仅在 ROI 策略下显示) ---
                if current_strategy == "roi":
                    st.info(
                        """
                        **💡 投放数值怎么填？**
                        * **保本投产 (底线)**：实际投放 ROI **必须大于** 此值，否则亏本。
                        * **★最佳投产比 (建议)**：推荐填入广告后台的目标值。
                            * 想要 **更高利润**？设得 **比计算值大** (单量可能变少)。
                            * 想要 **更多单量**？设得 **比计算值小** (利润会变薄，但跑得快)。
                        """
                    )
                
                # 核心展示列 (自动包含存在的列)
                # 将 原始计算价 插入到 建议售价 之前
                base_cols = ["name", "price", "selling_price", "raw_calculated_price", "suggested_price"]
                extra_cols = ["breakeven_price", "ad_cost_limit", "breakeven_roi", "net_roi", "best_roi", "error"]
                
                cols = [c for c in base_cols + extra_cols if c in group_df.columns]
                
                st.dataframe(
                    group_df[cols].rename(columns=rename_map),
                    column_config=column_config,
                    use_container_width=True,
                    hide_index=True
                )
                st.markdown("---")
        else:
            st.dataframe(df_all)

    # === Tab 2: 全局表格编辑 ===
    if True: # with tab_edit:
        st.info("💡 提示：在表格中直接修改【实际成交价】、【原价】或【运费】，然后点击下方按钮，即可按新数据重新计算指标。")
        
        # 准备编辑用的 DataFrame
        # 将 product_url 设为索引并隐藏，以节省空间但保留Key信息
        if "product_url" in df_all.columns:
            df_display = df_all.set_index("product_url")
        else:
            df_display = df_all

        # 必须列: name
        # 可编辑列: selling_price, price, overall_shipping_cost
        edit_cols = [
            "name", "price", "selling_price", 
            "overall_shipping_cost"
        ]
        # 添加计算结果列供参考 (只读)
        result_cols = ["profit_per_order", "breakeven_roi", "net_roi", "best_roi", "breakeven_price", "suggested_price", "raw_calculated_price"]
        
        # 确保列存在
        final_cols = [c for c in edit_cols + result_cols if c in df_display.columns]
        
        # 特殊处理：ROI 模式下隐藏“建议售价”列（因为它等于计划卖价，容易混淆）
        if current_strategy == "roi" and "suggested_price" in final_cols:
            final_cols.remove("suggested_price")
        
        edited_df = st.data_editor(
            df_display[final_cols],
            column_config=column_config,
            disabled=["name"] + result_cols, # 禁止编辑非输入项
            use_container_width=True,
            hide_index=True,
            key="global_editor"
        )
        
        if st.button("🔄 保存修改并重新计算", type="primary"):
            _sync_and_recalculate(edited_df, config)


def _recalculate(config):
    """仅执行计算，不涉及数据回写。"""
    calc_service = CalculationService()
    st.session_state.priced_data = calc_service.calculate_prices(
        st.session_state.products, config["strategy_func"], config["strategy_params"]
    )
    st.toast("定价已更新！")


def _sync_and_recalculate(edited_df: pd.DataFrame, config: Dict[str, Any]):
    """将编辑后的数据回写到内存对象，并重新计算。"""
    if edited_df.empty:
        return
        
    # 调用 Service 层进行数据回写 (解耦 UI 与 数据逻辑)
    calc_service = CalculationService()
    count = calc_service.sync_dataframe_to_products(st.session_state.products, edited_df)
            
    st.toast(f"已更新 {count} 条数据，正在重新计算...")
    
    # 重新计算
    _recalculate(config)
    
    # 强制刷新页面以更新表格显示
    st.rerun()


# ==========================================
# 主程序
# ==========================================

def main():
    st.set_page_config(page_title="1688 -> PDD 定价工具", page_icon="💰", layout="wide")
    init_session_state()
    
    st.title("💰 1688 -> PDD 自动定价工具")
    st.markdown("---")

    config = render_sidebar()
    render_fetch_area(config)
    render_results_area(config)


if __name__ == "__main__":
    main()
