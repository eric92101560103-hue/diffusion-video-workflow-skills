# 本機成片發現與排程審核

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

## 每兩天掃描與審核提醒

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
