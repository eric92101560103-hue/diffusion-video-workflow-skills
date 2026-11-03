# 2026-11-03 IG 帳號與授權排查

本次使用者授權繼續完成IG串接。主票為#2「授權指定 IG 帳號並完成單支核准影片發佈」。此紀錄只包含可公開核對的帳號／App配置與結果，不保存憑證、密碼、私訊或影片。帳號UI查核不等於API成功。

## 本次直接觀察

- Instagram登入帳號為`_eric_han`。「創作者工具和控制項」標題為「創作者」，可選「切換為商業帳號」及「切換為個人帳號」；因此目前為創作者帳號，沒有操作任何帳號類型切換。
- Instagram「帳號狀態 → 你無法使用的功能」顯示「目前可以使用所有功能」。這排除目前UI所列的功能處分，不保證API權限或所有安全檢查通過。
- Meta App `2341681909967569`的角色頁仍列管理員及`_eric_han` Instagram測試人員，後者沒有待接受邀請提示；統一登入的產生憑證表格仍列該帳號與`17841403997461963`。
- 商家`793333293126263`的「連結的應用程式」列Eric Reels Publisher，資產清單含`_eric_han`，操作清單含讀取個人檔案／貼文及上傳媒體／建立貼文。
- 選定配置`28933137333004395`（Eric Reels Publishing）標示與Instagram登入相容，SUAT、Instagram資產必填、`instagram_basic`及`instagram_content_publish`。預覽目前顯示永不到期，與先前約60天憑證的紀錄不同；測試憑證與正式配置可能有不同有效期，這不是已證實的失敗原因。

IG資產「連結的資產」頁顯示沒有連結的資產；商家導覽URL中的Page ID不能作為Facebook Page連結成功的證據。商家一般「系統工作人員」清單為空，也不能推論統一登入SUAT不存在；不據此另建人員、擴權或重新綁定帳號。

## 結論與尚未核實

目前沒有證據需要把創作者改為商業帳號，也沒有證據應以開啟第三方訊息存取作為內容發佈修正。官方內容發佈文件對Unified Login列的所需權限為`instagram_basic`及`instagram_content_publish`。不因文件列舉其他功能的錯誤就主動新增訊息／廣告權限。

使用者起初回覆曝光憑證尚未處理或不確定，後依人工交接回覆已更新。商家連結現在顯示2026-11-03新增，連結識別與舊紀錄不同，仍分享同一IG及兩項內容權限。憑證由使用者自行產生及更新；程式只從指定登入鑰匙圈項目讀入記憶體並向Meta呼叫，不將值寫入本報告、repo或一般日誌。未新增權限或發文。

本輪新增`instagram-diagnose`，同一憑證先核對商家，再核對指定IG身分；不建立候選庫，保留失敗階段、空清單／ID差異／username不符及分頁限制，不回顯秘密。Keychain確認逾時與API錯誤分開，允許60秒完成macOS確認；錯誤僅保留數字碼與通過字元、長度及憑證比對的fbtrace_id。

## 新憑證真實只讀結果

以`env -u REEL_IG_ACCESS_TOKEN`排除舊環境憑證，指定`EricReelsPublisher.Instagram`、account=`17841403997461963`，從登入鑰匙圈讀取使用者更新的項目。受限執行曾未能讀取；在明確授權的執行環境讀取指定項目後完成以下GET，未據此宣稱已證實第一次失敗的OS根因，也未讀取其他鑰匙圈項目。

- `me?fields=client_business_id`：`793333293126263`，符合預期商家。
- `me/assigned_instagram_accounts?fields=id,username&limit=100`：空data、無後續頁面，status=`no_accounts_in_response`。
- `me?fields=id,client_business_id`：新的System User ID=`122097788277539156`，與舊紀錄`122099677641529995`不同；商家仍相同。這支持本輪測試確實使用新的授權身分，不是重跑舊快照。
- `17841403997461963?fields=id,username`：HTTP400、Meta100/33；2026-11-03約02:57台北時間補收追蹤碼`Azpw7VckaezUiUtS2eMEoYk`。只讀故障蒐證，不重試正式發佈。

帳號類型／可用功能、UI資產分享及角色均已確認，但新SUAT的帳號存取仍未通過。尚不能斷定Meta平台bug、權限層級或其他授權映射才是根因。停止反覆重建相同配置及猜測ID。

## 已核准並建立的 Facebook Login 對照配置

進一步在Facebook專頁`1424349244092893`的Connected assets直接看到`_eric_han`，故先前IG資產頁空白不能據此判定專頁未連結。其View asset網址的`658794750661258`是另一UI資產識別；點入後展示的IG ID仍為`17841403997461963`。未把UI內部識別替代官方API帳號ID。

App仍提供Facebook Login舊版路線，官方頁明示需要連結專頁。使用者明確同意新增`pages_show_list`及`pages_read_engagement`，並只以現有同名專頁與IG進行對照。兩項已分別新增，權限頁均顯示「可供測試」。沒有使用包含額外權限的整批新增按鈕，也沒有新增`business_management`、廣告或訊息權限。

保留原Unified Login配置，另外成功建立`Eric Reels Facebook Test`，配置ID=`4622652997968792`：General登入、用戶存取憑證，恰好包含`instagram_basic`、`instagram_content_publish`、`pages_read_engagement`、`pages_show_list`。選擇專頁的限制仍須在實際用戶授權畫面確認，配置建立本身不等於已分享專頁或取得新憑證。

Graph API Explorer的Configurations模式已顯示這份配置、用戶存取憑證及上述四項權限。但在Codex內建瀏覽器點選Generate Access Token後，沒有開啟授權視窗，也沒有產生憑證；頁面曾記錄Failed to fetch，但尚不能據此證實網路或瀏覽器的根因。這是授權視窗未完成，不是已取得新Facebook憑證後API拒絕存取的證據。停止重複點擊，請使用者在平常的Chrome／Safari完成同一份配置的授權，僅選既有專頁／IG，遇到額外權限先停下。

新Facebook用戶憑證尚未取得；因此尚未執行對照路線的`me/accounts?fields=id,name,instagram_business_account`，不能把原SUAT的空清單結果套用成Facebook路線的結果。後續回報只提供帳號、專頁與錯誤摘要，不貼憑證；讀取專頁列表時不要求回傳`access_token`欄位。

## 官方依據

2026-11-03經官方頁面重新讀取：

- [Unified Login驗證與存取憑證](https://developers.facebook.com/documentation/instagram-platform/instagram-api-with-unified-login/authentication)：SUAT、商家及/me身分、指定IG清單、機密儲存。
- [資格與排查](https://developers.facebook.com/documentation/instagram-platform/instagram-api-with-unified-login/eligibility-and-troubleshooting)：專業帳號／所屬商家、不同功能錯誤的分別處理、支援蒐證不能含秘密。
- [內容發佈](https://developers.facebook.com/documentation/instagram-platform/content-publishing)：Unified Login最小發佈權限、媒體處理及正式media_publish；可用Meta resumable上傳本機影片，後續T01可先驗證單支發文，不以正式雲端服務開通為必要前置。

T01仍未完成。下一個外部前置是在Chrome／Safari完成已核准配置的Facebook授權，再核對專頁連結的IG。原Unified Login已有不含秘密的蒐證供Meta支援排查。通過身分核對後，仍需具體測試影片、完整文案及發佈時間的明確核准，以及正式上傳／處理／發文工具的實作與真實驗證。
