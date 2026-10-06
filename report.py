"""產生每日 HTML 報告（手機、電腦都能看，支援深色模式）。"""
from html import escape
import math

import config

CSS = """
:root{--bg:#F3F5F7;--surface:#FFFFFF;--ink:#15202B;--muted:#5E6B78;--line:#D9DEE3;
--up:#C62828;--down:#1B7F4C;--caution:#A86A12;--bar:#2F5D8A;--chip:#E8EDF2;
box-sizing:border-box;padding-top:env(safe-area-inset-top,0px);padding-bottom:env(safe-area-inset-bottom,0px)}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){--bg:#12181F;--surface:#1A222B;
--ink:#E6EBF0;--muted:#93A0AD;--line:#2A3540;--up:#F0605D;--down:#3CB878;--caution:#E0A84A;--bar:#6E9CCB;--chip:#243039}}
:root[data-theme="dark"]{--bg:#12181F;--surface:#1A222B;--ink:#E6EBF0;--muted:#93A0AD;--line:#2A3540;
--up:#F0605D;--down:#3CB878;--caution:#E0A84A;--bar:#6E9CCB;--chip:#243039}
*,*::before,*::after{box-sizing:inherit}
html{-webkit-text-size-adjust:100%}
body{margin:0;background:var(--bg);color:var(--ink);
font-family:"Noto Sans TC","PingFang TC","Microsoft JhengHei",system-ui,sans-serif;
font-size:16px;line-height:1.6;font-variant-numeric:tabular-nums}
main{max-width:980px;margin:0 auto;padding:28px 18px 64px}
header{padding-bottom:20px;border-bottom:2px solid var(--ink);margin-bottom:28px}
header h1{font-size:1.15rem;font-weight:500;margin:0;color:var(--muted)}
header .date{font-size:2.4rem;font-weight:700;letter-spacing:.02em;line-height:1.2;margin:2px 0 8px}
header p{margin:0;color:var(--muted);font-size:.92rem}
h2{font-size:1.3rem;margin:44px 0 6px}
.lead{color:var(--muted);margin:0 0 16px;font-size:.93rem;max-width:62ch}
.top{list-style:none;margin:0;padding:0}
.top>li{display:grid;grid-template-columns:2.2rem 1fr auto;gap:4px 16px;padding:18px 0;border-bottom:1px solid var(--line)}
.top .rank{font-size:1.5rem;font-weight:700;color:var(--muted);line-height:1.1}
.top .code{font-size:2.1rem;font-weight:700;line-height:1.05;letter-spacing:.01em}
.top .name{font-size:1.15rem;font-weight:500;margin-left:8px}
.top .meta{margin-top:6px;font-size:.88rem;color:var(--muted)}
.chip{display:inline-block;background:var(--chip);border-radius:4px;padding:1px 8px;margin-right:6px;color:var(--ink)}
.top .px{text-align:right}
.top .px .c{font-size:1.4rem;font-weight:600}
.top .px .s{font-size:.85rem;color:var(--muted)}
.top ul{grid-column:2/4;margin:8px 0 0;padding-left:1.1em;font-size:.93rem}
.top ul li{margin:2px 0}
.up,.top .px .up{color:var(--up)}.down,.top .px .down{color:var(--down)}
.scroll{overflow-x:auto;-webkit-overflow-scrolling:touch;background:var(--surface);border:1px solid var(--line);border-radius:6px}
table{border-collapse:collapse;width:100%;font-size:.9rem;white-space:nowrap}
th,td{padding:9px 12px;text-align:right;border-bottom:1px solid var(--line)}
th{font-weight:600;color:var(--muted);font-size:.82rem;background:var(--surface);position:sticky;top:0}
td.l,th.l{text-align:left}
td.why{white-space:normal;min-width:240px;text-align:left;color:var(--muted);font-size:.84rem}
tr:last-child td{border-bottom:0}
.heat{display:flex;align-items:center;gap:8px;justify-content:flex-end}
.heat span.b{display:inline-block;height:8px;border-radius:2px;background:var(--bar)}
.caution{border-left:3px solid var(--caution);padding:10px 14px;background:var(--surface);margin:0 0 14px;font-size:.9rem}
.empty{color:var(--muted);padding:18px;background:var(--surface);border:1px dashed var(--line);border-radius:6px}
details{margin-top:44px;background:var(--surface);border:1px solid var(--line);border-radius:6px;padding:12px 16px}
summary{cursor:pointer;font-weight:600}
details li{margin:4px 0;font-size:.9rem}
footer{margin-top:36px;color:var(--muted);font-size:.82rem}
footer a{color:var(--muted)}
a:focus-visible,summary:focus-visible{outline:2px solid var(--bar);outline-offset:2px}
@media (max-width:560px){header .date{font-size:1.9rem}.top .code{font-size:1.7rem}
.top>li{grid-template-columns:1.6rem 1fr auto;gap:2px 10px}}
"""


