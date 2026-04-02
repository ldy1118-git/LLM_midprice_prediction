"""
Chart-based Midprice Prediction - Image Generation (Step 1)
blank_3m 차트를 Gemini에게 보내 빈 영역을 캔들로 채운 이미지를 생성

사용법:
  python predict.py --model gemini --variant flash --prompt A
  python predict.py --model gemini --variant flash --prompt A --ticker AAPL
"""

from google import genai
from google.genai import types
from pathlib import Path
from PIL import Image
import time
import io
import sys
import json
import argparse
import os
from datetime import datetime

sys.stdout.reconfigure(line_buffering=True)

# ── 경로 설정 ──
BASE_DIR = Path(__file__).resolve().parent.parent
INPUT_DIR = BASE_DIR / "data" / "input"
PROMPTS_DIR = BASE_DIR / "prompts"
OUTPUT_DIR = BASE_DIR / "output"

# ── API 설정 ──
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
DELAY_BETWEEN_IMAGES = 10  # 초
MAX_RETRIES = 3
RATE_LIMIT_BACKOFF = 600   # 10분

MODEL_MAP = {
    ("gemini", "flash"): "gemini-2.5-flash-image",
    ("gemini", "pro"): "gemini-3-pro-image-preview",
}


def load_chart_image(path: Path) -> bytes:
    """차트 이미지를 로드하여 bytes 반환"""
    img = Image.open(path)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def load_prompt(prompt_name: str) -> str:
    """프롬프트 파일 로드"""
    prompt_path = PROMPTS_DIR / f"{prompt_name}.txt"
    if not prompt_path.exists():
        raise FileNotFoundError(f"프롬프트 없음: {prompt_path}")
    return prompt_path.read_text(encoding="utf-8").strip()


def get_tickers() -> list[str]:
    """input 폴더에서 티커 목록 추출"""
    tickers = []
    for f in sorted(INPUT_DIR.glob("*_blank_3m.png")):
        ticker = f.stem.replace("_blank_3m", "")
        tickers.append(ticker)
    return tickers


def load_progress(progress_path: Path) -> dict:
    """진행 상황 로드"""
    if progress_path.exists():
        return json.loads(progress_path.read_text())
    return {"completed": [], "failed": []}


def save_progress(progress: dict, progress_path: Path):
    """진행 상황 저장"""
    progress_path.write_text(json.dumps(progress, indent=2))


def predict_single(client, model_id: str, chart_bytes: bytes,
                   prompt_text: str, ticker: str) -> bytes | None:
    """단일 차트에 대해 Gemini API 호출 → 생성된 이미지 bytes 반환"""
    contents = [
        types.Part.from_bytes(data=chart_bytes, mime_type="image/png"),
        prompt_text,
    ]

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = client.models.generate_content(
                model=model_id,
                contents=contents,
                config=types.GenerateContentConfig(
                    temperature=0.0,
                    response_modalities=["Image"],
                ),
            )

            if response.candidates:
                for part in response.candidates[0].content.parts:
                    if part.inline_data:
                        print(f"  [{ticker}] 이미지 생성 성공 (attempt {attempt})")
                        return part.inline_data.data

            print(f"  [{ticker}] 응답에 이미지 없음 (attempt {attempt}/{MAX_RETRIES})")
            time.sleep(10)

        except Exception as e:
            error_msg = str(e)
            if "429" in error_msg or "RESOURCE_EXHAUSTED" in error_msg:
                print(f"  [{ticker}] RATE LIMIT! {RATE_LIMIT_BACKOFF}s 대기...")
                time.sleep(RATE_LIMIT_BACKOFF)
            elif "quota" in error_msg.lower():
                print(f"  [{ticker}] QUOTA 초과! 종료.")
                sys.exit(1)
            else:
                print(f"  [{ticker}] 에러 (attempt {attempt}): {error_msg}")
                time.sleep(30)

    return None


def main():
    parser = argparse.ArgumentParser(description="Chart prediction via Gemini API")
    parser.add_argument("--model", default="gemini", choices=["gemini"])
    parser.add_argument("--variant", default="flash", choices=["flash", "pro"])
    parser.add_argument("--prompt", default="A", help="프롬프트 이름 (A, B, ...)")
    parser.add_argument("--ticker", default=None, help="특정 티커만 실행")
    args = parser.parse_args()

    # 모델 설정
    model_id = MODEL_MAP.get((args.model, args.variant))
    if not model_id:
        print(f"지원하지 않는 모델: {args.model}/{args.variant}")
        sys.exit(1)

    # 출력 폴더
    out_dir = OUTPUT_DIR / args.model / args.variant / args.prompt
    raw_dir = out_dir / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)

    # 프롬프트 로드
    prompt_text = load_prompt(args.prompt)
    print(f"모델: {model_id}")
    print(f"프롬프트: {args.prompt}")
    print(f"출력: {out_dir}\n")

    # Gemini 클라이언트
    if not GEMINI_API_KEY:
        print("GEMINI_API_KEY 환경변수를 설정해주세요.")
        sys.exit(1)
    client = genai.Client(api_key=GEMINI_API_KEY)

    # 티커 목록
    tickers = [args.ticker] if args.ticker else get_tickers()

    # 진행 상황
    progress_path = out_dir / "progress.json"
    progress = load_progress(progress_path)

    print(f"총 {len(tickers)}개 티커 | 완료: {len(progress['completed'])}개\n")

    for i, ticker in enumerate(tickers):
        if ticker in progress["completed"]:
            print(f"[{i+1}/{len(tickers)}] {ticker} - 이미 완료, 스킵")
            continue

        print(f"[{i+1}/{len(tickers)}] {ticker} 예측 중...")

        # 차트 이미지 로드
        chart_path = INPUT_DIR / f"{ticker}_blank_3m.png"
        if not chart_path.exists():
            print(f"  차트 없음: {chart_path}")
            progress["failed"].append(ticker)
            save_progress(progress, progress_path)
            continue

        chart_bytes = load_chart_image(chart_path)

        # API 호출
        result_bytes = predict_single(client, model_id, chart_bytes, prompt_text, ticker)

        if result_bytes:
            # 생성 이미지 저장 (타임스탬프 포함하여 이전 결과 보존)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            save_path = raw_dir / f"{ticker}_{timestamp}.png"
            with open(save_path, "wb") as f:
                f.write(result_bytes)
            print(f"  저장: {save_path.name}")

            progress["completed"].append(ticker)
            save_progress(progress, progress_path)
        else:
            print(f"  [{ticker}] 실패!")
            progress["failed"].append(ticker)
            save_progress(progress, progress_path)

        # 딜레이
        if i < len(tickers) - 1:
            time.sleep(DELAY_BETWEEN_IMAGES)

    # 완료 요약
    print(f"\n완료: {len(progress['completed'])}/{len(tickers)}")
    if progress["failed"]:
        print(f"실패: {progress['failed']}")


if __name__ == "__main__":
    main()
