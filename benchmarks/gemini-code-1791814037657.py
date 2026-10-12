import numpy as np
import pandas as pd
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score

def calculate_metrics(y_true, y_pred):
    rmse = np.sqrt(mean_squared_error(y_true, y_pred))
    mae = mean_absolute_error(y_true, y_pred)
    r2 = r2_score(y_true, y_pred)
    # MAPE (0 나눗셈 방지 epsilon 적용)
    epsilon = 1.0
    mape = np.mean(np.abs((y_true - y_pred) / (y_true + epsilon))) * 100
    return {"RMSE": round(rmse, 2), "MAE": round(mae, 2), "MAPE(%)": round(mape, 2), "R²": round(r2, 4)}

targets = {
    'bike': ('따릉이_대여', trained_models['bike']),
    'bus': ('버스_승차', trained_models['bus']),
    'subway': ('지하철_승차', trained_models['subway'])
}

comparison_results = []

for mode, (target_col, model) in targets.items():
    y_true = y_test_full[target_col].values
    
    # 1. 이전 기준 (베이스라인: 과거 시간대별/구별 단순 평균 예측)
    baseline_pred = df.loc[train_mask].groupby(['구', '시간'])[target_col].transform('mean')
    y_base = df.loc[test_mask, ['구', '시간']].merge(
        df.loc[train_mask].groupby(['구', '시간'])[target_col].mean().reset_index(),
        on=['구', '시간'], how='left'
    )[target_col].fillna(y_true.mean()).values
    
    # 2. 신규 모델 (Optuna 튜닝 LightGBM)
    y_pred = np.clip(model.predict(X_test), 0, None)
    
    # 지표 계산
    base_metrics = calculate_metrics(y_true, y_base)
    model_metrics = calculate_metrics(y_true, y_pred)
    
    comparison_results.append({
        "수단": mode.upper(),
        "지표": "R² (설명력)",
        "이전 모델(Baseline)": base_metrics["R²"],
        "신규 모델(LightGBM)": model_metrics["R²"],
        "개선도": f"+{round((model_metrics['R²'] - base_metrics['R²']) * 100, 2)}%p"
    })
    comparison_results.append({
        "수단": mode.upper(),
        "지표": "MAPE (오차율)",
        "이전 모델(Baseline)": f"{base_metrics['MAPE(%)']}%",
        "신규 모델(LightGBM)": f"{model_metrics['MAPE(%)']}%",
        "개선도": f"-{round(base_metrics['MAPE(%)'] - model_metrics['MAPE(%)'], 2)}%p"
    })
    comparison_results.append({
        "수단": mode.upper(),
        "지표": "RMSE (오차량)",
        "이전 모델(Baseline)": base_metrics["RMSE"],
        "신규 모델(LightGBM)": model_metrics["RMSE"],
        "개선도": f"-{round(base_metrics['RMSE'] - model_metrics['RMSE'], 2)}"
    })

# 비교표 출력
comp_df = pd.DataFrame(comparison_results)
display(comp_df)