def _f(x, nd=2, sign=False):
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return "—"
    return f"{x:+.{nd}f}" if sign else f"{x:,.{nd}f}"


def _cls(x):
    if x is None or (isinstance(x, float) and math.isnan(x)) or x == 0:
        return ""
    return "up" if x > 0 else "down"


def _top_section(top):
    if not len(top):
        return '<p class="empty">今天沒有股票符合趨勢扭轉或箱型量增的條件。</p>'
    items = []
    for i, (code, r) in enumerate(top.iterrows(), 1):
        reasons = "".join(f"<li>{escape(x)}</li>" for x in r["reasons"])
        grank = r.get("group_rank")
        gtxt = f"族群熱度第 {grank} 名" if grank is not None and str(grank) != "<NA>" else "族群未排名"
        items.append(f"""
<li><div class="rank">{i}</div>
<div><span class="code">{escape(code)}</span><span class="name">{escape(str(r['name']))}</span>
<div class="meta"><span class="chip">{escape(str(r['industry']))}</span>{gtxt}　量 {r['vol_ratio']:.1f} 倍</div></div>
<div class="px"><div class="c {_cls(r['chg_pct'])}">{_f(r['close'])}</div>
<div class="s {_cls(r['chg_pct'])}">{_f(r['chg_pct'], 2, True)}%</div>
<div class="s">總分 {r['final']:.0f}</div></div>
<ul>{reasons}</ul></li>""")
    return f'<ol class="top">{"".join(items)}</ol>'


def _rotation_table(rot, limit=15):
    if not len(rot):
        return '<p class="empty">無法取得產業分類，今天沒有族群資料。</p>'
    rows = []
    for i, (ind, r) in enumerate(rot.head(limit).iterrows(), 1):
        w = max(4, r["heat"] * 0.9)
        rows.append(f"""<tr><td>{i}</td><td class="l">{escape(str(ind))}</td>
<td><div class="heat">{r['heat']:.0f}<span class="b" style="width:{w:.0f}px"></span></div></td>
<td>{_f(r['turnover_today'], 1)}</td><td>{_f(r['share_today'], 2)}%</td>
<td>{_f(r['share_vs_20d'], 2)}×</td><td>{_f(r['share_5d_vs_20d'], 2)}×</td>
<td class="{_cls(r['avg_change'])}">{_f(r['avg_change'], 2, True)}%</td>
<td>{_f(r['up_ratio'], 0)}%</td><td>{int(r['members'])}</td></tr>""")
    return f"""<div class="scroll"><table><thead><tr><th>#</th><th class="l">族群</th><th>熱度</th>
<th>成交額(億)</th><th>資金占比</th><th>占比 vs 20日</th><th>5日 vs 20日</th>
<th>平均漲跌</th><th>上漲比例</th><th>家數</th></tr></thead><tbody>{''.join(rows)}</tbody></table></div>"""


def _stock_table(df, show_k=False):
    if not len(df):
        return '<p class="empty">今天沒有符合條件的股票。</p>'
    rows = []
    for i, (code, r) in enumerate(df.head(config.LIST_LIMIT).iterrows(), 1):
        extra = f"<td class='l'>{escape(r['k_type'])}</td>" if show_k else ""
        rows.append(f"""<tr><td>{i}</td><td class="l">{escape(code)}</td><td class="l">{escape(str(r['name']))}</td>
<td class="l">{escape(str(r['industry']))}</td><td>{r['score']:.0f}</td>
<td>{_f(r['close'])}</td><td class="{_cls(r['chg_pct'])}">{_f(r['chg_pct'], 2, True)}%</td>
<td>{_f(r['volume'], 0)}</td><td>{_f(r['vol_ratio'], 1)}×</td>{extra}
<td class="why">{escape('、'.join(r['reasons']))}</td></tr>""")
    kh = "<th class='l'>K 棒</th>" if show_k else ""
    more = f"<p class='lead'>共 {len(df)} 檔，顯示前 {min(len(df), config.LIST_LIMIT)} 檔。</p>"
    return more + f"""<div class="scroll"><table><thead><tr><th>#</th><th class="l">代號</th><th class="l">名稱</th>
<th class="l">族群</th><th>分數</th><th>收盤</th><th>漲跌</th><th>成交量(張)</th><th>量比</th>{kh}
<th class="l">入選理由</th></tr></thead><tbody>{''.join(rows)}</tbody></table></div>"""


