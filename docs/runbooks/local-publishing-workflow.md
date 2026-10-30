# 本機成片發現與排程審核

> 主要掃描／待審提醒改用 Codex 對話定時任務，每兩天台北08:00。SMTP／watch／launchd 為選用且非必要前置，不要和主要任務重複啟用。[現行需求與驗收](../specs/2026-10-30-codex-notification-amendment.md)；本機可重用plugin與回報工具由 #13 交付，真實到期／恢復由 #7 驗證。

目前可在本機完成候選掃描、防重複、填文案、順序及日期預覽、版本核准。雲端發佈尚未實作與部署；`approved` 只表示內容審核完成，不能解讀為已排程啟用。程式沒有正式發文命令。

## 安裝與驗證

需要 Python 3.11+ 與 FFmpeg／ffprobe。開發及測試在 repo 執行：

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[dev]'
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/mypy reel_publisher
```

本機預設來源為桌面的「Reels 成片／待發佈」，既有歸檔為「Reels 成片／已發佈」。兩個資料夾需已存在且互不包含；不擅自另建相近名稱目錄。狀態預設保存於使用者 Application Support 的 ReelPublisher 目錄，不寫進 repo。測試必須使用臨時資料夾，不用真實素材做核准或重發測試。

## 從掃描到核准

操作會輸出 JSON，供 agent 在對話中整理為使用者可審閱的清單。由 agent 呼叫工具不代表得到發文授權。

```sh
python3 -m reel_publisher scan
python3 -m reel_publisher list
python3 -m reel_publisher caption CANDIDATE_ID --file /absolute/path/caption.txt
python3 -m reel_publisher preview CANDIDATE_ID_1 CANDIDATE_ID_2 --first-date YYYY-MM-DD
```

首次預覽指定首發日期，之後省略日期沿用原本節奏。輸出每支影片的 ID、內容指紋、文案、版本與含時區的日期。日期固定以台北時間隔日 20:00 安排，過期或與已核准安排衝突時需重新預覽。

使用者確認完整清單後，將實際審閱版本寫成 JSON 對照，再核准：

```json
{"CANDIDATE_ID_1": 3, "CANDIDATE_ID_2": 4}
```

```sh
python3 -m reel_publisher approve --versions-file /absolute/path/approved-versions.json
```

數字是該次清單回傳的 revision，不是固定填入 3 或 4。修改文案或重新安排日期會使受影響舊版本失效；缺少文案、檔案變動、過期或版本不符時整批拒絕，不只核准其中一部分。

掃描發現同一路徑影片內容變更時，舊候選顯示 `invalidated` 及原因，舊核准清除，新內容建立新的待審候選。重複排除會顯示依據：`local_archive` 是本機既有歸檔，會附位置並標示平台未驗證；`existing_candidate` 則會附既有候選 ID。

明確重發時可使用 `replay /absolute/path/video.mp4 --confirm-replay` 建立新的待審候選；仍需填文案與核准。已有待審或已核准的同內容項目時會拒絕重建。

## 選用：SMTP 掃描與審核提醒（非主要流程）

Email 使用 SMTP over TLS，預設連線埠 465。非秘密設定包含 `REEL_SMTP_HOST`、`REEL_SMTP_PORT`、`REEL_EMAIL_FROM`、`REEL_EMAIL_TO`、`REEL_SMTP_USERNAME`。密碼從 `REEL_SMTP_PASSWORD` 環境變數，或明確指定的 macOS Keychain 項目取得。

使用 Keychain 時設定 `REEL_SMTP_KEYCHAIN_SERVICE` 及 `REEL_SMTP_USERNAME`；程式只讀取該服務與帳號，不搜尋其他已存憑證。可透過 Keychain Access 應用程式建立項目。不要把憑證放進 Git、指令參數、聊天或啟動設定明文。

程式不自動載入 `.env`；設定由執行環境提供。repo 的 `.env.example` 只有空值範例，個人收件地址可保存在被忽略的 `.env.local` 中，但尚需由使用者選擇寄信服務及配置寄件權限。

首次掃描時間須由使用者提供並包含時區：

```sh
python3 -m reel_publisher tick --first-scan YYYY-MM-DDTHH:MM:SS+08:00
python3 -m reel_publisher notices
```

`tick` 只在到期時掃描；錯過多次時補掃一次，下一次仍沿原本兩天節奏。發現候選後建立待審提醒，重複執行不重寄同一候選。寄送可能已被郵件服務接受但未回應時顯示 `unknown`，不自動盲目重寄；需人工核對後處理。`sent` 只表示 SMTP 接受，不保證收件匣投遞或已讀。

背景執行可使用 `watch`，由本機受控的背景服務維持：

```sh
python3 -m reel_publisher watch --first-scan YYYY-MM-DDTHH:MM:SS+08:00
```

它每分鐘檢查是否到期，實際資料夾掃描仍是每兩天一次。Mac 關機或休眠不會執行；醒來後補掃。尚未安裝或啟用任何背景服務，尚未寄出真實測試信。

## IG 帳號預檢與外部阻擋

`instagram-check` 只讀核對配置的帳號，並非 OAuth 授權實作，也不驗證發佈權限或執行正式發文。

完成 Meta 官方授權後，配置 `REEL_IG_ACCOUNT_ID`、`REEL_IG_API_VERSION` 及 `REEL_IG_LOGIN`（instagram 或 facebook）。API 版本須以設定當下的官方文件為準，工具不預設未核實版本。Token 放在 `REEL_IG_ACCESS_TOKEN` 或透過 `REEL_IG_KEYCHAIN_SERVICE` 明確指向以帳號 ID 為 account 的 Keychain 項目。

```sh
python3 -m reel_publisher instagram-check
```

目前只允許核對 @_eric_han。未配置時直接列出缺項，不呼叫發佈 API。Meta 應用程式是否存在、實際登入流程、權限、媒體傳輸及真實發佈都還需後續完成；不得以帳號檢查成功宣稱 Issue #2 已完成。

## 任務狀態與剩餘工作

| GitHub 任務 | 本次交付 | 尚缺 |
| --- | --- | --- |
| #2 | 只讀帳號預檢與憑證配置入口 | Meta App、正式授權、官方端點真實驗證、影片傳輸與核准後的單支發佈 |
| #3 | 候選掃描、內容防重複與歷史歸檔比對，程式審查已通過 | 無部署前置需求；只讀掃描不等於發佈 |
| #4 | 文案、順序、固定時段、版本核准與測試，程式審查已通過 | 上傳與啟用由後續雲端任務負責 |
| #7 | 到期掃描、補掃、通知去重及背景執行入口 | 寄信服務配置、首次掃描時間、真實投遞及背景服務驗證 |
| #5、#6、#8–#11 | 需求與依賴已記錄 | 依前置任務完成後繼續，雲端尚未部署 |

停止本機 `watch` 只能停止新候選掃描。未來若已啟用雲端發佈，停止本機程式不能視為取消雲端排程。

## 準備背景服務（不啟用）

在 repo 的虛擬環境完成安裝後，以使用者選定的首次掃描時間產生新目錄；以下都是佔位值，不能當作使用者已選定的時間。bundle 應放 repo 外的私人資料夾。

```sh
.venv/bin/python -m reel_publisher scan-service-prepare \
  --directory '/absolute/private/scan-service' \
  --first-scan 'YYYY-MM-DDTHH:MM:SS+08:00'
