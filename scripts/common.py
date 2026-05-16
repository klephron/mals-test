from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import cast


JsonObject = dict[str, object]


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
    metadata: dict[str, object] | None = None


@dataclass(frozen=True)
class TestResult:
    case: TestCase
    server: str
    method: str
    completions: list[str]
    error: str = ""
    duration_ms: int = 0
    raw_result: object | None = None


@dataclass(frozen=True)
class MetricScores:
    exact_match: float
    edit_similarity: float
    identifier_exact_match: float
    identifier_f1: float


@dataclass(frozen=True)
class CompletionEvaluation:
    completion: str
    metrics: MetricScores


@dataclass(frozen=True)
class EvaluationResult:
    case: TestCase
    server: str
    method: str
    completion_metrics: list[CompletionEvaluation]


@dataclass(frozen=True)
class DiagnosticEvaluation:
    variant: str
    project_dir: str
    command: list[str]
    return_code: int
    diagnostic_count: int
    new_diagnostics: list[str]
    new_diagnostic_count: int


@dataclass(frozen=True)
class MaterializedEvaluation:
    materialized_project: str
    case: TestCase
    server: str
    method: str
    duration_ms: int
    checker: str
    baseline: DiagnosticEvaluation
    completions: list[DiagnosticEvaluation]


@dataclass(frozen=True)
class MetricSummary:
    group: dict[str, str]
    count: int
    metrics: MetricScores


@dataclass(frozen=True)
class AggregationResult:
    summary: list[MetricSummary]
    record_count: int
    skipped_without_metrics: int = 0


@dataclass(frozen=True)
class MaterializedDiagnosticSummary:
    group: dict[str, str]
    count: int
    completion_count: int
    avg_baseline_diagnostic_count: float
    avg_completion_diagnostic_count: float
    avg_new_diagnostic_count: float


@dataclass(frozen=True)
class MaterializedAggregationResult:
    summary: list[MaterializedDiagnosticSummary]
    record_count: int
    completion_count: int


def json_object(value: object) -> JsonObject:
    return cast(JsonObject, value) if isinstance(value, dict) else {}


def json_list(value: object) -> list[object]:
    return value if isinstance(value, list) else []


def string_value(value: object) -> str:
    return str(value or "")


def int_value(value: object) -> int:
    if isinstance(value, str | bytes | bytearray | int | float):
        try:
            return int(value)
        except ValueError:
            return 0
    return 0


def float_value(value: object) -> float:
    if isinstance(value, str | bytes | bytearray | int | float):
        try:
            return float(value)
        except ValueError:
            return 0.0
    return 0.0


def metric_scores_from_dict(data: JsonObject) -> MetricScores:
    return MetricScores(
        exact_match=float_value(data.get("exact_match")),
        edit_similarity=float_value(data.get("edit_similarity")),
        identifier_exact_match=float_value(data.get("identifier_exact_match")),
        identifier_f1=float_value(data.get("identifier_f1")),
    )


def cursor_position_from_dict(data: JsonObject) -> CursorPosition:
    return CursorPosition(
        line=int_value(data.get("line")),
        character=int_value(data.get("character")),
        offset=int_value(data.get("offset")),
    )


def test_case_from_dict(data: JsonObject) -> TestCase:
    files = json_list(data.get("files"))
    metadata = data.get("metadata")
    return TestCase(
        id=string_value(data.get("id")),
        dataset=string_value(data.get("dataset")),
        language=string_value(data.get("language")),
        root_dir=string_value(data.get("root_dir")),
        source_file=string_value(data.get("source_file")),
        cursor=cursor_position_from_dict(json_object(data.get("cursor"))),
        prefix=string_value(data.get("prefix")),
        suffix=string_value(data.get("suffix")),
        ground_truth=string_value(data.get("ground_truth")),
        files=[string_value(item) for item in files],
        metadata=json_object(metadata) if isinstance(metadata, dict) else None,
    )


def test_result_from_dict(data: JsonObject) -> TestResult:
    completions = json_list(data.get("completions"))
    return TestResult(
        case=test_case_from_dict(json_object(data.get("case"))),
        server=string_value(data.get("server")),
        method=string_value(data.get("method")),
        completions=[string_value(item) for item in completions],
        error=string_value(data.get("error")),
        duration_ms=int_value(data.get("duration_ms")),
        raw_result=data.get("raw_result"),
    )


def completion_evaluation_from_dict(data: JsonObject) -> CompletionEvaluation | None:
    metrics = data.get("metrics")
    if not isinstance(metrics, dict):
        return None
    return CompletionEvaluation(
        completion=string_value(data.get("completion")),
        metrics=metric_scores_from_dict(json_object(metrics)),
    )


def completion_evaluations_from_list(data: list[object]) -> list[CompletionEvaluation]:
    items = []
    for item in data:
        completion_evaluation = completion_evaluation_from_dict(json_object(item))
        if completion_evaluation is not None:
            items.append(completion_evaluation)
    return items


def evaluation_result_from_dict(data: JsonObject) -> EvaluationResult:
    return EvaluationResult(
        case=test_case_from_dict(json_object(data.get("case"))),
        server=string_value(data.get("server")),
        method=string_value(data.get("method")),
        completion_metrics=completion_evaluations_from_list(
            json_list(data.get("completion_metrics"))
        ),
    )


