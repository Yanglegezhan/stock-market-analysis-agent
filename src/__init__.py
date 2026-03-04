"""大盘分析Agent - 基于LLM的智能技术分析系统"""

import sys
import io

# 修复 Windows 控制台编码问题
if sys.platform == 'win32':
    try:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
    except Exception:
        pass
