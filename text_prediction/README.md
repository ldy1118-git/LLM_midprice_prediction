# Experiment 1 — Text (OHLC) Mid-price Interpolation

Paper 실험 1의 공식 파이프라인. 생성형 AI 3종(ChatGPT 5.4, Gemini 3.1 Pro, Claude opus 4.7)에게
마스킹된 OHLC 수치만 주고 중간 62일의 OHLC를 CSV로 생성하도록 한다.

## 실험 설계

- **종목**: 나스닥 대장주 20개 (chart_prediction과 동일)
  `AAPL, MSFT, AMZN, TSLA, NVDA, META, GOOGL, NFLX, AMD, AVGO, PLTR, ASML, CSCO, ADBE, QCOM, TXN, INTU, AMAT, INTC, PANW`
- **윈도우**: 종목별 랜덤 126 거래일 (전체 기간 2016-01-04 ~ 2025-01-30 이내, seed=42)
- **입력**: D1~D63 + D126 (64행) OHLC
- **예측 대상**: D64~D125 (62행) OHLC
- **마스킹**: 티커 → A~T, 날짜 → D1~D126 (매핑은 `data/windows.csv`에 보관)
- **반복**: 각 데이터셋(20개) × 5회 = 모델당 100회 예측

## 디렉토리 구조

```
text_prediction/
├── scripts/
│   ├── sample_and_build.py       # 샘플링 + 마스킹 + 입력/라벨 생성
│   ├── build_batched_prompts.py  # 배치=2 프롬프트 생성
│   ├── split_batched_response.py # LLM 응답 파싱
│   └── quick_metrics.py          # 중간 지표 확인
├── data/
│   ├── windows.csv           # (code, ticker, 실제 날짜 매핑)
│   ├── input/{CODE}.csv      # D1~D63 + D126 OHLC (64행)
│   └── label/{CODE}.csv      # D64~D125 OHLC (62행, 정답)
├── prompts/batched/batch{N}.txt  # 배치=2 프롬프트 (유일한 제출 방식)
├── output/{model}/run{k}/{CODE}.csv   # 모델×반복별 예측 결과
└── evaluation/
    └── evaluate.py           # 4개 MSE 지표 계산
```

## 사용법

### 1. 데이터셋 재생성 (이미 1회 실행됨, seed=42 고정)

```bash
python3 scripts/sample_and_build.py
```

### 2. 모델 예측 수집

**배치 2 방식 (총 150회 제출 = 10 배치 × 5 run × 3 모델)**

```bash
python3 scripts/build_batched_prompts.py   # prompts/batched/batch1~10.txt 생성
```

각 모델(3종)×각 run(5회)에 대해 `batch1.txt`~`batch10.txt`를 붙여넣고 응답 전체를
`output/{model}/run{k}/_raw/batch{N}.txt`로 저장. 그 뒤 파싱:

참고: 과거 batch=4 실험은 Gemini 3.1 Pro가 2번째 종목부터 D126 엔드포인트를 무시하는
문제가 있어 폐기되었고, `output/_diagnostic/batch4_test/`에 아카이브됨.

```bash
python3 scripts/split_batched_response.py --run-dir output/chatgpt5.4/run1
```

응답에서 `=== CODE: X ===` ... `=== END ===` 구분자로 2개 CSV가 자동 분리되어
`output/chatgpt5.4/run1/{A,B}.csv`로 저장된다.

최종 CSV는 헤더 `day,open,high,low,close` + 62행(D64..D125) 형식이어야 한다.

### 3. 평가

```bash
python3 evaluation/evaluate.py \
    output/chatgpt5.4 \
    output/gemini3.1pro \
    output/claude-opus-4.7
```

결과:
- `evaluation/results/per_run.csv` — 100회 × 모델별 상세
- `evaluation/results/summary.csv` — 모델별 평균 ± 표준편차

## 지표 정의

| 지표 | 정의 |
|------|------|
| `close_mse` | MSE(정답 종가, 예측 종가) |
| `std_close_mse` | `close_mse` ÷ MSE(정답 종가, D64·D125 선형보간) |
| `vol_mse` | MSE(정답 고저차, 예측 고저차) |
| `std_vol_mse` | `vol_mse` ÷ MSE(정답 고저차, D64·D125 선형보간) |

표준화 지표 < 1 → 단순 선형보간보다 우수.

## 샘플링된 윈도우 (seed=42)

`data/windows.csv` 참고. 기간은 2016-02-10 ~ 2023-10-23 범위에 분포.

## 작업 분담 (run별)

| run | 담당자 | 상태 |
|-----|--------|------|
| run1 | 대윤 | ✅ 완료 |
| run2 | 대윤 | ⏳ 진행중 |
| run3 | 대윤 | 대기 |
| run4 | 진우 | 대기 |
| run5 | 진우 | 대기 |

**충돌 방지 규칙**
- 각자 자기 run 폴더(`output/{model}/run{N}/`)만 수정
- `evaluation/results/`는 **커밋하지 않음** (언제든 로컬에서 재생성)
- 스크립트(`scripts/`, `evaluation/evaluate.py`, `evaluation/quick_metrics.py`) 변경은 사전 합의 후
- `data/input/`, `data/label/`, `prompts/`는 seed=42 재생성시 동일한 결과 → 수정 금지

**각자 작업 끝나면**: `git pull` → 배치 수집 → `git add output/{model}/runX/` → `git commit` → `git push`
