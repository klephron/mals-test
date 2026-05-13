from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


EXTENSIONS = {
    "python": ".py",
    "java": ".java",
    "go": ".go",
    "js": ".js",
    "javascript": ".js",
    "typescript": ".ts",
    "cpp": ".cpp",
    "rust": ".rs",
    "csharp": ".cs",
}


def extension(language: str) -> str:
    return EXTENSIONS.get(language, ".txt")


def sanitize_name(value: str) -> str:
    value = re.sub(r"[^A-Za-z0-9._-]+", "_", value)
    value = value.strip("._-")
    return value or "entry"


def safe_relative_path(value: str) -> Path:
    parts = []
    for part in Path(value.replace("\\", "/")).parts:
        if part in ("", ".", "..") or part.endswith(":"):
            continue
        parts.append(sanitize_name(part))
    return Path(*parts) if parts else Path("main.txt")


def line_col_offset(text: str) -> dict[str, int]:
    line = 0
    character = 0
    for ch in text:
        if ch == "\n":
            line += 1
            character = 0
        else:
            character += 1
    return {"line": line, "character": character, "offset": len(text)}


def read_jsonl(path: Path, limit: int | None = None):
    with path.open(encoding="utf-8") as handle:
        for index, line in enumerate(handle):
            if limit is not None and index >= limit:
                break
            if line.strip():
                yield index, json.loads(line)


def write_text(root: Path, relative: str | Path, text: str) -> str:
    rel = safe_relative_path(str(relative))
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return rel.as_posix()


def write_completion_json(entry_dir: Path, payload: dict[str, Any]) -> None:
    (entry_dir / "completion.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def build_completion_payload(
    *,
    dataset: str,
    entry_id: str,
    language: str,
    source_file: str,
    prefix: str,
    suffix: str,
    ground_truth: str,
    files: list[str],
    metadata: dict[str, Any],
) -> dict[str, Any]:
    return {
        "id": entry_id,
        "dataset": dataset,
        "language": language,
        "root_dir": "root",
        "source_file": source_file,
        "cursor": line_col_offset(prefix),
        "prefix": prefix,
        "suffix": suffix,
        "ground_truth": ground_truth,
        "files": files,
        "metadata": metadata,
    }
