"""Compose 1x4 fig2 composite (truth + 3 models) with taller/narrower cells."""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

from render_prediction_chart import render

REPO = Path(__file__).resolve().parent.parent.parent
FIGS = REPO / "paper" / "figures"
FONT_PATH = "/project/ahnailab/ldy1118/AIETF/LLM_midprice_prediction/assets/fonts/Pretendard-Bold.ttf"

CODE = "D"
RUN = "run1"
FIGSIZE = (5, 5.5)
CELLS = [
    ("truth", f"실제 {CODE} 종목의 라벨"),
    ("claude-opus-4.7", "Claude opus 4.7"),
    ("gemini3.1pro", "Gemini 3.1 Pro"),
    ("chatgpt5.4", "ChatGPT 5.4"),
]

TITLE_H = 80
TITLE_FONT_SIZE = 56
PAD = 20

for src, title in CELLS:
    out = FIGS / f"fig2_{CODE}_{src}_tall.png"
    render(CODE, src, RUN, out, title, figsize=FIGSIZE)

imgs = [Image.open(FIGS / f"fig2_{CODE}_{src}_tall.png") for src, _ in CELLS]
W, H = imgs[0].size
font = ImageFont.truetype(FONT_PATH, TITLE_FONT_SIZE)

cells = []
for img, (_, title) in zip(imgs, CELLS):
    cell = Image.new("RGB", (W, TITLE_H + H), "white")
    d = ImageDraw.Draw(cell)
    bbox = d.textbbox((0, 0), title, font=font)
    tw = bbox[2] - bbox[0]
    d.text(((W - tw) / 2, (TITLE_H - TITLE_FONT_SIZE) / 2 - 4), title, fill="black", font=font)
    cell.paste(img, (0, TITLE_H))
    cells.append(cell)

total_w = W * 4 + PAD * 3
total_h = TITLE_H + H
canvas = Image.new("RGB", (total_w, total_h), "white")
for i, cell in enumerate(cells):
    canvas.paste(cell, (i * (W + PAD), 0))

out = FIGS / f"fig2_{CODE}_1x4.png"
canvas.save(out, dpi=(150, 150))
print(f"saved {out} ({canvas.size})")
