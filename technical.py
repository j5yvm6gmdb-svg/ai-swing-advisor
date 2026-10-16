from __future__ import annotations

import math
import numpy as np
import pandas as pd


def _safe_float(v):
    try:
        x = float(v)
        return x if math.isfinite(x) else np.nan
    except Exception:
        return np.nan


def _rsi(close: pd.Series, n: int = 14) -> float:
    s = close.dropna().astype(float)
    if len(s) < n + 2:
        return np.nan
    d = s.diff()
    up = d.clip(lower=0).ewm(alpha=1/n, adjust=False).mean()
    dn = (-d.clip(upper=0)).ewm(alpha=1/n, adjust=False).mean()
    rs = up / dn.replace(0, np.nan)
    rsi = 100 - 100 / (1 + rs)
    return _safe_float(rsi.iloc[-1])


def _atr(df: pd.DataFrame, n: int = 14) -> float:
    if len(df) < n + 2 or not {"high", "low", "close"}.issubset(df.columns):
        return np.nan
    h = df["high"].astype(float)
    l = df["low"].astype(float)
    c = df["close"].astype(float)
    pc = c.shift(1)
    tr = pd.concat([(h-l).abs(), (h-pc).abs(), (l-pc).abs()], axis=1).max(axis=1)
    return _safe_float(tr.ewm(alpha=1/n, adjust=False).mean().iloc[-1])


def _pct(s: pd.Series, bars: int) -> float:
    x = s.dropna().astype(float)
    if len(x) <= bars:
        return np.nan
    return (x.iloc[-1] / x.iloc[-1-bars] - 1) * 100


