"""Quick per-code metrics inspector for experiment 1.

Usage:
    # show metrics for specific codes, all models
    python3 scripts/quick_metrics.py E F

    # specific run (default: run1)
    python3 scripts/quick_metrics.py E F --run run2

    # specific models (default: all three)
    python3 scripts/quick_metrics.py E F --models claude-opus-4.7 chatgpt5.4

    # all codes that exist in the run dir
    python3 scripts/quick_metrics.py --all --run run1

    # cumulative summary (mean across codes per model)
    python3 scripts/quick_metrics.py --summary --run run1
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_MODELS = ["claude-opus-4.7", "chatgpt5.4", "gemini3.1pro"]
METRICS = ["std_close", "std_vol"]


def lin_baseline(first: float, last: float, n: int = 62) -> np.ndarray:
    return np.linspace(first, last, n)


def per_code(code: str, run: str, models: list[str]) -> list[dict]:
    inp = pd.read_csv(ROOT / "data" / "input" / f"{code}.csv")
    lab = pd.read_csv(ROOT / "data" / "label" / f"{code}.csv")
    d126 = float(inp.close.iloc[-1])
    tc = lab.close.to_numpy()
    tv = (lab.high - lab.low).to_numpy()
    tv_mean = float(tv.mean())
    rows = []
    for m in models:
        p = ROOT / "output" / m / run / f"{code}.csv"
        if not p.exists():
            continue
        pred = pd.read_csv(p)
        pc = pred.close.to_numpy()
        pv = (pred.high - pred.low).to_numpy()
        close_mse = np.mean((tc - pc) ** 2)
        vol_mse = np.mean((tv - pv) ** 2)
        std_close = close_mse / np.mean((tc - lin_baseline(tc[0], tc[-1])) ** 2)
        std_vol = vol_mse / np.mean((tv - lin_baseline(tv[0], tv[-1])) ** 2)
        rows.append({
            "code": code,
            "model": m,
            "D125": round(float(pc[-1]), 2),
            "gap": round(d126 - float(pc[-1]), 2),
            "close_mse": round(float(close_mse), 3),
            "std_close": round(float(std_close), 3),
            "vol_mse": round(float(vol_mse), 3),
            "std_vol": round(float(std_vol), 3),
            "truth_vol": round(tv_mean, 2),
            "pred_vol": round(float(pv.mean()), 2),
        })
    return rows


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("codes", nargs="*", help="codes to inspect (A..T)")
    ap.add_argument("--all", action="store_true",
                    help="inspect every code present in the run directory")
    ap.add_argument("--run", default="run1")
    ap.add_argument("--models", nargs="+", default=DEFAULT_MODELS)
    ap.add_argument("--summary", action="store_true",
                    help="print only per-model means across selected codes")
    args = ap.parse_args()

    if args.all:
        present = set()
        for m in args.models:
            d = ROOT / "output" / m / args.run
            if d.is_dir():
                present.update(p.stem for p in d.glob("*.csv"))
        codes = sorted(present)
    else:
        codes = list(args.codes)

    if not codes:
        print("no codes to inspect (pass codes or --all)")
        return

    rows: list[dict] = []
    for c in codes:
        rows.extend(per_code(c, args.run, args.models))

    if not rows:
        print("no predictions found for the given codes")
        return

    df = pd.DataFrame(rows)
    print(df.to_string(index=False))

    if args.summary or len(codes) > 1:
        print(f"\n--- means across {len(codes)} code(s), run={args.run} ---")
        print(df.groupby("model")[METRICS].mean().round(3).to_string())


if __name__ == "__main__":
    main()
