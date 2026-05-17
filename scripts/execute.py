from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ServerConfig:
    prefix: str
    command: str
    method: str
    output: Path
    init_options: str = ""
    request_options: str = ""


@dataclass(frozen=True)
class ProjectCase:
    project: Path
    dataset: str
    language: str
    case_id: str

    @property
    def name(self) -> str:
        return self.project.name


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--server",
        help="server command passed to mals-test --server",
    )
    parser.add_argument(
        "--prefix",
        help="output prefix used in result paths",
    )
    parser.add_argument(
        "--method",
        help="completion method passed to mals-test --method",
    )
    parser.add_argument(
        "--init-options",
        help="optional JSON path passed to mals-test --init-options",
    )
    parser.add_argument(
        "--request-options",
        help="optional JSON path passed to mals-test --request-options",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("result"),
        help="base output directory",
    )
    parser.add_argument(
        "--jobs",
        type=int,
        default=int(1),
        help="number of parallel worker processes",
    )
    parser.add_argument(
        "--limit",
        type=int,
        help="optional number of projects per dataset/language pair",
    )
    parser.add_argument(
        "--datasets",
        default="humanevalpack,repobench-c,cceval",
        help="comma-separated dataset names, for example humanevalpack,repobench-c",
    )
    return parser.parse_args()


def run_find(args: list[str]) -> list[Path]:
    process = subprocess.run(
        ["find", *args],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if process.stdout:
        sys.stdout.write(process.stdout)
    if process.stderr:
        sys.stderr.write(process.stderr)
    if process.returncode != 0:
        raise subprocess.CalledProcessError(process.returncode, ["find", *args])
    return [Path(line) for line in process.stdout.splitlines() if line]


def discover_dataset_dirs(dataset_filter: str) -> list[Path]:
    print("Datasets that will be executed:")
    if dataset_filter:
        dataset_dirs = []
        for dataset in dataset_filter.split(","):
            dataset = dataset.strip()
            if not dataset:
                continue
            dataset_dirs.extend(
                run_find(
                    [
                        "data",
                        "-maxdepth",
                        "1",
                        "-type",
                        "d",
                        "-name",
                        f"{dataset}.projects",
                        "-print",
                    ]
                )
            )
        return sorted(set(dataset_dirs))

    return sorted(
        run_find(
            [
                "data",
                "-maxdepth",
                "1",
                "-type",
                "d",
                "-name",
                "*.projects",
                "-print",
            ]
        )
    )


def read_json(path: Path) -> dict[str, object]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path}: expected one JSON object")
    return data


def select_projects(dataset_dirs: list[Path], limit: int | None) -> list[ProjectCase]:
    groups: dict[tuple[str, str], list[ProjectCase]] = defaultdict(list)

    for dataset_dir in dataset_dirs:
        for completion_json in sorted(dataset_dir.glob("*/completion.json")):
            data = read_json(completion_json)
            dataset = str(
                data.get("dataset") or dataset_dir.name.removesuffix(".projects")
            )
            language = str(data.get("language") or "unknown")
            case_id = str(data.get("id") or completion_json.parent.name)
            groups[(dataset, language)].append(
                ProjectCase(
                    project=completion_json.parent,
                    dataset=dataset,
                    language=language,
                    case_id=case_id,
                )
            )

    selected = []
    for (dataset, language), projects in sorted(groups.items()):
        cases = projects[:limit] if limit is not None else projects
        print(
            f"selected {len(cases):>3} projects for {dataset}/{language}",
            file=sys.stderr,
        )
        selected.extend(cases)
    return selected


def run_command(command: list[str], done_message: str = "") -> None:
    subprocess.run(command, stdout=sys.stdout, stderr=sys.stderr, check=True)
    if done_message:
        print(done_message, flush=True)


def run_parallel(title: str, jobs: int, commands: list[list[str]]) -> None:
    print(f"\n{title}")
    if not commands:
        print("nothing to run")
        return

    with ThreadPoolExecutor(max_workers=jobs) as executor:
        futures = [executor.submit(run_command, command) for command in commands]
        for future in as_completed(futures):
            future.result()


def run_parallel_with_done_messages(
    title: str,
    jobs: int,
    commands: list[tuple[list[str], str]],
) -> None:
    print(f"\n{title}")
    if not commands:
        print("nothing to run")
        return

    with ThreadPoolExecutor(max_workers=jobs) as executor:
        futures = [
            executor.submit(run_command, command, done_message)
            for command, done_message in commands
        ]
        for future in as_completed(futures):
            future.result()


def mals_test_command(config: ServerConfig, case: ProjectCase) -> list[str]:
    out = config.output / "mals-test" / config.prefix / case.dataset / f"{case.name}.json"
    command = [
        "go",
        "run",
        "./cmd/mals-test",
        "--server",
        config.command,
        "--method",
        config.method,
        "--timeout",
        "5m",
        "--out",
        out.as_posix(),
    ]
    if config.init_options:
        command.extend(["--init-options", config.init_options])
    if config.request_options:
        command.extend(["--request-options", config.request_options])
    command.append(case.project.as_posix())
    return command


