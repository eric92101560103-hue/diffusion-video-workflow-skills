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

使用者明確回覆曝光憑證尚未處理或不確定。本輪沒有讀取鑰匙圈秘密、沿用曝光憑證測試、重新產生憑證、改權限或發文。已提供舊授權撤銷→相同資產及權限重新授權→更新登入鑰匙圈的人工交接。新憑證需由使用者完成輸入及提交，之後才執行只讀診斷。

本輪新增`instagram-diagnose`，同一憑證先核對商家，再核對指定IG身分；不建立候選庫，保留失敗階段、空清單／ID差異／username不符及分頁限制，不回顯秘密。仍待新憑證的真實API結果，才能判斷資產授權、舊憑證／ID混用或其他Meta端問題。首個成功只讀結果仍不等於真實發佈成功。

## 官方依據

2026-11-03經官方頁面重新讀取：

- [Unified Login驗證與存取憑證](https://developers.facebook.com/documentation/instagram-platform/instagram-api-with-unified-login/authentication)：SUAT、商家及/me身分、指定IG清單、機密儲存。
- [資格與排查](https://developers.facebook.com/documentation/instagram-platform/instagram-api-with-unified-login/eligibility-and-troubleshooting)：專業帳號／所屬商家、不同功能錯誤的分別處理、支援蒐證不能含秘密。
- [內容發佈](https://developers.facebook.com/documentation/instagram-platform/content-publishing)：Unified Login最小發佈權限、媒體處理及正式media_publish；可用Meta resumable上傳本機影片，後續T01可先驗證單支發文，不以正式雲端服務開通為必要前置。

T01仍未完成。下一個外部前置是使用者完成曝光憑證撤銷與安全替換；通過身分核對後，仍需具體測試影片、完整文案及發佈時間的明確核准，以及正式上傳／處理／發文工具的實作與真實驗證。
