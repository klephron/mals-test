# noted

```sh
find data/humanevalpack.projects -mindepth 1 -maxdepth 1 -type d -print0 |
  xargs -0 -P8 -I{} sh -c '
    dir="$1"
    name=$(basename "$dir")
    go run ./cmd/mals-test \
      --server lsp-ai \
      --method textDocument/completion \
      --init-options ./config/lsp-ai_v1.json \
      --timeout 5m \
      --out "result/mals-test/lsp-ai/humanevalpack/${name}.json" \
      "$dir"
    echo $1
  ' _ {}
```
