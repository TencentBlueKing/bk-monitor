# Skill: TAPD Submit Backfill（Comment-Only + Commit/PR Gate）

Trigger（`.aafe.config.json` → `tapd.enabled === true` **且任务过程中有关联 TAPD 单**）:

1. **自测流程结束后**（含用户跳过自测）
2. 用户意图 **commit / push / submit / 提交代码 / 提测 / 提 PR**（且本任务有 TAPD 关联）

**无 TAPD 关联**：跳过 Phase E/F 及 C1 新建/关联询问；可常规 Commit/PR。

Companions:

- Hard rule: `.ai-agent/rules/tapd-submit-backfill.mdc`
- Self-test: `.ai-agent/skills/minimal-convergent-self-test.md`
- Impact: `.ai-agent/skills/architecture-impact-test-forecast.md`

## TAPD 关联判定

进入本 Skill 回填分支前，确认任务过程中**已涉及 TAPD 单**（ID/链接/MCP/用户绑定）。  
**否** → 不执行 Phase E/F；Commit 用常规 message；结束。

## End-to-end pipeline（有关联 TAPD 时）

```text
[A] 确保自测产物齐全（缺则先跑 impact + self-test；代码变更任务才需）
[B] 询问是否 Commit
    ├─ 是 → [C]/[D] 按 submit.cli（git|gtm）执行 Commit/PR → [E] 询问回填 TAPD
    └─ 否 → [E] 仍询问回填 TAPD
[E] 同意 → [F] 评论回填 + 可选 PR 字段 + 状态流转
    拒绝 → 结束
```

**Hard：** 有关联 TAPD 时，即使不 Commit 也必须执行 [E]。**无关联**则整段 [E][F] 跳过。

### Submit CLI 选择（强制先读配置）

Read `.aafe.config.json` → `submit.cli`:

| 值 | 含义 |
| --- | --- |
| `git`（默认） | Phase C/D 走 Git CLI + `gh` |
| `gtm` | Phase C/D 走 `gtm commit` / `gtm pr` |

可用 `aafe update --submit-cli=git|gtm` 更新配置。

---

## GTM Task Start — 分支与 TAPD 关联（仅 `submit.cli=gtm`）

**触发**：新任务开始（已拿到具体 TAPD 单 / 需求，准备改代码前）。`submit.cli=git` 时跳过本节。

### G0 检查当前分支是否已关联 TAPD

```bash
git branch --show-current
```

GTM 关联分支命名约定：

```text
{type}/{feature-slug}/#{tapd_full_id}
```

示例：`feat/search-tag/#1010158081136674445`

| 段 | 含义 |
| --- | --- |
| `feat` / `feature` | 需求（story） |
| `bug` / `fix` | 缺陷（bug） |
| `search-tag` | 当前分支功能短名（可读英文） |
| `#1010158081136674445` | TAPD 链接最后一段数字 ID |

TAPD 链接示例：

```text
https://tapd.woa.com/tapd_fe/10158081/story/detail/1010158081136674445
→ full id = 1010158081136674445
→ GTM 单据短 ID = 最后 9 位 = 136674445
```

**判定**：

- 当前分支匹配 `{type}/{slug}/#{digits}` → **已关联**，记录 `tapd_entry_type` / `tapd_entry_id` / `tapd_short_id`，进入需求分析/开发
- 不匹配（如 `master` / `main` / 无 `#id` 后缀）→ **未关联**，执行 G1

### G1 未关联时：`gtm create issue` 关联已有单据并建开发分支

```bash
gtm create issue
```

按交互提示依次操作：

1. 选择 **关联已有单据**
2. **输入单据 ID**：TAPD 地址最后一段数字的**最后 9 位**  
   - 例：`.../detail/1010158081136674445` → 输入 `136674445`
3. **请输入目标分支**：`master`（或项目约定的主干名）
4. **请输入新的开发分支名称**：根据 TAPD 单据标题生成**可读英文短名**（kebab-case，如 `search-tag`）  
   - 只需输入功能短名；**系统会自动补充前缀（feat/bug）与后缀（`#fullId`）**
   - 不要手写完整 `feat/.../#...`，避免与 GTM 自动规则冲突

完成后再次 `git branch --show-current`，确认已变为 `feat|bug/<slug>/#<fullId>`，再继续写代码。

**失败/异常**：简要报告；由项目 GTM 侧处理，本 Skill 不强制降级；未关联成功时提醒用户手动完成后继续。

---

## Core policy（回填）

| Allowed | Forbidden for backfill |
| --- | --- |
| `comments_create` | `stories_update` / `bugs_update` 改 `description` |
| 状态逐步流转（status only） | 改写 `test_focus` / 业务自定义字段正文塞自测 |
| 图片上传后嵌入评论 | 覆盖原单背景、截图、目标 |
| PR 链接字段写入（见 Step F3） | 跳步状态（如 backlog→doing）、伪造测试 pass |
| 用户明确要求的其它单字段 | 自动流转到 for_test / status_done |

