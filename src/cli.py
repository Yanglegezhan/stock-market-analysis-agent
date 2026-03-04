"""命令行接口

大盘分析Agent的CLI入口，支持：
- 指定数据文件或使用AKShare实时数据
- 指定分析日期和时间
- 配置LLM参数
- 选择输出格式（JSON/文本/图表/Markdown）

Requirements: 全部
"""

import argparse
import sys
from datetime import datetime, date
from pathlib import Path
from typing import Optional

from src.agent.market_agent import MarketAnalysisAgent, AgentConfig, AnalysisResult
from src.data.parser import DataParser, ParseResult
from src.data.akshare_source import AKShareDataSource, AKShareConfig
from src.llm.base import LLMConfig
from src.llm.config_loader import load_config
from src.models.market_data import AnalysisInput
from src.output.report_generator import ReportGenerator
from src.output.chart_renderer import ChartRenderer


def parse_date(date_str: str) -> date:
    """解析日期字符串
    
    支持格式：YYYY-MM-DD, YYYYMMDD
    """
    for fmt in ["%Y-%m-%d", "%Y%m%d"]:
        try:
            return datetime.strptime(date_str, fmt).date()
        except ValueError:
            continue
    raise argparse.ArgumentTypeError(f"无效的日期格式: {date_str}，请使用 YYYY-MM-DD 或 YYYYMMDD")


def parse_time(time_str: str) -> str:
    """解析时间字符串
    
    支持格式：HH:MM:SS, HH:MM, HHMM
    """
    for fmt in ["%H:%M:%S", "%H:%M", "%H%M"]:
        try:
            dt = datetime.strptime(time_str, fmt)
            return dt.strftime("%H:%M:%S")
        except ValueError:
            continue
    raise argparse.ArgumentTypeError(f"无效的时间格式: {time_str}，请使用 HH:MM:SS 或 HH:MM")


