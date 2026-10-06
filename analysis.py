"""
選股與資金輪動分析。
所有指標都以「日期 × 股票代號」的寬表一次算完，上千檔股票幾秒內就能跑完。
"""
import numpy as np
import pandas as pd

import config


# ── 整理資料 ──────────────────────────────────────────

def build_panels(history: pd.DataFrame, stock_list: pd.DataFrame):
    """把長表轉成寬表（index=日期, columns=代號），只保留普通股。"""
    h = history.copy()
    h["code"] = h["code"].astype(str).str.strip()
    if len(stock_list):
        h = h[h["code"].isin(set(stock_list["code"]))]
    else:  # 抓不到產業分類時：只留 4 碼、非 0 開頭的代號（排除 ETF）
        h = h[h["code"].str.fullmatch(r"[1-9]\d{3}")]
    h = h.drop_duplicates(["date", "code"], keep="last")
    panels = {}
    for col in ("open", "high", "low", "close", "volume", "turnover"):
        panels[col] = h.pivot(index="date", columns="code", values=col).sort_index()
    # 沒有成交的日子收盤價為空，用前一天收盤補，量補 0
    panels["close"] = panels["close"].ffill()
    for col in ("open", "high", "low"):
        panels[col] = panels[col].fillna(panels["close"])
    panels["volume"] = panels["volume"].fillna(0) / 1000  # 股 → 張
    panels["turnover"] = panels["turnover"].fillna(0)
    names = h.sort_values("date").groupby("code")["name"].last()
    return panels, names


# ── 技術指標 ──────────────────────────────────────────

def rsi(close, n):
    diff = close.diff()
    up = diff.clip(lower=0).ewm(alpha=1 / n, adjust=False).mean()
    down = (-diff.clip(upper=0)).ewm(alpha=1 / n, adjust=False).mean()
    rs = up / down.replace(0, np.nan)
    out = 100 - 100 / (1 + rs)
    return out.where(down != 0, 100.0)


def kd(high, low, close, n):
    hh = high.rolling(n).max()
    ll = low.rolling(n).min()
    rsv = ((close - ll) / (hh - ll).replace(0, np.nan) * 100).fillna(50)
    k = np.full(rsv.shape, 50.0)
    d = np.full(rsv.shape, 50.0)
    vals = rsv.to_numpy()
    for i in range(1, len(vals)):
        k[i] = k[i - 1] * 2 / 3 + vals[i] / 3
        d[i] = d[i - 1] * 2 / 3 + k[i] / 3
    return (pd.DataFrame(k, index=rsv.index, columns=rsv.columns),
            pd.DataFrame(d, index=rsv.index, columns=rsv.columns))


def macd_hist(close, fast, slow, signal):
    dif = close.ewm(span=fast, adjust=False).mean() - close.ewm(span=slow, adjust=False).mean()
    dea = dif.ewm(span=signal, adjust=False).mean()
    return dif - dea


def _days_below_before_today(below: pd.DataFrame, max_days: int) -> pd.Series:
    """昨天往回數，連續幾天收盤在均線之下。"""
    arr = below.iloc[-(max_days + 1):-1].to_numpy()[::-1]  # 由昨天往前
    count = np.zeros(arr.shape[1], dtype=int)
    alive = np.ones(arr.shape[1], dtype=bool)
    for row in arr:
        alive &= row
        count += alive
    return pd.Series(count, index=below.columns)


# ── 個股篩選 ──────────────────────────────────────────

