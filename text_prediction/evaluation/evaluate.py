import pandas as pd
import numpy as np
import os
import sys
import re
from scipy.spatial.distance import euclidean
from dtaidistance import dtw
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

"""
LLM 주가 경로 예측 평가 스크립트

사용법:
    python evaluate.py <prediction_file> [--label <label_file>]

예시:
    python evaluate.py ../output/chatgpt5.4/thinking_expand/1y/A
"""

LABEL_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'label', 'actual_closes.csv')

TICKERS = ['ONDS', 'ABAT', 'CIFR', 'ENLV', 'CRNC', 'AMLX', 'EVGO', 'DHC', 'OPEN', 'ADV',
           'BGM', 'BLDP', 'PLUG', 'OCUL', 'ATPC', 'INTR', 'EDIT', 'HIMX', 'OPAL', 'BMEA']


def parse_prediction_file(filepath):
    """LLM 응답 파일을 파싱해서 {ticker: DataFrame} 형태로 반환"""
    with open(filepath, 'r') as f:
        content = f.read()

    predictions = {}
    # ### TICKER 패턴으로 분리
    sections = re.split(r'###\s+(\w+)\s*\n', content)
    # sections[0]은 첫 ### 이전 텍스트 (보통 빈 문자열)
    # sections[1] = ticker, sections[2] = data, sections[3] = ticker, ...

    for i in range(1, len(sections), 2):
        ticker = sections[i].strip()
        data_block = sections[i + 1].strip()

        # CSV 파싱
        lines = []
        for line in data_block.split('\n'):
            line = line.strip()
            if not line or line.startswith('date,close'):
                continue
            parts = line.split(',')
            if len(parts) == 2:
                try:
                    date = parts[0].strip()
                    close = float(parts[1].strip())
                    lines.append({'date': date, 'close': close})
                except ValueError:
                    continue

        if lines:
            df = pd.DataFrame(lines)
            df['date'] = pd.to_datetime(df['date'])
            predictions[ticker] = df.sort_values('date').reset_index(drop=True)

    return predictions


def load_labels(label_path):
    """라벨 파일 로드, 시작일/종료일 제외한 중간 62일만 반환"""
    df = pd.read_csv(label_path)
    df['date'] = pd.to_datetime(df['date'])

    labels = {}
    for ticker in TICKERS:
        tdf = df[df['ticker'] == ticker].sort_values('date').reset_index(drop=True)
        # 시작일(index 0)과 종료일(index -1) 제외
        labels[ticker] = tdf.iloc[1:-1].reset_index(drop=True)

    return labels


def linear_interpolation(start_close, end_close, n_days=62):
    """선형 보간 베이스라인"""
    return np.linspace(start_close, end_close, n_days + 2)[1:-1]


def brownian_bridge(start_close, end_close, n_days=62, actual_std=None, seed=42):
    """브라운 브릿지 베이스라인 (양 끝 고정 랜덤워크)"""
    rng = np.random.RandomState(seed)
    T = n_days + 1  # 총 스텝 (시작~종료)

    if actual_std is None:
        actual_std = abs(end_close - start_close) / (T * 2)

    path = np.zeros(T + 1)
    path[0] = start_close
    path[-1] = end_close

    # 브라운 브릿지 생성
    for t in range(1, T):
        remaining = T - t
        drift = (end_close - path[t - 1]) / (remaining + 1)
        noise = actual_std * rng.randn()
        path[t] = path[t - 1] + drift + noise

    return path[1:-1]  # 중간 62일만


