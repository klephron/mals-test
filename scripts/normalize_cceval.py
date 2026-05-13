from __future__ import annotations

import argparse
from pathlib import Path

try:
    from scripts.common_normalize import (
        build_completion_payload,
        extension,
        read_jsonl,
        sanitize_name,
        write_completion_json,
        write_text,
    )
except ModuleNotFoundError:
    from common_normalize import (
        build_completion_payload,
        extension,
        read_jsonl,
        sanitize_name,
        write_completion_json,
        write_text,
    )


DATASET = "cceval"


def crossfile_chunks(row: dict) -> dict[str, str]:
    context = row.get("crossfile_context") or {}
    chunks: dict[str, list[str]] = {}
    for item in context.get("list") or []:
        filename = item.get("filename")
        chunk = item.get("retrieved_chunk")
        if filename and chunk:
            chunks.setdefault(filename, []).append(chunk.rstrip())
    return {filename: "\n\n".join(parts).rstrip() + "\n" for filename, parts in chunks.items()}


def normalize(input_dir: Path, output_dir: Path, languages: set[str] | None, variants: set[str] | None, limit: int | None) -> int:
    count = 0
    output_dir.mkdir(parents=True, exist_ok=True)

    for path in sorted(input_dir.glob("*/*.jsonl")):
        language = path.parent.name
        variant = path.name.removesuffix(".jsonl")
        if languages and language not in languages:
            continue
        if variants and variant not in variants:
            continue

        for index, row in read_jsonl(path, limit):
            metadata = row.get("metadata") or {}
            task_id = metadata.get("task_id") or f"{language}/{variant}/{index}"
            entry_name = sanitize_name(f"{language}-{variant}-{task_id}")
            entry_dir = output_dir / entry_name
            root = entry_dir / "root"
            root.mkdir(parents=True, exist_ok=True)

            context_files = crossfile_chunks(row)
            files = []
            for context_path, context_text in context_files.items():
                files.append(write_text(root, context_path, context_text))

            if context_files:
                source_file = metadata.get("file") or f"main{extension(language)}"
            else:
                source_file = f"main{extension(language)}"

            prefix = row.get("prompt", "")
            suffix = row.get("right_context", "")
            source_written = write_text(root, source_file, prefix + suffix)
            if source_written not in files:
                files.append(source_written)

            payload = build_completion_payload(
                dataset=DATASET,
                entry_id=f"{DATASET}/{variant}/{task_id}",
                language=language,
                source_file=source_written,
                prefix=prefix,
                suffix=suffix,
                ground_truth=row.get("groundtruth", ""),
                files=files,
                metadata=row,
            )
            write_completion_json(entry_dir, payload)
            count += 1

    return count


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default="data/cceval")
    parser.add_argument("--output", default="data/cceval.projects")
    parser.add_argument("--languages", default="all", help="comma-separated languages or all")
    parser.add_argument("--variants", default="line_completion", help="comma-separated variants or all")
    parser.add_argument("--limit", type=int, default=None, help="limit per input file")
    args = parser.parse_args()

    languages = None if args.languages == "all" else {item.strip() for item in args.languages.split(",") if item.strip()}
    variants = None if args.variants == "all" else {item.strip() for item in args.variants.split(",") if item.strip()}
    count = normalize(Path(args.input), Path(args.output), languages, variants, args.limit)
    print(f"created {count} {DATASET} projects in {args.output}")


if __name__ == "__main__":
    main()
