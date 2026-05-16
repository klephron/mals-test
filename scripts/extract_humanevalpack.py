from __future__ import annotations

import argparse
from pathlib import Path

try:
    from scripts.extract_common import (
        build_completion_payload,
        extension,
        read_jsonl,
        sanitize_name,
        write_completion_json,
        write_text,
    )
except ModuleNotFoundError:
    from extract_common import (
        build_completion_payload,
        extension,
        read_jsonl,
        sanitize_name,
        write_completion_json,
        write_text,
    )


DATASET = "humanevalpack"


def extract(input_dir: Path, output_dir: Path, languages: set[str] | None, limit: int | None) -> int:
    count = 0
    output_dir.mkdir(parents=True, exist_ok=True)

    for path in sorted(input_dir.glob("*-test.json")):
        language = path.name.removesuffix("-test.json")
        if languages and language not in languages:
            continue

        for index, row in read_jsonl(path, limit):
            task_id = row.get("task_id") or f"{language}/{index}"
            entry_name = sanitize_name(f"{language}-{task_id}")
            entry_dir = output_dir / entry_name
            root = entry_dir / "root"
            root.mkdir(parents=True, exist_ok=True)

            source_file = f"main{extension(language)}"
            prefix = row.get("prompt", "")
            suffix = ""
            files = [write_text(root, source_file, prefix + suffix)]

            payload = build_completion_payload(
                dataset=DATASET,
                entry_id=f"{DATASET}/{task_id}",
                language=language,
                source_file=source_file,
                prefix=prefix,
                suffix=suffix,
                ground_truth=row.get("canonical_solution", ""),
                files=files,
                metadata=row,
            )
            write_completion_json(entry_dir, payload)
            count += 1

    return count


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default="data/humanevalpack")
    parser.add_argument("--output", default="data/humanevalpack.projects")
    parser.add_argument("--languages", default="all", help="comma-separated languages or all")
    parser.add_argument("--limit", type=int, default=None, help="limit per input file")
    args = parser.parse_args()

    languages = None if args.languages == "all" else {item.strip() for item in args.languages.split(",") if item.strip()}
    count = extract(Path(args.input), Path(args.output), languages, args.limit)
    print(f"created {count} {DATASET} projects in {args.output}")


if __name__ == "__main__":
    main()