def _rules():
    c = config
    return f"""<details><summary>選股規則與計分方式</summary><ul>
<li>基本門檻：5 日均量 ≥ {c.MIN_AVG_VOLUME_LOTS} 張，只看上市櫃普通股（排除 ETF、權證、特別股）。</li>
<li>型態①趨勢扭轉：之前至少連續 {c.TURN_MIN_DAYS_BELOW} 天收在 5MA 或 10MA 之下，今天收盤站上。站上一條 {c.SCORE_TURN_ONE_LINE} 分，兩條 {c.SCORE_TURN_BOTH} 分。</li>
<li>型態③箱型量增：近 {c.BOX_DAYS} 日最高最低價差 ≤ {c.BOX_MAX_RANGE_PCT:.0f}%，且 5 日均量 &gt; 10 日均量 &gt; 20 日均量。{c.SCORE_BOX} 分。</li>
<li>型態②空頭爆量搶反彈：5、10、20、60MA 空頭排列且股價在均線下，今日量 ≥ 前 5 日均量 {c.REBOUND_VOLUME_RATIO:.0f} 倍，K 棒收紅或下影線 ≥ 實體 {c.REBOUND_SHADOW_TO_BODY} 倍。另列清單，不列入前 5 名。</li>
<li>輔助加分：MACD 第一根紅柱 {c.SCORE_MACD_FIRST_RED} 分、KD 黃金交叉（今天或昨天）{c.SCORE_KD_GOLDEN} 分、RSI6 由下往上突破 50 {c.SCORE_RSI_CROSS_50} 分。</li>
<li>族群熱度：今日資金占比相對前 20 日的變化 {c.ROTATION_WEIGHTS['share_vs_20d']:.0%}、近 5 日占比延續性 {c.ROTATION_WEIGHTS['share_5d_vs_20d']:.0%}、族群平均漲幅 {c.ROTATION_WEIGHTS['avg_change']:.0%}、上漲家數比例 {c.ROTATION_WEIGHTS['up_ratio']:.0%}，換算成 0～100 分。</li>
<li>前 5 名總分：個股分數 ＋ 族群熱度 × {c.GROUP_HEAT_MAX_BONUS / 100:.1f}（最多加 {c.GROUP_HEAT_MAX_BONUS} 分）。</li>
<li>參數都在 config.py，可以自行調整。程式版本：{escape(c.VERSION)}</li></ul></details>"""


def render(date, top, rotation, trend, rebound, scanned, archive_links=(), note=""):
    archive = ""
    if archive_links:
        links = "、".join(f'<a href="{escape(h)}">{escape(t)}</a>' for t, h in archive_links)
        archive = f"<p>過去報告：{links}</p>"
    note_html = f'<p class="caution">{escape(note)}</p>' if note else ""
    return f"""<!doctype html><html lang="zh-Hant-TW"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>台股盤後選股 {date}</title>
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Noto+Sans+TC:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>{CSS}</style></head><body><main>
<header><h1>台股盤後選股</h1><div class="date">{date}</div>
<p>掃描 {scanned:,} 檔上市櫃普通股｜符合型態 {len(trend)} 檔｜搶反彈候選 {len(rebound)} 檔</p></header>
{note_html}
<section><h2>今日最該留意的 5 檔</h2>
<p class="lead">從符合「趨勢扭轉」或「箱型量增」的股票中，加上所屬族群的資金熱度排出。</p>
{_top_section(top)}</section>
<section><h2>資金輪動：族群熱度排名</h2>
<p class="lead">「占比 vs 20日」大於 1 代表今天流進這個族群的資金比平常多；「5日 vs 20日」大於 1 代表這幾天持續有資金進來。</p>
{_rotation_table(rotation)}</section>
<section><h2>符合買進型態的股票</h2>
<p class="lead">趨勢扭轉與箱型量增，依分數排序。</p>
{_stock_table(trend)}</section>
<section><h2>空頭爆量搶反彈</h2>
<p class="caution">逆勢搶反彈，風險比順勢高。請搭配 K 棒型態判斷是止跌還是恐慌殺盤。</p>
{_stock_table(rebound, show_k=True)}</section>
{_rules()}
<footer>{archive}<p>資料來源：臺灣證券交易所、證券櫃檯買賣中心。本報告依設定的技術條件自動篩選，僅供參考，不構成投資建議。</p></footer>
</main></body></html>"""


def render_closed(date, reason):
    return f"""<!doctype html><html lang="zh-Hant-TW"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>台股盤後選股</title><style>{CSS}</style></head><body><main>
<header><h1>台股盤後選股</h1><div class="date">{date}</div></header>
<p class="empty">{escape(reason)}</p></main></body></html>"""
