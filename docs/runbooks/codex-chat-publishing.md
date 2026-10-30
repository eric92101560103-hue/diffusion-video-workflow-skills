# 本機 Codex 掃描提醒與人工審核 plugin

本手冊對應 #13。現行通知規則以 PR #14 的 2026-10-30 修訂為準：Codex 對話為主要掃描提醒，Email／SMTP／launchd 非必要。這個套件只交付本機流程，沒有正式 IG 或雲端發佈能力。#7 的真實到期／可見通知／休眠恢復，與 #11 完整雲端 plugin，均需另外驗收。

## 安裝包與依賴

需 Python 3.11+、FFmpeg／ffprobe，以及能執行本機工具的 Codex。Python 程式只用標準函式庫，不必安裝 pip 執行依賴；FFmpeg 不打包在內，缺少時 preflight 會列出阻擋。不需要寄信帳號、應用程式密碼、IG token 或 Keychain。

在 repo 建立安裝包：

```sh
python3 scripts/build_local_plugin.py --output /absolute/output/reels-local.zip
```

輸出路徑需尚未存在。zip 包含一個獨立 marketplace 根目錄、portable plugin.json、三個技能與本機 CLI。只收 allowlist 檔案，不包含環境檔、資料庫、影片、虛擬環境或真實配置。

將 zip 解壓到長期保存的私人目錄。其 `diffusion-reels-local-marketplace/.agents/plugins/marketplace.json` 使用官方本機 marketplace 格式，指向同根目錄 `plugins/diffusion-reels-local`。在支援的 Codex CLI 可執行：

```sh
codex plugin marketplace add /absolute/private/diffusion-reels-local-marketplace
```

本機 Codex 若提供 `plugin add`，可直接完成安裝：

```sh
codex plugin add diffusion-reels-local@diffusion-reels-personal --json
codex plugin list --marketplace diffusion-reels-personal --json
```

核對 installed=true 與 enabled=true。2026-10-30 已在使用者主機透過此指令安裝成功；安裝後快取副本也通過合成影片操作驗收，詳見[驗收紀錄](../reviews/codex-chat-plugin.md)。這仍不等於桌面對話已載入技能。

若此主機沒有 CLI 安裝命令，則於桌面 App 的 Plugins 選擇「Reels 本機工作流程」本機來源並安裝；官方文件要求重新啟動 App 讓本機來源更新。**初次交付僅完成隔離演示；後續已依使用者授權註冊真實 marketplace 並安裝 plugin，尚未重啟 App。** App 實際辨識、新舊對話載入仍需在安裝後核對，不能以 JSON 檔有效就宣稱已載入。

此為 skills + 本機 CLI 的 desktop-only plugin，沒有宣告 MCP server、遠端網站、連接器或安裝鉤子。原字幕及匯出技能保持原檔；它們仍需另外已安裝的 Diffusion Studio 工具。安裝不執行掃描、不建立排程、不啟用 watch 或寄信。

官方格式核實日期 2026-10-30：

