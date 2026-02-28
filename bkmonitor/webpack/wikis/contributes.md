# 蓝鲸监控平台前端开发指南

> 本文档旨在帮助新人快速了解项目结构、开发规范和开发流程，快速上手开发。

## 目录

- [项目概述](#项目概述)
- [技术栈](#技术栈)
- [环境搭建](#环境搭建)
- [项目结构](#项目结构)
- [开发规范](#开发规范)
- [核心功能使用](#核心功能使用)
- [开发流程](#开发流程)
- [构建和部署](#构建和部署)
- [常见问题](#常见问题)
- [最佳实践](#最佳实践)

---

## 项目概述

蓝鲸监控平台前端采用**微前端架构**，包含多个独立的微应用模块：

- **monitor-pc**：监控平台主应用（Vue2 + TSX）
- **trace**：链路追踪应用（Vue3 + TSX）
- **apm**：应用性能监控（Vue2 + TSX）
- **fta-solutions**：故障自愈（Vue2 + TSX）
- **monitor-mobile**：移动端应用（Vue2 + Vue）
- **external**：外部应用（Vue2 + TSX）

### 技术栈

#### Vue 版本

- **Vue2 模块**：monitor-pc、apm、fta-solutions、monitor-mobile、external
  - Vue 2.x
  - TypeScript + TSX
  - Vue Router 3.x
  - Vuex 3.x

- **Vue3 模块**：trace
  - Vue 3.x
  - TypeScript + TSX
  - Vue Router 4.x
  - Pinia

#### 其他技术

- **包管理**：pnpm（必须使用 pnpm，项目已配置 `only-allow pnpm`）
- **构建工具**：@blueking/bkmonitor-cli + webpack
- **Node.js 版本**：>= 20.17.0（使用 nvm 管理）
- **UI 组件库**：
  - Vue2：bk-magic-vue
  - Vue3：bkui-vue、@blueking/tdesign-ui
- **图表库**：ECharts
- **代码规范**：ESLint + Biome + Prettier

---

## 环境搭建

### 1. 前置要求

- [pnpm](https://pnpm.io/installation) 用于前端依赖管理
- [nvm](https://github.com/nvm-sh/nvm) 用于 Node.js 版本管理
- Node.js >= 20.17.0

### 2. 安装依赖

```bash
# 使用 nvm 切换到项目要求的 Node.js 版本
nvm use

# 安装依赖（项目会自动检查是否使用 pnpm）
pnpm i
# 或使用 Makefile
make deps
```

### 3. 配置本地开发环境

在项目根目录创建 `local.settings.js` 文件（**此文件不会提交到 Git**）：

```javascript
const context = ['/apm', '/rest', '/fta', '/api', '/weixin', '/version_log', '/calendars', '/alert', '/query-api'];
const changeOrigin = true;
const secure = false;
const devProxyUrl = 'http://xxx.com'; // 代理的后台 API 目标环境地址

const host = `appdev.${devProxyUrl.match(/\.([^.]+)\.com\/?/)[1]}.com`; // 本地 hosts 配置的同级域名
const proxy = {
  context,
  changeOrigin,
  secure,
  target: devProxyUrl,
  headers: {
    host: devProxyUrl.replace(/https?:\/\//i, ''),
    referer: devProxyUrl,
    'X-CSRFToken: '', // 监控平台 API 所需的 X-CSRFToken
    Cookie: ``, // 监控平台 API 所需的 cookie
  },
};
const defaultBizId = proxy.headers.Cookie.match(/bk_biz_id=([^;]+);?/)[1]; // 默认空间业务 ID
module.exports = {
  devProxyUrl,
  host,
  proxy,
  defaultBizId,
};
```

### 4. 启动开发服务器

```bash
# monitor-pc 模块
make dev-pc
# 或
pnpm pc:dev

# trace 模块（Vue3）
make dev-vue3
# 或
pnpm trace:dev

# 其他模块
make dev-apm      # APM 模块
make dev-fta      # FTA 模块
make dev-mobile   # 移动端
make dev-external # 外部应用
```

**默认端口**：7001（会自动寻找可用端口，范围 7001-8888）

**访问地址**：`http://appdev.xxx.com:7001`（根据 `local.settings.js` 中的 host 配置）

---

## 项目结构

```
bkmonitor/webpack/
├── src/
│   ├── monitor-pc/          # 监控平台主应用（Vue2）
│   ├── trace/               # 链路追踪应用（Vue3）
│   ├── apm/                 # 应用性能监控（Vue2）
│   ├── fta-solutions/       # 故障自愈（Vue2）
│   ├── monitor-mobile/      # 移动端应用（Vue2）
│   ├── external/            # 外部应用（Vue2）
│   ├── monitor-api/         # API 封装（公共）
│   ├── monitor-common/      # 公共工具（公共）
│   ├── monitor-ui/          # UI 组件库（公共）
│   └── monitor-static/      # 静态资源（公共）
├── webpack/                 # webpack 配置
├── public/                  # 公共静态资源
├── package.json
├── pnpm-workspace.yaml     # pnpm workspace 配置
├── local.settings.js        # 本地开发配置（不提交）
├── Makefile                 # 常用命令
└── README.md
```

### 路径别名

项目配置了以下路径别名，方便引用：

- `@`：当前模块目录（如 `src/monitor-pc`）
- `@router`：路由目录
- `@store`：状态管理目录
- `@page`：页面目录
- `@api`：API 目录（`src/monitor-api`）
- `@static`：静态资源目录（`src/monitor-static`）
- `@common`：公共工具目录（`src/monitor-common`）

---

## 开发规范

### 1. 文件命名规范

- **文件名**：使用 kebab-case（如 `hello-world.tsx`）
- **组件名**：使用 PascalCase（如 `HelloWorld`）
- **SCSS 类名**：使用 kebab-case（如 `.hello-world`）

### 2. 代码格式规范

- **缩进**：2 个空格
- **行宽**：120 字符
- **引号**：单引号
- **分号**：必须使用
- **换行符**：LF

### 3. 组件开发规范

#### Vue2 组件模板（monitor-pc、apm、fta-solutions 等）

```tsx
import { Component } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import './hello-world.scss';

interface IHelloWorldProps {
  // TODO: 定义 props 类型
}

interface IHelloWorldEvents {
  // TODO: 定义 events 类型
}

@Component({
  name: 'HelloWorld',
})
export default class HelloWorld extends tsc<IHelloWorldProps, IHelloWorldEvents> {
  // @Prop({ type: String, default: '' }) propName: string;

  render() {
    return <div class='hello-world'>{/* TODO: 组件内容 */}</div>;
  }
}
```

#### Vue3 组件模板（trace 模块）

```tsx
import { defineComponent } from 'vue';

import './desk-top.scss';

export default defineComponent({
  name: 'DeskTop',
  props: {},
  emits: [],
  setup(props, { emit }) {
    return {};
  },
  render() {
    return <div class='desk-top'>{/* TODO: 组件内容 */}</div>;
  },
});
```

#### SCSS 文件模板

```scss
.hello-world {
  // TODO: 样式内容
}
```

**提示**：可以使用 `.cursor/commands/create-component.md` 命令快速创建组件模板。

### 4. Git 规范

#### 分支命名

格式：`type/功能名/#TAPD_ID`

示例：

- `feat/ai/#1010158081130505269`
- `fix/bug/#1010158081130505270`
- `feat/new-feature`（无 TAPD ID）

#### Commit Message 规范

遵循 [Conventional Commits](https://www.conventionalcommits.org/) 规范：

```
<type>(<scope>): <subject>

<body>
```

**类型（type）**：

- `feat`：新功能
- `fix`：Bug 修复
- `docs`：文档变更
- `style`：代码格式（不影响功能）
- `refactor`：重构
- `perf`：性能优化
- `test`：测试相关
- `chore`：构建/工具变更

**示例**：

```
feat: 【监控平台】新增告警通知配置功能

本次改动：
- 添加通知渠道选择组件
- 实现通知规则配置逻辑
- 新增相关 API 接口调用
```

**提示**：可以使用 `.cursor/commands/git-commit.md` 命令自动生成 commit message。

### 5. 代码检查

项目配置了 Git Hooks，提交前会自动检查：

- **pre-commit**：执行 `lint-staged`，检查代码格式
- **commit-msg**：验证 commit message 格式

如果检查失败，需要修复后才能提交。

---

## 核心功能使用

### 1. API 调用

#### Vue2 模块

```typescript
// 调用 API
this.$api[模块名][方法名](参数, 配置);

// 示例
const data = await this.$api.alert.searchAlert(
  {
    keyword: 'test',
    page: 1,
    page_size: 10,
  },
  {
    needMessage: false, // 不显示错误提示
    needCancel: true, // 取消重复请求
  }
);
```

#### Vue3 模块

```typescript
import Api from 'monitor-api';

// 调用 API
const data = await Api.alert.searchAlert({
  keyword: 'test',
  page: 1,
  page_size: 10,
});
```

#### API 配置选项

- `needBiz: true`：自动添加业务 ID（默认开启）
- `needMessage: true`：错误时自动弹窗提示（默认开启）
- `needCancel: false`：是否取消重复请求
- `isAsync: false`：是否为异步任务
- `needRes: false`：是否返回完整 response 对象

#### API 模块定义

API 模块定义在 `src/monitor-api/modules/` 目录下：

```javascript
import { request } from '../base';

export const searchAlert = request('POST', 'fta/alert/alert/search/');
export const alertDetail = request('GET', 'fta/alert/alert/detail/');

export default {
  searchAlert,
  alertDetail,
};
```

### 2. 路由配置

#### Vue2 模块

在对应模块的 `router/router-config.ts` 中定义路由：

```typescript
export default [
  {
    path: '/example',
    name: 'example',
    component: () => import('@page/example/example'),
    meta: {
      title: '示例页面',
      navId: 'example',
    },
  },
] as RouteConfig[];
```

#### Vue3 模块

在 `src/trace/router/router-config.ts` 中定义路由：

```typescript
export default [
  {
    path: '/example',
    name: 'example',
    component: () => import('@page/example/example'),
    meta: {
      title: '示例页面',
    },
  },
];
```

**注意**：微前端环境下，路由路径会自动添加 `parentRoute` 前缀。

### 3. 权限控制

#### Vue2 模块

使用 `authorityMixin` 混入：

```typescript
import authorityMixinCreate from '@/mixins/authorityMixin';

const authMap = {
  VIEW_AUTH: 'view_action_id',
  EDIT_AUTH: 'edit_action_id',
};

@Component
class MyComponent extends Mixins(authorityMixinCreate(authMap)) {
  // 通过 this.authority.VIEW_AUTH 判断权限
  render() {
    return (
      <div>
        {this.authority.VIEW_AUTH && <div>有查看权限</div>}
        {this.authority.EDIT_AUTH && <button>编辑</button>}
      </div>
    );
  }
}
```

#### Vue3 模块

使用 Pinia store：

```typescript
import { useAuthorityStore } from '@/store/modules/authority';

const authorityStore = useAuthorityStore();
const authority = await getAuthorityMap({
  VIEW_AUTH: 'view_action_id',
  EDIT_AUTH: 'edit_action_id',
});
```

### 4. 国际化

#### Vue2 模块

```typescript
// 在模板中使用
this.$t('common.confirm');
this.$tc('common.cancel');

// 在代码中使用
import i18n from '@/i18n';
i18n.t('common.confirm');
```

#### Vue3 模块

```typescript
import { useI18n } from 'vue-i18n';

const { t } = useI18n();
t('common.confirm');
```

**语言文件位置**：各模块的 `i18n/lang/` 目录

### 5. UI 组件使用

#### Vue2 模块（bk-magic-vue）

```tsx
import { bkButton, bkTable, bkDialog } from 'bk-magic-vue';

// 全局已注册，直接使用
<bk-button theme="primary">确认</bk-button>
<bk-table :data="tableData" />
```

#### Vue3 模块（bkui-vue）

```tsx
import { Button, Table, Message } from 'bkui-vue';

<Button theme="primary">确认</Button>
<Table :data="tableData" />
<Message theme="success">操作成功</Message>
```

### 6. 图表使用

#### Vue2 模块

```tsx
import MonitorEcharts from 'monitor-ui/monitor-echarts';

<MonitorEcharts
  :options="chartOptions"
  :get-series-data="getData"
  :height="400"
/>
```

#### Vue3 模块

```tsx
import VueEcharts from 'vue-echarts';

<VueEcharts
  :option="chartOptions"
  autoresize
/>
```

### 7. Loading 状态

#### Vue2 模块

```tsx
// 使用指令
<div v-bkloading={{ isLoading: loading }}>内容</div>;

// 全局 loading
this.$store.commit('app/SET_MAIN_LOADING', true);
```

#### Vue3 模块

```tsx
// 使用指令
<div v-loading='loading'>内容</div>
```

### 8. 表单验证

```typescript
// 获取表单引用
const formRef = this.$refs.formRef; // Vue2
const formRef = ref<InstanceType<typeof Form>>(null); // Vue3

// 验证
await formRef.validate();

// 清除验证
formRef.clearValidate();
```

### 9. 样式变量

各模块有主题变量文件：

- `src/monitor-pc/theme/theme.scss`
- `src/trace/theme/theme.scss`
- `src/apm/theme/theme.scss`

常用变量：

```scss
$primary-color: #3a84ff;
$success-color: #2dcb56;
$warning-color: #ff9c01;
$danger-color: #ea3636;
$font-size-base: 12px;
$border-color-base: #dcdee5;
```

---

## 开发流程

### 1. 根据 TAPD 单开发

#### 创建分支

**分支命名规则：** `{type}/{category}/#{TAPD_ID}`

| 单据类型      | type   | 示例分支名                       |
| ------------- | ------ | -------------------------------- |
| 需求（Story） | `feat` | `feat/opus/#1010158081130072997` |
| 缺陷（Bug）   | `fix`  | `fix/opus/#1010158081130072997`  |
| 任务（Task）  | `task` | `task/opus/#1010158081130072997` |

**category 取值规则：**

使用当前执行操作的 AI 模型缩写作为 category，如果无法确定则回退到 `ai`。

| 模型              | category   |
| ----------------- | ---------- |
| Claude Opus 4.5   | `opus`     |
| Claude Sonnet 4   | `sonnet`   |
| Claude 3.5 Sonnet | `sonnet35` |
| GPT-4             | `gpt4`     |
| 其他/未知         | `ai`       |

> 💡 category 用于标识分支由哪个 AI 模型辅助创建，方便追溯。

**创建步骤（三条 Git 命令）：**

```bash
# 1. 同步 upstream 仓库最新代码
git fetch upstream

# 2. 基于 upstream/master 创建新分支（以 Claude Opus 4.5 为例）
git checkout -b feat/opus/#1010158081130072997 upstream/master

# 3. 推送分支到 origin 仓库并设置上游追踪
git push --set-upstream origin feat/opus/#1010158081130072997
```

**命令说明：**

| 命令                                       | 作用                                    |
| ------------------------------------------ | --------------------------------------- |
| `git fetch upstream`                       | 从 upstream 仓库拉取最新代码（不合并）  |
| `git checkout -b <branch> upstream/master` | 基于 upstream/master 创建并切换到新分支 |
| `git push --set-upstream origin <branch>`  | 推送新分支到 origin 并建立追踪关系      |

**验证分支创建成功：**

```bash
git branch --show-current
# 输出：feat/opus/#1010158081130072997
```

#### 开发前准备

1. **提出实现方案**：开发新组件或需求前，先提出实现思路和方案，确认后再开始
2. **创建组件**：使用组件模板创建组件（`.cursor/commands/create-component.md`）
3. **了解需求**：仔细阅读 TAPD 单，明确需求细节

#### 开发中

1. **遵循规范**：按照代码规范和组件模板开发
2. **及时沟通**：遇到不确定的地方主动询问
3. **代码检查**：开发过程中注意代码格式和 lint 规则

#### 提交代码

```bash
# 1. 暂存文件
git add .

# 2. 使用 Git commit 命令自动生成 commit message
# （会自动从分支名提取 TAPD ID 并关联 TAPD 信息）

# 3. 如果 commit message 生成失败，手动编写
git commit -m "feat: 【监控平台】TAPD标题

本次改动：
- 改动说明1
- 改动说明2"
```

### 2. 开发新功能的标准流程

1. **需求分析**：理解需求，明确功能点
2. **技术方案**：提出实现思路和方案，**等待确认**
3. **创建分支**：基于 TAPD 单创建功能分支
4. **开发实现**：按照方案实现功能
5. **自测验证**：本地测试功能是否正常
6. **代码提交**：提交代码并推送到远程
7. **Code Review**：等待代码审查

### 3. 注意事项

⚠️ **重要提醒**：

- ✅ **开发前必须先提出方案，确认后再实现**
- ✅ **有任何不确定都需要主动询问**
- ❌ **不要主动处理 eslint 或格式问题**（需经过确认）
- ❌ **不要执行脚本**（需经过确认）
- ❌ **不要使用 `debugger`**（会被 lint 拦截）
- ❌ **不要提交 `local.settings.js`**（已加入 .gitignore）

---

## 构建和部署

### 构建命令

```bash
# 并行构建所有模块
make build
# 或
pnpm run build

# 串行构建
make build-s

# 单个模块构建
make build-pc      # monitor-pc
make build-vue3    # trace
make build-apm     # apm
make build-fta     # fta-solutions
make build-mobile  # monitor-mobile
make build-external # external

# 生产构建（构建 + 清理 + 移动文件）
make prod
```

### 构建输出

构建完成后，各模块会输出到对应目录：

- `monitor/` → `../static/monitor/`
- `trace/` → `../static/trace/`
- `apm/` → `../static/apm/`
- 等等...

### Docker 构建

```bash
make docker-build
# 或
./docker_build.sh
```

构建完成后会生成 `frontend.tar.gz` 文件。

### 构建分析

```bash
# 可视化构建分析
make vis-pc      # monitor-pc
make vis-vue3    # trace
make vis-apm     # apm
```

---

## 常见问题

### 1. 端口冲突

**问题**：开发服务器启动失败，提示端口被占用

**解决**：开发服务器会自动寻找可用端口（7001-8888），如果都被占用，需要手动关闭占用端口的进程。

### 2. 代理配置问题

**问题**：API 请求失败，无法连接后端

**解决**：

1. 检查 `local.settings.js` 中的 `devProxyUrl` 是否正确
2. 检查 `host` 配置是否在本地 hosts 文件中
3. 检查 `Cookie` 和 `X-CSRFToken` 是否正确

### 3. 权限问题

**问题**：页面显示 403 无权限

**解决**：

1. 检查路由配置中的 `authority` 配置
2. 确认当前用户是否有对应权限
3. 可以通过权限申请页面申请权限

### 4. 微前端环境判断

**问题**：路由跳转异常，路径不正确

**解决**：注意判断是否在微前端环境中：

```typescript
// 判断是否在微前端环境
if (window.__POWERED_BY_BK_WEWEB__) {
  // 微前端环境下的逻辑
  const parentRoute = window.__BK_WEWEB_DATA__?.parentRoute || '/';
}
```

### 5. Vue2 和 Vue3 语法差异

**问题**：在 trace 模块中使用 Vue2 语法报错

**解决**：

- trace 模块是 Vue3，需要使用 Vue3 的语法
- 其他模块是 Vue2，使用 Vue2 的语法
- 注意区分 `defineComponent`（Vue3）和 `@Component`（Vue2）

### 6. 代码检查失败

**问题**：提交代码时 lint 检查失败

**解决**：

1. 查看错误信息，修复对应问题
2. 未使用的变量：删除或使用
3. 格式问题：运行 `pnpm biome:check` 自动修复
4. TypeScript 错误：修正类型定义

### 7. 依赖安装失败

**问题**：`pnpm i` 失败

**解决**：

1. 确认使用 pnpm（项目强制使用 pnpm）
2. 检查 Node.js 版本（>= 20.17.0）
3. 清除缓存：`pnpm store prune`
4. 删除 `node_modules` 和 `pnpm-lock.yaml`，重新安装

---

## 最佳实践

### 1. 代码组织

- ✅ 使用路径别名（`@`、`@api`、`@common` 等）
- ✅ 优先使用公共工具函数（`monitor-common/utils`）
- ✅ 遵循组件模板规范
- ✅ 合理使用代码分割和懒加载

### 2. 性能优化

- ✅ 路由使用懒加载
- ✅ 大组件使用代码分割
- ✅ 避免不必要的重复渲染
- ✅ 使用 `keep-alive` 缓存页面组件
- ✅ 图表组件支持按需加载

### 3. 错误处理

- ✅ API 调用统一错误处理
- ✅ 使用 try-catch 捕获异常
- ✅ 友好的错误提示（使用 `bkMessage`）
- ✅ 404/403 页面跳转处理

### 4. 样式规范

- ✅ 优先使用主题变量，避免硬编码颜色
- ✅ 使用 SCSS 混入（mixins）复用样式
- ✅ 遵循 BEM 命名规范（部分模块）
- ✅ 样式文件与组件文件同名

### 5. 调试技巧

- ✅ 使用 Vue DevTools 调试组件
- ✅ 使用 `console.log` 调试（生产环境会自动移除）
- ✅ 移动端可通过 URL 参数 `?console` 启用 vconsole
- ✅ 使用浏览器 Network 面板查看 API 请求

### 6. Git 使用

- ✅ 提交前先检查代码（`git status`、`git diff`）
- ✅ 使用有意义的 commit message
- ✅ 及时提交代码，避免大文件提交
- ✅ 提交前确保代码通过 lint 检查

---

## 相关资源

### 文档

- [README.md](../README.md)：项目基础文档
- [.cursor/commands/create-component.md](../.cursor/commands/create-component.md)：组件创建命令
- [.cursor/commands/git-commit.md](../.cursor/commands/git-commit.md)：Git 提交命令

### 工具

- **Makefile**：常用命令集合，运行 `make help` 查看所有命令
- **组件模板**：使用 `.cursor/commands/create-component.md` 快速创建组件
- **Git 提交助手**：使用 `.cursor/commands/git-commit.md` 自动生成 commit message

### 联系方式

如有问题，可以：

1. 查看项目文档
2. 询问团队成员
3. 查看代码注释和 TODO

---

## 总结

作为新人，开发时请记住：

1. ✅ **先理解需求，再提出方案，确认后再实现**
2. ✅ **遵循代码规范和项目结构**
3. ✅ **遇到问题主动询问，不要自己猜测**
4. ✅ **提交前检查代码，确保通过 lint**
5. ✅ **使用项目提供的工具和模板，提高效率**

祝开发顺利！🎉
