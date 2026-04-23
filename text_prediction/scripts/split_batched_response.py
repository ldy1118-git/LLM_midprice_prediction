"""Split a batched LLM response into per-code CSV files.

Usage:
    # split a single raw batch file
    python3 scripts/split_batched_response.py output/chatgpt5.4/run1/_raw/batch1.txt

    # split every *.txt under a run directory's _raw/ folder
    python3 scripts/split_batched_response.py --run-dir output/chatgpt5.4/run1

Each raw batch file is expected to contain 4 sections with delimiters:
    === CODE: A ===
    day,open,high,low,close
    D64,...
    ...
    D125,...
    === CODE: B ===
    ...

The parser is lenient about:
  - leading/trailing whitespace on each line
  - optional ```csv fences
  - extra blank lines between sections
  - a trailing `=== END ===` marker

But it fails loudly if a section has the wrong number of rows, wrong header,
or day labels outside D64..D125.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

EXPECTED_DAYS = [f"D{i}" for i in range(64, 126)]
CODE_RE = re.compile(r"^\s*={2,}\s*CODE\s*:\s*([A-Z])\s*={2,}\s*$", re.IGNORECASE)
END_RE = re.compile(r"^\s*={2,}\s*END\s*={2,}\s*$", re.IGNORECASE)
FENCE_RE = re.compile(r"^\s*```")


def split_sections(text: str) -> dict[str, list[str]]:
    sections: dict[str, list[str]] = {}
    current_code: str | None = None
    for raw in text.splitlines():
        if FENCE_RE.match(raw):
            continue
        if END_RE.match(raw):
            current_code = None
            continue
        m = CODE_RE.match(raw)
        if m:
            current_code = m.group(1).upper()
            sections[current_code] = []
            continue
        if current_code is None:
            continue
        sections[current_code].append(raw.rstrip())
    return sections


def parse_section(code: str, lines: list[str]) -> str:
    """Return validated CSV text (header + 62 rows, newline-joined).

    Tolerates an extra trailing D126 row (some models echo back the given
    anchor day); it's dropped silently. Also tolerates extra rows after D125.
    """
    body = [ln for ln in lines if ln.strip() != ""]
    if not body:
        raise ValueError(f"[{code}] empty section")
    header = body[0].strip().lower().replace(" ", "")
    if header != "day,open,high,low,close":
        raise ValueError(f"[{code}] unexpected header: {body[0]!r}")
    data_all = body[1:]
    # Keep only rows whose day label is in D64..D125, preserving order.
    wanted = set(EXPECTED_DAYS)
    data = [row for row in data_all
            if row.split(",", 1)[0].strip() in wanted]
    if len(data) != 62:
        raise ValueError(f"[{code}] expected 62 rows (D64..D125), got {len(data)}"
                         f" (total rows in section: {len(data_all)})")
    cleaned = []
    for i, row in enumerate(data):
        parts = [p.strip() for p in row.split(",")]
        if len(parts) != 5:
            raise ValueError(f"[{code}] row {i} has {len(parts)} fields: {row!r}")
        day = parts[0]
        if day != EXPECTED_DAYS[i]:
            raise ValueError(f"[{code}] row {i}: expected day {EXPECTED_DAYS[i]} got {day}")
        # Validate that OHLC are numeric (raises if not)
        o, h, lo, c = (float(x) for x in parts[1:])
        if lo > min(o, c) + 1e-9 or h < max(o, c) - 1e-9 or lo > h + 1e-9:
            print(f"  warn [{code}] row {i} ({day}) violates OHLC ordering: "
                  f"o={o} h={h} l={lo} c={c}", file=sys.stderr)
        cleaned.append(f"{day},{o},{h},{lo},{c}")
    return "day,open,high,low,close\n" + "\n".join(cleaned) + "\n"


def process_file(raw_path: Path) -> list[Path]:
    """Split one raw batch file. Writes {CODE}.csv next to the `_raw/` dir
    (i.e., under the parent run directory). Returns written paths."""
    run_dir = raw_path.parent.parent  # .../run{k}/_raw/batch{N}.txt -> run{k}
    text = raw_path.read_text()
    sections = split_sections(text)
    if not sections:
        raise RuntimeError(f"{raw_path}: no `=== CODE: X ===` markers found")
    written: list[Path] = []
    for code, lines in sections.items():
        try:
            csv_text = parse_section(code, lines)
        except Exception as e:
            print(f"FAIL {raw_path.name} [{code}]: {e}", file=sys.stderr)
            continue
        out = run_dir / f"{code}.csv"
        out.write_text(csv_text)
        written.append(out)
        print(f"ok   {out.relative_to(run_dir.parent.parent.parent)}")
    return written


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("paths", nargs="*", type=Path, help="raw batch *.txt files")
    ap.add_argument("--run-dir", type=Path,
                    help="scan RUN_DIR/_raw/*.txt instead of listing files")
    args = ap.parse_args()

    targets: list[Path] = list(args.paths)
    if args.run_dir:
        raw_dir = args.run_dir / "_raw"
        if not raw_dir.is_dir():
            sys.exit(f"no _raw/ under {args.run_dir}")
        targets.extend(sorted(raw_dir.glob("*.txt")))
    if not targets:
        sys.exit("nothing to do (pass files or --run-dir)")

    total = 0
    for p in targets:
        if not p.is_file():
            print(f"skip (not a file): {p}", file=sys.stderr)
            continue
        total += len(process_file(p))
    print(f"\n{total} CSV file(s) written")


if __name__ == "__main__":
    main()
