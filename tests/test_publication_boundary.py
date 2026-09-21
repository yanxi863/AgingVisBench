from __future__ import annotations

import re
from pathlib import Path

from scripts.check_public_repo import scan


ROOT = Path(__file__).resolve().parents[1]
LINK = re.compile(r"\[[^\]]+\]\(([^)]+)\)")


def test_public_repository_boundary():
    assert scan(ROOT) == []


def test_markdown_relative_links_exist():
    missing = []
    for path in ROOT.rglob("*.md"):
        if ".git" in path.parts:
            continue
        text = path.read_text(encoding="utf-8")
        for target in LINK.findall(text):
            if "://" in target or target.startswith(("#", "mailto:")):
                continue
            target_path = target.split("#", 1)[0]
            if target_path and not (path.parent / target_path).exists():
                missing.append(f"{path.relative_to(ROOT)} -> {target}")
    assert missing == []
