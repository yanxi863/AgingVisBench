from __future__ import annotations

import re
import sys
from pathlib import Path


FORBIDDEN_DIRS = {
    "AI audit image",
    "Output data",
    "RQ2_analysis_output",
    "OLD-RQ2_analysis_output",
    "Result",
    "archive",
    "__pycache__",
    ".idea",
    ".vscode",
}
FORBIDDEN_SUFFIXES = {
    ".pyc", ".pyo", ".pt", ".pth", ".ckpt", ".onnx",
    ".pdf", ".doc", ".docx", ".ppt", ".pptx", ".xls", ".xlsx",
}
ALLOWED_BINARY = {
    Path("examples/sample_corpus/synthetic_model/60yo_Test_Woman/placeholder.png")
}
MAX_PUBLIC_FILE_BYTES = 5 * 1024 * 1024
SECRET_PATTERNS = {
    "Anthropic-style key": re.compile(rb"\bsk-ant-[A-Za-z0-9_-]{12,}\b"),
    "generic sk key": re.compile(rb"\bsk-(?!ant-)[A-Za-z0-9_-]{16,}\b"),
    "GitHub token": re.compile(rb"\bgh[opusr]_[A-Za-z0-9]{20,}\b"),
    "AWS access key": re.compile(rb"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b"),
    "Google API key": re.compile(rb"\bAIza[0-9A-Za-z_-]{30,}\b"),
    "Volcengine access key": re.compile(rb"\bAKLT[A-Za-z0-9]{12,}\b"),
    "JWT": re.compile(rb"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b"),
}
PRIVATE_MARKERS = [
    b"86180",
    "交大杂事".encode("utf-8"),
    re.compile(rb"[A-Za-z]:[\\/]Users[\\/](?!<|user|username)[^\\/\s]+"),
    re.compile(rb"/(?:Users|home)/(?!<|user|username)[^/\s]+"),
]


def scan(root: Path) -> list[str]:
    errors: list[str] = []
    for path in root.rglob("*"):
        rel = path.relative_to(root)
        if any(part in {".git", ".venv", ".pytest_cache", "__pycache__"} for part in rel.parts):
            continue
        if any(part in FORBIDDEN_DIRS for part in rel.parts):
            errors.append(f"forbidden path: {rel.as_posix()}")
            continue
        if not path.is_file():
            continue
        if path.stat().st_size > MAX_PUBLIC_FILE_BYTES:
            errors.append(f"oversized file: {rel.as_posix()} ({path.stat().st_size} bytes)")
        if path.suffix.lower() in FORBIDDEN_SUFFIXES:
            errors.append(f"forbidden extension: {rel.as_posix()}")
        if path.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp", ".bmp"} and rel not in ALLOWED_BINARY:
            errors.append(f"unreviewed image: {rel.as_posix()}")

        if rel.as_posix() == "scripts/check_public_repo.py" or path.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp", ".bmp"}:
            continue
        data = path.read_bytes()
        for label, pattern in SECRET_PATTERNS.items():
            if pattern.search(data):
                errors.append(f"{label} candidate: {rel.as_posix()} (value suppressed)")
        for marker in PRIVATE_MARKERS:
            matched = marker.search(data) if hasattr(marker, "search") else marker in data
            if matched:
                errors.append(f"private path/identity marker: {rel.as_posix()} (value suppressed)")
                break
    return sorted(set(errors))


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    errors = scan(root)
    if errors:
        print("Public-repository check failed:")
        for error in errors:
            print(f"- {error}")
        return 1
    print("Public-repository check passed: no forbidden files or high-confidence secret/path markers found.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
