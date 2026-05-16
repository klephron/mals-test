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


def aggregate_evaluation_results(
    records: list[EvaluationResult],
    group_by: list[str],
) -> AggregationResult:
    fields = group_by
    groups: dict[tuple[str, ...], list[tuple[EvaluationResult, MetricScores]]] = {}
    skipped_without_metrics = 0

    for record in records:
        metrics = best_record_metrics(record)
        if metrics is None:
            skipped_without_metrics += 1
            continue
        groups.setdefault(group_key(record, fields), []).append((record, metrics))

    summary = []
    for key, items in sorted(groups.items()):
        metrics = MetricScores(
            exact_match=mean(metrics.exact_match for _, metrics in items),
            edit_similarity=mean(metrics.edit_similarity for _, metrics in items),
            identifier_exact_match=mean(
                metrics.identifier_exact_match for _, metrics in items
            ),
            identifier_f1=mean(metrics.identifier_f1 for _, metrics in items),
        )
        summary.append(
            MetricSummary(
                group=group_dict(fields, key),
                count=len(items),
                metrics=metrics,
            )
        )

    return AggregationResult(
        summary=summary,
        record_count=len(records),
        skipped_without_metrics=skipped_without_metrics,
    )


def aggregate_evaluation_result_files(
    input_paths: list[str | Path],
    group_by: list[str],
) -> AggregationResult:
    return aggregate_evaluation_results(read_evaluation_results(input_paths), group_by)


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
                "records": result.record_count,
                "skipped_without_metrics": result.skipped_without_metrics,
                "output": args.output,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