```

只產生 `settings.json`、plist、`enable.sh` 與 `disable.sh`，不安裝 LaunchAgent、不掃描或寄信。目錄權限 700，設定 600；存在時拒絕覆寫。使用產生 bundle 的同一 Python 環境，移動或刪除 checkout／虛擬環境前須先停用，之後重新產生。

在私有 `settings.json` 的 smtp 欄位填非秘密的 `REEL_SMTP_HOST`、`REEL_EMAIL_FROM`、`REEL_EMAIL_TO`、`REEL_SMTP_USERNAME` 及明確指定的 `REEL_SMTP_KEYCHAIN_SERVICE`；可另填 `REEL_SMTP_PORT`，只支援 implicit TLS，通常為 465，不支援 STARTTLS 587。密碼不可寫入設定檔；檢查會拒絕秘密欄位。寄件服務必須另行配置，不能因為設定了名稱便假定 Keychain 已有有效憑證。

```sh
.venv/bin/python -m reel_publisher.scan_service '/absolute/private/scan-service/settings.json' --check
```

`--check` 不讀 Keychain、不連 SMTP，也不證明憑證或投遞有效。只有使用者明確核准啟用及真實通知驗證後，才可執行 bundle 的 `enable.sh --confirm-enable`。它檢查設定後呼叫 launchctl bootstrap；若失敗請查看真實狀態，不宣稱安裝完成。啟用腳本將設定複製到使用者的 Library/LaunchAgents 後載入，既有同名設定不覆寫；停用會卸載並僅刪除與該 bundle 相符的已安裝設定。啟用失敗時可能留下待檢查的設定，可用該 bundle 的 disable.sh 清理。實機登入／重啟恢復仍待驗證；本次沒有執行安裝。

每分鐘啟動一個短 tick，實際掃描仍依兩天節奏；RunAtLoad 在載入時檢查是否補掃。launchd 觸發不保證每分鐘準時喚醒休眠電腦；沒有登入 session 或 Mac 關機時不執行。服務錯誤保存在 bundle 的 scan-error.log，不輸出原始 SMTP 錯誤。使用 `disable.sh` 停止這個掃描服務，不會取消任何雲端工作。

## 查看掃描失敗與核對通知

```sh
.venv/bin/python -m reel_publisher scan-status
.venv/bin/python -m reel_publisher notices
```

`scan-status` 顯示最近嘗試、成功、結果及下一次掃描。來源失去權限或不存在時記錄 failed，不消耗該次掃描時段；恢復後可補掃。沒有執行機會時不會捏造失敗或成功，最後嘗試時間可用來識別中斷。

通知 unknown 需要先核對寄件服務與收件信箱。確定已投遞可標記 delivered；明確確認未寄送／未投遞且決定接受重寄後，才使用 not-delivered 將通知恢復 pending，下一個 tick 才重寄。Message-ID 不是服務端保證去重；不能只因沒有看到信就認定未寄送。

```sh
.venv/bin/python -m reel_publisher notice-resolve CANDIDATE_ID \
  --outcome delivered --confirm-checked
```

## 未部署的雲端原型

完整準備範圍與限制見 [發佈服務準備](../design/publishing-preparation.md)。原型無正式發文 CLI、無真實平台轉接器，只在測試中使用合成素材及模擬平台。通過模擬不能把 #5–#11 改為已驗收。
