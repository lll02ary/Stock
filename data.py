"""
資料抓取：證交所（上市）、櫃買中心（上櫃）每日收盤行情，以及股票產業分類。
每天的行情存成一個小檔案，下次執行只補抓缺少的日期。
"""
import io
import time
import datetime as dt
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import requests

import config

TPE = ZoneInfo("Asia/Taipei")
CACHE_DIR = Path(__file__).parent / "data" / "cache"
DAILY_DIR = CACHE_DIR / "daily"
STOCK_LIST_FILE = CACHE_DIR / "stock_list.csv"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Accept": "application/json, text/html;q=0.9",
}

_last_request = 0.0


def taipei_today() -> dt.date:
    return dt.datetime.now(TPE).date()


def _get(url, params=None, timeout=30):
    """有節流與重試的 GET，避免太快被證交所暫時封鎖。"""
    global _last_request
    waits = [0, 15, 45]
    last_err = None
    for extra in waits:
        gap = time.time() - _last_request
        need = config.REQUEST_INTERVAL_SEC + extra
        if gap < need:
            time.sleep(need - gap)
        try:
            r = requests.get(url, params=params, headers=HEADERS, timeout=timeout)
            _last_request = time.time()
            r.raise_for_status()
            return r
        except requests.RequestException as e:
            _last_request = time.time()
            last_err = e
            print(f"  連線失敗，稍後重試：{e}")
    raise RuntimeError(f"多次重試仍無法取得資料：{url}（{last_err}）")


def _num(s):
    if s is None:
        return np.nan
    s = str(s).replace(",", "").strip()
    if s in ("", "--", "---", "-", "X", "除權息", "除息", "除權"):
        return np.nan
    try:
        return float(s)
    except ValueError:
        return np.nan


def _find_col(fields, *keywords, default=None):
    for i, f in enumerate(fields):
        name = str(f).replace(" ", "")
        if all(k in name for k in keywords):
            return i
    return default


# ── 每日行情 ──────────────────────────────────────────

def fetch_twse_day(date: dt.date):
    """上市每日收盤行情。休市回傳 None。"""
    url = "https://www.twse.com.tw/rwd/zh/afterTrading/MI_INDEX"
    j = _get(url, {"date": date.strftime("%Y%m%d"), "type": "ALLBUT0999",
                   "response": "json"}).json()
    if j.get("stat") != "OK":
        return None
    table = None
    for t in j.get("tables", []):
        fields = t.get("fields") or []
        if _find_col(fields, "證券代號") is not None and _find_col(fields, "收盤價") is not None:
            table = t
            break
    if table is None or not table.get("data"):
        return None
    f = table["fields"]
    idx = {
        "code": _find_col(f, "證券代號"), "name": _find_col(f, "證券名稱"),
        "volume": _find_col(f, "成交股數"), "turnover": _find_col(f, "成交金額"),
        "open": _find_col(f, "開盤價"), "high": _find_col(f, "最高價"),
        "low": _find_col(f, "最低價"), "close": _find_col(f, "收盤價"),
    }
    return _rows_to_df(table["data"], idx)


def fetch_tpex_day(date: dt.date):
    """上櫃每日收盤行情。休市回傳 None。"""
    url = "https://www.tpex.org.tw/www/zh-tw/afterTrading/dailyQuotes"
    j = _get(url, {"date": date.strftime("%Y/%m/%d"), "response": "json"}).json()
    tables = j.get("tables") or []
    if not tables or not tables[0].get("data"):
        return None
    t = tables[0]
    f = t.get("fields") or []
    # 預設欄位順序：代號、名稱、收盤、漲跌、開盤、最高、最低、均價、成交股數、成交金額、成交筆數
    idx = {
        "code": _find_col(f, "代號", default=0), "name": _find_col(f, "名稱", default=1),
        "close": _find_col(f, "收盤", default=2), "open": _find_col(f, "開盤", default=4),
        "high": _find_col(f, "最高", default=5), "low": _find_col(f, "最低", default=6),
        "volume": _find_col(f, "成交股數", default=8),
        "turnover": _find_col(f, "成交金額", default=9),
    }
    return _rows_to_df(t["data"], idx)


def _rows_to_df(rows, idx):
    out = []
    for r in rows:
        out.append({
            "code": str(r[idx["code"]]).strip(),
            "name": str(r[idx["name"]]).strip(),
            "open": _num(r[idx["open"]]), "high": _num(r[idx["high"]]),
            "low": _num(r[idx["low"]]), "close": _num(r[idx["close"]]),
            "volume": _num(r[idx["volume"]]), "turnover": _num(r[idx["turnover"]]),
        })
    df = pd.DataFrame(out)
    return df if len(df) else None


