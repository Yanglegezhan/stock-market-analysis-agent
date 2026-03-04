"""每日定时任务运行脚本

功能：
1. 运行大盘分析Agent
2. 将分析结果推送到飞书
"""

import subprocess
import sys
import json
import httpx
from pathlib import Path
from datetime import datetime
from typing import Optional
import io
import os

# 强制使用 UTF-8 编码
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# 配置
PROJECT_DIR = Path(__file__).parent
# 优先使用环境变量，否则使用默认值
FEISHU_WEBHOOK = os.environ.get("FEISHU_WEBHOOK", "https://open.feishu.cn/open-apis/bot/v2/hook/1690b295-e029-4752-ba3b-cbd3013ded56")


def run_analysis() -> dict:
    """运行大盘分析，返回结果"""
    print(f"[{datetime.now()}] 开始运行大盘分析...")

    # 运行命令，输出JSON格式到临时文件
    output_file = PROJECT_DIR / "output" / f"daily_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    output_file.parent.mkdir(parents=True, exist_ok=True)

    cmd = [
        sys.executable, "-m", "src",
        "--output-format", "json",
        "--output", str(output_file),
        "--quiet"
    ]

    # 设置环境变量，强制使用 UTF-8 编码
    import os
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"

    try:
        result = subprocess.run(
            cmd,
            cwd=PROJECT_DIR,
            capture_output=True,
            text=True,
            timeout=300,  # 5分钟超时
            encoding='utf-8',
            errors='replace',
            env=env
        )

        if result.returncode != 0:
            print(f"分析失败: {result.stderr}")
            return {
                "success": False,
                "error": result.stderr,
                "output_file": None
            }

        print(f"[{datetime.now()}] 分析完成，结果保存到: {output_file}")

        return {
            "success": True,
            "output_file": str(output_file)
        }

    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "error": "分析超时（超过5分钟）",
            "output_file": None
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "output_file": None
        }


def load_report(output_file: str) -> Optional[dict]:
    """加载分析报告"""
    try:
        with open(output_file, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"加载报告失败: {e}")
        return None


def format_feishu_message(report: dict) -> dict:
    """格式化飞书消息"""
    # 提取关键信息
    data_date = report.get("data_cutoff", "未知日期")
    current_price = report.get("current_price", 0)

    # 趋势分析
    trend = report.get("trend_analysis", {})
    short_term = trend.get("short_term", {})
    mid_term = trend.get("mid_term", {})
    long_term = trend.get("long_term", {})

    # 支撑压力位
    sr = report.get("support_resistance", {})
    key_support = sr.get("key_support_today", {})
    key_resistance = sr.get("key_resistance_today", {})

    # 综合建议
    summary = report.get("summary", {})

    # 构建消息内容
    content_lines = [
        f"**日期**: {data_date}",
        f"**当前价格**: {current_price:.2f}",
        "",
        "**趋势判断**",
        f"- 短期: {short_term.get('direction', '未知')} ({short_term.get('strength', '未知')})",
        f"- 中期: {mid_term.get('direction', '未知')} ({mid_term.get('strength', '未知')})",
        f"- 长期: {long_term.get('direction', '未知')} ({long_term.get('strength', '未知')})",
        "",
        "**关键位置**",
    ]

    if key_support:
        content_lines.append(f"- 关键支撑: {key_support.get('price', 0):.2f}")
    if key_resistance:
        content_lines.append(f"- 关键压力: {key_resistance.get('price', 0):.2f}")

    content_lines.extend([
        "",
        "**操作建议**",
        summary.get("recommendation", "无"),
    ])

    # 风险提示
    risks = summary.get("risk_warning", [])
    if risks:
        content_lines.append("")
        content_lines.append("**风险提示**")
        for risk in risks[:3]:  # 最多显示3条
            content_lines.append(f"- {risk}")

    # 飞书消息格式
    message = {
        "msg_type": "interactive",
        "card": {
            "header": {
                "title": {
                    "tag": "plain_text",
                    "content": "每日大盘分析报告"
                },
                "template": "blue"
            },
            "elements": [
                {
                    "tag": "markdown",
                    "content": "\n".join(content_lines)
                },
                {
                    "tag": "note",
                    "elements": [
                        {
                            "tag": "plain_text",
                            "content": f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                        }
                    ]
                }
            ]
        }
    }

    return message


def send_to_feishu(message: dict) -> bool:
    """发送消息到飞书"""
    print(f"[{datetime.now()}] 正在发送到飞书...")

    try:
        response = httpx.post(
            FEISHU_WEBHOOK,
            json=message,
            timeout=30
        )

        if response.status_code == 200:
            result = response.json()
            if result.get("code") == 0:
                print(f"[{datetime.now()}] 飞书推送成功")
                return True
            else:
                print(f"飞书推送失败: {result}")
                return False
        else:
            print(f"飞书推送失败: HTTP {response.status_code}")
            return False

    except Exception as e:
        print(f"飞书推送异常: {e}")
        return False


def send_error_notification(error: str) -> bool:
    """发送错误通知到飞书"""
    message = {
        "msg_type": "interactive",
        "card": {
            "header": {
                "title": {
                    "tag": "plain_text",
                    "content": "大盘分析运行失败"
                },
                "template": "red"
            },
            "elements": [
                {
                    "tag": "markdown",
                    "content": f"**错误信息**:\n```\n{error}\n```"
                },
                {
                    "tag": "note",
                    "elements": [
                        {
                            "tag": "plain_text",
                            "content": f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                        }
                    ]
                }
            ]
        }
    }

    return send_to_feishu(message)


def main():
    """主函数"""
    print("=" * 50)
    print(f"[{datetime.now()}] 开始每日大盘分析任务")
    print("=" * 50)

    # 1. 运行分析
    result = run_analysis()

    if not result["success"]:
        # 发送错误通知
        send_error_notification(result["error"])
        return 1

    # 2. 加载报告
    report = load_report(result["output_file"])
    if not report:
        send_error_notification("无法加载分析报告")
        return 1

    # 3. 发送到飞书
    message = format_feishu_message(report)
    success = send_to_feishu(message)

    print("=" * 50)
    print(f"[{datetime.now()}] 任务完成")
    print("=" * 50)

    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())