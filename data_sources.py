from __future__ import annotations

from typing import Iterable

import pandas as pd
import yfinance as yf


def fetch_yfinance_daily(symbols: Iterable[str], period: str = "9mo") -> pd.DataFrame:
    symbols = list(dict.fromkeys(symbols))
    raw = yf.download(
        tickers=symbols,
        period=period,
        interval="1d",
        auto_adjust=True,
        group_by="column",
        threads=True,
        progress=False,
    )
    if raw.empty:
        return pd.DataFrame()

    if isinstance(raw.columns, pd.MultiIndex):
        for field in ["Close", "close"]:
            if field in raw.columns.get_level_values(0):
                close = raw[field].copy()
                close.columns = [str(c) for c in close.columns]
                return close.dropna(how="all")
        for field in ["Close", "close"]:
            if field in raw.columns.get_level_values(1):
                close = raw.xs(field, axis=1, level=1).copy()
                close.columns = [str(c) for c in close.columns]
                return close.dropna(how="all")
    else:
        col = "Close" if "Close" in raw.columns else "close"
        return raw[[col]].rename(columns={col: symbols[0]}).dropna(how="all")

    raise RuntimeError("yfinanceの列形式を解釈できませんでした。yfinanceを更新してください。")
