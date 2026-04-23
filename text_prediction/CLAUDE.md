# text_prediction 작업 컨텍스트 (Claude 에이전트용)

이 문서는 실험 1(수치 기반 주가 보간 예측)을 **대윤·진우 둘이 나눠서** 진행하고 있는
상황에서, 진우 쪽 Claude 에이전트가 이어서 작업할 때 필요한 배경을 전수하기 위한 것.

## 한눈에 보는 실험

- **목표**: LLM 3종(ChatGPT 5.4 / Gemini 3.1 Pro / Claude opus 4.7)이 주가 보간 예측을
  얼마나 잘 하는지 비교. 논문 한 편을 위한 벤치마크.
- **데이터셋**: 나스닥 대장주 20개(A~T로 마스킹) × 각 126 거래일 윈도우 × 5회 반복
  = 총 300개 응답 수집 필요.
- **입력**: D1~D63 + D126의 OHLC (64행)
- **출력**: D64~D125의 OHLC (62행, CSV)
- **지표**: 종가 MSE, 표준화 종가 MSE, 일일변동성 MSE, 표준화 일일변동성 MSE
- **배치 사이즈**: 2 (`prompts/batched/batch{1..10}.txt`)

## 작업 분담

| run | 담당자 | 상태 (2026-04-23 기준) |
|-----|--------|------|
| run1 | 대윤 | ✅ 완료 (20/20 × 3 모델) |
| run2 | 대윤 | ⏳ 진행중 (batch 1~2 완료) |
| run3 | 대윤 | 대기 |
| **run4** | **진우** | 대기 |
| **run5** | **진우** | 대기 |

진우 쪽 Claude가 할 일: **run4, run5** 를 채우는 것.

## 수집 워크플로우 (매 배치 반복)

1. **새 채팅 세션** 열기 (매 배치마다, 각 모델별로). 이게 중요합니다 — 같은 세션 안에서
   이어 보내면 앞 배치 응답이 context로 남아 독립성이 깨짐. 우리는 모든 (batch × run ×
   model) 조합을 독립 세션으로 처리하고 있음.
2. `prompts/batched/batch{N}.txt` 내용 복사 → 모델에 붙여넣기
3. 응답 텍스트 그대로를 `output/{model}/run{K}/_raw/batch{N}.txt` 로 저장
4. 파싱: `python3 scripts/split_batched_response.py --run-dir output/{model}/run{K}`
   또는 단일 파일: `python3 scripts/split_batched_response.py output/{model}/run{K}/_raw/batch{N}.txt`
5. 중간 확인: `python3 scripts/quick_metrics.py --all --run run{K}`

### 모델명 (폴더명 고정):
- `claude-opus-4.7`
- `gemini3.1pro`
- `chatgpt5.4`

### 수집 순서 관례:
매 배치마다 **Claude → Gemini → ChatGPT** 순서로 제출. 이유는 Claude가 가장 빠름.

### 모델별 모드 설정 (방법론 섹션에 명시할 것):
- ChatGPT 5.4: **Thinking-Standard** 모드 (Auto나 Instant, Extended 아님)
- Gemini 3.1 Pro: 기본
- Claude opus 4.7: 기본

## 중요한 이슈들 (이미 발견·해결됨)

### 1. 배치 사이즈 = 2 (원래 4였다가 2로 바꿈)
배치 4에서 Gemini가 **2번째 종목부터 D126 엔드포인트를 무시**하는 현상 확인.
배치 2로 내리니 세 모델 모두 엔드포인트 준수. 폐기된 배치 4 실험은
`output/_diagnostic/batch4_test/`에 보관.

### 2. 프롬프트에 CRITICAL ENDPOINT CONSTRAINT 포함
주어진 D126과 D125 예측값 사이에 비현실적 갭(>5%)이 있으면 안 된다는 경고를 명시.
현재 `prompts/batched/batch{N}.txt` 모두 이 경고 포함 (`scripts/build_batched_prompts.py`
에서 자동 생성).

### 3. 응답 뒤에 D126 행을 덧붙이는 모델이 있음 (Claude가 가끔)
63행이 아니라 63+1=64행으로 D126까지 에코해서 돌려주는 경우. 파서가 자동으로
D126 행을 버리게 업데이트되어 있음 (`scripts/split_batched_response.py`).

