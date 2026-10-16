from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from config import AI_GROUPS, BENCHMARKS, SECTOR_ETFS, WATCHLIST
from data_sources import fetch_yfinance_daily
from regime import build_ai_group_returns, classify_latest_regime

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "output"
OUT.mkdir(exist_ok=True)


def compound(r: pd.Series) -> float:
    r = r.dropna()
    return float((1 + r).prod() - 1) if len(r) else np.nan


def build_stats(close: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.Series]:
    ret = close.pct_change(fill_method=None)
    groups, ai = build_ai_group_returns(close)
    stats = []

    for name, ticker in SECTOR_ETFS.items():
        if ticker not in ret.columns:
            continue
        s = ret[ticker]
        aligned = pd.concat([ai.rename("ai"), s.rename("sector"), ret.get("SPY", pd.Series(index=ret.index, dtype=float)).rename("spy")], axis=1).dropna(subset=["ai", "sector"])
        if len(aligned) < 20:
            continue

        cond_up = aligned["sector"] >= 0.0075
        cond_rel = (aligned["sector"] - aligned["spy"]) >= 0.005 if "spy" in aligned else pd.Series(False, index=aligned.index)
        cross = (aligned["sector"] > 0) & (aligned["ai"] < 0)

        corr = aligned["ai"].corr(aligned["sector"])
        rolling20 = aligned["ai"].rolling(20).corr(aligned["sector"])
        lead_corr = aligned["sector"].corr(aligned["ai"].shift(-1))

        stats.append({
            "sector": name,
            "ticker": ticker,
            "period_return_pct": compound(aligned["sector"]) * 100,
            "corr_ai_daily": corr,
            "corr_ai_latest20d": rolling20.dropna().iloc[-1] if rolling20.notna().any() else np.nan,
            "corr_ai_avg20d": rolling20.mean(),
            "sector_up_gt_0.75_days": int(cond_up.sum()),
            "p_ai_down_given_sector_up_gt_0.75": float((aligned.loc[cond_up, "ai"] < 0).mean()) if cond_up.any() else np.nan,
            "avg_ai_return_when_sector_up_gt_0.75_pct": float(aligned.loc[cond_up, "ai"].mean() * 100) if cond_up.any() else np.nan,
            "sector_beats_spy_gt_0.5_days": int(cond_rel.sum()),
            "p_ai_down_given_sector_beats_spy_gt_0.5": float((aligned.loc[cond_rel, "ai"] < 0).mean()) if cond_rel.any() else np.nan,
            "sector_up_ai_down_days": int(cross.sum()),
            "sector_up_ai_down_share": float(cross.mean()),
            "lead_corr_sector_today_vs_ai_tomorrow": lead_corr,
        })

    stats_df = pd.DataFrame(stats)
    if not stats_df.empty:
        stats_df = stats_df.sort_values(
            ["p_ai_down_given_sector_up_gt_0.75", "sector_up_ai_down_days"],
            ascending=[False, False],
        )
    return stats_df, groups, ai


def save_charts(close: pd.DataFrame, ai: pd.Series):
    ret = close.pct_change(fill_method=None)
    series = {"AI basket": ai}
    for ticker in ["SMH", "XLV", "XLE", "XLF", "XLP", "XLK", "SPY"]:
        if ticker in ret.columns:
            series[ticker] = ret[ticker]
    df = pd.DataFrame(series).dropna(how="all")
    growth = (1 + df.fillna(0)).cumprod() * 100

    plt.figure(figsize=(12, 7))
    for c in growth.columns:
        plt.plot(growth.index, growth[c], label=c)
    plt.axhline(100, linewidth=0.8)
    plt.title("AI basket vs sectors (start = 100)")
    plt.ylabel("Growth index")
    plt.legend(ncol=2)
    plt.tight_layout()
    plt.savefig(OUT / "ai_vs_sectors.png", dpi=160)
    plt.close()

    if "SMH" in ret.columns:
        rel = pd.DataFrame({
            "AI basket": ai,
            "Health Care - AI": ret.get("XLV") - ai if "XLV" in ret else np.nan,
            "Energy - AI": ret.get("XLE") - ai if "XLE" in ret else np.nan,
            "Financials - AI": ret.get("XLF") - ai if "XLF" in ret else np.nan,
            "Staples - AI": ret.get("XLP") - ai if "XLP" in ret else np.nan,
        })
        rolling = rel.drop(columns=["AI basket"]).rolling(10).sum() * 100
        plt.figure(figsize=(12, 7))
        for c in rolling.columns:
            plt.plot(rolling.index, rolling[c], label=c)
        plt.axhline(0, linewidth=0.8)
        plt.title("10-day relative return vs AI basket")
        plt.ylabel("percentage points")
        plt.legend()
        plt.tight_layout()
        plt.savefig(OUT / "sector_rotation_10d.png", dpi=160)
        plt.close()


