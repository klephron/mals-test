from pathlib import Path
import shutil
import tarfile

REPO = Path("third_party/cceval")
OUT = Path("data/cceval")
ARCHIVES = list(REPO.rglob("*.tar.xz"))

for archive in ARCHIVES:
    if OUT.exists():
        shutil.rmtree(OUT)
        print(f"Removed {OUT}")

    OUT.mkdir(parents=True, exist_ok=True)

    with tarfile.open(archive, "r:xz") as tar:
        tar.extractall(OUT)
        print(f"Extracted {OUT}")