### 4. 응답 잘못 붙이기 실수 방지
- 모델별 소수점 자릿수 패턴: **ChatGPT/Claude는 4자리**, **Gemini는 2자리** 경향
- 응답 받을 때 스타일이 모델명과 맞는지 즉시 확인
- 이미 저장한 다른 모델/배치 값과 중복되는지 체크 (우리 발견 사례: Gemini 응답을
  ChatGPT 슬롯에 두 번 연속 잘못 저장한 케이스)

## 주요 파일 위치

```
text_prediction/
├── scripts/
│   ├── sample_and_build.py       # 데이터셋 재생성 (seed=42, 이미 1회 실행됨)
│   ├── build_batched_prompts.py  # batched/batch{1..10}.txt 재생성
│   ├── split_batched_response.py # raw 응답 → {CODE}.csv
│   └── quick_metrics.py          # 진행 중간 지표 확인
├── data/
│   ├── windows.csv               # (code, ticker, 실제 날짜) 매핑 — 민감
│   ├── input/{A..T}.csv          # 입력 OHLC (64행)
│   └── label/{A..T}.csv          # 정답 OHLC (62행)
├── prompts/
│   └── batched/batch{1..10}.txt  # 배치=2 프롬프트 (유일한 제출 방식)
├── output/
│   ├── claude-opus-4.7/run{1..5}/{A..T}.csv + _raw/batch{1..10}.txt
│   ├── chatgpt5.4/run{1..5}/...
│   ├── gemini3.1pro/run{1..5}/...
│   └── _diagnostic/              # 폐기된 batch=4 테스트 기록 (남겨둠)
├── evaluation/
│   ├── evaluate.py               # 최종 집계 (4개 MSE 지표)
│   └── results/                  # .gitignore — 로컬에서만 재생성
├── README.md                     # 사람용 개요
└── CLAUDE.md                     # 이 문서
```

## 배치별 코드 매핑

| batch | codes | | batch | codes |
|---|---|---|---|---|
| 1 | A, B | | 6 | K, L |
| 2 | C, D | | 7 | M, N |
| 3 | E, F | | 8 | O, P |
| 4 | G, H | | 9 | Q, R |
| 5 | I, J | | 10 | S, T |

## 충돌 방지

- `output/{model}/run{자기담당}/` 외에는 건드리지 말 것
- `evaluation/results/`는 `.gitignore`에 들어있음 — 커밋 안 함
- `scripts/`, `data/`, `prompts/` 변경은 사전 합의 필요
- 커밋하기 전 `git pull --rebase` 하고 충돌 여부 확인

## 지금 풀고 있는 문제의 구조

- 매 응답 받을 때마다 파싱해서 중간 지표 찍어봄 (안심용)
- 최종 평가는 전부 수집 후 `python3 evaluation/evaluate.py output/chatgpt5.4 output/claude-opus-4.7 output/gemini3.1pro` 1회로 n=100 통계 확정
- 논문 draft는 `/project/ahnailab/ldy1118/AIETF/LLM_midprice_prediction/paper/` 에 있음
  (교수님 초안 + 심사용 docx 2개 + build_paper.py)

## 자주 하는 질문 미리 답

- **Q: 모델에게 배치 2개가 독립적이라고 이해시키나?**
  A: 프롬프트에 "Treat each prediction as its own separate task. The 2 stocks
  are UNRELATED" 명시. 지금까지 관찰로는 세 모델 모두 잘 지킴 (각 코드별 가격 스케일
  /변동성/패턴이 독립적으로 다르게 나옴).
- **Q: 응답 포맷 실패하면?** A: 파서가 `expected 62 rows, got X` 에러 냄. 원본
  `_raw/batch{N}.txt` 그대로 두고, 실패한 배치만 재제출.
- **Q: 진행 중 모델이 답변 거절/이상하게 짧게 답변하면?** A: 새 세션 열어 재시도.
  반복해서 실패하면 해당 (run, batch)를 스킵 메모하고 평가에서 제외 가능. 하지만
  지금까지 한 번도 이런 일 없었음.
