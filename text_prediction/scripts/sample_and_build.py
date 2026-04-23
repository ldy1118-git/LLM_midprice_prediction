"""Sample 20 (ticker, 126-trading-day window) datasets and build masked
input/label files for experiment 1.

Paper spec:
  - 20 NASDAQ large-cap tickers (shared with chart_prediction)
  - Each window is 126 consecutive trading days entirely within
    2016-01-04 ~ 2025-01-30.
  - Ticker is masked to A~T, dates are masked to D1~D126.
  - Input: OHLC for D1..D63 and D126 (64 rows).
  - Label: OHLC for D64..D125 (62 rows).
  - Seed: 42.

Individual per-code prompts are NOT generated here; collection uses only the
batched prompts built by scripts/build_batched_prompts.py (batch=2).
"""
from __future__ import annotations

import random
import string
from pathlib import Path

import pandas as pd

SEED = 42
ROOT = Path(__file__).resolve().parent.parent
PANEL_PATH = ROOT.parent / "data" / "stock_panel_data.parquet"

INPUT_DIR = ROOT / "data" / "input"
LABEL_DIR = ROOT / "data" / "label"
WINDOWS_CSV = ROOT / "data" / "windows.csv"

# 20 NASDAQ large-cap tickers (same as chart_prediction)
TICKERS = [
    "AAPL", "MSFT", "AMZN", "TSLA", "NVDA", "META", "GOOGL", "NFLX",
    "AMD",  "AVGO", "PLTR", "ASML", "CSCO", "ADBE", "QCOM", "TXN",
    "INTU", "AMAT", "INTC", "PANW",
]

WINDOW_START = pd.Timestamp("2016-01-04")
WINDOW_END = pd.Timestamp("2025-01-30")
WINDOW_LEN = 126  # D1..D126


def load_panel() -> pd.DataFrame:
    df = pd.read_parquet(PANEL_PATH, columns=["ticker", "date", "open", "high", "low", "close"])
    df["date"] = pd.to_datetime(df["date"])
    return df


def sample_window(df_ticker: pd.DataFrame, rng: random.Random) -> pd.DataFrame:
    """Pick a contiguous 126-row slice whose first and last dates both fall in
    [WINDOW_START, WINDOW_END]."""
    rows = df_ticker.sort_values("date").reset_index(drop=True)
    valid = rows[(rows["date"] >= WINDOW_START) & (rows["date"] <= WINDOW_END)]
    if len(valid) < WINDOW_LEN:
        raise RuntimeError(f"Not enough rows in window for {df_ticker['ticker'].iloc[0]}")
    first_idx = valid.index[0]
    last_start_idx = valid.index[-1] - (WINDOW_LEN - 1)
    if last_start_idx < first_idx:
        raise RuntimeError(f"No valid start for {df_ticker['ticker'].iloc[0]}")
    start = rng.randint(int(first_idx), int(last_start_idx))
    return rows.iloc[start : start + WINDOW_LEN].reset_index(drop=True)


def main() -> None:
    rng = random.Random(SEED)

    codes = list(string.ascii_uppercase[:20])  # A..T
    shuffled_tickers = TICKERS.copy()
    rng.shuffle(shuffled_tickers)
    ticker_to_code = dict(zip(shuffled_tickers, codes))

    panel = load_panel()

    windows_rows = []
    for ticker in shuffled_tickers:
        code = ticker_to_code[ticker]
        sub = panel[panel.ticker == ticker].sort_values("date").reset_index(drop=True)
        win = sample_window(sub, rng)

        # write input CSV (64 rows: D1..D63 + D126)
        input_rows = []
        for i in range(63):
            r = win.iloc[i]
            input_rows.append({
                "day": f"D{i+1}",
                "open": round(r.open, 4),
                "high": round(r.high, 4),
                "low": round(r.low, 4),
                "close": round(r.close, 4),
            })
        r = win.iloc[125]
        input_rows.append({
            "day": "D126",
            "open": round(r.open, 4), "high": round(r.high, 4),
            "low":  round(r.low, 4),  "close": round(r.close, 4),
        })
        pd.DataFrame(input_rows).to_csv(INPUT_DIR / f"{code}.csv", index=False)

        # write label CSV (62 rows: D64..D125)
        label_rows = []
        for i in range(63, 125):
            r = win.iloc[i]
            label_rows.append({
                "day": f"D{i+1}",
                "open": round(r.open, 4),
                "high": round(r.high, 4),
                "low": round(r.low, 4),
                "close": round(r.close, 4),
            })
        pd.DataFrame(label_rows).to_csv(LABEL_DIR / f"{code}.csv", index=False)

        windows_rows.append({
            "code": code,
            "ticker": ticker,
            "start_date": win["date"].iloc[0].date().isoformat(),
            "d63_date":   win["date"].iloc[62].date().isoformat(),
            "d64_date":   win["date"].iloc[63].date().isoformat(),
            "d125_date":  win["date"].iloc[124].date().isoformat(),
            "d126_date":  win["date"].iloc[125].date().isoformat(),
        })

    windows_df = pd.DataFrame(windows_rows).sort_values("code").reset_index(drop=True)
    windows_df.to_csv(WINDOWS_CSV, index=False)
    print(windows_df.to_string(index=False))
    print(f"\nWrote {len(windows_df)} datasets to {ROOT}")


if __name__ == "__main__":
    main()
