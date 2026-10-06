"""
台股盤後選股：主程式
用法：
  python main.py            正常執行（抓資料 → 選股 → 寄 Email）
  python main.py --no-email 只產生報告檔，不寄信（在自己電腦測試用）
"""
import argparse
import os
import smtplib
import sys
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

import analysis
import data
import report
import pandas as pd

OUT = Path(__file__).parent / "output"


def send_email(subject, html_body, attachments):
    """用 Gmail 寄出報告。需要 GitHub Secrets：MAIL_USERNAME、MAIL_PASSWORD、MAIL_TO。"""
    user, pw, to = (os.environ.get(k, "").strip() for k in ("MAIL_USERNAME", "MAIL_PASSWORD", "MAIL_TO"))
    missing = [k for k, v in (("MAIL_USERNAME", user), ("MAIL_PASSWORD", pw), ("MAIL_TO", to)) if not v]
    if missing:
        raise RuntimeError(f"尚未設定 GitHub Secrets：{'、'.join(missing)}（請看 README 步驟 5）")
    msg = MIMEMultipart()
    msg["Subject"], msg["From"], msg["To"] = subject, user, to
    msg.attach(MIMEText(html_body, "html", "utf-8"))
    for filename, content in attachments:
        part = MIMEApplication(content, Name=filename)
        part["Content-Disposition"] = f'attachment; filename="{filename}"'
        msg.attach(part)
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=60) as s:
        s.login(user, pw.replace(" ", ""))
        s.sendmail(user, [x.strip() for x in to.split(",") if x.strip()], msg.as_string())
    print(f"    已寄出 Email 給 {to}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-email", action="store_true", help="不寄信，只產生報告檔")
    args = ap.parse_args()
    manual = os.environ.get("GITHUB_EVENT_NAME") == "workflow_dispatch" or args.no_email

    today = data.taipei_today()
    print(f"執行日期（台北時間）：{today}")

    print("1/4 更新股票清單與產業分類…")
    stock_list = data.fetch_stock_list()
    print(f"    普通股 {len(stock_list)} 檔")

    print("2/4 補齊歷史行情…")
    today_ok, fetched = data.update_history(today)
    print(f"    新抓取 {fetched} 天")
    report_date = today
    if not today_ok:
        latest = data.latest_trading_date()
        if not manual or latest is None:
            print("今天沒有收盤資料（休市，或交易所尚未公布），今天不寄報告。")
            return
        report_date = latest
        print(f"    今天沒有收盤資料，手動執行改用最近交易日 {latest}")

    print("3/4 計算指標與選股…")
    history = data.load_history()
    history = history[history["date"] <= pd.Timestamp(report_date)]
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
    date_str = str(report_date)
    full_html = report.render(date_str, top, rotation, trend, rebound, scanned)
    mail_html = report.render_email(date_str, top, rotation, trend, rebound, scanned)
    csv_bytes = report.to_csv(trend, rebound)
    OUT.mkdir(exist_ok=True)
    (OUT / "report.html").write_text(full_html, encoding="utf-8")
    (OUT / "email.html").write_text(mail_html, encoding="utf-8")
    (OUT / "candidates.csv").write_bytes(csv_bytes)
    print(f"    報告已存到 {OUT}")

    if args.no_email:
        return
    top_names = "、".join(f"{c} {r['name']}" for c, r in top.head(3).iterrows())
    subject = f"台股盤後選股 {date_str}" + (f"｜{top_names}" if top_names else "")
    send_email(subject, mail_html,
               [(f"report_{date_str}.html", full_html.encode("utf-8")),
                (f"candidates_{date_str}.csv", csv_bytes)])


if __name__ == "__main__":
    try:
        main()
    except Exception as e:  # noqa: BLE001
        print(f"❌ 執行失敗：{e}")
        sys.exit(1)
