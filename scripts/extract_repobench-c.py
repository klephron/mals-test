from __future__ import annotations

import argparse
import re
from pathlib import Path

try:
    from scripts.common_extract import (
        build_completion_payload,
        read_jsonl,
        sanitize_name,
        write_completion_json,
        write_text,
    )
except ModuleNotFoundError:
    from common_extract import (
        build_completion_payload,
        read_jsonl,
        sanitize_name,
        write_completion_json,
        write_text,
    )


DATASET = "repobench-c"
PATH_MARKER_RE = re.compile(r"^\s*(?://|#)\s*Path:\s*(?P<path>.+?)\s*$")


def strip_repobench_comment_prefix(line: str) -> str:
    if line.startswith("# "):
        return line[2:]
    if line == "#":
        return ""
    if line.startswith("// "):
        return line[3:]
    if line == "//":
        return ""
    return line


def parse_repobench_context_files(text: str) -> dict[str, str]:
    sections: dict[str, list[str]] = {}
    current_path: str | None = None
    current_lines: list[str] = []

    def flush() -> None:
        nonlocal current_lines, current_path
        if current_path is not None:
            sections.setdefault(current_path, []).extend(current_lines)
            if current_lines:
                sections[current_path].append("")
        current_lines = []

    for raw_line in text.splitlines():
        match = PATH_MARKER_RE.match(raw_line)
        if match:
            flush()
            current_path = match.group("path")
            continue
        if current_path is not None:
            current_lines.append(strip_repobench_comment_prefix(raw_line))
    flush()

    return {path: "\n".join(lines).rstrip() + "\n" for path, lines in sections.items()}


def insert_repobench_java_imports(code: str, imports: str) -> str:
    if not imports.strip():
        return code
    lines = code.splitlines(keepends=True)
    for index, line in enumerate(lines):
        if line.strip().startswith("package ") and line.strip().endswith(";"):
            return "".join(lines[: index + 1]) + "\n" + imports.rstrip() + "\n" + "".join(lines[index + 1 :])
    return imports.rstrip() + "\n\n" + code


def target_prefix(language: str, row: dict) -> str:
    code = row.get("code", "")
    imports = row.get("import_statement", "")
    if language == "java":
        return insert_repobench_java_imports(code, imports)
    if imports.strip() and imports.strip() not in code:
        return imports.rstrip() + "\n\n" + code
    return code


def extract(input_dir: Path, output_dir: Path, languages: set[str] | None, limit: int | None) -> int:
    count = 0
    output_dir.mkdir(parents=True, exist_ok=True)

    for path in sorted(input_dir.glob("*-test.json")):
        config = path.name.removesuffix("-test.json")
        language = config.split("_", 1)[0]
        if languages and language not in languages:
            continue

        for index, row in read_jsonl(path, limit):
            repo = row.get("repo_name", "repo")
            entry_name = sanitize_name(f"{config}-{repo}-{index}")
            entry_dir = output_dir / entry_name
            root = entry_dir / "root"
            root.mkdir(parents=True, exist_ok=True)

            files = []
            for context_path, context_text in parse_repobench_context_files(row.get("context", "")).items():
                files.append(write_text(root, context_path, context_text))

            source_file = row.get("file_path") or "main.txt"
            prefix = target_prefix(language, row)
            suffix = ""
            source_written = write_text(root, source_file, prefix + suffix)
            if source_written not in files:
                files.append(source_written)

            entry_id = f"{DATASET}/{config}/{index}"
            payload = build_completion_payload(
                dataset=DATASET,
                entry_id=entry_id,
                language=language,
                source_file=source_written,
                prefix=prefix,
                suffix=suffix,
                ground_truth=row.get("next_line", ""),
                files=files,
                metadata=row,
            )
            write_completion_json(entry_dir, payload)
            count += 1

    return count


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default="data/repobench-c")
    parser.add_argument("--output", default="data/repobench-c.projects")
    parser.add_argument("--languages", default="all", help="comma-separated languages or all")
    parser.add_argument("--limit", type=int, default=None, help="limit per input file")
    args = parser.parse_args()

    languages = None if args.languages == "all" else {item.strip() for item in args.languages.split(",") if item.strip()}
    count = extract(Path(args.input), Path(args.output), languages, args.limit)
    print(f"created {count} {DATASET} projects in {args.output}")


if __name__ == "__main__":
    main()
