# aesthetic-profile · 审美画像

> 让 AI 记住你喜欢什么，而不是每次设计都从「请问你想要什么风格」开始。

[English](README.en.md) ｜ 中文

## 这解决什么问题

每次让 AI 做视觉（网页配色、壁纸、头像、海报、PPT、封面），它要么给你一套通用的「科技蓝」模板，
要么反问你一堆问题，问完下次又忘。原因很简单：**审美没有被存成机器能读的东西。**

这个 skill 干三件事：

1. **量出来** — 一个本地调研页，327 种可用作壁纸 / 头像 / 设计配图的视觉风格 × 14 大类，
   配真实图片、可点开放大、可搜索筛选。
2. **存下来** — 结果合并成一份带版本号、带证据的 JSON 画像，agent 直接读它做决策。
3. **长起来** — 每次设计交付后追加一条证据，画像随使用变准；旧的判断被推翻也保留痕迹。

## 为什么不是「一次问卷定终身」

用户原话：**「这个喜好是不断丰富的，不是一成不变的」**。

所以画像里每个值都必须能指回一条证据：

| 强度 | 含义 | 能做什么 |
|---|---|---|
| `strong` | 他主动说的偏好 / 明确否定 | 直接改轴值、加硬规则 |
| `medium` | 他在我给的选项里选了一个 | 调权重，不加硬规则 |
| `weak` | 他只说「行」，或我推断的 | **只记录，不改任何值** |

没有证据的字段一律 `null`，**禁止填 50 假装中性**。这条是整个设计里最重要的约束 ——
假画像比没画像更糟，因为后来的人会以为它被确认过，从而不再问。

## 快速开始

```bash
git clone https://github.com/kuangketongxue/aesthetic-profile.git
cd aesthetic-profile

# 1. 打开调研页（双击即可，无需服务器、无需联网）
#    survey/index.html  →  选风格 / 点图放大  →  生成画像  →  导出 JSON

# 2. 合并进画像（自动算轴值、色板、关键词，并升版本）
python scripts/profile_tool.py merge --input ~/Downloads/aesthetic-survey-2026-11-12.json

# 3. 看结果
python scripts/profile_tool.py validate
python scripts/profile_tool.py render      # 生成 profile/profile.md
```

零依赖：只用 Python 标准库，Python 3.9+。Windows / macOS / Linux 都能跑。

## agent 怎么用它

把整个目录放进 `~/.workbuddy/skills/`（或 Claude Code 的 skills 目录）即可，`SKILL.md` 会被自动加载。

它规定了一个三步流程：

1. **读画像** —— 先看 `hard_rules`（硬约束优先于喜好），再看当前场景有没有单独校准过
2. **翻译成决策** —— 轴值 → 配色 / 明暗 / 繁简 / 找图关键词，见 `references/design-checklist.md`
3. **回写证据** —— 交付后追加一条，这是画像能长大的唯一原因

还写了一串硬性禁令：不许编造偏好、不许把「他没反对」当「他喜欢」、不许跨场景套用（壁纸偏暗 ≠ PPT 要暗）。

## 目录

```
SKILL.md                       agent 入口：何时读、怎么读、怎么回写
profile/
  aesthetic-profile.json       画像本体（唯一真身）
  profile.schema.json          数据结构约束（含「null 是合法值」的说明）
  profile.md                   人读摘要（由 render 生成）
survey/
  index.html                   调研页：327 风格 / 14 大类 / 点图放大 / 导出 JSON
  styles.json                  风格清单（真身）
  picks.json                   25 张视觉偏好图数据
  images/                      39 张本地参考图（已压缩，全部可离线打开）
references/
  design-checklist.md          画像 → 具体设计数值
  enrichment.md                证据、衰减、冲突、版本语义
  style-catalog.md             14 大类索引（快速查 id 与关键词）
scripts/
  profile_tool.py              validate / merge / render
  build_survey_js.py           JSON → 浏览器可直接用的 .js
  build_catalog.py             生成 style-catalog.md
tests/
  test_profile_tool.py         22 个测试，守护「画像不说谎」
```

## 设计取向（为什么长这样）

- **不做打分问卷**。10 个问题算不出审美；真实的做法是给全景让人挑，再问少数几个能定轴的二选一。
- **8 个连续轴而非标签**。标签（「极简」「赛博」）互斥且含混；轴值（0-100）能组合、能迁移、能算距离。
- **硬规则单列**。偏好是「倾向」，硬规则是「底线」；混在一起就会用「他喜欢暗色」去解释「不能用示意图」。
- **分场景**。同一个人的壁纸和 PPT 常常相反，`contexts` 彼此独立。
- **可 fork**。画像属于个人，仓库属于模板：改 `owner`、重跑调研，就是另一个人的画像。

## 已知局限

- 调研页只有 4 道二选一，能定的轴有限（温度 / 明暗 / 繁简 / 写实度），其余 4 个轴（饱和、对比、有机、年代）
  需要靠后续设计反馈补。**这是设计取舍，不是遗漏** —— 多问会让人选择疲劳。
- 风格参考图是图库摄影，不是艺术史原作，只能表达氛围，不能代表流派技法。
- 327 种不可能覆盖「所有」风格。清单是活的：新风格自己做一次调研就能加进来。

## 图片授权

参考图来自 [Unsplash](https://unsplash.com/license) 与 [Pexels](https://www.pexels.com/license) 免费可商用图库，
已全部下载到本地并逐张验证可打开，仅作氛围参考。清单与匹配数据以 MIT 协议开源；图片本身遵循各自图库协议。

## License

MIT © [kuangketongxue](https://github.com/kuangketongxue)
