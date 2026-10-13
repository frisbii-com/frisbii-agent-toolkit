"""Build the public skills bundle for docs.frisbii.com/.well-known/skills/.

    python3 tools/build_skills_index.py [--out dist]

Writes <out>/.well-known/skills/index.json plus a copy of every public skill's
files under <out>/.well-known/skills/<skill>/. Upload the contents of <out> to
the docs site so agents can discover the skills (e.g. `npx skills add
https://docs.frisbii.com`).
"""

import argparse
import json
import os
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from validate import ROOT, frontmatter  # noqa: E402

PUBLIC_PLUGINS = ("plugins/frisbii",)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(ROOT, "dist"))
    a = ap.parse_args()
    target = os.path.join(a.out, ".well-known", "skills")
    if os.path.exists(target):
        shutil.rmtree(target)
    os.makedirs(target)

    index = {"skills": []}
    for plugin in PUBLIC_PLUGINS:
        skills_dir = os.path.join(ROOT, plugin, "skills")
        for skill in sorted(os.listdir(skills_dir)):
            src = os.path.join(skills_dir, skill)
            meta, _ = frontmatter(os.path.join(src, "SKILL.md"))
            files = []
            for dirpath, _, filenames in os.walk(src):
                for name in sorted(filenames):
                    rel = os.path.relpath(os.path.join(dirpath, name), src).replace(os.sep, "/")
                    files.append(rel)
            shutil.copytree(src, os.path.join(target, skill))
            index["skills"].append({"name": meta["name"], "description": meta["description"],
                                    "files": sorted(files)})
    with open(os.path.join(target, "index.json"), "w", encoding="utf-8") as f:
        json.dump(index, f, indent=2)
        f.write("\n")
    print(f"{len(index['skills'])} skills → {target}")


if __name__ == "__main__":
    main()
