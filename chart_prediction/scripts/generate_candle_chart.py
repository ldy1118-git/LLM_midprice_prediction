"""
트레이딩뷰 스타일 캔들차트 생성기
- 6개월 전체 차트 (ground truth)
- 앞 3개월만 보이는 차트 (LLM에게 제공할 차트)
"""
import math
import pandas as pd
import numpy as np
import mplfinance as mpf
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import os

# ── 설정 ─────────────────────────────────────────────────────────
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_PATH = os.path.join(SCRIPT_DIR, "..", "..", "data", "stock_panel_data.parquet")
BASE_DIR = os.path.join(SCRIPT_DIR, "..")
INPUT_DIR = os.path.join(BASE_DIR, "data", "input")          # blank_3m 차트
LABEL_DIR = os.path.join(BASE_DIR, "data", "label", "full_charts")  # full_6m 차트
os.makedirs(INPUT_DIR, exist_ok=True)
os.makedirs(LABEL_DIR, exist_ok=True)

# 20개 대장주 (왼쪽 6m 히스토리 + 오른쪽 3m 예측, 랜덤 구간)
PAIRS = [
    {"ticker": "AAPL",  "start": "2022-08-13", "split": "2023-02-13", "end": "2023-05-13", "cat": "major"},
    {"ticker": "MSFT",  "start": "2023-12-11", "split": "2024-06-11", "end": "2024-09-11", "cat": "major"},
    {"ticker": "AMZN",  "start": "2013-06-03", "split": "2013-12-03", "end": "2014-03-03", "cat": "major"},
    {"ticker": "TSLA",  "start": "2015-08-22", "split": "2016-02-22", "end": "2016-05-22", "cat": "major"},
    {"ticker": "NVDA",  "start": "2014-06-30", "split": "2014-12-30", "end": "2015-03-30", "cat": "major"},
    {"ticker": "META",  "start": "2016-09-28", "split": "2017-03-28", "end": "2017-06-28", "cat": "major"},
    {"ticker": "GOOGL", "start": "2022-04-14", "split": "2022-10-14", "end": "2023-01-14", "cat": "major"},
    {"ticker": "NFLX",  "start": "2016-07-05", "split": "2017-01-05", "end": "2017-04-05", "cat": "major"},
    {"ticker": "AMD",   "start": "2018-08-15", "split": "2019-02-15", "end": "2019-05-15", "cat": "major"},
    {"ticker": "AVGO",  "start": "2011-11-09", "split": "2012-05-09", "end": "2012-08-09", "cat": "major"},
    {"ticker": "PLTR",  "start": "2021-08-02", "split": "2022-02-02", "end": "2022-05-02", "cat": "major"},
    {"ticker": "ASML",  "start": "2011-04-24", "split": "2011-10-24", "end": "2012-01-24", "cat": "major"},
    {"ticker": "CSCO",  "start": "2015-11-24", "split": "2016-05-24", "end": "2016-08-24", "cat": "major"},
    {"ticker": "ADBE",  "start": "2018-06-27", "split": "2018-12-27", "end": "2019-03-27", "cat": "major"},
    {"ticker": "QCOM",  "start": "2023-09-12", "split": "2024-03-12", "end": "2024-06-12", "cat": "major"},
    {"ticker": "TXN",   "start": "2022-08-08", "split": "2023-02-08", "end": "2023-05-08", "cat": "major"},
    {"ticker": "INTU",  "start": "2021-08-07", "split": "2022-02-07", "end": "2022-05-07", "cat": "major"},
    {"ticker": "AMAT",  "start": "2010-07-07", "split": "2011-01-07", "end": "2011-04-07", "cat": "major"},
    {"ticker": "INTC",  "start": "2016-09-15", "split": "2017-03-15", "end": "2017-06-15", "cat": "major"},
    {"ticker": "PANW",  "start": "2015-08-10", "split": "2016-02-10", "end": "2016-05-10", "cat": "major"},
]


def load_data():
    """stock_panel_data에서 OHLCV 로드"""
    df = pd.read_parquet(DATA_PATH, columns=["ticker", "date", "open", "high", "low", "close", "volume"])
    df["date"] = pd.to_datetime(df["date"])
    return df


