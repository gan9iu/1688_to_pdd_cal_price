# 1688 to PDD 自动定价工具

这是一个用于自动化抓取 1688 商品信息，并根据预设策略计算拼多多（PDD）建议售价的工具。它支持多种定价模式，并提供 Web 界面和命令行两种使用方式。

## ✨ 核心功能

*   **自动化抓取**: 基于 Selenium 的爬虫，支持 1688 商品详情页（SKU、价格、库存、运费）的自动抓取，内置反爬虫对抗机制。
*   **多策略定价**:
    *   **默认策略**: 基于成本、目标毛利率、平台费率自动计算售价。
    *   **限时限量策略**: 基于目标到手价、立减券和折扣率反推拼单价。
*   **多端接入**:
    *   **Web UI**: 基于 Streamlit 的可视化界面，操作简单，支持实时预览和 Excel 下载。
    *   **CLI**: 高效的命令行工具，适合批量处理和脚本集成。
    *   **API Server**: [新增] 专为飞书机器人/外部系统设计的 FastAPI 接口服务，支持“1688规格”和“类目”字段抓取。
*   **专业导出**: 生成格式化的 Excel 报表，包含商品链接跳转和详细的 SKU 定价信息。

## 📂 项目结构与文件职责

```text
1688_to_pdd_cal_price/
├── web_app.py              # [Web入口] Streamlit 应用主程序。负责 UI 展示、参数接收，调用 Service 层处理业务。
├── cli_app.py              # [CLI入口] 命令行工具主程序。负责解析命令行参数，调用 Service 层处理业务。
├── api_server.py           # [★API入口] 新增：飞书专用入口 (FastAPI)，提供 RESTful API 供机器人调用。
├── requirements.txt        # [依赖文件] 项目运行所需的 Python 库列表。
├── README.md               # [项目文档] 项目说明书。
├── urls.txt                # [示例输入] 存放待抓取商品链接的文本文件。
├── src/                    # [源码目录]
│   ├── __init__.py
│   ├── models.py           # [数据模型] 定义 Product 和 SKU 的数据结构 (Dataclass)，确保数据流转的规范性。
│   ├── service.py          # [业务服务] 核心业务逻辑层。封装了"抓取->计算->导出"的完整流程，供 Web 和 CLI 调用。
│   ├── crawler.py          # [爬虫模块] 封装 Selenium 操作。负责浏览器启动、页面加载、元素定位和数据解析。
│   ├── exporter.py         # [导出模块] 负责将计算结果写入 Excel 文件，并应用格式样式。
│   └── pricing/            # [定价模块]
│       ├── __init__.py
│       ├── engine.py       # [计算引擎] 负责批量处理 SKU 列表，调度具体的定价策略函数。
│       └── strategies/     # [策略集合]
│           ├── __init__.py
│           ├── default.py  # [默认策略] 实现基于成本加成的定价公式。
│           └── limited.py  # [限时策略] 实现基于活动倒推的定价公式。
└── tests/                  # [测试目录]
    ├── test_default_strategy.py  # 测试默认定价逻辑的正确性。
    └── test_limited_strategy.py  # 测试限时限量定价逻辑的正确性。
```

## 🚀 快速开始

### 1. 安装依赖

确保已安装 Python 3.8+，然后运行：

```bash
pip install -r requirements.txt
```

*注意：你需要安装 Firefox 浏览器，脚本会自动管理 geckodriver 驱动。*

### 2. 运行 Web 应用 (推荐)

启动可视化界面：

```bash
streamlit run web_app.py
```

在浏览器中打开显示的地址（通常是 `http://localhost:8501`），即可在侧边栏配置参数，输入链接并开始抓取。

### 3. 运行命令行工具

如果你有 `urls.txt` 文件（每行一个链接），可以使用 CLI 模式：

```bash
# 使用默认策略
python cli_app.py --input urls.txt --out result.xlsx

# 使用限时限量策略
python cli_app.py --input urls.txt --strategy limited --instant-coupon 5 --discount 0.9
```

### 4. 运行 API 服务 (Feishu 集成)

启动 FastAPI 服务，主要用于对接飞书机器人或其他外部系统。

```bash
python api_server.py
# 服务默认运行在 http://0.0.0.0:8000
```

**接口说明**:
*   `POST /feishu_fetch`: 接收 `{"url": "..."}` JSON，返回抓取的成本、运费、类目和规格信息。

## 🧮 定价策略说明

### 1. 默认毛利定价 (Default)
适用于日常销售定价。
*   **公式**: `建议售价 = (基础成本 + 运费 + 额外加价) / ((1 - 平台费率) * (1 - 目标毛利率))`
*   **参数**: 成本、运费、平台费率(如 0.06)、目标毛利率(如 0.20)。

### 2. 限时限量活动定价 (Limited)
适用于参加平台活动时的反向定价。
*   **公式**: `最终拼单价 = (目标到手价 + 立减券金额 + 1) / 限时折扣率`
*   **参数**: 目标到手价(卖价)、立减券金额、限时折扣(0.5-1.0)。
