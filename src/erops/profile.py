"""Profile the raw ER CSV before a single model is written.

    python -m erops.profile

Phase 0 of the build. The column names, date range and null rates in this
dataset vary between reuploads, so nothing downstream should be written from
assumption -- run this first and paste the output into docs/data_dictionary.md.

Deliberately schema-agnostic: it reports whatever columns are actually there
rather than asserting the ones we expect.
"""

from __future__ import annotations

import sys

import pandas as pd

from erops.config import RAW_CSV


def profile(df: pd.DataFrame) -> None:
    print(f"\nrows: {len(df):,}    columns: {len(df.columns)}")

    print("\n--- columns ---")
    summary = pd.DataFrame(
        {
            "dtype": df.dtypes.astype(str),
            "nulls": df.isna().sum(),
            "null_pct": (df.isna().mean() * 100).round(1),
            "distinct": df.nunique(dropna=True),
        }
    )
    print(summary.to_string())

    print("\n--- low-cardinality values (candidate dimensions) ---")
    for col in df.columns:
        n = df[col].nunique(dropna=True)
        if 0 < n <= 15:
            counts = df[col].value_counts(dropna=False).head(15)
            print(f"\n{col}  ({n} distinct)")
            print(counts.to_string())

    print("\n--- numeric distributions ---")
    numeric = df.select_dtypes("number")
    if not numeric.empty:
        print(numeric.describe(percentiles=[0.25, 0.5, 0.75, 0.9, 0.95, 0.99]).to_string())

    print("\n--- datetime-ish columns ---")
    for col in df.columns:
        if df[col].dtype == "object":
            parsed = pd.to_datetime(df[col], errors="coerce")
            # Treat as a date column only if nearly everything parses.
            if parsed.notna().mean() > 0.9:
                print(f"{col}: {parsed.min()}  ->  {parsed.max()}")

    print("\n--- duplicate check ---")
    print(f"fully duplicated rows: {df.duplicated().sum():,}")
    for col in df.columns:
        if "id" in col.lower():
            dupes = df[col].duplicated().sum()
            print(f"duplicate values in {col}: {dupes:,}")


def main() -> int:
    if not RAW_CSV.exists():
        raise SystemExit(f"{RAW_CSV} not found -- run `make ingest` first.")
    profile(pd.read_csv(RAW_CSV))
    print("\nRecord these findings in docs/data_dictionary.md before writing models.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
