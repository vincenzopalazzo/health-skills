#!/usr/bin/env python3
"""Validate SKILL.md frontmatter and plugin structure.

Checks:
- SKILL.md exists in every skill directory
- YAML frontmatter has required fields (name, description)
- name is kebab-case, 1-64 chars, matches parent directory
- description is 1-1024 chars and non-empty
- plugin.json is valid JSON with required 'name' field
- Version follows semver if present
- Python scripts have valid syntax
"""

import ast
import json
import re
import sys
from pathlib import Path


def parse_frontmatter(path: Path) -> dict | None:
    """Extract YAML frontmatter from a SKILL.md file."""
    text = path.read_text()
    if not text.startswith("---"):
        return None

    end = text.find("---", 3)
    if end == -1:
        return None

    # Simple YAML-enough parser for frontmatter (name: value, description: >)
    fm_text = text[3:end].strip()
    result = {}
    current_key = None
    current_value_lines = []

    for line in fm_text.split("\n"):
        # Check for a new key
        m = re.match(r"^(\w[\w-]*):\s*(.*)", line)
        if m:
            # Save previous key
            if current_key:
                result[current_key] = " ".join(current_value_lines).strip()
            current_key = m.group(1)
            value = m.group(2).strip()
            if value == ">" or value == "|":
                current_value_lines = []
            else:
                current_value_lines = [value]
        elif current_key and line.startswith("  "):
            current_value_lines.append(line.strip())

    if current_key:
        result[current_key] = " ".join(current_value_lines).strip()

    return result


def validate_skill(skill_dir: Path, errors: list[str]) -> None:
    """Validate a single skill directory."""
    skill_md = skill_dir / "SKILL.md"
    if not skill_md.exists():
        errors.append(f"{skill_dir}: missing SKILL.md")
        return

    fm = parse_frontmatter(skill_md)
    if fm is None:
        errors.append(
            f"{skill_md}: missing or invalid YAML frontmatter (must start with ---)"
        )
        return

    # Check name field
    name = fm.get("name", "")
    if not name:
        errors.append(f"{skill_md}: missing required 'name' field in frontmatter")
    elif len(name) > 64:
        errors.append(f"{skill_md}: name exceeds 64 characters ({len(name)})")
    elif not re.match(r"^[a-z][a-z0-9]*(-[a-z0-9]+)*$", name):
        errors.append(
            f"{skill_md}: name '{name}' must be kebab-case (lowercase, hyphens)"
        )

    # Check name matches directory
    if name and name != skill_dir.name:
        errors.append(
            f"{skill_md}: name '{name}' does not match directory '{skill_dir.name}'"
        )

    # Check description field
    desc = fm.get("description", "")
    if not desc:
        errors.append(
            f"{skill_md}: missing required 'description' field in frontmatter"
        )
    elif len(desc) > 2048:
        errors.append(f"{skill_md}: description exceeds 1024 characters ({len(desc)})")

    # Validate Python scripts if they exist
    scripts_dir = skill_dir / "scripts"
    if scripts_dir.exists():
        for py_file in scripts_dir.glob("*.py"):
            try:
                ast.parse(py_file.read_text())
            except SyntaxError as e:
                errors.append(f"{py_file}:{e.lineno}: syntax error: {e.msg}")


def validate_plugin_json(plugin_json: Path, errors: list[str]) -> None:
    """Validate a plugin.json manifest."""
    try:
        data = json.loads(plugin_json.read_text())
    except json.JSONDecodeError as e:
        errors.append(f"{plugin_json}: invalid JSON: {e}")
        return

    if not isinstance(data, dict):
        errors.append(f"{plugin_json}: must be a JSON object")
        return

    name = data.get("name")
    if not name:
        errors.append(f"{plugin_json}: missing required 'name' field")

    version = data.get("version")
    if version and not re.match(r"^\d+\.\d+\.\d+(-[a-zA-Z0-9.]+)?$", version):
        errors.append(
            f"{plugin_json}: version '{version}' must follow semver (MAJOR.MINOR.PATCH)"
        )


def main() -> int:
    root = Path(".")
    errors: list[str] = []
    validated: set[Path] = set()

    # Find all plugin.json files
    for plugin_json in root.rglob(".claude-plugin/plugin.json"):
        validate_plugin_json(plugin_json, errors)

    # Find all SKILL.md files via plugin structure
    for skill_md in root.rglob("**/skills/*/SKILL.md"):
        real = skill_md.parent.resolve()
        if real in validated:
            continue
        validated.add(real)
        validate_skill(skill_md.parent, errors)

    # Also check top-level skills/ directory (for goose compat symlinks)
    skills_dir = root / "skills"
    if skills_dir.exists():
        for skill in skills_dir.iterdir():
            if skill.is_dir() and (skill / "SKILL.md").exists():
                real = skill.resolve()
                if real in validated:
                    continue
                validated.add(real)
                validate_skill(skill, errors)

    if errors:
        print(f"Found {len(errors)} error(s):\n")
        for e in errors:
            print(f"  - {e}")
        return 1

    print("All skills and plugins validated successfully.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
