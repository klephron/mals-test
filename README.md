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

The Go runner expects a normalized project directory as its first argument. The directory must contain `completion.json` and `root/`.

```sh
go run ./cmd/mals-test \
  ./data/humanevalpack.projects/cpp-CPP_0 \
  --server lsp-ai \
  --method textDocument/completion \
  --init-options ./config/lsp-ai.json \
  --timeout 5m \
  --out result/mals-test/lsp-ai/humanevalpack/cpp-CPP_0.json
```

For `llm-ls`:

```sh
go run ./cmd/mals-test \
  data/humanevalpack.projects/python-Python_0 \
  --server llm-ls \
  --method llm-ls/getCompletions \
  --out result/mals-test/llm-ls/humanevalpack/python-Python_0.json
```

The runner executes one project against one LSP server and writes one JSON object. The JSON includes the completion text plus exact match, edit similarity, identifier exact match, and identifier F1.

## Summarize completion metrics

`scripts/evaluate_completions.py` reads the JSON result produced by `mals-test` and writes a smaller summary JSON.

Example for the `lsp-ai` result above:

```sh
python scripts/evaluate_completions.py \
  --input result/mals-test/lsp-ai/humanevalpack/cpp-CPP_0.json \
  --output result/completions/lsp-ai/humanevalpack/cpp-CPP_0.json
```

Example for the `llm-ls` result above:

```sh
python scripts/evaluate_completions.py \
  --input result/mals-test/llm-ls/humanevalpack.projects/python-Python_0.json \
  --output result/completions/llm-ls/humanevalpack.projects/python-Python_0.json
```

The summary JSON contains grouped metrics, per-record metric rows, and a `skipped_without_metrics` counter. The full completion response remains in the original `result/mals-test/...` file.

To merge many JSON files into single JSONL to pass to `evaluate_completions.py`:

```sh
find result/mals-test/lsp-ai -name '*.json' -print0 \
  | sort -z \
  | xargs -0 jq -c '.' \
  > result/mals-test/lsp-ai/all.jsonl
```
