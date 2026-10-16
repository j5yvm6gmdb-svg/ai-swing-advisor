from __future__ import annotations
from universe import AI_UNIVERSE

AI_GROUPS = AI_UNIVERSE
WATCHLIST = sorted({s for symbols in AI_GROUPS.values() for s in symbols})
BENCHMARKS = ["SPY", "QQQ", "SMH"]

SECTOR_ETFS = {
    "Health Care": "XLV",
    "Energy": "XLE",
    "Financials": "XLF",
    "Consumer Staples": "XLP",
    "Utilities": "XLU",
    "Real Estate": "XLRE",
    "Industrials": "XLI",
    "Materials": "XLB",
    "Consumer Discretionary": "XLY",
    "Communication Services": "XLC",
    "Technology": "XLK",
}
DEFENSIVE_VALUE_CORE = ["XLV", "XLE", "XLF", "XLP", "XLU", "XLRE", "XLI", "XLB"]

ALERT_RULES = {
    "volume_ratio": 2.0,
    "breakout_20bars": True,
}
