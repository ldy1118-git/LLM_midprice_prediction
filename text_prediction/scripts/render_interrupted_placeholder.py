"""Render a 'generation interrupted midway' placeholder for fig3.

Uses Claude opus 4.7 run1 predictions for a given code, but fills only the
first N_FILL candles (D64..D64+N_FILL-1) inside the blue forecast box; the
remaining D64+N_FILL..D125 positions stay empty (simulating a generation
that stopped midway). Output matches chart_prediction's exp2 image layout.
"""
from __future__ import annotations

import math
from pathlib import Path

import matplotlib
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import matplotlib.font_manager as fm
import mplfinance as mpf
import numpy as np
import pandas as pd
from matplotlib.patches import Rectangle

REPO = Path(__file__).resolve().parent.parent.parent
TEXT_DATA = REPO / "text_prediction" / "data"
FIGS = REPO / "paper" / "figures"
FIGS.mkdir(parents=True, exist_ok=True)

FONT_PATH = REPO / "assets" / "fonts" / "Pretendard-Bold.ttf"
fm.fontManager.addfont(str(FONT_PATH))
matplotlib.rcParams["font.family"] = "Pretendard"

CODE = "I"
N_FILL = 30
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
    facecolor="white", edgecolor="white", figcolor="white",
    gridstyle="-", gridcolor="#e0e0e0", y_on_right=True,
    rc={"font.size": 11, "axes.labelsize": 11,
        "xtick.labelsize": 10, "ytick.labelsize": 10},
)


def main():
    inp = pd.read_csv(TEXT_DATA / "input" / f"{CODE}.csv")
    head63 = inp[inp.day != "D126"].copy()
    d126 = inp[inp.day == "D126"].copy()
    truth = pd.read_csv(TEXT_DATA / "label" / f"{CODE}.csv")
    assert len(truth) == N_PRED
    partial = truth.iloc[:N_FILL].copy()
    nan_rows = pd.DataFrame({
        "day": [f"D{64+i}" for i in range(N_FILL, N_PRED)],
        "open": np.nan, "high": np.nan, "low": np.nan, "close": np.nan,
    })
    full = pd.concat([head63, partial, nan_rows, d126], ignore_index=True)
    assert len(full) == N_TOTAL

    end_ohlc = (
        float(d126.iloc[0]["open"]), float(d126.iloc[0]["high"]),
        float(d126.iloc[0]["low"]), float(d126.iloc[0]["close"]),
    )
    end_close = end_ohlc[3]

    visible = pd.concat([head63, partial, d126], ignore_index=True)
    ylim_lo = visible["low"].min() * 0.97
    ylim_hi = visible["high"].max() * 1.03

    df = full.rename(columns={
        "open": "Open", "high": "High", "low": "Low", "close": "Close",
    })[["Open", "High", "Low", "Close"]]
    df["Volume"] = 0
    df.index = pd.bdate_range("2000-01-03", periods=N_TOTAL)
    df.index.name = "Date"
    # Set D126 to NaN so we can redraw manually (matches chart_prediction style)
    df.iloc[-1, :4] = np.nan

    candle_width = 0.7
    fig, axes = mpf.plot(
        df, type="candle", style=TV_STYLE, volume=False, ylabel="",
        figsize=(20, 9), tight_layout=True, returnfig=True,
        scale_padding={"left": 0.05, "top": 0.6, "right": 0.8, "bottom": 0.5},
        update_width_config=dict(candle_linewidth=1.0, candle_width=candle_width),
        ylim=(ylim_lo, ylim_hi),
    )
    ax = axes[0]
    ax.set_title(CODE, loc="left", fontsize=14, fontweight="bold", pad=10)

    tick_positions = [0, 19, 39, 59, 79, 99, 119, 125]
    tick_labels = [f"D{p + 1}" for p in tick_positions]
    ax.set_xticks(tick_positions)
    ax.set_xticklabels(tick_labels, fontsize=11)

    y_lo, y_hi = ax.get_ylim()
    y_range = y_hi - y_lo
    nice_steps = [0.01, 0.02, 0.05, 0.10, 0.20, 0.25, 0.50,
                  1, 2, 4, 5, 10, 20, 25, 50, 100, 200, 500]
    raw_step = y_range / 17
    step = next((s for s in nice_steps if s >= raw_step), nice_steps[-1])
    y_tick_lo = math.floor(y_lo / step) * step
    y_tick_hi = math.ceil(y_hi / step) * step + step
    yticks = np.arange(y_tick_lo, y_tick_hi, step)
    ax.set_yticks(yticks)
    fmt = "%.2f" if step >= 1 else f"%.{max(2, len(str(step).rstrip('0').split('.')[-1]))}f"
    ax.yaxis.set_major_formatter(mticker.FormatStrFormatter(fmt))

    last_x = N_TOTAL - 1
    split_x = N_VIS - 1
    x_split_boundary = split_x + 0.5

    ax.xaxis.grid(False); ax.yaxis.grid(False)
    for ytick in yticks:
        if y_lo <= ytick <= y_hi:
            ax.plot([-0.5, x_split_boundary],
                    [ytick, ytick], color="#e0e0e0", linewidth=0.5, zorder=0,
                    solid_capstyle="butt")
    for xpos in tick_positions:
        if xpos <= split_x:
            ax.plot([xpos, xpos], [y_lo, y_hi],
                    color="#e0e0e0", linewidth=0.5, zorder=0, solid_capstyle="butt")

    # All 62 guide lines (D64..D125) — same as original input template
    for i in range(1, N_PRED + 1):
        x_line = split_x + i
        ax.axvline(x=x_line, color="#90caf9", linewidth=0.7, zorder=1, alpha=0.9)

    pred_rect = Rectangle(
        (split_x + 0.5, y_lo),
        (last_x - 0.5) - (split_x + 0.5),
        y_hi - y_lo,
        linewidth=2.0, edgecolor="#1976d2", facecolor="none", zorder=2,
    )
    ax.add_patch(pred_rect)

    ax.plot([split_x, last_x], [end_close, end_close],
            color="#ef5350", linewidth=1.2, linestyle="--", alpha=0.7, zorder=4)

    # Manually draw D126 target candle
    e_open, e_high, e_low, e_close = end_ohlc
    body_color = "#26a69a" if e_close >= e_open else "#ef5350"
    ax.plot([last_x, last_x], [e_low, e_high], color=body_color, linewidth=1.0, zorder=5)
    body_lo = min(e_open, e_close)
    body_hi = max(e_open, e_close)
    body_h = max(body_hi - body_lo, (y_hi - y_lo) * 0.001)
    ax.add_patch(Rectangle(
        (last_x - candle_width / 2, body_lo),
        candle_width, body_h,
        linewidth=1.0, edgecolor=body_color, facecolor=body_color, zorder=5,
    ))
    ax.annotate(
        f"${end_close:.2f}",
        xy=(last_x, end_close),
        xytext=(-10, 12), textcoords="offset points",
        fontsize=10, fontweight="bold", color="#ef5350", ha="right",
    )

    out = FIGS / "fig3_placeholder_interrupted.png"
    fig.savefig(out, dpi=150, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(f"saved {out}")


if __name__ == "__main__":
    main()
