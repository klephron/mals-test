from pathlib import Path
from datasets import load_dataset

DATASET = "bigcode/humanevalpack"
CONFIGS = ["python", "js", "java", "go", "cpp", "rust"]
OUT = "data/humanevalpack"

OUT = Path(OUT)
OUT.mkdir(parents=True, exist_ok=True)

for lang in CONFIGS:
    ds = load_dataset(DATASET, lang)
    for split_name, split in ds.items():
        split.to_json(OUT / f"{lang}-{split_name}.json")
