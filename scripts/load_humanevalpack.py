from pathlib import Path
from datasets import load_dataset

dataset = "bigcode/humanevalpack"
configs = ["python", "js", "java", "go", "cpp", "rust"]
out = "data/humanevalpack"

out = Path(out)
out.mkdir(parents=True, exist_ok=True)

for lang in configs:
    ds = load_dataset(dataset, lang)
    for split_name, split in ds.items():
        split.to_json(out / f"{lang}-{split_name}.json")