def get_ohlcv(panel: pd.DataFrame, ticker: str, start: str, end: str) -> pd.DataFrame:
    """특정 티커, 기간의 OHLCV 데이터를 mplfinance 형식으로 반환"""
    mask = (panel["ticker"] == ticker) & (panel["date"] >= start) & (panel["date"] <= end)
    df = panel[mask].copy().sort_values("date")
    df.set_index("date", inplace=True)
    df.index.name = "Date"
    # mplfinance 컬럼명 맞추기
    df.rename(columns={
        "open": "Open", "high": "High", "low": "Low", "close": "Close", "volume": "Volume"
    }, inplace=True)
    return df[["Open", "High", "Low", "Close", "Volume"]]


# ── 트레이딩뷰 스타일 정의 ─────────────────────────────────────
tv_style = mpf.make_mpf_style(
    base_mpf_style="charles",
    marketcolors=mpf.make_marketcolors(
        up="#26a69a",       # 초록 - 상승 (미국장 컨벤션)
        down="#ef5350",     # 빨강 - 하락
        edge="inherit",
        wick="inherit",
        volume={"up": "#90caf9", "down": "#f5a0a0"},  # 볼륨 연한 색
    ),
    facecolor="white",
    edgecolor="white",
    figcolor="white",
    gridstyle="-",
    gridcolor="#e0e0e0",
    y_on_right=True,
    rc={
        "font.size": 11,
        "axes.labelsize": 11,
        "xtick.labelsize": 10,
        "ytick.labelsize": 10,
    },
)


