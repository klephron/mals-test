from pathlib import Path
from datasets import load_dataset

DATASET = "tianyang/repobench-c"
CONFIGS = ['java_cff', 'java_cfr', 'java_if', 'python_cff', 'python_cfr', 'python_if']
OUT = "data/repobench-c"

OUT = Path(OUT)
OUT.mkdir(parents=True, exist_ok=True)

for lang in CONFIGS:
    ds = load_dataset(DATASET, lang)
    for split_name, split in ds.items():
        split.to_json(OUT / f"{lang}-{split_name}.json")
