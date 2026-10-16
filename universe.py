from __future__ import annotations

# AIの恩恵が比較的直接的な企業を中心に、AIインフラ全体を横断するユニバース。
# 銘柄の追加・削除はこのファイルだけ編集すればよい。
AI_UNIVERSE = {
    "GPU_COMPUTE": ["NVDA", "AMD", "AVGO", "ARM", "QCOM"],
    "MEMORY_STORAGE": ["MU", "SNDK"],
    "FOUNDRY_EQUIPMENT": ["TSM", "ASML", "AMAT", "LRCX", "KLAC"],
    "NETWORK_OPTICAL": ["ANET", "MRVL", "CRDO", "LITE", "COHR", "AAOI", "CIEN", "FN"],
    "POWER_COOLING": ["VRT", "ETN", "PWR", "HUBB", "NVT"],
    "SERVER_HARDWARE": ["DELL", "HPE", "SMCI"],
    "AI_POWER_ENERGY": ["CEG", "VST", "GEV"],
    "CLOUD_PLATFORM": ["MSFT", "GOOGL", "AMZN", "META", "ORCL"],
    "AI_DATACENTER": ["IREN", "NBIS", "CRWV", "APLD"],
    "EDA_SOFTWARE": ["SNPS", "CDNS", "PLTR"],
}

UNIVERSE = sorted({s for names in AI_UNIVERSE.values() for s in names})
BENCHMARKS = ["SPY", "QQQ", "SMH"]

# 業績調査の同時実行数を抑えるための標準値。
# GitHub Actions上でレート制限が出る場合は小さくする。
DEFAULT_RESEARCH_LIMIT = 40
