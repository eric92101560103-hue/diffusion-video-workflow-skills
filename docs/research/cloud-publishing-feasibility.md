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
