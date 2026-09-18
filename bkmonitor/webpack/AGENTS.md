# AGENTS.md

本文件是 `bkmonitor/webpack` 的 AI 工作宪法，每轮对话默认生效。

只写**硬门禁、开发风格、口令歧义**。流程细节以对应 skill 为准，禁止把 skill 正文抄到这里造成双源漂移。

冲突优先级：**用户当次明确口令 > 本文件 > 对应 skill > 通用最佳实践**。

---

## 0. 先路由，再动手

| 场景                                  | 必读 skill                                        |
| ------------------------------------- | ------------------------------------------------- |
| 改业务代码 / 修 bug / 新页面          | `bkmonitor-dev` + `bkmonitor-dev-guardrails`      |
| Figma / 设计稿还原                    | 先 `blueking-figma-dev`，编码仍过 `bkmonitor-dev` |
| TAPD 建单 / 分支 / commit / PR / 回写 | `blueking-tapd-dev`（该 skill **不编码**）        |
| 一次性 E2E / 设计还原度               | `bkmonitor-e2e-test`                              |
| 环境搭建                              | `bkmonitor-onboarding`                            |
| 用户明确要求沉淀会话经验              | `bkmonitor-continual-learning`                    |

混合任务顺序：护栏与方案确认 → 设计还原 / 编码 → 验证询问 → TAPD 交付。

Git 根在 `bk-monitor/`，不在 `bkmonitor/webpack/`。git 写操作通常需要完整权限。

---

## 1. 硬门禁

1. **不确定就问**。禁止猜测业务交互、组件选型、路由契约、范围外功能、remote / base。
2. **写代码前先出方案并得到确认**（目录、复用点、明确不做项、数据来源：真实接口或 mock）。琐碎改动（改文案、调已有样式一两处）可跳过。
3. **脚本、dev server、批量 lint/format、浏览器自动化、git 写操作**（commit / push / checkout / stash）必须先征得同意。只读侦察（`status` / `diff` / `log` / `rg`）可直接跑。
4. **格式化工具能修的问题不要手改**。不要写 licensed 头。注释只在有必要且有信息量时加。
5. 分支策略（切 / 建、基于哪条）以**当次口令**为准；未确认前不要为了「规范」擅自切分支。
6. 需求含「有没有 X / 好像没生效 / 补上 X」时，先核验现状再动手，禁止重复实现。

---

## 2. 开发风格

- 先定位 `src/*` package，再选 Vue2 / Vue3，禁止混用语法。
- Vue3 只在 `src/trace`：TSX `defineComponent` + `setup` + `render`，Pinia，`shallowRef` 优先，`useI18n`。禁止 `.vue` SFC、`<script setup>`、直接 `ref()`（用 `shallowRef` / `deepRef`）。
- Vue2（`monitor-pc` / `apm` / `fta-solutions`）：TSX class + Vuex + `this.$t` + `bk-magic-vue`。
- Vue3 新页面默认四层：`typings/`（M）→ `components/`（V）→ `hooks/`（C）→ `services/`（取数）。目录名跟仓库多数实现用 `hooks/`；用户点名 `composables/` 时从其口令。组件层不直接打 API。
- **可参考旧实现，禁止照搬。** 优先复用用户点名或相邻已有封装。要改共享源头（`trace-explore`、`monitor-ui`、`common-table` 等）必须单独确认，默认在本目录做 adapter。
- 用户写「只改 X / 暂时不开发 Y / 不兼容旧版」时严格限缩 diff；范围外用空占位，禁止顺手做完。
- 多变体 UI 用注册表 / 配置扩展，少写类型 if-else。
- API 未通：按文档 mock，数据要多样，去掉敏感信息。
- 可见文案走 i18n，不要硬编码中文（调试占位除外）。
- 文件名 kebab-case；组件 PascalCase；2 空格、行宽 120、单引号、分号。
- 微前端是 `@blueking/bk-weweb`，不要引入 qiankun。新页面对照 `bkmonitor-dev-guardrails` 清单；Vue2 容器 class 不得与自定义元素 tag 撞名。

---

## 3. Figma → 代码

