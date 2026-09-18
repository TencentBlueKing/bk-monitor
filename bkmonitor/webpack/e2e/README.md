# 一次性 E2E 基础设施

本目录保存可复用、无敏感信息的 E2E 公共能力：Playwright 配置、运行器、视觉对比和报告生成脚本。每个需求特有的测试用例、登录态、截图、视频与 trace 写入仓库根目录的 `.e2e-runs/`，该目录已被 Git 忽略。

## 使用边界

- 公共基础设施：`e2e/`、根目录 `package.json` 和锁文件，纳入版本管理。
- 一次性资产：`.e2e-runs/<run-id>/`，不提交仓库。
- 登录态、Cookie、Token、业务数据和内网地址不得写入 `e2e/`。
- 每次只测试“当前需求验收标准”与“当前代码 diff”交集内的功能。
- 每个已执行场景保留结束截图和视频；失败场景额外保留 trace。
- 设计稿任务除了交互 E2E，还要执行截图对比并人工检查结构、状态和视觉语义；布局/溢出/遮挡类缺陷即使没有设计稿，也要做几何断言并保留最终截图。
- 产品失败不会直接触发改码；AI 展示证据和拟修复范围，获得“修复 + 同范围复测”授权后最多执行一轮修复，报告保留完整闭环。

## 常用命令

```bash
# 首次安装或 Playwright 升级后安装 Chromium
pnpm e2e:install

# 测试前检查环境
pnpm e2e:doctor

# 创建本次运行目录和用例模板
pnpm e2e:init -- --title "需求标题" --viewport 1440x900

# 填写 scope.json.runtime 后，先检查服务、登录跳转和目标路由
pnpm e2e:preflight -- --run-dir .e2e-runs/<run-id> --base-url http://appdev.<domain>:<port>

# 侦察完成并把正式验收场景写入 tests/scoped-e2e.spec.mjs 后执行
pnpm e2e:run -- --run-dir .e2e-runs/<run-id> --base-url http://appdev.<domain>:<port>

# 补全 scope.json 的分类后生成本地报告和结构化交付事实
pnpm e2e:report -- \
  --results .e2e-runs/<run-id>/results.json \
  --scope .e2e-runs/<run-id>/scope.json \
  --output .e2e-runs/<run-id>/report

# 前检已确定 BLOCKED_ENV，或本次为 NOT_RUN 时不伪造 results.json
pnpm e2e:report -- \
  --scope .e2e-runs/<run-id>/scope.json \
  --output .e2e-runs/<run-id>/report

# 截图已有报告并把完整图/分段图加入待上传清单，不重跑业务 E2E
node e2e/scripts/capture-report.mjs --run-dir .e2e-runs/<run-id>

# 补全 delivery.json 的背景、文件级改动、行为对比和影响面后生成 PR 正文
pnpm e2e:delivery -- \
  --phase pr \
  --facts .e2e-runs/<run-id>/report/delivery-facts.json \
  --delivery .e2e-runs/<run-id>/delivery.json \
  --output .e2e-runs/<run-id>/delivery

# PR 验证后上传报告图/场景图/视频，填写附件链接与报告图 imageUrl，再生成评论
pnpm e2e:delivery -- \
  --phase tapd \
  --facts .e2e-runs/<run-id>/report/delivery-facts.json \
  --delivery .e2e-runs/<run-id>/delivery.json \
  --output .e2e-runs/<run-id>/delivery
```

`e2e:preflight` 会在运行目录生成 `preflight.json`，失败时附带 `preflight.png`；它只证明页面可以开始测试，不计入业务通过数。初始化的 `scope.testPhase` 是 `reconnaissance`，正式场景完整映射验收项后才改成 `acceptance`，否则报告器拒绝生成 `PASS`。

报告目录会生成 `index.html` 可视化报告、`report.md` 详细文本报告、`delivery-facts.json` 结构化事实，以及仅供复核的 `pr-summary.md`、`tapd-test-fragment.md`。`delivery-facts.json.internal.artifacts` 提供 TAPD 待上传图片/视频的运行目录相对路径。交付阶段消费结构化事实和 `delivery.json`：先生成完整、公开脱敏的 `pr-body.md`；PR 创建并验证后上传并验证代表性图片和视频，把稳定附件链接写入 `delivery.json.internal.attachments`，再生成包含真实交付事实、紧凑测试摘要、附件和追溯信息的完整 `tapd-comment.md`。

`pr-summary.md` 与 `tapd-test-fragment.md` 只是中间材料。PR 通过 `scope.publicSummary` 与 `delivery.public` 脱敏；可选 `delivery.public.behavior.before/after`、`reviewFocus` 说明行为变化与审查重点，`scope.publicSummary.checks` 提供实际断言。TAPD 评论可保留内网业务上下文，禁止凭据和本地绝对路径。

`capture-report.mjs` 展开 HTML 明细，生成完整长图，高度超过 1800px 时生成带重叠的分段图。待上传图以 `role="report"` 加入 `internal.artifacts`，不修改测试结果；报告更新后重新截图。上传前检查图片。`delivery.internal.attachments` 的报告图填写 `{ kind: "image", role: "report", name, url, imageUrl }`（name 与待上传文件名一致），通过 TAPD 图片上传得到可持久引用的 `imageUrl`，生成器用 `<img>` 内嵌。Bug 详情 URL 不能充当图片地址。场景图片与视频仍使用附件链接，报告图不能替代它们。

用户已要求 PR 与 TAPD 回写时，准备一次预览后按已授权范围连续执行；缺少授权才合并询问一次，不为真实链接补齐、报告截图或认证恢复重复确认。HTML、JSON 和 trace 保留本地。本地生成与渲染可用 `node --test e2e/tests/delivery.test.mjs` 验证。
