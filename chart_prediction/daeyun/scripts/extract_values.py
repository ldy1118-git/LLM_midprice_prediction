"""
Chart-based Midprice Prediction - Value Extraction (Step 2)
predict.py가 생성한 차트 이미지를 LLM에 보내 캔들 OHLC 값을 추출

파이프라인:
  blank_3m → LLM(그리기) → 생성 이미지 → LLM(읽기) → OHLC CSV

사용법:
  python extract_values.py --model gemini --variant flash --prompt test
  python extract_values.py --model gemini --variant flash --prompt test --ticker AAPL
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
import csv

sys.stdout.reconfigure(line_buffering=True)

# ── 경로 설정 ──
BASE_DIR = Path(__file__).resolve().parent.parent       # daeyun/
PROMPTS_DIR = BASE_DIR / "prompts"                      # daeyun/prompts
OUTPUT_DIR = BASE_DIR / "output"                        # daeyun/output

# ── API 설정 ──
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
DELAY_BETWEEN_CALLS = 10
MAX_RETRIES = 3
RATE_LIMIT_BACKOFF = 600

# 값 추출용 모델 (텍스트 출력)
MODEL_MAP = {
    ("gemini", "flash"): "gemini-2.5-flash",
    ("gemini", "pro"): "gemini-2.5-pro",
}


def load_image_bytes(path: Path) -> bytes:
    """이미지 로드 → bytes"""
    img = Image.open(path)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def load_prompt(prompt_name: str) -> str:
    """추출용 프롬프트 로드"""
    prompt_path = PROMPTS_DIR / f"{prompt_name}.txt"
    if not prompt_path.exists():
        raise FileNotFoundError(f"프롬프트 없음: {prompt_path}")
    return prompt_path.read_text(encoding="utf-8").strip()


def find_generated_images(raw_dir: Path, ticker: str) -> list[Path]:
    """특정 티커의 생성된 이미지 목록 (최신순)"""
    images = sorted(raw_dir.glob(f"{ticker}_*.png"), reverse=True)
    return images


def parse_csv_response(text: str) -> list[dict]:
    """LLM 응답 텍스트에서 CSV 파싱"""
    # 마크다운 코드블록 제거
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        lines = [l for l in lines if not l.strip().startswith("```")]
        text = "\n".join(lines)

    rows = []
    reader = csv.DictReader(io.StringIO(text.strip()))
    for row in reader:
        try:
            rows.append({
                "candle_number": int(row["candle_number"]),
                "open": float(row["open"]),
                "high": float(row["high"]),
                "low": float(row["low"]),
                "close": float(row["close"]),
            })
        except (ValueError, KeyError) as e:
            print(f"    파싱 실패 row: {row} ({e})")
            continue
    return rows


def extract_single(client, model_id: str, image_bytes: bytes,
                   prompt_text: str, ticker: str) -> str | None:
    """단일 이미지에서 OHLC 값 추출"""
    contents = [
        types.Part.from_bytes(data=image_bytes, mime_type="image/png"),
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
                print(f"  [{ticker}] 추출 성공 (attempt {attempt})")
                return response.text

            print(f"  [{ticker}] 응답에 텍스트 없음 (attempt {attempt}/{MAX_RETRIES})")
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
    parser = argparse.ArgumentParser(description="Extract OHLC values from generated chart images")
    parser.add_argument("--model", default="gemini", choices=["gemini"])
    parser.add_argument("--variant", default="flash", choices=["flash", "pro"])
    parser.add_argument("--prompt", default="test", help="생성에 사용한 프롬프트 이름 (output 폴더 매칭)")
    parser.add_argument("--extract-prompt", default="extract", help="추출용 프롬프트 이름")
    parser.add_argument("--ticker", default=None, help="특정 티커만 실행")
    args = parser.parse_args()

    # 생성된 이미지 폴더
    raw_dir = OUTPUT_DIR / args.model / args.variant / args.prompt / "raw"
    if not raw_dir.exists():
        print(f"생성 이미지 폴더 없음: {raw_dir}")
        sys.exit(1)

    # 추출 결과 저장 폴더
    extract_dir = OUTPUT_DIR / args.model / args.variant / args.prompt / "extracted"
    extract_dir.mkdir(parents=True, exist_ok=True)

    # 모델 설정
    model_id = MODEL_MAP.get((args.model, args.variant))
    if not model_id:
        print(f"지원하지 않는 모델: {args.model}/{args.variant}")
        sys.exit(1)

    # 프롬프트
    prompt_text = load_prompt(args.extract_prompt)
    print(f"모델: {model_id}")
    print(f"추출 프롬프트: {args.extract_prompt}")
    print(f"생성 이미지: {raw_dir}")
    print(f"출력: {extract_dir}\n")

    # Gemini 클라이언트
    if not GEMINI_API_KEY:
        print("GEMINI_API_KEY 환경변수를 설정해주세요.")
        sys.exit(1)
    client = genai.Client(api_key=GEMINI_API_KEY)

    # 진행 상황
    progress_path = extract_dir / "progress.json"
    if progress_path.exists():
        progress = json.loads(progress_path.read_text())
    else:
        progress = {"completed": [], "failed": []}

    # 티커 목록 (생성된 이미지에서 추출)
    if args.ticker:
        tickers = [args.ticker]
    else:
        all_files = sorted(raw_dir.glob("*.png"))
        tickers = sorted(set(f.stem.rsplit("_", 1)[0] for f in all_files))

    print(f"총 {len(tickers)}개 티커 | 완료: {len(progress['completed'])}개\n")

    for i, ticker in enumerate(tickers):
        if ticker in progress["completed"]:
            print(f"[{i+1}/{len(tickers)}] {ticker} - 이미 완료, 스킵")
            continue

        print(f"[{i+1}/{len(tickers)}] {ticker} 값 추출 중...")

        # 가장 최신 생성 이미지
        images = find_generated_images(raw_dir, ticker)
        if not images:
            print(f"  생성 이미지 없음: {ticker}")
            progress["failed"].append(ticker)
            progress_path.write_text(json.dumps(progress, indent=2))
            continue

        image_path = images[0]  # 최신
        print(f"  이미지: {image_path.name}")
        image_bytes = load_image_bytes(image_path)

        # API 호출 → 텍스트 추출
        response_text = extract_single(client, model_id, image_bytes, prompt_text, ticker)

        if response_text:
            # Raw 응답 저장
            raw_txt_path = extract_dir / f"{ticker}_raw.txt"
            raw_txt_path.write_text(response_text, encoding="utf-8")

            # CSV 파싱 & 저장
            rows = parse_csv_response(response_text)
            if rows:
                csv_path = extract_dir / f"{ticker}.csv"
                with open(csv_path, "w", newline="") as f:
                    writer = csv.DictWriter(f, fieldnames=["candle_number", "open", "high", "low", "close"])
                    writer.writeheader()
                    writer.writerows(rows)
                print(f"  저장: {csv_path.name} ({len(rows)} candles)")

                progress["completed"].append(ticker)
            else:
                print(f"  [{ticker}] CSV 파싱 실패")
                progress["failed"].append(ticker)
        else:
            print(f"  [{ticker}] 추출 실패!")
            progress["failed"].append(ticker)

        progress_path.write_text(json.dumps(progress, indent=2))

        if i < len(tickers) - 1:
            time.sleep(DELAY_BETWEEN_CALLS)

    # 완료 요약
    print(f"\n완료: {len(progress['completed'])}/{len(tickers)}")
    if progress["failed"]:
        print(f"실패: {progress['failed']}")


if __name__ == "__main__":
    main()
