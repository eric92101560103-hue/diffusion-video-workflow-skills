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

Graph API Explorer的Configurations模式已顯示這份配置、用戶存取憑證及上述四項權限。最初在Codex內建瀏覽器點選Generate Access Token後沒有開啟授權視窗；頁面曾記錄Failed to fetch，但尚不能據此證實根因。之後使用者回覆已點選授權，重新連回Explorer已看到「用戶憑證」並完成以下真實只讀查詢。

## Facebook 用戶憑證真實只讀成功

以下查詢使用同一份Explorer中的新Facebook用戶憑證、graph.facebook.com、v26.0，不回傳或保存憑證欄位：

- `me?fields=id,name`：回傳Eric Han的Facebook用戶身分，與原SUAT的System User不同。
- `me/permissions`：`pages_show_list`、`instagram_basic`、`instagram_content_publish`、`pages_read_engagement`及原有`public_profile`均為`granted`。配置所列權限與憑證實際授予權限已分別核對。
- `me/accounts?fields=id,name,instagram_business_account{id,username}`：空data。不能單憑此結果宣稱專頁／IG不可存取。
- `1424349244092893?fields=id,name,instagram_business_account{id,username}`：成功回傳專頁「韓沂展 Eric Han」，其`instagram_business_account.id`為`17841403997461963`、username為`_eric_han`。
- `17841403997461963?fields=id,username`：成功回傳相同IG ID及`_eric_han`。這是目標IG的實際API身分讀取成功，已超過UI連結查核，但不是實際發文成功。

結論：Facebook Login用戶憑證可存取指定專頁與IG，無須為此次讀取再新增廣告／商家／訊息權限。專頁清單列舉與直接存取的行為不同，原因尚未確定；原Unified Login SUAT的失敗原因也尚未證實，不能把替代路線成功描述為已修復SUAT。

使用者已確認將新憑證另存登入鑰匙圈`EricReelsPublisher.Facebook`、account=`17841403997461963`，保留原SUAT項目。排除環境憑證後，以本機`REEL_IG_LOGIN=facebook`執行`instagram-check`成功，回傳相同IG ID／username、`publishing_permission=not_verified`及`published=false`。

另以指定專頁路徑在記憶體取得專頁憑證、再以此憑證核對IG，讀取`content_publishing_limit?fields=quota_usage,config`成功：當次quota_usage=0、quota_total=100、quota_duration=86400。只輸出數字、專頁及IG身分，不輸出或保存專頁憑證。這證明讀取此發佈相關端點可用，仍不等於正式發佈成功。憑證有效期與長期更新方式尚未驗收。沒有建立媒體容器、上傳影片或呼叫`media_publish`。

## 官方依據

2026-11-03經官方頁面重新讀取：

- [Unified Login驗證與存取憑證](https://developers.facebook.com/documentation/instagram-platform/instagram-api-with-unified-login/authentication)：SUAT、商家及/me身分、指定IG清單、機密儲存。
- [資格與排查](https://developers.facebook.com/documentation/instagram-platform/instagram-api-with-unified-login/eligibility-and-troubleshooting)：專業帳號／所屬商家、不同功能錯誤的分別處理、支援蒐證不能含秘密。
- [內容發佈](https://developers.facebook.com/documentation/instagram-platform/content-publishing)：Unified Login最小發佈權限、媒體處理及正式media_publish；可用Meta resumable上傳本機影片，後續T01可先驗證單支發文，不以正式雲端服務開通為必要前置。

T01仍未完成。Facebook路線已通過Explorer與本機身分預檢，單支上傳／處理／發文工具的操作與驗收限制見[人工驗收入口](../runbooks/ig-single-test.md)。本機實際素材與文案的待核准快照留在私有工作區，未加入repo。下一個外部前置為具體副本、完整文案與立即公開發佈的明確核准。原Unified Login仍保留不含秘密的蒐證；正式上傳／發文結果及憑證長期有效性尚未驗收。

後續使用者將該具體內容的發佈時間指定為2026-11-03 20:00 Asia/Taipei，要求串聯Codex Scheduled及原每兩日掃描；因此不執行立即發佈。另經Meta只讀debug_token確認，目前使用者與專頁憑證皆於當日13:00到期，早於所選時間，已交接使用者延長並更新指定鑰匙圈項目。未把定時提醒的建立視為Instagram已接受排程，也未在缺少新憑證效期證據時宣稱今晚可成功發佈。

使用者接著回覆已延長並更新。重新由指定鑰匙圈讀取，Meta只讀debug_token回傳使用者與專頁憑證皆is_valid=true、expires_at=0，專頁憑證讀取指定IG成功。這排除先前已知的當日13:00固定到期阻擋；0只記錄當次未列固定到期時間，不保證永久有效或免於撤銷。未輸出新憑證，仍未建立容器、上傳或正式發文。
