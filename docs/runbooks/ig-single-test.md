# 單支 Instagram 發佈驗收

這是 #2 的人工驗收入口，不是每兩天／20:00 的持續排程，也不啟用現有本機 plugin 的正式發文能力。僅支援已核對的 Facebook Login 路線及指定的 @_eric_han。真實帳號預檢已成功；正式發佈能力仍需具體影片驗收。

## 先準備可審核結果

使用獨立的 `--database`、`--source`、`--published`，避免改動主要掃描器的候選與排程。先沿用共同 CLI 的 `scan`、`caption`，取得候選與最新 revision。若影片已有一般排程核准，不直接拿來當立即發佈測試；需另有獨立待審項目。

```sh
.venv/bin/python -m reel_publisher <共同路徑參數> instagram-test-prepare CANDIDATE_ID \
  --revision REVIEWED_REVISION --page-id 1424349244092893 --api-version v26.0
.venv/bin/python -m reel_publisher <共同路徑參數> instagram-test-get TEST_ID
```

準備入口只檢查影片並保存私有媒體副本與快照，不讀憑證、不建立容器、不上傳。回傳完整文案、原路徑、內容 fingerprint、revision、目標帳號、專頁與 `timing=immediately_after_explicit_approval`，狀態為 `awaiting_approval`。由操作者向使用者展示實際影片、完整文案及「核准後立即公開發佈」的時間語意。CLI 確認旗標只是執行機制，不能取代使用者對這份具體內容的核准。

本機保守檢查 MOV／MP4、單一 H.264／HEVC 影像、4:2:0、23–60 FPS、水平像素不超過 1920、長寬比範圍、3–900 秒、不超過 300 MB；有音訊時要求 AAC、48 kHz 以下、單／雙聲道及可核對且不超過 128 kbps。封閉 GOP、完整封裝細節與平台資格仍由 Meta 處理驗證。本機不保證所有規格與 PPA／審查條件都已通過，也不自動轉碼原檔。

## 取得具體核准後才執行

憑證配置沿用[只讀預檢](ig-readonly-preflight.md)，使用者的 Facebook 憑證存入指定登入鑰匙圈。工具只向指定專頁讀取其連結與專頁憑證，並以專頁憑證再核對 IG；專頁憑證只保留在記憶體，不保存至工作紀錄或輸出。

```sh
env -u REEL_IG_ACCESS_TOKEN \
  REEL_IG_LOGIN=facebook \
  REEL_IG_API_VERSION=v26.0 \
  REEL_IG_ACCOUNT_ID=17841403997461963 \
  REEL_IG_KEYCHAIN_SERVICE=EricReelsPublisher.Facebook \
  .venv/bin/python -m reel_publisher <共同路徑參數> \
  instagram-test-publish TEST_ID --confirm-publish-now
```

首次執行持久記錄立即發佈核准時間並保留候選，不允許同時改文案／重發。重新核對版本與媒體副本後，建立 `REELS`／`upload_type=resumable` 容器，串流傳送本機副本，再查 `status_code`。只有 `FINISHED` 才能送出 `media_publish`。所有 API 主機固定，不跟隨 redirect，秘密只置於授權 header。

| 回傳 status | 操作者下一步 |
| --- | --- |
| processing | 到 `next_check_at` 後才對同一 TEST_ID 執行相同命令；不建立另一份工作。每分鐘最多查一次，處理上限五分鐘 |
| published | 已保存正式媒體 ID；可取得時另存 permalink。重跑只回傳原收據，不再次發文 |
| blocked | 準備／上傳／處理未確認完成或核准逾時；不自動重送，先檢查 reason |
| publishing／unknown | 可能已發佈；先人工核對 IG，禁止重發或將查無結果當作未發佈的證據 |
| cancelled | 已停止本次測試，不能沿用舊快照發文 |

立即發佈核准有 30 分鐘操作上限，正式發佈前再次檢查；不把過期工作移至其他日期。正式請求送出前先持久記錄 `publishing`；逾時、失去回應、非法回應或程序中斷都不能自動再次發文。只有收到合法平台媒體 ID 才標記 `published`。permalink 讀取失敗不改寫已保存的成功結果。結果不明目前只提供人工核對，不會猜測貼文對應關係，也沒有自動恢復發佈功能。

取消未正式發佈的測試：

```sh
.venv/bin/python -m reel_publisher <共同路徑參數> instagram-test-cancel TEST_ID --confirm-cancel
```

取消不刪除原片、副本或遠端容器；若已進入 publishing／unknown／published，回傳原狀態，不能宣稱取消成功。可取消的項目回到待審並增加版本，新一輪仍須準備與核准。工具不移入已發佈資料夾；真實收據與歸檔屬不同動作，後續票另行驗收。

## 官方依據與驗證界線

2026-11-03核實：[內容發佈](https://developers.facebook.com/documentation/instagram-platform/content-publishing)、[媒體建立及 Reels 規格](https://developers.facebook.com/documentation/instagram-platform/instagram-graph-api/reference/ig-user/media#creating)。建立容器不等於發佈；容器 24 小時未發佈會過期。此工具在更短的人工驗收上限內執行，不儲存容器作長期排程。

模擬整合經共同 Workflow／CLI 驗證，只有外部 HTTP、媒體檢查程序及時間由測試控制。這不能取代 Meta 真實上傳與正式媒體收據，也不能證明憑證長期有效或 Mac 關機後會執行。未取得真實單支驗收結果前，T01 保持開啟。
