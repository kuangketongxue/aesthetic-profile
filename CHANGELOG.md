# 变更日志

格式参考 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)；版本号遵循语义化。

画像本身的版本单独记在 `profile/aesthetic-profile.json` 的 `profile_version`，
这里记的是 **skill / 工具链**的版本，两者不要混。

## [0.1.0] - 2026-11-12

首个可用版本。

### 新增

- `SKILL.md`：三步流程（读画像 → 翻译决策 → 回写证据）+ 六条硬性禁令
- `profile/aesthetic-profile.json`：版本化画像，8 个连续轴、liked/disliked、硬规则、分场景、证据日志
- `profile/profile.schema.json`：数据契约；**`null` 是合法值**，未测量就不许填
- `survey/index.html`：327 种视觉风格 / 14 大类，搜索筛选、点图放大灯箱、多选、
  4 道二选一、生成画像、导出机器可读 JSON
- `survey/styles.json` + `picks.json`：风格清单与 25 张视觉偏好图（真身）
- `survey/images/`：39 张本地参考图（压缩至 6.3MB，全部离线可打开）
- `references/design-checklist.md`：轴值 → 配色 / 明暗 / 繁简 / 找图的具体数值
- `references/enrichment.md`：证据强度、衰减、冲突处理、版本语义、禁止事项
- `references/style-catalog.md`：327 条索引（自动生成）
- `scripts/profile_tool.py`：`validate` / `merge` / `render`，零依赖
- `scripts/build_survey_js.py`：JSON → 浏览器可用的 `.js`，带 `--check` 防漂移
- `scripts/build_catalog.py`：生成风格索引
- `tests/test_profile_tool.py`：22 个测试，防「画像说谎」「重复合并升版本」「JS 与 JSON 漂移」

### 设计取舍

- 只做 4 道二选一，放弃一次测满 8 个轴 —— 避免选择疲劳，剩余轴留给真实设计反馈
- 调研页不依赖任何远程资源，双击即用（`file://` 下 `fetch` 会被拦，所以数据用 `<script>` 注入）
