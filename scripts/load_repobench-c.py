from pathlib import Path
from datasets import load_dataset

dataset = "tianyang/repobench-c"
configs = ['java_cff', 'java_cfr', 'java_if', 'python_cff', 'python_cfr', 'python_if']
out = "data/repobench-c"

out = Path(out)
out.mkdir(parents=True, exist_ok=True)

for lang in configs:
    ds = load_dataset(dataset, lang)
    for split_name, split in ds.items():
        split.to_json(out / f"{lang}-{split_name}.json")
