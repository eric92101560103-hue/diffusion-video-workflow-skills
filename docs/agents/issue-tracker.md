# Issue tracker: GitHub

本專案議題與規格使用 https://github.com/eric92101560103-hue/diffusion-video-workflow-skills/issues 。
範圍包括剪輯技能、未來的 plugin 打包、IG API 工具與發佈排程；不包含影片素材與帳號憑證。

## Operations

優先使用已連接且具備所需能力的 GitHub 工具；不足時使用 gh CLI。
CLI 操作明確指定 `--repo eric92101560103-hue/diffusion-video-workflow-skills`，避免誤用外層剪輯工作區。

- 建立議題：`gh issue create --repo eric92101560103-hue/diffusion-video-workflow-skills --title '標題' --body-file /absolute/path/body.md`。
- 讀取議題：`gh issue view NUMBER --repo eric92101560103-hue/diffusion-video-workflow-skills --json number,title,body,labels,comments`。
- 列出議題：`gh issue list --repo eric92101560103-hue/diffusion-video-workflow-skills --state open --json number,title,labels`。
- 更新標籤：`gh issue edit NUMBER --repo eric92101560103-hue/diffusion-video-workflow-skills --add-label LABEL` 或 `--remove-label LABEL`。
- 發表留言：`gh issue comment NUMBER --repo eric92101560103-hue/diffusion-video-workflow-skills --body-file /absolute/path/comment.md`。
- 關閉議題：`gh issue close NUMBER --repo eric92101560103-hue/diffusion-video-workflow-skills`。

將多行內容先寫入檔案，使用 --body-file 傳入。外部留言與發佈仍須符合當次使用者授權。

## Pull requests as a triage surface

PRs as a request surface: no.

## Skill conventions

技能要求「publish to the issue tracker」時，建立 GitHub issue。
要求「fetch the relevant ticket」時，依網址或編號讀取該 issue。
需要子議題時使用 GitHub 原生子議題；不可用時，在子議題開頭寫 `Part of #NUMBER`，並在父議題以清單連結。
需要依賴關係時優先使用原生 issue dependencies；不可用時寫 `Blocked by: #NUMBER`。

## Wayfinding operations

- Map：單一標記 `wayfinder:map` 的 issue，包含 Notes、Decisions-so-far 與 Fog。
- Child：map 的子議題，標記 `wayfinder:research`、`wayfinder:prototype`、`wayfinder:grilling` 或 `wayfinder:task`。
- Frontier：依 map 順序，選取第一個尚未關閉、沒有未結依賴且尚未指派的子議題。
- Claim：開始工作前將議題指派給執行者。
- Resolve：在授權範圍內記錄答案、關閉子議題，並在 map 的 Decisions-so-far 加入結論與連結。