def generate_chart(ohlcv: pd.DataFrame, ticker: str, suffix: str, title: str = "",
                   ylim=None, end_close=None, end_ohlc=None):
    """캔들차트 이미지 생성 & 저장
    end_close: 차트 마지막 날짜의 종가 (빨간 점선 + 가격 라벨용)
    end_ohlc:  (open, high, low, close) 튜플 - 마지막 칸에 실제 정답 캔들 삽입
    """
    if len(ohlcv) == 0:
        print(f"  [SKIP] {ticker} - no data")
        return

    # 캔들 너비 설정 (트레이딩뷰처럼 넓게)
    candle_width = 0.7

    kwargs = dict(
        type="candle",
        style=tv_style,
        volume=False,
        ylabel="",
        figsize=(20, 9),
        tight_layout=True,
        returnfig=True,
        scale_padding={"left": 0.05, "top": 0.6, "right": 0.8, "bottom": 0.5},
        update_width_config=dict(
            candle_linewidth=1.0,
            candle_width=candle_width,
        ),
    )
    if ylim is not None:
        kwargs["ylim"] = ylim

    fig, axes = mpf.plot(ohlcv, **kwargs)

    ax = axes[0]

    # 타이틀 추가 (트레이딩뷰처럼 좌상단)
    ax.set_title(title, loc="left", fontsize=12, fontweight="bold", pad=10)

    # ── X축: 트레이딩뷰 스타일 (월 이름 굵게 + 중간 날짜) ──
    dates = ohlcv.index
    tick_positions = []
    tick_labels = []
    month_names = {
        1: "Jan", 2: "Feb", 3: "Mar", 4: "Apr", 5: "May", 6: "Jun",
        7: "Jul", 8: "Aug", 9: "Sep", 10: "Oct", 11: "Nov", 12: "Dec",
    }
    prev_month = None
    for i, d in enumerate(dates):
        if prev_month is not None and d.month != prev_month:
            # 월 경계: 굵은 월 이름
            label = month_names[d.month]
            if d.month == 1:
                label = f"{d.year}"
            tick_positions.append(i)
            tick_labels.append((label, True))  # True = bold
        elif d.day in (5, 6, 7) or d.day in (11, 12, 13) or d.day in (17, 18, 19) or d.day in (23, 24, 25):
            # 주 단위 날짜: 해당 주에서 첫 거래일만 표시
            is_first_in_week = True
            for j in range(max(0, i - 2), i):
                dj = dates[j]
                if dj.month == d.month and abs(dj.day - d.day) <= 2 and (dj.day, True) != (d.day, True):
                    # 같은 주 범위에 이미 라벨이 있으면 스킵
                    if any(tp == j for tp in tick_positions):
                        is_first_in_week = False
                        break
            if is_first_in_week:
                tick_positions.append(i)
                tick_labels.append((str(d.day), False))  # False = normal
        prev_month = d.month

    # x축 적용
    ax.set_xticks(tick_positions)
    labels_obj = ax.set_xticklabels([t[0] for t in tick_labels], fontsize=10)
    for lbl, (_, is_bold) in zip(labels_obj, tick_labels):
        if is_bold:
            lbl.set_fontweight("bold")
            lbl.set_fontsize(11)

    # ── Y축: 트레이딩뷰처럼 ~17틱 목표, nice number 간격 ──
    price_lo, price_hi = ax.get_ylim()
    price_range = price_hi - price_lo
    nice_steps = [0.01, 0.02, 0.05, 0.10, 0.20, 0.25, 0.50,
                  1, 2, 4, 5, 10, 20, 25, 50, 100, 200, 500]
    target_ticks = 17
    raw_step = price_range / target_ticks
    step = nice_steps[0]
    for s in nice_steps:
        if s >= raw_step:
            step = s
            break
    tick_lo = math.floor(price_lo / step) * step
    tick_hi = math.ceil(price_hi / step) * step + step
    yticks = np.arange(tick_lo, tick_hi, step)
    ax.set_yticks(yticks)
    # 소수점 자릿수 자동 결정
    if step >= 1:
        fmt = "%.2f"
    else:
        decimals = max(2, len(str(step).rstrip('0').split('.')[-1]))
        fmt = f"%.{decimals}f"
    ax.yaxis.set_major_formatter(mticker.FormatStrFormatter(fmt))

    # 예측 영역 표시: 왼쪽 그리드만 수동으로 + 오른쪽은 거래일 세로선 + 타겟
    if end_close is not None:
        from matplotlib.patches import Rectangle, FancyBboxPatch

        last_x = len(ohlcv) - 1  # mplfinance x축은 0-indexed 정수
        # NaN 시작점 찾기 (split point)
        valid_mask = ohlcv['Close'].notna()
        split_x = valid_mask.sum() - 1  # 마지막 유효 캔들 위치

        y_lo, y_hi = ax.get_ylim()
        x_split_boundary = split_x + 0.5

        # ── 0) 기본 그리드 끄고 왼쪽(히스토리)에만 수동 그리드 ──
        ax.xaxis.grid(False)
        ax.yaxis.grid(False)
        # 왼쪽 가로선 (y-tick마다)
        for ytick in yticks:
            if y_lo <= ytick <= y_hi:
                ax.plot(
                    [-0.5, x_split_boundary], [ytick, ytick],
                    color="#e0e0e0", linewidth=0.5, zorder=0,
                    solid_capstyle="butt",
                )
        # 왼쪽 세로선 (x-tick 위치 중 split 이전만)
        for xpos in tick_positions:
            if xpos <= split_x:
                ax.plot(
                    [xpos, xpos], [y_lo, y_hi],
                    color="#e0e0e0", linewidth=0.5, zorder=0,
                    solid_capstyle="butt",
                )

        # ── 1) 예측 영역: 각 거래일 위치(정수 좌표)에 세로선 ──
        #       → 예측 캔들/정답 캔들이 이 선에 꽂히도록
        #       (Gemini regeneration에서도 선이 유지되도록 진하고 굵게)
        n_pred = last_x - split_x
        for i in range(1, n_pred + 1):
            ax.axvline(
                x=split_x + i,
                color="#888888", linewidth=1.0, zorder=1, alpha=1.0,
            )

        # ── 2) 목표 가격 빨간 수평 점선 (split → 차트 끝) ──
        ax.plot([split_x, last_x], [end_close, end_close],
                color="#ef5350", linewidth=1.2, linestyle="--", alpha=0.7, zorder=4)

        # ── 3) 마지막 칸에 실제 OHLC 정답 캔들 삽입 ──
        if end_ohlc is not None:
            e_open, e_high, e_low, e_close = end_ohlc
            is_up = e_close >= e_open
            body_color = "#26a69a" if is_up else "#ef5350"  # 초록↑/빨강↓
            # wick (심지)
            ax.plot([last_x, last_x], [e_low, e_high],
                    color=body_color, linewidth=1.0, zorder=5)
            # body (실제 OHLC 박스)
            body_lo = min(e_open, e_close)
            body_hi = max(e_open, e_close)
            body_h = max(body_hi - body_lo, (y_hi - y_lo) * 0.001)  # doji 최소 두께 보정
            ax.add_patch(Rectangle(
                (last_x - candle_width / 2, body_lo),
                candle_width, body_h,
                linewidth=1.0, edgecolor=body_color, facecolor=body_color,
                zorder=5,
            ))

        # 가격 라벨
        ax.annotate(
            f"${end_close:.2f}",
            xy=(last_x, end_close),
            xytext=(-10, 12), textcoords="offset points",
            fontsize=10, fontweight="bold", color="#ef5350",
            ha="right",
        )

    fname = f"{ticker}_{suffix}.png"
    out_dir = INPUT_DIR if "blank" in suffix else LABEL_DIR
    fpath = os.path.join(out_dir, fname)
    fig.savefig(fpath, dpi=150, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return fpath


def main():
    print("데이터 로딩 중...")
    panel = load_data()
    print(f"로딩 완료: {len(panel)} rows\n")

    label_rows = []          # actual_midprices.csv용 (요약)
    prediction_ohlcv = []    # 예측 기간 일별 OHLCV (정답 라벨)

    for p in PAIRS:
        ticker = p["ticker"]
        cat_label = "대장주" if p["cat"] == "major" else "랜덤"
        print(f"[{cat_label}] {ticker}")

        # 전체 6개월 데이터 로드
        full_data = get_ohlcv(panel, ticker, p["start"], p["end"])
        split_dt = pd.to_datetime(p["split"])

        # 예측 기간(split 다음날 ~ end) 일별 OHLCV → 정답 라벨
        pred_period = full_data.loc[full_data.index > split_dt].copy()
        for date_idx, row in pred_period.iterrows():
            prediction_ohlcv.append({
                "ticker": ticker,
                "date": date_idx.strftime("%Y-%m-%d"),
                "open": round(row["Open"], 2),
                "high": round(row["High"], 2),
                "low": round(row["Low"], 2),
                "close": round(row["Close"], 2),
                "volume": int(row["Volume"]),
            })
        print(f"  정답 라벨: {len(pred_period)} trading days ({p['split']} ~ {p['end']})")

        # 뒤 3개월 비워놓은 차트 (LLM에게 제공)
        blank_data = full_data.copy()
        blank_data.loc[blank_data.index > split_dt, ["Open", "High", "Low", "Close", "Volume"]] = float("nan")
        visible_part = blank_data.loc[blank_data.index <= split_dt]
        actual_end_close = full_data["Close"].iloc[-1]
        actual_end_ohlc = (
            float(full_data["Open"].iloc[-1]),
            float(full_data["High"].iloc[-1]),
            float(full_data["Low"].iloc[-1]),
            float(full_data["Close"].iloc[-1]),
        )
        # ylim은 마지막 날의 High/Low도 반영
        ylim_lo = min(visible_part["Low"].min(), actual_end_ohlc[2]) * 0.97
        ylim_hi = max(visible_part["High"].max(), actual_end_ohlc[1]) * 1.03
        title_blank = f"{ticker} · NASDAQ · 1D"
        path_blank = generate_chart(
            blank_data, ticker, "blank_3m", title_blank,
            ylim=(ylim_lo, ylim_hi), end_close=actual_end_close,
            end_ohlc=actual_end_ohlc,
        )
        n_visible = visible_part.dropna().shape[0]
        print(f"  입력 차트: {path_blank} ({n_visible} candles + blank)")

        # 요약 정보 수집
        last_visible_close = visible_part["Close"].dropna().iloc[-1]
        label_rows.append({
            "ticker": ticker,
            "category": p["cat"],
            "start": p["start"],
            "split": p["split"],
            "end": p["end"],
            "last_visible_close": round(last_visible_close, 2),
            "actual_end_close": round(actual_end_close, 2),
            "prediction_days": len(pred_period),
        })

    # 1) 요약 CSV 저장
    label_csv = os.path.join(BASE_DIR, "data", "label", "actual_midprices.csv")
    pd.DataFrame(label_rows).to_csv(label_csv, index=False)
    print(f"\n요약 CSV: {label_csv}")

    # 2) 예측 기간 일별 OHLCV 정답 라벨 저장
    ohlcv_csv = os.path.join(BASE_DIR, "data", "label", "prediction_ohlcv.csv")
    pd.DataFrame(prediction_ohlcv).to_csv(ohlcv_csv, index=False)
    print(f"정답 OHLCV: {ohlcv_csv} ({len(prediction_ohlcv)} rows)")
    print(f"입력 차트:  {INPUT_DIR}")


if __name__ == "__main__":
    main()
