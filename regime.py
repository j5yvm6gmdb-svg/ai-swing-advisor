from __future__ import annotations

import numpy as np
import pandas as pd

from config import AI_GROUPS, DEFENSIVE_VALUE_CORE, SECTOR_ETFS


def build_ai_group_returns(close: pd.DataFrame) -> tuple[pd.DataFrame, pd.Series]:
    returns = close.pct_change(fill_method=None)
    group_returns = {}
    for group, symbols in AI_GROUPS.items():
        available = [s for s in symbols if s in returns.columns]
        if available:
            group_returns[group] = returns[available].mean(axis=1, skipna=True)
    groups = pd.DataFrame(group_returns)
    ai_basket = groups.mean(axis=1, skipna=True).rename("AI_BASKET")
    return groups, ai_basket


def classify_latest_regime(close: pd.DataFrame) -> dict:
    groups, ai = build_ai_group_returns(close)
    rets = close.pct_change(fill_method=None)
    last = rets.dropna(how="all").index[-1]
    ai_last = float(ai.loc[last]) if last in ai.index and pd.notna(ai.loc[last]) else np.nan
    spy = float(rets.loc[last, "SPY"]) if "SPY" in rets.columns and pd.notna(rets.loc[last, "SPY"]) else np.nan

    core = [s for s in DEFENSIVE_VALUE_CORE if s in rets.columns]
    sector_returns = rets.loc[last, core].dropna() if core else pd.Series(dtype=float)
    non_ai_median = float(sector_returns.median()) if len(sector_returns) else np.nan
    breadth = float((sector_returns > 0).mean()) if len(sector_returns) else np.nan
    ai_rel_spy = ai_last - spy if pd.notna(ai_last) and pd.notna(spy) else np.nan

    # 閾値は日次リターン（例: 0.006 = 0.6%）
    if pd.notna(ai_last) and pd.notna(non_ai_median) and ai_last > 0.005 and ai_rel_spy > 0.004 and non_ai_median <= 0:
        regime = "AI_CONCENTRATION"
        jp = "AI集中相場"
    elif pd.notna(ai_last) and pd.notna(non_ai_median) and ai_last < -0.005 and (non_ai_median > 0 or (pd.notna(breadth) and breadth >= 0.625)):
        regime = "ROTATION_OUT_OF_AI"
        jp = "AI→非AIローテーション"
    elif pd.notna(ai_last) and pd.notna(spy) and ai_last > 0 and spy > 0 and pd.notna(breadth) and breadth >= 0.625:
        regime = "BROAD_RISK_ON"
        jp = "全面リスクオン"
    elif pd.notna(ai_last) and pd.notna(spy) and ai_last < 0 and spy < 0 and pd.notna(breadth) and breadth <= 0.375:
        regime = "BROAD_RISK_OFF"
        jp = "全面リスクオフ"
    else:
        regime = "MIXED"
        jp = "混合・方向感弱い"

    sector_snapshot = {}
    ticker_to_name = {ticker: name for name, ticker in SECTOR_ETFS.items()}
    for ticker in [t for t in SECTOR_ETFS.values() if t in rets.columns]:
        value = rets.loc[last, ticker]
        if pd.notna(value):
            sector_snapshot[ticker_to_name[ticker]] = round(float(value) * 100, 3)

    return {
        "date": str(pd.Timestamp(last).date()),
        "regime": regime,
        "regime_jp": jp,
        "ai_basket_pct": round(ai_last * 100, 3) if pd.notna(ai_last) else None,
        "spy_pct": round(spy * 100, 3) if pd.notna(spy) else None,
        "ai_vs_spy_pct": round(ai_rel_spy * 100, 3) if pd.notna(ai_rel_spy) else None,
        "non_ai_core_median_pct": round(non_ai_median * 100, 3) if pd.notna(non_ai_median) else None,
        "non_ai_core_breadth_positive": round(breadth, 3) if pd.notna(breadth) else None,
        "sectors_pct": sector_snapshot,
    }
