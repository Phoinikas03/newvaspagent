#!/usr/bin/env python3
"""
快速验证 SKILL.md 是否符合基本格式要求。

用法: python scripts/quick_validate.py <skill目录>
退出码: 0 = 合法，1 = 不合法
"""
import sys
import re
import yaml
from pathlib import Path


def validate_skill(skill_path) -> tuple[bool, str]:
    skill_path = Path(skill_path)
    skill_md = skill_path / "SKILL.md"

    if not skill_md.exists():
        return False, "SKILL.md 文件不存在"

    content = skill_md.read_text(encoding="utf-8")

    if not content.startswith("---"):
        return False, "缺少 YAML frontmatter（需以 --- 开头）"

    match = re.match(r"^---\n(.*?)\n---", content, re.DOTALL)
    if not match:
        return False, "frontmatter 格式非法（未找到闭合的 ---）"

    try:
        fm = yaml.safe_load(match.group(1))
        if not isinstance(fm, dict):
            return False, "frontmatter 必须是 YAML 字典"
    except yaml.YAMLError as e:
        return False, f"frontmatter YAML 解析失败：{e}"

    ALLOWED = {"name", "description", "license", "allowed-tools", "metadata", "compatibility", "version"}
    unexpected = set(fm.keys()) - ALLOWED
    if unexpected:
        return False, (
            f"frontmatter 含非法字段：{', '.join(sorted(unexpected))}。"
            f"允许的字段：{', '.join(sorted(ALLOWED))}"
        )

    if "name" not in fm:
        return False, "frontmatter 缺少 'name' 字段"
    if "description" not in fm:
        return False, "frontmatter 缺少 'description' 字段"

    name = str(fm["name"]).strip()
    if not re.match(r"^[a-z0-9-]+$", name):
        return False, f"name '{name}' 必须为 kebab-case（小写字母、数字、连字符）"
    if name.startswith("-") or name.endswith("-") or "--" in name:
        return False, f"name '{name}' 不能以连字符开头/结尾，或含连续连字符"
    if len(name) > 64:
        return False, f"name 过长（{len(name)} 字符），最大 64"

    description = str(fm["description"]).strip()
    if "<" in description or ">" in description:
        return False, "description 不能包含尖括号 < >"
    if len(description) > 1024:
        return False, f"description 过长（{len(description)} 字符），最大 1024"

    compatibility = fm.get("compatibility", "")
    if compatibility and len(str(compatibility)) > 500:
        return False, f"compatibility 过长（{len(str(compatibility))} 字符），最大 500"

    return True, f"✓ SKILL '{name}' 格式合法"


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("用法: python scripts/quick_validate.py <skill目录>")
        sys.exit(1)

    valid, message = validate_skill(sys.argv[1])
    print(message)
    sys.exit(0 if valid else 1)
