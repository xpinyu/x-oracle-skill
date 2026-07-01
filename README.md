# x-oracle

An [Agent Skill](https://skills.sh) for BaZi-based uncertainty-resolution interviews — your AI agent reads birth charts, maps stuck points to Four Pillars evidence, and helps you clarify decisions.

Supports: **Hermes Agent**, **Claude Code**, **Codex**, **Cursor**, and 60+ more via [`npx skills`](https://github.com/vercel-labs/skills).

## What it does

X-Oracle is not a generic destiny report generator. It's an **uncertainty-resolution interview** powered by BaZi (Four Pillars of Destiny / 八字):

1. Calculate your core chart from birth date/time
2. Map your current stuck point to chart evidence (career, relationship, timing, relocation, etc.)
3. Calibrate hypotheses against your real experience
4. Give you a 30/90-day action window with blind-spot warnings

Deep reports cover Four Pillars, Day Master, Ten Gods, Five-Element flow, Luck Cycles, and annual timing. Optional add-ons: Zi Wei Dou Shu (紫微斗数), I Ching (周易), Tarot.

## Install

```bash
npx skills add xpinyu/x-oracle-skill
```

Or target specific agents:

```bash
npx skills add xpinyu/x-oracle-skill -a hermes-agent -a claude-code -a cursor
```

## Usage

Just tell your agent you want a reading. The skill activates when you say things like:

- "x-oracle"
- "帮我排个八字"
- "看看我的命盘"
- "最近一直纠结要不要换工作"
- "这段关系我不知道还要不要继续"
- "帮我用八字分析一下事业方向"

The agent will ask for your birth date and time, then conduct a **focused interview** — not a broad life report, but a conversation anchored in chart evidence.

## Features

- **BaZi core chart calculation** — Four Pillars, Day Master, Ten Gods, Five-Element balance, branch interactions (合冲刑害)
- **Uncertainty interview mode** — start from your stuck point, not a generic report
- **Evidence-first writing** — every claim tied to specific chart signals with classical principles named
- **Calibration questions** — the agent tests hypotheses against your real experience, not astrology clichés
- **30/90-day action windows** — specific, non-deterministic experiments, not fate enforcement
- **Zi Wei Dou Shu** — optional life-domain mapping (career palace, wealth palace, spouse palace)
- **Tarot / I Ching** — symbolic add-ons for current-question psychology (never replace BaZi)
- **Python scripts included** — `calculate_core_chart.py` and `calculate_ziwei.py` for AI agents that can execute code
- **Cross-platform** — works with Hermes, Claude Code, Codex, Cursor, Windsurf, Zed, Gemini CLI, and 60+ others

## Boundaries

- No absolute claims (guaranteed wealth, divorce, illness, disaster, death)
- No deterministic medical, legal, or investment advice
- Lower confidence marked when birth time is approximate or unknown
- Tarot and I Ching are symbolic add-ons — BaZi remains the reasoning spine

## Scripts

Two Python scripts are included for AI agents that support code execution:

```bash
pip install lunar_python  # required for calculate_core_chart.py
pip install purplestar    # or iztro-py, for calculate_ziwei.py
```

```bash
python skills/x-oracle/scripts/calculate_core_chart.py \
  --birth-date 1990-01-01 --birth-time 08:30 --gender male --pretty
```

## License

MIT
