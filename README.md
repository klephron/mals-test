# mals-test

## Install

Clone with submodules.

Install datasets:

```sh
python scripts/load_cceval.py
uv run --with "datasets" --with "huggingface_hub" scripts/load_humanevalpack.py
uv run --python "3.12" --with "datasets<4" --with "huggingface_hub" scripts/load_repobench-c.py
```

## Extract project dataset layouts

```sh
python scripts/extract_cceval.py
python scripts/extract_humanevalpack.py
python scripts/extract_repobench-c.py
```

## Run test for extracted project

The Go runner expects one extracted project directory after the flags. The directory must contain `completion.json` and `root/`.

```sh
go run ./cmd/mals-test \
  --server lsp-ai \
  --method textDocument/completion \
  --init-options ./config/lsp-ai.json \
  --timeout 5m \
  --out result/mals-test/lsp-ai/humanevalpack/cpp-CPP_0.json \
  ./data/humanevalpack.projects/cpp-CPP_0
```

For `llm-ls`:

```sh
go run ./cmd/mals-test \
  --server llm-ls \
  --method llm-ls/getCompletions \
  --out result/mals-test/llm-ls/humanevalpack/python-Python_0.json \
  data/humanevalpack.projects/python-Python_0
```

The JSON includes extracted completion candidates, request metadata, duration, and any error. If `--out` is omitted, the runner writes the completion result to stdout. Other messages are written to stderr.

## Evaluate test results

`scripts/evaluate_test_result.py` reads one JSON test result produced by `mals-test`, calculates metrics, and writes one evaluation result.

```sh
python scripts/evaluate_test_result.py \
  --input result/mals-test/lsp-ai/humanevalpack/cpp-CPP_0.json \
  --output result/evaluated/lsp-ai/humanevalpack/cpp-CPP_0.json
```

The evaluated JSON contains the original test metadata, extracted completions, and metrics. The full completion response remains in the original `result/mals-test/...` file.

## Aggregate metrics

`scripts/aggregate_evaluation_result.py` reads evaluation result files from `evaluate_test_result.py`, groups them, and writes averaged metrics.

```sh
python scripts/aggregate_evaluation_result.py \
  --output result/aggregated/humanevalpack/lsp-ai.json \
  --group-by server,dataset,language \
  result/evaluated/lsp-ai/humanevalpack/cpp-CPP_0.json \
```
