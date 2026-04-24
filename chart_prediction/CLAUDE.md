# chart_prediction 작업 컨텍스트 (Claude 에이전트용)

이 문서는 실험 2(이미지 기반 캔들차트 보간 예측)의 배경을 진우 쪽 Claude 에이전트가
이어서 파악할 수 있도록 정리한 것.

## 한눈에 보는 실험

- **목표**: LLM 3종(ChatGPT 5.4 / Gemini 3.1 Pro / Claude opus 4.7)이 캔들차트 이미지
  보간 예측을 얼마나 잘 하는지 비교. exp1과 동일한 (종목, 윈도우) 20쌍을 사용.
- **데이터셋**: A~T 마스킹 종목 20개 × 5회 반복 × 3 모델 = 300 이미지
- **입력**: D1~D63 캔들 + 파란 박스(D64~D125 빈 영역) + 라이트블루 가이드 62개 + D126 타깃 캔들·종가 라벨
- **출력**: 박스 안에 62개 캔들이 채워진 동일 차트 이미지
- **마스킹**: 티커명 제거 → 코드 letter(A~T), 캘린더 날짜 제거 → 인덱스(D1~D126)
- **반복 횟수**: 5 (text_prediction과 통일)

## 평가 단계 (논문 §2.4 기준)

- **1단계 (stage1)**: 모델이 이미지를 반환했는지 (yes=1)
- **2단계 (stage2)**: 반환된 이미지가 "사용 가능한 예측"인지 (yes=1)
  - 캔들 개수 50~63개 (목표 62, 약간의 오차 허용 / >62는 "초과" 실패)
  - 캔들 색이 섞여 있지 않음 ("겹침" 실패)
  - 박스 영역 손상 없음

자동 카운팅(`scripts/count_candles.py`)은 모델별 출력 해상도/색감 차이로 신뢰도 낮음.
**수동 라벨링이 사실상의 표준.** 자동 스크립트는 보조용으로만 사용.

## 현재 진행 상황 (2026-04-24)

| run | 담당 | 상태 |
|-----|------|------|
| run1 | 대윤 | 이미지 수집 완료 (3 모델 × 20). chatgpt5.4 라벨링 ✅ 완료, claude-opus-4.7 / gemini3.1pro 라벨링 진행 중 |
| **run2** | **대윤** | 진행 예정 |
| **run3** | **진우** | 진행 예정 |
| run4 | 미정 | 수요일 시험 이후 |
| run5 | 미정 | 수요일 시험 이후 |

**계획**: run1~3까지 라벨링 완료한 결과로 논문 초안 작성 → 시험 후 run4~5 추가 →
최종 제출 전 수치 업데이트. 교수님 승인 받을 예정.

진우 쪽 Claude가 할 일: **run3** 의 60장(3 모델 × 20 코드) 수집 + 라벨링.

### chatgpt5.4 run1 라벨 결과 참고치
- 1단계: 20/20 (100%)
- 2단계: 2/20 (10%) — D=62, K=63
- 실패 사유: 11건 "초과" (>62 캔들), 7건 "겹침" (색 섞임)

## 수집 워크플로우

매 (model, run, code) 조합당:
1. **새 채팅 세션** 열기 (모델별로 독립 세션)
2. `prompts/{model}.txt` 내용 복사 + `data/input/{CODE}.png` 이미지 첨부 → 모델에 제출
3. 응답 이미지를 `output/{model}/run{K}/{CODE}.png` 로 저장
4. 모든 코드 수집 완료 후 수동 라벨링 → `output/{model}/run{K}/labels.csv` 작성

### 모델명 (폴더명 고정 — text_prediction과 동일)
- `claude-opus-4.7`
- `gemini3.1pro`
- `chatgpt5.4`

### 모델별 모드 설정
- ChatGPT 5.4: **Thinking-Standard** (Auto / Instant / Extended 아님)
- Gemini 3.1 Pro: 기본
- Claude opus 4.7: 기본

