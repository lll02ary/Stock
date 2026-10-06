# 台股盤後選股（網頁版）

每個交易日下午 5 點（台北時間），GitHub 會自動幫你：

1. 抓取上市、上櫃所有股票的收盤行情
2. 依照你的三種買進型態篩選並排名
3. 統計今天資金流向哪些族群
4. 綜合兩者，排出最值得留意的前 5 名

結果會產生成一個網頁，用手機或電腦打開網址就能看。

> 確認版本：打開 `config.py`，第 5 行應該是 `VERSION = "網頁版 2026-10-06"`。

---

## 設定步驟（只需要做一次）

1. **上傳程式檔**：在專案頁面點 **Add file** → **Upload files**，把 `main.py`、`config.py`、`data.py`、`analysis.py`、`report.py`、`requirements.txt`、`README.md` 拖進去，按 **Commit changes**。
2. **建立排程檔**：點 **Add file** → **Create new file**，檔名輸入 `.github/workflows/daily.yml`（前面不能有空格），用記事本打開 `daily.yml` 全部複製貼上，按 **Commit changes**。如果已經有這個檔案，就點開它按鉛筆圖示，全選刪除後貼上新內容。
3. **開啟寫入權限**：**Settings** → **Actions** → **General** → 最下面 **Workflow permissions** 選 **Read and write permissions** → **Save**。
4. **手動執行第一次**：**Actions** → 左側「台股盤後選股」→ **Run workflow**。第一次要抓約半年資料，大約 20～30 分鐘，出現綠色勾勾 ✅ 就成功。建議在平日下午 5 點後執行。
5. **開啟網頁**：**Settings** → **Pages** → Source 選 **Deploy from a branch**，Branch 選 `main`、資料夾選 `/docs` → **Save**。
6. **加入書籤**：網址是 `https://你的帳號.github.io/專案名稱/`（大小寫要和專案名稱一致）。

> 專案必須是 **Public** 才能免費使用網頁功能。

---

## 選用：同時寄 Email

到 Google 帳戶開啟兩步驟驗證並建立「應用程式密碼」，再到 GitHub **Settings** → **Secrets and variables** → **Actions** 新增：

| Name | Secret |
|---|---|
| `MAIL_USERNAME` | 寄信用的 Gmail 地址 |
| `MAIL_PASSWORD` | 16 碼應用程式密碼 |
| `MAIL_TO` | 收報告的信箱（多個用逗號分隔） |

沒設定也沒關係，網頁照常更新。

---

## 調整選股參數

所有數字都在 `config.py`，每一項都有中文說明。在 GitHub 上點開 `config.py` → 鉛筆圖示 → 修改 → **Commit changes**，下次執行就會套用。

| 參數 | 預設 | 說明 |
|---|---|---|
| `MIN_AVG_VOLUME_LOTS` | 500 | 5 日均量門檻（張） |
| `TURN_MIN_DAYS_BELOW` | 5 | 趨勢扭轉：之前至少幾天在均線下 |
| `REBOUND_VOLUME_RATIO` | 2.0 | 搶反彈：爆量倍數 |
| `BOX_DAYS` | 60 | 箱型觀察天數 |
| `BOX_MAX_RANGE_PCT` | 15 | 箱型最大震幅（%） |
| `GROUP_HEAT_MAX_BONUS` | 30 | 族群熱度最多加幾分 |

執行時間在 `.github/workflows/daily.yml` 的 `cron: "0 9 * * 1-5"`。GitHub 用 UTC 時間，比台灣慢 8 小時，`0 9` 就是台灣 17:00。

---

## 常見問題

**Actions 出現紅色叉叉 ❌**：點進去看「執行選股」那一步的錯誤訊息。`多次重試仍無法取得資料` 代表證交所暫時擋住連線，等 30 分鐘再手動執行；`Permission denied` 或 `403` 請確認步驟 3。

**網頁沒更新**：GitHub Pages 會延遲 1～2 分鐘，手機瀏覽器下拉重新整理即可。

**歷史資料重新抓取**：資料存在 GitHub 快取，超過 7 天沒用會被清除（例如長假後），程式會自動重抓，那一次會跑比較久。

---

## 目前的限制

- 股價沒有做除權息還原，除權息當天的跳空可能讓均線短暫失真。
- 族群使用證交所官方產業分類，不包含市場自訂的概念股（如 AI 伺服器、重電）。
- 全額交割股沒有特別排除，但多數會被 500 張的成交量門檻擋掉。
- 本程式只依技術條件篩選，不代表股票一定會漲，買賣決定請自行判斷。