- 必须读 Annotations / 画布旁注 / 多态 variants。设计稿与标注优先于推断。大画板先 `get_metadata`，再 `get_design_context` + `get_screenshot`。
- 设计稿与接口 / 旧实现冲突时，列差异表询问，禁止静默选边。
- 组件候选走 BlueKing 映射，出码前读对应组件 skill reference（API 以 reference 为准，相邻代码只决定封装与风格）。
- Vue3：表格默认 `@blueking/tdesign-ui`；tips 默认 `vue-tippy`；另做 icon / 主题映射。Vue2：主要做组件映射。
- 静态 map 与组件 skill 都未命中时，列出缺口并询问是否允许最小手写，禁止发明基础组件 API。
- 样式：同模块有稳定相邻实现则对齐相邻。Vue3 在项目已加载对应 token 时用 `var(--xxx)`，否则用局部既有写法或设计值。Vue2 可用设计稿原始值。
- 交付对照截图与标注做视觉 / 行为自检。未跑通的不要写成已还原。

---

## 4. TAPD 与 Git 交付

- 「基于暂存区 / 改动生成 tapd」= 反向建单：只读 diff → 展示草稿 → 确认后才创建。大改动默认按功能拆单，拆法需确认。
- 蓝鲸监控 TAPD workspace 默认 `10158081`；owner / 迭代预填后仍要展示核对。
- 交付授权按用户请求的范围复用。用户明确要求串联交付时，commit / push / PR / TAPD 评论与测试附件合并为一次交付预览；已经明确授权且目标无歧义则展示后连续执行，不逐步重复询问。只要求 PR 不自动授权 TAPD 回写。建单、分支变更、状态/负责人/迭代变更仅在请求涵盖时执行；缺少必要选择或实质范围变化时才补问，细则见 `blueking-tapd-dev`。
- **严格听当次口令**，不沿用上一会话习惯：`不需要切换分支` / `本分支提 PR` / `切开发分支` / `PR 提到 feat/X` / `推 fork`。
- 「upstream」不等于 remote 一定叫 `upstream`。以 `git remote -v` 为准；交付预览必须写清 `head_remote:head → pr_target_remote:base`。
- 「PR 提到 feat/X」默认 base = `feat/X`，不要默认合进 `master`。base 必须 fetch 验证存在；不存在则停问，禁止静默改 base。
- commit subject 走 hook 限制（约 1–50 字），关联格式 `--story=<短ID>` 或 `--bug=<短ID>`。公开仓库禁止贴 TAPD 完整链接。
- 未 review / 用户未说可以提交前，不 commit。`/git-commit` 只表示现在允许提交，不等于 push / PR / 回写。
- GPG / SSH 签名和交互认证交给用户本地执行，只提供可复制命令。
- TAPD 回写仅在用户要求或交付预览确认后执行；评论只写已验证的分支 / SHA / PR URL，禁止猜测链接。
- 状态只能是：计划执行 / 等待确认 / 已请求但结果未知 / 已验证成功。摘要不得把前三类说成已完成。

---

## 5. 验证

- 业务改动的对话交付用三段式：改了什么 / 验证到哪一步 / 影响面。`[未验证]` 不得空；没跑本地就写「未本地运行验证」。
- 不要用「已修复」这类断言。没有实际执行过的动作，只能写未验证或假设。
- 实现完成后主动问是否跑一次性 E2E（`bkmonitor-e2e-test`）；询问中说明会预检登录态，必要时打开临时浏览器由用户完成登录并安全刷新本地鉴权。同一份 diff 已答复则不重复问，也不为这次鉴权刷新再次询问。设计稿任务若跑 E2E，必须带视觉还原对比；布局/溢出/遮挡类缺陷必须带几何断言和最终截图。
- 用户连续否定你的根因判断时停止打补丁，先对齐复现、观察和假设差异。

---

## 6. 红线

- 不用 `--no-verify`。默认禁止 force push；仅当用户对本分支和目标 SHA 明确授权时可用 `--force-with-lease`。
- 不静默 stash / reset，不把无关文件混进提交。
- 不改、不提交、不把 `local.settings.js` 全文读进对话。凭据零接触（Cookie / Token / bk_ticket）。
- 不留 `debugger` 和提交用的 `console.log`。
- `postMessage` 禁止 `targetOrigin='*'`；`/share/:token` 类分享链接不外广播。
- 公开 PR / commit 不得出现内网 URL。

---

## 7. 细节去哪查

- 各 package 写法 → `bkmonitor-dev`
- 影响面 / 同类扫描 / 对外安全 → `bkmonitor-dev-guardrails`
- PR 正文与 TAPD 评论模板 → `blueking-tapd-dev`
- 组件 API → `bkui-vue-components` / `bk-magicbox-vue-components` / `blueking-tdesign-ui`
