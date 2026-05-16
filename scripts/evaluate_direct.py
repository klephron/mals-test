"""Calculate per-completion metrics for results produced by mals-test."""

from __future__ import annotations

import argparse
import importlib
import json
import re
from collections.abc import Iterator
from collections import defaultdict
from enum import Enum
from pathlib import Path
from types import ModuleType
from typing import Callable

from tree_sitter import Language, Node, Parser

try:
    from .common import (
        MetricEvaluation,
        DirectResult,
        MetricScores,
        TestResult,
        read_test_result,
        write_direct_result,
    )
except ImportError:
    from common import (
        MetricEvaluation,
        DirectResult,
        MetricScores,
        TestResult,
        read_test_result,
        write_direct_result,
    )


class IdentifierMetricsMode(str, Enum):
    REGEX = "regex"
    TREE_SITTER = "tree-sitter"

    def __str__(self) -> str:
        return self.value


def identifier_metrics_mode(value: str | IdentifierMetricsMode) -> IdentifierMetricsMode:
    return value if isinstance(value, IdentifierMetricsMode) else IdentifierMetricsMode(value)


TREE_SITTER_PACKAGES = {
    "cpp": "tree_sitter_cpp",
    "csharp": "tree_sitter_c_sharp",
    "go": "tree_sitter_go",
    "java": "tree_sitter_java",
    "javascript": "tree_sitter_javascript",
    "js": "tree_sitter_javascript",
    "python": "tree_sitter_python",
    "rust": "tree_sitter_rust",
    "typescript": "tree_sitter_typescript",
}

TREE_SITTER_LANGUAGE_FACTORIES = {
    "typescript": ("language_typescript", "language"),
}


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


def metric_scores(
    prediction: str,
    reference: str,
    prediction_ids: list[str],
    reference_ids: list[str],
) -> MetricScores:
    return MetricScores(
        exact_match=float(prediction == reference),
        edit_similarity=edit_similarity(prediction, reference),
        identifier_exact_match=float(prediction_ids == reference_ids),
        identifier_f1=identifier_f1(prediction_ids, reference_ids),
    )


def regex_identifiers(text: str) -> list[str]:
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

    return [item for item in re.compile(r"[A-Za-z_][A-Za-z0-9_]*").findall(text) if item not in KEYWORDS]


def calculate_metrics_regex(completion: str, ground_truth: str) -> MetricScores:
    prediction = completion.strip()
    reference = ground_truth.strip()
    prediction_ids = regex_identifiers(prediction)
    reference_ids = regex_identifiers(reference)
    return metric_scores(prediction, reference, prediction_ids, reference_ids)


def tree_sitter_import_language(language: str) -> Language:
    package = TREE_SITTER_PACKAGES.get(language)
    if not package:
        raise ValueError(f"tree-sitter metrics are not configured for language: {language}")

    try:
        grammar: ModuleType = importlib.import_module(package)
    except ImportError as exc:
        raise RuntimeError(
            f"tree-sitter metrics for {language} require Python packages: "
            f"tree-sitter and {package.replace('_', '-')}"
        ) from exc

    language_factory: Callable[[], object] | None = None
    for factory_name in TREE_SITTER_LANGUAGE_FACTORIES.get(language, ("language",)):
        factory = getattr(grammar, factory_name, None)
        if callable(factory):
            language_factory = factory
            break
    if language_factory is None:
        raise RuntimeError(
            f"tree-sitter metrics for {language} could not find a language factory "
            f"in Python package: {package.replace('_', '-')}"
        )

    raw_language = language_factory()
    return (
        raw_language
        if isinstance(raw_language, Language)
        else Language(raw_language)
    )


def tree_sitter_make_parser(language: str) -> Parser:
    parsed_language = tree_sitter_import_language(language)
    parser = Parser()
    parser.language = parsed_language
    return parser


def node_text(source: bytes, node: Node) -> str:
    return source[node.start_byte : node.end_byte].decode("utf-8", errors="ignore")


def same_node(left: Node | None, right: Node | None) -> bool:
    if left is None or right is None:
        return False
    return (
        left.type == right.type
        and left.start_byte == right.start_byte
        and left.end_byte == right.end_byte
    )


def ancestors(node: Node) -> list[Node]:
    values: list[Node] = []
    parent = node.parent
    while parent is not None:
        values.append(parent)
        parent = parent.parent
    return values


def is_identifier_node(node: Node) -> bool:
    if node.named_children:
        return False

    node_type = node.type
    return (
        node_type in {
            "field_identifier",
            "identifier",
            "predefined_type",
            "primitive_type",
            "property_identifier",
            "scoped_type_identifier",
            "type_identifier",
        }
        or node_type.endswith("_identifier")
    )


def node_has_type_context(node: Node) -> bool:
    if node.type in {
        "predefined_type",
        "primitive_type",
        "scoped_type_identifier",
        "type_identifier",
    }:
        return True
    return any(parent.type in {
        "array_type",
        "bounded_type",
        "extends_clause",
        "generic_type",
        "implements_clause",
        "optional_type",
        "pointer_type",
        "predefined_type",
        "primitive_type",
        "qualified_type",
        "scoped_type_identifier",
        "slice_type",
        "superclass",
        "trait_bound",
        "type",
        "type_annotation",
        "type_arguments",
        "type_identifier",
        "type_parameter",
        "type_parameters",
        "union_type",
    } for parent in ancestors(node))


