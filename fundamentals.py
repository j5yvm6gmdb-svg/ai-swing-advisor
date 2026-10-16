from __future__ import annotations

import math
import os
import re
import time
from datetime import datetime, timezone

import numpy as np
import pandas as pd
import requests
import yfinance as yf


def _f(v):
    try:
        x = float(v)
        return x if math.isfinite(x) else np.nan
    except Exception:
        return np.nan


def _row(df, idx, col="growth"):
    try:
        return _f(df.loc[idx, col])
    except Exception:
        return np.nan


def _df_safe(fn):
    try:
        x = fn()
        return x if isinstance(x, pd.DataFrame) else pd.DataFrame()
    except Exception:
        return pd.DataFrame()


def yfinance_research(symbol: str) -> dict:
    t = yf.Ticker(symbol)
    try:
        info = t.get_info() or {}
    except Exception:
        info = {}

    rev = _df_safe(t.get_revenue_estimate)
    eps = _df_safe(t.get_earnings_estimate)
    revs = _df_safe(t.get_eps_revisions)
    trend = _df_safe(t.get_eps_trend)
    growth = _df_safe(t.get_growth_estimates)
    hist = _df_safe(t.get_earnings_history)
    try:
        targets = t.get_analyst_price_targets() or {}
    except Exception:
        targets = {}
    try:
        recs = t.get_recommendations() or pd.DataFrame()
    except Exception:
        recs = pd.DataFrame()

    next_earnings_date = None
    days_to_earnings = np.nan
    try:
        ed = t.get_earnings_dates(limit=8)
        if isinstance(ed, pd.DataFrame) and not ed.empty:
            now = pd.Timestamp.now(tz="UTC")
            idx = pd.to_datetime(ed.index, utc=True, errors="coerce")
            future = [x for x in idx if pd.notna(x) and x >= now]
            if future:
                nxt = min(future)
                next_earnings_date = nxt.date().isoformat()
                days_to_earnings = (nxt - now).total_seconds() / 86400
    except Exception:
        pass

    price = _f(targets.get("current", info.get("currentPrice")))
    target_mean = _f(targets.get("mean"))
    upside = (target_mean / price - 1) * 100 if pd.notna(price) and price > 0 and pd.notna(target_mean) else np.nan

    # 0q/+1q/0y/+1y are yfinance documented index labels.
    next_rev_growth = _row(rev, "+1y")
    next_eps_growth = _row(eps, "+1y")
    cur_rev_growth = _row(rev, "0y")
    cur_eps_growth = _row(eps, "0y")
    lt_growth = _row(growth, "+5y", "stock")

    up30 = _row(revs, "+1y", "upLast30days")
    down30 = _row(revs, "+1y", "downLast30days")
    current_eps_est = _row(trend, "+1y", "current")
    eps30 = _row(trend, "+1y", "30daysAgo")
    eps_revision_pct = ((current_eps_est / eps30) - 1) * 100 if pd.notna(current_eps_est) and pd.notna(eps30) and eps30 != 0 else np.nan

    surprise = np.nan
    if not hist.empty and "surprisePercent" in hist.columns:
        s = pd.to_numeric(hist["surprisePercent"], errors="coerce").dropna().tail(4)
        if len(s): surprise = _f(s.mean())

    buy_share = np.nan
    analyst_count = 0
    try:
        row = recs.iloc[0]
        vals = {k: _f(row.get(k)) for k in ["strongBuy", "buy", "hold", "sell", "strongSell"]}
        total = sum(v for v in vals.values() if pd.notna(v))
        analyst_count = int(total) if total else 0
        if total:
            buy_share = (vals.get("strongBuy", 0) + vals.get("buy", 0)) / total * 100
    except Exception:
        pass

    total_cash = _f(info.get("totalCash"))
    total_debt = _f(info.get("totalDebt"))
    fcf = _f(info.get("freeCashflow"))
    revenue = _f(info.get("totalRevenue"))
    market_cap = _f(info.get("marketCap"))

    return {
        "symbol": symbol,
        "name": info.get("shortName") or info.get("longName") or symbol,
        "sector": info.get("sector"),
        "industry": info.get("industry"),
        "market_cap": market_cap,
        "revenue_growth_ttm": _f(info.get("revenueGrowth")),
        "earnings_growth_ttm": _f(info.get("earningsGrowth")),
        "gross_margin": _f(info.get("grossMargins")),
        "operating_margin": _f(info.get("operatingMargins")),
        "profit_margin": _f(info.get("profitMargins")),
        "roe": _f(info.get("returnOnEquity")),
        "debt_to_equity": _f(info.get("debtToEquity")),
        "total_cash": total_cash,
        "total_debt": total_debt,
        "net_cash": total_cash-total_debt if pd.notna(total_cash) and pd.notna(total_debt) else np.nan,
        "free_cashflow": fcf,
        "fcf_margin": fcf/revenue if pd.notna(fcf) and pd.notna(revenue) and revenue else np.nan,
        "forward_pe": _f(info.get("forwardPE")),
        "trailing_pe": _f(info.get("trailingPE")),
        "price_to_sales": _f(info.get("priceToSalesTrailing12Months")),
        "peg_ratio": _f(info.get("pegRatio")),
        "ev_to_ebitda": _f(info.get("enterpriseToEbitda")),
        "beta": _f(info.get("beta")),
        "cur_rev_growth_est": cur_rev_growth,
        "next_rev_growth_est": next_rev_growth,
        "cur_eps_growth_est": cur_eps_growth,
        "next_eps_growth_est": next_eps_growth,
        "long_term_growth_est": lt_growth,
        "eps_revision_up_30d": up30,
        "eps_revision_down_30d": down30,
        "eps_est_revision_pct_30d": eps_revision_pct,
        "earnings_surprise_avg": surprise,
        "analyst_target_mean": target_mean,
        "analyst_upside_pct": _f(upside),
        "analyst_buy_share_pct": _f(buy_share),
        "analyst_count": analyst_count,
        "next_earnings_date": next_earnings_date,
        "days_to_earnings": _f(days_to_earnings),
        "source": "yfinance",
    }