### 수집 순서 관례
exp1과 동일: **Claude → Gemini → ChatGPT** (Claude가 가장 빠름)

## 모델별 프롬프트가 다른 이유

원래는 동일 프롬프트로 통일하려 했으나, 모델별 인터페이스 차이로 불가피하게 분기:
- **Claude**: 코드 실행으로 그릴 때 17번씩 반복 호출하며 점진 작업하는 경향 → "single
  code execution / do NOT iterate" 강제 문구 추가
- **Gemini**: 이미지를 처음부터 새로 렌더링하는 경향 → "edit the attached image, do
  NOT regenerate" 명시
- **ChatGPT**: 가끔 코드/ASCII로 응답 → "rendered raster image only" 명시

**과제 자체와 11개 제약 조건은 3개 프롬프트에서 동일.** 종목별 분기는 아님(모든 코드에
같은 프롬프트 사용). 논문 §2.4에 이 사실 명시 예정.

## 라벨 CSV 포맷

`output/{model}/run{K}/labels.csv`:
```csv
code,stage1,stage2,n_candles,fail_reason
A,1,0,,초과
D,1,1,62,
K,1,1,63,
```
- `stage1`, `stage2`: 0/1
- `n_candles`: 성공 시 실제 갯수, 실패 시 빈칸
- `fail_reason`: `초과` (>62), `겹침` (색 섞임), `부족` (<50), `박스손상` 등

## 주요 파일 위치

```
chart_prediction/
├── scripts/
│   ├── generate_charts.py    # text_prediction 데이터로 input/label 차트 재생성
│   └── count_candles.py      # 자동 캔들 카운팅 (보조용, 신뢰도 낮음)
├── data/
│   ├── windows.csv           # text_prediction과 동일 (code, ticker, 날짜)
│   ├── input/{A..T}.png      # 마스킹된 입력 차트 (D1~D126 인덱스, 티커 제거)
│   └── label/full_charts/{A..T}.png   # 정답 차트 (마스킹 그대로 + D64~D125 캔들 채워진 버전)
├── prompts/
│   ├── claude-opus-4.7.txt
│   ├── gemini3.1pro.txt
│   └── chatgpt5.4.txt
├── output/
│   ├── claude-opus-4.7/run{1..5}/{A..T}.png + labels.csv
│   ├── chatgpt5.4/run{1..5}/...
│   └── gemini3.1pro/run{1..5}/...
├── evaluation/
│   └── results/              # 집계 결과 (TBD)
└── CLAUDE.md                 # 이 문서
```

## 데이터 일관성

- `data/windows.csv`는 `text_prediction/data/windows.csv`와 **동일한 20쌍**.
  exp1/exp2가 같은 (종목, 윈도우)에서 비교 가능.
- `data/input/{CODE}.png`는 `text_prediction/data/input/{CODE}.csv`(D1~D63 + D126)
  로부터 `generate_charts.py`가 생성한 것. 정렬 순서·코드 letter 매핑 동일.

## 차트 사양 (generate_charts.py)

- 색: TradingView 팔레트
  - up candle: `#26a69a` (green)
  - down candle: `#ef5350` (red)
  - 박스 테두리: `#1976d2` (dark blue)
  - 가이드선: `#90caf9` (light blue, 62개)
- X축 틱: `D1, D20, D40, D60, D80, D100, D120, D126`
- 타이틀: 코드 letter만 (티커 노출 금지)
- D126 타깃 캔들 + 빨간 점선 + `$XX.XX` 종가 라벨

## 충돌 방지

- `output/{model}/run{자기담당}/` 외에는 건드리지 말 것
  - 진우는 `output/*/run3/`, 대윤은 `output/*/run2/`
- 라벨 기준은 사전 합의된 항목(초과/겹침/부족/박스손상)만 사용. 새 사유 추가 시 합의 후 진행
- `scripts/`, `data/`, `prompts/` 변경은 사전 합의 필요
- 커밋 전 `git pull --rebase` 하고 충돌 여부 확인
