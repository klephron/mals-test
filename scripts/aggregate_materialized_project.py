"""Aggregate diagnostics calculated by evaluate_materialized_project.py."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from statistics import mean

try:
    from .aggregate_common import group_dict, group_key, parse_group_by
    from .common import (
        MaterializedAggregationResult,
        MaterializedDiagnosticSummary,
        MaterializedEvaluation,
        read_materialized_evaluations,
        write_materialized_aggregation_result,
    )
except ImportError:
    from aggregate_common import group_dict, group_key, parse_group_by
    from common import (
        MaterializedAggregationResult,
        MaterializedDiagnosticSummary,
        MaterializedEvaluation,
        read_materialized_evaluations,
        write_materialized_aggregation_result,
    )


def best_completion_diagnostic(record: MaterializedEvaluation):
    return min(
        record.completion_diagnostics,
        key=lambda diagnostic: (
            diagnostic.new_diagnostic_count,
            diagnostic.diagnostic_count,
        ),
    )


def aggregate_materialized_evaluations(
    records: list[MaterializedEvaluation],
    group_by: list[str],
) -> MaterializedAggregationResult:
    fields = group_by
    groups: dict[tuple[str, ...], list[MaterializedEvaluation]] = {}
    skipped_without_metrics = 0

    for record in records:
        if not record.completion_diagnostics:
            skipped_without_metrics += 1
            continue
        groups.setdefault(group_key(record, fields), []).append(record)

    summary = []
    for key, items in sorted(groups.items()):
        best_diagnostics = [best_completion_diagnostic(record) for record in items]
        summary.append(
            MaterializedDiagnosticSummary(
                group=group_dict(fields, key),
                count=len(items),
                completion_count=sum(
                    len(record.completion_diagnostics)
                    for record in items
                ),
                baseline_diagnostic_count=mean(
                    item.baseline.diagnostic_count for item in items
                ),
                avg_completion_diagnostic_count=mean(
                    mean(diagnostic.diagnostic_count for diagnostic in record.completion_diagnostics)
                    for record in items
                ),
                avg_new_diagnostic_count=mean(
                    mean(diagnostic.new_diagnostic_count for diagnostic in record.completion_diagnostics)
                    for record in items
                ),
                best_completion_diagnostic_count=mean(
                    diagnostic.diagnostic_count for diagnostic in best_diagnostics
                ),
                best_new_diagnostic_count=mean(
                    diagnostic.new_diagnostic_count for diagnostic in best_diagnostics
                ),
            )
        )

    return MaterializedAggregationResult(
        summary=summary,
        skipped_without_metrics=skipped_without_metrics,
    )


def aggregate_materialized_evaluation_files(
    input_paths: list[str | Path],
    group_by: list[str],
) -> MaterializedAggregationResult:
    return aggregate_materialized_evaluations(
        read_materialized_evaluations(input_paths),
        group_by,
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        "-o",
        default="result/materialized_diagnostics_summary.json",
    )
    parser.add_argument("--group-by", default="server,dataset,language")
    parser.add_argument("inputs", nargs="+")
    args = parser.parse_args()

    result = aggregate_materialized_evaluation_files(
        args.inputs,
        parse_group_by(args.group_by),
    )
    write_materialized_aggregation_result(result, args.output)
    print(
        json.dumps(
            {
                "groups": len(result.summary),
                "output": args.output,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
