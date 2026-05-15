#!/usr/bin/env python3
"""Calculate per-completion metrics for results produced by mals-test."""

from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


IDENTIFIER_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")

KEYWORDS = {
    "abstract",
    "as",
    "assert",
    "async",
    "await",
    "bool",
    "boolean",
    "break",
    "case",
    "catch",
    "char",
    "class",
    "const",
    "continue",
    "def",
    "default",
    "defer",
    "do",
    "double",
    "else",
    "enum",
    "extends",
    "false",
    "final",
    "finally",
    "float",
    "fn",
    "for",
    "func",
    "go",
    "if",
    "implements",
    "import",
    "in",
    "int",
    "interface",
    "let",
    "long",
    "namespace",
    "new",
    "nil",
    "none",
    "null",
    "package",
    "private",
    "protected",
    "public",
    "return",
    "static",
    "struct",
    "switch",
    "this",
    "throw",
    "throws",
    "true",
    "try",
    "type",
    "using",
    "var",
    "void",
    "while",
}


@dataclass(frozen=True)
class CursorPosition:
    line: int
    character: int
    offset: int = 0


@dataclass(frozen=True)
class TestCase:
    id: str
    dataset: str
    language: str
    root_dir: str
    source_file: str
    cursor: CursorPosition
    prefix: str
    ground_truth: str
    suffix: str = ""
    files: list[str] | None = None
    metadata: dict[str, Any] | None = None


@dataclass(frozen=True)
class TestResult:
    case: TestCase
    server: str
    method: str
    completions: list[str]
    error: str = ""
    duration_ms: int = 0
    raw_result: Any | None = None


@dataclass(frozen=True)
class MetricScores:
    exact_match: float
    edit_similarity: float
    identifier_exact_match: float
    identifier_f1: float


@dataclass(frozen=True)
class EvaluationResult:
    case: TestCase
    server: str
    method: str
    completions: list[str]
    metrics: MetricScores | None
    error: str = ""
    duration_ms: int = 0


def cursor_position_from_dict(data: dict[str, Any]) -> CursorPosition:
    return CursorPosition(
        line=int(data.get("line") or 0),
        character=int(data.get("character") or 0),
        offset=int(data.get("offset") or 0),
    )


def test_case_from_dict(data: dict[str, Any]) -> TestCase:
    return TestCase(
        id=str(data.get("id") or ""),
        dataset=str(data.get("dataset") or ""),
        language=str(data.get("language") or ""),
        root_dir=str(data.get("root_dir") or ""),
        source_file=str(data.get("source_file") or ""),
        cursor=cursor_position_from_dict(data.get("cursor") or {}),
        prefix=str(data.get("prefix") or ""),
        suffix=str(data.get("suffix") or ""),
        ground_truth=str(data.get("ground_truth") or ""),
        files=[str(item) for item in data.get("files") or []],
        metadata=data.get("metadata") if isinstance(data.get("metadata"), dict) else None,
    )


def test_result_from_dict(data: dict[str, Any]) -> TestResult:
    completions = data.get("completions") or []
    return TestResult(
        case=test_case_from_dict(data.get("case") or {}),
        server=str(data.get("server") or ""),
        method=str(data.get("method") or ""),
        completions=[str(item) for item in completions],
        error=str(data.get("error") or ""),
        duration_ms=int(data.get("duration_ms") or 0),
        raw_result=data.get("raw_result"),
    )


def evaluation_result_from_dict(data: dict[str, Any]) -> EvaluationResult:
    metrics = data.get("metrics")
    return EvaluationResult(
        case=test_case_from_dict(data.get("case") or {}),
        server=str(data.get("server") or ""),
        method=str(data.get("method") or ""),
        completions=[str(item) for item in data.get("completions") or []],
        metrics=MetricScores(**metrics) if isinstance(metrics, dict) else None,
        error=str(data.get("error") or ""),
        duration_ms=int(data.get("duration_ms") or 0),
    )


