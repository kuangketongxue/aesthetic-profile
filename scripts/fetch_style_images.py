#!/usr/bin/env python3
"""按风格关键词抓真实示例图，并写回 styles.json。

背景：327 种风格里，只有 33 种能用手头已有的图验证。其余如果硬凑一张，
就会「描述说白云羽毛、图里是星空」，这比不给图更糟。所以要么没有图，
要么是搜来的、看得懂的照片。

用法（key 只从环境变量或文件读，绝不写进代码/仓库）：

    set PEXELS_KEY=xxxx            # Windows cmd
    export PEXELS_KEY=xxxx         # bash
    python scripts/fetch_style_images.py --provider pexels --max 180

    # 或把 key 放在仓库外的文件里
    python scripts/fetch_style_images.py --provider pexels --key-file ../_secrets/pexels.key

额度（官方）：Pexels 200 次/小时；Unsplash 50 次/小时。
所以默认每次跑 180 个就停，把进度写进 survey/.fetch-progress.json，下次接着跑。

用 --dry-run 先看会搜什么词，不消耗额度。
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import urllib.parse
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STYLES = ROOT / "survey" / "styles.json"
IMGDIR = ROOT / "survey" / "images"
PROGRESS = ROOT / "survey" / ".fetch-progress.json"
CREDITS = ROOT / "survey" / "image-credits.json"

UA = "aesthetic-profile/0.1 (+https://github.com/kuangketongxue/aesthetic-profile)"
MAX_EDGE = 1200
QUALITY = 78


def die(msg: str) -> None:
    print("FAIL", msg)
    raise SystemExit(1)


def read_key(args) -> str:
    if args.key_file:
        p = Path(args.key_file)
        if not p.exists():
            die(f"key 文件不存在：{p}")
        return p.read_text(encoding="utf-8").strip()
    env = "PEXELS_KEY" if args.provider == "pexels" else "UNSPLASH_KEY"
    v = os.environ.get(env, "").strip()
    if not v:
        die(f"没有 key。设环境变量 {env}，或用 --key-file 指向仓库外的文件。\n"
            f"     （Pexels 免费 key：https://www.pexels.com/api/ —— 不写进代码、不进仓库）")
    return v


def http_json(url: str, headers: dict) -> tuple[int, dict]:
    cmd = ["curl", "-s", "--noproxy", "*", "-w", "\n%{http_code}", url,
           "-H", "User-Agent: " + UA]
    for k, v in headers.items():
        cmd += ["-H", f"{k}: {v}"]
    r = subprocess.run(cmd, capture_output=True, timeout=60)
    out = r.stdout.decode("utf-8", "replace")
    body, _, code = out.rpartition("\n")
    try:
        return int(code or 0), json.loads(body) if body.strip() else {}
    except json.JSONDecodeError:
        return int(code or 0), {}


def download(url: str, dest: Path) -> int:
    tmp = dest.with_suffix(".part")
    cmd = ["curl", "-sL", "--noproxy", "*", "-A", UA, "-o", str(tmp),
           "-w", "%{http_code}", "--max-time", "90", url]
    r = subprocess.run(cmd, capture_output=True, timeout=120)
    code = int(r.stdout.decode().strip() or 0)
    if code != 200 or not tmp.exists() or tmp.stat().st_size < 4096:
        if tmp.exists():
            tmp.unlink()
        return code
    tmp.replace(dest)
    return 200


def shrink(path: Path) -> bool:
    """压到 MAX_EDGE 并校验能解码。PIL 缺失时退化为文件头检查。"""
    try:
        from PIL import Image
    except ImportError:
        with path.open("rb") as f:
            return f.read(2) == b"\xff\xd8"
    try:
        im = Image.open(path)
        im.load()
        im = im.convert("RGB")
        w, h = im.size
        if max(w, h) > MAX_EDGE:
            r = MAX_EDGE / max(w, h)
            im = im.resize((round(w * r), round(h * r)), Image.LANCZOS)
        im.save(path, "JPEG", quality=QUALITY, optimize=True, progressive=True)
        return True
    except Exception as e:
        print("   图片解码失败：", e)
        return False


def query_for(style: dict) -> str:
    kws = style.get("kw") or []
    return " ".join(kws[:2]) if kws else style.get("en", "")


def search_pexels(q: str, key: str) -> tuple[int, list]:
    url = ("https://api.pexels.com/v1/search?query=%s&per_page=3&orientation=landscape"
           % urllib.parse.quote(q))
    code, j = http_json(url, {"Authorization": key})
    if code != 200:
        return code, []
    out = []
    for p in (j.get("photos") or []):
        out.append({
            "file": (p.get("src") or {}).get("large") or (p.get("src") or {}).get("original"),
            "alt": (p.get("alt") or "").strip(),
            "page": p.get("url", ""),
            "author": (p.get("photographer") or "").strip(),
            "source": "Pexels",
        })
    return code, out


def search_unsplash(q: str, key: str) -> tuple[int, list]:
    url = ("https://api.unsplash.com/search/photos?query=%s&per_page=3&orientation=landscape"
           % urllib.parse.quote(q))
    code, j = http_json(url, {"Authorization": "Client-ID " + key})
    if code != 200:
        return code, []
    out = []
    for p in (j.get("results") or []):
        u = ((p.get("urls") or {}).get("regular") or "")
        out.append({
            "file": u.split("?")[0] + "?w=1200&q=78&fm=jpg" if u else "",
            "alt": (p.get("alt_description") or p.get("description") or "").strip(),
            "page": (p.get("links") or {}).get("html", ""),
            "author": (p.get("user") or {}).get("name", ""),
            "source": "Unsplash",
        })
    return code, out


def main() -> int:
    ap = argparse.ArgumentParser(description="按风格关键词抓真实示例图")
    ap.add_argument("--provider", choices=["pexels", "unsplash"], default="pexels")
    ap.add_argument("--key-file", help="指向仓库外保存 key 的文件")
    ap.add_argument("--max", type=int, default=180, help="本次最多抓多少个（额度保护）")
    ap.add_argument("--sleep", type=float, default=1.0, help="每次请求间隔秒数")
    ap.add_argument("--overwrite", action="store_true", help="连已有的图也重抓")
    ap.add_argument("--dry-run", action="store_true", help="只打印搜索词，不消耗额度")
    args = ap.parse_args()

    data = json.loads(STYLES.read_text(encoding="utf-8"))
    IMGDIR.mkdir(parents=True, exist_ok=True)
    progress = json.loads(PROGRESS.read_text(encoding="utf-8")) if PROGRESS.exists() else {"done": {}}
    credits = json.loads(CREDITS.read_text(encoding="utf-8")) if CREDITS.exists() else {}

    todo = [s for s in data["styles"]
            if args.overwrite or s.get("imgKind") != "example" or not s.get("img")]
    print(f"待配图 {len(todo)} / {len(data['styles'])}，本次上限 {args.max}")
    if args.dry_run:
        for s in todo[:30]:
            print(f"  {s['id']} {s['cn']:12s} → {query_for(s)}")
        print(f"  …共 {len(todo)} 条（--dry-run 不请求接口）")
        return 0
    if not todo:
        print("全部都有图了。")
        return 0

    key = read_key(args)
    search = search_pexels if args.provider == "pexels" else search_unsplash
    ok = fail = 0
    quota_hit = False

    for i, s in enumerate(todo[: args.max], 1):
        q = query_for(s)
        code, cands = search(q, key)
        if code == 429:
            print("  额度用尽（429），本轮停止。等一小时后重跑即可续上。")
            quota_hit = True
            break
        if code != 200:
            print(f"  [{i}] {s['id']} 搜索失败 HTTP {code}，跳过")
            fail += 1
            continue

        picked = None
        for c in cands:
            if not c["file"]:
                continue
            dest = IMGDIR / f"{s['id']}.jpg"
            got = download(c["file"], dest)
            if got == 200 and shrink(dest):
                picked = c
                break
        if not picked:
            print(f"  [{i}] {s['id']} {s['cn']} 没有可用图")
            fail += 1
            continue

        s["img"] = f"images/{s['id']}.jpg"
        s["imgKind"] = "example"
        s["imgNote"] = (f'{picked["source"]} 实拍：{picked["alt"]}' if picked["alt"]
                        else f'{picked["source"]} 实拍')
        credits[s["id"]] = {"source": picked["source"], "author": picked["author"],
                            "page": picked["page"], "query": q}
        progress["done"][s["id"]] = q
        ok += 1
        print(f"  [{i}] {s['id']} {s['cn']:12s} ← {q[:40]}")

        STYLES.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        CREDITS.write_text(json.dumps(credits, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        PROGRESS.write_text(json.dumps(progress, ensure_ascii=False, indent=1), encoding="utf-8")
        time.sleep(args.sleep)

    left = len([x for x in data["styles"] if x.get("imgKind") != "example"])
    print(f"\n本轮成功 {ok}，失败 {fail}，剩余待配图 {left}")
    if quota_hit:
        print("额度用尽：等一小时再跑同一条命令即可继续（进度已存）。")
    if ok:
        print("下一步：python scripts/build_survey_js.py && python scripts/build_catalog.py")
    return 0 if ok or not fail else 1


if __name__ == "__main__":
    sys.exit(main())
