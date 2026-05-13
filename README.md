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

The Go runner expects a normalized project directory as its first argument. The
directory must contain `completion.json` and `root/`.

```sh
go run ./cmd/mals-test \
  ./data/humanevalpack.projects/cpp-CPP_0 \
  --server lsp-ai \
  --method textDocument/completion \
  --init-options ./config/lsp-ai.json \
  --timeout 5m \
  --out results/lsp-ai/humanevalpack.projects/cpp-CPP_0.json
```

For `llm-ls`:

```sh
go run ./cmd/mals-test \
  data/humanevalpack.projects/python-Python_0 \
  --server llm-ls \
  --method llm-ls/getCompletions \
  --out results/llm-ls-project-result.json
```

The runner executes one project against one LSP server and writes one JSON
object. The JSON includes the completion text plus exact match, edit similarity,
identifier exact match, and identifier F1.
