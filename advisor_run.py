from __future__ import annotations

import json, os, time
from datetime import datetime, timezone
from pathlib import Path
import pandas as pd
import requests
import yfinance as yf
from dotenv import load_dotenv

from advisor import score_stock
from fundamentals import research_symbol
from regime import classify_latest_regime
from universe import AI_UNIVERSE, UNIVERSE, BENCHMARKS, DEFAULT_RESEARCH_LIMIT
from config import SECTOR_ETFS
from data_sources import fetch_yfinance_daily
from technical import analyze_swing, technical_score
from notifier import send_discord

ROOT=Path(__file__).resolve().parent
DOCS=ROOT/"docs"; DATA=DOCS/"data"; STATE=ROOT/"state"
DATA.mkdir(parents=True,exist_ok=True); STATE.mkdir(parents=True,exist_ok=True)

def json_safe(v):
    """Convert NaN/Infinity/numpy scalars into strict browser-safe JSON."""
    if isinstance(v, dict):
        return {str(k): json_safe(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)):
        return [json_safe(x) for x in v]
    try:
        if hasattr(v, "item") and not isinstance(v, (str, bytes)):
            v = v.item()
    except Exception:
        pass
    if isinstance(v, float):
        if pd.isna(v) or v == float("inf") or v == float("-inf"):
            return None
    try:
        if pd.isna(v):
            return None
    except Exception:
        pass
    return v


def load_json(path, default):
    try: return json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception: return default

def remote_json(name):
    base=os.getenv("PAGES_BASE_URL","").rstrip("/")
    if not base:return None
    try:
        r=requests.get(f"{base}/data/{name}?t={int(time.time())}",timeout=12)
        return r.json() if r.ok else None
    except Exception:return None

def group_for(sym):
    return next((g for g,ss in AI_UNIVERSE.items() if sym in ss),"OTHER")

def load_portfolio():
    p=ROOT/"portfolio.json"; data=load_json(p,{"positions":[]}) if p.exists() else {"positions":[]}
    return {str(x.get("symbol","")).upper():x for x in data.get("positions",[]) if x.get("symbol")}

def fetch_daily_ohlcv(symbols):
    raw=yf.download(tickers=symbols,period="1y",interval="1d",auto_adjust=True,group_by="ticker",threads=True,progress=False)
    out={}
    if raw.empty:return out
    if isinstance(raw.columns,pd.MultiIndex):
        l0=set(raw.columns.get_level_values(0)); l1=set(raw.columns.get_level_values(1))
        for s in symbols:
            try:
                d=raw[s].copy() if s in l0 else raw.xs(s,axis=1,level=1).copy() if s in l1 else None
                if d is None:continue
                d.columns=[str(c).lower() for c in d.columns]
                if "close" in d.columns:out[s]=d.dropna(subset=["close"])
            except Exception:pass
    return out

def build_screening(frames, smh):
    rows=[]
    for s in UNIVERSE:
        tech=analyze_swing(frames.get(s,pd.DataFrame()),smh)
        try: ts,dts,wts,pos,risks=technical_score(tech)
        except Exception: ts=dts=wts=0; pos=[]; risks=["価格データ不足"]
        # Technical score is 40 max. Convert to a 100-point first-stage score.
        screen=max(0,min(100,ts/40*100))
        rows.append({
            "symbol":s,"group":group_for(s),"screen_score":round(screen,1),
            "technical_score":round(ts,1),"daily_technical_score":round(dts,1),"weekly_technical_score":round(wts,1),
            "price":tech.get("price"),"rsi14":tech.get("rsi14"),"weekly_rsi14":tech.get("weekly_rsi14"),
            "ret_20d_pct":tech.get("ret_20d_pct"),"ret_60d_pct":tech.get("ret_60d_pct"),"weekly_ret_13w_pct":tech.get("weekly_ret_13w_pct"),
            "rs_smh_20d_pct":tech.get("rs_smh_20d_pct"),"weekly_rs_smh_13w_pct":tech.get("weekly_rs_smh_13w_pct"),
            "positives":pos[:5],"risks":risks[:5]
        })
    rows.sort(key=lambda x:x["screen_score"],reverse=True)
    return rows

def research_cache(symbols):
    max_age_hours=float(os.getenv("FUNDAMENTAL_CACHE_HOURS","20"))
    existing=remote_json("fundamentals.json") or load_json(DATA/"fundamentals.json",{})
    updated=existing.get("updated_at") if isinstance(existing,dict) else None
    fresh=False
    if updated:
        try:fresh=(datetime.now(timezone.utc)-datetime.fromisoformat(updated.replace("Z","+00:00"))).total_seconds()/3600<max_age_hours
        except Exception:pass
    items=(existing.get("items",{}) if isinstance(existing,dict) else {}) or {}
    missing=[s for s in symbols if s not in items]
    targets=missing if fresh else symbols
    for i,s in enumerate(targets,1):
        try:
            print(f"research {i}/{len(targets)} {s}"); items[s]=research_symbol(s,use_fmp=True)
        except Exception as e:
            print(f"research failed {s}: {e}"); items.setdefault(s,{"symbol":s,"name":s,"source":"error"})
        time.sleep(float(os.getenv("RESEARCH_SLEEP","0.15")))
    payload={"updated_at":datetime.now(timezone.utc).isoformat(),"items":items}
    (DATA/"fundamentals.json").write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding="utf-8")
    return items,bool(targets)

