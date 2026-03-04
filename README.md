# 大盘分析Agent

基于LLM的智能技术分析系统，通过多时间周期的上证指数数据（日线、15分钟线、5分钟线）结合均线数据，由LLM自动识别支撑压力位，并对大盘未来走势进行预期分析。

## 功能特性

- **多周期数据分析**：支持日线（3个月）、15分钟线（1周）、5分钟线（1日）数据
- **LLM驱动分析**：支撑压力位识别、走势预期等核心分析由LLM完成
- **多LLM支持**：默认使用智谱GLM-4，支持OpenAI、DeepSeek、通义千问等
- **时间隔离**：严格防止未来数据泄露，支持盘中分析模式
- **多种输出格式**：JSON、文本、Markdown、K线图表
- **数据源灵活**：支持AKShare实时数据（免费无限制）和本地JSON文件

## 安装

### 环境要求

- Python 3.10+
- pip 或 uv 包管理器

### 安装依赖

```bash
# 使用pip
pip install -e .

# 或使用uv
uv pip install -e .
```

### 依赖列表

- zhipuai - 智谱AI SDK
- openai - OpenAI SDK
- pandas - 数据处理
- matplotlib - 图表绑定
- mplfinance - K线图绑制
- pydantic - 数据验证
- pyyaml - 配置文件解析
- akshare - 股票数据接口（免费，无需API Token）

## 配置

### 1. 创建配置文件

复制示例配置文件并填入你的API密钥：

```bash
cp config.yaml.example config.yaml
```

### 2. 配置LLM

编辑 `config.yaml`，配置LLM提供商和API密钥：

```yaml
llm:
  # 选择提供商: zhipu / openai / deepseek / qwen
  provider: zhipu
  model: glm-4
  api_key: "your-api-key-here"
  
  # 可选配置
  temperature: 0.3
  max_tokens: 4096
```

### 3. 配置AKShare（可选）

AKShare是免费开源的金融数据接口，无需API Token，无频率限制。默认配置即可使用：

```yaml
akshare:
  index_code: "000001"      # 上证指数代码
  index_name: "sh000001"    # 用于日线数据
  daily_days: 65            # 日线数据天数（三个月）
  m15_days: 5               # 15分钟线数据天数（一周）
  m5_days: 1                # 5分钟线数据天数（当日）
```

## 使用方法

### 基本用法

```bash
# 使用AKShare实时数据分析今日行情
python -m src.cli

# 分析指定日期
python -m src.cli --date 2024-01-15

# 盘中模式（指定截止时间）
python -m src.cli --date 2024-01-15 --time 14:30
```

### 使用本地数据文件

```bash
# 使用示例数据文件
python -m src.cli --data-file examples/sample_data.json

# 指定输出格式
python -m src.cli -f examples/sample_data.json --output-format json
```

### 输出格式选项

```bash
# 文本格式（默认）
python -m src.cli --output-format text

# JSON格式
python -m src.cli --output-format json --output report.json

# Markdown格式
python -m src.cli --output-format markdown --output report.md

# K线图表
python -m src.cli --output-format chart --output chart.png

# 所有格式
python -m src.cli --output-format all --output output/report
```

### LLM配置覆盖

```bash
# 使用OpenAI
python -m src.cli --provider openai --model gpt-4 --api-key YOUR_KEY

# 调整生成温度
python -m src.cli --temperature 0.5
```

### 完整参数列表

```bash
python -m src.cli --help
```

| 参数 | 简写 | 说明 |
|------|------|------|
| `--data-file` | `-f` | 本地数据文件路径（JSON格式） |
| `--date` | `-d` | 分析日期（YYYY-MM-DD） |
| `--time` | `-t` | 盘中截止时间（HH:MM:SS） |
| `--config` | `-c` | 配置文件路径，默认 config.yaml |
| `--provider` | `-p` | LLM提供商 |
| `--model` | `-m` | 模型名称 |
| `--api-key` | `-k` | API密钥 |
| `--temperature` | | 生成温度（0-1） |
| `--output-format` | `-F` | 输出格式：json/text/markdown/chart/all |
| `--output` | `-o` | 输出文件路径 |
| `--chart-timeframe` | | 图表时间周期：daily/m15/m5 |
| `--quiet` | `-q` | 静默模式 |

## 数据格式

### JSON输入格式

系统接受以下JSON格式的市场数据：

```json
{
  "analysis_date": "2024-01-15",
  "analysis_time": "14:30:00",
  "daily": {
    "data": [
      {
        "timestamp": "2024-01-15",
        "open": 3000.0,
        "high": 3050.0,
        "low": 2980.0,
        "close": 3020.0,
        "volume": 100000000
      }
    ],
    "ma": [
      {
        "timestamp": "2024-01-15",
        "ma5": 3010.0,
        "ma10": 3000.0,
        "ma20": 2990.0,
        "ma60": 2950.0,
        "ma120": 2900.0
      }
    ]
  },
  "m15": { ... },
  "m5": { ... }
}
```

