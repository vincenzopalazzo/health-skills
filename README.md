# skills

[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)

A collection of personal AI skills — installable as a Claude Code plugin marketplace and compatible with [Goose](https://block.github.io/goose/).

## Available Skills

| Skill | Description |
|-------|-------------|
| [corpo](plugins/corpo) | Body recomposition tracker — parses nutritional/training PDFs, tracks body composition, manages supplement cycles with health risk assessment, and generates interactive dashboards |

## Installation

### Claude Code

**Marketplace:**

```
/plugin marketplace add vincenzopalazzo/skills
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
│   └── <skill>/
│       └── .claude-plugin/
│           ├── plugin.json       # Claude Code plugin metadata
│           └── skills/
│               └── <skill>/
│                   ├── SKILL.md  # Skill definition (shared by both)
│                   └── scripts/  # Supporting scripts
├── skills/
│   └── <skill> -> ../plugins/<skill>/.claude-plugin/skills/<skill>
│                                 # Symlink for Goose compatibility
├── LICENSE
└── README.md
```

The `skills/` directory is a symlink-based mirror of the canonical skill files under `plugins/`, so both Claude Code and Goose always use the same source.

## Adding More Skills

More skills will be added over time. Each skill lives under `plugins/<skill-name>/` with a corresponding symlink in `skills/` for Goose compatibility.

## License

Apache 2.0 — Copyright Vincenzo Palazzo
