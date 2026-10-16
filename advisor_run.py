from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
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
from technical import analyze_swing
from notifier import send_discord

ROOT=Path(__file__).resolve().parent
DOCS=ROOT/"docs"; DATA=DOCS/"data"; STATE=ROOT/"state"
DATA.mkdir(parents=True,exist_ok=True); STATE.mkdir(parents=True,exist_ok=True)


def load_json(path, default):
    try: return json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception: return default


def remote_json(name):
    base=os.getenv("PAGES_BASE_URL","").rstrip("/")
    if not base: return None
    try:
        r=requests.get(f"{base}/data/{name}?t={int(time.time())}",timeout=12)
        return r.json() if r.ok else None
    except Exception:return None


def group_for(sym):
    return next((g for g,ss in AI_UNIVERSE.items() if sym in ss),"OTHER")


def load_portfolio():
    p=ROOT/"portfolio.json"
    data=load_json(p,{"positions":[]}) if p.exists() else {"positions":[]}
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
                if "close" in d.columns: out[s]=d.dropna(subset=["close"])
            except Exception:pass
    elif len(symbols)==1:
        d=raw.copy(); d.columns=[str(c).lower() for c in d.columns]; out[symbols[0]]=d
    return out


def research_cache(symbols):
    max_age_hours=float(os.getenv("FUNDAMENTAL_CACHE_HOURS","20"))
    existing=remote_json("fundamentals.json") or load_json(DATA/"fundamentals.json",{})
    updated=existing.get("updated_at") if isinstance(existing,dict) else None
    fresh=False
    if updated:
        try:
            age=(datetime.now(timezone.utc)-datetime.fromisoformat(updated.replace("Z","+00:00"))).total_seconds()/3600
            fresh=age<max_age_hours
        except Exception: pass
    items=(existing.get("items",{}) if isinstance(existing,dict) else {}) or {}
    if fresh and all(s in items for s in symbols): return items, False

    limit=int(os.getenv("RESEARCH_LIMIT",str(DEFAULT_RESEARCH_LIMIT)))
    for i,s in enumerate(symbols[:limit],1):
        try:
            print(f"research {i}/{min(limit,len(symbols))} {s}")
            items[s]=research_symbol(s,use_fmp=True)
        except Exception as e:
            print(f"research failed {s}: {e}")
            items.setdefault(s,{"symbol":s,"name":s,"source":"error"})
        time.sleep(float(os.getenv("RESEARCH_SLEEP","0.15")))
    payload={"updated_at":datetime.now(timezone.utc).isoformat(),"items":items}
    (DATA/"fundamentals.json").write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding="utf-8")
    return items, True


def notify_top(ranked, regime, previous):
    threshold=float(os.getenv("ADVISOR_ALERT_SCORE","80"))
    top=[x for x in ranked if x["score"]>=threshold and x["action"] not in {"見送り","中立・確認待ち"}][:5]
    prev_syms=set(previous.get("top_symbols",[])) if previous else set()
    new=[x for x in top if x["symbol"] not in prev_syms]
    if new:
        lines=[f"📊 AI ADVISOR 新規上位候補 | {regime.get('regime_jp','')}" ]
        for x in new[:3]:
            lines.append(f"{x['symbol']} {x['score']}/100 {x['action']} ${x['price']} | Tech {x['technical_score']}/40 Forward {x['forward_score']}/25")
        try: send_discord("\n".join(lines))
        except Exception as e: print("discord",e)
    return {"top_symbols":[x["symbol"] for x in top],"updated_at":datetime.now(timezone.utc).isoformat()}


def main():
    load_dotenv(ROOT/".env")
    all_syms=UNIVERSE+BENCHMARKS+list(SECTOR_ETFS.values())
    frames=fetch_daily_ohlcv(all_syms)
    smh=frames.get("SMH",pd.DataFrame()).get("close",pd.Series(dtype=float))
    close=fetch_yfinance_daily(all_syms,period="9mo")
    regime=classify_latest_regime(close) if not close.empty else {}

    fundamentals,refreshed=research_cache(UNIVERSE)
    portfolio=load_portfolio()

    ranked=[]
    for s in UNIVERSE:
        tech=analyze_swing(frames.get(s,pd.DataFrame()),smh)
        res=fundamentals.get(s,{"symbol":s,"name":s})
        pos=portfolio.get(s)
        ranked.append(score_stock(s,group_for(s),res,tech,regime,owned=bool(pos),avg_cost=(pos or {}).get("avg_cost")))
    ranked.sort(key=lambda x:(x["score"],x["confidence"]),reverse=True)

    previous=remote_json("advisor_state.json") or load_json(STATE/"advisor_state.json",{})
    new_state=notify_top(ranked,regime,previous)
    (STATE/"advisor_state.json").write_text(json.dumps(new_state,ensure_ascii=False,indent=2),encoding="utf-8")
    (DATA/"advisor_state.json").write_text(json.dumps(new_state,ensure_ascii=False,indent=2),encoding="utf-8")

    payload={
        "updated_at":datetime.now(timezone.utc).isoformat(),"regime":regime,"fundamentals_refreshed":refreshed,
        "ranking":ranked,"portfolio_symbols":list(portfolio.keys()),
        "methodology":{
            "weights":"Technical 40 + Forward/Guidance 25 + Fundamental Quality 20 + Valuation 10 + Regime ±5 - Risk penalty",
            "technical":"スイング向け日足25点 + 週足15点。日足: 21EMA/50DMA/200DMA, RSI, MACD, 20日ブレイク, 20/60日SMH相対強度, ATR。週足: 10週EMA/30週EMA, RSI, MACD, 13週高値, 13週SMH相対強度",
            "forward":"翌期売上/EPS成長予想, EPS予想修正, 決算サプライズ, アナリスト目標; FMP利用時は決算コールのguidance/outlookトーンも加点",
            "warning":"これは機械的な意思決定支援であり、利益を保証する売買指示ではありません。特にyfinance・トランスクリプトの自動抽出には欠損/遅延/誤解釈があり得ます。発注前に一次情報とブローカー価格を確認してください。"
        }
    }
    (DATA/"advisor.json").write_text(json.dumps(payload,ensure_ascii=False,indent=2,default=lambda o:None),encoding="utf-8")
    print("advisor updated",payload["updated_at"],"top",[(x['symbol'],x['score']) for x in ranked[:5]])

if __name__=="__main__": main()
