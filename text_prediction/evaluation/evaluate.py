"""Evaluate experiment-1 predictions for experiment-1 of the stock-price-prediction
paper.

Inputs
------
Predictions are read from:
    text_prediction/output/{model}/run{k}/{CODE}.csv
Each file must have header `day,open,high,low,close` and 62 rows D64..D125.

Ground truth is read from `text_prediction/data/label/{CODE}.csv` (same format).

Metrics (paper spec, Experiment 1)
----------------------------------
For each (dataset, model, run):
    close_mse          = mean((truth_close - pred_close) ** 2)
    std_close_mse      = close_mse / baseline_close_mse
        baseline_close = linear_interp(truth_close[D64], truth_close[D125])
        baseline_close_mse = mean((truth_close - baseline_close) ** 2)
    vol_mse            = mean((truth_vol - pred_vol) ** 2)          vol = high - low
    std_vol_mse        = vol_mse / baseline_vol_mse
        baseline_vol   = linear_interp(truth_vol[D64], truth_vol[D125])

Aggregate across 20 datasets * 5 runs = 100 samples -> mean +/- std per model.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
LABEL_DIR = ROOT / "data" / "label"
DAYS = [f"D{i}" for i in range(64, 126)]  # 62 labels


def linear_baseline(first: float, last: float, n: int = 62) -> np.ndarray:
    return np.linspace(first, last, n)


def load_label(code: str) -> pd.DataFrame:
    df = pd.read_csv(LABEL_DIR / f"{code}.csv")
    if list(df.day) != DAYS:
        raise ValueError(f"Label {code} day order mismatch")
    return df


def load_prediction(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    for col in ("day", "open", "high", "low", "close"):
        if col not in df.columns:
            raise ValueError(f"{path}: missing column {col}")
    if list(df.day) != DAYS:
        raise ValueError(f"{path}: day column must be D64..D125 in order")
    return df


def metrics_for_run(truth: pd.DataFrame, pred: pd.DataFrame) -> dict[str, float]:
    tc, pc = truth.close.to_numpy(), pred.close.to_numpy()
    tv, pv = (truth.high - truth.low).to_numpy(), (pred.high - pred.low).to_numpy()

    close_mse = float(np.mean((tc - pc) ** 2))
    base_close = linear_baseline(tc[0], tc[-1], len(tc))
    close_mse_base = float(np.mean((tc - base_close) ** 2))

    vol_mse = float(np.mean((tv - pv) ** 2))
    base_vol = linear_baseline(tv[0], tv[-1], len(tv))
    vol_mse_base = float(np.mean((tv - base_vol) ** 2))

    return {
        "close_mse": close_mse,
        "std_close_mse": close_mse / close_mse_base if close_mse_base > 0 else np.nan,
        "vol_mse": vol_mse,
        "std_vol_mse": vol_mse / vol_mse_base if vol_mse_base > 0 else np.nan,
    }


def evaluate_model(model_dir: Path) -> pd.DataFrame:
    """Return a per-run long-format DataFrame with columns
    [model, run, code, close_mse, std_close_mse, vol_mse, std_vol_mse]."""
    rows: list[dict] = []
    model_name = model_dir.name
    run_dirs = sorted(d for d in model_dir.iterdir() if d.is_dir() and d.name.startswith("run"))
    if not run_dirs:
        raise RuntimeError(f"No run*/ subdirectories under {model_dir}")
    for run_dir in run_dirs:
        for pred_path in sorted(run_dir.glob("*.csv")):
            code = pred_path.stem
            truth = load_label(code)
            pred = load_prediction(pred_path)
            m = metrics_for_run(truth, pred)
            rows.append({"model": model_name, "run": run_dir.name, "code": code, **m})
    return pd.DataFrame(rows)


def summarize(long_df: pd.DataFrame) -> pd.DataFrame:
    metrics = ["close_mse", "std_close_mse", "vol_mse", "std_vol_mse"]
    out = []
    for model, grp in long_df.groupby("model"):
        row = {"model": model, "n": len(grp)}
        for m in metrics:
            row[f"{m}_mean"] = grp[m].mean()
            row[f"{m}_std"] = grp[m].std(ddof=1)
        out.append(row)
    return pd.DataFrame(out)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "model_dirs", nargs="+", type=Path,
        help="Model directories containing runN subfolders (e.g. output/chatgpt5.4)")
    ap.add_argument("--out", type=Path, default=ROOT / "evaluation" / "results")
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    all_long: list[pd.DataFrame] = []
    for d in args.model_dirs:
        if not d.is_dir():
            print(f"skip (not a dir): {d}", file=sys.stderr)
            continue
        all_long.append(evaluate_model(d))
    if not all_long:
        sys.exit("No predictions evaluated.")

    long_df = pd.concat(all_long, ignore_index=True)
    long_df.to_csv(args.out / "per_run.csv", index=False)

    summary = summarize(long_df)
    summary.to_csv(args.out / "summary.csv", index=False)
    pd.set_option("display.float_format", lambda x: f"{x:.4f}")
    print(summary.to_string(index=False))


if __name__ == "__main__":
    main()
