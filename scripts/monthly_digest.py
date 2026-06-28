#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
沉淀层 · 月度结晶
==================
独立旁挂脚本,不依赖 Horizon 主流程的内部结构。

作用:把当月每天的"第三层整体分析"(synthesis)汇总起来,
交给 AI 提炼成一篇"月度综述"——本月 AI 领域发生了什么、哪些是真信号
哪些是噪音、趋势走向哪里。这是真正沉淀进知识库、不会过期的东西。

数据来源:Horizon 每天把第三层整体分析存到 data/summaries/{date}-summary-synthesis.md
(由 orchestrator._synthesize_daily 写入)

用法:
  python scripts/monthly_digest.py              # 结晶上个月(每月1号自动跑时用)
  python scripts/monthly_digest.py 2026-06      # 结晶指定月份

环境变量:
  NVIDIA_API_KEY  必填
"""

import os
import sys
import glob
import datetime as dt
from pathlib import Path

try:
    from openai import OpenAI
except ImportError:
    print("需要 openai 库:pip install openai")
    sys.exit(1)

NVIDIA_API_KEY = os.environ.get("NVIDIA_API_KEY", "")
BASE_URL = "https://integrate.api.nvidia.com/v1"
MODEL = os.environ.get("SYNTHESIS_MODEL", "deepseek-ai/deepseek-v4-pro")

# Horizon 存每日 synthesis 的目录
SUMMARIES_DIR = Path("data/summaries")
# 月度结晶输出目录(会被工作流推到知识库)
OUTPUT_DIR = Path("data/monthly")


def _la_today():
    """返回洛杉矶时区的当前日期(系统所有日期统一用洛杉矶时间)。"""
    try:
        from zoneinfo import ZoneInfo
        return dt.datetime.now(ZoneInfo("America/Los_Angeles")).date()
    except Exception:
        # 兜底:zoneinfo 不可用时退回 UTC-7(夏令时近似)
        return (dt.datetime.utcnow() - dt.timedelta(hours=7)).date()


MONTHLY_SYSTEM = """你是顶尖的 AI 行业战略分析师。下面是某一整月里,每天的"AI 新闻整体分析"汇总。
请基于这一个月的逐日分析,提炼出一篇**月度综述**。

要求回答:
1. **本月主线**:这个月 AI 领域最重要的 2-4 条主线脉络是什么?把分散在各天的信号归纳成趋势。
2. **真信号 vs 噪音**:回望整月,哪些当时看着重要的事后来被证明是真趋势?哪些是当时炒作、现在看是噪音?
3. **趋势走向**:这些主线指向哪里?下个月可能延续或转折的点在哪?
4. **沉淀价值**:这个月哪些进展是"不会过期的"、值得长期记住的?

要求:
- 简体中文,专有名词保留英文。
- 这是要沉淀进知识库、长期回看的文档,要有结构、有判断、有洞见。
- 600-1000 字。诚实区分事实与推演。如果某个月本身平淡,如实说明,不要硬拔高。
"""

MONTHLY_USER = """月份:{month}

本月逐日整体分析汇总(每段是一天):

{daily_digest}

请输出本月的月度综述(本月主线 / 真信号vs噪音 / 趋势走向 / 沉淀价值),600-1000字,简体中文。直接输出正文。"""


def get_target_month():
    """确定要结晶哪个月。默认上个月。"""
    if len(sys.argv) > 1:
        return sys.argv[1]  # 形如 2026-06
    today = _la_today()
    first = today.replace(day=1)
    last_month = first - dt.timedelta(days=1)
    return last_month.strftime("%Y-%m")


def collect_daily_syntheses(month):
    """收集指定月份的所有每日整体分析。"""
    pattern = str(SUMMARIES_DIR / f"{month}-*-summary-synthesis.md")
    files = sorted(glob.glob(pattern))
    # 兼容另一种命名:{date}-summary-synthesis.md
    if not files:
        pattern2 = str(SUMMARIES_DIR / f"{month}-*synthesis*.md")
        files = sorted(glob.glob(pattern2))
    entries = []
    for fp in files:
        date_part = Path(fp).name[:10]  # YYYY-MM-DD
        text = Path(fp).read_text(encoding="utf-8").strip()
        if text:
            entries.append((date_part, text))
    return entries


def main():
    if not NVIDIA_API_KEY:
        print("❌ 缺少 NVIDIA_API_KEY")
        sys.exit(1)

    month = get_target_month()
    print(f"📅 月度结晶目标:{month}")

    entries = collect_daily_syntheses(month)
    if not entries:
        print(f"⚠️  {month} 没有找到每日整体分析文件,跳过。")
        print(f"   (查找路径:{SUMMARIES_DIR}/{month}-*-summary-synthesis.md)")
        return

    print(f"   找到 {len(entries)} 天的整体分析")

    daily_digest = "\n\n".join(
        f"【{date}】\n{text}" for date, text in entries
    )

    client = OpenAI(base_url=BASE_URL, api_key=NVIDIA_API_KEY)
    print("🧪 正在生成月度综述...")
    resp = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": MONTHLY_SYSTEM},
            {"role": "user", "content": MONTHLY_USER.format(month=month, daily_digest=daily_digest)},
        ],
        temperature=0.5,
        max_tokens=4000,
    )
    content = resp.choices[0].message.content
    import re
    content = re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL).strip()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUTPUT_DIR / f"{month}-月度综述.md"
    header = f"# AI 月度综述 · {month}\n\n> 基于本月 {len(entries)} 天的逐日整体分析提炼。\n\n---\n\n"
    out_path.write_text(header + content, encoding="utf-8")
    print(f"✅ 月度综述已生成:{out_path}")


if __name__ == "__main__":
    main()
