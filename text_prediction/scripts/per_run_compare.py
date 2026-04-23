"""Compare per-run means across runs for each model.

Reads evaluation/results/per_run.csv and prints (model, run) × metric table.
"""
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
df = pd.read_csv(ROOT / "evaluation" / "results" / "per_run.csv")

print("Per-run means (across 20 codes):")
grouped = df.groupby(["model", "run"])[
    ["close_mse", "std_close_mse", "vol_mse", "std_vol_mse"]
].mean().round(3)
print(grouped.to_string())

print("\nRun-to-run diff (run2 - run1):")
diff_rows = []
for model in df["model"].unique():
    sub = grouped.loc[model]
    if "run1" in sub.index and "run2" in sub.index:
        diff = sub.loc["run2"] - sub.loc["run1"]
        diff_rows.append({"model": model, **diff.round(3).to_dict()})
print(pd.DataFrame(diff_rows).to_string(index=False))