### 字段说明

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `analysis_date` | string | 是 | 分析截止日期 |
| `analysis_time` | string | 否 | 盘中截止时间 |
| `daily` | object | 是 | 日线数据（三个月） |
| `m15` | object | 是 | 15分钟线数据（一周） |
| `m5` | object | 是 | 5分钟线数据（当日） |

### OHLCV数据字段

| 字段 | 类型 | 说明 |
|------|------|------|
| `timestamp` | string | 时间戳（支持多种格式） |
| `open` | float | 开盘价 |
| `high` | float | 最高价 |
| `low` | float | 最低价 |
| `close` | float | 收盘价 |
| `volume` | float | 成交量 |

### 均线数据字段

| 字段 | 类型 | 说明 |
|------|------|------|
| `timestamp` | string | 时间戳 |
| `ma5` | float | 5日均线（可选） |
| `ma10` | float | 10日均线（可选） |
| `ma20` | float | 20日均线（可选） |
| `ma60` | float | 60日均线（可选） |
| `ma120` | float | 120日均线（可选） |

## 输出示例

### 文本格式输出

```
============================================================
大盘分析报告
============================================================
分析时间：2024-01-15 15:00:00
数据截止：2024-01-15 14:30:00
当前价格：3018.56

----------------------------------------
【支撑压力位】
----------------------------------------
压力位：
  3050.00 - 前期高点（强）
  3030.00 - 15分钟前高（中）
  3025.00 - MA5均线（弱）
支撑位：
  3000.00 - 整数关口+MA20（强）
  2990.00 - 前期低点（中）
  2972.67 - MA20均线（弱）
当日关键压力：3050.00（日线级别前高）
当日关键支撑：3000.00（整数关口+均线支撑）

----------------------------------------
【当前位置分析】
----------------------------------------
位置判断：中间偏支撑
距最近支撑：18.56点（0.62%）
距最近压力：31.44点（1.04%）

----------------------------------------
【短期预期（次日）】
----------------------------------------
场景：震荡修复（概率：60%）
  预期：在3000-3050区间震荡整理
  目标：[3030, 3050]
  止损：[2990, 2980]
操作建议：观望为主，等待方向明确
置信度：medium
风险提示：注意成交量变化

----------------------------------------
【中长期预期】
----------------------------------------
当前趋势：震荡趋势（强度：中）
周线预期：震荡，目标区间[2950, 3100]
月线预期：震荡偏多，目标区间[2900, 3150]
趋势转折信号：
  - 突破3100确认上升趋势（触发位：3100.00）
  - 跌破2900确认下降趋势（触发位：2900.00）
置信度：medium
```

### JSON格式输出

```json
{
  "analysis_time": "2024-01-15T15:00:00",
  "data_cutoff": "2024-01-15 14:30:00",
  "current_price": 3018.56,
  "support_levels": [...],
  "resistance_levels": [...],
  "position_analysis": {...},
  "short_term": {...},
  "long_term": {...}
}
```

## 项目结构

```
.
├── config.yaml              # 配置文件
├── examples/
│   └── sample_data.json     # 示例数据
├── prompts/                 # 提示词模板
│   ├── system.txt           # 系统提示词
│   ├── support_resistance.txt
│   ├── short_term.txt
│   ├── long_term.txt
│   └── examples/            # Few-shot示例
├── src/
│   ├── agent/               # 分析Agent
│   │   └── market_agent.py
│   ├── analysis/            # 分析模块
│   │   ├── calculator.py    # 价格计算
│   │   ├── context_builder.py
│   │   └── prompt_engine.py
│   ├── data/                # 数据处理
│   │   ├── parser.py        # 数据解析
│   │   ├── time_filter.py   # 时间过滤
│   │   └── akshare_source.py # AKShare数据源
│   ├── llm/                 # LLM接口
│   │   ├── base.py          # 抽象接口
│   │   ├── client.py        # 客户端实现
│   │   └── config_loader.py
│   ├── models/              # 数据模型
│   │   ├── market_data.py
│   │   └── analysis_result.py
│   ├── output/              # 输出模块
│   │   ├── report_generator.py
│   │   └── chart_renderer.py
│   └── cli.py               # 命令行入口
└── tests/                   # 测试文件
```

## 开发

### 运行测试

```bash
# 运行所有测试
pytest

# 运行特定测试
pytest tests/test_parser.py

# 运行属性测试
pytest tests/test_calculator_properties.py
```

### 代码风格

项目使用以下工具保持代码质量：

- ruff - 代码检查和格式化
- mypy - 类型检查

```bash
# 代码检查
ruff check src/

# 格式化
ruff format src/
```

## 注意事项

1. **API密钥安全**：请勿将API密钥提交到版本控制系统
2. **数据时间隔离**：系统会自动过滤未来数据，确保分析的准确性
3. **LLM分析质量**：分析结果依赖于LLM的能力和提示词设计
4. **投资风险**：本系统仅供技术分析参考，不构成投资建议

## 许可证

MIT License
