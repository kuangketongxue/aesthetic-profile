#!/usr/bin/env python3
"""把 survey 的 JSON 数据源生成浏览器可直接用的 .js 包装。

设计原因：调研页要能直接双击打开（file://），此时 fetch 本地 JSON 会被浏览器
拦住，所以必须用 <script src> 引入一个把数据挂到 window 上的 .js。

唯一真身是 styles.json / picks.json；styles.js / picks.js 由本脚本生成。
带 --check 时只校验两者是否一致，不写文件（用于 CI / 交付前自检）。

用法：
    python scripts/build_survey_js.py          # 重新生成
    python scripts/build_survey_js.py --check  # 只校验是否漂移
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SURVEY = ROOT / "survey"

PAIRS = [
    ("styles.json", "styles.js", "SURVEY_STYLES", "视觉风格全清单"),
    ("picks.json", "picks.js", "SURVEY_DATA", "审美调研图数据"),
]


def render(json_name: str, var: str, label: str) -> str:
    data = json.loads((SURVEY / json_name).read_text(encoding="utf-8"))
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    return (
        f"/* {label}：由 scripts/build_survey_js.py 从 {json_name} 生成，勿手改。 */\n"
        f"window.{var} = {payload};\n"
    )


def main() -> int:
    check = "--check" in sys.argv
    drifted, written = [], []
    for json_name, js_name, var, label in PAIRS:
        text = render(json_name, var, label)
        target = SURVEY / js_name
        old = target.read_text(encoding="utf-8") if target.exists() else ""
        if old != text:
            drifted.append(js_name)
            if not check:
                target.write_text(text, encoding="utf-8")
                written.append(js_name)
        size_kb = len(text.encode("utf-8")) / 1024
        print(f"  {js_name:12s} {size_kb:8.1f} KB  {'OK' if old == text else 'DRIFT'}")

    if check and drifted:
        print(f"FAIL 漂移：{', '.join(drifted)}（跑一次不带 --check 的即可修复）")
        return 1
    if written:
        print(f"已重写：{', '.join(written)}")
    print("OK" if not drifted else "OK 已修复")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