# ── 產業分類與股票清單 ────────────────────────────────

def fetch_stock_list(force=False) -> pd.DataFrame:
    """上市、上櫃普通股清單與產業別（排除 ETF、權證、特別股、TDR）。每 7 天更新一次。"""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    if STOCK_LIST_FILE.exists() and not force:
        age = time.time() - STOCK_LIST_FILE.stat().st_mtime
        if age < 7 * 86400:
            return pd.read_csv(STOCK_LIST_FILE, dtype=str)

    frames = []
    for mode, market in (("2", "上市"), ("4", "上櫃")):
        try:
            r = _get("https://isin.twse.com.tw/isin/C_public.jsp", {"strMode": mode}, timeout=60)
            r.encoding = "cp950"
            tables = pd.read_html(io.StringIO(r.text), header=0)
            t = max(tables, key=len)
            t.columns = [str(c).strip() for c in t.columns]
            code_col = [c for c in t.columns if "代號" in c][0]
            t = t[t["CFICode"] == "ESVUFR"]  # 普通股
            sp = t[code_col].astype(str).str.split("\u3000", n=1, expand=True)
            frames.append(pd.DataFrame({
                "code": sp[0].str.strip(),
                "name": sp[1].str.strip(),
                "market": market,
                "industry": t["產業別"].fillna("其他").astype(str).str.strip(),
            }))
        except Exception as e:  # noqa: BLE001
            print(f"  ⚠ 無法取得{market}產業分類：{e}")

    if frames:
        df = pd.concat(frames, ignore_index=True).drop_duplicates("code")
        df.loc[df["industry"].isin(["", "nan"]), "industry"] = "其他"
        df.to_csv(STOCK_LIST_FILE, index=False)
        return df
    if STOCK_LIST_FILE.exists():
        print("  ⚠ 改用上次儲存的產業分類")
        return pd.read_csv(STOCK_LIST_FILE, dtype=str)
    return pd.DataFrame(columns=["code", "name", "market", "industry"])


# ── 歷史資料維護 ──────────────────────────────────────

def _day_file(market, date, empty=False):
    return DAILY_DIR / f"{market}_{date:%Y%m%d}.{'none' if empty else 'csv'}"


def _ensure_day(market, date, fetcher, today):
    """確保某市場某天的資料在快取中。回傳 True（有交易）/ False（休市）/ None（今天尚未公布）。"""
    f, fn = _day_file(market, date), _day_file(market, date, empty=True)
    if f.exists():
        return True
    if fn.exists():
        return False
    df = fetcher(date)
    if df is None:
        if date < today:
            fn.touch()
            return False
        return None
    df.to_csv(f, index=False)
    return True


def update_history(today=None):
    """
    補齊最近 HISTORY_TRADING_DAYS 個交易日的資料。
    回傳 (今天是否有資料, 新抓取的天數)。
    第一次執行要抓約半年資料，大約需要 20～30 分鐘；之後每天只抓 1 天。
    """
    DAILY_DIR.mkdir(parents=True, exist_ok=True)
    today = today or taipei_today()
    need = config.HISTORY_TRADING_DAYS
    found, fetched = 0, 0
    today_ok = None
    d = today
    oldest_kept = today
    for _ in range(int(need * 1.6) + 30):
        if found >= need:
            break
        if d.weekday() < 5:
            existed = _day_file("twse", d).exists() or _day_file("twse", d, True).exists()
            if not existed:
                fetched += 1
                if fetched == 1 or fetched % 10 == 0:
                    print(f"  抓取中… 目前到 {d}（已抓 {fetched} 天）")
            ok = _ensure_day("twse", d, fetch_twse_day, today)
            if ok:
                _ensure_day("tpex", d, fetch_tpex_day, today)
                found += 1
                oldest_kept = d
            if d == today:
                today_ok = bool(ok)
        d -= dt.timedelta(days=1)

    # 清掉用不到的舊檔案
    for p in DAILY_DIR.iterdir():
        try:
            file_date = dt.datetime.strptime(p.stem.split("_")[1], "%Y%m%d").date()
        except (IndexError, ValueError):
            continue
        if file_date < oldest_kept - dt.timedelta(days=10):
            p.unlink()
    return bool(today_ok), fetched


def load_history() -> pd.DataFrame:
    """讀取快取中的所有日資料，合併成一張長表。"""
    frames = []
    for p in sorted(DAILY_DIR.glob("*.csv")):
        _, ds = p.stem.split("_")
        df = pd.read_csv(p, dtype={"code": str})
        df["date"] = pd.Timestamp(dt.datetime.strptime(ds, "%Y%m%d"))
        frames.append(df)
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True)
