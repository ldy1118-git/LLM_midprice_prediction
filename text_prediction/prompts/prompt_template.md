# Prompt Template for LLM Stock Price Path Prediction

## 실험 설계
- **기간**: 1년(252일), 2년(504일), 3년(756일), 4년(1008일), 5년(1260일)
- **피처**: A(close), B(OHLCV), C(OHLCV+기술지표), D(OHLCV+기술지표+매크로), E(전체)
- **종목**: 20개 (LightGBM v1 2024-07-01 기준 랭크 1,5,10,...,95)
- **예측 구간**: 2024-04-01 ~ 2024-07-01 (64거래일, 양 끝 고정, 중간 62일 예측)

---

## Prompt

```
You are a quantitative analyst specializing in stock price modeling.

I will provide you with:
1. A stock ticker
2. Historical trading data for the stock
3. The closing price on a start date (2024-04-01)
4. The closing price on an end date (2024-07-01), which is 63 trading days later

Your task is to predict the 62 intermediate daily closing prices between the start and end dates.

## Stock Information
- Ticker: {TICKER}
- Start Date: 2024-04-01, Close: ${START_CLOSE}
- End Date: 2024-07-01, Close: ${END_CLOSE}

## Historical Data
{HISTORICAL_DATA_CSV}

## Instructions
- Predict the closing price for each of the 62 trading days listed below.
- Use the historical data to understand this stock's typical price behavior, volatility patterns, and trend characteristics.
- The predicted path should realistically connect the start price to the end price.
- Consider the stock's historical daily movement range and volatility.

## Output Format
Return ONLY a CSV with exactly 62 rows, no additional text:
date,close
2024-04-02,{predicted}
2024-04-03,{predicted}
2024-04-04,{predicted}
2024-04-05,{predicted}
2024-04-08,{predicted}
2024-04-09,{predicted}
2024-04-10,{predicted}
2024-04-11,{predicted}
2024-04-12,{predicted}
2024-04-15,{predicted}
2024-04-16,{predicted}
2024-04-17,{predicted}
2024-04-18,{predicted}
2024-04-19,{predicted}
2024-04-22,{predicted}
2024-04-23,{predicted}
2024-04-24,{predicted}
2024-04-25,{predicted}
2024-04-26,{predicted}
2024-04-29,{predicted}
2024-04-30,{predicted}
2024-05-01,{predicted}
2024-05-02,{predicted}
2024-05-03,{predicted}
2024-05-06,{predicted}
2024-05-07,{predicted}
2024-05-08,{predicted}
2024-05-09,{predicted}
2024-05-10,{predicted}
2024-05-13,{predicted}
2024-05-14,{predicted}
2024-05-15,{predicted}
2024-05-16,{predicted}
2024-05-17,{predicted}
2024-05-20,{predicted}
2024-05-21,{predicted}
2024-05-22,{predicted}
2024-05-23,{predicted}
2024-05-24,{predicted}
2024-05-28,{predicted}
2024-05-29,{predicted}
2024-05-30,{predicted}
2024-05-31,{predicted}
2024-06-03,{predicted}
2024-06-04,{predicted}
2024-06-05,{predicted}
2024-06-06,{predicted}
2024-06-07,{predicted}
2024-06-10,{predicted}
2024-06-11,{predicted}
2024-06-12,{predicted}
2024-06-13,{predicted}
2024-06-14,{predicted}
2024-06-17,{predicted}
2024-06-18,{predicted}
2024-06-20,{predicted}
2024-06-21,{predicted}
2024-06-24,{predicted}
2024-06-25,{predicted}
2024-06-26,{predicted}
2024-06-27,{predicted}
2024-06-28,{predicted}
```

---

## Feature Sets

### A: close만
```
date,close
```

### B: OHLCV
```
date,open,high,low,close,volume
```

### C: OHLCV + 핵심 기술지표
```
date,open,high,low,close,volume,rsi_14,macd,macd_signal,macd_hist,atr_14,bb_upper,bb_middle,bb_lower,bb_width,bb_position
```

### D: OHLCV + 기술지표 + 매크로
```
date,open,high,low,close,volume,rsi_14,macd,macd_signal,macd_hist,atr_14,bb_upper,bb_middle,bb_lower,bb_width,bb_position,vix,fed_funds_rate,unemployment_rate,cpi,treasury_10y,treasury_2y,yield_curve,oil_price,usd_eur,high_yield_spread
```

### E: 전체 52컬럼
(stock_panel_data.csv의 모든 컬럼)
