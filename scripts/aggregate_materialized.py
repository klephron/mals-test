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
        MaterializedResult,
        read_materialized_results,
        write_materialized_aggregation_result,
    )
except ImportError:
    from aggregate_common import group_dict, group_key, parse_group_by
    from common import (
        MaterializedAggregationResult,
        MaterializedDiagnosticSummary,
        MaterializedResult,
        read_materialized_results,
        write_materialized_aggregation_result,
    )


def best_result_diagnostic(record: MaterializedResult):
    return min(
        record.completion_diagnostics,
        key=lambda diagnostic: (
            diagnostic.new_diagnostic_count,
            diagnostic.diagnostic_count,
        ),
    )


def aggregate_materialized_results(
    results: list[MaterializedResult],
    group_by: list[str],
) -> MaterializedAggregationResult:
    fields = group_by
    groups: dict[tuple[str, ...], list[MaterializedResult]] = {}
    skipped_without_metrics = 0

    for result in results:
        if not result.completion_diagnostics:
            skipped_without_metrics += 1
            continue
        groups.setdefault(group_key(result, fields), []).append(result)

    summary = []
    for key, items in sorted(groups.items()):
        best_results_diagnostic = [best_result_diagnostic(result) for result in items]
        summary.append(
            MaterializedDiagnosticSummary(
                group=group_dict(fields, key),
                count=len(items),
                completion_count=sum(
                    len(record.completion_diagnostics)
                    for record in items
                ),
                baseline_diagnostic_count=mean(
                    result.baseline.diagnostic_count for result in items
                ),
                avg_completion_diagnostic_count=mean(
                    mean(diagnostic.diagnostic_count for diagnostic in result.completion_diagnostics)
                    for result in items
                ),
                avg_new_diagnostic_count=mean(
                    mean(diagnostic.new_diagnostic_count for diagnostic in result.completion_diagnostics)
                    for result in items
                ),
                best_completion_diagnostic_count=mean(
                    diagnostic.diagnostic_count for diagnostic in best_results_diagnostic
                ),
                best_new_diagnostic_count=mean(
                    diagnostic.new_diagnostic_count for diagnostic in best_results_diagnostic
                ),
            )
        )

    return MaterializedAggregationResult(
        summary=summary,
        skipped_without_metrics=skipped_without_metrics,
    )


def aggregate_materialized_result_files(
    input_paths: list[str | Path],
    group_by: list[str],
) -> MaterializedAggregationResult:
    return aggregate_materialized_results(
        read_materialized_results(input_paths),
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

    result = aggregate_materialized_result_files(
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
