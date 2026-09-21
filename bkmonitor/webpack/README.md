# 蓝鲸监控平台前端

这里是 `bkmonitor/webpack` 前端工作区，包含监控主应用、APM、告警与故障处理、Trace / Profiling / RUM、移动端及共享模块。项目使用 pnpm workspace 管理多个 package，Vue2 与 Vue3 并存，通过 `@blueking/bk-weweb` 集成微前端；应用构建使用 `@blueking/bkmonitor-cli` 与 webpack，部分组件库构建使用 Vite。

项目提供配套的 AI 开发 skills，覆盖环境搭建、需求分析、设计实现、代码开发、一次性 E2E 和 PR / TAPD 交付。开发者给出目标、范围与验收要求，AI 根据项目规则推进，并用源码、实际执行结果和交付产物说明完成情况。

## 从 AI 开发开始

### 准备工作区与 skills

使用能够读取项目文件并执行工具的 AI 开发环境打开本目录，先让 AI 读取 [AGENTS.md](./AGENTS.md)。它是项目规则入口；本 README 介绍如何使用，具体约束与操作步骤由 AGENTS 和对应 skill 维护。

团队 skills 在独立仓库维护，通过团队分发方式安装到 AI 宿主可发现的位置。本地通常可见 `.agents/skills/<skill-name>/SKILL.md`；`.agents/` 被 Git 忽略，**只克隆本项目不会自动安装 skills**。不要把私有 skill 正文或运行脚本复制进公开仓库。

首次使用时，向团队维护者获取完整的 `bkmonitor-onboarding` 目录包，包含 `SKILL.md`、`references/` 和 `scripts/`。在 macOS 的选定工作目录中放入 `.agents/skills/bkmonitor-onboarding/`，再让 AI 读取入口文件。该流程可用于尚未安装开发工具的新电脑，当前 onboarding 支持 macOS，提供 Cursor / Codex 宿主适配。其他环境按实际工具链准备，不直接套用 macOS 安装步骤。

```text
请读取 .agents/skills/bkmonitor-onboarding/SKILL.md，
检查这台 Mac 的开发环境，补齐工具和团队 skills，
配置并启动监控前端，验证目标页面能够访问。
```

已有项目与工具时，先核对已安装 skills，缺失项按团队分发流程补齐。安装清单以 onboarding 的 `references/default-skills.txt` 为准，不以某台机器上的不完整安装结果为准。

读取 Figma、操作 TAPD 或创建 GitHub PR 时，还需要相应集成、工具与账号权限；安装 skill 本身不等于这些能力已经可用。缺少某项集成时，只暂停依赖它的步骤，不阻塞其他已具备条件的本地工作。

### 按目标选择入口

可以直接描述任务，也可以点名使用的 skill。不是所有任务都要走完整开发流程。

| 你要做的事 | 主要入口 | 得到什么 |
| --- | --- | --- |
| 首次搭建环境 | `bkmonitor-onboarding` | 工具、代码、skills、鉴权与目标页面的启动验证 |
| 已有环境启动或排错 | `bkmonitor-dev-server` | 实际访问地址、进程归属、编译与鉴权状态 |
| 开发功能、修 bug、接续开发 | `bkmonitor-workflow` | 基线与方案、实现、验证和下一步交接 |
| 查询架构、规范或审查实现 | `bkmonitor-dev` + `bkmonitor-dev-guardrails` | 技术栈依据、现状、影响面与验证范围 |
| 按 Figma 或截图实现界面 | `blueking-figma-dev`，由开发流程衔接 | 设计状态、组件映射与视觉验收输入 |
| 针对本次需求跑 E2E | `bkmonitor-e2e-test` | 一次性用例、实际结果、本地报告与交付事实 |
| 验证设计还原或布局缺陷 | `bkmonitor-e2e-visual`，配合 E2E | 视觉对比、几何断言和截图证据 |
| TAPD 建单、Git / PR 交付、回写 | `blueking-tapd-dev` | 已核验的单据、提交、PR 与评论；该 skill 不编码 |
| 沉淀已验证的会话经验 | `bkmonitor-continual-learning` | 经审阅的团队知识；仅在明确要求时执行 |

组件与框架问题按**实际 import、Vue 入口和安装版本**选择资料：

