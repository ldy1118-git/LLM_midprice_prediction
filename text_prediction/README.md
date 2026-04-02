# LLM Price Path Prediction

LLM에게 시작일 종가와 63거래일 후 종가를 제공하고, 중간 62일의 일별 종가 경로를 예측하게 하는 실험.

## 목적

기존 stock_prediction 프로젝트에서 63일 후 종가를 예측하고 있음. 이 예측 종가까지의 **중간 경로를 LLM으로 생성**하여 그래프로 시각화하면, 사용자에게 "이 종목이 어떤 흐름으로 예측 가격에 도달하는지"를 보여줄 수 있음.

## 실험 설계

### 데이터
- **기준일**: 2024-07-01 (LightGBM v1 예측 기준)
- **예측 구간**: 2024-04-01 ~ 2024-07-01 (64거래일, 양 끝 고정, 중간 62일 예측)
- **종목**: LightGBM v1이 2024-07-01에 예측한 상위 랭크 20종목

### 실험 변수

**과거 데이터 기간 (5가지)**
| 기간 | 거래일 수 |
|------|----------|
| 1년 | 252일 |
| 2년 | 504일 |
| 3년 | 756일 |
| 4년 | 1008일 |
| 5년 | 1260일 |

**피처 세트 (5가지)**
| 세트 | 내용 | 컬럼 수 |
|------|------|---------|
| A | close만 | 2 |
| B | OHLCV | 6 |
| C | OHLCV + 핵심 기술지표 (RSI, MACD, ATR, 볼린저밴드) | 16 |
| D | OHLCV + 기술지표 + 매크로 (VIX, 금리, 유가 등) | 26 |
| E | 전체 | 52 |

**LLM 모델**
- ChatGPT 5.4: thinking_expand / auto / instant

### 평가 지표
| 지표 | 설명 |
|------|------|
| MAE | 평균 절대 오차 |
| MAPE | 평균 절대 백분율 오차 |
| RMSE | 평균 제곱근 오차 |
| Pearson / Spearman | 경로 상관계수 |
| DTW | Dynamic Time Warping 거리 (형태 유사도) |
| Direction Accuracy | 일별 상승/하락 방향 일치율 |
| Volatility Ratio | 예측 변동성 / 실제 변동성 (1.0이 이상적) |
| vs Linear | 선형 보간 대비 MAE 비교 |
| vs Brownian Bridge | 브라운 브릿지 대비 MAE 비교 |

## 폴더 구조

```
LLM/
├── data/
│   ├── input/
│   │   └── historical_data.csv       # 20종목 과거 데이터 (52컬럼)
│   └── label/
│       └── actual_closes.csv         # 실제 62일 종가 (정답)
├── prompts/
│   ├── prompt_template.md            # 프롬프트 템플릿 설명
│   └── 1y/
│       ├── A.txt ~ E.txt             # 1년 × 피처셋별 완성 프롬프트
│       └── ...
├── output/                           # LLM 응답 원본
│   └── {model}/{mode}/{period}/{feature_set}
│       예: chatgpt5.4/thinking_expand/1y/A
├── evaluation/
│   ├── evaluate.py                   # 평가 스크립트
│   └── results/                      # 평가 결과 (CSV + 그래프)
│       ├── *_eval.csv                # 수치 결과
│       ├── *_summary.png             # 20종목 요약 그래프 (4x5)
│       └── *_plots/                  # 종목별 개별 그래프
└── README.md
```

## 사용법

### 1. 프롬프트 복사 -> 챗봇에 입력
```
prompts/1y/A.txt 내용을 챗봇에 붙여넣기
```

### 2. 응답 저장
```
output/{model}/{mode}/{period}/{feature_set} 에 저장
```

### 3. 평가 실행
```bash
cd evaluation
python evaluate.py ../output/chatgpt5.4/thinking_expand/1y/A
```