---

## MCP workflow（user-tapd_taihu）

1. `lookup_tool_param_schema` → get args
2. `proxy_execute_tool` → execute
3. Optional: `lookup_tapd_tool` when unsure

Common tools: `stories_get`, `stories_create`, `stories_update`, `bugs_*`, `comments_create`, `tapd_id_get`, `tapd_file_upload_url_generate`

## Config（`.aafe.config.json`）

### `submit.cli`（Commit/PR provider）

```json
{ "submit": { "cli": "git" } }
```

- `git`（默认）：Git CLI + `gh`
- `gtm`：`gtm commit` / `gtm pr`
- Update: `aafe update --submit-cli=gtm`

### `tapd`

Use `workspace_id`, `milestone_id`, `tapd_story.*`, `tapd_bug.*` status values.
Submit-backfill story target is `status_doing` (first token if comma-separated); do **not** auto-advance to `status_done`.

Optional PR field keys（任一存在且非空即用）:

- `tapd.pr_field`
- `tapd.tapd_story.pr_field`
- `tapd.tapd_bug.pr_field`

字段名示例（以项目实际为准）：`source`、`custom_field_*`、业务配置的「PR 链接」字段。未配置时见 Step F3 探测。

---

## Phase A — Ensure artifacts

Ensure before Commit/回填询问：

| Artifact | Source |
| --- | --- |
| 处理结果 / 变更摘要 | 本次 diff + 结论 |
| 影响范围 | `architecture-impact-test-forecast.md` |
| 自测结果 | `minimal-convergent-self-test.md` |
| `ui_test_paths`（若有 UI case） | 自测 Skill Step 2.5；执行 UI 前必须已生成 |

若缺失：先补跑 impact + self-test（含 UI 是否测、URL、路径预生成）。用户明确「跳过自测」：产物标注 `self_test=skipped`，仍可进入 B/E。

---

## Phase B — Ask Commit

问：

> 自测已完成。是否执行 Commit？

| 回答 | 动作 |
| --- | --- |
| 是 / Yes / Y / 需要 / 提交 / commit / 好的 / 可以 / ok | → Phase C |
| 否 / No / N / 不需要 / 跳过 | → Phase E（**仅有关联 TAPD 时**；否则结束） |

---

## Phase C — Commit

先确认 `submit.cli`（见上表），再执行对应分支。仅在用户同意 Phase B 后执行。

### C1 Resolve TAPD entry（**仅有关联 TAPD 时**）

| Source | Action |
| --- | --- |
| TAPD-origin task | Use known `entry_type`, `entry_id`, `workspace_id`, title |
| User provides ID | Short ID → `tapd_id_get`；确认 story vs bug；`stories_get` / `bugs_get` 取标题 |

**无 TAPD 关联**：不询问新建/关联单、不索取 `workspace_id` / `milestone_id`。

**禁止**在无 TAPD 关联时瞎编 `--bug=` / `--story=` ID。

### C2 Message hint（有关联 TAPD 时）

```text
# bug
bug: {TAPD标题} --bug={bug_id}

# story / 需求
feat: {TAPD标题} --story={story_id}
```

若 `submit.cli=gtm` 且项目 GTM 已自动注入 TAPD ID，可直接执行。

### C3a Execute when `submit.cli=git`（默认）

按仓库 committing-changes 规则：`git status` / `diff` / `log` → stage 相关文件 → commit（HEREDOC message）→ `git status` 验证。  
Hook 失败：修问题后 **新建** commit，禁止擅自 amend（除非用户规则允许）。

### C3b Execute when `submit.cli=gtm`

```bash
gtm commit
```

- 成功：记录 commit 结果（若输出可见）
- **失败/异常**：简要报告；由项目内 GTM/钩子处理，**不强制**重试、amend 或降级裸 git；**不阻断** Phase D/E

---

## Phase D — Try PR

### D1 when `submit.cli=git`（默认）

Commit 成功后尝试 PR：

1. 确认分支相对 base 的提交与远程同步（按 creating-pull-requests 规则）
2. 需要时 `git push -u origin HEAD`
3. `gh pr create`（HEREDOC body），Summary 含变更要点；Test plan 可引用自测表
4. 记录 `pr_url`；失败则报告原因，**不阻断** Phase E

### D2 when `submit.cli=gtm`

```bash
gtm pr
```

- 成功：记录 `pr_url`（若输出可见）
- **失败/异常**：简要报告；项目内处理，**不强制**补救或降级 `gh`；**不阻断** Phase E

---

## Phase E — Ask TAPD backfill（**仅有关联 TAPD 时**）

