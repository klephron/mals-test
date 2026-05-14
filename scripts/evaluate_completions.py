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
class CompletionResult:
    case: dict[str, Any]
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
class EvaluatedCompletion:
    case: dict[str, Any]
    server: str
    method: str
    completion: str
    completions: list[str]
    metrics: MetricScores | None
    error: str = ""
    duration_ms: int = 0


@dataclass(frozen=True)
class EvaluationResult:
    records: list[EvaluatedCompletion]
    skipped_errors: int = 0
    skipped_without_ground_truth: int = 0


def completion_result_from_dict(data: dict[str, Any]) -> CompletionResult:
    completions = data.get("completions") or []
    return CompletionResult(
        case=data.get("case") or {},
        server=str(data.get("server") or ""),
        method=str(data.get("method") or ""),
        completions=[str(item) for item in completions],
        error=str(data.get("error") or ""),
        duration_ms=int(data.get("duration_ms") or 0),
        raw_result=data.get("raw_result"),
    )


def evaluated_completion_from_dict(data: dict[str, Any]) -> EvaluatedCompletion:
    metrics = data.get("metrics")
    return EvaluatedCompletion(
        case=data.get("case") or {},
        server=str(data.get("server") or ""),
        method=str(data.get("method") or ""),
        completion=str(data.get("completion") or ""),
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


def evaluate_completion(record: CompletionResult) -> EvaluatedCompletion | None:
    if "ground_truth" not in record.case:
        return None
    completion = record.completions[0] if record.completions else ""
    return EvaluatedCompletion(
        case=record.case,
        server=record.server,
        method=record.method,
        completion=completion,
        completions=record.completions,
        metrics=calculate_metrics(completion, str(record.case.get("ground_truth") or "")),
        error=record.error,
        duration_ms=record.duration_ms,
    )


def evaluate_completions(
    records: list[CompletionResult],
    include_errors: bool = False,
) -> EvaluationResult:
    evaluated: list[EvaluatedCompletion] = []
    skipped_errors = 0
    skipped_without_ground_truth = 0

    for record in records:
        if record.error and not include_errors:
            skipped_errors += 1
            continue
        item = evaluate_completion(record)
        if item is None:
            skipped_without_ground_truth += 1
            continue
        evaluated.append(item)

    return EvaluationResult(
        records=evaluated,
        skipped_errors=skipped_errors,
        skipped_without_ground_truth=skipped_without_ground_truth,
    )


def load_json_records(path: Path) -> list[dict[str, Any]]:
    if path.is_dir():
        records: list[dict[str, Any]] = []
        for item in sorted(path.rglob("*.json")):
            records.extend(load_json_records(item))
        return records

    if path.suffix == ".json":
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, list):
            return data
        if isinstance(data, dict) and "records" in data:
            return data["records"]
        if isinstance(data, dict):
            return [data]
        raise ValueError(f"{path}: expected JSON object or array")

    records = []
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if line.strip():
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError as exc:
                    raise ValueError(f"{path}:{line_number}: invalid JSON: {exc}") from exc
    return records


def read_completion_results(path: str | Path) -> list[CompletionResult]:
    return [completion_result_from_dict(item) for item in load_json_records(Path(path))]


def write_evaluation_result(result: EvaluationResult, path: str | Path) -> None:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(evaluation_result_to_dict(result), indent=2),
        encoding="utf-8",
    )


def read_evaluation_result(path: str | Path) -> EvaluationResult:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    records = [evaluated_completion_from_dict(item) for item in data.get("records", [])]
    return EvaluationResult(
        records=records,
        skipped_errors=int(data.get("skipped_errors") or 0),
        skipped_without_ground_truth=int(data.get("skipped_without_ground_truth") or 0),
    )


def evaluate_completion_files(
    input_path: str | Path,
    include_errors: bool = False,
) -> EvaluationResult:
    return evaluate_completions(read_completion_results(input_path), include_errors)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", "-i", default="results/completions.json")
    parser.add_argument("--output", "-o", default="results/evaluated_completions.json")
    parser.add_argument("--include-errors", action="store_true")
    args = parser.parse_args()

    result = evaluate_completion_files(args.input, args.include_errors)
    write_evaluation_result(result, args.output)
    print(
        json.dumps(
            {
                "records": len(result.records),
                "skipped_errors": result.skipped_errors,
                "skipped_without_ground_truth": result.skipped_without_ground_truth,
                "output": args.output,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
