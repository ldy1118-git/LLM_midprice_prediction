"""Render candlestick charts for exp1 prediction results (figures in paper).

For a given code and source, produces a full 126-day chart:
  - D1..D63 from input CSV
  - D64..D125 from the chosen source:
      * 'truth' -> text_prediction/data/label/{code}.csv
      * model   -> text_prediction/output/{model}/run{K}/{code}.csv
  - D126 from input CSV
Saves PNG to paper/figures/fig2_{code}_{source}.png
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

import matplotlib
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import matplotlib.font_manager as fm
import mplfinance as mpf
import numpy as np
import pandas as pd

# Register Korean font
KO_FONT_PATH = "/project/ahnailab/ldy1118/AIETF/LLM_midprice_prediction/assets/fonts/Pretendard-Bold.ttf"
if Path(KO_FONT_PATH).exists():
    fm.fontManager.addfont(KO_FONT_PATH)
    matplotlib.rcParams["font.family"] = "Pretendard"

ROOT = Path(__file__).resolve().parent.parent   # text_prediction/
REPO = ROOT.parent
DATA = ROOT / "data"
OUT_FIG = REPO / "paper" / "figures"
OUT_FIG.mkdir(parents=True, exist_ok=True)

N_VIS = 63
N_PRED = 62
N_TOTAL = 126

TV_STYLE = mpf.make_mpf_style(
    base_mpf_style="charles",
    marketcolors=mpf.make_marketcolors(
        up="#26a69a", down="#ef5350",
        edge="inherit", wick="inherit",
        volume={"up": "#90caf9", "down": "#f5a0a0"},
    ),
    facecolor="#f2f2f2", edgecolor="#f2f2f2", figcolor="#f2f2f2",
    gridstyle="-", gridcolor="#d0d0d0", y_on_right=True,
    rc={"font.size": 14, "axes.labelsize": 14,
        "xtick.labelsize": 14, "ytick.labelsize": 14,
        "font.weight": "bold", "axes.labelweight": "bold"},
)


def load_combined(code: str, source: str, run: str = "run1") -> pd.DataFrame:
    inp = pd.read_csv(DATA / "input" / f"{code}.csv")
    head63 = inp[inp.day != "D126"].copy()
    d126 = inp[inp.day == "D126"].copy()

    if source == "truth":
        mid_path = DATA / "label" / f"{code}.csv"
    else:
        mid_path = ROOT / "output" / source / run / f"{code}.csv"
    mid = pd.read_csv(mid_path)
    assert len(mid) == N_PRED, f"{mid_path}: expected {N_PRED} rows"

    full = pd.concat([head63, mid, d126], ignore_index=True)
    assert len(full) == N_TOTAL

    fake_idx = pd.bdate_range("2000-01-03", periods=N_TOTAL)
    df = full.rename(columns={
        "open": "Open", "high": "High", "low": "Low", "close": "Close",
    })[["Open", "High", "Low", "Close"]]
    df["Volume"] = 0
    df.index = fake_idx
    df.index.name = "Date"
    return df


def render(code: str, source: str, run: str, out_path: Path, title: str,
           figsize: tuple[float, float] = (8, 4.5)):
    df = load_combined(code, source, run)
    end_ohlc = (df.iloc[-1]["Open"], df.iloc[-1]["High"],
                df.iloc[-1]["Low"], df.iloc[-1]["Close"])
    ylim_lo = df["Low"].min() * 0.97
    ylim_hi = df["High"].max() * 1.03

    fig, axes = mpf.plot(
        df, type="candle", style=TV_STYLE, volume=False, ylabel="",
        figsize=figsize, tight_layout=True, returnfig=True,
        scale_padding={"left": 0.05, "top": 0.6, "right": 0.8, "bottom": 0.5},
        update_width_config=dict(candle_linewidth=1.0, candle_width=0.7),
        ylim=(ylim_lo, ylim_hi),
    )
    ax = axes[0]
    # Title is overlayed in PIL (Korean glyphs unreliable in matplotlib here)

    tick_positions = [0, 19, 39, 59, 79, 99, 119, 125]
    tick_labels = [f"D{p + 1}" for p in tick_positions]
    ax.set_xticks(tick_positions)
    ax.set_xticklabels(tick_labels, fontsize=14, fontweight="bold")
    for lbl in ax.get_yticklabels():
        lbl.set_fontweight("bold")
        lbl.set_fontsize(14)

    y_lo, y_hi = ax.get_ylim()
    y_range = y_hi - y_lo
    nice_steps = [0.01, 0.02, 0.05, 0.10, 0.20, 0.25, 0.50,
                  1, 2, 4, 5, 10, 20, 25, 50, 100, 200, 500]
    raw_step = y_range / 12
    step = next((s for s in nice_steps if s >= raw_step), nice_steps[-1])
    y_tick_lo = math.floor(y_lo / step) * step
    y_tick_hi = math.ceil(y_hi / step) * step + step
    yticks = np.arange(y_tick_lo, y_tick_hi, step)
    ax.set_yticks(yticks)
    fmt = "%.2f" if step >= 1 else f"%.{max(2, len(str(step).rstrip('0').split('.')[-1]))}f"
    ax.yaxis.set_major_formatter(mticker.FormatStrFormatter(fmt))

    ax.xaxis.grid(False); ax.yaxis.grid(False)
    for ytick in yticks:
        if y_lo <= ytick <= y_hi:
            ax.plot([-0.5, N_TOTAL - 0.5], [ytick, ytick],
                    color="#e0e0e0", linewidth=0.5, zorder=0)
    for xpos in tick_positions:
        ax.plot([xpos, xpos], [y_lo, y_hi],
                color="#e0e0e0", linewidth=0.5, zorder=0)

    # Mark boundary between history and prediction with a faint vertical line
    ax.axvline(x=N_VIS - 0.5, color="#1976d2", linewidth=0.8, alpha=0.5, zorder=1)

    fig.savefig(out_path, dpi=150, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(f"  {title} -> {out_path.relative_to(REPO)}")


def main():
    code = sys.argv[1] if len(sys.argv) > 1 else "D"
    run = sys.argv[2] if len(sys.argv) > 2 else "run1"

    combos = [
        ("truth",           f"실제 {code} 종목의 라벨"),
        ("claude-opus-4.7", "Claude opus 4.7"),
        ("gemini3.1pro",    "Gemini 3.1 Pro"),
        ("chatgpt5.4",      "ChatGPT 5.4"),
    ]
    for source, title in combos:
        out = OUT_FIG / f"fig2_{code}_{source}.png"
        render(code, source, run, out, title)


if __name__ == "__main__":
    main()
