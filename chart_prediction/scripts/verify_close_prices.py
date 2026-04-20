"""actual_midprices.csv의 last_visible_close / actual_end_close 를 yfinance와 비교."""
import os
import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CSV = os.path.join(SCRIPT_DIR, "..", "data", "label", "actual_midprices.csv")

df = pd.read_csv(CSV)
rows = []
for _, r in df.iterrows():
    t = r["ticker"]
    for col, date_col in [("last_visible_close", "split"), ("actual_end_close", "end")]:
        d = pd.to_datetime(r[date_col])
        hist = yf.download(
            t, start=d - timedelta(days=7), end=d + timedelta(days=7),
            progress=False, auto_adjust=True, threads=False,
        )
        if hist.empty:
            rows.append({"ticker": t, "date": str(d.date()), "field": col,
                         "csv": r[col], "yf": None, "diff_pct": None})
            continue
        hist.index = pd.to_datetime(hist.index).tz_localize(None)
        if d in hist.index:
            yf_val = float(hist.loc[d, "Close"].iloc[0]) if hasattr(hist.loc[d, "Close"], "iloc") else float(hist.loc[d, "Close"])
        else:
            nearest = hist.index[hist.index.get_indexer([d], method="nearest")[0]]
            yf_val = float(hist.loc[nearest, "Close"].iloc[0]) if hasattr(hist.loc[nearest, "Close"], "iloc") else float(hist.loc[nearest, "Close"])
        diff_pct = (r[col] - yf_val) / yf_val * 100
        rows.append({"ticker": t, "date": str(d.date()), "field": col,
                     "csv": round(r[col], 4), "yf": round(yf_val, 4),
                     "diff_pct": round(diff_pct, 2)})

out = pd.DataFrame(rows)
print(out.to_string(index=False))
print("\n=== |diff_pct| > 1% ===")
print(out[out["diff_pct"].abs() > 1].to_string(index=False))
