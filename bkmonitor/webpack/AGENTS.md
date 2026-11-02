# AGENTS.md

本文件是 `bkmonitor/webpack` 的 AI 工作宪法，每轮对话默认生效。

只写**硬门禁、开发风格、口令歧义**。流程细节以对应 skill 为准，禁止把 skill 正文抄到这里造成双源漂移。

冲突优先级：**用户当次明确口令 > 本文件 > 对应 skill > 通用最佳实践**。

---

## 0. 先路由，再动手

| 场景                                  | 必读 skill                                        |
| ------------------------------------- | ------------------------------------------------- |
| 改业务代码 / 修 bug / 新页面 / 续跑   | `bkmonitor-workflow`，按阶段使用 `bkmonitor-dev` / `bkmonitor-dev-guardrails` |
| 只读分析 / 规范咨询                   | 按问题使用对应 skill，不启动完整开发流程         |
| Figma / 设计稿还原                    | `bkmonitor-workflow` + `blueking-figma-dev`       |
| TAPD 建单 / 分支 / commit / PR / 回写 | `blueking-tapd-dev`（该 skill **不编码**）        |
| 一次性 E2E / 设计还原度               | `bkmonitor-e2e-test`                              |
| 首次环境搭建                          | `bkmonitor-onboarding`                            |
| 已有环境启动 / 服务诊断               | `bkmonitor-dev-server`                            |
| 用户明确要求沉淀会话经验              | `bkmonitor-continual-learning`                    |

混合任务由 `bkmonitor-workflow` 推进：确认目标分支与基线 → 代码 / 设计取证与护栏核验 → 方案确认 → 实现 → 已授权验证。仅在用户要求时进入 Git / TAPD 交付；单独测试、启动、咨询或交付保留各自终点。

Git 根用 `git rev-parse --show-toplevel` 获取，不依赖本地目录名。权限按实际操作和工具限制处理，不预设需要提权。

---

## 1. 硬门禁

1. **先查证，仍有实质歧义再问**。通过代码、配置和对应文档核验；仍存在会改变业务行为、范围或交付目标的歧义时集中询问，只暂停依赖该决定的工作。禁止猜测业务交互、路由契约、范围外功能、remote / base。
2. **写代码前先出方案并得到确认**（目录、复用点、明确不做项、数据来源：真实接口或 mock）。已有批准且范围未变时直接复用；琐碎改动（改文案、调已有样式一两处）可跳过。
3. **脚本、dev server、浏览器自动化、git 写操作**（commit / push / checkout / stash）执行前核对授权，缺失时先征得同意。明确请求所覆盖的必要动作跨轮次、跨 skill 复用授权，不逐命令重复询问；新增范围、环境或副作用才补问。只读侦察（`status` / `diff` / `log` / `rg`）可直接跑。
4. **不主动处理代码格式问题，不运行格式修复或批量 lint/format**；新增代码遵循既有风格。用户的明确限制持续有效。不要写 licensed 头。注释只在有必要且有信息量时加。
5. 开发、修复及设计实现相关的业务代码分析前，先确认目标分支与基线，核验当前分支相对基线的领先 / 落后及工作区改动；分支策略（继续 / 切 / 建、基于哪条）以**当次口令**为准。已有确认且事实未变直接复用，不默认当前分支等于主分支，不擅自切分支或同步代码。
6. 需求含「有没有 X / 好像没生效 / 补上 X」时，先核验现状再动手，禁止重复实现。
7. 规范咨询、skills / 文档审查与 Git 元数据侦察可直接只读进行；涉及开发根因或实现方案的业务代码分析仍先确认分支与基线，但不要求先批准开发方案。只读任务不自动扩展为实现、测试或交付。

---

## 2. 开发风格

