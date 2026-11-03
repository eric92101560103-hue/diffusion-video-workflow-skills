---
name: reels-meta-schedule
description: 將已核准 Reels 經 Meta Business Suite 原生 UI 上傳排程，修改或取消既有排程，核對已發佈結果並歸檔。沿用本機候選資料庫，需可用的 computer use；不使用 API 補發。
---

# Meta 原生 Reels 排程

使用本 plugin 的 `scripts/reels.py`，全域 source／published／database 參數放子命令前。沿用使用者既有唯一狀態庫及審核對話。CLI 只管理持久操作意圖與觀察回執；外部寫入與核對必須由可用的 computer use 在 Meta Business Suite 完成。無可用瀏覽器或登入時保留待辦，不假稱已交付。

## 建立或核對既有排程

1. `get`、`native-list` 核對候選及既有安排。先在 Meta 查同一項目；已有排程時走讀取核對，不再上傳。本機 approved 只表示使用者核准確切原片、完整文案及時刻；未核准時先回審核流程。
2. `native-prepare ID --revision N` 保存快照與私有上傳副本。若已核准轉碼檔，另傳 `--media /absolute/file --confirm-media`；影片畫面或內容變更需重新審閱，不能自行替換。建立新排程前呼叫 `native-begin JOB --revision N --action create --confirm-operation`，保存 operation_id，再對 Meta 寫入一次。中斷後這份寫入授權不可重用，先核對。
3. Meta 只選 @_eric_han 的 Instagram、公開、無 Facebook 跨貼；現在就上傳 job.media_path，輸入完整 job.caption，設定 job.scheduled_for 的台北日期／20:00，保存後重新載入確認。文案用實際鍵盤輸入；單純 AX setValue 曾讓編輯器顯示文字卻未保存。需同時看到正確帳號、完整文案、時間及已上傳項目。
4. 保存私有截圖與結構化回執，用 `native-observe JOB --receipt /absolute/private/receipt.json` 收錄。欄位及範例讀[原生操作手冊](../../docs/runbooks/meta-native-scheduling.md)。CLI 成功只表示收錄回執；不能代替真實 Meta 證據。IG app 沒顯示、清單空白或逾時不能當成可重送證據。

## 修改、取消及未知結果

尚未 native-begin 的 prepared 項目若過期或使用者撤回，可明確 `native-withdraw JOB --confirm-withdraw` 結束本機準備，再以明確 replay 建立新待審候選。只有本機證明從未開始外部操作才允許，不能用此入口取消或解除未知 Meta 操作。

使用者需核准指定項目的確切變更；先查看 Meta 最新狀態及 `native-get` 版本，再 `native-begin --action modify`（完整文案檔／時刻）或 `--action cancel`。操作同一 native_schedule_id，保存後重新載入收錄回執；其他影片日期不動。取消要有平台明確確認，缺席不足以證明取消；已公開項目不自動刪除。

operation_id 尚未結束時只核對既有平台紀錄。若修改期間舊內容已公開，收錄有證據的實際結果，不冒稱新版本已生效。無法確認時保存 unknown／failed 回執並交人工介入，不另建排程、不走 API 補發。舊與擬修改日期都保留，直到核對完成。

## 定時核對與歸檔

每兩天08:00既有 Codex 任務先查 `native-list`，再用 Meta Scheduled／Published 唯讀核對並收錄回執；瀏覽器不可用或需登入時，用 `native-blocked JOB --reason browser_unavailable/login_required` 持久記錄核對阻擋，保留最後已知平台狀態；內容不符用 item_mismatch。只對已交付項目使用，prepared 尚未外送者保留本機待辦。不要為登入失敗偽造 Meta 觀察回執；恢復後收錄真實觀察即可解除阻擋。`native-check` 只檢查本機已收錄狀態，不查網路；20:30起仍無成功證據產生去重待核對事件，並非即時監控。`chat-check` 沿用同一通知回執，不自動確認送達。

只有實際 Meta 已發佈項目對應正確帳號與同一影片，才收錄 published，附獨立正式媒體 ID、IG 連結及公開時間。native_schedule_id 不是 IG 媒體 ID；拿不到正式證據就保持待核對。`native-archive JOB` 只在正式成功後歸檔原片，失敗時保留平台成功，不重新發文。需清理時，明確 `native-cleanup JOB --confirm-cleanup` 只刪本工具管理的已終止上傳副本；Meta 內部副本、原片及證據不在清理範圍。

停用掃描／plugin 不取消 Meta 既有排程；取消必須另走上述流程。原 API 單支正式發文驗收為暫緩 #17，不以原生排程取代。
