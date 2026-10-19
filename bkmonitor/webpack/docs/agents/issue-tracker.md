# Issue tracker: TAPD

Issues and specs for this repo live in TAPD, not GitHub Issues.

## Where work lives

TAPD workspace `10158081`.

建单、查单、改状态/负责人/迭代，以及 PR 成功后回写评论，走 `blueking-tapd-dev`，不在 GitHub Issues 建单。需求用 story、缺陷用 bug；commit 关联 `--story=<短ID>` 或 `--bug=<短ID>`。公开仓库的 commit / PR 不贴 TAPD 完整链接。owner 和迭代预填后仍需人工核对。反向建单只读 diff，展示草稿，确认后才创建。

## Pull requests as a triage surface

**PRs as a request surface: no.**

## When a skill says "publish to the issue tracker"

在 workspace `10158081` 创建 TAPD story 或 bug，操作走 `blueking-tapd-dev`。不要执行 `gh issue create`。

## When a skill says "fetch the relevant ticket"

用 `blueking-tapd-dev` 读取对应 TAPD story 或 bug。短 ID 就是 commit 里的 `--story=` / `--bug=`。

## Labels

Triage 角色使用 `docs/agents/triage-labels.md` 里的字符串。这不是 GitHub Issues，不要创建 GitHub label。只通过 `blueking-tapd-dev` 已经支持的 TAPD 字段或评论记录角色；没有对应能力时先问，不要新造字段。

## Close

关闭单据是一次 TAPD 状态变更，走 `blueking-tapd-dev`，先确认目标状态再改。