def evaluation_result_to_dict(result: EvaluationResult) -> dict[str, Any]:
    return asdict(result)


def identifiers(text: str) -> list[str]:
    return [
        item
        for item in IDENTIFIER_RE.findall(text)
        if item.lower() not in KEYWORDS
    ]


def levenshtein_distance(a: str, b: str) -> int:
    if a == b:
        return 0
    if len(a) < len(b):
        a, b = b, a
    previous = list(range(len(b) + 1))
    for i, char_a in enumerate(a, start=1):
        current = [i]
        for j, char_b in enumerate(b, start=1):
            insert = current[j - 1] + 1
            delete = previous[j] + 1
            replace = previous[j - 1] + (char_a != char_b)
            current.append(min(insert, delete, replace))
        previous = current
    return previous[-1]


def edit_similarity(prediction: str, reference: str) -> float:
    max_len = max(len(prediction), len(reference))
    if max_len == 0:
        return 1.0
    return 1.0 - levenshtein_distance(prediction, reference) / max_len


def identifier_f1(prediction_ids: list[str], reference_ids: list[str]) -> float:
    if not prediction_ids and not reference_ids:
        return 1.0
    if not prediction_ids or not reference_ids:
        return 0.0

    reference_counts: dict[str, int] = defaultdict(int)
    for item in reference_ids:
        reference_counts[item] += 1

    overlap = 0
    for item in prediction_ids:
        if reference_counts[item] > 0:
            overlap += 1
            reference_counts[item] -= 1
    if overlap == 0:
        return 0.0

    precision = overlap / len(prediction_ids)
    recall = overlap / len(reference_ids)
    return 2 * precision * recall / (precision + recall)


def calculate_metrics(completion: str, ground_truth: str) -> MetricScores:
    prediction = completion.strip()
    reference = ground_truth.strip()
    prediction_ids = identifiers(prediction)
    reference_ids = identifiers(reference)
    return MetricScores(
        exact_match=float(prediction == reference),
        edit_similarity=edit_similarity(prediction, reference),
        identifier_exact_match=float(prediction_ids == reference_ids),
        identifier_f1=identifier_f1(prediction_ids, reference_ids),
    )


def evaluate_test_result(
    record: TestResult,
    include_errors: bool = False,
) -> EvaluationResult:
    completion = record.completions[0] if record.completions else ""
    metrics = None
    if record.case.ground_truth and (include_errors or not record.error):
        metrics = calculate_metrics(completion, record.case.ground_truth)
    return EvaluationResult(
        case=record.case,
        server=record.server,
        method=record.method,
        completions=record.completions,
        metrics=metrics,
        error=record.error,
        duration_ms=record.duration_ms,
    )


def read_test_result(path: str | Path) -> TestResult:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path}: expected one JSON object")
    return test_result_from_dict(data)


def write_evaluation_result(result: EvaluationResult, path: str | Path) -> None:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(evaluation_result_to_dict(result), indent=2),
        encoding="utf-8",
    )


def read_evaluation_result(path: str | Path) -> EvaluationResult:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path}: expected one JSON object")
    return evaluation_result_from_dict(data)


def read_evaluation_results(paths: list[str | Path]) -> list[EvaluationResult]:
    records: list[EvaluationResult] = []
    for path in paths:
        records.append(read_evaluation_result(Path(path)))
    return records


def evaluate_test_result_file(
    input_path: str | Path,
    include_errors: bool = False,
) -> EvaluationResult:
    return evaluate_test_result(read_test_result(input_path), include_errors)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", "-i", default="result/completions.json")
    parser.add_argument("--output", "-o", default="result/evaluated_completions.json")
    parser.add_argument("--include-errors", action="store_true")
    args = parser.parse_args()

    result = evaluate_test_result_file(args.input, args.include_errors)
    write_evaluation_result(result, args.output)
    print(
        json.dumps(
            {
                "metrics_calculated": result.metrics is not None,
                "output": args.output,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
