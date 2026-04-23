"""Build batched prompts (2 datasets per prompt) for experiment 1.

Creates prompts/batched/batch{N}.txt for N=1..10:
    batch1: A B    batch2: C D    batch3: E F    batch4: G H    batch5: I J
    batch6: K L    batch7: M N    batch8: O P    batch9: Q R    batch10: S T

Each prompt packs 2 independent (masked) OHLC histories and asks for 2 CSV
outputs separated by strict delimiters.

Rationale: batch=4 showed endpoint-ignore failures in Gemini 3.1 Pro starting
from the 2nd section. batch=2 keeps instruction-to-section ratio higher and
is uniform across the 3 models for fair comparison.
"""
from __future__ import annotations

import string
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
INPUT_DIR = ROOT / "data" / "input"
OUT_DIR = ROOT / "prompts" / "batched"

BATCH_SIZE = 2
ALL_CODES = list(string.ascii_uppercase[:20])  # A..T

HEADER = """\
You are a quantitative analyst specializing in stock price path modeling.

You will be given daily OHLC (Open, High, Low, Close) histories for TWO
independent, masked NASDAQ-listed stocks. Each stock is identified by a code
letter. Dates are replaced with relative day indices D1..D126; no calendar
dates are revealed.

For EACH of the 2 stocks:
  - OHLC for D1..D63 (63 trading days) is provided.
  - OHLC for D126 (the last day of the 126-day window) is also provided.
  - OHLC for D64..D125 (62 trading days in the middle) is MISSING.

Your task is to predict the missing OHLC for D64..D125 (62 rows) for EACH of
the 2 stocks, INDEPENDENTLY. The 2 stocks are UNRELATED: do NOT average,
align, or propagate information across them. Treat each prediction as its
own separate task.

For every predicted day:
  - Reflect the average volatility and typical candle patterns of that
    stock's OWN input (D1..D63). Capture dynamic movement (trends, swings,
    occasional gaps); do NOT over-smooth into a near-linear path.
  - Satisfy per-day OHLC constraints: low <= min(open, close), and
    high >= max(open, close), and low <= high.

CRITICAL ENDPOINT CONSTRAINT — read carefully before producing each section:
  D126 for that stock is GIVEN. Your predicted D125 close MUST be within a
  realistic single-day move of the given D126 open/close (typically within
  ~1 average daily range of the input history). It is a HARD ERROR to output
  a D125 that would require a >5% gap overnight to reach D126. Before
  emitting the final rows of each section, verify this by comparing your
  D125 close against D126 and adjust if the gap is unrealistic.

--- INPUT DATA ---
"""

OUTPUT_INSTRUCTIONS = """\
--- OUTPUT INSTRUCTIONS ---
Return the 2 predictions in the following STRICT format. No prose, no code
fences, no blank lines inside a section. Each stock's section starts with a
delimiter line, followed by the CSV header, followed by exactly 62 data rows
in the order D64..D125.

=== CODE: <code> ===
day,open,high,low,close
D64,<open>,<high>,<low>,<close>
D65,<open>,<high>,<low>,<close>
...
D125,<open>,<high>,<low>,<close>

Emit the 2 sections in this exact order: {order}.
Remember the CRITICAL ENDPOINT CONSTRAINT above: the D125 close in each
section must connect plausibly to that section's given D126 — no unrealistic
overnight gap.
End the response with a single final line:
=== END ===
"""


def load_known_csv(code: str) -> str:
    df = pd.read_csv(INPUT_DIR / f"{code}.csv")
    lines = []
    for _, r in df.iterrows():
        lines.append(f"{r.day},{r.open:.4f},{r.high:.4f},{r.low:.4f},{r.close:.4f}")
    return "\n".join(lines)


def build_batch(codes: list[str]) -> str:
    parts = [HEADER]
    for code in codes:
        parts.append(f"### STOCK CODE: {code}\n")
        parts.append("day,open,high,low,close\n")
        parts.append(load_known_csv(code))
        parts.append("\n\n")
    parts.append(OUTPUT_INSTRUCTIONS.format(order=", ".join(codes)))
    return "".join(parts)


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for i in range(0, len(ALL_CODES), BATCH_SIZE):
        codes = ALL_CODES[i : i + BATCH_SIZE]
        text = build_batch(codes)
        n = i // BATCH_SIZE + 1
        out = OUT_DIR / f"batch{n}.txt"
        out.write_text(text)
        print(f"wrote {out}  codes={codes}  bytes={len(text)}")


if __name__ == "__main__":
    main()
