"""Compose 1x2 fig3: stage1 failure (left) + stage2 failure (right)."""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

REPO = Path(__file__).resolve().parent.parent.parent
FIGS = REPO / "paper" / "figures"
CHART = REPO / "chart_prediction"
FONT_PATH = "/project/ahnailab/ldy1118/AIETF/LLM_midprice_prediction/assets/fonts/Pretendard-Bold.ttf"

STAGE1_IMG = FIGS / "fig3_gemini_chat_crop.png"
STAGE2_IMG = FIGS / "fig3_placeholder_interrupted.png"

PANELS = [
    (STAGE1_IMG, "[이미지 생성 실패] Gemini"),
    (STAGE2_IMG, "[캔들 개수 불일치] Gemini, 종목 I"),
]

TITLE_H = 90
TITLE_FONT_SIZE = 42
PAD = 30
TARGET_H = 900

font = ImageFont.truetype(FONT_PATH, TITLE_FONT_SIZE)

cells = []
for path, title in PANELS:
    img = Image.open(path).convert("RGB")
    w, h = img.size
    new_w = int(w * TARGET_H / h)
    img = img.resize((new_w, TARGET_H), Image.LANCZOS)
    cell = Image.new("RGB", (new_w, TITLE_H + TARGET_H), "white")
    d = ImageDraw.Draw(cell)
    bbox = d.textbbox((0, 0), title, font=font)
    tw = bbox[2] - bbox[0]
    d.text(((new_w - tw) / 2, (TITLE_H - TITLE_FONT_SIZE) / 2 - 4),
           title, fill="black", font=font)
    cell.paste(img, (0, TITLE_H))
    cells.append(cell)

total_w = sum(c.size[0] for c in cells) + PAD
total_h = TITLE_H + TARGET_H
canvas = Image.new("RGB", (total_w, total_h), "white")
x = 0
for cell in cells:
    canvas.paste(cell, (x, 0))
    x += cell.size[0] + PAD

out = FIGS / "fig3_1x2.png"
canvas.save(out, dpi=(150, 150))
print(f"saved {out} ({canvas.size})")