def notify_signals(ranked, regime, previous):
    threshold=float(os.getenv("ADVISOR_ALERT_SCORE","80")); jump=int(os.getenv("RANK_JUMP_ALERT","10"))
    old={x.get("symbol"):x for x in (previous or {}).get("ranking",[]) if x.get("symbol")}
    alerts=[]
    for rank,x in enumerate(ranked,1):
        prev=old.get(x["symbol"],{}); old_rank=prev.get("rank"); old_action=prev.get("action")
        reasons=[]
        if x["score"]>=threshold and (not prev or float(prev.get("score",0))<threshold):reasons.append(f"{int(threshold)}点突破")
        if old_rank and old_rank-rank>=jump:reasons.append(f"順位↑ {old_rank}→{rank}")
        buy_actions={"スイング・エントリー候補","スイング・ブレイク候補"}
        if x.get("action") in buy_actions and old_action not in buy_actions:reasons.append("新規BUY候補")
        if x.get("owned") and old_action and old_action!=x.get("action"):reasons.append("保有銘柄シグナル変化")
        if reasons:alerts.append((rank,x,reasons))
    if alerts:
        lines=[f"📊 Swing Advisor | {regime.get('regime_jp','市場判定')} | 重要変化"]
        for rank,x,reasons in alerts[:8]:
            lines.append(f"#{rank} {x['symbol']} {x['score']}/100 {x['action']} | {' / '.join(reasons)}")
        base=os.getenv("PAGES_BASE_URL","").rstrip("/")
        if base:lines.append(f"Safari: {base}/")
        try:send_discord("\n".join(lines))
        except Exception as e:print("discord",e)
    return {"updated_at":datetime.now(timezone.utc).isoformat(),"ranking":[{"symbol":x["symbol"],"rank":i,"score":x["score"],"action":x.get("action")} for i,x in enumerate(ranked,1)]}

def main():
    load_dotenv(ROOT/".env")
    all_syms=sorted(set(UNIVERSE+BENCHMARKS+list(SECTOR_ETFS.values())))
    print("universe",len(UNIVERSE),"symbols")
    frames=fetch_daily_ohlcv(all_syms)
    smh=frames.get("SMH",pd.DataFrame()).get("close",pd.Series(dtype=float))
    close=fetch_yfinance_daily(all_syms,period="9mo")
    regime=classify_latest_regime(close) if not close.empty else {}

    screening=build_screening(frames,smh)
    limit=int(os.getenv("RESEARCH_LIMIT",str(DEFAULT_RESEARCH_LIMIT)))
    shortlist=[x["symbol"] for x in screening[:limit]]
    # Always include owned positions in detailed research.
    portfolio=load_portfolio()
    shortlist=list(dict.fromkeys(shortlist+list(portfolio.keys())))
    fundamentals,refreshed=research_cache(shortlist)

    ranked=[]
    for s in shortlist:
        tech=analyze_swing(frames.get(s,pd.DataFrame()),smh); res=fundamentals.get(s,{"symbol":s,"name":s}); pos=portfolio.get(s)
        ranked.append(score_stock(s,group_for(s),res,tech,regime,owned=bool(pos),avg_cost=(pos or {}).get("avg_cost")))
    ranked.sort(key=lambda x:(x["score"],x["confidence"]),reverse=True)

    previous=remote_json("advisor_state.json") or load_json(STATE/"advisor_state.json",{})
    new_state=notify_signals(ranked,regime,previous)
    (STATE/"advisor_state.json").write_text(json.dumps(new_state,ensure_ascii=False,indent=2),encoding="utf-8")
    (DATA/"advisor_state.json").write_text(json.dumps(json_safe(new_state),ensure_ascii=False,indent=2,allow_nan=False),encoding="utf-8")
    payload={"updated_at":datetime.now(timezone.utc).isoformat(),"regime":regime,"universe_count":len(UNIVERSE),"detailed_count":len(ranked),"fundamentals_refreshed":refreshed,"ranking":ranked,"screening":screening,"portfolio_symbols":list(portfolio.keys()),"methodology":{"weights":"一次: 日足+週足テクニカルで全銘柄を100点換算。上位40を Technical 40 + Forward/Guidance 25 + Quality 20 + Valuation 10 + Regime ±5 - Risk で詳細評価","technical":"5分足など短期足は不使用。日足25点 + 週足15点。21EMA/50DMA/200DMA, RSI, MACD, breakout, SMH相対強度, ATRを使用。","warning":"機械的な意思決定支援であり利益を保証する売買指示ではありません。発注前に一次情報とブローカー価格を確認してください。"}}
    (DATA/"advisor.json").write_text(json.dumps(json_safe(payload),ensure_ascii=False,indent=2,allow_nan=False,default=lambda o:None),encoding="utf-8")
    print("advisor updated",payload["updated_at"],"screened",len(screening),"detailed",len(ranked),"top",[(x['symbol'],x['score']) for x in ranked[:5]])

if __name__=="__main__":main()