def screen_stocks(panels, names, stock_list):
    c, o, h, l, v = (panels[k] for k in ("close", "open", "high", "low", "volume"))
    cfg = config
    ma = {n: c.rolling(n).mean() for n in (5, 10, 20, 60)}
    vol_prev5 = v.shift(1).rolling(5).mean()
    vol_ma = {n: v.rolling(n).mean() for n in (5, 10, 20)}

    t = -1  # 今天
    close_t, open_t, low_t = c.iloc[t], o.iloc[t], l.iloc[t]
    vol_t = v.iloc[t]
    df = pd.DataFrame(index=c.columns)
    df["name"] = names.reindex(df.index)
    df["close"] = close_t
    df["chg_pct"] = (close_t / c.iloc[-2] - 1) * 100
    df["volume"] = vol_t
    df["avg_vol5"] = vol_ma[5].iloc[t]
    df["vol_ratio"] = vol_t / vol_prev5.iloc[t]

    # 基本過濾：資料夠長、5 日均量門檻、今天有成交
    enough = c.notna().sum() >= cfg.BOX_DAYS + 5
    base_ok = enough & (df["avg_vol5"] >= cfg.MIN_AVG_VOLUME_LOTS) & (vol_t > 0)

    # 型態 ①：趨勢扭轉
    below5 = _days_below_before_today(c < ma[5], cfg.TURN_MAX_DAYS_CHECK)
    below10 = _days_below_before_today(c < ma[10], cfg.TURN_MAX_DAYS_CHECK)
    cross5 = (below5 >= cfg.TURN_MIN_DAYS_BELOW) & (close_t > ma[5].iloc[t])
    cross10 = (below10 >= cfg.TURN_MIN_DAYS_BELOW) & (close_t > ma[10].iloc[t])
    df["turn_5"], df["turn_10"] = cross5, cross10
    df["below5_days"], df["below10_days"] = below5, below10
    turn_score = np.where(cross5 & cross10, cfg.SCORE_TURN_BOTH,
                          np.where(cross5 | cross10, cfg.SCORE_TURN_ONE_LINE, 0))

    # 型態 ②：空頭爆量搶反彈（K 棒須收紅或留長下影線）
    m5, m10, m20, m60 = (ma[n].iloc[t] for n in (5, 10, 20, 60))
    bear = (m5 < m10) & (m10 < m20) & (m20 < m60) & (close_t < m5)
    body = (close_t - open_t).abs()
    lower_shadow = np.minimum(open_t, close_t) - low_t
    red_k = close_t > open_t
    long_shadow = (lower_shadow >= cfg.REBOUND_SHADOW_TO_BODY * body) & \
                  (lower_shadow / close_t * 100 >= cfg.REBOUND_SHADOW_MIN_PCT)
    rebound = bear & (df["vol_ratio"] >= cfg.REBOUND_VOLUME_RATIO) & (red_k | long_shadow)
    df["rebound"] = rebound
    df["k_type"] = np.where(red_k & long_shadow, "紅K＋長下影",
                            np.where(red_k, "紅K", np.where(long_shadow, "長下影線", "")))

    # 型態 ③：箱型量增
    box_hi = h.rolling(cfg.BOX_DAYS).max().iloc[t]
    box_lo = l.rolling(cfg.BOX_DAYS).min().iloc[t]
    box_range = (box_hi - box_lo) / box_lo * 100
    vol_up = (vol_ma[5].iloc[t] > vol_ma[10].iloc[t]) & (vol_ma[10].iloc[t] > vol_ma[20].iloc[t])
    box = (box_range <= cfg.BOX_MAX_RANGE_PCT) & vol_up
    df["box"], df["box_range"] = box, box_range

    # 輔助指標
    hist = macd_hist(c, cfg.MACD_FAST, cfg.MACD_SLOW, cfg.MACD_SIGNAL)
    k, d = kd(h, l, c, cfg.KD_PERIOD)
    r = rsi(c, cfg.RSI_PERIOD)
    macd_red = (hist.iloc[-2] <= 0) & (hist.iloc[t] > 0)
    golden_today = (k.iloc[-2] <= d.iloc[-2]) & (k.iloc[t] > d.iloc[t])
    golden_yday = (k.iloc[-3] <= d.iloc[-3]) & (k.iloc[-2] > d.iloc[-2]) & (k.iloc[t] > d.iloc[t])
    kd_golden = golden_today | golden_yday
    rsi_cross = (r.iloc[-2] < 50) & (r.iloc[t] >= 50)
    df["macd_red"], df["kd_golden"], df["rsi_cross"] = macd_red, kd_golden, rsi_cross

    df["main_score"] = turn_score + np.where(box, cfg.SCORE_BOX, 0)
    df["rebound_score"] = np.where(rebound, cfg.SCORE_REBOUND, 0)
    df["aux_score"] = (macd_red * cfg.SCORE_MACD_FIRST_RED + kd_golden * cfg.SCORE_KD_GOLDEN
                       + rsi_cross * cfg.SCORE_RSI_CROSS_50)

    df = df[base_ok.reindex(df.index).fillna(False)]
    if len(stock_list):
        info = stock_list.set_index("code")[["market", "industry"]]
        df = df.join(info, how="left")
    else:
        df["market"], df["industry"] = "", "未分類"
    df["industry"] = df["industry"].fillna("其他")
    df["reasons"] = df.apply(_reasons, axis=1) if len(df) else pd.Series(dtype=object)

    trend = df[df["main_score"] > 0].copy()
    trend["score"] = trend["main_score"] + trend["aux_score"]
    trend = trend.sort_values(["score", "vol_ratio"], ascending=False)

    reb = df[df["rebound"]].copy()
    reb["score"] = reb["rebound_score"] + reb["aux_score"]
    reb = reb.sort_values(["score", "vol_ratio"], ascending=False)
    return trend, reb


