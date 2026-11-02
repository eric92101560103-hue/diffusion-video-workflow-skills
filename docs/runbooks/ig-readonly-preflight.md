# IG 只讀帳號預檢

這個入口只驗證指定帳號身分，不取得新權限、不上傳／發佈、不驗證正式發佈能力。#2仍需真實帳號及另外核准的單支影片驗收；空清單與Meta 100/33仍可能是外部授權問題，不會因本修正而自動解決。

## 明確指定登入流程

| REEL_IG_LOGIN | 官方主機與查詢 | 使用的帳號欄位 |
| --- | --- | --- |
| unified | graph.facebook.com，me/assigned_instagram_accounts | 清單中符合配置的IG id及username，不把me系統用戶當IG |
| instagram | graph.instagram.com，me，fields=user_id,username | 專業帳號user_id，不能用app-scoped id代替 |
| facebook | graph.facebook.com，配置的IG帳號路徑 | id及username；保留既有Facebook登入路線 |

不從token字首猜登入類型，也不自動切換主機或換憑證重試。統一登入先從官方帳號清單取得實際IG ID；若清單為空，不能用商家／系統用戶ID代替，也不能假設UI所見ID在所有路線都可讀取。

2026-10-30核實的官方來源：[統一登入驗證與存取憑證](https://developers.facebook.com/documentation/instagram-platform/instagram-api-with-unified-login/authentication)、[統一登入取得帳號](https://developers.facebook.com/documentation/instagram-platform/instagram-api-with-unified-login/get-started)、[Instagram登入帳號欄位](https://developers.facebook.com/documentation/instagram-platform/instagram-api-with-instagram-login/get-started)。後續正式啟用仍須依當時官方支援版本核實。

## 非秘密配置與執行

設定 REEL_IG_ACCOUNT_ID、REEL_IG_API_VERSION 及 REEL_IG_LOGIN。API版本沒有預設值，必須是已核實的版本。只允許本專案目標用戶名稱；不同username由共同Workflow拒絕。

憑證放在執行環境的 REEL_IG_ACCESS_TOKEN，或透過 REEL_IG_KEYCHAIN_SERVICE 指定本機「登入」鑰匙圈的一般密碼項目，account欄位必須等於配置的IG帳號ID。不要把憑證放在shell指令參數、Git、對話或一般日誌。程式不自動載入.env檔案。已曝光憑證先依Meta官方機制撤銷，單純新增憑證不證明舊憑證失效。

完成必要設定及安全憑證配置後執行：

```sh
.venv/bin/python -m reel_publisher instagram-check
```

成功輸出仍是 publishing_permission=not_verified、published=false。這是帳號預檢，不是發佈成功或雲端已啟用。

## 統一登入分階段診斷

`instagram-diagnose --business-id BUSINESS_ID`先用同一憑證核對`me?fields=client_business_id`，商家符合才查`me/assigned_instagram_accounts?fields=id,username&limit=100`。此命令在開啟Workflow之前執行，不建立或修改候選資料庫，不掃描影片、不發佈、不調整配置。

已撤銷曝光憑證、完成重新授權並更新指定鑰匙圈項目後，才執行以下命令。環境憑證優先於鑰匙圈，因此用`env -u`排除殘留環境憑證；命令不包含任何秘密：

```sh
env -u REEL_IG_ACCESS_TOKEN \
  REEL_IG_LOGIN=unified \
  REEL_IG_API_VERSION=v26.0 \
  REEL_IG_ACCOUNT_ID=17841403997461963 \
  REEL_IG_KEYCHAIN_SERVICE=EricReelsPublisher.Instagram \
  .venv/bin/python -m reel_publisher instagram-diagnose --business-id 793333293126263
```

| status | 意義及下一個核對點 |
| --- | --- |
| identity_verified | 商家、已配置IG ID與目標username均符合；仍未驗證發佈權限 |
| business_mismatch | 回傳的商家不符合，停止後續IG查詢；核對本次登入所選商家 |
| no_accounts_in_response | 商家核對通過，但本頁沒有IG帳號；不是token必然無效的證明 |
| account_id_mismatch | API本頁找到目標username，但ID不同；observed_account供人工核對，不自動覆寫配置 |
| account_not_uniquely_identified／username_mismatch | 未能唯一核對原配置身分；保守阻擋，不改用其他帳號 |
| request_failed | stage指出商家或IG清單階段；只保留已核實的商家與安全錯誤診斷，不輸出原始回應 |

只有`identity_verified`退出碼為0；其他結果為1。輸出固定保留`publishing_permission=not_verified`、`published=false`。`accounts_page_complete=false`表示還有後續頁面；不跟隨可能包含憑證的paging.next網址，也不把第一頁結果當作完整資產清單。診斷不測試發佈權限、不代表帳號健康狀態，也不能直接關閉#2。

## 可理解的阻擋

- 統一登入空清單：回報「未列出任何IG帳號」，不宣稱token一定無效，也不直接查系統用戶當IG。
- 找不到唯一符合配置的IG帳號／缺少欄位／回應格式異常：拒絕身分核對；不以另一帳號或單一相似username替代。
- HTTP失敗：只附HTTP、Meta數字錯誤碼／子碼及通過字元／長度／憑證比對的fbtrace_id；不回傳原始錯誤訊息、網址或payload。
- 網路／解碼失敗：回報未取得可核對結果；所有錯誤都不執行任何正式發佈。

HTTP呼叫只使用Authorization header，禁止redirect，token不放入查詢網址。統一登入目前最多核對一頁100個資產；未在本頁找到時保守阻擋，不宣稱完整帳號清單為空。未實作OAuth交換、token更新、App Review判定或即時權限擴張。

## 本次驗證範圍

使用共同Workflow／CLI原有公開邊界及替代Meta HTTP環境驗證三條登入路徑、系統用戶與IG身分區別、空清單／重複身分阻擋及數字錯誤碼不回顯秘密。未讀取使用者真實憑證、未呼叫真實帳號API。這些測試不能關閉#2。
