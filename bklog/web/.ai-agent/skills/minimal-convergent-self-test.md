# Skill: Minimal Convergent Self-Test

Trigger: after impact analysis (code-change tasks only), or when TAPD backfill needs self-test results.

Companion: `.ai-agent/skills/architecture-impact-test-forecast.md` (impact) → this skill (tests) → **完成后** 若任务有关联 TAPD 单 → `.ai-agent/skills/tapd-submit-backfill.md`.

## Goal

按**本次变更影响范围**做最小收敛自测：能 Mock 则 Mock；只有 UI 真需要时才问浏览器 MCP。  
含 UI 时：**先代码分析生成完整测试路径，再按路径执行**，禁止自测过程中反复大范围读代码。

## Step 0 — Decide test mode from impact

| Impact class | Default mode | Location |
| --- | --- | --- |
| Pure function / data transform / computed / cache / percent calc | **unit**（Mock 输入 → 断言输出） | `test/` under install root |
| Component logic with props/emit, no visual claim | **unit/component**（Mock Props） | `test/` |
| Store getter/action contract | **unit**（Mock state） | `test/` |
| Visible layout / CSS / popover / chart render / interaction | **ui-optional** | **仅代码变更任务且已进入本 Skill 时**条件询问浏览器 MCP |

Rules:

- Prefer the narrowest mode that can fail if the bug regresses.
- Example: 组件内数据处理逻辑变更 → 只测函数/方法 I/O，**不要**默认开浏览器。
- Do not invent E2E for logic-only diffs.

## Step 1 — Ensure test directory

Path: install-root `test/`（与 `.aafe.config.json` / `.ai-agent` 同级；无则创建）。

Suggested layout:

```text
test/
  unit/           # pure logic / props I/O
  fixtures/       # mock data
  ui/             # UI paths + screenshots + notes（授权后）
```

Naming: `test/unit/<module>-<topic>.test.ts`（或项目既有后缀）。  
UI 路径产物建议：`test/ui/<module>-<topic>.path.md`（或同会话内结构化输出，不强制落盘文档除非便于复跑）。

## Step 2 — Author minimal cases

For each case:

| Field | Requirement |
| --- | --- |
| ID | TC-001… |
| Priority | P0 / P1 / P2 |
| Mode | unit \| ui |
| Target | file/symbol under test |
| Mock | props / store / API fixtures only |
| Assert | concrete I/O or UI observation |

Converge:

- Cover the changed branch + one adjacent edge (empty / zero / stale cache).
- Skip unrelated modules.
- No real API / prod data.

### Runner

1. Prefer existing project test runner if present (`vitest` / `jest` / `npm test`).
2. If none: use Node built-in `node:test` + `node:assert` for pure logic.
3. Record the exact command in results.

## Step 2.5 — Pre-generate UI test paths（UI cases only, before browser）

当 `test_cases` 含 `mode=ui` 时，在询问浏览器 / 拿到 URL **之后、开始点击之前**，必须基于**本次 diff 影响范围**做一次集中代码分析，产出完整 `ui_test_paths`。之后执行阶段**只消费该产物**，禁止再大范围翻组件实现。

### 分析范围（收敛）

仅读：

- 变更文件及其直接模板 / render（`.vue` / `.tsx` / `.jsx`）
- 为定位交互控件所必需的子组件入口（点到能写出稳定 selector / 文案 / role 为止）
- 影响报告中的路由 / Tab / 面板入口

禁止：无关目录全库检索、自测中途「再分析一下整个模块」。

### 交互类型（必须覆盖到变更相关的）

| Action | 含义 | 路径中要写清 |
| --- | --- | --- |
| `navigate` | 打开页面 / 路由 | 完整 URL（用户提供）+ 必要 query |
| `click` | 点击 | 目标文案 / `data-*` / role / CSS 选择器候选 |
| `switch` | Tab / 模式 / 开关切换 | 切换前状态 → 目标态控件 |
| `fill` | 输入 / 选择填充 | 目标控件 + 填充值 + 触发方式（input/enter/blur） |
| `hover` | 悬停 | 目标行/节点 + 期望出现的浮层/操作条 |
| `assert` | 观察断言 | 可见文本 / loading 结束 / 网络请求名 / 截图区域 |
| `screenshot` | 存证 | 建议文件名（`test/ui/...`） |