def evaluation_result_to_dict(result: EvaluationResult) -> JsonObject:
    return asdict(result)


def diagnostic_evaluation_from_dict(data: JsonObject) -> DiagnosticEvaluation:
    return DiagnosticEvaluation(
        variant=string_value(data.get("variant")),
        project_dir=string_value(data.get("project_dir")),
        command=[string_value(item) for item in json_list(data.get("command"))],
        return_code=int_value(data.get("return_code")),
        diagnostic_count=int_value(data.get("diagnostic_count")),
        new_diagnostics=[
            string_value(item) for item in json_list(data.get("new_diagnostics"))
        ],
        new_diagnostic_count=int_value(data.get("new_diagnostic_count")),
    )


def materialized_evaluation_from_dict(data: JsonObject) -> MaterializedEvaluation:
    return MaterializedEvaluation(
        materialized_project=string_value(data.get("materialized_project")),
        case=test_case_from_dict(json_object(data.get("case"))),
        server=string_value(data.get("server")),
        method=string_value(data.get("method")),
        duration_ms=int_value(data.get("duration_ms")),
        checker=string_value(data.get("checker")),
        baseline=diagnostic_evaluation_from_dict(json_object(data.get("baseline"))),
        completions=[
            diagnostic_evaluation_from_dict(json_object(item))
            for item in json_list(data.get("completions"))
        ],
    )


def materialized_evaluation_to_dict(result: MaterializedEvaluation) -> JsonObject:
    return asdict(result)


def aggregation_result_to_dict(result: AggregationResult) -> JsonObject:
    return asdict(result)


def materialized_aggregation_result_to_dict(
    result: MaterializedAggregationResult,
) -> JsonObject:
    return asdict(result)


def metric_summary_from_dict(data: JsonObject) -> MetricSummary:
    return MetricSummary(
        group={
            string_value(field): string_value(value)
            for field, value in json_object(data.get("group")).items()
        },
        count=int_value(data.get("count")),
        metrics=metric_scores_from_dict(json_object(data.get("metrics"))),
    )


def aggregation_result_from_dict(data: JsonObject) -> AggregationResult:
    return AggregationResult(
        summary=[
            metric_summary_from_dict(json_object(summary))
            for summary in json_list(data.get("summary"))
        ],
        record_count=int_value(data.get("record_count")),
        skipped_without_metrics=int_value(data.get("skipped_without_metrics")),
    )


def materialized_diagnostic_summary_from_dict(
    data: JsonObject,
) -> MaterializedDiagnosticSummary:
    return MaterializedDiagnosticSummary(
        group={
            string_value(field): string_value(value)
            for field, value in json_object(data.get("group")).items()
        },
        count=int_value(data.get("count")),
        completion_count=int_value(data.get("completion_count")),
        avg_baseline_diagnostic_count=float_value(
            data.get("avg_baseline_diagnostic_count")
        ),
        avg_completion_diagnostic_count=float_value(
            data.get("avg_completion_diagnostic_count")
        ),
        avg_new_diagnostic_count=float_value(data.get("avg_new_diagnostic_count")),
    )


def materialized_aggregation_result_from_dict(
    data: JsonObject,
) -> MaterializedAggregationResult:
    return MaterializedAggregationResult(
        summary=[
            materialized_diagnostic_summary_from_dict(json_object(summary))
            for summary in json_list(data.get("summary"))
        ],
        record_count=int_value(data.get("record_count")),
        completion_count=int_value(data.get("completion_count")),
    )


def read_test_result(path: str | Path) -> TestResult:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path}: expected one JSON object")
    return test_result_from_dict(json_object(data))


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
    return evaluation_result_from_dict(json_object(data))


def read_evaluation_results(paths: list[str | Path]) -> list[EvaluationResult]:
    records: list[EvaluationResult] = []
    for path in paths:
        records.append(read_evaluation_result(Path(path)))
    return records


def write_materialized_evaluation(
    result: MaterializedEvaluation,
    path: str | Path,
) -> None:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(materialized_evaluation_to_dict(result), indent=2),
        encoding="utf-8",
    )


def read_materialized_evaluation(path: str | Path) -> MaterializedEvaluation:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path}: expected one JSON object")
    return materialized_evaluation_from_dict(json_object(data))


def read_materialized_evaluations(
    paths: list[str | Path],
) -> list[MaterializedEvaluation]:
    records: list[MaterializedEvaluation] = []
    for path in paths:
        records.append(read_materialized_evaluation(Path(path)))
    return records


def write_aggregation_result(result: AggregationResult, path: str | Path) -> None:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(aggregation_result_to_dict(result), indent=2),
        encoding="utf-8",
    )


def read_aggregation_result(path: str | Path) -> AggregationResult:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path}: expected one JSON object")
    return aggregation_result_from_dict(json_object(data))


def write_materialized_aggregation_result(
    result: MaterializedAggregationResult,
    path: str | Path,
) -> None:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(materialized_aggregation_result_to_dict(result), indent=2),
        encoding="utf-8",
    )


def read_materialized_aggregation_result(
    path: str | Path,
) -> MaterializedAggregationResult:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path}: expected one JSON object")
    return materialized_aggregation_result_from_dict(json_object(data))
