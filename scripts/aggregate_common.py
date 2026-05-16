"""Shared helpers for result aggregation scripts."""

from __future__ import annotations


def parse_group_by(value: str) -> list[str]:
    return [part.strip() for part in value.split(",") if part.strip()]


def group_value(record: object, field: str) -> str:
    if field in {"server", "method"}:
        return str(getattr(record, field, "") or "")

    case = getattr(record, "case", None)
    if case is not None and hasattr(case, field):
        return str(getattr(case, field) or "")

    return str(getattr(record, field, "") or "")


def group_key(record: object, group_by: list[str]) -> tuple[str, ...]:
    return tuple(group_value(record, field) for field in group_by)


def group_dict(fields: list[str], key: tuple[str, ...]) -> dict[str, str]:
    return {field: value for field, value in zip(fields, key)}