def _fmp_get(path: str, params: dict) -> list | dict | None:
    key = os.getenv("FMP_API_KEY", "").strip()
    if not key:
        return None
    q = dict(params)
    q["apikey"] = key
    try:
        r = requests.get(f"https://financialmodelingprep.com/stable/{path}", params=q, timeout=25)
        if not r.ok:
            return None
        return r.json()
    except Exception:
        return None


def fmp_forward_overlay(symbol: str) -> dict:
    """Optional FMP enrichment. Missing/premium endpoints fail closed."""
    out = {}
    est = _fmp_get("analyst-estimates", {"symbol": symbol, "period": "annual", "page": 0, "limit": 5})
    if isinstance(est, list) and est:
        today = datetime.now(timezone.utc).date().isoformat()
        rows = sorted([r for r in est if str(r.get("date", "")) >= today], key=lambda x: str(x.get("date", "")))
        if len(rows) < 2:
            rows = sorted(est, key=lambda x: str(x.get("date", "")))
        # future annual estimates: nearest two rows when available
        if len(rows) >= 2:
            a, b = rows[0], rows[1]
            ra, rb = _f(a.get("revenueAvg")), _f(b.get("revenueAvg"))
            ea, eb = _f(a.get("epsAvg")), _f(b.get("epsAvg"))
            if pd.notna(ra) and ra: out["fmp_forward_revenue_growth"] = (rb/ra - 1)
            if pd.notna(ea) and ea: out["fmp_forward_eps_growth"] = (eb/ea - 1)
            out["fmp_estimate_date"] = b.get("date")
            out["fmp_num_analysts_revenue"] = b.get("numAnalystsRevenue")
            out["fmp_num_analysts_eps"] = b.get("numAnalystsEps")
    pt = _fmp_get("price-target-consensus", {"symbol": symbol})
    if isinstance(pt, list) and pt:
        out["fmp_target_consensus"] = _f(pt[0].get("targetConsensus"))
    return out