- 先定位 `src/*` package，再选 Vue2 / Vue3，禁止混用语法。
- `src/trace` 按 Vue3 规范：TSX `defineComponent` + `setup` + `render`，Pinia，`shallowRef` 优先，`useI18n`。禁止 `.vue` SFC、`<script setup>`、直接 `ref()`（用 `shallowRef` / `deepRef`）。
- Vue2（`monitor-pc` / `apm` / `fta-solutions`）：TSX class + Vuex + `this.$t` + `bk-magic-vue`。
- `monitor-mobile` 使用 Vue2 SFC + Vant；共享包及 Vue2/Vue3 适配入口按实际依赖、导入和构建配置核验，不仅凭 API 名称判断技术栈。
- 页面分层、hooks 目录与多变体实现按 `bkmonitor-dev` 的适用规范和已确认方案执行，不为凑层级创建空目录或无必要抽象。
- **可参考旧实现，禁止照搬。** 优先复用用户点名或相邻已有封装。修改共享源头（`trace-explore`、`monitor-ui`、`common-table` 等）时，在方案中说明消费方与回归范围；已有批准覆盖时不再单独确认。根据问题归属选择共享修复或局部 adapter。
- 用户写「只改 X / 暂时不开发 Y / 不兼容旧版」时严格限缩 diff；范围外保持现状，仅在已确认设计需要时增加占位。
- mock 必须属于已确认方案，按接口文档构造多样且脱敏的数据，并说明验证边界；真实接口异常不自动切换为 mock。
- 组件按目标 package、实际 import 包名与 Vue 入口路由。优先查对应 skill reference；版本不明、资料缺失或冲突时，核查匹配安装版本的类型、源码或官方资料。相邻用法不能单独证明 API，禁止凭记忆补全。
- 外部维护的组件 skill（如 MagicBox、bkui-vue）仅消费；项目侧处理版本适配，未经明确要求不修改其正文、生成器或 references。
- 可见文案走 i18n，不要硬编码中文（调试占位除外）。
- 文件名 kebab-case；组件 PascalCase。
- 微前端是 `@blueking/bk-weweb`，不要引入 qiankun。新页面对照 `bkmonitor-dev-guardrails` 清单；Vue2 容器 class 不得与自定义元素 tag 撞名。

---

## 3. Figma → 代码

- 必须核对设计稿及已有标注、旁注和相关状态，设计证据优先于推断；工具调用、组件映射、icon 与主题处理按 `blueking-figma-dev` 执行。
- 设计稿与接口 / 旧实现冲突时，列差异表询问，禁止静默选边。
- `src/trace` 新增表格 / tips 优先复用目标区域的业务封装；无既有封装时默认考虑 `@blueking/tdesign-ui` / `vue-tippy`，按语义、能力和版本核验，不为统一选型替换现有组件。
- 静态 map 与组件 skill 完整索引均未命中所需基础组件时，列出缺口并询问是否允许最小手写；普通 HTML/CSS 布局和业务组合不属于手写基础组件。
- 样式优先对齐同模块稳定实现；不得输出项目未加载或未定义的 token，具体映射按设计 skill 核验。
- 交付对照截图与标注做视觉 / 行为自检。未跑通的不要写成已还原。

---

## 4. TAPD 与 Git 交付

- 「基于暂存区 / 改动生成 tapd」= 反向建单：只读 diff → 展示草稿 → 确认后才创建。大改动默认按功能拆单，拆法需确认。
- 蓝鲸监控 TAPD workspace 默认 `10158081`；owner / 迭代预填后仍要展示核对。
- 交付授权按用户请求的范围复用。用户明确要求串联交付时，commit / push / PR / TAPD 评论与测试附件合并为一次交付预览；已经明确授权且目标无歧义则展示后连续执行，不逐步重复询问。本项目「提交 / 创建 PR」默认包含 PR 成功后自动回写对应 TAPD 评论，无需再次询问回写授权；用户明确「不要回写」时跳过。建单、分支变更、状态/负责人/迭代变更仅在请求涵盖时执行；缺少必要选择或实质范围变化时才补问，细则见 `blueking-tapd-dev`。
- **严格听当次口令**，不沿用上一会话习惯：`不需要切换分支` / `本分支提 PR` / `切开发分支` / `PR 提到 feat/X` / `推 fork`。
- 「upstream」不等于 remote 一定叫 `upstream`。以 `git remote -v` 为准；交付预览必须写清 `head_remote:head → pr_target_remote:base`。
- 「PR 提到 feat/X」默认 base = `feat/X`，不要默认合进 `master`。base 必须 fetch 验证存在；不存在则停问，禁止静默改 base。
- PR 标题、正文和 TAPD 评论的自然语言说明默认使用简体中文，用户明确指定其他语言时遵从；路径、API、命令、SHA、关联 ID 与状态枚举保留原文。公开内容脱敏不等于翻译成英文；发布前检查完整文稿，不只检查章节标题。
- commit subject 保持简短，格式以当前 hook 和交付规则为准；关联格式 `--story=<短ID>` 或 `--bug=<短ID>`。公开仓库禁止贴 TAPD 完整链接。
- 提交前完成本次 diff 自检，并确认提交动作在用户授权范围内；明确要求创建 PR 时按交付规则复用必要提交授权。用户明确要求人工 review 时等待其完成。`/git-commit` 只授权提交，不等于 push / PR / 回写。
- GPG / SSH 签名和交互认证交给用户本地执行，只提供可复制命令。
- PR 创建并核验成功后，自动回写已验证关联的 TAPD 单据；评论与所需证据按交付 skill 生成、查重、写入并核验。单据缺失或关联不明确时只补问目标，不猜测、不自动建单；PR 失败或结果未知时不回写成功评论。回写失败保留 PR 成功事实，从评论步骤恢复。评论只写已验证的分支 / SHA / PR URL，禁止猜测链接。
- 外部动作的证据状态区分：计划执行 / 等待确认 / 已请求但结果未知 / 已验证成功。前三类不得说成已完成；失败时明确失败事实与恢复点。测试分类另按验证 skill 记录，不套用这四类状态。

