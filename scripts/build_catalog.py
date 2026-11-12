#!/usr/bin/env python3
"""从 survey/styles.json 生成 references/style-catalog.md（14 大类索引）。

为什么要有这份 md：agent 在对话里要「快速查某个风格的 id 和关键词」时，
读 130KB 的 JSON 太费；这份按大类分节、一行一条，检索成本低得多。

    python scripts/build_catalog.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "survey" / "styles.json"
OUT = ROOT / "references" / "style-catalog.md"


def main() -> int:
    data = json.loads(SRC.read_text(encoding="utf-8"))
    styles = data["styles"]
    groups = data["groups"]

    L: list[str] = []
    L.append("# 视觉风格索引")
    L.append("")
    L.append("> 由 `scripts/build_catalog.py` 从 `survey/styles.json` 生成，**勿手改**。")
    L.append(f"> 共 {data['total']} 种 / {len(groups)} 大类 ｜ 生成于 {data.get('generated')}")
    L.append(f"> 口径：{data.get('scope')}")
    L.append("")
    L.append("怎么用：`liked_styles[].id` 就是这里的 `sNNN`；需要找图时直接复制该行的关键词到 Unsplash / Pexels。")
    L.append("")

    L.append("## 大类速览")
    L.append("")
    L.append("| 大类 | 数量 |")
    L.append("|---|---|")
    for g in groups:
        L.append(f"| {g['name']} | {g['count']} |")
    L.append("")

    for g in groups:
        name = g["name"]
        rows = [s for s in styles if s["group"] == name]
        L.append(f"## {name}（{len(rows)}）")
        L.append("")
        L.append("| id | 中文 | 英文 | 特征 | 找图关键词 | 代表色 |")
        L.append("|---|---|---|---|---|---|")
        for s in rows:
            kw = ", ".join(s["kw"])
            colors = " ".join(s["colors"])
            desc = (s.get("desc") or "").replace("|", "／")
            L.append(f"| `{s['id']}` | {s['cn']} | {s.get('en','')} | {desc} | {kw} | {colors} |")
        L.append("")

    L.append("---")
    L.append("")
    L.append("风格参考图来自 Unsplash / Pexels 免费可商用图库，仅作氛围参考；")
    L.append("清单本身是「可用来找图的分类」，不是艺术史流派谱系。")
    OUT.write_text("\n".join(L) + "\n", encoding="utf-8")
    print(f"已生成 references/style-catalog.md（{len(styles)} 行，{len(L)} 行文本）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
