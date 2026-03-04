"""每日定时任务运行脚本

功能：
1. 运行大盘分析Agent
2. 将完整Markdown报告推送到飞书
"""

import subprocess
import sys
import json
import httpx
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional
import io
import os

# 强制使用 UTF-8 编码
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# 配置
PROJECT_DIR = Path(__file__).parent
FEISHU_WEBHOOK = os.environ.get("FEISHU_WEBHOOK", "https://open.feishu.cn/open-apis/bot/v2/hook/1690b295-e029-4752-ba3b-cbd3013ded56")

# 飞书消息长度限制（约30KB）
FEISHU_MSG_LIMIT = 30000


def run_analysis(analysis_date: Optional[datetime] = None) -> dict:
    """运行大盘分析，返回结果"""
    if analysis_date is None:
        analysis_date = datetime.now()

    print(f"[{datetime.now()}] 开始运行大盘分析，目标日期: {analysis_date.strftime('%Y-%m-%d')}...")

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    output_dir = PROJECT_DIR / "output"
    output_dir.mkdir(parents=True, exist_ok=True)

    cmd = [
        sys.executable, "-m", "src",
        "--output-format", "markdown",
        "--output", str(output_dir / f"report_{timestamp}.md"),
        "--date", analysis_date.strftime("%Y-%m-%d"),
        "--quiet"
    ]

    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"

    try:
        result = subprocess.run(
            cmd,
            cwd=PROJECT_DIR,
            capture_output=True,
            text=True,
            timeout=300,
            encoding='utf-8',
            errors='replace',
            env=env
        )

        if result.returncode != 0:
            print(f"分析失败: {result.stderr}")
            return {"success": False, "error": result.stderr}

        # 查找生成的文件
        json_files = list(output_dir.glob("*.json"))
        md_files = list(output_dir.glob("*.md"))
        chart_files = list(output_dir.glob("*.png"))

        json_file = max(json_files, key=lambda f: f.stat().st_mtime) if json_files else None
        md_file = max(md_files, key=lambda f: f.stat().st_mtime) if md_files else None
        chart_file = max(chart_files, key=lambda f: f.stat().st_mtime) if chart_files else None

        print(f"[{datetime.now()}] 分析完成")
        print(f"  JSON: {json_file}")
        print(f"  MD: {md_file}")
        print(f"  Chart: {chart_file}")

        return {
            "success": True,
            "json_file": str(json_file) if json_file else None,
            "md_file": str(md_file) if md_file else None,
            "chart_file": str(chart_file) if chart_file else None
        }

    except subprocess.TimeoutExpired:
        return {"success": False, "error": "分析超时（超过5分钟）"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def load_report(json_file: str) -> Optional[dict]:
    """加载JSON报告"""
    try:
        with open(json_file, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"加载报告失败: {e}")
        return None


def load_markdown(md_file: str) -> Optional[str]:
    """加载Markdown报告"""
    try:
        with open(md_file, "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        print(f"加载Markdown失败: {e}")
        return None


def split_markdown_for_feishu(md_content: str) -> list:
    """将Markdown内容分割成适合飞书发送的多个部分"""
    if len(md_content) <= FEISHU_MSG_LIMIT:
        return [md_content]

    parts = []
    lines = md_content.split('\n')
    current_part = []
    current_length = 0

    for line in lines:
        if current_length + len(line) + 1 > FEISHU_MSG_LIMIT:
            if current_part:
                parts.append('\n'.join(current_part))
            current_part = [line]
            current_length = len(line) + 1
        else:
            current_part.append(line)
            current_length += len(line) + 1

    if current_part:
        parts.append('\n'.join(current_part))

    return parts


def send_markdown_to_feishu(md_content: str, title: str = "大盘分析报告") -> bool:
    """发送Markdown内容到飞书"""
    message = {
        "msg_type": "post",
        "content": {
            "post": {
                "zh_cn": {
                    "title": title,
                    "content": [[{"tag": "text", "text": md_content}]]
                }
            }
        }
    }

    try:
        response = httpx.post(FEISHU_WEBHOOK, json=message, timeout=30)
        if response.status_code == 200:
            result = response.json()
            if result.get("code") == 0:
                return True
            else:
                print(f"飞书推送失败: {result}")
        else:
            print(f"飞书推送失败: HTTP {response.status_code}")
    except Exception as e:
        print(f"飞书推送异常: {e}")

    return False


def send_card_to_feishu(md_content: str, title: str, template: str = "blue") -> bool:
    """发送卡片消息到飞书"""
    # 飞书卡片消息有长度限制，需要截断
    if len(md_content) > 28000:
        md_content = md_content[:28000] + "\n\n... (内容过长，已截断)"

    message = {
        "msg_type": "interactive",
        "card": {
            "header": {
                "title": {"tag": "plain_text", "content": title},
                "template": template
            },
            "elements": [
                {"tag": "markdown", "content": md_content}
            ]
        }
    }

    try:
        response = httpx.post(FEISHU_WEBHOOK, json=message, timeout=30)
        if response.status_code == 200:
            result = response.json()
            if result.get("code") == 0:
                return True
            else:
                print(f"飞书推送失败: {result}")
        else:
            print(f"飞书推送失败: HTTP {response.status_code}")
    except Exception as e:
        print(f"飞书推送异常: {e}")

    return False


def send_full_report_to_feishu(md_content: str) -> int:
    """发送完整报告到飞书，返回成功发送的消息数"""
    # 分割内容
    parts = split_markdown_for_feishu(md_content)

    success_count = 0
    total = len(parts)

    for i, part in enumerate(parts):
        if total == 1:
            title = "大盘分析报告"
        else:
            title = f"大盘分析报告 ({i+1}/{total})"

        if send_card_to_feishu(part, title):
            success_count += 1
            print(f"  已发送第 {i+1}/{total} 部分")
        else:
            print(f"  发送第 {i+1}/{total} 部分失败")

    return success_count


def send_summary_to_feishu(report: dict) -> bool:
    """发送概览消息到飞书"""
    data_date = report.get("data_cutoff", "未知日期")
    current_price = report.get("current_price", 0)
    analysis_time = report.get("analysis_time", "")

    position_analysis = report.get("position_analysis", {})
    long_term = report.get("long_term", {})
    key_support = report.get("key_support_today", {})
    key_resistance = report.get("key_resistance_today", {})
    short_term = report.get("short_term", {})

    content = [
        f"**日期**: {data_date}",
        f"**当前价格**: {current_price:.2f}",
        f"**位置判断**: {position_analysis.get('position', '未知')}",
        "",
        f"**趋势**: {long_term.get('trend', '未知')} ({long_term.get('strength', '未知')})",
        f"**置信度**: {long_term.get('confidence', '未知')}",
        "",
        "**关键位置**:",
    ]

    if key_support:
        content.append(f"- 支撑: {key_support.get('price', 0):.2f} ({key_support.get('reason', '')})")
    if key_resistance:
        content.append(f"- 压力: {key_resistance.get('price', 0):.2f} ({key_resistance.get('reason', '')})")

    content.append("")
    content.append(f"**操作建议**: {short_term.get('suggestion', '无')}")

    if short_term.get("risk_warning"):
        content.append(f"")
        content.append(f"**风险提示**: {short_term.get('risk_warning')}")

    content.append("")
    content.append(f"_分析时间: {analysis_time}_")

    return send_card_to_feishu('\n'.join(content), "大盘分析概览", "blue")


def send_error_notification(error: str) -> bool:
    """发送错误通知"""
    message = {
        "msg_type": "interactive",
        "card": {
            "header": {
                "title": {"tag": "plain_text", "content": "大盘分析运行失败"},
                "template": "red"
            },
            "elements": [
                {"tag": "markdown", "content": f"**错误信息**:\n```\n{error[:2000]}\n```"},
                {"tag": "note", "elements": [
                    {"tag": "plain_text", "content": f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"}
                ]}
            ]
        }
    }
    try:
        response = httpx.post(FEISHU_WEBHOOK, json=message, timeout=30)
        return response.status_code == 200 and response.json().get("code") == 0
    except:
        return False


def send_image_to_feishu(image_path: str) -> Optional[str]:
    """上传图片到飞书并返回 image_key

    注意：webhook机器人无法直接上传图片，这里使用base64编码
    实际上传需要使用飞书开放平台API和access_token
    """
    if not image_path or not Path(image_path).exists():
        print(f"图片文件不存在: {image_path}")
        return None

    try:
        # 读取图片
        with open(image_path, "rb") as f:
            image_data = f.read()

        # 检查图片大小（飞书限制10MB）
        if len(image_data) > 10 * 1024 * 1024:
            print("图片过大，跳过发送")
            return None

        print(f"  图片大小: {len(image_data) / 1024:.1f} KB")
        return image_path  # 返回路径供后续使用

    except Exception as e:
        print(f"处理图片失败: {e}")
        return None


def send_image_message_to_feishu(image_path: str) -> bool:
    """发送图片消息到飞书（使用image消息类型）"""
    if not image_path or not Path(image_path).exists():
        return False

    try:
        # 读取图片并转为base64
        with open(image_path, "rb") as f:
            image_data = f.read()

        import base64
        image_base64 = base64.b64encode(image_data).decode('utf-8')

        # 飞书图片消息格式
        message = {
            "msg_type": "image",
            "content": {
                "image_key": image_base64  # 这里需要实际的 image_key
            }
        }

        response = httpx.post(FEISHU_WEBHOOK, json=message, timeout=30)

        if response.status_code == 200:
            result = response.json()
            if result.get("code") == 0:
                return True
            else:
                # 图片消息类型可能不支持，尝试用卡片消息
                return False
        return False

    except Exception as e:
        print(f"发送图片失败: {e}")
        return False


def send_chart_to_feishu(chart_path: str) -> bool:
    """发送图表到飞书

    流程：1. 上传图片到 catbox.moe 图床  2. 发送图片链接到飞书
    """
    if not chart_path or not Path(chart_path).exists():
        print(f"图表文件不存在: {chart_path}")
        return False

    try:
        # 读取图片
        with open(chart_path, "rb") as f:
            image_data = f.read()

        print(f"  正在上传图表到图床 ({len(image_data) / 1024:.1f} KB)...")

        # 使用 catbox.moe 免费图床
        url = "https://catbox.moe/user/api.php"
        files = {"fileToUpload": ("chart.png", image_data, "image/png")}
        data = {"reqtype": "fileupload"}

        response = httpx.post(url, files=files, data=data, timeout=60)

        if response.status_code == 200 and response.text.startswith("http"):
            image_url = response.text.strip()
            print(f"  图表上传成功: {image_url}")

            # 发送到飞书（使用 post 消息类型）
            message = {
                "msg_type": "post",
                "content": {
                    "post": {
                        "zh_cn": {
                            "title": "K线图",
                            "content": [
                                [{"tag": "text", "text": "点击链接查看K线图："}],
                                [{"tag": "a", "text": "查看图表", "href": image_url}]
                            ]
                        }
                    }
                }
            }

            resp = httpx.post(FEISHU_WEBHOOK, json=message, timeout=30)
            if resp.status_code == 200 and resp.json().get("StatusCode") == 0:
                print(f"  图表发送成功")
                return True
            else:
                print(f"  图表发送失败: {resp.text[:100]}")
                return False
        else:
            print(f"  图表上传失败: {response.text[:100]}")
            return False

    except Exception as e:
        print(f"发送图表失败: {e}")
        return False


def main():
    """主函数"""
    print("=" * 50)
    print(f"[{datetime.now()}] 开始每日大盘分析任务")
    print("=" * 50)

    # 尝试今天和昨天
    dates_to_try = [datetime.now(), datetime.now() - timedelta(days=1)]

    result = None
    for target_date in dates_to_try:
        result = run_analysis(target_date)
        if result["success"]:
            break
        print(f"[{datetime.now()}] {target_date.strftime('%Y-%m-%d')} 分析失败，尝试下一个日期...")

    if not result["success"]:
        send_error_notification(result["error"])
        return 1

    # 发送概览
    if result.get("json_file"):
        report = load_report(result["json_file"])
        if report:
            print(f"[{datetime.now()}] 发送概览...")
            send_summary_to_feishu(report)

    # 发送完整Markdown报告
    if result.get("md_file"):
        md_content = load_markdown(result["md_file"])
        if md_content:
            print(f"[{datetime.now()}] 发送完整报告...")
            success_count = send_full_report_to_feishu(md_content)
            print(f"[{datetime.now()}] 完整报告发送完成 ({success_count} 条消息)")

    # 发送图表
    if result.get("chart_file"):
        print(f"[{datetime.now()}] 发送图表...")
        send_chart_to_feishu(result["chart_file"])

    print("=" * 50)
    print(f"[{datetime.now()}] 任务完成")
    print("=" * 50)

    return 0


if __name__ == "__main__":
    sys.exit(main())