def write_text_report(stats: pd.DataFrame, regime: dict, ai: pd.Series):
    ai_ret = compound(ai) * 100
    lines = [
        "AI MARKET ROTATION REPORT",
        "=" * 72,
        f"Latest regime: {regime.get('regime_jp')} ({regime.get('regime')})",
        f"Latest date: {regime.get('date')}",
        f"Latest AI basket: {regime.get('ai_basket_pct')}%",
        f"Latest non-AI core median: {regime.get('non_ai_core_median_pct')}%",
        f"AI basket compounded return over downloaded period: {ai_ret:.2f}%",
        "",
        "Interpretation:",
        "- p_ai_down_given_sector_up_gt_0.75 が高いほど、そのセクターの強い日にAIが下がりやすかった。",
        "- 相関は因果関係ではない。サンプルが少ない条件付き確率は過信しない。",
        "- lead_corr は探索用であり、予測力を意味しない。",
        "",
    ]
    if not stats.empty:
        show = stats[[
            "sector", "ticker", "period_return_pct", "corr_ai_daily",
            "p_ai_down_given_sector_up_gt_0.75", "sector_up_gt_0.75_days",
            "sector_up_ai_down_days"
        ]].copy()
        lines.append(show.to_string(index=False, float_format=lambda x: f"{x:.3f}"))
    (OUT / "rotation_report.txt").write_text("\n".join(lines), encoding="utf-8")


def main():
    p = argparse.ArgumentParser(description="AIバスケットとS&Pセクターのローテーション分析")
    p.add_argument("--period", default="6mo", help="yfinance period例: 3mo, 6mo, 1y")
    args = p.parse_args()

    symbols = WATCHLIST + BENCHMARKS + list(SECTOR_ETFS.values())
    print(f"Downloading daily data: period={args.period}, symbols={len(symbols)}")
    close = fetch_yfinance_daily(symbols, period=args.period)
    if close.empty:
        raise SystemExit("データ取得に失敗しました。ネット接続やyfinanceを確認してください。")

    stats, groups, ai = build_stats(close)
    regime = classify_latest_regime(close)

    close.to_csv(OUT / "daily_close.csv")
    groups.to_csv(OUT / "ai_group_daily_returns.csv")
    ai.to_csv(OUT / "ai_basket_daily_returns.csv")
    stats.to_csv(OUT / "rotation_stats.csv", index=False)
    (OUT / "market_regime.json").write_text(json.dumps(regime, ensure_ascii=False, indent=2), encoding="utf-8")
    save_charts(close, ai)
    write_text_report(stats, regime, ai)

    print(f"Latest regime: {regime['regime_jp']}")
    print(f"AI basket: {regime['ai_basket_pct']}% | non-AI median: {regime['non_ai_core_median_pct']}%")
    if not stats.empty:
        cols = ["sector", "ticker", "period_return_pct", "corr_ai_daily", "p_ai_down_given_sector_up_gt_0.75", "sector_up_gt_0.75_days"]
        print("\n" + stats[cols].to_string(index=False, float_format=lambda x: f"{x:.3f}"))
    print(f"\nSaved to: {OUT}")


if __name__ == "__main__":
    main()
