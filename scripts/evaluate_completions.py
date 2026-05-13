#!/usr/bin/env python3
"""Summarize JSONL results produced by the Go LSP benchmark runner."""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path
from statistics import mean
from typing import Any


METRICS = [
    "exact_match",
    "edit_similarity",
    "identifier_exact_match",
    "identifier_f1",
]


def key_for(record: dict[str, Any], group_by: list[str]) -> tuple[str, ...]:
    case = record.get("case") or {}
    values = []
    for field in group_by:
        if field == "server":
            values.append(record.get("server", ""))
        elif field == "dataset":
            values.append(case.get("dataset", ""))
        elif field == "language":
            values.append(case.get("language", ""))
        else:
            values.append(str(record.get(field, case.get(field, ""))))
    return tuple(values)


def record_metrics(record: dict[str, Any]) -> dict[str, float] | None:
    metrics = record.get("metrics")
    if not isinstance(metrics, dict):
        return None
    out = {}
    for metric in METRICS:
        value = metrics.get(metric)
        if value is None:
            return None
        out[metric] = float(value)
    return out


def summarize(records: list[dict[str, Any]], group_by: list[str], include_errors: bool) -> dict[str, Any]:
    groups: dict[tuple[str, ...], list[dict[str, Any]]] = defaultdict(list)
    rows = []
    skipped_without_metrics = 0

    for record in records:
        has_error = bool(record.get("error"))
        metrics = record_metrics(record)
        if has_error and not include_errors:
            continue
        if metrics is None:
            skipped_without_metrics += 1
            continue

        row = {
            "id": (record.get("case") or {}).get("id"),
            "server": record.get("server"),
            "dataset": (record.get("case") or {}).get("dataset"),
            "language": (record.get("case") or {}).get("language"),
            "error": record.get("error", ""),
            **metrics,
        }
        rows.append(row)
        groups[key_for(record, group_by)].append({"metrics": metrics, "error": has_error})

    summary = []
    for key, items in sorted(groups.items()):
        item = {field: value for field, value in zip(group_by, key)}
        item["count"] = len(items)
        item["error_count"] = sum(1 for entry in items if entry["error"])
        for metric in METRICS:
            item[metric] = mean(entry["metrics"][metric] for entry in items)
        summary.append(item)

    return {
        "summary": summary,
        "records": rows,
        "skipped_without_metrics": skipped_without_metrics,
    }


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    records = []
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if line.strip():
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError as exc:
                    raise ValueError(f"{path}:{line_number}: invalid JSON: {exc}") from exc
    return records


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", "-i", default="results/completions.jsonl")
    parser.add_argument("--output", "-o", default="results/metrics.json")
    parser.add_argument("--group-by", default="server,dataset,language")
    parser.add_argument("--include-errors", action="store_true")
    args = parser.parse_args()

    group_by = [part.strip() for part in args.group_by.split(",") if part.strip()]
    records = load_jsonl(Path(args.input))
    output = summarize(records, group_by, args.include_errors)

    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output).write_text(json.dumps(output, indent=2), encoding="utf-8")
    print(
        json.dumps(
            {
                "groups": len(output["summary"]),
                "records": len(output["records"]),
                "skipped_without_metrics": output["skipped_without_metrics"],
                "output": args.output,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