def create_parser() -> argparse.ArgumentParser:
    """创建命令行参数解析器"""
    parser = argparse.ArgumentParser(
        prog="market-agent",
        description="大盘分析Agent - 基于LLM的智能技术分析系统",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 使用AKShare实时数据分析今日行情
  python -m src.cli

  # 分析指定日期
  python -m src.cli --date 2024-01-15

  # 盘中模式（指定截止时间）
  python -m src.cli --date 2024-01-15 --time 14:30

  # 使用本地JSON数据文件
  python -m src.cli --data-file examples/sample_data.json

  # 输出Markdown格式报告
  python -m src.cli --output-format markdown --output report.md

  # 生成K线图
  python -m src.cli --output-format chart --output chart.png

  # 使用自定义LLM配置
  python -m src.cli --provider openai --model gpt-4 --api-key YOUR_KEY
        """
    )
    
    # 数据源选项
    data_group = parser.add_argument_group("数据源选项")
    data_group.add_argument(
        "--data-file", "-f",
        type=str,
        help="本地数据文件路径（JSON格式），不指定则使用AKShare实时数据"
    )
    data_group.add_argument(
        "--date", "-d",
        type=parse_date,
        default=None,
        help="分析日期（YYYY-MM-DD），默认为今日"
    )
    data_group.add_argument(
        "--time", "-t",
        type=parse_time,
        default=None,
        help="盘中截止时间（HH:MM:SS），用于盘中分析模式"
    )
    data_group.add_argument(
        "--config", "-c",
        type=str,
        default="config.yaml",
        help="配置文件路径，默认为 config.yaml"
    )
    
    # LLM选项
    llm_group = parser.add_argument_group("LLM选项")
    llm_group.add_argument(
        "--provider", "-p",
        type=str,
        choices=["zhipu", "openai", "deepseek", "qwen"],
        help="LLM提供商，覆盖配置文件设置"
    )
    llm_group.add_argument(
        "--model", "-m",
        type=str,
        help="模型名称，覆盖配置文件设置"
    )
    llm_group.add_argument(
        "--api-key", "-k",
        type=str,
        help="API密钥，覆盖配置文件设置"
    )
    llm_group.add_argument(
        "--temperature",
        type=float,
        help="生成温度（0-1），覆盖配置文件设置"
    )
    
    # 输出选项
    output_group = parser.add_argument_group("输出选项")
    output_group.add_argument(
        "--output-format", "-F",
        type=str,
        choices=["json", "text", "markdown", "chart", "pdf", "all"],
        default="text",
        help="输出格式：json/text/markdown/chart/pdf/all，默认为 text"
    )
    output_group.add_argument(
        "--output", "-o",
        type=str,
        help="输出文件路径，不指定则输出到标准输出（chart格式除外）"
    )
    output_group.add_argument(
        "--chart-timeframe",
        type=str,
        choices=["daily", "m15", "m5"],
        default="daily",
        help="图表使用的时间周期，默认为 daily"
    )
    output_group.add_argument(
        "--quiet", "-q",
        action="store_true",
        help="静默模式，只输出结果"
    )
    
    return parser


def load_llm_config(args: argparse.Namespace) -> LLMConfig:
    """加载LLM配置
    
    优先级：命令行参数 > 配置文件 > 默认值
    """
    # 从配置文件加载基础配置
    try:
        config = load_config(args.config)
    except ValueError as e:
        # 如果配置文件中没有API密钥，检查命令行参数
        if args.api_key:
            config = LLMConfig(
                api_key=args.api_key,
                provider=args.provider or "zhipu",
                model=args.model or "glm-4",
            )
        else:
            raise e
    
    # 命令行参数覆盖
    if args.provider:
        config.provider = args.provider
    if args.model:
        config.model = args.model
    if args.api_key:
        config.api_key = args.api_key
    if args.temperature is not None:
        config.temperature = args.temperature
    
    return config


def load_data_from_file(file_path: str) -> AnalysisInput:
    """从本地文件加载数据"""
    parser = DataParser()
    result = parser.parse_json_file(file_path)
    
    if not result.success:
        error_msgs = result.get_error_messages()
        raise ValueError(f"数据文件解析失败:\n" + "\n".join(error_msgs))
    
    return result.data


def load_data_from_akshare(
    config_path: str,
    analysis_date: Optional[date],
    analysis_time: Optional[str]
) -> AnalysisInput:
    """从AKShare加载实时数据"""
    try:
        akshare_config = AKShareConfig.from_yaml(config_path)
    except FileNotFoundError:
        # AKShare不需要配置文件，使用默认配置
        akshare_config = AKShareConfig()
    except Exception as e:
        raise ValueError(f"加载AKShare配置失败: {e}")
    
    source = AKShareDataSource(akshare_config)
    
    # 使用今日日期作为默认值
    if analysis_date is None:
        analysis_date = date.today()
    
    return source.get_all_data(analysis_date, analysis_time)


def output_result(
    result: AnalysisResult,
    input_data: AnalysisInput,
    args: argparse.Namespace
) -> None:
    """输出分析结果"""
    if not result.success:
        print("分析失败:", file=sys.stderr)
        for error in result.errors or []:
            print(f"  [{error.stage}] {error.message}", file=sys.stderr)
            if error.details:
                print(f"    详情: {error.details}", file=sys.stderr)
        sys.exit(1)
    
    report = result.report
    generator = ReportGenerator()
    
    # 输出警告信息
    if result.warnings and not args.quiet:
        print("警告:", file=sys.stderr)
        for warning in result.warnings:
            print(f"  - {warning.message}", file=sys.stderr)
        print(file=sys.stderr)
    
    output_format = args.output_format
    output_path = args.output
    
    # 处理 all 格式
    if output_format == "all":
        base_path = output_path or "output/report"
        base_dir = Path(base_path).parent
        base_name = Path(base_path).stem
        base_dir.mkdir(parents=True, exist_ok=True)
        
        # 输出所有格式
        json_path = base_dir / f"{base_name}.json"
        text_path = base_dir / f"{base_name}.txt"
        md_path = base_dir / f"{base_name}.md"
        chart_path = base_dir / f"{base_name}.png"
        pdf_path = base_dir / f"{base_name}.pdf"
        
        # JSON
        json_content = generator.generate_json(report)
        json_path.write_text(json_content, encoding="utf-8")
        
        # 文本
        text_content = generator.generate_text(report)
        text_path.write_text(text_content, encoding="utf-8")
        
        # 图表（先生成图表，再生成Markdown以便嵌入图片）
        _render_chart(input_data, report, str(chart_path), args)
        
        # Markdown（包含图片引用）
        md_content = generator.generate_markdown(report)
        # 在Markdown末尾添加图片
        chart_filename = chart_path.name
        md_content += f"\n\n---\n\n## 📈 K线图\n\n![多周期K线图]({chart_filename})\n"
        md_path.write_text(md_content, encoding="utf-8")
        
        # PDF（包含图片）
        _generate_pdf(md_content, str(pdf_path), str(chart_path))
        
        if not args.quiet:
            print(f"已生成报告文件:")
            print(f"  JSON: {json_path}")
            print(f"  文本: {text_path}")
            print(f"  Markdown: {md_path}")
            print(f"  图表: {chart_path}")
            print(f"  PDF: {pdf_path}")
        return
    
    # 单一格式输出
    if output_format == "json":
        content = generator.generate_json(report)
    elif output_format == "text":
        content = generator.generate_text(report)
    elif output_format == "markdown":
        content = generator.generate_markdown(report)
    elif output_format == "chart":
        if not output_path:
            output_path = "output/chart.png"
        _render_chart(input_data, report, output_path, args)
        if not args.quiet:
            print(f"图表已保存到: {output_path}")
        return
    elif output_format == "pdf":
        if not output_path:
            output_path = "output/report.pdf"
        # 先生成图表
        chart_path = str(Path(output_path).parent / f"{Path(output_path).stem}_chart.png")
        _render_chart(input_data, report, chart_path, args)
        # 生成Markdown内容
        md_content = generator.generate_markdown(report)
        md_content += f"\n\n---\n\n## 📈 K线图\n\n![多周期K线图]({Path(chart_path).name})\n"
        # 生成PDF
        _generate_pdf(md_content, output_path, chart_path)
        if not args.quiet:
            print(f"PDF报告已保存到: {output_path}")
            print(f"图表已保存到: {chart_path}")
        return
    else:
        content = generator.generate_text(report)
    
    # 输出到文件或标准输出
    if output_path:
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        if not args.quiet:
            print(f"报告已保存到: {output_path}")
    else:
        print(content)


def _render_chart(
    input_data: AnalysisInput,
    report,
    output_path: str,
    args: argparse.Namespace
) -> None:
    """渲染K线图（多周期）"""
    renderer = ChartRenderer()
    
    # 获取支撑压力位
    levels = (
        report.support_resistance.support_levels +
        report.support_resistance.resistance_levels
    )
    
    # 获取关键位
    key_support = None
    key_resistance = None
    if report.support_resistance.key_support_today:
        key_support = report.support_resistance.key_support_today.price
    if report.support_resistance.key_resistance_today:
        key_resistance = report.support_resistance.key_resistance_today.price
    
    # 确保输出目录存在
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    
    # 渲染多周期图表（日线+15分钟+5分钟）
    renderer.render_multi_timeframe(
        daily_data=input_data.daily_data,
        m15_data=input_data.m15_data,
        m5_data=input_data.m5_data,
        levels=levels,
        output_path=output_path,
        key_support=key_support,
        key_resistance=key_resistance,
        title=f"上证指数多周期分析 - {report.data_cutoff}",
    )


def _generate_pdf(md_content: str, output_path: str, chart_path: str) -> None:
    """将Markdown内容转换为PDF
    
    Args:
        md_content: Markdown内容
        output_path: PDF输出路径
        chart_path: 图表文件路径
    """
    # 确保输出目录存在
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    
    try:
        from fpdf import FPDF
        from fpdf.enums import XPos, YPos
        import re
        
        # 移除emoji符号（中文字体不支持）
        def remove_emoji(text: str) -> str:
            emoji_pattern = re.compile(
                "["
                "\U0001F600-\U0001F64F"  # emoticons
                "\U0001F300-\U0001F5FF"  # symbols & pictographs
                "\U0001F680-\U0001F6FF"  # transport & map symbols
                "\U0001F1E0-\U0001F1FF"  # flags
                "\U00002702-\U000027B0"
                "\U000024C2-\U0001F251"
                "\U0001f926-\U0001f937"
                "\U00010000-\U0010ffff"
                "\u2640-\u2642"
                "\u2600-\u2B55"
                "\u200d"
                "\u23cf"
                "\u23e9"
                "\u231a"
                "\ufe0f"
                "\u3030"
                "\u2022"  # bullet point
                "]+", 
                flags=re.UNICODE
            )
            return emoji_pattern.sub('', text)
        
        # 创建PDF
        pdf = FPDF()
        pdf.set_auto_page_break(auto=True, margin=15)
        pdf.add_page()
        
        # 尝试添加中文字体
        font_added = False
        font_paths = [
            ('SimHei', 'C:/Windows/Fonts/simhei.ttf'),
            ('Microsoft YaHei', 'C:/Windows/Fonts/msyh.ttc'),
            ('SimSun', 'C:/Windows/Fonts/simsun.ttc'),
        ]
        
        for font_name, font_path in font_paths:
            try:
                if Path(font_path).exists():
                    pdf.add_font(font_name, '', font_path)
                    pdf.set_font(font_name, size=12)
                    font_added = True
                    break
            except Exception:
                continue
        
        if not font_added:
            pdf.set_font('Arial', size=12)
        
        # 解析Markdown并转换为PDF
        lines = md_content.split('\n')
        
        for line in lines:
            line = line.rstrip()
            line = remove_emoji(line)  # 移除emoji
            
            # 跳过空行
            if not line:
                pdf.ln(3)
                continue
            
            # 跳过图片标记
            if line.startswith('!['):
                continue
            
            # 跳过分隔线
            if line.startswith('---'):
                pdf.ln(5)
                continue
            
            # 处理标题
            if line.startswith('# '):
                pdf.set_font_size(18)
                text = line[2:].strip()
                text = re.sub(r'\*\*([^*]+)\*\*', r'\1', text)
                try:
                    pdf.cell(0, 12, text, new_x=XPos.LMARGIN, new_y=YPos.NEXT, align='C')
                except:
                    pdf.cell(0, 12, '[标题]', new_x=XPos.LMARGIN, new_y=YPos.NEXT, align='C')
                pdf.ln(5)
                pdf.set_font_size(12)
                continue
            
            if line.startswith('## '):
                pdf.set_font_size(14)
                text = line[3:].strip()
                text = re.sub(r'\*\*([^*]+)\*\*', r'\1', text)
                try:
                    pdf.cell(0, 10, text, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
                except:
                    pdf.cell(0, 10, '[章节]', new_x=XPos.LMARGIN, new_y=YPos.NEXT)
                pdf.ln(3)
                pdf.set_font_size(12)
                continue
            
            if line.startswith('### '):
                pdf.set_font_size(12)
                text = line[4:].strip()
                text = re.sub(r'\*\*([^*]+)\*\*', r'\1', text)
                try:
                    pdf.cell(0, 8, text, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
                except:
                    pdf.cell(0, 8, '[小节]', new_x=XPos.LMARGIN, new_y=YPos.NEXT)
                pdf.ln(2)
                continue
            
            # 处理引用块
            if line.startswith('> '):
                text = line[2:].strip()
                text = re.sub(r'\*\*([^*]+)\*\*', r'\1', text)
                pdf.set_font_size(10)
                try:
                    pdf.multi_cell(0, 6, f"  {text}")
                except:
                    pass
                pdf.set_font_size(12)
                continue
            
            # 处理表格（简化处理）
            if line.startswith('|'):
                # 跳过表格分隔行
                if '---' in line or ':-' in line:
                    continue
                # 提取表格内容
                cells = [c.strip() for c in line.split('|')[1:-1]]
                text = ' | '.join(cells)
                pdf.set_font_size(10)
                try:
                    pdf.multi_cell(0, 5, text)
                except:
                    pass
                pdf.set_font_size(12)
                continue
            
            # 处理列表项
            if line.startswith('- ') or line.startswith('* '):
                text = line[2:].strip()
                text = re.sub(r'\*\*([^*]+)\*\*', r'\1', text)
                text = re.sub(r'`([^`]+)`', r'\1', text)
                try:
                    pdf.multi_cell(0, 6, f"  - {text}")
                except:
                    pass
                continue
            
            # 普通文本
            text = line.strip()
            text = re.sub(r'\*\*([^*]+)\*\*', r'\1', text)  # 移除粗体
            text = re.sub(r'`([^`]+)`', r'\1', text)  # 移除代码标记
            
            if text:
                try:
                    pdf.multi_cell(0, 6, text)
                except:
                    pass
        
        # 添加图表页
        if Path(chart_path).exists():
            pdf.add_page()
            pdf.set_font_size(14)
            try:
                pdf.cell(0, 10, 'K线图', new_x=XPos.LMARGIN, new_y=YPos.NEXT, align='C')
            except:
                pdf.cell(0, 10, 'Chart', new_x=XPos.LMARGIN, new_y=YPos.NEXT, align='C')
            pdf.ln(5)
            
            # 计算图片尺寸以适应页面
            page_width = pdf.w - 20  # 左右各留10mm边距
            pdf.image(chart_path, x=10, w=page_width)
        
        pdf.output(output_path)
        
    except ImportError:
        raise ImportError(
            "生成PDF需要安装 fpdf2 库。\n"
            "请运行: pip install fpdf2"
        )


def main() -> None:
    """CLI主入口"""
    parser = create_parser()
    args = parser.parse_args()
    
    try:
        # 加载LLM配置
        if not args.quiet:
            print("正在加载配置...", file=sys.stderr)
        llm_config = load_llm_config(args)
        
        # 加载数据
        if not args.quiet:
            print("正在加载数据...", file=sys.stderr)
        
        if args.data_file:
            input_data = load_data_from_file(args.data_file)
        else:
            input_data = load_data_from_akshare(
                args.config,
                args.date,
                args.time
            )
        
        if not args.quiet:
            print(f"数据加载完成，当前价格: {input_data.current_price:.2f}", file=sys.stderr)
        
        # 创建Agent并执行分析
        agent_config = AgentConfig(
            llm_config=llm_config,
            verbose=not args.quiet  # 非静默模式时输出进度
        )
        agent = MarketAnalysisAgent(agent_config)
        result = agent.analyze(input_data)
        
        # 输出结果
        output_result(result, input_data, args)
        
    except KeyboardInterrupt:
        print("\n操作已取消", file=sys.stderr)
        sys.exit(130)
    except ValueError as e:
        print(f"错误: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"未知错误: {e}", file=sys.stderr)
        if not args.quiet:
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