def evaluate_ticker(pred_df, label_df, ticker, label_all):
    """종목 하나에 대한 평가"""
    # 날짜 매칭
    merged = pd.merge(label_df, pred_df, on='date', suffixes=('_actual', '_pred'))

    if len(merged) == 0:
        return None

    actual = merged['close_actual'].values
    pred = merged['close_pred'].values

    # --- 1. 가격 정확도 ---
    mae = np.mean(np.abs(actual - pred))
    mape = np.mean(np.abs((actual - pred) / actual)) * 100
    rmse = np.sqrt(np.mean((actual - pred) ** 2))

    # --- 2. 경로 형태 ---
    if len(actual) > 1:
        pearson = np.corrcoef(actual, pred)[0, 1]
        spearman = pd.Series(actual).corr(pd.Series(pred), method='spearman')
        dtw_dist = dtw.distance(actual.astype(np.double), pred.astype(np.double))
    else:
        pearson = spearman = dtw_dist = np.nan

    # --- 3. 방향 일치율 ---
    if len(actual) > 1:
        actual_dir = np.diff(actual) > 0
        pred_dir = np.diff(pred) > 0
        direction_acc = np.mean(actual_dir == pred_dir) * 100
    else:
        direction_acc = np.nan

    # --- 4. 변동성 현실성 ---
    actual_daily_ret = np.diff(actual) / actual[:-1]
    pred_daily_ret = np.diff(pred) / pred[:-1]
    actual_vol = np.std(actual_daily_ret) if len(actual_daily_ret) > 0 else np.nan
    pred_vol = np.std(pred_daily_ret) if len(pred_daily_ret) > 0 else np.nan
    vol_ratio = pred_vol / actual_vol if actual_vol > 0 else np.nan

    # --- 5. 베이스라인 ---
    # 시작/종료 종가 가져오기
    ticker_all = label_all[label_all['ticker'] == ticker].sort_values('date')
    start_close = ticker_all.iloc[0]['close']
    end_close = ticker_all.iloc[-1]['close']

    linear = linear_interpolation(start_close, end_close)
    linear_vals = linear[:len(actual)]
    linear_mape = np.mean(np.abs((actual - linear_vals) / actual)) * 100

    bb = brownian_bridge(start_close, end_close, actual_std=actual_vol * start_close if actual_vol > 0 else None)
    bb_mae = np.mean(np.abs(actual - bb[:len(actual)]))

    # --- 6. 선형보간 대비 개선율 ---
    # MAPE 개선율: 양수면 LLM이 선형보간보다 나음, 음수면 못함
    mape_improvement = (linear_mape - mape) / linear_mape * 100 if linear_mape > 0 else np.nan

    # 예측과 선형보간 간 상관관계: 1에 가까우면 LLM이 선형보간과 거의 동일
    if len(pred) > 1:
        pred_linear_corr = np.corrcoef(pred, linear_vals)[0, 1]
    else:
        pred_linear_corr = np.nan

    return {
        'ticker': ticker,
        'mape': mape,
        'linear_mape': linear_mape,
        'mape_improvement': mape_improvement,
        'pred_linear_corr': pred_linear_corr,
        'pearson': pearson,
        'direction_acc': direction_acc,
        'vol_ratio': vol_ratio,
    }