### `ui_test_paths` 模板

```markdown
## UI 测试路径
### Meta
- Case IDs: TC-00x
- Entry URL: （用户提供，禁止猜测）
- Impact files: ...
- Generated from: （分析过的源文件列表）

### Path P-001 — （场景名）
1. navigate | {url} | 页面可交互 / 关键壳层可见
2. click | （控件：文案或 selector） | （期望）
3. switch | （如 Tab / 模式切换） | （期望）
4. fill | （输入目标）| value=... | （期望）
5. hover | （行/节点） | （期望浮层/按钮）
6. assert | （可观察结果）
7. screenshot | test/ui/xxx.png
```

要求：

- **完整可执行**：他人仅凭路径即可操作，无需再读源码
- 每步含：`action | target | expected`（fill 含 value）
- 目标优先稳定信号：可见文案、`role`、`data-test*`、业务 class；避免脆弱的 nth-child 链（除非无更好信号）
- 与 TC ID 关联；P0 路径优先生成

若影响分析阶段已产出同等质量路径，本步校验补全即可，勿重复劳动。

## Step 3 — UI tests (conditional ask, never auto)

**前置**：任务评估为代码变更 + 影响分类含 UI（`mode=ui` / ui-optional）。纯文档/需求分析任务**不得**进入本 Step。

When all preconditions met:

1. Ask:

   > 本次变更涉及 UI，是否启用浏览器 MCP（Chrome DevTools / cursor-ide-browser）做渲染自测？

2. If **否**：mark UI cases `not_run`，reason=`user_declined_browser_mcp`；仍可用 unit 覆盖可测逻辑。
3. If **是**：再问：

   > 请提供要测试的完整页面 URL（含环境与必要 query）。未提供则不自动探测。

4. URL 到手后：执行 **Step 2.5** 生成/补全 `ui_test_paths`，再严格按路径操作：
   - navigate → snapshot 定位 → click/switch/fill/hover → assert → screenshot
   - save under `test/ui/` when useful
   - do **not** guess hosts, retry random envs, or burn tokens re-analyzing code mid-run
5. 路径某步失效：允许**一次**局部重读该步相关模板修正路径，记录 `path_amended`；禁止借机全模块再分析。

## Step 4 — Results artifact

Produce `test_results`（+ 若有 UI：附 `ui_test_paths` 摘要）:

| ID | Mode | Status | Command / evidence | Summary |
| --- | --- | --- | --- | --- |
| TC-001 | unit | pass/fail/skipped/not_run | `node --test ...` | … |
| TC-002 | ui | pass/fail/not_run | screenshot + path id | … |

Hard rules:

- Never claim **pass** without execution.
- Unit results → text table for TAPD comment.
- UI results → screenshot(s) + path 摘要 → TAPD comment（见 tapd-submit-backfill skill）.

## Step 5 — Hand off to submit / backfill gate

自测结束后（含用户拒绝 UI、或仅 unit）：

1. 若任务过程中**有关联 TAPD 单**且 `tapd.enabled`：Read `.ai-agent/skills/tapd-submit-backfill.md` Phase B 起（Commit → PR → 询问 TAPD 回填）
2. 若无 TAPD 关联：可询问常规 Commit/PR；**跳过 TAPD 回填及关联单号/新建单等条件询问**
3. 若 `tapd.enabled !== true`：跳过 TAPD 回填询问

## Anti-patterns

- Auto-launching browser MCP without consent
- Guessing/testing multiple URLs
- UI 执行中途大范围代码分析（应用 Step 2.5 预生成路径）
- Full-suite regression for a one-file logic fix
- Editing TAPD story description to dump test matrices（评论回填即可）
- 自测结束后直接 commit/回填而不询问
