from __future__ import annotations

import math
import numpy as np
import pandas as pd

from fundamentals import quality_score, forward_score, valuation_score
from technical import technical_score


def _f(v):
    try:
        x = float(v)
        return x if math.isfinite(x) else np.nan
    except Exception:
        return np.nan


def regime_adjustment(regime: dict, group: str) -> tuple[float, str | None]:
    name=(regime or {}).get("regime")
    if name == "AI_CONCENTRATION": return 4.0, "AI集中相場"
    if name == "BROAD_RISK_ON": return 2.0, "全面リスクオン"
    if name == "ROTATION_OUT_OF_AI": return -4.0, "AIから資金流出"
    if name == "BROAD_RISK_OFF": return -5.0, "全面リスクオフ"
    return 0.0, None


def trade_plan(tech: dict, total: float) -> dict:
    """Swing entry framework using daily/weekly structure only."""
    p=_f(tech.get("price")); atr=_f(tech.get("atr14")); ema=_f(tech.get("ema21")); high20=_f(tech.get("high20")); ma50=_f(tech.get("ma50"))
    if pd.isna(p): return {"action":"データ不足"}
    ext=_f(tech.get("dist_ema21_atr"))
    weekly_ok = bool(tech.get("weekly_trend_stack") or (tech.get("weekly_above_ema10") and tech.get("weekly_above_ema30")))

    if total >= 80:
        if not weekly_ok:
            action="週足確認待ち"
            entry_low=entry_high=p
        elif pd.notna(ext) and ext > 2.3:
            action="押し目待ち"
            entry_low = ema if pd.notna(ema) else p-atr
            entry_high = p-0.7*atr if pd.notna(atr) else p
        elif tech.get("breakout20") or tech.get("weekly_breakout13"):
            action="スイング・ブレイク候補"
            entry_low = high20 if pd.notna(high20) else p
            entry_high = p + (0.25*atr if pd.notna(atr) else 0)
        elif tech.get("above_ema21") and tech.get("above_ma50"):
            action="スイング・エントリー候補"
            entry_low = max(ema, p-0.8*atr) if pd.notna(ema) and pd.notna(atr) else p
            entry_high = p + (0.15*atr if pd.notna(atr) else 0)
        else:
            action="日足トレンド確認待ち"
            entry_low=entry_high=p
    elif total >= 70:
        action="監視・押し目待ち"
        entry_low = ema if pd.notna(ema) else p
        entry_high = p
    elif total >= 60:
        action="中立・確認待ち"
        entry_low=entry_high=p
    else:
        action="見送り"
        entry_low=entry_high=p

    stop=np.nan; t1=np.nan; t2=np.nan
    if pd.notna(atr) and atr>0 and action not in {"見送り","中立・確認待ち","週足確認待ち","日足トレンド確認待ち"}:
        ref=(entry_low+entry_high)/2
        candidates=[ref-2.2*atr]
        if pd.notna(ma50): candidates.append(ma50-0.4*atr)
        valid=[x for x in candidates if pd.notna(x) and x<ref]
        stop=max(valid) if valid else ref-2.2*atr
        risk=ref-stop
        t1=ref+2*risk; t2=ref+3*risk
    return {
        "action": action,
        "entry_zone_low": round(float(entry_low),2) if pd.notna(entry_low) else None,
        "entry_zone_high": round(float(entry_high),2) if pd.notna(entry_high) else None,
        "invalidation": round(float(stop),2) if pd.notna(stop) else None,
        "target_2R": round(float(t1),2) if pd.notna(t1) else None,
        "target_3R": round(float(t2),2) if pd.notna(t2) else None,
    }