无 TAPD 关联 → **跳过本 Phase**，不向用户问回填。

有关联时，**无论** B 选否、C/D 成功或失败，都要问：

> 是否回填 TAPD 单子？（将追加评论：处理结果 / 影响范围 / 自测结果；若有 PR 且存在 PR 字段则写入链接）

同意词：`是` / `Yes` / `Y` / `需要` / `同意` / `回填` / `好的` / `可以` / `ok` 及明显同义肯定。  
否定：跳过并说明可稍后手动触发本 Skill。

---

## Phase F — Backfill（同意后）

### F1 Resolve entry

使用任务过程中已关联的 `entry_type` / `entry_id` / `workspace_id`。  
**禁止**在无 TAPD 关联时进入 F1–F6 或询问新建单 / `workspace_id` / `milestone_id`。

### F2 Upload UI screenshots（optional）

仅当自测产出 UI 截图：

1. `tapd_file_upload_url_generate` `{ upload_kind: "image", workspace_id }`
2. HTTP POST 图片到 `upload_url`（短链，尽快上传）
3. 保留 `html_code` / `image_src` 嵌入评论

禁止靠改写 description 挂截图。

### F3 PR 链接字段

若 Phase D 得到 `pr_url`（或用户提供 PR URL）：

1. 读配置 `pr_field`（story/bug 各自优先，否则 `tapd.pr_field`）
2. 未配置：`stories_get` / `bugs_get` 查看返回字段；或 `lookup_tapd_tool` 检索「获取需求/缺陷自定义字段」；名称含 `pr` / `pull` / `git` / `合并` / `MR` 等且语义为链接的字段可候选，**向用户确认字段名后**再写
3. 确认存在后：`stories_update` / `bugs_update` **仅** `{ [pr_field]: pr_url }`（可加 `check_workflow` 若接口要求）
4. 无该字段或不确认：评论中写明 PR URL，不猜字段强写

### F4 Post comment only

`comments_create`:

- `workspace_id`, `entry_type`（story|bug）, `entry_id`
- `description`：下方模板
- UI 截图 `html_code` 放在「UI 截图」

#### Comment template

```markdown
## 处理结果
（做了什么、关键结论、改动文件）

## 影响范围
### 直接影响
...
### 间接影响
...
### 潜在影响
...

## 自测结果
| ID | Mode | 状态 | 命令/证据 | 摘要 |
| --- | --- | --- | --- | --- |
| TC-001 | unit | pass | `node --test ...` | ... |

### UI 测试路径（摘要）
（若有：入口 → 关键步骤序列；完整路径见自测产物）

### UI 截图
（若有：粘贴 tapd 返回的 html_code）

## 提交信息
- Commit: （hash / message；无则 `skipped`）
- PR: （url；无则 `n/a`）

## 未覆盖风险
...
```

未 Commit 仍回填时：`提交信息` 标 `Commit: skipped`，照常写处理结果与自测。

### F5 Status transitions（submit backfill: backlog → todo → doing）

内容回填 ≠ 状态更新。Status 仅用 update 的 **status 字段**。  
提交回填**只推进到 doing**，不自动走到 `for_test` / `status_done`。

固定链路（映射 `tapd_story`）：

`status_backlog` → `status_todo` → `status_doing`（取配置首个 token）

按**当前状态**决定剩余步骤：

| 当前状态 | 操作 |
| --- | --- |
| `backlog`（`status_backlog`） | 先 → `todo`，再 → `doing` |
| `todo`（`status_todo`） | 直接 → `doing` |
| `doing`（`status_doing` / doing 链内任一） | **不做处理** |
| 已是 `for_test` / `status_done` 等更后状态 | **不做处理** |

**Forbidden:** backlog → doing 一步跳过；提交回填自动改到 for_test。

#### Bug

对齐同一目标：向 `tapd_bug.status_doing` 推进；已在 doing 则跳过；不自动改 `status_done`。

Algorithm:

1. `stories_get` / `bugs_get` — current status
2. 按上表计算剩余步骤（可用 `storySubmitRemainingPath` 语义）
3. Advance **one step at a time** with `check_workflow: "permission,condition"`
4. Stop and report on failure; never skip; already-doing → report skipped

### F6 Report to user

- TAPD link/ID
- Comment ID / success
- PR 字段是否写入及字段名
- Screenshots embedded?
- Status transition log / final status / errors

---

## Pure GitHub / 无 TAPD 关联

If `tapd` absent, `enabled: false`, or **任务无 TAPD 关联**：

- 仍可按 `submit.cli` 走 Commit/PR（`git` 默认 / `gtm`）
- **不询问** TAPD 回填、新建单、`workspace_id` / `milestone_id`
- 用户**主动**要求关联 TAPD 时，可单独走本 Skill 并先确认 entry
