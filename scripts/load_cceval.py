from pathlib import Path
import shutil
import tarfile

repo = Path("third_party/cceval")
out = Path("data/cceval")

archives = list(repo.rglob("*.tar.xz"))

for archive in archives:
    if out.exists():
        shutil.rmtree(out)
        print(f"Removed {out}")

    out.mkdir(parents=True, exist_ok=True)

    with tarfile.open(archive, "r:xz") as tar:
        tar.extractall(out)
        print(f"Extracted {out}")
