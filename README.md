# mals-test

## Install

Clone with submodules.

Install datasets:

```sh
python scripts/load_cceval.py
uv run --with "datasets" --with "huggingface_hub" scripts/load_humanevalpack.py
uv run --python "3.12" --with "datasets<4" --with "huggingface_hub" scripts/load_repobench-c.py
```
