# mals-test

Benchmark language-server completion tools on extracted code-completion tasks.

## Install And Load Data

Clone the repository with submodules.

Install Python dependencies:

```sh
uv pip install -r requirements.txt
```

Load the source datasets:

```sh
python scripts/load_cceval.py
uv run --with "datasets" --with "huggingface_hub" scripts/load_humanevalpack.py
uv run --python "3.12" --with "datasets<4" --with "huggingface_hub" scripts/load_repobench-c.py
```

## Extract Benchmark Projects

Convert raw datasets into project-shaped test cases. Each extracted case contains
`completion.json` and a project root.

```sh
python scripts/extract_cceval.py
python scripts/extract_humanevalpack.py
python scripts/extract_repobench-c.py
```

## Run Completion Tests

Run `mals-test` on one extracted project. The result JSON contains the test case,
generated completions, request metadata, duration, and any generation error.

```sh
go run ./cmd/mals-test \
  --server lsp-ai \
  --method textDocument/completion \
  --init-options ./config/lsp-ai_v1.json \
  --timeout 5m \
  --out result/mals-test/lsp-ai/humanevalpack/cpp-CPP_0.json \
  data/humanevalpack.projects/cpp-CPP_0
```

For `llm-ls`:

```sh
go run ./cmd/mals-test \
  --server llm-ls \
  --method llm-ls/getCompletions \
  --out result/mals-test/llm-ls/humanevalpack/python-Python_0.json \
  data/humanevalpack.projects/python-Python_0
```

If `--out` is omitted, the runner writes the completion result to stdout. Other
messages are written to stderr.

## Materialize Completion Projects

Create concrete project variants from one extracted project and one `mals-test`
result. The script writes a baseline project with the ground truth inserted and
one project per generated completion.

```sh
python scripts/materialize_test_result.py \
  --project data/humanevalpack.projects/cpp-CPP_0 \
  --result result/mals-test/lsp-ai/humanevalpack/cpp-CPP_0.json \
  --output result/materialized/lsp-ai/humanevalpack/cpp-CPP_0 \
  --overwrite
```

## Evaluate Direct Metrics

Calculate direct metrics for one `mals-test` result:

```sh
python scripts/evaluate_direct.py \
  --input result/mals-test/lsp-ai/humanevalpack/cpp-CPP_0.json \
  --output result/evaluated-direct/lsp-ai/humanevalpack/cpp-CPP_0.json
```

The evaluated JSON stores `completion_metrics`: one metric record per generated
completion.

## Evaluate Materialized Diagnostics

Run the language compiler/analyzer on `baseline/` and each `completion_N/`.
Diagnostics from the completion projects are compared against baseline
diagnostics, and only new diagnostics are stored for each completion.

```sh
python scripts/evaluate_materialized.py \
  --project result/materialized/lsp-ai/humanevalpack/cpp-CPP_0 \
  --result result/mals-test/lsp-ai/humanevalpack/cpp-CPP_0.json \
  --output result/evaluated-materialized/lsp-ai/humanevalpack/cpp-CPP_0.json
```

Checker selection is based on `case.language` from the `mals-test` result.
Supported checkers include `g++`/`clang++`, `dotnet`/`csc`, `go`, `javac`,
`node --check`, `tsc`, `pyright`/`py_compile`, and `cargo`/`rustc`.

## Aggregate Direct Metrics

Aggregate outputs from `evaluate_direct.py`.

```sh
python scripts/aggregate_direct.py \
  --output result/aggregated/humanevalpack/lsp-ai.json \
  --group-by server,dataset,language \
  result/evaluated/lsp-ai/humanevalpack/cpp-CPP_0.json
```

The summary includes:

- `avg_metrics`: average completion metrics per record, then averaged by group
- `best_metrics`: best completion per record, then averaged by group

## Aggregate Materialized Diagnostics

Aggregate outputs from `evaluate_materialized.py`.

```sh
python scripts/aggregate_materialized.py \
  --output result/materialized-aggregated/humanevalpack/lsp-ai.json \
  --group-by server,dataset,language \
  result/materialized-evaluated/lsp-ai/humanevalpack/cpp-CPP_0.json
```

The summary includes:

- `baseline_diagnostic_count`
- `avg_completion_diagnostic_count`
- `avg_new_diagnostic_count`
- `best_completion_diagnostic_count`
- `best_new_diagnostic_count`
