"""Get the raw ER visit CSV into data/raw/.

    python -m erops.ingest

Two paths, because Kaggle dataset slugs get renamed and reuploaded and a class
project should not break when that happens:

1. If a CSV is already sitting in data/raw/, use it. A manual download from
   Kaggle ("Download" button, unzip into data/raw/) is a perfectly good
   ingest and needs no API token.
2. Otherwise try `kagglehub`, which reads credentials from ~/.kaggle/kaggle.json.

Either way the file lands at config.RAW_CSV and everything downstream reads
that one path. The CSV itself is git-ignored: it is not ours to redistribute.
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

from erops.config import KAGGLE_DATASET, RAW, RAW_CSV


def find_local_csv() -> Path | None:
    """Return a CSV already present in data/raw/, preferring the canonical name."""
    if RAW_CSV.exists():
        return RAW_CSV
    candidates = sorted(RAW.glob("*.csv"))
    return candidates[0] if candidates else None


def fetch_from_kaggle() -> Path:
    """Download via kagglehub and copy the first CSV found into data/raw/."""
    try:
        import kagglehub
    except ImportError as exc:  # pragma: no cover - depends on optional install
        raise SystemExit(
            "kagglehub is not installed and no CSV was found in data/raw/.\n"
            "Either:\n"
            "  pip install kagglehub   (then set up ~/.kaggle/kaggle.json)\n"
            "or download the dataset manually from Kaggle and unzip it into\n"
            f"  {RAW}\n"
            "Both work identically from here on."
        ) from exc

    path = Path(kagglehub.dataset_download(KAGGLE_DATASET))
    csvs = sorted(path.rglob("*.csv"))
    if not csvs:
        raise SystemExit(f"No CSV found in the downloaded dataset at {path}.")
    shutil.copy2(csvs[0], RAW_CSV)
    return RAW_CSV


def main() -> int:
    local = find_local_csv()
    if local is not None:
        if local != RAW_CSV:
            shutil.copy2(local, RAW_CSV)
            print(f"adopted {local.name} as {RAW_CSV.name}")
        print(f"raw CSV ready: {RAW_CSV} ({RAW_CSV.stat().st_size:,} bytes)")
        return 0

    print(f"no CSV in {RAW} -- trying kagglehub ({KAGGLE_DATASET})")
    out = fetch_from_kaggle()
    print(f"raw CSV ready: {out} ({out.stat().st_size:,} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
