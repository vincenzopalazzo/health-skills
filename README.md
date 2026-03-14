# claude-skills

[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)

Custom Claude skills for body recomposition tracking & AI dataset generation — installable as a Claude Code plugin marketplace and compatible with [Goose](https://block.github.io/goose/).

## Available Skills

### corpo

Body recomposition tracker that:

- Parses nutritional and training program PDFs to extract body composition data (weight, fat mass, lean mass, BMI)
- Tracks body composition trends over time across multiple programs
- Manages supplement and compound cycle history with health risk assessment
- Calculates daily kcal and macronutrient estimates from Italian meal plans
- Detects training phases (cutting, bulking, PCT/recovery, maintenance)
- Generates interactive HTML dashboards with Chart.js visualizations
- Maintains persistent memory for next steps, nutritionist recommendations, and bloodwork history
- Integrates with Garmin wearable data for health tracking

## Installation

### Claude Code

**Marketplace:**

```
/plugin marketplace add vincenzopalazzo/claude-skills
/plugin install corpo@vincenzopalazzo-skills
```

**Manual (global):**

```bash
git clone https://github.com/vincenzopalazzo/skills.git
cp -r skills/plugins/corpo/.claude-plugin/skills/corpo ~/.claude/skills/corpo
```

**Project-level:**

```bash
mkdir -p .claude/skills
cp -r skills/plugins/corpo/.claude-plugin/skills/corpo .claude/skills/corpo
```

### Goose

This repo includes a `skills/` directory at the root that follows the [Goose skills convention](https://block.github.io/goose/docs/guides/context-engineering/using-skills/). Goose discovers skills from any of these directories (in priority order):

| Path | Scope |
|------|-------|
| `~/.config/goose/skills/` | Global, Goose-specific |
| `~/.config/agents/skills/` | Global, portable across AI agents |
| `~/.claude/skills/` | Global, shared with Claude Code |
| `./.goose/skills/` | Project-level, Goose-specific |
| `./.agents/skills/` | Project-level, portable across AI agents |
| `./.claude/skills/` | Project-level, shared with Claude Code |

**Global install (Goose-specific):**

```bash
git clone https://github.com/vincenzopalazzo/skills.git
cp -r skills/skills/corpo ~/.config/goose/skills/corpo
```

**Global install (portable across agents):**

```bash
cp -r skills/skills/corpo ~/.config/agents/skills/corpo
```

**Project-level:**

```bash
mkdir -p .goose/skills
cp -r skills/skills/corpo .goose/skills/corpo
```

## Repo Structure

```
.
├── .claude-plugin/
│   └── marketplace.json          # Claude Code plugin marketplace index
├── plugins/
│   └── corpo/
│       └── .claude-plugin/
│           ├── plugin.json       # Claude Code plugin metadata
│           └── skills/
│               └── corpo/
│                   ├── SKILL.md  # Skill definition (shared by both)
│                   └── scripts/  # Python scripts
├── skills/
│   └── corpo -> ../plugins/corpo/.claude-plugin/skills/corpo
│                                 # Symlink for Goose compatibility
├── LICENSE
└── README.md
```

The `skills/` directory is a symlink-based mirror of the canonical skill files under `plugins/`, so both Claude Code and Goose always use the same source.

## Adding More Skills

More skills will be added over time. Each skill lives under `plugins/<skill-name>/` with a corresponding symlink in `skills/` for Goose compatibility.

## License

Apache 2.0 — Copyright Vincenzo Palazzo
