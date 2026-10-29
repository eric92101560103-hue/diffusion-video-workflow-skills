# Diffusion Video Workflow Skills

以 Diffusion Studio 製作繁體中文字幕並輸出 IG Reels 的個人 Codex 技能集合。

目前收錄兩個核心技能，另有開發中的本機成片發現與排程審核工具，尚未封裝成 Plugin。影片的剪輯與最終人工審核由使用者負責。

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

## 本機發佈工作流程工具（開發中）

已可掃描候選成片、防止內容重複、填文案、預覽隔日 20:00 日期與確認版本。另提供每兩天到期掃描、SMTP 審核提醒與只讀 IG 帳號預檢入口；寄信與背景服務仍需配置及真實驗證。

目前沒有雲端發佈服務或正式發文命令，`approved` 只表示本機審核通過。安裝套件不會啟用排程、上傳影片或寄信。安裝、測試、操作與尚缺配置見 [操作說明](docs/runbooks/local-publishing-workflow.md)。
