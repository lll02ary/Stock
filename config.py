"""
選股參數設定檔
想調整策略時，只要改這個檔案的數字就好，不需要動其他程式。
"""

# ── 基本過濾 ──────────────────────────────────────────
MIN_AVG_VOLUME_LOTS = 500          # 5 日均量至少幾張（1 張 = 1000 股）

# ── 型態 ①：趨勢扭轉（剛站上 5MA / 10MA）──────────────
TURN_MIN_DAYS_BELOW = 5            # 站上之前，至少連續幾天收盤在均線之下
TURN_MAX_DAYS_CHECK = 10           # 最多往回看幾天（只用於顯示）
SCORE_TURN_ONE_LINE = 30           # 只站上 5MA 或 10MA 其中一條
SCORE_TURN_BOTH = 40               # 同時站上 5MA 與 10MA

# ── 型態 ②：空頭爆量搶反彈 ────────────────────────────
REBOUND_VOLUME_RATIO = 2.0         # 今日量 ≥ 前 5 日均量的幾倍才算爆量
REBOUND_SHADOW_TO_BODY = 1.5       # 長下影線：下影線長度 ≥ K 棒實體的幾倍
REBOUND_SHADOW_MIN_PCT = 1.0       # 長下影線：下影線長度至少佔收盤價幾 %
SCORE_REBOUND = 30

# ── 型態 ③：箱型量增 ──────────────────────────────────
BOX_DAYS = 60                      # 箱型觀察天數
BOX_MAX_RANGE_PCT = 15.0           # 箱型內最高與最低價差不超過幾 %
SCORE_BOX = 30

# ── 輔助指標（加分）───────────────────────────────────
SCORE_MACD_FIRST_RED = 10          # MACD 柱狀體第一根翻紅
SCORE_KD_GOLDEN = 10               # KD 黃金交叉（今天或昨天）
SCORE_RSI_CROSS_50 = 10            # RSI6 由 50 以下突破 50

KD_PERIOD = 9
RSI_PERIOD = 6
MACD_FAST, MACD_SLOW, MACD_SIGNAL = 12, 26, 9

# ── 資金輪動（族群熱度）────────────────────────────────
# 各項目在族群熱度分數中的權重，合計 1.0
ROTATION_WEIGHTS = {
    "share_vs_20d": 0.40,   # 今日成交金額占比 ÷ 前 20 日平均占比
    "share_5d_vs_20d": 0.20,  # 近 5 日平均占比 ÷ 前 20 日平均占比（輪動延續性）
    "avg_change": 0.20,     # 族群平均漲跌幅
    "up_ratio": 0.20,       # 族群上漲家數比例
}
ROTATION_MIN_MEMBERS = 3           # 成員少於幾檔的族群不列入排名

# ── 綜合前 5 名 ───────────────────────────────────────
# 總分 = 個股分數 ×（1 + 族群熱度/100 × GROUP_HEAT_MAX_BOOST）
GROUP_HEAT_MAX_BOOST = 0.5         # 族群熱度最高可讓個股分數放大幾成（0.5 = 最多 1.5 倍）
TOP_N = 5
LIST_LIMIT = 30                    # 報告中每個清單最多顯示幾檔
EMAIL_SECTORS = 10                 # Email 內文顯示前幾個族群

# ── 資料 ─────────────────────────────────────────────
HISTORY_TRADING_DAYS = 100         # 保存幾個交易日的資料（箱型 60 日＋指標暖身）
REQUEST_INTERVAL_SEC = 3.5         # 每次向證交所 / 櫃買中心請求的間隔，太快會被暫時封鎖
