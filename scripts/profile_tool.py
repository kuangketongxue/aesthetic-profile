#!/usr/bin/env python3
"""审美画像工具：校验 / 合并调研结果 / 生成人读摘要。

零依赖（只用标准库），Windows / macOS / Linux 都能直接跑。

    python scripts/profile_tool.py validate
    python scripts/profile_tool.py merge --input aesthetic-survey-2026-11-12.json [--dry-run]
    python scripts/profile_tool.py render

设计原则：
1. 没有证据就不写值（轴留 null，绝不填 50 假装中性）。
2. 合并只增不删；旧判断被推翻也保留，另记一条证据说明作废。
3. 版本号按「有没有改动判断」升，不按「跑了多少次」升。
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PROFILE = ROOT / "profile" / "aesthetic-profile.json"
SCHEMA = ROOT / "profile" / "profile.schema.json"
PROFILE_MD = ROOT / "profile" / "profile.md"
STYLES = ROOT / "survey" / "styles.json"

AXIS_KEYS = ["temperature", "brightness", "density", "saturation", "contrast", "organic", "realism", "era"]
AXIS_HINT = {
    "temperature": "冷 ← → 暖",
    "brightness": "暗 ← → 亮",
    "density": "简 ← → 繁",
    "saturation": "灰 ← → 艳",
    "contrast": "柔 ← → 硬",
    "organic": "几何 ← → 有机",
    "realism": "抽象 ← → 实拍",
    "era": "复古 ← → 未来",
}
AXIS_LABEL = {
    0: "极左", 20: "明显偏左", 40: "略偏左", 50: "居中", 60: "略偏右", 80: "明显偏右", 100: "极右",
}


# --------------------------------------------------------------------------- 校验
def load_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        fail(f"文件不存在：{path}")
    except json.JSONDecodeError as e:
        fail(f"JSON 解析失败：{path} 第 {e.lineno} 行 —— {e.msg}")
    return {}


def validate(data: dict, schema: dict) -> list[str]:
    """按 schema 里实际用到的约束做校验（故意不实现整个 JSON Schema，零依赖优先）。"""
    errs: list[str] = []

    for key in schema.get("required", []):
        if key not in data:
            errs.append(f"缺少必填字段：{key}")

    allowed = set(schema.get("properties", {}))
    for key in data:
        if key not in allowed:
            errs.append(f"未知字段：{key}（schema 里没有，拼写错了？）")

    def chk_enum(key, values):
        v = data.get(key)
        if v is not None and v not in values:
            errs.append(f"{key} 必须是 {values}，实际是 {v!r}")

    chk_enum("status", ["seed", "calibrated", "stable"])

    conf = data.get("confidence")
    if conf is not None and not (isinstance(conf, (int, float)) and 0 <= conf <= 1):
        errs.append(f"confidence 必须在 0-1 之间，实际是 {conf!r}")

    for key in ("schema_version", "updated"):
        v = data.get(key)
        if v is not None and not isinstance(v, str):
            errs.append(f"{key} 必须是字符串")

    axes = data.get("axes") or {}
    for k, v in axes.items():
        if k not in AXIS_KEYS:
            errs.append(f"axes 里有未知轴：{k}")
        if v is not None:
            if not isinstance(v, int) or isinstance(v, bool) or not 0 <= v <= 100:
                errs.append(f"axes.{k} 必须是 0-100 的整数或 null，实际是 {v!r}")

    if not isinstance(data.get("liked_styles", []), list):
        errs.append("liked_styles 必须是数组")
    if not isinstance(data.get("evidence", []), list):
        errs.append("evidence 必须是数组")

    for i, ev in enumerate(data.get("evidence", [])):
        for req in ("date", "source", "signal", "strength"):
            if req not in ev:
                errs.append(f"evidence[{i}] 缺少 {req}")
        if ev.get("strength") not in (None, "weak", "medium", "strong"):
            errs.append(f"evidence[{i}].strength 必须是 weak/medium/strong")

    for i, hr in enumerate(data.get("hard_rules", [])):
        for req in ("rule", "evidence", "date"):
            if req not in hr:
                errs.append(f"hard_rules[{i}] 缺少 {req}")

    # 自洽性：seed 却把色彩轴全填满，几乎一定是编造的
    filled = [k for k in AXIS_KEYS if axes.get(k) is not None]
    if data.get("status") == "seed" and len(filled) >= 6 and (conf or 0) > 0.5:
        errs.append(f"自相矛盾：status=seed 但已有 {len(filled)} 个轴值且 confidence>0.5，应升为 calibrated")

    return errs


def cmd_validate(_args) -> int:
    schema = load_json(SCHEMA)
    data = load_json(PROFILE)
    errs = validate(data, schema)
    if errs:
        print("FAIL 校验未通过：")
        for e in errs:
            print("  -", e)
        return 1

    axes = data.get("axes", {})
    filled = [k for k in AXIS_KEYS if axes.get(k) is not None]
    print("OK 校验通过")
    print(f"  版本 {data.get('profile_version')} · 状态 {data.get('status')} · 置信度 {data.get('confidence')}")
    print(f"  轴   {len(filled)}/{len(AXIS_KEYS)} 已测 · 喜欢 {len(data.get('liked_styles', []))} 种 "
          f"· 硬规则 {len(data.get('hard_rules', []))} 条 · 证据 {len(data.get('evidence', []))} 条")
    if len(filled) < len(AXIS_KEYS):
        print(f"  未测：{', '.join(k for k in AXIS_KEYS if axes.get(k) is None)}（保持 null 是正确做法，别填 50）")
    return 0


# --------------------------------------------------------------------------- 合并
def ratio(counts: dict, a: str, b: str) -> int | None:
    """a 占 (a+b) 的百分比。样本少于 2 个直接返回 None —— 一个选择推不出偏好。"""
    ca, cb = counts.get(a, 0), counts.get(b, 0)
    if ca + cb < 2:
        return None
    return round(ca / (ca + cb) * 100)


def load_style_index() -> dict[str, dict]:
    if not STYLES.exists():
        return {}
    data = load_json(STYLES)
    return {s["id"]: s for s in data.get("styles", [])}


def bump_version(version: str, level: str) -> str:
    major, minor, patch = (int(x) for x in version.split("."))
    if level == "major":
        return f"{major + 1}.0.0"
    if level == "minor":
        return f"{major}.{minor + 1}.0"
    return f"{major}.{minor}.{patch + 1}"


def cmd_merge(args) -> int:
    survey = load_json(Path(args.input))
    if survey.get("kind") != "aesthetic-profile-survey":
        print(f"FAIL 不是调研导出文件（kind={survey.get('kind')!r}）。请在调研页点「导出 JSON」。")
        return 1

    data = load_json(PROFILE)
    today = date.today().isoformat()
    axes = data.setdefault("axes", {})
    filled_before = len([k for k in AXIS_KEYS if axes.get(k) is not None])
    dims = survey.get("dims") or {}
    changes: list[str] = []

    # --- 轴：只算有数据、且样本足够的
    mapping = [
        ("temperature", "temp", "cool", "warm"),
        ("brightness", "light", "bright", "dark"),
        ("density", "density", "rich", "minimal"),
        ("realism", "texture", "photo", "render"),
    ]
    for axis, dim, hi, lo in mapping:
        counts = dims.get(dim) or {}
        val = ratio(counts, hi, lo)
        if val is None:
            continue
        if axes.get(axis) != val:
            changes.append(f"{axis} {axes.get(axis)} → {val}")
            axes[axis] = val

    # --- 喜欢的风格
    style_idx = load_style_index()
    liked = {x["id"]: x for x in data.get("liked_styles", [])}
    added = []
    for sid in survey.get("style_likes", []):
        weight = 0.8 if sid in survey.get("image_likes", []) else 0.7
        if sid in liked:
            if weight > liked[sid]["weight"]:
                liked[sid]["weight"] = weight
                changes.append(f"liked_styles[{sid}] 权重升至 {weight}")
        else:
            liked[sid] = {"id": sid, "weight": weight, "evidence": f"survey:{survey.get('generated', today)}"}
            added.append(sid)
    if added:
        names = [style_idx.get(i, {}).get("cn", i) for i in added]
        changes.append(f"新增 {len(added)} 个喜欢的风格：{'、'.join(names[:8])}{'…' if len(names) > 8 else ''}")
    data["liked_styles"] = sorted(liked.values(), key=lambda x: -x["weight"])

    # --- 色板与关键词
    palette = survey.get("palette") or []
    if palette:
        p = data.setdefault("palette", {})
        new_primary, new_accent = palette[:3], palette[3:6]
        if p.get("primary") != new_primary:
            changes.append(f"主色 {new_primary}")
        p["primary"], p["accent"] = new_primary, new_accent
    kws = survey.get("keywords") or []
    if kws:
        kk = data.setdefault("keywords", {"positive": [], "negative": []})
        merged, seen = [], set()
        for k in list(kws) + list(kk.get("positive", [])):
            if k and k not in seen:
                seen.add(k)
                merged.append(k)
        if merged != kk.get("positive"):
            changes.append(f"关键词 {len(kk.get('positive', []))} → {len(merged)}")
        kk["positive"] = merged

    # --- 证据
    filled = [k for k in AXIS_KEYS if axes.get(k) is not None]
    data.setdefault("evidence", []).append({
        "date": survey.get("generated", today),
        "source": "survey",
        "signal": (f"调研页作答：{len(survey.get('style_likes', []))} 个风格 / "
                   f"{len(survey.get('image_likes', []))} 张图 / {len(survey.get('answers', []))} 道题"),
        "effect": "；".join(changes) if changes else "无变化（重复合并同一份结果）",
        "strength": "strong",
    })

    # --- 状态与版本
    if not changes:
        print("OK 无变化（这份导出已经合并过），不升版本。")
        return 0
    data["profile_version"] = bump_version(data.get("profile_version", "0.0.0"), "minor")
    data["updated"] = today
    if len(filled) >= 6:
        data["status"] = "calibrated"
        data["confidence"] = max(float(data.get("confidence") or 0), 0.7)
    elif len(filled) >= 3:
        data["confidence"] = max(float(data.get("confidence") or 0), 0.45)
    elif len(data.get("liked_styles", [])) >= 5:
        # 轴没测出来，但「风格偏好」是他亲手选的，这条证据是硬的
        data["confidence"] = max(float(data.get("confidence") or 0), 0.4)

    if args.dry_run:
        print("DRY-RUN 未写入。将要发生的改动：")
        for c in changes:
            print("  -", c)
        print(f"  版本 {data['profile_version']} · 状态 {data['status']} · 置信度 {data['confidence']}")
        return 0

    PROFILE.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    cmd_render(args)
    print(f"OK 已合并 {len(changes)} 处改动 → 版本 {data['profile_version']}（轴 {filled_before}→{len(filled)}）")
    for c in changes:
        print("  -", c)
    return 0


# --------------------------------------------------------------------------- 渲染
def bar(v: int | None, width: int = 20) -> str:
    if v is None:
        return "·" * width + " 未测"
    n = round(v / 100 * width)
    return "█" * n + "░" * (width - n) + f" {v:3d}"


def cmd_render(_args) -> int:
    data = load_json(PROFILE)
    style_idx = load_style_index()
    axes = data.get("axes", {})
    L: list[str] = []
    L.append(f"# 审美画像 · {data.get('owner') or '未指定'}")
    L.append("")
    L.append("> 本文件由 `scripts/profile_tool.py render` 从 `aesthetic-profile.json` 生成，**勿手改**。")
    L.append(f"> 版本 {data.get('profile_version')} ｜ 状态 `{data.get('status')}` ｜ "
             f"置信度 {data.get('confidence')} ｜ 更新 {data.get('updated')}")
    L.append("")
    L.append(f"画像主人：{data.get('owner')} ｜ 证据 {len(data.get('evidence', []))} 条 ｜ "
             f"硬规则 {len(data.get('hard_rules', []))} 条")
    L.append("")

    L.append("## 一、八个轴")
    L.append("")
    L.append("| 轴 | 位置 | 值 | 方向 |")
    L.append("|---|---|---|---|")
    for k in AXIS_KEYS:
        v = axes.get(k)
        L.append(f"| `{k}` | `{bar(v)}` | {v if v is not None else 'null'} | {AXIS_HINT[k]} |")
    L.append("")
    L.append("`null` = 尚未测量。这不是缺陷，是「还不知道就别装知道」的记录。")
    L.append("")

    L.append("## 二、喜欢的风格")
    L.append("")
    liked = data.get("liked_styles", [])
    if liked:
        L.append("| 风格 | 英文 | 权重 | 大类 | 关键词 |")
        L.append("|---|---|---|---|---|")
        for x in liked[:30]:
            s = style_idx.get(x["id"], {})
            kw = ", ".join(s.get("kw", [])[:3])
            L.append(f"| {s.get('cn', x['id'])} | {s.get('en', '')} | {x.get('weight')} | {s.get('group', '')} | {kw} |")
    else:
        L.append("（未选。跑 `survey/index.html` 后 merge 一次就会填上）")
    L.append("")

    L.append("## 三、色板")
    L.append("")
    p = data.get("palette", {})
    for label, key in (("主色", "primary"), ("点缀", "accent"), ("中性", "neutral"), ("避开", "avoid")):
        vals = p.get(key) or []
        L.append(f"- **{label}**：{'　'.join('`' + v + '`' for v in vals) if vals else '（空）'}")
    L.append("")

    L.append("## 四、找图关键词")
    L.append("")
    kk = data.get("keywords", {})
    pos = kk.get("positive") or []
    neg = kk.get("negative") or []
    L.append(f"- **正向**（{len(pos)} 个）：{', '.join(pos) if pos else '（空）'}")
    L.append(f"- **排除**：{', '.join(neg) if neg else '（空）'}")
    L.append("")

    L.append("## 五、硬规则（优先级最高）")
    L.append("")
    for i, hr in enumerate(data.get("hard_rules", []), 1):
        L.append(f"{i}. **{hr['rule']}**")
        L.append(f"   - 为什么：{hr.get('why', '—')}")
        L.append(f"   - 原话：{hr.get('evidence', '—')}（{hr.get('date')}）")
    if not data.get("hard_rules"):
        L.append("（无）")
    L.append("")

    L.append("## 六、场景")
    L.append("")
    ctxs = data.get("contexts") or {}
    rows = [(k, v) for k, v in ctxs.items() if v]
    if rows:
        for k, v in rows:
            L.append(f"- **{k}**：{v.get('notes', '')}（证据：{v.get('evidence', '—')}）")
    else:
        L.append("（尚未按场景校准。壁纸 ≠ PPT ≠ 网页，不要互相套用）")
    L.append("")

    L.append("## 七、证据日志（最近 12 条）")
    L.append("")
    L.append("| 日期 | 来源 | 强度 | 观察 | 影响 |")
    L.append("|---|---|---|---|---|")
    for ev in data.get("evidence", [])[-12:][::-1]:
        sig = (ev.get("signal") or "").replace("|", "／")
        eff = (ev.get("effect") or "").replace("|", "／")
        L.append(f"| {ev.get('date')} | {ev.get('source')} | {ev.get('strength')} | {sig} | {eff} |")
    L.append("")
    L.append("---")
    L.append("")
    L.append("想让画像更准：打开 `survey/index.html` 选一遍 → 导出 JSON → `profile_tool.py merge`。")
    L.append("想让它更真：每次设计交付后，把「他说了什么」追加一条证据，**弱证据必须标 weak**。")

    PROFILE_MD.write_text("\n".join(L) + "\n", encoding="utf-8")
    print(f"已生成 {PROFILE_MD.relative_to(ROOT)}（{len(L)} 行）")
    return 0


# --------------------------------------------------------------------------- CLI
def fail(msg: str):
    print("FAIL", msg)
    raise SystemExit(1)


def main() -> int:
    ap = argparse.ArgumentParser(description="审美画像工具（零依赖）")
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("validate", help="校验 profile 结构")

    m = sub.add_parser("merge", help="合并调研页导出的 JSON")
    m.add_argument("--input", required=True, help="调研页导出的 JSON 路径")
    m.add_argument("--dry-run", action="store_true", help="只显示将要发生的改动，不写盘")

    sub.add_parser("render", help="从 JSON 生成人读摘要 profile.md")

    args = ap.parse_args()
    return {"validate": cmd_validate, "merge": cmd_merge, "render": cmd_render}[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())
