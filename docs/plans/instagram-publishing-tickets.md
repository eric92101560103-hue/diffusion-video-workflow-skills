# Instagram 發佈任務拆分（Codex 提醒修訂）

2026-10-30。父規格 [#1](https://github.com/eric92101560103-hue/diffusion-video-workflow-skills/issues/1)原文保持不變。使用者已批准將Codex對話定時任務作主要提醒，並要求修訂工作票及完成無憑證可實作項目。現行通知準則見[修訂](../specs/2026-10-30-codex-notification-amendment.md)，完整責任及缺項見[框架檢查](../design/framework-completeness-audit.md)。

原T01–T10識別保持；新增T11=#13，從完整plugin切出無雲端可驗收的本機流程。此為修訂時的GitHub快照，後續狀態以實際議題驗收為準；PR #12已合併但僅為準備與模擬原型。

| 識別 | GitHub 任務 | 狀態 | Blocked by |
| --- | --- | --- | --- |
| T01 | [#2 授權指定 IG 帳號並完成單支核准影片發佈](https://github.com/eric92101560103-hue/diffusion-video-workflow-skills/issues/2) | 未完成 | None |
| T02 | [#3 成片進入候選清單並防止重複入列](https://github.com/eric92101560103-hue/diffusion-video-workflow-skills/issues/3) | 已完成 | None |
| T03 | [#4 在對話中填文案、調整順序並確認固定發佈時段](https://github.com/eric92101560103-hue/diffusion-video-workflow-skills/issues/4) | 已完成 | #3 |
| T04 | [#5 核准影片上傳後由雲端準時發佈](https://github.com/eric92101560103-hue/diffusion-video-workflow-skills/issues/5) | 未完成 | #2、#4 |
| T05 | [#6 取消或修改已啟用排程並查看真實結果](https://github.com/eric92101560103-hue/diffusion-video-workflow-skills/issues/6) | 未完成 | #5 |
| T06 | [#7 每兩天以 Codex 掃描成片並在對話提醒](https://github.com/eric92101560103-hue/diffusion-video-workflow-skills/issues/7) | 未完成 | #13 |
| T07 | [#8 發佈故障安全補發、核對結果並回報 Codex](https://github.com/eric92101560103-hue/diffusion-video-workflow-skills/issues/8) | 未完成 | #5、#7 |
| T08 | [#9 雲端結果同步回本機並正確歸檔](https://github.com/eric92101560103-hue/diffusion-video-workflow-skills/issues/9) | 未完成 | #5 |
| T09 | [#10 成功七天後清理雲端影片並保留紀錄](https://github.com/eric92101560103-hue/diffusion-video-workflow-skills/issues/10) | 未完成 | #5 |
| T10 | [#11 封裝完整發佈 plugin 並驗證雲端與 Codex 工作流程](https://github.com/eric92101560103-hue/diffusion-video-workflow-skills/issues/11) | 未完成 | #6、#8、#9、#10、#13 |
| T11 | [#13 安裝本機 Codex 掃描提醒與人工審核 plugin](https://github.com/eric92101560103-hue/diffusion-video-workflow-skills/issues/13) | 未完成 | #3、#4 |

## T01 — 授權指定 IG 帳號並完成單支核准影片發佈

GitHub：[2](https://github.com/eric92101560103-hue/diffusion-video-workflow-skills/issues/2)；狀態：open。

## Parent

https://github.com/eric92101560103-hue/diffusion-video-workflow-skills/issues/1

## What to build
使用者完成官方授權、核對帳號後，透過工具明確核准一支影片與文案，完成影片傳輸、媒體處理及正式發佈，取得可核對結果。此票驗證真實平台能力，不設定持續排程。

## Acceptance criteria
- [ ] 重新核實目前官方登入、權限、媒體規格與處理效期，並回報此帳號是否具備所需能力；未配置或不符時清楚阻擋，不假定自用免審。
- [ ] 操作入口能核對授權帳號，安全保存憑證；憑證不出現在 repo、聊天或一般日誌。
- [ ] 只對使用者明確核准的具體影片與文案執行測試發佈，等待媒體就緒後才正式發佈，並保存平台識別碼與可取得連結。
- [ ] 失敗或回應不明時不宣稱成功，不自動再次正式發佈；未取得真實發佈授權時只做模擬測試並明確標記真實驗證尚未完成。
- [ ] 共同操作入口的模擬整合測試通過，並附真實帳號及影片驗證結果或具體外部阻擋原因。

## Spec coverage

User Stories 1、22、23；官方 API 可行性、憑證與真實發文授權限制。

## T02 — 成片進入候選清單並防止重複入列

GitHub：[3](https://github.com/eric92101560103-hue/diffusion-video-workflow-skills/issues/3)；狀態：closed。

## Parent

https://github.com/eric92101560103-hue/diffusion-video-workflow-skills/issues/1

## What to build
使用者將成片放進指定來源後，可透過工具掃描並查看持久保存的候選清單；改名、重跑或既有已發佈影片不會無意間重複入列。這張票提供單次掃描，定時執行由 T06 補上。

## Acceptance criteria
- [x] 對齊既有匯出技能與實際成片來源，只掃描指定資料夾；不移動或發佈未核准影片。
- [x] 排除複製中、不可讀取及不適用檔案，顯示可理解原因；空資料夾正常完成。
- [x] 以內容辨識重複，候選資料可在重啟後保留；改名或重複掃描不另建同一候選。
- [x] 可初始比對既有已發佈影片，但標示為本機歸檔依據，不捏造平台成功紀錄；使用者明確指定重發才允許再入列。
- [x] 從指定來源到候選清單的公開入口驗證檔案穩定性、空輸入、重複、改名、重啟及明確重發。

## Spec coverage

User Stories 4、5、6、7、34；匯出交接位置修正。

## T03 — 在對話中填文案、調整順序並確認固定發佈時段

GitHub：[4](https://github.com/eric92101560103-hue/diffusion-video-workflow-skills/issues/4)；狀態：closed。

## Parent

https://github.com/eric92101560103-hue/diffusion-video-workflow-skills/issues/1

## What to build
使用者透過對話可呼叫的操作入口查看候選影片、輸入文案、調整順序、指定首發日期並確認批次，得到明確綁定影片與內容版本的核准清單。此票不以核准本身宣稱雲端已啟用。

## Acceptance criteria
- [x] 清單包含影片、文案、順序、日期及 Asia/Taipei 時區，可修改及整批確認。
- [x] 從指定首發日的 20:00 起按固定隔日節奏安排；新批次接在最後一筆有效安排後，不侵入既有時段，空缺不改變節奏。
- [x] 文案不完整、影片不可用或未核准時不得形成可啟用清單；核准綁定內容與時間，變更會使受影響核准失效。
- [x] 候選日期過期時提出下一可用時段並要求再確認，不立即發佈、不挪動既有安排。
- [x] 透過共同入口及可控制時間驗證上述行為，包括重啟後核准保存；清楚區別核准、傳送中與已啟用狀態。

## Spec coverage

User Stories 10–19、30；固定時段及核准邊界。

原生阻擋關係：#3。

## T04 — 核准影片上傳後由雲端準時發佈

GitHub：[5](https://github.com/eric92101560103-hue/diffusion-video-workflow-skills/issues/5)；狀態：open。

## Parent

https://github.com/eric92101560103-hue/diffusion-video-workflow-skills/issues/1

## What to build
使用者啟用一筆已核准安排後，工具傳送影片及核准內容至雲端，雲端在指定時段使用官方 API 發佈。Mac 掃描端停止仍可執行；初始交付可安全停止故障項目，不具備 T07 的自動補發能力。

## Acceptance criteria
- [ ] 提供可驗證單筆雲端排程的服務選型與限制說明，優先免費方案；若需付費，先取得具體費用確認才部署。
- [ ] 上傳與啟用可查進度並恢復，缺少核准、內容版本不符或上傳未完成時不能啟用；重新送出不建立重複發佈工作。
- [ ] 雲端驗證呼叫者、最新核准權威與內容版本，拒絕舊快照或撤回核准；保存影片、核准安排及平台結果；20:00 為目標發佈時間，提前準備媒體並核對就緒條件，不捏造平台零延遲保證。
- [ ] 持久任務在服務重啟及重複觸發後不盲目重送正式發佈；不明結果先停為待核對，不以資料夾名稱或上傳成功代替平台成功。
- [ ] 完成模擬整合驗證及 Mac 掃描端停止時的雲端排程驗證；真實發佈使用另外核准的影片、文案與時間，結果可查。

## Spec coverage

User Stories 16、20–23、30；排程持久化、部署與失敗先安全停止。

## Notification revision

2026-10-30 使用者已採用 Codex 對話定時任務為主要掃描與提醒來源，並授權修訂工作票與長時間實作。本修訂取代父規格中本票的 Email 必要條款；父規格原文保留為歷史，不改寫或關閉。雲端發佈及平台成功驗收未被取消。 發片定時器與補發仍在雲端，Codex只負責本機發現／人工審核及同步後的主要提醒；不因換提醒通道取消遠端核准權威、媒體處理、持久排程及Mac關機實測。

原生阻擋關係：#2、#4。

## T05 — 取消或修改已啟用排程並查看真實結果

GitHub：[6](https://github.com/eric92101560103-hue/diffusion-video-workflow-skills/issues/6)；狀態：open。

## Parent

https://github.com/eric92101560103-hue/diffusion-video-workflow-skills/issues/1

## What to build
使用者透過對話工具明確取消或修改既有排程，看到雲端確認結果；取消不挪動其他影片，修改內容或時間需重新核准，不能在新舊版本之間誤發。

## Acceptance criteria
- [ ] 未進入正式發佈的項目可明確取消；操作回報確認成功、失敗或待核對，不把請求送出當成取消成功。
- [ ] 核准後修改影片、文案或順序會使受影響安排重新待審；舊版本不繼續發佈，新版本未核准不啟用。
- [ ] 已進入正式發佈的競爭情境回報真實狀態，不承諾一定可取消，不自動刪除已公開貼文。
- [ ] 取消保留原日期空位；本機刪除、改名及移動不會取消雲端安排，排程清單可反映雲端結果。
- [ ] 透過共同入口驗證取消競爭、重複取消、修改後未核准與其他任務日期不變。

## Spec coverage

User Stories 19、31、32、33。

原生阻擋關係：#5。

## T06 — 每兩天以 Codex 掃描成片並在對話提醒

GitHub：[7](https://github.com/eric92101560103-hue/diffusion-video-workflow-skills/issues/7)；狀態：open。

## Parent

https://github.com/eric92101560103-hue/diffusion-video-workflow-skills/issues/1

## Scope revision

2026-10-30 使用者已採用 Codex 對話定時任務為主要掃描與提醒來源，並授權修訂工作票與長時間實作。本修訂取代父規格中本票的 Email 必要條款；父規格原文保留為歷史，不改寫或關閉。雲端發佈及平台成功驗收未被取消。

## What to build

使用者已啟用附加在審核對話的 Codex 定時任務，每兩個日曆日台北時間 08:00 掃描指定待發佈來源，發現新候選才回到該對話提醒填文案與審核。沿用 #13 的公開操作與持久回報狀態，不要求 SMTP／Email／launchd 或 IG 憑證。Mac／App 不可用時不能掃描，恢復後補掃一次。

## Acceptance criteria

- [ ] 保存並可核對唯一主要掃描任務、審核對話、Asia/Taipei 與每兩天08:00節奏；首次人工掃描與後續實際到期執行分開記錄，不能以 ACTIVE 或手動掃描代替排程實測。
- [ ] 定時執行透過 #13 的同一公開操作與配置的持久資料庫發現候選、建立待回報事件並在指定對話提醒；填文案、排序與核准能延續同一候選，不建第二份狀態庫。
- [ ] 同候選、改名、重複執行與同一未變錯誤不重複提醒；沒有新候選／新錯誤保持安靜。回報確認、中斷與未知結果採 #13 的保守恢復規則，不把產生提示視為已送達。
- [ ] Mac 休眠／離線／App 不可用及來源或狀態失效時如實阻擋；恢復後僅補掃一次、保留原日曆節奏，驗證去重及故障恢復。不擅自新增 watch／launchd 與同一主要任務重複執行。
- [ ] 驗證實際排程觸發、通知可見性、靜默重跑與恢復，明確揭露系統通知權限及電腦在線限制。掃描不讀IG／SMTP憑證、不寄Email、不移動／刪除素材、不上傳或發佈。

## Spec coverage

User Stories 2–3、8–9；Codex 對話提醒取代 Email 必要條件。#13 提供可重用本機工具，本票驗收真實定時操作。

原生阻擋關係：#13。

## T07 — 發佈故障安全補發、核對結果並回報 Codex

GitHub：[8](https://github.com/eric92101560103-hue/diffusion-video-workflow-skills/issues/8)；狀態：open。

## Parent

https://github.com/eric92101560103-hue/diffusion-video-workflow-skills/issues/1

## Scope revision

2026-10-30 使用者已採用 Codex 對話定時任務為主要掃描與提醒來源，並授權修訂工作票與長時間實作。本修訂取代父規格中本票的 Email 必要條款；父規格原文保留為歷史，不改寫或關閉。雲端發佈及平台成功驗收未被取消。

## What to build

對已啟用的雲端任務提供可理解的恢復流程：只有可確定未發佈的暫時錯誤才補發至當晚20:30；結果不明先核對，不重複發片。雲端持久保存需介入事件，本機／Codex下次可用並同步結果時在審核對話回報。這不保證Mac關機時即時桌面通知，亦不使用兩天掃描任務執行20:30前的補發。

## Acceptance criteria

- [ ] 區分媒體未就緒、明確未發佈、授權失效、正式結果不明，保存attempt、平台識別與可查進度；不得把任意HTTP錯誤或timeout當成確定未發佈。
- [ ] 只有可確認不重複才由雲端安全補發；台北20:30起停止新補發嘗試，後續日期不變，行為不依賴Mac或Codex在線。
- [ ] 平台成功但回應遺失／程序中斷時先核對或持久標示unknown，避免重新取得正式發佈權；未查到貼文不等於確認未發佈。
- [ ] 需要介入的失敗、授權失效、不明結果形成持久事件；受驗證的同步流程讓Codex取得並依同一事件ID回報／確認，失敗或未知不改寫發佈結果、不盲目重報。與候選提醒分開保存，不能只檢查本機新影片。
- [ ] 透過共同公開入口及可控制時間驗證重啟、重複觸發、20:30邊界、回應遺失、離線累積／恢復同步及回報去重；實際雲端／IG轉接器驗收另附證據。說明提醒延遲；若使用者要求離線即時通知，先另外確認通道與成本，Email僅為未啟用選項。

## Spec coverage

User Stories 26–29；沿用 #5 雲端執行與 #7/#13 的對話通知操作，補上遠端事件來源。

原生阻擋關係：#5、#7。

## T08 — 雲端結果同步回本機並正確歸檔

GitHub：[9](https://github.com/eric92101560103-hue/diffusion-video-workflow-skills/issues/9)；狀態：open。

## Parent

https://github.com/eric92101560103-hue/diffusion-video-workflow-skills/issues/1

## What to build
已啟用影片歸入已排程；正式發佈成功後，本機同步雲端結果並移入已發佈。Mac 離線期間雲端繼續執行，本機恢復後補同步，檔案移動失敗不導致重發。

## Acceptance criteria
- [ ] 只有雲端確認啟用後才歸入已排程；正式成功且有平台結果後才歸入已發佈，失敗或不明項目不誤歸檔。
- [ ] Mac 離線時保留真實雲端結果，恢復後可重複安全同步；已成功歸檔不因重跑而覆寫既有成片。
- [ ] 改名、移動、缺檔或同名檔衝突時清楚回報本機同步問題，不改寫平台成功、不重新發片或取消雲端任務。
- [ ] 剪輯技能交付位置、候選掃描及結果歸檔使用相同的使用者配置；不移動未經本流程核准的影片。
- [ ] 驗證關機後雲端成功、本機恢復同步、移動失敗與重啟重跑，區分平台成功及本機待整理狀態。

## Spec coverage

User Stories 21、24、25、33；三階段資料夾與雲端權威結果。

原生阻擋關係：#5。

## T09 — 成功七天後清理雲端影片並保留紀錄

GitHub：[10](https://github.com/eric92101560103-hue/diffusion-video-workflow-skills/issues/10)；狀態：open。

## Parent

https://github.com/eric92101560103-hue/diffusion-video-workflow-skills/issues/1

## What to build
成功影片到保留期限後自動刪除雲端影片副本，使用者仍能查看發佈紀錄及本機成片。未成功、待核對或仍被有效任務使用的資料不因清理而消失。

## Acceptance criteria
- [ ] 從已核實成功時間計算七天，未到期不刪除；清理可重複執行並顯示失敗或待清理結果。
- [ ] 清理僅作用於本流程的雲端媒體副本，不刪本機影片、平台貼文或持久發佈結果。
- [ ] 尚未成功、結果不明或仍供其他有效重發任務使用的媒體不能被成功清理規則刪除。
- [ ] 取消及停用的暫存清理、帳號解除連接及憑證撤銷有明確操作說明，不將它們混同於成功保留期限。
- [ ] 使用可控制時間驗證期限邊界與不同任務狀態，透過真實儲存整合確認刪除範圍受控。

## Spec coverage

User Stories 35、36；雲端副本清理及停用操作。

原生阻擋關係：#5。

## T10 — 封裝完整發佈 plugin 並驗證雲端與 Codex 工作流程

GitHub：[11](https://github.com/eric92101560103-hue/diffusion-video-workflow-skills/issues/11)；狀態：open。

## Parent

https://github.com/eric92101560103-hue/diffusion-video-workflow-skills/issues/1

## Scope revision

2026-10-30 使用者已採用 Codex 對話定時任務為主要掃描與提醒來源，並授權修訂工作票與長時間實作。本修訂取代父規格中本票的 Email 必要條款；父規格原文保留為歷史，不改寫或關閉。雲端發佈及平台成功驗收未被取消。

## What to build

把已驗證的正式發佈工具接入 #13 的本機個人plugin，讓使用者在同一審核對話完成候選、文案確認、上傳啟用、修改、取消及查結果；Codex定時任務為主要掃描／提醒來源，正式發佈由雲端負責。#13 可獨立驗收本機切片，本票仍需完整真實串接及部署證據。

## Acceptance criteria

- [ ] 延用 #13 可安裝的本機工具與技能，連接已驗證的雲端操作；不另建文案網站、不要求對話一直開著、不以安裝或本機核准宣稱雲端已啟用。
- [ ] 配置帳號、來源、唯一狀態資料庫、審核對話、每兩天08:00掃描、首發日期及隔日20:00雲端節奏；Codex為主要提醒，不以SMTP／Gmail／launchd作必要前置。費用與外部服務啟用仍需具體確認。
- [ ] 整體示範新影片→Codex提醒→對話文案／版本核准→完整上傳／啟用→雲端到期發佈→Mac離線／恢復同步及歸檔，並驗證修改、取消、unknown、補發及事件回報。真實發片必須另外核准指定影片、文案與時間。
- [ ] 安裝不發佈舊影片，缺設定時清楚阻擋；暫停本機定時任務、停用plugin與暫停／取消雲端工作有明確區別，可核對操作結果。不因停止掃描而假稱雲端已停用。
- [ ] 完成整合、安裝／升級／恢復及部署驗證，GitHub不含影片、憑證或個人收件地址；清楚揭露Mac／App不可用時本機掃描與對話提醒延遲，不能用模擬原型代替真實雲端驗收。

## Spec coverage

User Stories 37–38 及完整使用流程；#13為無憑證可驗收的前置切片，本票保留原本正式發佈驗收。

原生阻擋關係：#6、#8、#9、#10、#13。

## T11 — 安裝本機 Codex 掃描提醒與人工審核 plugin

GitHub：[13](https://github.com/eric92101560103-hue/diffusion-video-workflow-skills/issues/13)；狀態：open。

## Parent

https://github.com/eric92101560103-hue/diffusion-video-workflow-skills/issues/1

## What to build

在不需要 IG、雲端或寄信憑證的情況下，安裝個人 plugin／技能與本機工具後，可從對話掃描指定成片、持久保存待回報候選、確認已回報、填文案、排序、預覽固定時段及核准版本。這是從原 #11 拆出的本機完整切片，並補齊 #7 定時任務所需的可重用通知工具；不代表完整發佈 plugin 已驗收。

## Acceptance criteria

- [ ] 依官方支援的 plugin／技能格式提供可驗證安裝包與安裝、升級、停用說明；安裝不自動建立定時任務、掃描、讀取憑證或發佈既有影片。依賴或配置缺項時回傳可理解的阻擋。
- [ ] 對話工具可完整操作指定來源掃描、候選查看、填文案、順序與日期預覽及版本核准；延用 #3/#4 的公開工作流程，不另建文案網站；不移動或上傳未核准素材。
- [ ] 掃描與待回報結果持久保存；回報確認與發現分開，可重跑、並行或中斷恢復，同候選及同一未變錯誤不重複提醒；回報結果不明時可查且不盲目重送，恢復事件可辨識。公開輸出不得包含憑證。
- [ ] Codex 定時提示與狀態操作使用同一工具及狀態來源，不需 SMTP、Email、launchd 或 Keychain。可檢視使用模式及停用方式，避免同時以定時任務與 watch 掃描；不擅自修改使用者現有 ACTIVE 任務或私有資料。
- [ ] 使用合成影片／臨時狀態，透過既有共同 Workflow／CLI 公開入口完成安裝後的掃描→回報確認→重跑去重→文案／日期核准演示與必要恢復驗證。真實 IG／雲端操作明確阻擋，測試與模擬結果不當作真實發佈。

## Spec coverage

User Stories 2–14、18–19、34、38 的本機部分。2026-10-30 使用者已採用 Codex 對話定時任務為主要掃描提醒，並授權修訂工作票及實作無憑證可完成項目。#7 保留真實定時執行、通知及恢復的操作驗收；#11 保留完整雲端發佈 plugin 驗收。

原生阻擋關係：#3、#4。

## 前沿與驗收

#13的前置#3/#4均已完成，可立即實作；#7改等#13公開回報工具後驗收真實定時操作。#2由原對話持續處理，未通過前#5正式平台交付仍受阻，不能以模擬原型關閉後續雲端票。

#7不再等待SMTP；#8需要雲端介入事件與同步後對話回報，而非單純本機候選掃描。#11仍需完整真實發佈plugin驗收，#13本機切片完成不能代替它。新增T11保留原38項User Stories的覆蓋，通知通道的修訂由獨立文件明確記錄。
