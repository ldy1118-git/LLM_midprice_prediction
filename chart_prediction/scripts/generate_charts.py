"""Generate 20 masked candlestick charts for exp2.

Reads OHLC from text_prediction/data/{input,label}/{CODE}.csv, renders:
  - data/input/{CODE}.png        : D1-D63 visible candles, D64-D125 blank with
                                   blue forecast box + guide lines, D126 target
                                   candle drawn on the right edge
  - data/label/full_charts/{CODE}.png : same layout but D64-D125 also filled
                                        with actual candles (for reference)

Compared to the legacy chart generator, this version:
  - uses code letter (A..T) instead of ticker as title
  - replaces the calendar-date x-axis with D1..D126 index ticks
"""
from __future__ import annotations

import math
import os
from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import mplfinance as mpf
import numpy as np
import pandas as pd
from matplotlib.patches import Rectangle

ROOT = Path(__file__).resolve().parent.parent
TEXT_DATA = ROOT.parent / "text_prediction" / "data"
INPUT_DIR = ROOT / "data" / "input"
FULL_DIR = ROOT / "data" / "label" / "full_charts"
INPUT_DIR.mkdir(parents=True, exist_ok=True)
FULL_DIR.mkdir(parents=True, exist_ok=True)

CODES = list("ABCDEFGHIJKLMNOPQRST")
N_VIS = 63     # D1..D63
N_PRED = 62    # D64..D125
N_TOTAL = 126  # D1..D126

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


def load_full_ohlc(code: str) -> pd.DataFrame:
    """Return 126-row OHLC frame indexed D1..D126 with synthetic DatetimeIndex.

    mplfinance requires a DatetimeIndex, so we fabricate consecutive business
    days starting from 2000-01-03. The synthetic dates are never displayed —
    only the D1..D126 labels derived from position.
    """
    inp = pd.read_csv(TEXT_DATA / "input" / f"{code}.csv")   # 64 rows: D1..D63 + D126
    lab = pd.read_csv(TEXT_DATA / "label" / f"{code}.csv")   # 62 rows: D64..D125
    # Merge back into D1..D126 order
    head63 = inp[inp.day != "D126"].copy()
    d126 = inp[inp.day == "D126"].copy()
    full = pd.concat([head63, lab, d126], ignore_index=True)
    assert len(full) == N_TOTAL, f"{code}: expected {N_TOTAL}, got {len(full)}"
    assert list(full.day) == [f"D{i}" for i in range(1, N_TOTAL + 1)]

    fake_idx = pd.bdate_range("2000-01-03", periods=N_TOTAL)
    df = full.rename(columns={
        "open": "Open", "high": "High", "low": "Low", "close": "Close",
    })
    df = df[["Open", "High", "Low", "Close"]]
    df["Volume"] = 0
    df.index = fake_idx
    df.index.name = "Date"
    return df


def render_chart(code: str, full: pd.DataFrame, masked: bool) -> Path:
    """Render one chart (masked=True -> exp2 input; masked=False -> full reference)."""
    # Build the actual dataframe passed to mpf: mask D64..D125 if requested
    df = full.copy()
    if masked:
        df.iloc[N_VIS:N_TOTAL - 1, :4] = np.nan  # rows D64..D125 OHLC -> NaN

    end_ohlc = (
        float(full.iloc[-1]["Open"]),
        float(full.iloc[-1]["High"]),
        float(full.iloc[-1]["Low"]),
        float(full.iloc[-1]["Close"]),
    )
    end_close = end_ohlc[3]

    # y-limits based on full visible range (use truth D1..D63 + D126 at least,
    # and when unmasked include D64..D125 too)
    visible = full.iloc[:N_VIS] if masked else full
    ylim_lo = min(visible["Low"].min(), end_ohlc[2]) * 0.97
    ylim_hi = max(visible["High"].max(), end_ohlc[1]) * 1.03

    candle_width = 0.7
    fig, axes = mpf.plot(
        df, type="candle", style=TV_STYLE, volume=False, ylabel="",
        figsize=(20, 9), tight_layout=True, returnfig=True,
        scale_padding={"left": 0.05, "top": 0.6, "right": 0.8, "bottom": 0.5},
        update_width_config=dict(candle_linewidth=1.0, candle_width=candle_width),
        ylim=(ylim_lo, ylim_hi),
    )
    ax = axes[0]
    ax.set_title(code, loc="left", fontsize=14, fontweight="bold", pad=10)

    # X-axis: index labels D1, D20, D40, D60, D80, D100, D120
    tick_positions = [0, 19, 39, 59, 79, 99, 119, 125]
    tick_labels = [f"D{p + 1}" for p in tick_positions]
    ax.set_xticks(tick_positions)
    ax.set_xticklabels(tick_labels, fontsize=11)

    # Y-axis: ~17 nice ticks
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

    last_x = N_TOTAL - 1       # position of D126
    split_x = N_VIS - 1        # position of D63 (last visible)
    x_split_boundary = split_x + 0.5

    # Disable default grid, draw manual grid only in historical region
    ax.xaxis.grid(False)
    ax.yaxis.grid(False)
    for ytick in yticks:
        if y_lo <= ytick <= y_hi:
            ax.plot([-0.5, x_split_boundary if masked else last_x + 0.5],
                    [ytick, ytick], color="#e0e0e0", linewidth=0.5, zorder=0,
                    solid_capstyle="butt")
    for xpos in tick_positions:
        # Only grid lines inside historical region for masked; full range otherwise
        if not masked or xpos <= split_x:
            ax.plot([xpos, xpos], [y_lo, y_hi],
                    color="#e0e0e0", linewidth=0.5, zorder=0, solid_capstyle="butt")

    if masked:
        # Blue vertical guide lines for D64..D125 positions (62 of them)
        for i in range(1, N_PRED + 1):
            x_line = split_x + i
            ax.axvline(x=x_line, color="#90caf9", linewidth=0.7, zorder=1, alpha=0.9)

        # Blue rectangle marking the forecast region (D64..D125, excluding D126)
        pred_rect = Rectangle(
            (split_x + 0.5, y_lo),
            (last_x - 0.5) - (split_x + 0.5),
            y_hi - y_lo,
            linewidth=2.0, edgecolor="#1976d2", facecolor="none", zorder=2,
        )
        ax.add_patch(pred_rect)

        # Red horizontal dashed line at D126 close, spanning forecast region
        ax.plot([split_x, last_x], [end_close, end_close],
                color="#ef5350", linewidth=1.2, linestyle="--", alpha=0.7, zorder=4)

        # Draw D126 target candle manually (since it's NaN in masked df)
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

        # Price label at D126 close
        ax.annotate(
            f"${end_close:.2f}",
            xy=(last_x, end_close),
            xytext=(-10, 12), textcoords="offset points",
            fontsize=10, fontweight="bold", color="#ef5350", ha="right",
        )

    out_dir = INPUT_DIR if masked else FULL_DIR
    fpath = out_dir / f"{code}.png"
    fig.savefig(fpath, dpi=150, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return fpath


def main():
    for code in CODES:
        full = load_full_ohlc(code)
        p_masked = render_chart(code, full, masked=True)
        p_full = render_chart(code, full, masked=False)
        print(f"  {code}: {p_masked.relative_to(ROOT)} | {p_full.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
