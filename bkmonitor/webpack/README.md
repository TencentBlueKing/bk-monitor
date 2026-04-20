# 蓝鲸监控平台前端

蓝鲸监控平台前端采用**微前端架构**，包含多个独立的微应用模块：

| 模块               | 说明           | 技术栈     |
| ------------------ | -------------- | ---------- |
| **monitor-pc**     | 监控平台主应用 | Vue2 + TSX |
| **trace**          | 链路追踪应用   | Vue3 + TSX |
| **apm**            | 应用性能监控   | Vue2 + TSX |
| **fta-solutions**  | 故障自愈       | Vue2 + TSX |
| **monitor-mobile** | 移动端应用     | Vue2 + Vue |
| **external**       | 外部应用       | Vue2 + TSX |

## 技术栈

- **包管理**：pnpm（项目已配置 `only-allow pnpm`）
- **构建工具**：@blueking/bkmonitor-cli + webpack
- **Node.js**：>= 20.17.0（推荐使用 nvm 管理）
- **UI 组件库**：bk-magic-vue（Vue2）/ bkui-vue、@blueking/tdesign-ui（Vue3）
- **图表库**：ECharts
- **代码规范**：ESLint + Biome + Prettier

## 快速开始

### 前置要求

- [pnpm](https://pnpm.io/installation) — 前端依赖管理
- [nvm](https://github.com/nvm-sh/nvm) — Node.js 版本管理

### 安装依赖

```bash
nvm use
pnpm i
# 或
make deps
```

### 配置本地开发环境

在项目根目录创建 `local.settings.js`（此文件已加入 .gitignore，不会提交）：

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
    'X-CSRFToken': '', // 监控平台 API 所需的 X-CSRFToken
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

### 启动开发服务器

```bash
make dev-pc        # monitor-pc（主应用）
make dev-vue3      # trace（Vue3）
make dev-apm       # APM
make dev-fta       # FTA
make dev-mobile    # 移动端
make dev-external  # 外部应用
```

默认端口 `7001`（自动寻找可用端口，范围 7001–8888），访问地址：`http://appdev.xxx.com:7001`

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
├── pnpm-workspace.yaml
├── local.settings.js        # 本地开发配置（不提交）
├── Makefile                 # 常用命令
└── README.md
```

### 路径别名

| 别名      | 路径                                |
| --------- | ----------------------------------- |
| `@`       | 当前模块目录（如 `src/monitor-pc`） |
| `@router` | 路由目录                            |
| `@store`  | 状态管理目录                        |
| `@page`   | 页面目录                            |
| `@api`    | `src/monitor-api`                   |
| `@static` | `src/monitor-static`                |
| `@common` | `src/monitor-common`                |

## 构建

```bash
make build           # 并行构建所有模块
make build-s         # 串行构建所有模块
make prod            # 生产构建（构建 + 清理 + 移动文件到 ../static/）

make build-pc        # 单独构建 monitor-pc
make build-vue3      # 单独构建 trace
make build-apm       # 单独构建 apm
make build-fta       # 单独构建 fta-solutions
make build-mobile    # 单独构建 monitor-mobile
make build-external  # 单独构建 external

make docker-build    # Docker 构建（生成 frontend.tar.gz）
```

## 所有 Make 命令

运行 `make help` 查看完整列表：

| 分类              | 命令                                                                                 | 说明                              |
| ----------------- | ------------------------------------------------------------------------------------ | --------------------------------- |
| **Dependencies**  | `make deps`                                                                          | 安装前端依赖                      |
| **Development**   | `make dev-pc`                                                                        | 启动 Monitor 开发服务器           |
|                   | `make dev-apm`                                                                       | 启动 APM 开发服务器               |
|                   | `make dev-fta`                                                                       | 启动 FTA 开发服务器               |
|                   | `make dev-vue3`                                                                      | 启动 Vue3 (trace) 开发服务器      |
|                   | `make dev-mobile`                                                                    | 启动移动端开发服务器              |
|                   | `make dev-external`                                                                  | 启动外部应用开发服务器            |
| **Build**         | `make build`                                                                         | 并行构建所有应用                  |
|                   | `make build-s`                                                                       | 串行构建所有应用                  |
|                   | `make prod`                                                                          | 生产构建                          |
|                   | `make build-pc / build-apm / build-fta / build-vue3 / build-mobile / build-external` | 单模块构建                        |
| **Linter**        | `make check-pc`                                                                      | Biome 检查 monitor-pc             |
|                   | `make eslint-pc`                                                                     | ESLint 检查 monitor-pc            |
| **Visualization** | `make vis-pc / vis-apm / vis-fta / vis-vue3 / vis-mobile / vis-external`             | 构建产物可视化分析                |
| **Docker**        | `make docker-build`                                                                  | Docker 构建并提取 frontend.tar.gz |
| **Utilities**     | `make clean`                                                                         | 清理旧静态文件                    |
|                   | `make move`                                                                          | 移动构建产物到 static 目录        |
|                   | `make reflesh-git-hooks`                                                             | 刷新 Git Hooks                    |

## 开发指南

更详细的开发规范、核心功能使用、开发流程、常见问题及最佳实践，请参阅 **[开发指南](./wikis/contributes.md)**，包含：

- 组件开发规范（Vue2/Vue3 组件模板）
- API 调用方式与配置选项
- 路由配置、权限控制、国际化
- Git 分支与 Commit 规范
- 常见问题排查
- 性能优化与最佳实践
