#!/usr/bin/env python3
"""Aggregate metrics calculated by evaluate_completions.py."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from statistics import mean
from typing import Any

try:
    from .evaluate_completions import (
        EvaluatedCompletion,
        EvaluationResult,
        MetricScores,
        evaluated_completion_from_dict,
    )
except ImportError:
    from evaluate_completions import (
        EvaluatedCompletion,
        EvaluationResult,
        MetricScores,
        evaluated_completion_from_dict,
    )


METRIC_FIELDS = [
    "exact_match",
    "edit_similarity",
    "identifier_exact_match",
    "identifier_f1",
]


@dataclass(frozen=True)
class MetricSummary:
    group: dict[str, str]
    count: int
    error_count: int
    metrics: MetricScores


@dataclass(frozen=True)
class AggregationResult:
    summary: list[MetricSummary]
    record_count: int
    skipped_without_metrics: int = 0


def aggregation_result_to_dict(result: AggregationResult) -> dict[str, Any]:
    return asdict(result)


def group_value(record: EvaluatedCompletion, field: str) -> str:
    if field == "server":
        return record.server
    if field == "method":
        return record.method
    if field == "dataset":
        return str(record.case.get("dataset") or "")
    if field == "language":
        return str(record.case.get("language") or "")
    if field == "id":
        return str(record.case.get("id") or "")
    return str(getattr(record, field, record.case.get(field, "")) or "")


def group_key(record: EvaluatedCompletion, group_by: list[str]) -> tuple[str, ...]:
    return tuple(group_value(record, field) for field in group_by)


def aggregate_metrics(
    records: list[EvaluatedCompletion],
    group_by: list[str] | None = None,
) -> AggregationResult:
    fields = group_by or ["server", "dataset", "language"]
    groups: dict[tuple[str, ...], list[EvaluatedCompletion]] = {}
    skipped_without_metrics = 0

    for record in records:
        if record.metrics is None:
            skipped_without_metrics += 1
            continue
        groups.setdefault(group_key(record, fields), []).append(record)

    summary = []
    for key, items in sorted(groups.items()):
        metrics = MetricScores(
            exact_match=mean(item.metrics.exact_match for item in items if item.metrics),
            edit_similarity=mean(item.metrics.edit_similarity for item in items if item.metrics),
            identifier_exact_match=mean(
                item.metrics.identifier_exact_match for item in items if item.metrics
            ),
            identifier_f1=mean(item.metrics.identifier_f1 for item in items if item.metrics),
        )
        summary.append(
            MetricSummary(
                group={field: value for field, value in zip(fields, key)},
                count=len(items),
                error_count=sum(1 for item in items if item.error),
                metrics=metrics,
            )
        )

    return AggregationResult(
        summary=summary,
        record_count=len(records),
        skipped_without_metrics=skipped_without_metrics,
    )


def aggregate_evaluation_result(
    result: EvaluationResult,
    group_by: list[str] | None = None,
) -> AggregationResult:
    return aggregate_metrics(result.records, group_by)


def load_evaluated_records(path: Path) -> list[EvaluatedCompletion]:
    if path.is_dir():
        records: list[EvaluatedCompletion] = []
        for item in sorted(path.rglob("*.json")):
            records.extend(load_evaluated_records(item))
        return records

    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict) and "records" in data:
        return [evaluated_completion_from_dict(item) for item in data["records"]]
    if isinstance(data, list):
        return [evaluated_completion_from_dict(item) for item in data]
    if isinstance(data, dict):
        return [evaluated_completion_from_dict(data)]
    raise ValueError(f"{path}: expected JSON object or array")


def read_evaluated_records(path: str | Path) -> list[EvaluatedCompletion]:
    return load_evaluated_records(Path(path))


def write_aggregation_result(result: AggregationResult, path: str | Path) -> None:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(aggregation_result_to_dict(result), indent=2),
        encoding="utf-8",
    )


def read_aggregation_result(path: str | Path) -> AggregationResult:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return AggregationResult(
        summary=[
            MetricSummary(
                group=item.get("group") or {},
                count=int(item.get("count") or 0),
                error_count=int(item.get("error_count") or 0),
                metrics=MetricScores(**(item.get("metrics") or {})),
            )
            for item in data.get("summary", [])
        ],
        record_count=int(data.get("record_count") or 0),
        skipped_without_metrics=int(data.get("skipped_without_metrics") or 0),
    )


def aggregate_metric_files(
    input_path: str | Path,
    group_by: list[str] | None = None,
) -> AggregationResult:
    return aggregate_metrics(read_evaluated_records(input_path), group_by)


def parse_group_by(value: str) -> list[str]:
    return [part.strip() for part in value.split(",") if part.strip()]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", "-i", default="results/evaluated_completions.json")
    parser.add_argument("--output", "-o", default="results/metrics_summary.json")
    parser.add_argument("--group-by", default="server,dataset,language")
    args = parser.parse_args()

    result = aggregate_metric_files(args.input, parse_group_by(args.group_by))
    write_aggregation_result(result, args.output)
    print(
        json.dumps(
            {
                "groups": len(result.summary),
                "records": result.record_count,
                "skipped_without_metrics": result.skipped_without_metrics,
                "output": args.output,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