def _weekly(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()
    d = df.copy()
    if not isinstance(d.index, pd.DatetimeIndex):
        d.index = pd.to_datetime(d.index)
    agg = {}
    if "open" in d: agg["open"] = "first"
    if "high" in d: agg["high"] = "max"
    if "low" in d: agg["low"] = "min"
    agg["close"] = "last"
    if "volume" in d: agg["volume"] = "sum"
    return d.resample("W-FRI").agg(agg).dropna(subset=["close"])


def analyze_swing(df: pd.DataFrame, benchmark_close: pd.Series | None = None) -> dict:
    """Daily + weekly technical picture for multi-day / multi-week swing trades."""
    if df is None or df.empty or len(df) < 80:
        return {}

    d = df.dropna(subset=["close"]).copy()
    close = d["close"].astype(float)
    volume = d["volume"].astype(float) if "volume" in d else pd.Series(index=d.index, dtype=float)
    price = _safe_float(close.iloc[-1])

    ema21_s = close.ewm(span=21, adjust=False).mean()
    ma50_s = close.rolling(50).mean()
    ma200_s = close.rolling(200).mean()
    ema21 = _safe_float(ema21_s.iloc[-1])
    ma50 = _safe_float(ma50_s.iloc[-1])
    ma200 = _safe_float(ma200_s.iloc[-1]) if len(close) >= 200 else np.nan

    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()
    macd_s = ema12 - ema26
    signal_s = macd_s.ewm(span=9, adjust=False).mean()
    macd = _safe_float(macd_s.iloc[-1])
    macd_signal = _safe_float(signal_s.iloc[-1])

    atr14 = _atr(d, 14)
    atr_pct = atr14 / price * 100 if price and pd.notna(atr14) else np.nan
    rsi14 = _rsi(close, 14)

    vol20 = volume.tail(20).median() if len(volume.dropna()) >= 20 else np.nan
    volume_ratio = _safe_float(volume.iloc[-1] / vol20) if pd.notna(vol20) and vol20 > 0 else np.nan

    high20 = _safe_float(d["high"].tail(21).iloc[:-1].max()) if "high" in d and len(d) > 21 else _safe_float(close.tail(21).iloc[:-1].max())
    low20 = _safe_float(d["low"].tail(21).iloc[:-1].min()) if "low" in d and len(d) > 21 else _safe_float(close.tail(21).iloc[:-1].min())
    high52 = _safe_float(d["high"].tail(252).max()) if "high" in d else _safe_float(close.tail(252).max())

    rs20 = np.nan
    rs60 = np.nan
    if benchmark_close is not None and not benchmark_close.empty:
        aligned = pd.concat([close.rename("s"), benchmark_close.rename("b")], axis=1).dropna()
        if len(aligned) > 21:
            rs20 = ((aligned.s.iloc[-1]/aligned.s.iloc[-21]) / (aligned.b.iloc[-1]/aligned.b.iloc[-21]) - 1) * 100
        if len(aligned) > 61:
            rs60 = ((aligned.s.iloc[-1]/aligned.s.iloc[-61]) / (aligned.b.iloc[-1]/aligned.b.iloc[-61]) - 1) * 100

    # Weekly structure removes much of the intraday noise and is deliberately material to the score.
    w = _weekly(d)
    wc = w["close"].astype(float) if not w.empty else pd.Series(dtype=float)
    wema10 = _safe_float(wc.ewm(span=10, adjust=False).mean().iloc[-1]) if len(wc) >= 10 else np.nan
    wema30 = _safe_float(wc.ewm(span=30, adjust=False).mean().iloc[-1]) if len(wc) >= 30 else np.nan
    wrsi14 = _rsi(wc, 14) if len(wc) >= 16 else np.nan
    wmacd = np.nan
    wmacd_signal = np.nan
    if len(wc) >= 30:
        wm = wc.ewm(span=12, adjust=False).mean() - wc.ewm(span=26, adjust=False).mean()
        ws = wm.ewm(span=9, adjust=False).mean()
        wmacd = _safe_float(wm.iloc[-1])
        wmacd_signal = _safe_float(ws.iloc[-1])

    whigh13 = np.nan
    if len(wc) > 13:
        source = w["high"] if "high" in w else wc
        whigh13 = _safe_float(source.tail(14).iloc[:-1].max())

    weekly_volume_ratio = np.nan
    if "volume" in w and len(w) >= 11:
        base = pd.to_numeric(w["volume"], errors="coerce").iloc[-11:-1].median()
        latest = _safe_float(w["volume"].iloc[-1])
        if pd.notna(base) and base > 0:
            weekly_volume_ratio = _safe_float(latest / base)

    wrs13 = np.nan
    if benchmark_close is not None and not benchmark_close.empty and len(wc) > 13:
        bdf = pd.DataFrame({"close": benchmark_close})
        bw = _weekly(bdf)
        aligned_w = pd.concat([wc.rename("s"), bw["close"].rename("b")], axis=1).dropna()
        if len(aligned_w) > 13:
            wrs13 = ((aligned_w.s.iloc[-1]/aligned_w.s.iloc[-14]) / (aligned_w.b.iloc[-1]/aligned_w.b.iloc[-14]) - 1) * 100

    return {
        "price": price,
        "ret_5d_pct": _safe_float(_pct(close, 5)),
        "ret_20d_pct": _safe_float(_pct(close, 20)),
        "ret_60d_pct": _safe_float(_pct(close, 60)),
        "ema21": ema21,
        "ma50": ma50,
        "ma200": ma200,
        "rsi14": rsi14,
        "macd": macd,
        "macd_signal": macd_signal,
        "atr14": atr14,
        "atr_pct": _safe_float(atr_pct),
        "volume_ratio": volume_ratio,
        "high20": high20,
        "low20": low20,
        "high52": high52,
        "breakout20": bool(pd.notna(high20) and price > high20),
        "above_ema21": bool(pd.notna(ema21) and price > ema21),
        "above_ma50": bool(pd.notna(ma50) and price > ma50),
        "above_ma200": bool(pd.notna(ma200) and price > ma200),
        "trend_stack": bool(pd.notna(ma200) and price > ema21 > ma50 > ma200),
        "dist_ema21_atr": _safe_float((price-ema21)/atr14) if pd.notna(ema21) and pd.notna(atr14) and atr14 > 0 else np.nan,
        "dist_52w_high_pct": _safe_float((price/high52 - 1)*100) if pd.notna(high52) and high52 > 0 else np.nan,
        "rs_smh_20d_pct": _safe_float(rs20),
        "rs_smh_60d_pct": _safe_float(rs60),
        "weekly_ret_13w_pct": _safe_float(_pct(wc, 13)) if len(wc) > 13 else np.nan,
        "weekly_ret_26w_pct": _safe_float(_pct(wc, 26)) if len(wc) > 26 else np.nan,
        "weekly_ema10": wema10,
        "weekly_ema30": wema30,
        "weekly_rsi14": wrsi14,
        "weekly_macd": wmacd,
        "weekly_macd_signal": wmacd_signal,
        "weekly_high13": whigh13,
        "weekly_breakout13": bool(pd.notna(whigh13) and price > whigh13),
        "weekly_above_ema10": bool(pd.notna(wema10) and price > wema10),
        "weekly_above_ema30": bool(pd.notna(wema30) and price > wema30),
        "weekly_trend_stack": bool(pd.notna(wema10) and pd.notna(wema30) and price > wema10 > wema30),
        "weekly_volume_ratio": weekly_volume_ratio,
        "weekly_rs_smh_13w_pct": _safe_float(wrs13),
    }


def technical_score(m: dict) -> tuple[float, float, float, list[str], list[str]]:
    """40 points total: Daily 25 + Weekly 15."""
    if not m:
        return 0.0, 0.0, 0.0, [], ["価格データ不足"]

    d = 0.0
    w = 0.0
    positives: list[str] = []
    risks: list[str] = []

    # DAILY: max 25 before clamping
    if m.get("above_ema21"):
        d += 3
        positives.append("日足21EMA上")
    else:
        d -= 2
        risks.append("日足21EMA下")
    if m.get("above_ma50"):
        d += 3
        positives.append("日足50DMA上")
    else:
        d -= 2
        risks.append("日足50DMA下")
    if m.get("above_ma200"):
        d += 2
    if m.get("trend_stack"):
        d += 4
        positives.append("日足の移動平均が上昇整列")
    if m.get("breakout20"):
        d += 3
        positives.append("日足20日高値ブレイク")

    rsi = m.get("rsi14", np.nan)
    if pd.notna(rsi):
        if 50 <= rsi <= 68:
            d += 2
        elif 68 < rsi <= 75:
            d += 1
        elif rsi > 78:
            d -= 3
            risks.append("日足RSI過熱")
        elif rsi < 42:
            d -= 2
            risks.append("日足モメンタム弱い")

    if pd.notna(m.get("macd")) and pd.notna(m.get("macd_signal")):
        if m["macd"] > m["macd_signal"]:
            d += 2
        else:
            d -= 1

    rs20 = m.get("rs_smh_20d_pct", np.nan)
    rs60 = m.get("rs_smh_60d_pct", np.nan)
    if pd.notna(rs20):
        if rs20 >= 8:
            d += 3
            positives.append("SMH比20日で強い")
        elif rs20 >= 2:
            d += 2
        elif rs20 <= -8:
            d -= 3
            risks.append("SMH比20日で弱い")
    if pd.notna(rs60):
        if rs60 >= 10:
            d += 2
        elif rs60 <= -12:
            d -= 2

    vr = m.get("volume_ratio", np.nan)
    if pd.notna(vr) and vr >= 1.5:
        d += 1
        positives.append("日足出来高増")

    ext = m.get("dist_ema21_atr", np.nan)
    if pd.notna(ext):
        if ext > 2.5:
            d -= 4
            risks.append("21EMAから2.5ATR超の乖離")
        elif -0.4 <= ext <= 1.2 and m.get("above_ema21"):
            d += 2
            positives.append("日足の押し目圏")

    d = float(max(0, min(25, d)))

    # WEEKLY: max 15
    if m.get("weekly_above_ema10"):
        w += 2
        positives.append("週足10EMA上")
    else:
        w -= 1
        risks.append("週足10EMA下")
    if m.get("weekly_above_ema30"):
        w += 2
    if m.get("weekly_trend_stack"):
        w += 4
        positives.append("週足トレンド良好")

    wrsi = m.get("weekly_rsi14", np.nan)
    if pd.notna(wrsi):
        if 50 <= wrsi <= 70:
            w += 2
        elif wrsi > 76:
            w -= 2
            risks.append("週足RSI過熱")
        elif wrsi < 42:
            w -= 2
            risks.append("週足モメンタム弱い")

    if pd.notna(m.get("weekly_macd")) and pd.notna(m.get("weekly_macd_signal")):
        if m["weekly_macd"] > m["weekly_macd_signal"]:
            w += 2
        else:
            w -= 1

    wrs = m.get("weekly_rs_smh_13w_pct", np.nan)
    if pd.notna(wrs):
        if wrs >= 8:
            w += 3
            positives.append("SMH比13週で強い")
        elif wrs >= 2:
            w += 2
        elif wrs <= -10:
            w -= 2
            risks.append("SMH比13週で弱い")

    if m.get("weekly_breakout13"):
        w += 2
        positives.append("13週高値ブレイク")

    w = float(max(0, min(15, w)))
    total = float(max(0, min(40, d + w)))
    return total, d, w, positives, risks
