"""Create concrete project variants for one produced by mals-test."""

from __future__ import annotations

import argparse
import json
import shutil
from dataclasses import dataclass
from pathlib import Path

try:
    from .common import TestResult, read_test_result
except ImportError:
    from common import TestResult, read_test_result


@dataclass(frozen=True)
class MaterializedProject:
    result_path: Path
    variant: str
    output_dir: Path


def validate_project_matches_result(project_dir: Path, record: TestResult) -> None:
    completion_json = project_dir / "completion.json"
    if not completion_json.exists():
        return

    data = json.loads(completion_json.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{completion_json}: expected one JSON object")

    project_case_id = str(data.get("id") or "")
    if project_case_id and project_case_id != record.case.id:
        raise ValueError(
            f"project/result mismatch: project case id is {project_case_id!r}, "
            f"but result case id is {record.case.id!r}"
        )


def source_project_root(project_dir: Path, record: TestResult) -> Path:
    root = project_dir / record.case.root_dir
    if root.is_dir():
        return root

    direct_source = project_dir / record.case.source_file
    if direct_source.exists():
        return project_dir

    raise FileNotFoundError(
        f"could not find source project root for {record.case.id} in {project_dir}: "
    )


def copy_project(src_root: Path, dest: Path, overwrite: bool) -> None:
    if dest.exists():
        if not overwrite:
            raise FileExistsError(f"{dest} already exists")
        shutil.rmtree(dest)
    shutil.copytree(src_root, dest)


def patch_source_file(project_dir: Path, record: TestResult, replacement: str) -> None:
    source_path = project_dir / record.case.source_file
    source_path.parent.mkdir(parents=True, exist_ok=True)
    source_path.write_text(
        record.case.prefix + replacement + record.case.suffix,
        encoding="utf-8",
    )


def materialize_result(
    *,
    project_dir: Path,
    result_path: Path,
    output_dir: Path,
    overwrite: bool,
) -> list[MaterializedProject]:
    record = read_test_result(result_path)
    validate_project_matches_result(project_dir, record)
    source_root = source_project_root(project_dir, record)

    variants = [("baseline", record.case.ground_truth)]
    variants.extend(
        (f"completion_{index}", completion)
        for index, completion in enumerate(record.completions)
    )

    materialized = []
    for variant, replacement in variants:
        destination = output_dir / variant
        copy_project(source_root, destination, overwrite)
        patch_source_file(destination, record, replacement)
        materialized.append(
            MaterializedProject(
                result_path=result_path,
                variant=variant,
                output_dir=destination,
            )
        )

    return materialized


def default_output_dir(project_dir: Path) -> Path:
    return Path("result/materialized") / project_dir.name


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--project",
        "-p",
        required=True,
        help="one project directory produced by an extract_* script",
    )
    parser.add_argument(
        "--result",
        "-r",
        required=True,
        help="one mals-test result JSON file",
    )
    parser.add_argument(
        "--output",
        "-o",
        default=None,
        help="output directory",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="replace existing materialized project variants",
    )
    args = parser.parse_args()

    project_dir = Path(args.project)
    result_path = Path(args.result)
    output_dir = Path(args.output) if args.output else default_output_dir(project_dir)

    created = materialize_result(
        project_dir=project_dir,
        result_path=result_path,
        output_dir=output_dir,
        overwrite=args.overwrite,
    )

    print(
        json.dumps(
            {
                "project": str(project_dir),
                "result": str(result_path),
                "variants_created": len(created),
                "output": str(output_dir),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
