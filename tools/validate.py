"""Validate the toolkit: marketplace, plugin manifests and skill frontmatter.

    python3 tools/validate.py
"""

import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NAME_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")


def frontmatter(path):
    with open(path, encoding="utf-8") as f:
        text = f.read()
    m = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    if not m:
        return None, text
    meta = {}
    for line in m.group(1).splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            meta[k.strip()] = v.strip()
    return meta, text[m.end():]


def main() -> int:
    errors = []
    with open(os.path.join(ROOT, ".claude-plugin", "marketplace.json"), encoding="utf-8") as f:
        market = json.load(f)
    seen_skills = {}
    for plugin in market["plugins"]:
        pdir = os.path.normpath(os.path.join(ROOT, plugin["source"]))
        manifest = os.path.join(pdir, ".claude-plugin", "plugin.json")
        if not os.path.exists(manifest):
            errors.append(f"{plugin['name']}: missing {manifest}")
            continue
        with open(manifest, encoding="utf-8") as f:
            pj = json.load(f)
        if pj.get("name") != plugin["name"]:
            errors.append(f"{plugin['name']}: plugin.json name '{pj.get('name')}' differs from marketplace")
        skills_dir = os.path.join(pdir, "skills")
        for skill in sorted(os.listdir(skills_dir)):
            path = os.path.join(skills_dir, skill, "SKILL.md")
            if not os.path.exists(path):
                errors.append(f"{skill}: missing SKILL.md")
                continue
            meta, body = frontmatter(path)
            rel = os.path.relpath(path, ROOT)
            if meta is None:
                errors.append(f"{rel}: missing frontmatter")
                continue
            if meta.get("name") != skill:
                errors.append(f"{rel}: name '{meta.get('name')}' must equal directory '{skill}'")
            if not NAME_RE.match(meta.get("name", "")) or len(meta.get("name", "")) > 64:
                errors.append(f"{rel}: name must be lowercase-hyphenated, <= 64 chars")
            desc = meta.get("description", "")
            if not desc or len(desc) > 1024:
                errors.append(f"{rel}: description missing or > 1024 chars ({len(desc)})")
            if skill in seen_skills:
                errors.append(f"{rel}: duplicate skill name (also in {seen_skills[skill]})")
            seen_skills[skill] = rel
            if len(body.splitlines()) > 500:
                errors.append(f"{rel}: body over 500 lines; move detail to references/")
            for link in re.findall(r"\]\(((?:references|scripts)/[^)#]+)\)", body):
                if not os.path.exists(os.path.join(skills_dir, skill, link)):
                    errors.append(f"{rel}: broken link {link}")
    for e in errors:
        print(f"ERROR: {e}")
    print(f"{len(seen_skills)} skills checked, {len(errors)} errors")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