def _reasons(row):
    out = []
    if row["turn_5"] and row["turn_10"]:
        out.append(f"同時站上 5MA、10MA（之前 {int(min(row['below5_days'], row['below10_days']))} 天站不上）")
    elif row["turn_5"]:
        out.append(f"剛站上 5MA（之前連續 {int(row['below5_days'])} 天在下方）")
    elif row["turn_10"]:
        out.append(f"剛站上 10MA（之前連續 {int(row['below10_days'])} 天在下方）")
    if row["box"]:
        out.append(f"{config.BOX_DAYS} 日箱型震幅 {row['box_range']:.1f}%，量能逐步放大")
    if row["rebound"]:
        out.append(f"空頭排列中爆量 {row['vol_ratio']:.1f} 倍，{row['k_type']}")
    if row["macd_red"]:
        out.append("MACD 第一根紅柱")
    if row["kd_golden"]:
        out.append("KD 黃金交叉")
    if row["rsi_cross"]:
        out.append("RSI6 突破 50")
    return out


# ── 資金輪動 ──────────────────────────────────────────

def _pct_rank(s):
    return s.rank(pct=True).fillna(0.5) * 100


def sector_rotation(panels, stock_list):
    """以產業別統計成交金額占比的變化、平均漲幅與上漲家數比例，計算族群熱度。"""
    if not len(stock_list):
        return pd.DataFrame()
    tv = panels["turnover"]
    c = panels["close"]
    ind = stock_list.set_index("code")["industry"].reindex(tv.columns).fillna("其他")
    sector_tv = tv.T.groupby(ind).sum().T  # 日期 × 產業
    share = sector_tv.div(sector_tv.sum(axis=1), axis=0) * 100

    share_today = share.iloc[-1]
    share_20 = share.iloc[-21:-1].mean()
    share_5 = share.iloc[-5:].mean()

    chg = (c.iloc[-1] / c.iloc[-2] - 1) * 100
    traded = tv.iloc[-1] > 0
    g = pd.DataFrame({"chg": chg[traded], "ind": ind[traded]})
    grp = g.groupby("ind")

    out = pd.DataFrame({
        "members": grp.size(),
        "turnover_today": sector_tv.iloc[-1] / 1e8,  # 億元
        "share_today": share_today,
        "share_20d": share_20,
        "share_vs_20d": share_today / share_20.replace(0, np.nan),
        "share_5d_vs_20d": share_5 / share_20.replace(0, np.nan),
        "avg_change": grp["chg"].mean(),
        "up_ratio": grp["chg"].apply(lambda s: (s > 0).mean() * 100),
    })
    out = out[out["members"] >= config.ROTATION_MIN_MEMBERS].copy()
    w = config.ROTATION_WEIGHTS
    out["heat"] = sum(_pct_rank(out[k]) * wt for k, wt in w.items())
    return out.sort_values("heat", ascending=False)


# ── 綜合前 5 名 ───────────────────────────────────────

def pick_top(trend, rotation):
    """個股分數 ＋ 所屬族群熱度加分。搶反彈股性質不同，不列入前 5 名。"""
    if not len(trend):
        return trend
    t = trend.copy()
    heat = rotation["heat"] if len(rotation) else pd.Series(dtype=float)
    t["group_heat"] = t["industry"].map(heat).fillna(50)
    t["group_rank"] = t["industry"].map(
        pd.Series(range(1, len(heat) + 1), index=heat.index)).astype("Int64")
    t["final"] = t["score"] + t["group_heat"] / 100 * config.GROUP_HEAT_MAX_BONUS
    return t.sort_values(["final", "vol_ratio"], ascending=False).head(config.TOP_N)
