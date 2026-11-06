# Diffusion Video Workflow Skills

以 Diffusion Studio 製作繁體中文字幕並輸出 IG Reels 的個人 Codex 技能集合。

目前收錄兩個核心技能，另有可打包的本機審核及 Meta 原生排程工作流程 Plugin。影片的剪輯與最終人工審核由使用者負責。

## 工作流程

已剪影片 → 繁體中文字幕 → 人工審核 → IG Reels 匯出 → 桌面待發佈資料夾

| 技能 | 用途 | 驗證狀態 |
| --- | --- | --- |
| [diffusion-tc-subtitles](skills/diffusion-tc-subtitles/SKILL.md) | 本機轉錄、繁中校正、語意斷句、可編輯字幕、整組樣式控制 | 已在兩支影片上使用；結構檢查與畫面抽查通過 |
| [diffusion-reels-export](skills/diffusion-reels-export/SKILL.md) | 人工審核後匯出高品質 Reels，檢查成片並交付 | 技能格式驗證通過；尚未實際完成一次匯出驗證 |

## 安裝

1. 下載或 clone 本儲存庫。
2. 將 `skills/` 內的兩個技能資料夾複製到 `~/.codex/skills/`；已有同名技能時先備份再比較內容。
3. 在 Codex 中確認兩個技能已可選用；若目前對話未重新載入技能清單，開啟新對話。

安裝技能不會自動安裝 Diffusion Studio、FFmpeg 或 Whisper 模型。

## 使用

開啟 Diffusion Studio 專案後，對 Codex 說：

```text
使用 $diffusion-tc-subtitles 幫我現在開啟的專案上字幕
```

人工確認字幕、時間與構圖後，再說：

```text
審核好了，使用 $diffusion-reels-export 幫我出片
```

## 預設

字幕使用 Noto Sans TC、白色與黑色陰影；1440 × 2560 畫布上的基準字級為 80 px。字幕內容與時間逐段可編輯，外觀由整組控制。完整樣式在 [settings.json](skills/diffusion-tc-subtitles/references/settings.json)。

Reels 上傳版預設為 9:16、1080 × 1920、30 fps、H.264 MP4 20 Mbps，音訊為 AAC 48 kHz 256 kbps。已核准專案明確使用 60 fps 時保留 60 fps。這些是個人輸出預設，不是 Instagram 唯一允許的格式。

匯出通過檢查後存入 `~/Desktop/Reels 成片/待發佈/`，以影片名稱與台北時間命名，保留既有同名成片。技能不會自動上傳或發佈社群。

## 執行環境與費用

- 此版本以 macOS 與已啟用 MCP／CLI 的 Diffusion Studio 為目標；API 以安裝版本自帶文件為準。
- 語音轉錄需安裝 whisper.cpp 與多語言模型，優先使用 Metal GPU；可重用已存在的轉錄快取。
- 成片驗證需要本機 FFmpeg／ffprobe。
- 目標是使用本機處理，避免 Diffusion AI credits；Codex 或其他外部服務本身的訂閱與額度另計。

本儲存庫包含技能、本機發佈工作流程工具、設定與字幕樣式範例，不包含影片、音訊、模型權重、逐字稿、憑證或個人專案檔案。新素材仍需人工核對辨識文字與時間；技能指令不保證每次都產生完全相同的結果。

## Reels Plugin：審核與 Meta 原生排程

掃描 → Codex 對話文案／版本核准 → 準備好即經 Meta Business Suite 原生 UI 上傳排程 → 修改／取消 → 結果核對 → 成功後歸檔。每兩天08:00掃描，預覽沿首發日隔日20:00；Meta 保存後由平台執行，不需自建雲端發佈服務。

[本機安裝及審核](docs/runbooks/codex-chat-publishing.md)、[原生排程／回執](docs/runbooks/meta-native-scheduling.md)、[有效規格](docs/specs/instagram-reels-publishing.md)。CLI 管理持久意圖、操作回執及安全歸檔；外部 UI 需可用的 computer use 與登入，不是原生排程 API。打包與合成測試不代表完整真實驗收已完成。

原 SMTP／雲端模擬與單支 API 工具保留為歷史／暫緩路徑，不是目前必要依賴。原 API media_publish 真實發文驗收另見 #17；未知原生結果絕不走 API 補發。停止掃描或 plugin 不取消 Meta 已保存排程。T09七天雲端副本清理已撤銷，不能控制 Meta 內部副本刪除。

儲存庫另提供 `.agents/plugins/marketplace.json` 供 GitHub marketplace 發現；此 PR 合併後可依 [官方 plugin 安裝流程](https://developers.openai.com/plugins/build/plugins) 加入此 repo。既有同名本機 marketplace 使用者先保留原設定，按操作手冊升級，避免建立第二套資料庫或掃描器。
