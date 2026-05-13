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
GOCACHE=/tmp/mals-test-go-build go run ./cmd/lspbench \
  data/cceval.projects/csharp-line_completion_oracle_bm25-project_cc_csharp_1 \
  --server lsp-ai=lsp-ai \
  --method lsp-ai=textDocument/completion \
  --out results/project-result.jsonl
```

For `llm-ls`:

```sh
GOCACHE=/tmp/mals-test-go-build go run ./cmd/lspbench \
  data/humanevalpack.projects/python-Python_0 \
  --server llm-ls=llm-ls \
  --method llm-ls=llm-ls/getCompletions \
  --out results/llm-ls-project-result.jsonl
```

Each output row includes the completion text plus exact match, edit similarity,
identifier exact match, and identifier F1.