def main():
    if len(sys.argv) < 2:
        print("Usage: python evaluate.py <prediction_file> [--label <label_file>]")
        sys.exit(1)

    pred_path = sys.argv[1]
    label_path = LABEL_PATH

    if '--label' in sys.argv:
        idx = sys.argv.index('--label')
        label_path = sys.argv[idx + 1]

    # 로드
    print(f"예측 파일: {pred_path}")
    print(f"라벨 파일: {label_path}")
    print()

    predictions = parse_prediction_file(pred_path)
    labels = load_labels(label_path)
    label_all = pd.read_csv(label_path)
    label_all['date'] = pd.to_datetime(label_all['date'])

    print(f"파싱된 종목 수: {len(predictions)}")
    print(f"라벨 종목 수: {len(labels)}")
    print()

    # 평가
    results = []
    for ticker in TICKERS:
        if ticker not in predictions:
            print(f"  {ticker}: 예측 없음, 스킵")
            continue
        if ticker not in labels:
            print(f"  {ticker}: 라벨 없음, 스킵")
            continue

        result = evaluate_ticker(predictions[ticker], labels[ticker], ticker, label_all)
        if result:
            results.append(result)

    if not results:
        print("평가 가능한 종목이 없습니다.")
        sys.exit(1)

    results_df = pd.DataFrame(results)

    # --- 종목별 결과 ---
    print("=" * 100)
    print("종목별 평가 결과")
    print("=" * 100)
    print(f"{'Ticker':<8} {'MAPE%':>8} {'LinMAPE%':>9} {'Improv%':>8} {'PredLinR':>9} {'Pearson':>8} {'Dir%':>8} {'VolRatio':>8}")
    print("-" * 100)

    for _, r in results_df.iterrows():
        print(f"{r['ticker']:<8} {r['mape']:>8.2f} {r['linear_mape']:>9.2f} {r['mape_improvement']:>8.1f} "
              f"{r['pred_linear_corr']:>9.4f} {r['pearson']:>8.4f} "
              f"{r['direction_acc']:>8.1f} {r['vol_ratio']:>8.4f}")

    # --- 전체 평균 ---
    print("-" * 100)
    mean = results_df.mean(numeric_only=True)

    print(f"{'평균':<8} {mean['mape']:>8.2f} {mean['linear_mape']:>9.2f} {mean['mape_improvement']:>8.1f} "
          f"{mean['pred_linear_corr']:>9.4f} {mean['pearson']:>8.4f} "
          f"{mean['direction_acc']:>8.1f} {mean['vol_ratio']:>8.4f}")
    print()

    # --- 요약 ---
    print("=" * 100)
    print("요약")
    print("=" * 100)
    print(f"  LLM MAPE:          {mean['mape']:.2f}%")
    print(f"  Linear MAPE:       {mean['linear_mape']:.2f}%")
    print(f"  MAPE 개선율:       {mean['mape_improvement']:.1f}% (양수=LLM이 선형보간보다 나음)")
    print(f"  Pred-Linear Corr:  {mean['pred_linear_corr']:.4f} (1.0이면 선형보간과 동일)")
    print(f"  Pearson:           {mean['pearson']:.4f}")
    print(f"  Direction Acc:     {mean['direction_acc']:.1f}%")
    print(f"  Volatility Ratio:  {mean['vol_ratio']:.4f} (1.0이 이상적)")

    # 결과 저장
    result_base = os.path.join(os.path.dirname(__file__), 'results')
    os.makedirs(result_base, exist_ok=True)

    # 예측 파일 경로에서 결과 파일명 생성
    pred_name = os.path.basename(os.path.dirname(pred_path))  # 1y
    pred_parent = os.path.basename(os.path.dirname(os.path.dirname(pred_path)))  # thinking_expand
    pred_model = os.path.basename(os.path.dirname(os.path.dirname(os.path.dirname(pred_path))))  # chatgpt5.4
    pred_file = os.path.splitext(os.path.basename(pred_path))[0]  # A

    # results/{model}/{mode}/{period}/ 구조
    result_dir = os.path.join(result_base, pred_model, pred_parent, pred_name)
    os.makedirs(result_dir, exist_ok=True)

    result_path = os.path.join(result_dir, f"{pred_file}_eval.csv")
    round_cols = ['mape', 'linear_mape', 'mape_improvement', 'pred_linear_corr', 'pearson', 'direction_acc', 'vol_ratio']
    results_df[round_cols] = results_df[round_cols].round(3)
    results_df.to_csv(result_path, index=False)
    print(f"\n종목별 결과 저장: {result_path}")

    # --- 실험 요약 CSV (누적, results/ 최상위) ---
    experiment_name = f"{pred_model}_{pred_parent}_{pred_name}_{pred_file}"
    summary_row = pd.DataFrame([{
        'experiment': experiment_name,
        'model': pred_model,
        'mode': pred_parent,
        'period': pred_name,
        'feature_set': pred_file,
        'mape': round(mean['mape'], 3),
        'linear_mape': round(mean['linear_mape'], 3),
        'mape_improvement': round(mean['mape_improvement'], 3),
        'pred_linear_corr': round(mean['pred_linear_corr'], 3),
        'pearson': round(mean['pearson'], 3),
        'direction_acc': round(mean['direction_acc'], 3),
        'vol_ratio': round(mean['vol_ratio'], 3),
        'n_tickers': len(results),
    }])

    summary_path = os.path.join(result_base, 'experiment_summary.csv')
    if os.path.exists(summary_path):
        existing = pd.read_csv(summary_path)
        # 같은 실험이면 업데이트, 아니면 추가
        existing = existing[existing['experiment'] != experiment_name]
        summary_df = pd.concat([existing, summary_row], ignore_index=True)
    else:
        summary_df = summary_row

    summary_df.to_csv(summary_path, index=False)
    print(f"실험 요약 저장: {summary_path}")

    # --- 그래프 ---
    # 개별 종목 그래프
    individual_dir = os.path.join(result_dir, f"{pred_file}_plots")
    os.makedirs(individual_dir, exist_ok=True)

    for ticker in TICKERS:
        if ticker not in predictions or ticker not in labels:
            continue

        label_df = labels[ticker]
        pred_df = predictions[ticker]
        merged = pd.merge(label_df, pred_df, on='date', suffixes=('_actual', '_pred'))
        if len(merged) == 0:
            continue

        # 시작/종료 종가
        ticker_all_df = label_all[label_all['ticker'] == ticker].sort_values('date')
        start_close = ticker_all_df.iloc[0]['close']
        end_close = ticker_all_df.iloc[-1]['close']
        start_date = ticker_all_df.iloc[0]['date']
        end_date = ticker_all_df.iloc[-1]['date']

        # 베이스라인
        linear = linear_interpolation(start_close, end_close)
        actual_daily_ret = np.diff(merged['close_actual'].values) / merged['close_actual'].values[:-1]
        actual_vol = np.std(actual_daily_ret) if len(actual_daily_ret) > 0 else None
        bb = brownian_bridge(start_close, end_close,
                             actual_std=actual_vol * start_close if actual_vol and actual_vol > 0 else None)

        # 종목별 MAE
        ticker_result = results_df[results_df['ticker'] == ticker].iloc[0]

        fig, ax = plt.subplots(figsize=(12, 5))

        # 시작/종료점 포함한 날짜 배열
        all_dates = [start_date] + merged['date'].tolist() + [end_date]
        actual_full = [start_close] + merged['close_actual'].tolist() + [end_close]
        pred_full = [start_close] + merged['close_pred'].tolist() + [end_close]
        linear_full = [start_close] + linear[:len(merged)].tolist() + [end_close]
        bb_full = [start_close] + bb[:len(merged)].tolist() + [end_close]

        ax.plot(all_dates, actual_full, 'b-', linewidth=2, label='Actual', alpha=0.9)
        ax.plot(all_dates, pred_full, 'r--', linewidth=1.5, label='LLM Prediction', alpha=0.8)
        ax.plot(all_dates, linear_full, 'g:', linewidth=1, label='Linear Interpolation', alpha=0.6)
        ax.plot(all_dates, bb_full, 'm:', linewidth=1, label='Brownian Bridge', alpha=0.6)

        # 시작/종료 점 표시
        ax.scatter([start_date, end_date], [start_close, end_close],
                   color='black', zorder=5, s=60, label='Fixed Points')

        ax.set_title(f'{ticker} | MAPE={ticker_result["mape"]:.1f}%  '
                     f'Pearson={ticker_result["pearson"]:.3f}  Dir={ticker_result["direction_acc"]:.0f}%',
                     fontsize=11)
        ax.set_xlabel('Date')
        ax.set_ylabel('Close Price ($)')
        ax.legend(loc='best', fontsize=8)
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%m/%d'))
        ax.xaxis.set_major_locator(mdates.WeekdayLocator(interval=2))
        plt.xticks(rotation=45)
        ax.grid(True, alpha=0.3)
        plt.tight_layout()
        fig.savefig(os.path.join(individual_dir, f'{ticker}.png'), dpi=150)
        plt.close(fig)

    print(f"개별 그래프 저장: {individual_dir}/")

    # 전체 subplot (4×5)
    fig, axes = plt.subplots(4, 5, figsize=(28, 20))
    fig.suptitle(f'LLM Price Path Prediction — {pred_model} / {pred_parent} / {pred_name} / {pred_file}\n'
                 f'Mean MAPE={mean["mape"]:.1f}%  Pearson={mean["pearson"]:.3f}  '
                 f'Direction={mean["direction_acc"]:.1f}%  VolRatio={mean["vol_ratio"]:.3f}',
                 fontsize=14, y=0.98)

    for idx, ticker in enumerate(TICKERS):
        row, col = idx // 5, idx % 5
        ax = axes[row][col]

        if ticker not in predictions or ticker not in labels:
            ax.set_title(f'{ticker} (no data)')
            continue

        label_df = labels[ticker]
        pred_df = predictions[ticker]
        merged = pd.merge(label_df, pred_df, on='date', suffixes=('_actual', '_pred'))
        if len(merged) == 0:
            continue

        ticker_all_df = label_all[label_all['ticker'] == ticker].sort_values('date')
        start_close = ticker_all_df.iloc[0]['close']
        end_close = ticker_all_df.iloc[-1]['close']
        start_date = ticker_all_df.iloc[0]['date']
        end_date = ticker_all_df.iloc[-1]['date']

        linear = linear_interpolation(start_close, end_close)

        all_dates = [start_date] + merged['date'].tolist() + [end_date]
        actual_full = [start_close] + merged['close_actual'].tolist() + [end_close]
        pred_full = [start_close] + merged['close_pred'].tolist() + [end_close]
        linear_full = [start_close] + linear[:len(merged)].tolist() + [end_close]

        ax.plot(all_dates, actual_full, 'b-', linewidth=1.5, label='Actual', alpha=0.9)
        ax.plot(all_dates, pred_full, 'r--', linewidth=1.2, label='LLM', alpha=0.8)
        ax.plot(all_dates, linear_full, 'g:', linewidth=0.8, label='Linear', alpha=0.5)
        ax.scatter([start_date, end_date], [start_close, end_close],
                   color='black', zorder=5, s=30)

        ticker_result = results_df[results_df['ticker'] == ticker].iloc[0]
        ax.set_title(f'{ticker}  MAPE={ticker_result["mape"]:.1f}%  r={ticker_result["pearson"]:.2f}', fontsize=9)
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%m/%d'))
        ax.xaxis.set_major_locator(mdates.MonthLocator())
        ax.tick_params(axis='both', labelsize=7)
        plt.setp(ax.xaxis.get_majorticklabels(), rotation=45)
        ax.grid(True, alpha=0.2)

        if idx == 0:
            ax.legend(fontsize=6, loc='best')

    plt.tight_layout(rect=[0, 0, 1, 0.95])
    summary_path = os.path.join(result_dir, f'{pred_file}_summary.png')
    fig.savefig(summary_path, dpi=150)
    plt.close(fig)
    print(f"전체 요약 그래프 저장: {summary_path}")


if __name__ == '__main__':
    main()
