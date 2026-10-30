# 發佈準備雙軸審查

2026-10-30。固定點 `064bfcd692414c830ebe4c3188331de889df8a05`，比較 `git diff 064bfcd692414c830ebe4c3188331de889df8a05...HEAD`。初始交付 `9f5ad9a`，修正 `7e1145b`。

使用 code-review 技能，兩位獨立審查者分別檢查 Standards 與 Spec；未操作真實帳號、寄信或背景服務。原型交付限制以 `docs/design/publishing-preparation.md` 為準，不將局部模擬視為完整工程票驗收。

## Standards

已閱讀 AGENTS.md、docs/agents/issue-tracker.md、docs/agents/domain.md、GLOSSARY.md 及規格 Testing Decisions。沒有額外 CONTRIBUTING、CODING_STANDARDS 或 ADR。未發現明確的文件標準違反或需要修改的 baseline smell。

發現一項 P2 行為缺陷：舊 bundle 的 disable.sh 在檢查安裝設定歸屬前先 bootout 固定 Label，可能停掉後來替換的新版服務。以隔離目錄和替身 launchctl 重現，未操作真實服務。

已改成先確認設定存在並與本 bundle 完全相符，再停用與刪除。回歸測試修正前失敗，記錄到 print／bootout；修正後不同設定不呼叫 launchctl。原審查者複查確認缺陷解決、未發現新增問題，scan_service 四項測試通過。

## Spec

未發現超出範圍。以下三組限制已記錄，維持未驗收：

1. 「啟用前核對該版本」：本機 export_release 核對版本，遠端權威尚未接通；原型無法作為正式啟用授權。
2. 「Mac 關機後已啟用的雲端排程仍可執行」：本機原型不能證明雲端部署、跨服務競爭與實際關機執行。publishing 中斷先標 unknown 而不重送已模擬驗證。
3. 「同步雲端結果」「成功後七天清理雲端影片副本」：已模擬成功限定歸檔、拒絕覆寫及共享副本保留，真實同步、跨磁碟恢復、改名搜尋與物件儲存刪除驗證未完成。

在縮限原型內，未確認新增具體 bug。20:30 使用 >= 排除；unknown 不盲目重送；取消回報持久狀態；歸檔問題不重發；清理從成功／核對保守起點計算七天。

Standards：硬性違反 0，heuristic 0，行為缺陷 1 已修正。Spec：未揭露的實作錯誤 0，已揭露的部分涵蓋 3 組；不得關閉 #5–#11。