| 依赖 / 能力 | 对应 skill |
| --- | --- |
| Vue2 `bk-magic-vue` | `bk-magicbox-vue-components` |
| Vue3 `bkui-vue` | `bkui-vue-components` |
| `@blueking/tdesign-ui` | `blueking-tdesign-ui` |
| `@blueking/date-picker` | `blueking-date-picker` |
| `@blueking/search-select-v3` | `blueking-search-select-v3` |
| `@blueking/bk-weweb` 微前端 | `bk-weweb` |
| `@blueking/open-telemetry` RUM SDK | `bk-rum-otele` |

组件名称或相邻用法不能单独证明 API。文档缺失或与依赖冲突时，需要核对匹配版本的类型、源码或官方资料；示例还需适配目标 package 的写法。

## 从需求到交付

```mermaid
flowchart LR
    A[明确目标与任务终点] --> B[确认目标分支与基线]
    B --> C[源码与设计取证]
    C --> D[确认实现方案]
    D --> E[实现与已授权验证]
    E --> F[交付本地结果]
    F -->|要求提交 PR| G[创建并核验 PR]
    G -->|默认回写，明确禁止时跳过| H[对应 TAPD 评论与核验]
```

### 1. 先确定分析哪份代码

业务开发、修复和设计实现相关的分析，先确认目标分支、基线及继续 / 切换 / 新建策略，再检查领先、落后和未提交改动。当前分支可能比主分支旧，也可能包含主分支没有的实现，不能直接把当前工作区当成主分支现状。

AI 可以先做 Git 元数据侦察；已确认且未变化的选择直接复用，不擅自切分支、同步代码或暂存无关改动。规范咨询、skills / 文档审查可直接只读进行。只要求分析时，任务停在结论与方案，不自动扩展为开发。

### 2. 用证据形成方案

先定位目标 package，核验功能是否已经存在、可复用的实现、真实接口与共享消费方，再提出修改范围、实现方式和验收要点。设计任务还要核对画板、旁注及相关状态，不能只根据一张截图猜交互。

方案确认后再写业务代码；已有批准且范围未变时继续执行。无法通过查证解决的实质歧义集中询问，只暂停依赖该决定的工作。

### 3. 按范围实现与验证

AI 遵循目标 package 的技术栈和已确认方案，保持改动集中。实际执行的检查、覆盖范围及未覆盖项随结果一起交付；代码阅读、静态检查和浏览器验证分别说明。

业务实现完成且还没有 E2E 决定时，主流程会询问是否执行一次性测试，说明登录态预检、必要的临时浏览器登录、开发服务与本地报告。已明确要求 E2E 时直接复用授权；同范围修复后的复测也复用原授权。

### 4. 提交 PR 并回写 TAPD

明确要求提交 PR 后，交付 skill 核对 `head remote:branch → target remote:base`，准备具体文稿并完成已授权的提交、推送和 PR 核验。不会把 remote 名称或 `master` 当成未经确认的默认答案。

**本项目提交 PR 默认包含成功后自动回写对应 TAPD 评论。** 评论复用真实的改动、测试事实、SHA、PR 链接与所需证据；关联单据不明确时只补问目标。回写前查重，写后核验；失败时保留已成功的 PR，从未完成步骤恢复。明确说“不要回写”时跳过，仅修改已有 PR 文案也不会触发新增评论。

PR 标题、正文及 TAPD 评论的自然语言说明默认简体中文，路径、API、命令和标识符保留原文。公开内容需要脱敏；不能把英文当成脱敏要求，也不能把未执行或失败的测试写成通过。

### 给 AI 的任务示例

说明**目标、目录 / 入口、分支与基线、验收标准、做到哪一步**，可以减少来回确认。不清楚的字段直接写“待核对”，不必为了填满模板猜测。

```text
请按项目 AGENTS.md 和 bkmonitor-workflow 处理这个需求。
目标：<期望解决的问题或新增行为>
入口 / 目录：<页面、路由或 package>
分支与基线：<已确认目标；不清楚的部分先核对>
验收：<操作步骤、预期结果、需要覆盖的状态>
范围：<允许修改的部分与明确不做的部分>
本次终点：先分析并给方案，确认后再实现。
```

