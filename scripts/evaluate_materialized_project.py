"""Evaluate compiler/analyzer diagnostics for a materialized test project."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

try:
    from .common import (
        DiagnosticEvaluation,
        MaterializedEvaluation,
        TestResult,
        read_test_result,
        write_materialized_evaluation,
        materialized_evaluation_to_dict,
    )
except ImportError:
    from common import (
        DiagnosticEvaluation,
        MaterializedEvaluation,
        TestResult,
        read_test_result,
        write_materialized_evaluation,
        materialized_evaluation_to_dict,
    )


@dataclass(frozen=True)
class CheckerResult:
    project_dir: Path
    command: list[str]
    return_code: int
    stdout: str
    stderr: str


def normalize_diagnostic_line(line: str, project_dir: Path) -> str:
    line = line.strip()
    if not line:
        return ""

    project_text = str(project_dir.resolve())
    line = line.replace(project_text, "<project>")
    line = line.replace(str(project_dir), "<project>")
    line = " ".join(line.split())
    return line


def normalize_diagnostics(diagnostics: list[str], project_dir: Path) -> list[str]:
    return [
        normalized
        for diagnostic in diagnostics
        if (normalized := normalize_diagnostic_line(diagnostic, project_dir))
    ]


def extract_diagnostics(output: str) -> list[str]:
    diagnostics = []
    seen = set()
    for line in output.splitlines():
        diagnostic = line.strip()
        if not diagnostic or diagnostic in seen:
            continue
        diagnostics.append(diagnostic)
        seen.add(diagnostic)
    return diagnostics


def checker_output(result: CheckerResult) -> str:
    return "\n".join([result.stdout, result.stderr])


def executable(name: str) -> str | None:
    return shutil.which(name)


def files_with_suffix(project_dir: Path, suffixes: tuple[str, ...]) -> list[Path]:
    return sorted(
        path
        for path in project_dir.rglob("*")
        if path.is_file() and path.suffix in suffixes
    )


def relative_files(project_dir: Path, paths: list[Path]) -> list[str]:
    return [path.relative_to(project_dir).as_posix() for path in paths]


def checker_command(
    project_dir: Path,
    language: str,
    source_file: str,
) -> list[str]:
    language = language.lower()

    if language in {"cpp", "c++"}:
        compiler = executable("g++") or executable("clang++")
        if not compiler:
            raise RuntimeError("missing checker for cpp: install g++ or clang++")
        return [
            compiler,
            "-std=c++17",
            "-fsyntax-only",
            source_file,
        ]

    if language == "csharp":
        dotnet = executable("dotnet")
        if dotnet and (
            list(project_dir.glob("*.sln")) or list(project_dir.rglob("*.csproj"))
        ):
            return [dotnet, "build", "--no-restore"]
        csc = executable("csc")
        if csc:
            return [
                csc,
                "-nologo",
                "-t:library",
                *relative_files(project_dir, files_with_suffix(project_dir, (".cs",))),
            ]
        raise RuntimeError("missing checker for csharp: install dotnet or csc")

    if language == "go":
        go = executable("go")
        if not go:
            raise RuntimeError("missing checker for go: install go")
        if (project_dir / "go.mod").exists():
            return [go, "test", "./..."]
        go_files = relative_files(project_dir, files_with_suffix(project_dir, (".go",)))
        return [go, "test", *go_files]

    if language == "java":
        javac = executable("javac")
        if not javac:
            raise RuntimeError("missing checker for java: install javac")
        java_files = relative_files(project_dir, files_with_suffix(project_dir, (".java",)))
        return [
            javac,
            "-Xlint:none",
            "-proc:none",
            "-d",
            tempfile.mkdtemp(prefix="mals-javac-"),
            *java_files,
        ]

    if language in {"js", "javascript"}:
        node = executable("node")
        if not node:
            raise RuntimeError("missing checker for javascript: install node")
        files = relative_files(project_dir, files_with_suffix(project_dir, (".js",)))
        if source_file in files:
            return [node, "--check", source_file]
        if files:
            return [node, "--check", files[0]]
        raise RuntimeError(f"missing javascript source file in {project_dir}")

    if language == "typescript":
        tsc = executable("tsc")
        if not tsc:
            raise RuntimeError("missing checker for typescript: install tsc")
        if (project_dir / "tsconfig.json").exists():
            return [tsc, "--noEmit"]
        ts_files = relative_files(
            project_dir,
            files_with_suffix(project_dir, (".ts", ".tsx")),
        )
        return [tsc, "--noEmit", "--skipLibCheck", *ts_files]

    if language == "python":
        pyright = executable("pyright")
        if pyright:
            return [pyright, "--outputjson", "."]
        python = executable("python") or executable("python3")
        if not python:
            raise RuntimeError("missing checker for python: install pyright or python")
        return [
            python,
            "-m",
            "py_compile",
            *relative_files(project_dir, files_with_suffix(project_dir, (".py",))),
        ]

    if language == "rust":
        cargo = executable("cargo")
        if cargo and (project_dir / "Cargo.toml").exists():
            return [cargo, "check", "--offline"]
        rustc = executable("rustc")
        if rustc:
            return [rustc, "--emit=metadata", source_file]
        raise RuntimeError("missing checker for rust: install cargo or rustc")

    raise ValueError(f"unsupported language: {language}")


def run_checker(project_dir: Path, language: str, source_file: str) -> CheckerResult:
    command = checker_command(project_dir, language, source_file)

    process = subprocess.run(
        command,
        cwd=project_dir,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    return CheckerResult(
        project_dir=project_dir,
        command=command,
        return_code=process.returncode,
        stdout=process.stdout,
        stderr=process.stderr,
    )


def evaluate_checker_result(
    variant_dir: Path,
    variant: str,
    checker_result: CheckerResult,
    baseline_checker_result: CheckerResult | None,
) -> DiagnosticEvaluation:
    diagnostics = extract_diagnostics(checker_output(checker_result))
    normalized_diagnostics = normalize_diagnostics(diagnostics, variant_dir)
    baseline_diagnostics = (
        set(
            normalize_diagnostics(
                extract_diagnostics(checker_output(baseline_checker_result)),
                baseline_checker_result.project_dir,
            )
        )
        if baseline_checker_result is not None
        else set()
    )
    new_diagnostics = [
        diagnostic
        for diagnostic, normalized_diagnostic in zip(diagnostics, normalized_diagnostics)
        if normalized_diagnostic not in baseline_diagnostics
    ]
    return DiagnosticEvaluation(
        variant=variant,
        project_dir=str(variant_dir),
        command=checker_result.command,
        return_code=checker_result.return_code,
        diagnostic_count=len(diagnostics),
        new_diagnostics=new_diagnostics,
        new_diagnostic_count=len(new_diagnostics),
    )


def evaluate_materialized_project(
    materialized_project: Path,
    record: TestResult,
) -> MaterializedEvaluation:
    language = record.case.language
    source_file = record.case.source_file

    baseline_dir = materialized_project / "baseline"
    if not baseline_dir.is_dir():
        raise FileNotFoundError(f"missing baseline directory: {baseline_dir}")

    baseline_checker_result = run_checker(baseline_dir, language, source_file)
    baseline = evaluate_checker_result(
        baseline_dir,
        "baseline",
        baseline_checker_result,
        baseline_checker_result=None,
    )

    completions = []
    for index, _ in enumerate(record.completions):
        variant = f"completion_{index}"
        variant_dir = materialized_project / variant
        if not variant_dir.is_dir():
            raise FileNotFoundError(f"missing completion directory: {variant_dir}")
        checker_result = run_checker(variant_dir, language, source_file)
        completions.append(
            evaluate_checker_result(
                variant_dir,
                variant,
                checker_result,
                baseline_checker_result,
            )
        )
    checker = " ".join(baseline.command[:1])
    return MaterializedEvaluation(
        materialized_project=str(materialized_project),
        case=record.case,
        server=record.server,
        method=record.method,
        duration_ms=record.duration_ms,
        checker=checker,
        baseline=baseline,
        completions=completions,
    )

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--project",
        "-p",
        required=True,
        help="materialized project directory containing baseline/ and completion_N/",
    )
    parser.add_argument(
        "--result",
        "-r",
        required=True,
        help="mals-test result JSON used to infer completion directories and metadata",
    )
    parser.add_argument("--output", "-o", default=None)
    args = parser.parse_args()

    materialized_project = Path(args.project)
    record = read_test_result(args.result)
    evaluation = evaluate_materialized_project(
        materialized_project,
        record,
    )

    if args.output:
        write_materialized_evaluation(evaluation, args.output)

    payload = materialized_evaluation_to_dict(evaluation)
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
