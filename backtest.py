"""Historical daily/weekly TECHNICAL-ONLY proxy backtest. No historical fundamentals."""
import json
from pathlib import Path
import numpy as np
import pandas as pd
import yfinance as yf
from universe import UNIVERSE

OUT=Path('docs/data'); OUT.mkdir(parents=True,exist_ok=True)
HORIZONS=(5,10,20)

def run():
    symbols=list(dict.fromkeys(UNIVERSE if isinstance(UNIVERSE,list) else list(UNIVERSE.keys())))
    symbols=[s if isinstance(s,str) else s.get('symbol','') for s in symbols]
    symbols=[s for s in symbols if s]
    symbols=list(dict.fromkeys(symbols+['SMH']))
    raw=yf.download(symbols,period='3y',interval='1d',auto_adjust=True,progress=False,threads=False,group_by='ticker')
    results=[]
    for symbol in symbols:
        if symbol=='SMH': continue
        try:
            df=raw[symbol].dropna(subset=['Close']).copy()
            if len(df)<260: continue
            c=df['Close'].astype(float); v=df['Volume'].astype(float)
            e21=c.ewm(span=21,adjust=False).mean(); m50=c.rolling(50).mean(); m200=c.rolling(200).mean()
            r=c.pct_change(20); rs=c.pct_change(60)
            delta=c.diff(); ups=delta.clip(lower=0).ewm(alpha=1/14,adjust=False).mean(); downs=(-delta.clip(upper=0)).ewm(alpha=1/14,adjust=False).mean()
            rsi=100-100/(1+ups/downs.replace(0,np.nan))
            prior20=c.shift(1).rolling(20).max(); volratio=v/v.shift(1).rolling(20).median()
            # Strictly completed weekly candles: prior Friday close and historical weekly moving averages.
            weekly=c.resample('W-FRI').last().dropna(); w10=weekly.ewm(span=10,adjust=False).mean(); w30=weekly.ewm(span=30,adjust=False).mean()
            wk_good=((weekly>w10)&(w10>w30)).shift(1).reindex(c.index,method='ffill').fillna(False)
            # Proxy score out of 100: no future financial/guidance information is used.
            score=(20*(c>e21)+15*(e21>m50)+15*(m50>m200)+10*(r>0)+10*(rs>0)+
                   10*(rsi.between(45,70))+10*(c>prior20)+5*(volratio>1.3)+5*wk_good).astype(float)
            # Decisions after close t; buy next session open, exit at close t+h (h sessions from signal).
            for i in range(220,len(df)-21):
                if score.iloc[i]<80 or score.iloc[i-1]>=80: continue
                if pd.isna(df['Open'].iloc[i+1]) or df['Open'].iloc[i+1]<=0: continue
                entry=float(df['Open'].iloc[i+1]); date=str(df.index[i].date())
                rec={'symbol':symbol,'signal_date':date,'proxy_score':float(score.iloc[i]),'entry_next_open':entry}
                for h in HORIZONS:
                    ret=float(df['Close'].iloc[i+h]/entry-1)*100
                    rec[f'return_{h}d_pct']=round(ret,3)
                results.append(rec)
        except Exception as exc:
            print('SKIP',symbol,str(exc)[:120])
    trades=pd.DataFrame(results)
    if trades.empty: raise RuntimeError('No valid signals; check market data / symbols')
    trades.to_csv(OUT/'backtest_trades.csv',index=False)
    summary=[]
    for h in HORIZONS:
        x=trades[f'return_{h}d_pct'].dropna()
        summary.append({'horizon_days':h,'signals':int(len(x)),'mean_return_pct':round(float(x.mean()),3),'median_return_pct':round(float(x.median()),3),'win_rate_pct':round(float((x>0).mean()*100),2),'worst_pct':round(float(x.min()),3)})
    (OUT/'backtest_summary.json').write_text(json.dumps({'method':'TECHNICAL-ONLY proxy; NOT the v3 fundamental+guidance score','execution':'signal at close, entry next session open, exit h sessions after signal at close','period':'3y download; warmup ~220 trading days','bias_notes':'Survivorship bias: present-day universe; no delisted names. Overlapping trades; no costs, spread, slippage or tax. Historical guidance unavailable. No out-of-sample optimization.','summary':summary},ensure_ascii=False,indent=2))
    print(pd.DataFrame(summary).to_string(index=False))
if __name__=='__main__':run()
