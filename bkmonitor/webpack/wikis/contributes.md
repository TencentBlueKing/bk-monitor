# 开发与 AI 协作指南

本文面向在 `bkmonitor/webpack` 中开发、排查问题和交付改动的贡献者，重点说明如何让 AI 在正确的代码基线上工作，以及如何从源码定位到可验证的结果。

[README](../README.md) 提供项目介绍、skills 入口与环境启动方法；[AGENTS.md](../AGENTS.md) 维护项目硬约束；已安装的 skills 维护各阶段的具体操作。本文提供开发导航，不替代这些规则。目录、依赖和实现细节必须与本次任务的目标分支核对。

## 1. 开始一个任务

### 准备环境与 AI 能力

首次搭建使用 `bkmonitor-onboarding`；已有环境的启动、代理鉴权和服务诊断使用 `bkmonitor-dev-server`。工具版本与安装步骤见 [README：本地运行与构建](../README.md#本地运行与构建)。

团队 skills 独立分发，本地常见路径为 `.agents/skills/<skill-name>/SKILL.md`。该目录被 Git 忽略，克隆业务仓库不会自动获得 skills。缺少时获取完整目录包，不只复制入口文件；也不要把私有正文、脚本或凭据复制到公开文档中。

AI 需要能够读取项目、执行已授权的工具；Figma、TAPD、GitHub 等外部操作还需要对应集成与账号权限。缺少集成时，说明受影响的步骤，继续其余已具备条件的工作。

### 描述目标和终点

任务至少说清楚预期行为、入口、验收要求和本次做到哪一步。有条件时补充复现步骤、截图、接口说明和已知影响范围。

```text
目标：<期望解决的问题>
页面 / 目录：<入口或目标 package>
分支与基线：<已确认目标；不确定的先核对>
现象与预期：<复现步骤、实际结果、期望结果>
范围：<允许修改的内容与明确不做项>
验收：<需要验证的操作、状态和边界>
本次终点：<只分析 / 实现并验证 / 提交 PR>
```

业务开发由 `bkmonitor-workflow` 编排。只查组件 API、启动服务、执行测试或交付已有改动时，使用对应 skill，保留各自的任务终点。只要求分析，不自动进入编码或提交。

### 先核对分支，再分析业务实现

当前分支可能落后于目标基线，也可能包含尚未合入的功能。业务开发、修复和设计实现的分析前，需要确认目标分支、基线及继续 / 切换 / 新建策略；已确认且事实未变时复用，不重复询问。

以下是可直接进行的只读侦察：

```bash
git rev-parse --show-toplevel
git status --short --branch
git branch --show-current
git remote -v
```

确定基线后，核验引用是否最新，再比较双方独有的提交和工作区改动。例如 `git rev-list --left-right --count <baseline-ref>...HEAD` 左侧为基线独有提交数，右侧为当前分支独有提交数；占位符需要替换为已确认的引用。未更新的本地 remote-tracking 引用不能代表远端最新状态。

不要假定基线是 `master`、remote 叫 `upstream`，也不要为了准备环境自动 checkout、stash、reset 或 rebase。规范咨询、文档审查和 Git 元数据检查可先只读进行。

### 用源码形成方案

实现前先定位已有功能、数据流、可复用封装和共享消费方。方案说明修改目录、复用点、接口或已批准的 mock、明确不做项及验证范围；获批后实施，范围未变时不重复审批。

需要人决定的是查证后仍会改变行为、范围或交付目标的歧义。其余可确认的事实先从源码、配置和资料中查清楚。

## 2. 找到正确的源码入口

### 按 package 选择技术栈

| 目录 | 组件与状态约定 | 常用 UI / 国际化 |
| --- | --- | --- |
| [`src/monitor-pc`](../src/monitor-pc) | Vue2，TSX class 为主，Vuex；包含历史 SFC | `bk-magic-vue`、`this.$t` |
| [`src/apm`](../src/apm) | Vue2，TSX class、Vuex | 复用 PC 系组件与国际化 |
| [`src/fta-solutions`](../src/fta-solutions) | Vue2，TSX class、Vuex | 复用 PC 系组件与国际化 |
| [`src/trace`](../src/trace) | Vue3，TSX `defineComponent` + `setup` + `render`，Pinia | `bkui-vue` / `@blueking/tdesign-ui`、`useI18n` |
| [`src/monitor-mobile`](../src/monitor-mobile) | Vue2 SFC、Vuex | Vant，独立语言资源 |

`external` 是 `monitor-pc` 的构建变体，没有独立的 `src/external`。具体映射见 [webpack/utils.js](../webpack/utils.js)。`trace` 的业务也不限于 Trace 检索，当前包含告警、主机、轮值、Profiling、RUM 等页面。

跨包复用时查看实际依赖、import 和构建入口。`monitor-ui` 以 Vue2 为主；不能因 `monitor-common` 或 `monitor-static` 名称带有“公共”就认定其中所有内容都与 Vue 版本无关。

### 从页面追到依赖

推荐按以下顺序阅读，而不是先全仓库扫描所有组件：

1. 页面入口、实际路由与导航配置，确认用户如何到达页面。
2. 页面使用的组件、hooks / mixins、store，确认状态由谁持有。
3. API 声明、请求封装和接口契约，确认数据来源及错误处理。
4. 共享模块的调用方，确认修复应放在共享源头还是局部适配层。
5. 已有测试、设计标注与相关状态，确定本次验收边界。

可按任务关键词从 `src/<package>` 开始用 `rg` 搜索，再扩大到共享包。包内别名以该包的 `tsconfig.json` 与构建配置为准，不把另一应用的 `@`、`@static` 等映射直接搬过来。

| 要找的能力 | 源码入口 |
| --- | --- |
| API 声明与请求行为 | [monitor-api/modules](../src/monitor-api/modules)、[base.ts](../src/monitor-api/base.ts)、[axios](../src/monitor-api/axios) |
| 公共工具 | [monitor-common](../src/monitor-common) |
| 共享 UI、样式与图标 | [monitor-ui](../src/monitor-ui)、[monitor-static](../src/monitor-static) |
| 主应用初始化 | [monitor-pc/index.ts](../src/monitor-pc/index.ts) |
| Vue3 应用初始化 | [trace/index.ts](../src/trace/index.ts) |
| 组件库构建与跨 Vue 适配入口 | [scripts](../scripts)、[package.json](../package.json) 中的 `build:*components` 与 `build:apm-vue3-for-vue2` |

## 3. 实现时需要核对的约定

### 组件、状态和复用边界

Vue2 页面遵循所在模块的 TSX class、Vuex 和 `this.$t` 方式；移动端保留 Vue2 SFC 与 Vant 的实现方式。不要把 Vue3 的组合式写法直接移入 Vue2 页面。

`src/trace` 按项目约定使用 TSX `defineComponent`、`setup` 和 `render`，不新写 `.vue` SFC 或 `<script setup>`。响应式状态优先 `shallowRef`，需要深层响应时采用规范中的 `deepRef` 写法；浅层状态的内部修改不会自动等同于替换引用。组件内使用 `useI18n`，跨组件状态按需要放入 Pinia。

TSX 中使用 JavaScript 表达式传递属性，例如 `data={rows}`；不要混入 Vue 模板的 `:data="rows"`。具体事件、插槽、指令与 ref 写法应匹配该 package 的 JSX 转换和组件 API。

页面展示、状态编排、数据转换和 API 调用按职责分离。新增目录与抽象必须服务于实际需求，不为凑层级建立空的 hooks / services，也不顺手重构无关代码。可参考旧实现，但先判断版本、契约和业务差异，优先复用已有封装。

### API 与异步状态

接口声明集中在 [monitor-api/modules](../src/monitor-api/modules)。例如 [alert.js](../src/monitor-api/modules/alert.js) 的 `searchAlert` 使用 `request('POST', 'fta/alert/alert/search/')` 声明接口；参数字段与响应类型仍需查对应接口契约，不能从函数名推断。

新增 API 时，先查是否已有等价接口，再按所在模块形式声明和导出。[api.ts](../src/monitor-api/api.ts) 会收集 `modules` 下的 `.js` 模块；改变模块形式或后缀前，要检查这个聚合入口及实际导入方。

调用前重点核对 [base.ts](../src/monitor-api/base.ts) 和拦截器中的以下行为：

| 问题 | 核对重点 |
| --- | --- |
| 返回什么 | 默认取响应的 `data`；`needRes` 会改变返回形态，业务类型应与之对应 |
| 业务 / 空间参数从哪里来 | 请求封装会处理业务与空间上下文；按实际请求方法分支核对，不重复猜填 |
| 是否出现重复错误提示 | `needMessage`、本地开关、拦截器和页面自有提示共同影响行为 |
| 连续查询或切换页面是否串数据 | 检查取消、过期响应和卸载清理；`needCancel` 按方法与 URL 管理请求，使用前考虑并发调用方 |
| 无权限如何处理 | 核对 403、权限映射和页面反馈，不将所有失败显示为空列表 |

界面分别处理加载、成功、空结果和失败状态。真实接口异常不自动切换为 mock；mock 仅用于已批准的方案，数据需脱敏，并在验证结果中说明边界。

### 路由、导航和权限

路由定义与导航配置是两个入口，新增一个并不意味着另一个已经生效。

| 应用 | 路由与页面挂载 | 导航信息 |
| --- | --- | --- |
| 监控主应用 | [monitor-pc/router/router.ts](../src/monitor-pc/router/router.ts) 及其导入的路由文件 | [monitor-pc/router/router-config.ts](../src/monitor-pc/router/router-config.ts) |
| Vue3 应用 | [trace/router/router.ts](../src/trace/router/router.ts)、[trace/router/modules](../src/trace/router/modules) | [trace/router/router-config.ts](../src/trace/router/router-config.ts) |

新增或调整页面时，一起核对路由名称、参数、懒加载、入口菜单、激活态、面包屑和返回路径；涉及分享、外部访问或嵌入场景时，只检查本次实际支持的入口，不擅自扩展功能。

权限实现可从 [Vue2 authorityMixin](../src/monitor-pc/mixins/authorityMixin.ts) 和 [Vue3 authority store](../src/trace/store/modules/authority.ts) 追踪。权限 ID、资源范围及申请流程以当前契约为准；只隐藏按钮不等于完成权限校验，还需核对路由与接口失败时的行为。

### 国际化、组件与样式

PC 系语言资源聚合入口为 [monitor-pc/i18n/common.ts](../src/monitor-pc/i18n/common.ts)，资源位于 [monitor-pc/lang](../src/monitor-pc/lang)。[trace/i18n/i18n.ts](../src/trace/i18n/i18n.ts) 也复用该聚合逻辑；移动端使用 [monitor-mobile/i18n/i18n.ts](../src/monitor-mobile/i18n/i18n.ts) 和自身语言资源。新增可见文案先找已有语义一致的词条，再按实际分类补充，不假设每个 package 都有独立的 `i18n/lang`。

组件按实际 import 包名选择对应 skill，完整索引见 [README：按目标选择入口](../README.md#按目标选择入口)。API、props、events 和 slots 需要匹配已安装版本；相邻示例可用于理解业务，不能独立证明组件 API。

设计任务使用 `blueking-figma-dev` 核对画板、标注与状态。`trace` 新增表格或 tips 优先复用目标区域已有业务封装；没有合适封装时再按项目规范核验 TDesign / `vue-tippy` 等选型。基础组件资料无匹配项时，先说明缺口，不直接手写替代品。

样式优先对齐同模块稳定实现与已加载的主题资源。不能把设计工具中的 token 名称直接当作项目 CSS 变量，也不因局部任务替换现有组件体系。文件名使用 kebab-case，组件名使用 PascalCase；AI 不主动处理格式问题或运行批量格式修复。

### 微前端边界

项目使用 `@blueking/bk-weweb`。涉及装载、路由或宿主上下文时，同时读宿主容器与子应用入口。例如 [monitor-pc/pages/rum/rum.tsx](../src/monitor-pc/pages/rum/rum.tsx) 提供子应用地址、`parentRoute` 和卸载回调；[trace/index.ts](../src/trace/index.ts) 根据嵌入上下文初始化应用，并注册卸载处理。

需要重点验证：

- 宿主使用的子应用地址与实际开发服务一致，不能只看端口已经监听。
- `parentRoute` 与子应用路由拼接正确，刷新、前进后退和入口跳转符合预期。
- 切换业务 / 空间时上下文正确，重复进入不会残留实例、监听器或旧请求。
- Vue2 容器 class 不与自定义元素 tag 撞名；跨窗口通信不使用 `targetOrigin='*'`。

是否覆盖独立访问和宿主嵌入两种模式，由本次支持的场景和改动影响决定；只验证独立页不能证明嵌入链路通过。

## 4. 调试与验证

### 选择与问题相符的检查

| 改动或现象 | 验证重点 |
| --- | --- |
| 纯文档更新 | 路径、链接、命令和源码事实一致，无需业务 E2E |
| 请求、数据转换或状态逻辑 | 相关现有测试、实际参数和响应、竞态与失败分支 |
| 页面交互 | 需求范围内的一次性 E2E，覆盖主要操作与边界状态 |
| Figma 还原 | 设计状态、行为、视觉对比与截图 |
| 溢出、遮挡、截断 | 对应几何断言和最终截图，不只判断元素存在 |
| 共享模块或微前端契约 | 明确消费方，验证受影响入口、上下文与卸载行为 |
| 构建配置或适配入口 | 相关应用 / 组件库的构建及实际消费路径 |

优先查 [tests](../tests) 中已有的相关用例，按改动范围选择验证。构建通过不等于浏览器行为通过；开发服务启动、登录态有效与测试通过也要分别记录。

业务实现后尚无 E2E 决定时，由主流程统一询问。直接要求 E2E 已包含对应授权；同范围修复后的复测复用授权，不逐条命令重复确认。环境、验收范围或副作用变化时再核对新增范围。

### 一次性 E2E 的产物

`bkmonitor-e2e-test` 负责本次需求用例、执行和报告，设计或布局任务配合 `bkmonitor-e2e-visual`。公共配置说明见 [e2e/README.md](../e2e/README.md)。

```bash
pnpm e2e:doctor
pnpm e2e:install
```

前者检查运行前提，后者在需要时安装匹配项目版本的 Chromium，都不能替代测试执行。公共配置只执行本次运行目录中的用例，没有预置全站回归套件。

运行产物保留在 `.e2e-runs/<run-id>/`，HTML 报告入口为 `report/index.html`，`delivery-facts.json` 供交付复用。认证状态、一次性用例、截图、视频、trace 和报告不提交到 Git；分享证据前需脱敏。

### 哪些情况需要复测

**已测试且代码内容未变，提交 PR 时复用结果；测试后代码发生变化，必须按影响范围复测。**

仅 commit SHA 改变而代码相同，核对内容后保留原测试记录；仅修改 PR 文案、报告展示或附件，不重跑业务 E2E。测试源码、验收条件、设计基准或执行工具变化时，需要重新核对证据有效性。

报告写清测试对象、覆盖范围与实际结果。失败、环境阻塞和未执行分别说明，不把历史通过结果或未完成的命令写成当前通过。

### 常见问题定位

| 现象 | 先核对什么 |
| --- | --- |
| 依赖安装失败 | 当前 Node / pnpm、锁文件和具体错误；不要先删锁文件或清空依赖缓存 |
| 服务启动后访问不到 | 启动日志、实际端口、监听进程、host 与代理配置；交给 `bkmonitor-dev-server` 诊断 |
| 登录跳转、401 或代理鉴权失效 | 本人通过安全登录流程刷新，不在对话中传递 Cookie / Token |
| 接口返回 403 | 区分登录态与业务权限，检查对应权限契约 |
| Vue3 独立页正常，宿主内空白 | 子应用地址、宿主传参、路由前缀、挂载与卸载，不先重装依赖 |
| 修改路由后菜单不对 | 路由模块与导航元数据是否一致 |
| 文案没有翻译 | 词条归属、聚合入口与当前语言，避免加到未加载的资源文件 |
| 修复后原问题仍存在 | 补充真实复现和新证据；根因已被否定时先调整假设再修改 |

`local.settings.js` 含本地代理与鉴权配置，不手工修改、提交或全文读入对话。配置骨架创建与安全鉴权刷新按开发服务 skill 执行。

## 5. 从本地结果到 PR / TAPD

### 先检查本次 diff

完成本地任务时，说明改动行为、影响面、实际验证和有意义的未覆盖项。交付前检查全部待提交改动，排除无关文件、本地配置和运行产物；不要用 `git add .` 把整个工作区一并纳入。

只有用户要求 Git / TAPD 交付时，才进入 `blueking-tapd-dev`。已授权范围内连续执行，明确要求人工 review 时等待其完成。

### 核对交付目标和文稿

交付预览明确写出 `head_remote:head → pr_target_remote:base`、关联 TAPD 单据、提交内容和测试事实。remote 以实际配置为准，base 需要 fetch 验证存在；“PR 提到 feat/X”表示目标 base 为 `feat/X`，不是默认改合主分支。

commit subject 简短描述最终改动，关联形式为 `--story=<短ID>` 或 `--bug=<短ID>`，具体校验见 [webpack/verify-commit.js](../webpack/verify-commit.js)。不要把完整单据标题或内部链接直接塞进提交信息。

PR 标题、正文和 TAPD 评论的自然语言默认简体中文，路径、API、命令、SHA 与 ID 保留原文。说明问题、修改后的行为、影响范围和已完成的验证；公开内容不包含内网 URL、完整 TAPD 链接或凭据。脱敏不等于翻译成英文。

项目提交 hook 配置见 [package.json](../package.json)。不使用 `--no-verify` 绕过检查，不主动批量修格式；若 hook 改变了待交付代码，需要重新检查 diff，并按代码变化规则复测。签名和交互认证由本人本地完成。

### PR 成功后自动回写

本项目“提交 / 创建 PR”默认包含成功后自动回写对应 TAPD 评论，明确要求不要回写时跳过。流程为：

1. 创建并核验 PR，取得真实 URL、分支与 SHA。
2. 核对关联单据；缺失或不明确时只补问目标，不猜测或自动建单。
3. 基于真实改动与测试事实准备评论及所需证据，写入前查重。
4. 回写并核验结果；失败时保留 PR 成功事实，从评论步骤恢复。

PR 创建失败或结果未知时，不写“PR 已创建”的成功评论。只修改历史 PR 的文案，不自动新增 TAPD 评论；建单、状态、负责人和迭代变更也不包含在默认回写中。

### 中断后继续

续跑时复核已确认的分支、基线、方案、授权、代码和验证产物，从首个未完成步骤恢复。记录外部动作是计划执行、等待确认、已请求但结果未知，还是已核验成功；结果未知时先查现状，避免重复 PR 或评论。

## 6. 构建与资料索引

开发、构建命令在 `bkmonitor/webpack` 执行，完整入口见 [package.json](../package.json) 和 [Makefile](../Makefile)。按目标选择 `pnpm pc:build`、`pnpm trace:build`、`pnpm apm:build`、`pnpm fta:build`、`pnpm mobile:build` 或 `pnpm external:build`；只有需要全量构建时才使用 `pnpm build`。

[webpack/utils.js](../webpack/utils.js) 定义应用与产物目录映射，例如主应用输出到 `monitor`、移动端输出到 `weixin`。`make prod` 包含构建、清理和搬运到 `../static/`，不能把它当作无副作用检查或已经完成部署的证据。

| 进一步核对 | 维护入口 |
| --- | --- |
| AI 工作规则与授权边界 | [AGENTS.md](../AGENTS.md) |
| 安装、启动和 skills 清单 | [README](../README.md) |
| 流程推进与续跑 | `bkmonitor-workflow` |
| 各 package 规范、架构与共享边界 | `bkmonitor-dev`、`bkmonitor-dev-guardrails` |
| 设计取证、组件映射与验收 | `blueking-figma-dev` 与匹配依赖的组件 skill |
| 环境与服务诊断 | `bkmonitor-onboarding`、`bkmonitor-dev-server` |
| 验证与视觉证据 | `bkmonitor-e2e-test`、`bkmonitor-e2e-visual`、[公共 E2E 配置](../e2e/README.md) |
| PR / TAPD 文稿与交付操作 | `blueking-tapd-dev` |

团队经验仅在明确要求时通过 `bkmonitor-continual-learning` 沉淀；历史经验使用前仍需与当前源码核对。更新本文时优先修正入口和事实，具体操作规则继续在对应 skill 中维护，避免产生多套不一致的流程。