def evaluate_direct_command(config: ServerConfig, case: ProjectCase) -> list[str]:
    return [
        sys.executable,
        "scripts/evaluate_direct.py",
        "--input",
        (
            config.output
            / "mals-test"
            / config.prefix
            / case.dataset
            / f"{case.name}.json"
        ).as_posix(),
        "--output",
        (
            config.output
            / "evaluated-direct"
            / config.prefix
            / case.dataset
            / f"{case.name}.json"
        ).as_posix(),
    ]


def materialize_command(config: ServerConfig, case: ProjectCase) -> list[str]:
    return [
        sys.executable,
        "scripts/materialize_test_result.py",
        "--project",
        case.project.as_posix(),
        "--result",
        (
            config.output
            / "mals-test"
            / config.prefix
            / case.dataset
            / f"{case.name}.json"
        ).as_posix(),
        "--output",
        (
            config.output
            / "materialized"
            / config.prefix
            / case.dataset
            / case.name
        ).as_posix(),
        "--overwrite",
    ]


def evaluate_materialized_command(config: ServerConfig, case: ProjectCase) -> list[str]:
    return [
        sys.executable,
        "scripts/evaluate_materialized.py",
        "--project",
        (
            config.output
            / "materialized"
            / config.prefix
            / case.dataset
            / case.name
        ).as_posix(),
        "--result",
        (
            config.output
            / "mals-test"
            / config.prefix
            / case.dataset
            / f"{case.name}.json"
        ).as_posix(),
        "--output",
        (
            config.output
            / "evaluated-materialized"
            / config.prefix
            / case.dataset
            / f"{case.name}.json"
        ).as_posix(),
    ]


def aggregate_direct_commands(
    config: ServerConfig,
    cases: list[ProjectCase],
) -> list[list[str]]:
    return [
        [
            sys.executable,
            "scripts/aggregate_direct.py",
            "--output",
            (
                config.output
                / "aggregated-direct"
                / dataset
                / f"{config.prefix}.json"
            ).as_posix(),
            "--group-by",
            "server,dataset,language",
            *[
                (
                    config.output
                    / "evaluated-direct"
                    / config.prefix
                    / case.dataset
                    / f"{case.name}.json"
                ).as_posix()
                for case in cases
                if case.dataset == dataset
            ],
        ]
        for dataset in sorted({case.dataset for case in cases})
    ]


def aggregate_materialized_commands(
    config: ServerConfig,
    cases: list[ProjectCase],
) -> list[list[str]]:
    return [
        [
            sys.executable,
            "scripts/aggregate_materialized.py",
            "--output",
            (
                config.output
                / "aggregated-materialized"
                / dataset
                / f"{config.prefix}.json"
            ).as_posix(),
            "--group-by",
            "server,dataset,language",
            *[
                (
                    config.output
                    / "evaluated-materialized"
                    / config.prefix
                    / case.dataset
                    / f"{case.name}.json"
                ).as_posix()
                for case in cases
                if case.dataset == dataset
            ],
        ]
        for dataset in sorted({case.dataset for case in cases})
    ]


def main() -> None:
    args = parse_args()
    if args.jobs < 1:
        raise SystemExit("--jobs must be at least 1")
    if args.limit is not None and args.limit < 1:
        raise SystemExit("--limit must be at least 1")

    config = ServerConfig(
        prefix=args.prefix.lower(),
        command=args.server,
        method=args.method,
        output=args.output,
        init_options=args.init_options,
        request_options=args.request_options,
    )

    dataset_dirs = discover_dataset_dirs(args.datasets)

    if not dataset_dirs:
        raise SystemExit("no datasets found")

    cases = select_projects(dataset_dirs, args.limit)
    if not cases:
        raise SystemExit("no projects found")

    run_parallel_with_done_messages(
        "1. execute mals-test",
        args.jobs,
        [
            (
                mals_test_command(config, case),
                f"mals-test {case.dataset}/{case.name} is done",
            )
            for case in cases
        ],
    )
    run_parallel(
        "2. evaluate_direct",
        args.jobs,
        [evaluate_direct_command(config, case) for case in cases],
    )
    run_parallel(
        "3. create materialized projects",
        args.jobs,
        [materialize_command(config, case) for case in cases],
    )
    run_parallel(
        "4. evaluate_materialized",
        args.jobs,
        [evaluate_materialized_command(config, case) for case in cases],
    )
    run_parallel(
        "5. aggregate_direct",
        args.jobs,
        aggregate_direct_commands(config, cases),
    )
    run_parallel(
        "6. aggregate_materialized",
        args.jobs,
        aggregate_materialized_commands(config, cases),
    )


if __name__ == "__main__":
    main()