def fmp_guidance_overlay(symbol: str) -> dict:
    """Latest earnings transcript guidance/outlook heuristic.

    It does not pretend to understand every company. It extracts sentences around guidance/outlook
    and creates a transparent tone score; the dashboard exposes low confidence when unavailable.
    """
    dates = _fmp_get("earning-call-transcript-dates", {"symbol": symbol})
    if not isinstance(dates, list) or not dates:
        return {"guidance_available": False}
    latest = sorted(dates, key=lambda x: str(x.get("date", "")), reverse=True)[0]
    year = latest.get("fiscalYear")
    quarter = latest.get("quarter")
    if year is None or quarter is None:
        return {"guidance_available": False}
    tx = _fmp_get("earning-call-transcript", {"symbol": symbol, "year": year, "quarter": quarter, "limit": 1})
    if not isinstance(tx, list) or not tx:
        return {"guidance_available": False}
    content = str(tx[0].get("content", ""))
    if not content:
        return {"guidance_available": False}

    sentences = re.split(r"(?<=[.!?])\s+", content)
    keys = ("guidance", "outlook", "expect", "forecast", "raise", "lower", "reaffirm", "full year", "next quarter")
    snippets = [s.strip() for s in sentences if any(k in s.lower() for k in keys)]
    snippets = [s for s in snippets if 30 <= len(s) <= 500][:12]
    text = " ".join(snippets).lower()
    positive = ["raise", "raised", "increase", "above", "strong", "accelerat", "higher", "reaffirm", "exceed", "improv"]
    negative = ["lower", "lowered", "decrease", "below", "weak", "slow", "headwind", "declin", "reduce", "pressure"]
    pos = sum(text.count(w) for w in positive)
    neg = sum(text.count(w) for w in negative)
    tone = max(-1.0, min(1.0, (pos-neg)/max(3, pos+neg)))
    return {
        "guidance_available": bool(snippets),
        "guidance_tone": tone,
        "guidance_period": f"FY{year} Q{quarter}",
        "guidance_snippets": snippets[:4],
        "guidance_method": "keyword_heuristic_from_earnings_transcript",
    }


def research_symbol(symbol: str, use_fmp: bool = True) -> dict:
    out = yfinance_research(symbol)
    if use_fmp and os.getenv("FMP_API_KEY", "").strip():
        out.update(fmp_forward_overlay(symbol))
        out.update(fmp_guidance_overlay(symbol))
        out["source"] = "yfinance+FMP"
    out["researched_at"] = datetime.now(timezone.utc).isoformat()
    return out


def quality_score(x: dict) -> tuple[float, list[str], list[str]]:
    s = 0.0; pos=[]; risk=[]
    rg = x.get("revenue_growth_ttm", np.nan)
    eg = x.get("earnings_growth_ttm", np.nan)
    gm = x.get("gross_margin", np.nan)
    om = x.get("operating_margin", np.nan)
    fcfm = x.get("fcf_margin", np.nan)
    roe = x.get("roe", np.nan)
    ndebt = x.get("net_cash", np.nan)

    if pd.notna(rg):
        if rg >= .25: s+=4; pos.append("売上高成長率が高い")
        elif rg >= .10: s+=3
        elif rg >= 0: s+=1
        else: s-=2; risk.append("売上高減少")
    if pd.notna(eg):
        if eg >= .30: s+=4; pos.append("利益成長が強い")
        elif eg >= .10: s+=3
        elif eg < 0: s-=2; risk.append("利益成長マイナス")
    if pd.notna(gm):
        if gm >= .55: s+=3
        elif gm >= .35: s+=2
    if pd.notna(om):
        if om >= .25: s+=3; pos.append("営業利益率が高い")
        elif om >= .12: s+=2
        elif om < 0: s-=2; risk.append("営業赤字")
    if pd.notna(fcfm):
        if fcfm >= .20: s+=3; pos.append("FCF創出力が高い")
        elif fcfm >= .08: s+=2
        elif fcfm < 0: s-=2; risk.append("FCFマイナス")
    if pd.notna(roe):
        if roe >= .20: s+=2
        elif roe >= .10: s+=1
    if pd.notna(ndebt):
        if ndebt > 0: s+=1
        else: risk.append("ネット有利子負債")
    return float(max(0,min(20,s))), pos, risk


