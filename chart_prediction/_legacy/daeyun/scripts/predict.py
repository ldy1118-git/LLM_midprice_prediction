"""
Chart-based Midprice Prediction
blank_3m 차트를 LLM에게 보내 예측 결과를 받음
- 이미지 모드 (v3, v4): LLM이 캔들을 직접 그린 이미지 반환
- 텍스트 모드 (v5+):   LLM이 OHLC 값을 CSV 텍스트로 반환

사용법:
  python predict.py --version v4 --ticker AAPL          # 이미지 출력
  python predict.py --version v5 --ticker AAPL --text    # 텍스트(CSV) 출력
"""

from google import genai
from google.genai import types
from pathlib import Path
from PIL import Image
import time
import io
import sys
import argparse
import os
import random

sys.stdout.reconfigure(line_buffering=True)

# ── 경로 설정 ──
BASE_DIR = Path(__file__).resolve().parent.parent       # daeyun/
SHARED_DIR = BASE_DIR.parent                            # chart_prediction/
INPUT_DIR = SHARED_DIR / "data" / "input"               # 공유 입력 차트
PROMPTS_DIR = BASE_DIR / "prompts"                      # daeyun/prompts
OUTPUT_DIR = BASE_DIR / "output"                        # daeyun/output

# ── API 설정 ──
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
DELAY_BETWEEN_CALLS = 10
MAX_RETRIES = 3
RATE_LIMIT_BACKOFF = 600

# 이미지 생성용 모델
IMAGE_MODEL_MAP = {
    ("gemini", "flash"): "gemini-2.5-flash-image",
    ("gemini", "pro"): "gemini-3-pro-image-preview",
}

# 텍스트 출력용 모델
TEXT_MODEL_MAP = {
    ("gemini", "flash"): "gemini-2.5-flash",
    ("gemini", "pro"): "gemini-2.5-pro",
}


def load_chart_image(path: Path) -> bytes:
    img = Image.open(path)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def load_prompt(prompt_name: str, version: str) -> tuple[str, Path]:
    prompt_path = PROMPTS_DIR / prompt_name / f"{prompt_name}.{version}.txt"
    if not prompt_path.exists():
        raise FileNotFoundError(f"프롬프트 없음: {prompt_path}")
    return prompt_path.read_text(encoding="utf-8").strip(), prompt_path


def get_tickers() -> list[str]:
    tickers = []
    for f in sorted(INPUT_DIR.glob("*_blank_3m.png")):
        ticker = f.stem.replace("_blank_3m", "")
        tickers.append(ticker)
    return tickers


def predict_image(client, model_id: str, chart_bytes: bytes,
                  prompt_text: str, ticker: str) -> bytes | None:
    """이미지 모드: LLM이 캔들을 그린 이미지 반환"""
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
                    response_modalities=["Text", "Image"],
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
            _handle_error(e, ticker, attempt)
    return None


def predict_text(client, model_id: str, chart_bytes: bytes,
                 prompt_text: str, ticker: str) -> str | None:
    """텍스트 모드: LLM이 OHLC CSV 텍스트 반환"""
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
                ),
            )
            if response.text:
                print(f"  [{ticker}] 텍스트 추출 성공 (attempt {attempt})")
                return response.text
            print(f"  [{ticker}] 응답에 텍스트 없음 (attempt {attempt}/{MAX_RETRIES})")
            time.sleep(10)
        except Exception as e:
            _handle_error(e, ticker, attempt)
    return None


def _handle_error(e: Exception, ticker: str, attempt: int):
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


def main():
    parser = argparse.ArgumentParser(description="Chart prediction via Gemini API")
    parser.add_argument("--model", default="gemini", choices=["gemini"])
    parser.add_argument("--variant", default="flash", choices=["flash", "pro"])
    parser.add_argument("--prompt", default="test", help="프롬프트 이름 (test, A, ...)")
    parser.add_argument("--version", required=True, help="버전 (v3, v4, v5, ...)")
    parser.add_argument("--text", action="store_true", help="텍스트(CSV) 출력 모드 (v5+)")
    parser.add_argument("--ticker", default=None, help="특정 티커만 실행")
    parser.add_argument("--random", action="store_true", help="랜덤 티커 1개 선택")
    args = parser.parse_args()

    # 모델 설정
    model_map = TEXT_MODEL_MAP if args.text else IMAGE_MODEL_MAP
    model_id = model_map.get((args.model, args.variant))
    if not model_id:
        print(f"지원하지 않는 모델: {args.model}/{args.variant}")
        sys.exit(1)

    # 출력 폴더
    out_dir = OUTPUT_DIR / args.model / args.variant / args.prompt
    raw_dir = out_dir / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)

    # 프롬프트 로드
    prompt_text, prompt_path = load_prompt(args.prompt, args.version)
    mode_label = "텍스트(CSV)" if args.text else "이미지"
    print(f"모델: {model_id}")
    print(f"모드: {mode_label}")
    print(f"프롬프트: {prompt_path.relative_to(SHARED_DIR)}")
    print(f"출력: {raw_dir.relative_to(SHARED_DIR)}\n")

    # Gemini 클라이언트
    if not GEMINI_API_KEY:
        print("GEMINI_API_KEY 환경변수를 설정해주세요.")
        sys.exit(1)
    client = genai.Client(api_key=GEMINI_API_KEY)

    # 티커 목록
    if args.ticker:
        tickers = [args.ticker]
    elif args.random:
        tickers = [random.choice(get_tickers())]
    else:
        tickers = get_tickers()
    print(f"총 {len(tickers)}개 티커\n")

    completed = []
    failed = []

    for i, ticker in enumerate(tickers):
        print(f"[{i+1}/{len(tickers)}] {ticker} 예측 중...")

        chart_path = INPUT_DIR / f"{ticker}_blank_3m.png"
        if not chart_path.exists():
            print(f"  차트 없음: {chart_path}")
            failed.append(ticker)
            continue

        chart_bytes = load_chart_image(chart_path)

        if args.text:
            # 텍스트 모드 → CSV 저장
            result = predict_text(client, model_id, chart_bytes, prompt_text, ticker)
            if result:
                save_path = raw_dir / f"{args.version}_{ticker}.csv"
                save_path.write_text(result, encoding="utf-8")
                print(f"  저장: {save_path.name}")
                completed.append(ticker)
            else:
                print(f"  [{ticker}] 실패!")
                failed.append(ticker)
        else:
            # 이미지 모드 → PNG 저장
            result = predict_image(client, model_id, chart_bytes, prompt_text, ticker)
            if result:
                save_path = raw_dir / f"{args.version}_{ticker}.png"
                with open(save_path, "wb") as f:
                    f.write(result)
                print(f"  저장: {save_path.name}")
                completed.append(ticker)
            else:
                print(f"  [{ticker}] 실패!")
                failed.append(ticker)

        if i < len(tickers) - 1:
            time.sleep(DELAY_BETWEEN_CALLS)

    print(f"\n완료: {len(completed)}/{len(tickers)}")
    if failed:
        print(f"실패: {failed}")


if __name__ == "__main__":
    main()
