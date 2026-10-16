from __future__ import annotations

# Broad US swing-trading universe. The first stage screens all names with daily/weekly
# price action; only the strongest names are sent to the slower fundamental research stage.
MARKET_UNIVERSE = {
    "MEGA_CAP_TECH": ["AAPL","MSFT","GOOGL","GOOG","AMZN","META","NFLX","ORCL","CRM","NOW","ADBE","INTU","PANW","CRWD","FTNT","DDOG","NET","SNOW","MDB","PLTR"],
    "SEMICONDUCTORS": ["NVDA","AMD","AVGO","QCOM","ARM","MU","SNDK","TSM","ASML","AMAT","LRCX","KLAC","MRVL","CRDO","ADI","TXN","NXPI","MCHP","ON","MPWR","SWKS","QRVO","WOLF","INTC","GFS"],
    "AI_NETWORK_OPTICAL": ["ANET","LITE","COHR","AAOI","CIEN","FN","GLW","APH","TEL","KEYS","DELL","HPE","SMCI","VRT","ETN","PWR","HUBB","NVT","GEV"],
    "AI_DATACENTER_POWER": ["IREN","NBIS","CRWV","APLD","CEG","VST","NRG","TLN","OKLO","SMR","CCJ","BWXT","LEU"],
    "EDA_INDUSTRIAL_TECH": ["SNPS","CDNS","ROP","PH","EMR","ROK","HON","MMM","GE","RTX","LMT","NOC","GD","TDG","HEI","AXON"],
    "FINANCIALS": ["JPM","BAC","WFC","C","GS","MS","SCHW","BLK","BX","KKR","APO","COF","AXP","V","MA","PYPL","HOOD","IBKR","CME","ICE"],
    "ENERGY": ["XOM","CVX","COP","EOG","OXY","SLB","HAL","MPC","VLO","PSX","LNG","WMB","KMI","OKE","FANG","DVN","EQT","BKR"],
    "INDUSTRIALS": ["CAT","DE","URI","PCAR","CMI","FAST","GWW","UNP","CSX","NSC","UPS","FDX","DAL","UAL","LUV","UBER","DASH"],
    "CONSUMER": ["WMT","COST","TGT","HD","LOW","NKE","SBUX","MCD","CMG","YUM","BKNG","ABNB","MAR","HLT","RCL","CCL","GM","F","TSLA","RIVN"],
    "HEALTHCARE": ["LLY","NVO","JNJ","ABBV","MRK","PFE","BMY","AMGN","GILD","VRTX","REGN","ISRG","SYK","BSX","MDT","ABT","TMO","DHR","UNH","CI","HCA"],
    "COMMUNICATION_MEDIA": ["DIS","CMCSA","T","VZ","TMUS","SPOT","RDDT","PINS","SNAP","TTD","ROKU"],
    "MATERIALS_MINING": ["LIN","FCX","NEM","GOLD","SCCO","AA","CLF","STLD","NUE","MP","ALB"],
    "DEFENSIVE_REITS": ["PG","KO","PEP","PM","MO","CL","KMB","MDLZ","NEE","SO","DUK","AEP","SRE","PLD","AMT","EQIX","DLR","O","SPG"],
    "GROWTH_FINTECH_CRYPTO": ["COIN","MSTR","MARA","RIOT","CLSK","SOFI","AFRM","NU","XYZ","SHOP","MELI","SE","GRAB"],
}

# Backward-compatible name used by the rest of the project.
AI_UNIVERSE = MARKET_UNIVERSE
UNIVERSE = sorted({s for names in MARKET_UNIVERSE.values() for s in names})
BENCHMARKS = ["SPY", "QQQ", "SMH"]
DEFAULT_RESEARCH_LIMIT = 40