def score_stock(symbol: str, group: str, research: dict, tech: dict, regime: dict, owned: bool=False, avg_cost: float|None=None) -> dict:
    ts, daily_ts, weekly_ts, tp, tr = technical_score(tech)
    qs, qp, qr = quality_score(research)
    fw, fwp, fwr = forward_score(research)
    vs, vp, vr = valuation_score(research)
    ra, regime_note = regime_adjustment(regime, group)

    penalty=0.0; risks=[]
    beta=_f(research.get("beta")); atrp=_f(tech.get("atr_pct"))
    if pd.notna(beta) and beta >= 2: penalty += 2; risks.append("高ベータ")
    if pd.notna(atrp) and atrp >= 7: penalty += 3; risks.append("日次ボラティリティ高い")
    if research.get("free_cashflow") is not None and pd.notna(_f(research.get("free_cashflow"))) and _f(research.get("free_cashflow")) < 0:
        penalty += 2
    if research.get("guidance_available") is False and research.get("source") == "yfinance+FMP":
        risks.append("経営陣ガイダンス抽出なし")
    dte=_f(research.get("days_to_earnings"))
    if pd.notna(dte) and dte <= 7:
        penalty += 3
        risks.append(f"決算まで約{max(0,int(round(dte)))}日")

    total=max(0.0,min(100.0,ts+qs+fw+vs+ra-penalty))
    if total >= 85: grade="A"
    elif total >= 75: grade="B"
    elif total >= 65: grade="C"
    elif total >= 55: grade="D"
    else: grade="E"

    confidence_fields=[
        tech.get("price"),tech.get("ma50"),tech.get("weekly_ema10"),tech.get("weekly_ema30"),
        research.get("revenue_growth_ttm"),research.get("operating_margin"),research.get("next_rev_growth_est"),
        research.get("next_eps_growth_est"),research.get("forward_pe")
    ]
    confidence=sum(pd.notna(_f(v)) for v in confidence_fields)/len(confidence_fields)
    if research.get("guidance_available"): confidence=min(1.0,confidence+.08)

    plan=trade_plan(tech,total)
    if pd.notna(dte) and dte <= 5 and plan.get("action") in {"スイング・エントリー候補","スイング・ブレイク候補","監視・押し目待ち"}:
        plan["action"] = "決算前・確認待ち"
    positives=(tp+qp+fwp+vp)[:8]
    risks=(tr+qr+fwr+vr+risks)[:8]
    if regime_note:
        (positives if ra>0 else risks).append(regime_note)

    holding_note=None
    if owned:
        p=_f(tech.get("price")); c=_f(avg_cost)
        pnl=(p/c-1)*100 if pd.notna(p) and pd.notna(c) and c>0 else np.nan
        if total >= 75 and tech.get("above_ma50") and tech.get("weekly_above_ema10"):
            holding_note="スイング保有継続候補"
        elif total < 55 or not tech.get("above_ma50") or not tech.get("weekly_above_ema10"):
            holding_note="リスク縮小を検討"
        else:
            holding_note="保有は可、追加は日足/週足確認待ち"
        if pd.notna(pnl): holding_note += f"（取得単価比 {pnl:+.1f}%）"

    return {
        "symbol":symbol,"group":group,"name":research.get("name",symbol),
        "score":round(total,1),"grade":grade,"confidence":round(confidence*100),
        "technical_score":round(ts,1),"daily_technical_score":round(daily_ts,1),"weekly_technical_score":round(weekly_ts,1),
        "quality_score":round(qs,1),"forward_score":round(fw,1),"valuation_score":round(vs,1),
        "regime_adjustment":round(ra,1),"risk_penalty":round(penalty,1),
        "price":tech.get("price"),"rsi14":tech.get("rsi14"),"weekly_rsi14":tech.get("weekly_rsi14"),
        "rs_smh_20d_pct":tech.get("rs_smh_20d_pct"),"rs_smh_60d_pct":tech.get("rs_smh_60d_pct"),
        "weekly_rs_smh_13w_pct":tech.get("weekly_rs_smh_13w_pct"),
        "ret_20d_pct":tech.get("ret_20d_pct"),"ret_60d_pct":tech.get("ret_60d_pct"),
        "weekly_ret_13w_pct":tech.get("weekly_ret_13w_pct"),"weekly_ret_26w_pct":tech.get("weekly_ret_26w_pct"),
        "ema21":tech.get("ema21"),"ma50":tech.get("ma50"),"ma200":tech.get("ma200"),
        "weekly_ema10":tech.get("weekly_ema10"),"weekly_ema30":tech.get("weekly_ema30"),
        "next_rev_growth_est":research.get("fmp_forward_revenue_growth",research.get("next_rev_growth_est")),
        "next_eps_growth_est":research.get("fmp_forward_eps_growth",research.get("next_eps_growth_est")),
        "eps_revision_pct_30d":research.get("eps_est_revision_pct_30d"),"forward_pe":research.get("forward_pe"),
        "fcf_margin":research.get("fcf_margin"),"operating_margin":research.get("operating_margin"),
        "analyst_upside_pct":research.get("analyst_upside_pct"),"next_earnings_date":research.get("next_earnings_date"),"days_to_earnings":research.get("days_to_earnings"),"guidance_tone":research.get("guidance_tone"),
        "guidance_available":research.get("guidance_available"),"guidance_snippets":research.get("guidance_snippets",[]),
        "positives":positives,"risks":risks,"owned":owned,"avg_cost":avg_cost,"holding_note":holding_note,
        **plan,
    }