- **只分析**：“先核对目标分支与基线，分析这个 bug 的根因和影响面，给出最小修复方案，不改代码。”
- **设计实现**：“按这份 Figma / 截图实现指定区域，先核对标注、状态、现有封装和接口，再给方案。”
- **只测试**：“对当前已确认版本执行一次性 E2E，覆盖这些验收项，输出报告；发现产品问题先报告。”
- **交付**：“把已完成的改动提交 PR 到已确认的目标 remote / base，并按项目规则回写对应 TAPD。代码未变，复用已有测试结果。”
- **续跑**：“继续当前任务，复核已有分支、方案、授权和产物，从首个未完成步骤继续。”

## 测试结果如何使用

一次性 E2E 围绕本次需求及相关 diff 编写，不等于全站回归。设计任务包含视觉对比；溢出、遮挡、截断等布局问题需要对应几何断言和最终截图。

| 当前情况 | 处理方式 |
| --- | --- |
| 已测试，代码内容未变 | 复用已有结果，不因提交 PR 重跑 |
| 测试后代码发生变化 | 按影响范围复测，保留历史证据 |
| 仅 commit SHA 变化，内容相同 | 核对内容后复用，保留测试时的提交记录 |
| 仅 PR 文案、报告展示或附件变化 | 核对、更新交付材料，不重跑业务 E2E |
| 验收、测试源码、设计基准或执行工具变化 | 核对证据有效性，按验证规则重验 |
| 测试失败、环境阻塞或未执行 | 如实记录原因、影响与恢复点，不归为通过 |

本地报告位于 `.e2e-runs/<run-id>/report/index.html`，`delivery-facts.json` 保存交付使用的测试事实。测试目录、截图、视频、trace 及认证状态不提交到 Git。报告“当前有效”只覆盖声明的测试范围，交付前仍须核对完整 diff。

公共运行配置见 [e2e/README.md](./e2e/README.md)：

```bash
pnpm e2e:doctor   # 检查运行前提，不等于测试通过
pnpm e2e:install  # 需要时安装项目版本对应的 Chromium
```

公共配置只执行指定运行目录里的用例；没有预置的全站 E2E 套件。用例规划、实际执行、报告与证据校验由已安装的 E2E skills 负责。

## 项目与源码导航

### 应用与技术栈

| 应用 / 目录 | 主要职责 | 主要技术栈 | 启动命令 |
| --- | --- | --- | --- |
| [`src/monitor-pc`](./src/monitor-pc) | 监控主应用与微前端宿主入口 | Vue2、TSX class、Vuex、bk-magic-vue | `pnpm pc:dev` |
| [`src/trace`](./src/trace) | Vue3 应用，包含检索、告警、主机、Profiling、RUM 等页面 | Vue3、TSX、Pinia、bkui-vue / TDesign | `pnpm trace:dev` |
| [`src/apm`](./src/apm) | APM 应用 | Vue2、TSX class、Vuex | `pnpm apm:dev` |
| [`src/fta-solutions`](./src/fta-solutions) | 故障自愈应用 | Vue2、TSX class、Vuex | `pnpm fta:dev` |
| [`src/monitor-mobile`](./src/monitor-mobile) | 移动端 | Vue2 SFC、Vuex、Vant | `pnpm mobile:dev` |
| `external` 构建变体 | 复用 `src/monitor-pc` 的外部应用 | Vue2，按构建变量裁剪 | `pnpm external:dev` |

`external` 不是独立源码 package；应用和产物目录的映射见 [webpack/utils.js](./webpack/utils.js)。共享模块及 Vue2 / Vue3 适配入口须按实际依赖确认，不能仅根据 API 名称判断技术栈。

### 常用目录

```text
bkmonitor/webpack/
├── AGENTS.md              # AI 项目规则入口
├── src/
│   ├── monitor-pc/        # 监控主应用
│   ├── trace/             # Vue3 应用
│   ├── apm/               # APM 应用
│   ├── fta-solutions/     # 故障自愈应用
│   ├── monitor-mobile/    # 移动端
│   ├── monitor-api/       # API 声明与请求封装
│   ├── monitor-common/    # 公共能力
│   ├── monitor-ui/        # 共享 UI，以 Vue2 为主
│   └── monitor-static/    # 共享样式、图标与静态资源
├── webpack/               # 构建辅助逻辑
├── webpack.config.js      # 开发代理、端口与构建配置
├── scripts/               # 组件库等构建脚本
├── tests/                 # 已有回归用例，按需求查找
├── e2e/                   # 公共 Playwright 配置与依赖检查
├── wikis/                 # 开发参考文档
├── package.json           # 项目依赖与 pnpm 命令
└── pnpm-workspace.yaml     # workspace 与依赖配置
```

