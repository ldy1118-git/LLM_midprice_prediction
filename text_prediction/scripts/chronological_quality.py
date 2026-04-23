"""Track model quality chronologically.

Assumes submissions went run1/batch1 → run1/batch2 → ... → run1/batch10 →
run2/batch1 → ... → run2/batch10 for each model. Computes the mean metric
per batch (2 codes each) across that sequence, and flags whether quality
trends downward.
"""
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
df = pd.read_csv(ROOT / "evaluation" / "results" / "per_run.csv")

# Assign chronological order index: run1/b1 = 1, run1/b2 = 2, ..., run2/b10 = 20
BATCH_ORDER = [
    ("A", 1), ("B", 1),
    ("C", 2), ("D", 2),
    ("E", 3), ("F", 3),
    ("G", 4), ("H", 4),
    ("I", 5), ("J", 5),
    ("K", 6), ("L", 6),
    ("M", 7), ("N", 7),
    ("O", 8), ("P", 8),
    ("Q", 9), ("R", 9),
    ("S", 10), ("T", 10),
]
code_to_batch = dict(BATCH_ORDER)
df["batch"] = df["code"].map(code_to_batch)
run_to_off = {"run1": 0, "run2": 10}
df["slot"] = df["run"].map(run_to_off) + df["batch"]

metrics = ["close_mse", "std_close_mse", "vol_mse", "std_vol_mse"]

for m in ["chatgpt5.4", "gemini3.1pro", "claude-opus-4.7"]:
    sub = df[df.model == m].groupby("slot")[metrics].mean().round(3)
    print(f"\n=== {m} (slot = chronological batch submission order) ===")
    print(sub.to_string())

    # correlation between slot (time) and std_close / std_vol
    print(f"  Pearson r(slot, std_close_mse) = "
          f"{df[df.model == m][['slot', 'std_close_mse']].corr().iloc[0,1]:.3f}")
    print(f"  Pearson r(slot, std_vol_mse)   = "
          f"{df[df.model == m][['slot', 'std_vol_mse']].corr().iloc[0,1]:.3f}")
    print(f"  Pearson r(slot, close_mse)     = "
          f"{df[df.model == m][['slot', 'close_mse']].corr().iloc[0,1]:.3f}")
