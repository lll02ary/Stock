"""
台股盤後選股（網頁版）：主程式
用法：python main.py
"""
import os
import smtplib
import sys
from email.mime.text import MIMEText
from pathlib import Path

import analysis
import config
import data
import report

DOCS = Path(__file__).parent / "docs"
ARCHIVE = DOCS / "archive"


def send_email(subject, html):
    """選用：有設定 MAIL_USERNAME / MAIL_PASSWORD / MAIL_TO 才寄信（Gmail 需使用應用程式密碼）。"""
    user, pw, to = (os.environ.get(k, "").strip() for k in ("MAIL_USERNAME", "MAIL_PASSWORD", "MAIL_TO"))
    if not (user and pw and to):
        return
    msg = MIMEText(html, "html", "utf-8")
    msg["Subject"], msg["From"], msg["To"] = subject, user, to
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=60) as s:
        s.login(user, pw)
        s.sendmail(user, [x.strip() for x in to.split(",")], msg.as_string())
    print("已寄出 Email 報告")


def main():
    today = data.taipei_today()
    print(f"程式版本：{config.VERSION}")
    print(f"執行日期（台北時間）：{today}")

    print("1/4 更新股票清單與產業分類…")
    stock_list = data.fetch_stock_list()
    print(f"    普通股 {len(stock_list)} 檔")

    print("2/4 補齊歷史行情…")
    today_ok, fetched = data.update_history(today)
    print(f"    新抓取 {fetched} 天")
    if not today_ok:
        print("今天沒有收盤資料（休市，或交易所尚未公布）。保留上一次的報告。")
        DOCS.mkdir(exist_ok=True)
        if not (DOCS / "index.html").exists():
            (DOCS / "index.html").write_text(
                report.render_closed(str(today), "今天沒有收盤資料，可能是休市或交易所尚未公布。下一個交易日下午 5 點後會自動產生報告。"),
                encoding="utf-8")
        return

    print("3/4 計算指標與選股…")
    history = data.load_history()
    panels, names = analysis.build_panels(history, stock_list)
    trend, rebound = analysis.screen_stocks(panels, names, stock_list)
    rotation = analysis.sector_rotation(panels, stock_list)
    top = analysis.pick_top(trend, rotation)
    scanned = int((panels["volume"].iloc[-1] > 0).sum())

    print(f"    符合型態 {len(trend)} 檔，搶反彈 {len(rebound)} 檔")
    for i, (code, r) in enumerate(top.iterrows(), 1):
        print(f"    第{i}名 {code} {r['name']}（{r['industry']}）總分 {r['final']:.0f}")
    if len(rotation):
        print("    族群熱度前 3：" + "、".join(rotation.index[:3]))

    print("4/4 產生報告…")
    ARCHIVE.mkdir(parents=True, exist_ok=True)
    date_str = str(today)
    (ARCHIVE / f"{date_str}.html").write_text(
        report.render(date_str, top, rotation, trend, rebound, scanned), encoding="utf-8")
    past = sorted((p.stem for p in ARCHIVE.glob("*.html")), reverse=True)[1:21]
    links = [(d, f"archive/{d}.html") for d in past]
    html = report.render(date_str, top, rotation, trend, rebound, scanned, links)
    (DOCS / "index.html").write_text(html, encoding="utf-8")
    print("    已更新 docs/index.html")

    try:
        send_email(f"台股盤後選股 {date_str}", html)
    except Exception as e:  # noqa: BLE001
        print(f"⚠ Email 寄送失敗：{e}")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:  # noqa: BLE001
        print(f"❌ 執行失敗：{e}")
        sys.exit(1)