- [Package your plugin：portable manifest、本機 marketplace 與停用](https://developers.openai.com/plugins/build/plugins)
- [Desktop-only skills plugin 標記](https://developers.openai.com/plugins/deploy/desktop-only)

## 前置檢查與配置

以下 `PLUGIN` 代表解壓後的 `plugins/diffusion-reels-local`，只是說明中的路徑佔位值。執行指令時使用其絕對路徑。每次都傳入同一組來源、歸檔與資料庫，避免建立第二份候選歷史；預設會使用桌面 Reels 成片資料夾與 Application Support/ReelPublisher/state.sqlite3，既有使用者應明確指定已在用的資料庫。

```sh
python3 /absolute/PLUGIN/scripts/reels.py \
  --source /absolute/Reels成片/待發佈 \
  --published /absolute/Reels成片/已發佈 \
  --database /absolute/private/state.sqlite3 preflight
```

preflight 純讀，不建立資料庫、不掃描影片、不連網及讀憑證。`runtime_ready=false` 時先解決 missing；`configured=false` 或 `enabled=false` 表示尚未配置／啟用，不代表可自動執行。

```sh
python3 /absolute/PLUGIN/scripts/reels.py --database /absolute/private/state.sqlite3 \
  chat-setup --first-scan 'YYYY-MM-DDT08:00:00+08:00'
python3 /absolute/PLUGIN/scripts/reels.py --database /absolute/private/state.sqlite3 \
  chat-enable --confirm-primary
```

自訂來源時在以上各命令維持相同 --source／--published。setup 保持停用，enable 只允許本資料庫以 Codex 作主要掃描通道；它不操作 Codex 排程器，也不啟用任何雲端功能。首次掃描時間保存隔日節奏，不可透過重跑 setup 改寫既有歷史。

若已有 SMTP tick/watch 使用同一資料庫，Codex enable 會拒絕接手。先停止舊背景服務並明確核對，再執行 `scan-release-primary --confirm-stopped` 釋放通道，之後才 chat-enable；釋放會停用本機 chat-check，但保留節奏、候選及回報紀錄；不能為繞過拒絕而建立另一個資料庫。新版 tick/watch 也會拒絕在 Codex 主通道下運行。這是同一資料庫內的互斥，不能偵測另一個資料庫或舊版程式的背景服務；部署前仍須核對只有一條主要來源。

## 手動立即掃描與檔案穩定性

`scan` 回傳 discovered 與 skipped，每個略過項目包含原因；`chat-check` 也保留當次 skipped。影片最後修改後需穩定至少 10 秒，剛複製／匯出的檔案會略過；scanned=true 只表示掃描有執行，不保證每個檔案可入列。先告訴使用者略過原因，待檔案完成並穩定後，在相同資料庫明確執行 scan → chat-check。這樣可立即發現新候選而不重設下一個隔日掃描時間，也不必更換資料庫。定時檢查沒有新候選時仍保持安靜，不能用 skipped 當成發佈授權。

## 對話回報與確認

```sh
python3 /absolute/PLUGIN/scripts/reels.py --database /absolute/private/state.sqlite3 chat-check
python3 /absolute/PLUGIN/scripts/reels.py --database /absolute/private/state.sqlite3 chat-status
```

chat-check 每兩個日曆日到期才掃描；錯過多次時只補掃一次，下一次仍沿原節奏。它使用與 scan 相同的內容比對及 Workflow，候選與通知共用同一個 SQLite；狀態庫及共用 scan.lock 序列化多個觸發。

notification 為 null 就保持安靜。否則將其中 items 在目前對話呈現一次，並附 report ID。回傳前已持久記為 **unconfirmed**；這是「領取過一次，送達未確認」，不是收到證明。工具輸出、agent 生成文字、對話顯示或桌面彈窗都不會自動改為 received。若領取後程式／輸出中斷，下一次不重報，chat-status 留有 report ID 供人工核對。跨本機與對話無共同交易，因此採保守不自動重送，不能宣稱恰好送達一次。

只有使用者明確確認收到整份報告，才記錄：

```sh
python3 /absolute/PLUGIN/scripts/reels.py --database /absolute/private/state.sqlite3 \
  chat-resolve REPORT_ID --outcome received --confirm-checked
```

查閱原回報用 chat-report REPORT_ID，查閱不重送。若確定未送達且使用者明確接受再次提醒，才把 outcome 改成 not-delivered；事件回到 pending，下次 chat-check 才領取新的 report ID。相同確認可重跑，不同結果不能覆寫已完成核對。通知確認與影片內容核准分開。

錯誤與恢復使用相同持久通知機制。相同未變的掃描故障只回報一次；故障不消耗掃描時段，恢復後補掃並回報恢復事件。單檔不適用原因仍可透過 scan 的 skipped 查閱，不能把無效影片當作可核准成片。資料庫或程式自身不可用時可能無法保存錯誤，此時需由呼叫端保留首次阻擋，不重建另一個資料庫；這不是獨立於 Codex 的即時監控。

## 既有 JSON 通知紀錄的遷移

遷移是明確操作，不會自動尋找 `.env`、chat-notices 或任何其他對話配置。**這次沒有遷移目前 ACTIVE 任務正在使用的資料庫或通知檔。** 上線時先停用或暫停原任務，備份既有資料庫，確認使用同一資料庫與來源，才操作新工具。

```sh
python3 /absolute/PLUGIN/scripts/reels.py --database /absolute/private/existing-state.sqlite3 \
  chat-import --ledger /absolute/private/existing-chat-notices.json --confirm-checked
```

只接受 reported_candidate_ids 字串陣列，所有 ID 必須存在於所選資料庫。壞 JSON、重複／未知 ID 或混用資料庫整批拒絕，不部分寫入。舊「已回報」只導入 unconfirmed，避免假造已送達，也避免再自動提醒同一候選。重複導入同一清單冪等；現有通知狀態優先，不覆寫已核對紀錄。

完成遷移並核對後，才由使用者授權更新原定時任務，改呼叫安裝後的 chat-check，而不再手寫 JSON 去重。保留每兩天台北08:00、同一審核對話與私有資料路徑。不要建立第二個任務；本次不修改已 ACTIVE 的 reels。

## 文案與版本核准

沿用 list、get、caption、preview、approve、明確 replay。範例：

```sh
python3 /absolute/PLUGIN/scripts/reels.py --database /absolute/private/state.sqlite3 list
python3 /absolute/PLUGIN/scripts/reels.py --database /absolute/private/state.sqlite3 caption ID --text '使用者提供的文案'
python3 /absolute/PLUGIN/scripts/reels.py --database /absolute/private/state.sqlite3 preview ID --first-date YYYY-MM-DD
python3 /absolute/PLUGIN/scripts/reels.py --database /absolute/private/state.sqlite3 approve --versions-file /absolute/private/reviewed-versions.json
```

先讓使用者查看影片、完整文案、順序、日期、時區與 revision，再整批核准；修改後重新確認。核准檔為 {"候選ID":審閱版本整數}。approved 只表示本機審核通過，影片不移動、不上傳、不建立正式發佈工作。本機入口不提供 instagram-check、SMTP、雲端原型或正式發文命令。

## 升級與停用

升級前先暫停既有 Codex 任務，核對沒有正在回報的操作，備份私有狀態。安裝新版到新目錄，保留原 source／published／database；preflight 後確認舊候選及 unconfirmed report 都在，再更新同一 marketplace 路徑並按官方流程重新載入。重新 setup 不能重設節奏或清除歷史。只有核對完成且得到授權才恢復原任務。

停用分成兩層：先以 Codex automation 工具停用對應排程，再執行同一資料庫的 chat-disable。它保留候選、通知、文案與核准，阻止後續 chat-check。若只停用 plugin 而排程仍呼叫舊腳本，排程可能繼續工作，不能宣稱已停止。

本機 marketplace plugin 可在 Plugins 停用；受信任專案也可用官方 `.codex/config.toml` 的 `[plugins."diffusion-reels-local@diffusion-reels-personal"] enabled=false`。不要直接改寫使用者現有整份設定。移除套件前先核對排程停止；私有資料庫不隨套件刪除。這些本機停用操作不會取消任何已啟用雲端工作。

## 本次證據與未完成項目

安裝包在臨時目錄解壓後，已用合成影片跑通公開 CLI 的 preflight → 配置／啟用 → 掃描 → 明確回報確認 → 重跑去重 → 文案／日期／版本核准 → 本機停用，未移動或上傳影片。另驗證並行觸發、輸出中斷、掃描中斷、錯誤／恢復與舊通知遷移。

後續實機安裝與安裝副本驗證已完成；尚需使用者重啟 App 並核對新對話與既有對話載入；再經授權遷移原狀態與更新原 ACTIVE 任務。真正08:00到期、桌面通知可見性與休眠恢復需 #7 實測。官方 IG、雲端排程、遠端事件同步與完整 plugin 在其他票驗收；此套件不替代它們。
