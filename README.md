# mals-test

## Install

Clone with submodules.

Install datasets:

```sh
python scripts/load_cceval.py
uv run --with "datasets" --with "huggingface_hub" scripts/load_humanevalpack.py
uv run --python "3.12" --with "datasets<4" --with "huggingface_hub" scripts/load_repobench-c.py
```

## Normalize project dataset layouts

```sh
python scripts/normalize_cceval.py
python scripts/normalize_humanevalpack.py
python scripts/normalize_repobench-c.py
```

## Run one normalized project through an LSP server

The Go runner expects one normalized project directory after the flags. The directory must contain `completion.json` and `root/`.

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

The runner executes one project against one LSP server and writes one JSON object. The JSON includes extracted completion candidates, request metadata, duration, and any error.
If `--out` is omitted, the runner writes the completion result to stdout. Other messages are written to stderr.
The runner only executes completion requests; it does not calculate metrics.

## Evaluate completion metrics

`scripts/evaluate_completions.py` reads JSON, JSONL, or a directory of JSON completion results produced by `mals-test`, calculates per-record metrics, and writes evaluated records.

Example for the `lsp-ai` result above:

```sh
python scripts/evaluate_completions.py \
  --input result/mals-test/lsp-ai/humanevalpack/cpp-CPP_0.json \
  --output result/evaluated/lsp-ai/humanevalpack/cpp-CPP_0.json
```

Example for the `llm-ls` result above:

```sh
python scripts/evaluate_completions.py \
  --input result/mals-test/llm-ls/humanevalpack.projects/python-Python_0.json \
  --output result/evaluated/llm-ls/humanevalpack.projects/python-Python_0.json
```

The evaluated JSON contains typed per-record metric data plus skipped counters. The full completion response remains in the original `result/mals-test/...` file.

To merge many JSON files into single JSONL to pass to `evaluate_completions.py`:

```sh
find result/mals-test/lsp-ai -name '*.json' -print0 \
  | sort -z \
  | xargs -0 jq -c '.' \
  > result/mals-test/lsp-ai/all.jsonl
```

## Aggregate metrics

`scripts/aggregate_metrics.py` reads evaluated records from `evaluate_completions.py`, groups them, and writes averaged metrics.

```sh
python scripts/aggregate_metrics.py \
  --input result/evaluated/lsp-ai \
  --output result/metrics/lsp-ai.json \
  --group-by server,dataset,language
```