---

## 5. 验证

- 交付说明改动、实际验证、影响面与未覆盖项，篇幅与任务相称，不强制固定版式或非空的未验证项。未本地运行时明确说明。
- 结论不得超出验证证据；代码阅读、静态检查、运行时验证分开陈述，未执行不得宣称通过。
- 业务实现完成且尚无 E2E 决定时，由主流程统一询问是否跑一次性 E2E（`bkmonitor-e2e-test`）。询问须说明登录态预检、必要的临时浏览器登录及安全鉴权刷新、所需服务和本地报告；直接要求 E2E 视为授权。同一任务范围内复用接受或拒绝决定；已测试且代码内容未变时复用结果，不因提交 PR 重跑；测试后代码发生变化必须复测，复用原范围测试授权。仅提交 SHA、PR 文案、报告展示或附件变化不触发业务 E2E；测试证据仍须完整可信。环境、验收范围或副作用变化才补问。具体执行与证据要求由 E2E skill 维护。
- 设计任务的 E2E 包含视觉对比；布局、溢出、遮挡类缺陷的 E2E 包含几何断言和最终截图。未执行时如实说明，不声称视觉或行为通过。
- 明确根因被实际结果否定后，先补复现路径、实际观察和不同于上轮的假设，再修复；无新证据不继续打补丁。

---

## 6. 红线

- 不用 `--no-verify`。默认禁止 force push；仅当用户对本分支和目标 SHA 明确授权时可用 `--force-with-lease`。
- 不静默 stash / reset，不把无关文件混进提交。
- 不手工修改、不提交、不把 `local.settings.js` 全文或凭据读进对话；允许 `bkmonitor-dev-server` 指定脚本在已有授权内创建配置骨架或刷新鉴权。模型不读取、索要或回显 Cookie / Token / bk_ticket。
- 不留 `debugger` 和提交用的 `console.log`。
- `postMessage` 禁止 `targetOrigin='*'`；`/share/:token` 类分享链接不外广播。
- 公开 PR / commit 不得出现内网 URL。

---

## 7. 细节去哪查

- 阶段推进 / 授权复用 / 续跑 → `bkmonitor-workflow`
- 各 package 写法 → `bkmonitor-dev`
- 影响面 / 同类扫描 / 对外安全 → `bkmonitor-dev-guardrails`
- 设计取证 / 映射 / 视觉验收输入 → `blueking-figma-dev`
- 环境与鉴权 → `bkmonitor-dev-server`；首次搭建 → `bkmonitor-onboarding`
- 一次性测试与视觉证据 → `bkmonitor-e2e-test` / `bkmonitor-e2e-visual`
- PR 正文与 TAPD 评论模板 → `blueking-tapd-dev`
- 组件 API → 按实际包名选择组件 skill，包括基础组件、`blueking-tdesign-ui`、`blueking-date-picker`、`blueking-search-select-v3`