`.agents/`、`.e2e-runs/` 和 `local.settings.js` 属于本地安装、运行或配置内容，不应作为业务提交的一部分。

新增代码先选对 package：`trace` 按项目约定使用 TSX `defineComponent`，Vue2 页面按既有 class / SFC 方式实现；组件、状态管理、i18n 与微前端边界见 [AGENTS.md](./AGENTS.md) 和 `bkmonitor-dev`。共享代码修改要说明消费方与回归范围，不为凑分层创建空目录或无必要抽象。

## 本地运行与构建

以下命令在 `bkmonitor/webpack` 目录执行。首次配置可交给 onboarding；已有环境仅启动或排错，使用 `bkmonitor-dev-server`。

### 工具与依赖

当前 `.nvmrc` 指定 Node 22，团队 onboarding 使用 Node **22.12.0 及以上的 22.x** 和 **pnpm 10.x**。根 `package.json` 的 Node 下限较宽，不能仅凭该字段判断整套构建工具可用；实际还需满足锁定依赖的 engines。

已安装并加载 nvm 时：

```bash
nvm install
nvm use
npm install -g pnpm@10
pnpm install
```

项目依赖只用 pnpm 安装。`Makefile` 的 `make deps` 在未找到 pnpm 时仍会安装 pnpm 8，因此新环境先按上面的工具版本准备，不用该旧兜底完成初装。依赖或锁文件冲突应查看实际错误，不通过删锁文件、清缓存或忽略失败来宣称安装成功。

### 配置与启动

启动前需要可访问的后端环境、对应权限、本地 host 与代理鉴权配置。使用 `bkmonitor-dev-server` 创建缺失的配置骨架、检查登录态并在必要时打开临时浏览器，由本人完成登录。已有团队配置按实际环境复用；配置读取与合并入口见 [webpack.config.js](./webpack.config.js)。

`local.settings.js` 不提交到 Git，也不要把其中的 Cookie、Token 或完整文件发进 AI 对话。登录、账号权限及需要管理员权限的系统操作由本人参与完成。

配置完成后选择一个目标模块启动，例如：

```bash
pnpm pc:dev
# Vue3 应用使用 pnpm trace:dev；其他入口见上方应用表。
```

默认起始端口为 `7001`，实际可由本地配置覆盖，并自动寻找至 `8888` 范围内的可用端口，**以本次启动日志为准**。涉及微前端时，还要确认宿主请求的子应用地址与实际服务匹配；只看到端口监听或独立页面可打开，不代表嵌入链路已验证。

### 常用构建命令

| 目标 | 命令 |
| --- | --- |
| 构建所有应用 | `pnpm build` / `make build` |
| 构建监控主应用 | `pnpm pc:build` |
| 构建 Vue3 应用 | `pnpm trace:build` |
| 构建其他应用 | `pnpm apm:build` / `pnpm fta:build` / `pnpm mobile:build` / `pnpm external:build` |
| 串行构建应用 | `make build-s` |
| 查看 Make 任务 | `make help` |

`make prod` 还会清理并搬运产物到 `../static/`，按实际交付需要使用。完整命令以 [package.json](./package.json) 和 [Makefile](./Makefile) 为准。部分名称看似“检查”的任务会写文件，例如 `make check-pc` 包含 `--write`；AI 不主动处理格式问题或运行批量格式修复。

## 进一步阅读

| 要核对的内容 | 入口 |
| --- | --- |
| AI 路由、开发约束与交付口径 | [AGENTS.md](./AGENTS.md) |
| 当前脚本与依赖声明 | [package.json](./package.json)、[pnpm-workspace.yaml](./pnpm-workspace.yaml)、[pnpm-lock.yaml](./pnpm-lock.yaml) |
| Node 版本选择 | [.nvmrc](./.nvmrc) |
| 应用映射、代理与端口行为 | [webpack/utils.js](./webpack/utils.js)、[webpack.config.js](./webpack.config.js) |
| 公共 E2E 运行配置 | [e2e/README.md](./e2e/README.md) |
| 日常开发、源码约定、验证与交付 | [开发与 AI 协作指南](./wikis/contributes.md) |

不同分支的目录、依赖和命令可能变化。遇到 README、历史文档与当前实现不一致时，先确认目标分支与版本，再依据源码和配置核验；不要沿用未经确认的历史结论。