def node_has_import_context(node: Node) -> bool:
    return any(parent.type in {
        "import_declaration",
        "import_spec",
        "import_statement",
        "namespace_import",
        "package_clause",
        "use_declaration",
        "using_directive",
    } for parent in ancestors(node))


def is_declaration_name(node: Node, declaration_types: set[str]) -> bool:
    for parent in ancestors(node):
        if parent.type in declaration_types and same_node(
            parent.child_by_field_name("name"), node
        ):
            return True
    return False


def tree_sitter_identifier_role(node: Node) -> str:
    if (is_declaration_name(node, {
        "class_declaration",
        "class_definition",
        "class_specifier",
        "enum_declaration",
        "enum_item",
        "enum_specifier",
        "interface_declaration",
        "record_declaration",
        "struct_declaration",
        "struct_item",
        "struct_specifier",
        "trait_item",
        "type_alias_declaration",
        "type_declaration",
        "type_spec",
    }) or node_has_type_context(node)):
        return "type"
    if node_has_import_context(node):
        return "import"
    if is_declaration_name(node, {
        "assignment",
        "const_declaration",
        "field_declaration",
        "formal_parameter",
        "function_declaration",
        "function_definition",
        "function_item",
        "function_signature_item",
        "lexical_declaration",
        "local_variable_declaration",
        "method_declaration",
        "method_definition",
        "parameter",
        "parameter_declaration",
        "short_var_declaration",
        "var_declaration",
        "variable_declaration",
    }):
        return "value"
    return "value"


def walk_tree(node: Node) -> Iterator[Node]:
    yield node
    for child in node.children:
        yield from walk_tree(child)


def tree_sitter_identifiers(
    parser: Parser,
    prefix: str,
    completion: str,
    suffix: str,
) -> list[str]:
    source = f"{prefix}{completion}{suffix}".encode("utf-8")
    start_byte = len(prefix.encode("utf-8"))
    end_byte = start_byte + len(completion.encode("utf-8"))
    tree = parser.parse(source)

    result = []
    for node in walk_tree(tree.root_node):
        is_completion = node.end_byte > start_byte and node.start_byte < end_byte
        is_identifier = is_identifier_node(node)
        if not is_completion or not is_identifier:
            continue
        text = node_text(source, node)
        result.append(f"{node.type}:{text}")

    return result


def calculate_metrics_tree_sitter(
    completion: str,
    ground_truth: str,
    *,
    language: str,
    prefix: str = "",
    suffix: str = "",
) -> MetricScores:
    parser = tree_sitter_make_parser(language)
    prediction = completion.strip()
    reference = ground_truth.strip()
    prediction_ids = tree_sitter_identifiers(parser, prefix, prediction, suffix)
    reference_ids = tree_sitter_identifiers(parser, prefix, reference, suffix)
    return metric_scores(prediction, reference, prediction_ids, reference_ids)


def calculate_metrics(
    record: TestResult,
    completion: str,
    identifier_metrics: IdentifierMetricsMode,
) -> MetricScores:
    identifier_metrics = identifier_metrics_mode(identifier_metrics)
    if identifier_metrics == IdentifierMetricsMode.REGEX:
        return calculate_metrics_regex(completion, record.case.ground_truth)
    if identifier_metrics == IdentifierMetricsMode.TREE_SITTER:
        return calculate_metrics_tree_sitter(
            completion,
            record.case.ground_truth,
            language=record.case.language,
            prefix=record.case.prefix,
            suffix=record.case.suffix,
        )
    raise ValueError(f"unknown identifier metric mode: {identifier_metrics}")


def evaluate_test_result(
    record: TestResult,
    include_errors: bool,
    identifier_metrics: IdentifierMetricsMode,
) -> DirectResult:
    completion_metrics = []
    if record.case.ground_truth and (include_errors or not record.error):
        completion_metrics = [
            MetricEvaluation(
                completion=completion,
                metrics=calculate_metrics(
                    record,
                    completion,
                    identifier_metrics,
                ),
            )
            for completion in record.completions
        ]
    return DirectResult(
        case=record.case,
        server=record.server,
        method=record.method,
        completion_metrics=completion_metrics,
    )


def evaluate_test_result_file(
    input_path: str | Path,
    include_errors: bool = False,
    identifier_metrics: IdentifierMetricsMode = IdentifierMetricsMode.TREE_SITTER,
) -> DirectResult:
    return evaluate_test_result(read_test_result(input_path), include_errors, identifier_metrics)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", "-i", default="result/completions.json")
    parser.add_argument("--output", "-o", default="result/evaluated_completions.json")
    parser.add_argument("--include-errors", action="store_true")
    parser.add_argument(
        "--identifier-metrics",
        choices=[mode.value for mode in IdentifierMetricsMode],
        default=IdentifierMetricsMode.TREE_SITTER.value,
        help=(
            "Regex identifier metric implementation. "
            "Tree-sitter language-aware type/value/import identifier implementation."
        ),
    )
    args = parser.parse_args()

    result = evaluate_test_result_file(
        args.input,
        args.include_errors,
        IdentifierMetricsMode(args.identifier_metrics),
    )
    write_direct_result(result, args.output)
    print(
        json.dumps(
            {
                "metrics_calculated": bool(result.completion_metrics),
                "completion_metrics_calculated": len(result.completion_metrics),
                "output": args.output,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
