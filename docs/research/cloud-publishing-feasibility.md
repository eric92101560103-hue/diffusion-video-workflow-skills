# 雲端發佈候選服務備忘

調查日期：2026-10-29。這是後續 Issue #5 的前期資料，不代表服務已選定、已啟用或已獲付費批准。

Cloudflare Workers 與 R2 是可進一步驗證的候選組合：官方文件列出 Cron Trigger、R2 Standard 儲存每月 10 GB-month 免費額度，以及 Workers Free 的每日請求額度。惟「有免費額度」不表示完全沒有訂閱、帳務或超額費用；R2 啟用需要帳號與 R2 subscription，實際配置前仍須核對帳務條件。

重要限制：Cloudflare Free account 的單次 HTTP request body 上限為 100 MB，並非適合直接把任意成片整支傳入 Worker。以 20 Mbps 編碼的 60 秒影片，僅影像約 150 MB（十進位，尚未計音訊與封裝），因此不能因成片短就假定落在限制內；應研究對物件儲存直接或分段上傳，而非縮小影片來遷就錯誤架構。

Workers Free 的 CPU 與子請求限制，也要求將媒體傳送、準備、狀態查詢與正式發佈拆成可恢復進度；不能以長時間占用一次排程呼叫來等待整個平台處理完成。是否適用需在選型及真實原型中驗證。

尚未建立任何雲端資源。先完成 Meta App 與帳號授權、確認有效的官方媒體傳輸流程，再比較服務限制與實際成片容量；任何付費部署先交由使用者確認。部署前重新核對以下官方資料。

- [Workers limits](https://developers.cloudflare.com/workers/platform/limits/)
- [Cron Triggers](https://developers.cloudflare.com/workers/configuration/cron-triggers/)
- [R2 pricing](https://developers.cloudflare.com/r2/pricing/)
- [R2 getting started](https://developers.cloudflare.com/r2/get-started/)

## 2026-10-30 官方限制再核實

這次只讀官方文件，沒有登入供應商、建立帳號或資源。小量候選仍建議 Workers + D1 + R2，但尚未選定或部署，也不能保證零費用。

| 項目 | 官方目前列出的限制 | 對本流程的影響 |
| --- | --- | --- |
| Workers Free | 每日 100,000 請求、HTTP 與 Cron CPU 10 ms、每次 50 子請求、帳號 5 個 Cron Trigger | 每分鐘只處理少量持久步驟；須實測 CPU，不能靠一次呼叫等待影片完成 |
| 免費 Cloudflare 網域方案 | 送入 Worker 的 request body 100 MB | 影片直接／分段送儲存，避免整支穿過 Worker；限制屬網域方案而非 Workers 付費級別 |
| D1 Free | 每庫 500 MB、每帳號 5 GB、單次 Worker 50 queries | 只放任務與紀錄，不放影片；另須驗證讀寫每日額度與超額停止行為 |
| R2 Standard 免費額度 | 每月 10 GB-month、A 類 100 萬、B 類 1,000 萬次操作 | 七天保留能降低用量，但失敗／未知會繼續占用；不能為省空間刪待核對項目 |
| Resend Free 候選 | 每月 3,000 封、每日 100 封；SMTP 需 API key 與已驗證網域 | 每候選一次提醒可小量驗證；無既有網域時不能假定能以任意 Gmail 地址寄件 |

依 R2 入門頁，需完成 subscription 的 checkout；官方說明按月計量收費。尚未確認此使用者帳號是否需綁卡、是否有可設定的支出控制；未經具體批准不執行 checkout。免費額度不是硬性費用上限。

Resend SMTP 支援 implicit TLS 465，與現有 SMTP_SSL 相容；587 是 STARTTLS，本程式不支援，不能只更換連線埠。這是寄件服務候選，沒有選定、配置網域或開通 API key。真實驗證仍待使用者選擇寄件信箱／服務及首次掃描時間。

台北 20:00 是 UTC 12:00。Cron 每分鐘觸發後讀具體的已核准日期；不使用「每月奇／偶日」表示固定隔日，避免跨月節奏錯位。沒有部署延遲保證，平台處理及免費服務限額都可能影響實際時間。

核實來源：

- [Workers limits](https://developers.cloudflare.com/workers/platform/limits/)
- [Cron Triggers](https://developers.cloudflare.com/workers/configuration/cron-triggers/)
- [D1 limits](https://developers.cloudflare.com/d1/platform/limits/)
- [R2 pricing](https://developers.cloudflare.com/r2/pricing/)
- [R2 get started](https://developers.cloudflare.com/r2/get-started/)
- [Resend pricing](https://resend.com/pricing)
- [Resend SMTP](https://resend.com/docs/send-with-smtp)

背景服務採 launchd 的理由及休眠限制可參照 [Apple Scheduling Timed Jobs](https://developer.apple.com/library/archive/documentation/MacOSX/Conceptual/BPSystemStartup/Chapters/ScheduledJobs.html)；這是封存文件，實際 bootstrap、登入恢復與讀取權限仍需在目標 macOS 驗證。
