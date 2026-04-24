"""Count candle bodies inside the forecast region of each output image.

For each image in output/{model}/run{k}/{CODE}.png:
  - Try to locate the dark-blue forecast rectangle (#1976d2).
  - If found, count candle-colored column clusters inside that rectangle.
  - If not found (model regenerated the image from scratch), fall back to
    counting candle columns in the right 55 percent of the image and report
    `box_found=False`.

Output: labels.csv per run folder with columns
  code, stage1, stage2, n_candles, box_found, notes
where
  stage1 = 1 if the file exists (image was returned)
  stage2 = 1 if n_candles >= 50   (>= 62 * 0.8)
"""
from __future__ import annotations

import csv
import sys
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = ROOT / "output"

CODES = list("ABCDEFGHIJKLMNOPQRST")
MODELS = ["claude-opus-4.7", "gemini3.1pro", "chatgpt5.4"]
STAGE2_MIN = 50  # 62 * 0.8


def _column_runs(mask_1d: np.ndarray, min_width: int = 2) -> int:
    """Count contiguous True-runs of at least `min_width` columns."""
    runs = 0
    in_run = False
    run_start = 0
    for i, v in enumerate(mask_1d):
        if v and not in_run:
            in_run = True
            run_start = i
        elif not v and in_run:
            in_run = False
            if i - run_start >= min_width:
                runs += 1
    if in_run and len(mask_1d) - run_start >= min_width:
        runs += 1
    return runs


def count_candles_in_image(path: Path) -> tuple[int, bool]:
    """Return (n_candles, box_found)."""
    img = np.array(Image.open(path).convert("RGB"))
    H, W, _ = img.shape
    r, g, b = img[..., 0], img[..., 1], img[..., 2]

    # Blue rectangle edge: #1976d2 ≈ (25, 118, 210). Be generous with tolerance.
    blue_edge = (r < 80) & (g > 90) & (g < 160) & (b > 170)

    # Candle body colors (with tolerance):
    # Up candle target:  #26a69a = (38, 166, 154)
    # Down candle target: #ef5350 = (239, 83, 80)
    green_mask = (r < 110) & (g > 120) & (g < 210) & (b > 100) & (b < 190)
    red_mask = (r > 200) & (g < 140) & (b < 140)
    candle_mask = green_mask | red_mask

    # Locate blue rectangle by finding column ranges where blue-edge spans
    # a large vertical extent (the vertical sides of the rectangle).
    col_blue_counts = blue_edge.sum(axis=0)
    vertical_side_threshold = H * 0.4  # the rect side should span most of the plot height
    strong_blue_cols = np.where(col_blue_counts > vertical_side_threshold)[0]

    box_found = False
    if len(strong_blue_cols) >= 2:
        left = int(strong_blue_cols[0])
        right = int(strong_blue_cols[-1])
        if right - left > W * 0.15:
            box_found = True

    if box_found:
        fc = candle_mask[:, left + 2 : right - 1]
    else:
        # Fallback: the forecast region is roughly the right 55% of the image.
        left = int(W * 0.45)
        fc = candle_mask[:, left:]

    # Column-wise candle pixel counts
    col_sums = fc.sum(axis=0)
    if col_sums.max() == 0:
        return 0, box_found

    # A column "contains a candle body" if it has a meaningful number of
    # candle pixels relative to the strongest column in this region.
    threshold = max(4, col_sums.max() * 0.15)
    is_candle_col = col_sums > threshold

    n = _column_runs(is_candle_col, min_width=2)
    return n, box_found


def process_run(model: str, run: str) -> None:
    run_dir = OUTPUT_DIR / model / run
    if not run_dir.exists():
        return

    rows = []
    for code in CODES:
        p = run_dir / f"{code}.png"
        if not p.exists():
            rows.append({
                "code": code, "stage1": 0, "stage2": 0,
                "n_candles": 0, "box_found": "", "notes": "no image",
            })
            continue
        n, box_found = count_candles_in_image(p)
        stage2 = 1 if n >= STAGE2_MIN else 0
        rows.append({
            "code": code, "stage1": 1, "stage2": stage2,
            "n_candles": n, "box_found": int(box_found), "notes": "",
        })

    out = run_dir / "labels.csv"
    with out.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["code", "stage1", "stage2", "n_candles", "box_found", "notes"])
        writer.writeheader()
        writer.writerows(rows)
    # Print summary
    s1 = sum(r["stage1"] for r in rows)
    s2 = sum(r["stage2"] for r in rows)
    print(f"{model}/{run}: stage1={s1}/20, stage2={s2}/20, avg candles={np.mean([r['n_candles'] for r in rows]):.1f}")


def main():
    # Default: process all runs that exist
    targets = []
    if len(sys.argv) > 1:
        targets = sys.argv[1:]   # e.g., gemini3.1pro/run1
    else:
        for m in MODELS:
            for r in ["run1", "run2", "run3", "run4", "run5"]:
                if (OUTPUT_DIR / m / r).exists():
                    targets.append(f"{m}/{r}")

    for t in targets:
        m, r = t.split("/")
        process_run(m, r)


if __name__ == "__main__":
    main()
