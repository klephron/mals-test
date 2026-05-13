#!/usr/bin/env python3
"""Evaluate LSP completion JSONL produced by cmd/lspbench."""

from __future__ import annotations

import argparse
import difflib
import json
import keyword
import re
from collections import Counter, defaultdict
from pathlib import Path
from statistics import mean


IDENT_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
EXTRA_KEYWORDS = {
    "true",
    "false",
    "null",
    "nil",
    "none",
    "public",
    "private",
    "protected",
    "static",
    "final",
    "class",
    "interface",
    "package",
    "import",
    "return",
    "if",
    "else",
    "for",
    "while",
    "switch",
    "case",
    "break",
    "continue",
    "func",
    "fn",
    "let",
    "const",
    "var",
}


def normalize(text: str, mode: str) -> str:
    if mode == "strip":
        return text.strip()
    if mode == "space":
        return " ".join(text.split())
    return text


def identifiers(text: str) -> list[str]:
    ids = []
    for item in IDENT_RE.findall(text):
        lowered = item.lower()
        if lowered in keyword.kwlist or lowered in EXTRA_KEYWORDS:
            continue
        ids.append(item)
    return ids


def f1(pred: list[str], ref: list[str]) -> float:
    if not pred and not ref:
        return 1.0
    if not pred or not ref:
        return 0.0
    overlap = sum((Counter(pred) & Counter(ref)).values())
    if overlap == 0:
        return 0.0
    precision = overlap / len(pred)
    recall = overlap / len(ref)
    return 2 * precision * recall / (precision + recall)


def score_record(record: dict, normalize_mode: str) -> dict:
    pred = normalize(record.get("completion") or "", normalize_mode)
    ref = normalize(record.get("case", {}).get("ground_truth") or "", normalize_mode)
    pred_ids = identifiers(pred)
    ref_ids = identifiers(ref)
    return {
        "exact_match": float(pred == ref),
        "edit_similarity": difflib.SequenceMatcher(a=pred, b=ref).ratio(),
        "identifier_exact_match": float(pred_ids == ref_ids),
        "identifier_f1": f1(pred_ids, ref_ids),
    }


def key_for(record: dict, group_by: list[str]) -> tuple[str, ...]:
    case = record.get("case", {})
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


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", "-i", default="results/completions.jsonl")
    parser.add_argument("--output", "-o", default="results/metrics.json")
    parser.add_argument("--normalize", choices=["none", "strip", "space"], default="strip")
    parser.add_argument("--group-by", default="server,dataset,language")
    parser.add_argument("--include-errors", action="store_true")
    args = parser.parse_args()

    group_by = [part.strip() for part in args.group_by.split(",") if part.strip()]
    groups: dict[tuple[str, ...], list[dict]] = defaultdict(list)
    rows = []

    with Path(args.input).open(encoding="utf-8") as handle:
        for line in handle:
            record = json.loads(line)
            if record.get("error") and not args.include_errors:
                continue
            scores = score_record(record, args.normalize)
            row = {
                "id": record.get("case", {}).get("id"),
                "server": record.get("server"),
                **scores,
            }
            rows.append(row)
            groups[key_for(record, group_by)].append(scores)

    summary = []
    for key, scores in sorted(groups.items()):
        item = {field: value for field, value in zip(group_by, key)}
        item["count"] = len(scores)
        for metric in ["exact_match", "edit_similarity", "identifier_exact_match", "identifier_f1"]:
            item[metric] = mean(score[metric] for score in scores) if scores else 0.0
        summary.append(item)

    output = {"summary": summary, "records": rows}
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output).write_text(json.dumps(output, indent=2), encoding="utf-8")
    print(json.dumps({"groups": len(summary), "records": len(rows), "output": args.output}, indent=2))


if __name__ == "__main__":
    main()
