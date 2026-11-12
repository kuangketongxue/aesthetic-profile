# aesthetic-profile

> Make AI remember what you find beautiful — instead of asking "what style do you want?" every single time.

[中文](README.md) ｜ English

## The problem

Every time you ask an AI to design something — a landing page, a wallpaper, an avatar, a poster, a deck cover —
it either hands you a generic "tech blue" template or interviews you from scratch. And then forgets.

The root cause is simple: **your taste was never stored in a machine-readable form.**

This skill fixes that in three moves:

1. **Measure it** — a local survey page: 327 visual styles across 14 families, real reference images,
   click-to-zoom, searchable and filterable. Double-click to open; no server, no network.
2. **Store it** — the answers merge into a versioned JSON profile with an evidence log. Agents read it and decide.
3. **Grow it** — after every design delivery, one more piece of evidence. The profile gets sharper with use,
   and overturned judgments stay on the record.

## Why not a one-shot questionnaire

The user's words: *"This preference keeps growing, it's not fixed."*

So every value in the profile must trace back to a piece of evidence:

| Strength | Meaning | Allowed to do |
|---|---|---|
| `strong` | They stated a preference, or explicitly rejected something | Set axis values, add hard rules |
| `medium` | They picked one of the options I offered | Adjust weights only |
| `weak` | They just said "ok", or I inferred it | **Record only — change nothing** |

Fields without evidence stay `null`. **Filling in 50 as a "neutral default" is forbidden.**
This is the single most important rule in the design: a fake profile is worse than none,
because the next agent will assume it was confirmed and stop asking.

## Quick start

```bash
git clone https://github.com/kuangketongxue/aesthetic-profile.git
cd aesthetic-profile

# 1. Open survey/index.html (double-click — no server, no network needed)
#    pick styles → zoom images → generate → export JSON

# 2. Merge into the profile (computes axes, palette, keywords; bumps version)
python scripts/profile_tool.py merge --input ~/Downloads/aesthetic-survey-2026-11-12.json

# 3. Inspect
python scripts/profile_tool.py validate
python scripts/profile_tool.py render      # writes profile/profile.md
```

Zero dependencies — Python standard library only, Python 3.9+. Works on Windows, macOS and Linux.

## For agents

Drop the folder into `~/.workbuddy/skills/` (or your Claude Code skills directory); `SKILL.md` is autoloaded.

It enforces a three-step loop: **read the profile** (hard rules first) → **translate to decisions**
(see `references/design-checklist.md`) → **write evidence back**. Plus a list of bans:
don't invent preferences, don't upgrade "they didn't object" to "they like it",
don't reuse wallpaper taste for slides.

## Structure

```
SKILL.md                      entry point: when to read, how to read, how to write back
profile/
  aesthetic-profile.json      the profile itself (single source of truth)
  profile.schema.json         data contract (note: null is a legal value)
  profile.md                  human-readable summary (generated)
survey/
  index.html                  327 styles / 14 families / zoom / JSON export
  styles.json                 style catalog (source of truth)
  picks.json                  25 visual-preference images
  images/                     39 local reference images (compressed, offline-ready)
references/
  design-checklist.md         profile → concrete design numbers
  enrichment.md               evidence, decay, conflicts, versioning
  style-catalog.md            index of all 327 styles with ids and keywords
scripts/
  profile_tool.py             validate / merge / render
  build_survey_js.py          JSON → browser-friendly .js
  build_catalog.py            regenerate style-catalog.md
tests/
  test_profile_tool.py        22 tests guarding "the profile must not lie"
```

## Design choices

- **No scored questionnaire.** Ten questions can't capture taste. Show the full field, let people pick,
  then ask a few binary questions that actually pin down an axis.
- **Eight continuous axes instead of tags.** Tags are mutually exclusive and ambiguous;
  axis values combine, transfer and can be compared.
- **Hard rules kept separate.** Preferences are tendencies, hard rules are floors. Mixing them
  leads to justifying "no hand-drawn diagrams" with "they like dark colors".
- **Per-context.** The same person's wallpaper and slide deck often disagree. `contexts` are independent.
- **Forkable.** The profile belongs to a person; the repo is a template.

## Known limitations

- Only 4 binary questions, so only 4 of 8 axes can be measured by the survey. The rest
  (saturation, contrast, organic, era) must come from real design feedback. That's a deliberate trade-off —
  more questions cause choice fatigue.
- Reference images are stock photography, not art-historical originals: they convey mood, not technique.
- 327 styles can't cover "all" styles. The catalog is alive: run a new survey round to add more.

## Image licensing

Reference images come from [Unsplash](https://unsplash.com/license) and
[Pexels](https://www.pexels.com/license) — free for commercial use, attribution not required.
All were downloaded locally and each verified to open. The catalog and matching data are MIT-licensed;
the images remain under their respective library licenses.

## License

MIT © [kuangketongxue](https://github.com/kuangketongxue)