def forward_score(x: dict) -> tuple[float, list[str], list[str]]:
    s=0.0; pos=[]; risk=[]
    revg = x.get("fmp_forward_revenue_growth", x.get("next_rev_growth_est", np.nan))
    epsg = x.get("fmp_forward_eps_growth", x.get("next_eps_growth_est", np.nan))
    rev_pct = revg*100 if pd.notna(revg) and abs(revg) < 2 else revg
    eps_pct = epsg*100 if pd.notna(epsg) and abs(epsg) < 2 else epsg
    if pd.notna(rev_pct):
        if rev_pct >= 25: s+=6; pos.append("翌期売上成長予想が強い")
        elif rev_pct >= 12: s+=4
        elif rev_pct >= 5: s+=2
        elif rev_pct < 0: s-=3; risk.append("翌期売上減少予想")
    if pd.notna(eps_pct):
        if eps_pct >= 30: s+=6; pos.append("翌期EPS成長予想が強い")
        elif eps_pct >= 15: s+=4
        elif eps_pct >= 5: s+=2
        elif eps_pct < 0: s-=3; risk.append("翌期EPS減少予想")
    rev = x.get("eps_est_revision_pct_30d", np.nan)
    if pd.notna(rev):
        if rev >= 3: s+=4; pos.append("EPS予想が上方修正")
        elif rev > 0: s+=2
        elif rev <= -3: s-=4; risk.append("EPS予想が下方修正")
    up = x.get("eps_revision_up_30d", np.nan); dn=x.get("eps_revision_down_30d", np.nan)
    if pd.notna(up) and pd.notna(dn):
        if up > dn: s+=2
        elif dn > up: s-=2
    surprise=x.get("earnings_surprise_avg",np.nan)
    if pd.notna(surprise):
        if surprise >= 5: s+=2
        elif surprise < -3: s-=2
    upside=x.get("analyst_upside_pct",np.nan)
    if pd.notna(upside):
        if 10 <= upside <= 50: s+=2
        elif upside < -5: s-=2
    buy=x.get("analyst_buy_share_pct",np.nan)
    if pd.notna(buy) and buy >= 70: s+=1
    tone=x.get("guidance_tone",np.nan)
    if pd.notna(tone):
        if tone > .2: s+=2; pos.append("経営陣ガイダンスのトーン良好")
        elif tone < -.2: s-=2; risk.append("経営陣ガイダンスのトーン弱い")
    return float(max(0,min(25,s))), pos, risk


def valuation_score(x: dict) -> tuple[float, list[str], list[str]]:
    s=5.0; pos=[]; risk=[]  # neutral midpoint
    pe=x.get("forward_pe",np.nan); peg=x.get("peg_ratio",np.nan); ps=x.get("price_to_sales",np.nan)
    growth=x.get("next_eps_growth_est",np.nan)
    gpct = growth*100 if pd.notna(growth) and abs(growth)<2 else growth
    if pd.notna(peg):
        if 0 < peg <= 1.5: s+=3; pos.append("PEGが比較的低い")
        elif peg >= 3: s-=2; risk.append("PEG高め")
    elif pd.notna(pe) and pd.notna(gpct) and gpct > 0:
        ratio=pe/gpct
        if ratio <= 1.0: s+=2
        elif ratio >= 2.0: s-=2
    if pd.notna(pe):
        if pe > 80: s-=2; risk.append("Forward P/E高い")
        elif 0 < pe < 30: s+=1
    if pd.notna(ps) and ps > 25: s-=2; risk.append("P/S高い")
    return float(max(0,min(10,s))), pos, risk
