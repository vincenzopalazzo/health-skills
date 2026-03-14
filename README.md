# claude-skills

[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)

Custom Claude skills for body recomposition tracking & AI dataset generation — installable as a Claude Code plugin marketplace.

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

### Method 1: Claude Code Marketplace

```
/plugin marketplace add vincenzopalazzo/claude-skills
/plugin install corpo@vincenzopalazzo-skills
```

### Method 2: Manual Clone (Global)

```bash
git clone https://github.com/vincenzopalazzo/claude-skills.git
cp -r claude-skills/plugins/corpo/.claude-plugin/skills/corpo ~/.claude/skills/corpo
```

### Method 3: Project-Level

```bash
git clone https://github.com/vincenzopalazzo/claude-skills.git
mkdir -p .claude/skills
cp -r claude-skills/plugins/corpo/.claude-plugin/skills/corpo .claude/skills/corpo
```

## Adding More Skills

More skills will be added over time. Each skill lives under `plugins/<skill-name>/` and follows the Claude Code plugin structure.

## License

Apache 2.0 — Copyright Vincenzo Palazzo
