# Codex 本機通知與 plugin 審查

2026-10-30，主票 #13。固定點 main `baeb5affb4f18227f737afc44cbda23e5b888e8d`，初始實作 `270d56f`，試用後修正 `37f80ff`。規格依 #13 及 PR #14 的 `2026-10-30-codex-notification-amendment.md`。本分支不改原工作票／主規格，亦不修改現有 ACTIVE 任務或私有資料。

## Standards

依 code-review 技能，以獨立審查者檢查 AGENTS.md、issue-tracker、domain、GLOSSARY、Testing Decisions 及 Fowler smell baseline。未找到額外 CONTRIBUTING／CODING_STANDARDS。

文件化違規 0、需修改的 heuristic 0。共同 Workflow 保留公開測試入口，通知模組負責持久回報，不以私有資料結構斷言行為。主掃描通道互斥、JSON 特殊字元、保守 unconfirmed、套件離開 repo 後的執行均經審查及臨時測試。

## Spec

未發現範圍擴張或尚未修正的具體實作錯誤。生成／領取通知與使用者確認分開；重跑、中斷及未確認結果不盲目重報。Codex 與 SMTP 的同庫主通道互斥；跨資料庫／舊版程式無法自動偵測，已在安裝手冊要求核對交接。

仍有一組已揭露的部分驗收：App 實際辨識安裝包、既有及新對話載入尚未測試。本機 zip 解壓後的 CLI 演示不等於 App 已載入。#7 真實到期／通知可見性／休眠恢復與 #11 真實雲端完整發佈仍未驗收。

## 獨立技能試用及修正

使用 skill-creator 的 forward-testing，在隔離目錄實際打包解壓，依技能完成合成影片的前置檢查、配置、掃描、收到確認、文案、預覽、版本核准及停用。Python 使用隔離模式、不載入 site-packages，證明解壓後不依賴原 repo 的 editable 安裝。

試用發現剛匯出的影片可能因 10 秒穩定門檻略過，卻缺少操作說明。已讓 chat-check 保留 skipped 原因，技能新增手動 scan → chat-check 分支及穩定性說明；新回歸測試先失敗再通過。獨立試用者複查，在相同 DB 用穩定後的合成影片補掃，不重設 next_scan 即可領取通知，未誤認資料夾沒有影片。

自查另發現明確 not-delivered 後，若故障已恢復，舊 pending failure 可能與 recovery 一起重報。已在領取前將過時 pending 事件標為 obsolete，保留原 unconfirmed 報告歷史；回歸測試先紅後綠。Standards 與 Spec 審查者均複查這兩項增量，未發現新增問題。

所有演示只用臨時目錄／合成影片；未操作真實寄信、IG、Keychain、ACTIVE automation 或目前私有候選資料。

## 需要使用者返回後處理

- 核對實際 App 安裝與新舊對話載入；本次不重啟使用中的 App。
- 經具體授權後，備份並遷移原候選庫／chat-notices，更新原定時提示呼叫正式工具；不另建第二個任務。
- 在真正到期時檢查通知可見性與離線恢復，才可驗收 #7。
- IG 資產、正式上傳／發片、雲端服務與費用等由各原票繼續；本機通知不構成相關授權。

## 實機安裝驗收（2026-10-30，使用者授權後）

使用者已明確授權直接進行驗收。此輪以PR #15 `d52bbb1`建立獨立安裝包，使用本機Codex的正式指令註冊marketplace及安裝plugin。`codex plugin list --marketplace diffusion-reels-personal --json`確認`installed=true`、`enabled=true`、版本`0.1.0`，主機已接受portable manifest。

安裝快取位於`~/.codex/plugins/cache/diffusion-reels-personal/diffusion-reels-local/0.1.0`。已逐一比對23個安裝檔與來源檔完全相同；以此快取中的入口、Python隔離模式及不載入site-packages，在臨時目錄執行合成影片：前置檢查→配置預設停用→啟用測試庫→掃描→重跑不重報→明確收到確認→文案→日期預覽→版本核准→停用。停用後chat-check拒絕執行，IG／SMTP／雲端命令拒絕，測試影片未移動。

上述已證明真實Codex安裝管理器接受套件及安裝後工具可用，取代先前僅解壓驗證的部分證據。仍不能證明目前桌面App的既有／新對話已載入技能。電腦操作工具拒絕存取`com.openai.codex`，不能代替使用者重啟並檢查技能選單。此為工具限制，不是plugin載入失敗的證據。#13保持開啟，直到使用者完成畫面驗收。

本輪未重啟App、未切換既有ACTIVE任務、未遷移真實候選庫、未讀取IG憑證，也未操作真實影片。#7真正到期與恢復驗收、T01/#2及其正式雲端依賴仍未通過。

## 既有對話載入與排程交接（2026-10-30）

使用者於原既有對話成功選取並呼叫`diffusion-reels-local:reels-local-review`，系統技能目錄亦包含plugin提供的三個技能。本輪依該技能從安裝快取執行preflight，runtime_ready=true且missing為空；已證明既有對話能載入技能。另開全新對話的使用者操作仍未獨立驗證，不擅自建立新對話。

依先前「完成所有可自主驗收項目」的授權，已暫停既有reels任務，先以狀態庫副本驗證遷移，再於私有目錄以SQLite backup及原通知JSON副本保存備份。沿用原資料庫、原影片來源與原審核對話，匯入兩支已回報候選為unconfirmed；候選完整資料列及舊通知JSON均保持不變。配置首次自動掃描2026-11-01 08:00 Asia/Taipei，後續每兩個日曆日；不是修改原候選首發日期。

已更新原reels任務呼叫安裝後的chat-check，再恢復ACTIVE；未建立第二個任務。實機check回傳scanned=false、notification=null、next_scan=2026-11-01T08:00:00+08:00，證明此次未提前掃描或重報兩支舊候選。舊JSON保留備份但不再作排程去重來源；新的回報狀態由同一資料庫保存。

此輪未核准真實文案、首發日或素材，未移動、上傳或發佈影片。#7尚缺真正到期、通知可見性及休眠恢復的證據；不能因ACTIVE及手動check成功就關閉。#13既有對話載入已驗證，全新對話載入仍保留待驗收。
