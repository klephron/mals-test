"""Aggregate metrics calculated by evaluate_test_result.py."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from statistics import mean

try:
    from .aggregate_common import group_dict, group_key, parse_group_by
    from .common import (
        AggregationResult,
        EvaluationResult,
        MetricSummary,
        MetricScores,
        read_evaluation_results,
        write_aggregation_result,
    )
except ImportError:
    from aggregate_common import group_dict, group_key, parse_group_by
    from common import (
        AggregationResult,
        EvaluationResult,
        MetricSummary,
        MetricScores,
        read_evaluation_results,
        write_aggregation_result,
    )


METRIC_FIELDS = [
    "exact_match",
    "edit_similarity",
    "identifier_exact_match",
    "identifier_f1",
]


def combined_metric_score(metrics: MetricScores) -> float:
    return sum(getattr(metrics, field) for field in METRIC_FIELDS)


def best_record_metrics(record: EvaluationResult) -> MetricScores | None:
    if not record.completion_metrics:
        return None
    return max(
        record.completion_metrics,
        key=lambda item: combined_metric_score(item.metrics),
    ).metrics


def avg_record_metrics(record: EvaluationResult) -> MetricScores:
    return MetricScores(
        exact_match=mean(
            completion.metrics.exact_match for completion in record.completion_metrics
        ),
        edit_similarity=mean(
            completion.metrics.edit_similarity for completion in record.completion_metrics
        ),
        identifier_exact_match=mean(
            completion.metrics.identifier_exact_match
            for completion in record.completion_metrics
        ),
        identifier_f1=mean(
            completion.metrics.identifier_f1 for completion in record.completion_metrics
        ),
    )


def avg_metrics(metrics: list[MetricScores]) -> MetricScores:
    return MetricScores(
        exact_match=mean(item.exact_match for item in metrics),
        edit_similarity=mean(item.edit_similarity for item in metrics),
        identifier_exact_match=mean(item.identifier_exact_match for item in metrics),
        identifier_f1=mean(item.identifier_f1 for item in metrics),
    )


def aggregate_evaluation_results(
    records: list[EvaluationResult],
    group_by: list[str],
) -> AggregationResult:
    fields = group_by
    groups: dict[tuple[str, ...], list[EvaluationResult]] = {}
    skipped_without_metrics = 0

    for record in records:
        if not record.completion_metrics:
            skipped_without_metrics += 1
            continue
        groups.setdefault(group_key(record, fields), []).append(record)

    summary = []
    for key, items in sorted(groups.items()):
        record_avg_metrics = [avg_record_metrics(record) for record in items]
        record_best_metrics = [
            metrics
            for record in items
            if (metrics := best_record_metrics(record)) is not None
        ]
        summary.append(
            MetricSummary(
                group=group_dict(fields, key),
                count=len(items),
                avg_metrics=avg_metrics(record_avg_metrics),
                best_metrics=avg_metrics(record_best_metrics),
            )
        )

    return AggregationResult(
        summary=summary,
        skipped_without_metrics=skipped_without_metrics,
    )


def aggregate_evaluation_result_files(
    input_paths: list[str | Path],
    group_by: list[str],
) -> AggregationResult:
    return aggregate_evaluation_results(
        read_evaluation_results(input_paths),
        group_by,
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", "-o", default="result/metrics_summary.json")
    parser.add_argument("--group-by", default="server,dataset,language")
    parser.add_argument("inputs", nargs="+")
    args = parser.parse_args()

    result = aggregate_evaluation_result_files(args.inputs, parse_group_by(args.group_by))
    write_aggregation_result(result, args.output)
    print(
        json.dumps(
            {
                "groups": len(result.summary),
                "output": args.output,
                "skipped_without_metrics": result.skipped_without_metrics,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
