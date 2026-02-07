# bklog/web 前端架构与路由数据流说明

> 说明：本文基于 `bklog/web/src` 当前代码（Vue2 + TS/TSX + 部分 Composition API 用法）静态分析整理，聚焦“架构设计、路由模块组件调用、数据流执行、主要 API 请求”。

---

### 1. 代码入口与整体架构

- **前端位置**：`bklog/web`
- **应用入口**：`bklog/web/src/main.js`
- **根组件壳**：`bklog/web/src/app.tsx`
- **路由入口**：`bklog/web/src/router/index.js`（运行时动态生成 routes）
- **状态管理**：`bklog/web/src/store/index.js`（Vuex，包含模块 `retrieve` / `collect` / `globals`）
- **HTTP 封装**：`bklog/web/src/api/index.js`（axios + 请求队列 + promise 缓存 + 统一错误处理）
- **服务定义（API key → url/method）**：`bklog/web/src/services/index.js`（聚合各业务域 service）

整体形态可以理解为：

- **App 壳（Header/Notice/Dialog/GlobalSetting）** 负责全局 UI 容器与通用状态；
- **Router** 按模块拆分（retrieve/manage/dashboard/monitor），并在路由切换时统一取消请求、做外部版重定向与路由日志上报；
- **Store（Vuex）** 承载空间/业务/索引集/检索参数/菜单等关键状态，页面通过 dispatch/commit 驱动 API 请求与视图更新；
- **HTTP 层** 负责请求缓存、取消、拦截器注入 header、错误兜底（登录/鉴权弹窗/统一提示）。

---

### 2. 启动时序（从加载到可用）

以 `src/main.js` 为主线，启动流程关键节点如下：

- **(1) 初始化全局能力**
  - 注册全局组件：`JsonFormatWrapper`、`LogButton`、`LogIcon`
  - 注册全局 mixin / plugin：`docsLinkMixin`、`methods`、`vue-virtual-scroller`
  - 设置 `Vue.prototype.$renderHeader / $xss`

- **(2) preload 阶段（决定空间/用户/全局配置）**
  - 调用 `preload({ http, store })`（`src/preload.ts`）并行拉取（Promise.allSettled）：
    - **默认空间**：`space/getMySpaceList`（必要时先 `indexSet/getSpaceByIndexId` 兜底）
    - **用户信息**：`userInfo/getUsername`
    - **全局配置**：`collect/globals`（同时会动态更新内置隐藏字段配置）
    - **用户引导**：`meta/getUserGuide`
  - preload 结果会通过 `store.commit` 写入 `spaceUid/bkBizId/userMeta/globalsData/userGuideData` 等

- **(3) 生成 router + 拉菜单 + mount Vue**
  - `getRouter(spaceUid, bkBizId, externalMenu)` 创建路由实例（`src/router/index.js`）
  - `store.dispatch('requestMenuList', spaceUid)` 拉取菜单（`meta/menu`），并映射 navId（如 search→retrieve、manage_xxx→manage-xxx）
  - mount：
    - `new Vue({ el:'#app', router, store, i18n, template:'<App/>' })`
    - 若没有 `space` 且当前不是 `share`，会跳转 `/un-authorized`（带上 spaceUid/bkBizId/indexId 等 query）

- **(4) development 环境额外步骤**
  - `http.request('meta/getEnvConstant')` 拉取环境常量并写入 `window.*`（如 `FEATURE_TOGGLE`、白名单等）

---

### 3. 路由系统设计（模块拆分 + 守卫）

#### 3.1 动态路由生成

`src/router/index.js` 中的 `getRoutes(spaceUid, bkBizId, externalMenu)` 组装完整 routes：

- 根路径 `''`：根据是否外部版、externalMenu 决定默认跳转到 `retrieve` 或 `manage`
- 业务模块：
  - `retrieveRoutes()`：检索模块
  - `monitorRoutes()`：监控嵌入模块（apm/trace）
  - `dashboardRoutes()`：仪表盘模块
  - `manageRoutes()`：管理模块（嵌套路由最多）
- 兜底：
  - `/un-authorized`：无权限页
  - `*`：404/exception

#### 3.2 beforeEach：路由切换取消请求 + 外部版重定向 + 跨应用通信

- **取消请求**：从 `http.queue` 取出 `cancelWhenRouteChange` 的请求并统一 cancel（避免路由切换后数据串扰）。
- **跨应用通信**：当 `to.name === 'retrieve'` 时，会向 `window.parent` `postMessage`（用于日志 → 监控/上层的参数同步）。
- **外部版重定向**：
  - 外部版且目标路由不在白名单（`retrieve/extract-home/extract-create/extract-clone`）时，强制跳到 `retrieve` 或 `manage`（取决于 externalMenu）。

#### 3.3 afterEach：路由日志上报

每次路由切换后（排除 exception），调用 `reportLogStore.reportRouteLog` 上报：

- `route_id`（route.name）、`nav_id`（meta.navId）、`nav_name`（meta.title）、`external_menu`、`tab` 等。

---

### 4. App 壳组件调用关系（全局 UI 容器）

`src/app.tsx` 是最外层容器，渲染结构与职责：

- **Notice**：`@blueking/notice-component-vue2`（非 iframe 场景渲染；api-url 指向 `.../notice/announcements/`）
- **Header**：`HeadNav`（非 iframe 且非根路径时渲染）
- **Body**：
  - `<router-view class="manage-content" />`：承载各路由页面
  - `AuthDialog`：当接口返回特定 code（如 `9900403`）会通过 store 写入 `authDialogData` 触发
  - `GlobalSettingDialog`：全局设置弹窗（脱敏灰度、我申请的、我的订阅等）

此外：

- 当 `route.query.from === 'monitor'` 时，会进入 iframe 模式（隐藏部分 header、高度变量不同）。

---

### 5. Store（Vuex）关键状态与数据流入口

`src/store/index.js`：

- **模块**：`retrieve` / `collect` / `globals`
- **全局关键 state（摘取）**
  - 空间/业务：`spaceUid`、`bkBizId`、`space`、`mySpaceList`
  - 菜单：`topMenu`、`currentMenu`、`activeManageNav/activeManageSubNav`
  - 检索：`indexId`、`indexItem`（时间范围、keyword、addition、ids/unionList 等）、`indexFieldInfo`、`indexSetQueryResult`
  - 全局配置：`globalsData`、`maskingToggle`、`globalSettingList`
  - 外部版：`isExternal`、`externalMenu`

- **关键 action（典型链路）**
  - `requestMenuList(spaceUid)` → `meta/menu`
  - `requestIndexSetFieldInfo()` → `retrieve/getLogTableHead` 或 `unionSearch/unionMapping`
  - `requestIndexSetQuery()` → axiosInstance 直发 `/search/index_set/{id}/search/` 或 `/search/index_set/union_search/`
  - `requestFavoriteList()` → `favorite/getFavoriteByGroupList`

同时 store 对 `dispatch` 做了 hack：允许第三个参数 `config` 传入，用于控制 http 行为（fromCache/cancelPrevious/catchIsShowMessage 等）。

---

### 6. HTTP/API 层设计（请求队列、缓存、取消、错误处理）

`src/api/index.js` 的核心设计点：

- **baseURL**：`window.AJAX_URL_PREFIX || '/api/v1'`
- **request interceptor**
  - 外部版自动加 `X-Bk-Space-Uid`
  - 自动生成 `Traceparent`
  - 若 store 有时区信息，追加 `X-BKLOG-TIMEZONE`
- **response interceptor**
  - Blob 场景：非 200 先读成 JSON 再走统一错误；200 直接返回 response
  - 非 Blob：统一走 `handleResponse/handleReject`
- **请求管理**
  - `RequestQueue`：记录进行中的请求（支持按 requestId cancel）
  - `CachedPromise`：按 requestId 缓存 promise（支持 fromCache / clearCache）
  - 默认 `cancelWhenRouteChange: true`，因此路由切换会统一 cancel
- **错误处理**
  - 401：弹登录框（`@blueking/login-modal`）或跳转平台登录页
  - 业务鉴权：`code === '9900403'` 写入 `authDialogData`
  - 其余：按配置 `catchIsShowMessage` 控制 bkMessage 提示

---

### 7. 路由模块详解：组件调用与数据流

#### 7.1 Retrieve（检索）模块

##### 路由与入口组件

- `GET /retrieve/:indexId?` → `@/views/retrieve-hub`（`RetrieveHub`）
  - `RetrieveHub` 会根据 `localStorage.retrieve_version` 决定渲染：
    - `v1`：`@/views/retrieve/container`
    - 默认：`v3`：`@/views/retrieve-v3/index`
- `GET /template-manage` → `@/views/retrieve-v3/search-result/template-manage/index.tsx`
- `GET /external-auth/:activeNav?` → `@/views/authorization/authorization-list`
- `GET /share/:linkId?` → `@/views/share/index.tsx`
- `GET /data_id/:id?` → `@/views/data-id-url/index.tsx`

##### Retrieve v3 的初始化数据流（核心）

`retrieve-v3` 的关键初始化逻辑集中在 `@/views/retrieve-v3/use-app-init.tsx`：

- **解析 URL → 回写 store**
  - `updateURLArgs(route)` + `getDefaultRetrieveParams(...)`
  - 识别单选/联合查询：
    - `index_id` → `ids=[index_id]`、`isUnionIndex=false`
    - `unionList` → `ids=[...]`、`isUnionIndex=true`
  - `store.commit('updateIndexItem', routeParams)`
  - `store.commit('updateSpace', spaceUid)`
  - `store.commit('updateState', { indexId })`

- **拉取索引集列表（前置依赖）**
  - `store.dispatch('retrieve/getIndexSetList', { spaceUid, bkBizId, is_group:true })`
  - 若扁平索引集列表为空，直接跳转 `/un-authorized?type=indexset`
  - 处理 tags 注入的联合索引逻辑、处理“URL/缓存索引无效时的兜底选择”

- **拉取字段信息 → 执行查询**
  - `store.dispatch('requestIndexSetFieldInfo')`
  - 成功后触发：
    - `RetrieveEvent.TREND_GRAPH_SEARCH`（趋势图）
    - `RetrieveEvent.LEFT_FIELD_INFO_UPDATE`（字段侧栏）
  - 若 `tab` 为 origin（或未传），并且 fields 存在 → `store.dispatch('requestIndexSetQuery')`

- **收藏夹与空间切换**
  - `onMounted`：`store.dispatch('requestFavoriteList')`
  - 监听 `spaceUid`：
    - 重置索引/联合索引状态
    - 重新拉取索引集列表 + 收藏夹
    - 同步修正 URL query（spaceUid/bizId + 默认查询参数）

##### 分享链接 / data_id 解析链路

- `/share/:linkId`
  - `retrieve/getShareParams?token=...`
  - 返回 `data.store`（storage/indexItem/catchFieldCustomConfig）写入 Vuex 后，`router.push(data.route)` 进入目标检索页
- `/data_id/:id`
  - `retrieve/getIndexSetDataByDataId?bk_data_id=...`
  - 解析出 `{ index_set_id, space_uid }` 后跳转到 `retrieve`，并带上 `params.indexId` 与 `query.spaceUid`

##### 检索模块主要 API（按链路）

- **空间/用户/全局（preload）**
  - `space/getMySpaceList` → `GET /meta/spaces/mine/`
  - `indexSet/getSpaceByIndexId` → `GET /index_set/:index_set_id/space/`
  - `userInfo/getUsername` →（见 `src/services/userInfo.js`，用于 userMeta）
  - `collect/globals` → `GET /meta/globals/`
  - `meta/getUserGuide` → `GET /meta/user_guide/`
- **索引集与检索**
  - `retrieve/getIndexSetList` → `GET /search/index_set/`
  - `requestIndexSetFieldInfo`：
    - 单索引：`GET /search/index_set/:index_set_id/fields/`
    - 联合：`unionSearch/unionMapping`（联合字段映射）
  - `requestIndexSetQuery`：
    - 单索引：`POST /search/index_set/:index_set_id/search/`
    - 联合：`POST /search/index_set/union_search/`
  - 衍生能力：
    - 趋势图：`POST /search/index_set/:index_set_id/aggs/date_histogram/`
    - Terms：`POST /search/index_set/:index_set_id/aggs/terms/`
    - 上下文/实时：`POST /search/index_set/:index_set_id/context/`、`POST /search/index_set/:index_set_id/tail_f/`
    - 导出：`POST /search/index_set/:index_set_id/export/`、`/quick_export/`、`/async_export/` 以及 union 版本
    - UI→querystring：`POST /search/index_set/generate_querystring/`
    - 分享：`POST /share/create_or_update_token/`、`GET share/get_share_params/`
    - data_id：`GET /index_set/query_by_dataid/`

---

#### 7.2 Manage（管理）模块

##### 路由与组件结构（概览）

`/manage` → `@/views/manage/index.vue`（管理壳，左侧导航 + 子导航 + 右侧内容）

内部主要分组（只列关键路径/页面）：

- **日志接入 / 采集**
  - `/manage/log-collection/collection-item/list` → 采集项列表
  - `/manage/log-collection/collection-item/manage/:collectorId` → 采集项详情/管理
  - `/manage/log-collection/collection-item/{add|edit|field|storage|masking|start|stop}/:collectorId?` → 接入步骤（`@/components/collection-access`）
  - `/manage/log-collection/log-index-set/list` → 索引集列表
  - `/manage/log-collection/log-index-set/{manage|edit|masking}/:indexSetId` → 索引集详情/编辑/脱敏
- **客户端日志（tgpa）**
  - `/manage/tgpa-task/list` → `@/views/manage-v2/client-log/index.tsx`
  - `/manage/tgpa-task/clean-config` → 清洗配置
- **计算平台 / 第三方 ES / 自定义上报**
  - `/manage/bk-data-collection/...`、`/manage/es-collection/...`、`/manage/custom-report/...`
- **日志清洗**
  - `/manage/clean-list/list`、`/manage/clean-templates/list`、`/manage/log-desensitize/list`
- **日志归档**
  - `/manage/archive-repository`、`/manage/archive-list`、`/manage/archive-restore`
- **日志提取**
  - `/manage/manage-log-extract`（提取配置）
  - `/manage/log-extract-task`（任务，含 `extract-home/extract-create/extract-clone`）
  - `/manage/extract-link-manage`（链路管理）
- **ES 集群 / 订阅 / 全链路追踪 / 设置**
  - `/manage/es-cluster-manage`、`/manage/report-manage`、`/manage/collection-track`、`/manage/sdk-track`、`/manage/manage-data-link-conf`

##### 管理模块壳组件的数据流

`@/views/manage/index.vue` 关键逻辑：

- 菜单来源：从 `store.state.topMenu` 中取 `manage` 的 children 作为导航数据
  - 外部版会过滤菜单（只保留“日志提取”相关）
  - 当前激活菜单通过 `route.meta.navId` 匹配得到
- 点击菜单项：`router.push({ name: id, query: { spaceUid } })`
- 监听 `spaceUid` 变化：
  - 触发 `router.replace` 保持当前“最外层子路径”不变，只刷新 query（spaceUid/bizId）
  - 通过 `refreshKey` 让 `<router-view>` 强制刷新
- 功能开关示例：`tgpa-task` 菜单是否展示由 `window.FEATURE_TOGGLE.tgpa_task` + 白名单决定

##### 管理模块主要 API（按业务域）

管理端页面覆盖面广，常见 API 域与典型接口如下（来自 `src/services/*.js`）：

- **菜单/元信息**
  - `meta/menu` → `GET /meta/menu/`（决定左侧导航与 navId）
- **采集（databus）**
  - 采集项：`/databus/collectors/`（list/create）、`/databus/collectors/:id/`（detail/update/delete）
  - 启停：`/databus/collectors/:id/start/`、`/stop/`
  - 清洗：`/databus/collectors/:id/update_or_create_clean_config/`、`/etl_preview/`、`/etl_time/`
  - 下发状态：`/databus/collectors/:id/task_status/`、`/retry/`
- **索引集（index_set）**
  - CRUD：`/index_set/`、`/index_set/:index_set_id/`
  - 收藏：`/index_set/:index_set_id/mark_favorite/`、`/cancel_favorite/`
- **日志提取（log_extract）**
  - topo：`/log_extract/strategies/topo/`（外部版常用）
- **客户端日志（tgpa）**
  - 任务：`/tgpa/task/`、`/tgpa/task/download_url/`、`/tgpa/task/index_set_id/`

---

#### 7.3 Dashboard（仪表盘）模块

路由：`/dashboard`（父容器 `@/views/dashboard/index`）

子路由：

- `/dashboard/home` → `@/views/dashboard/home`
- `/dashboard/default-dashboard` → `@/views/dashboard/old-index.vue`
- `/dashboard/create-dashboard`、`/dashboard/create-folder`、`/dashboard/import-dashboard` → 复用 `old-index.vue`（通过 meta.needBack/backName 控制返回）

仪表盘相关 API 聚合在 `src/services/dashboard.js`（此处不展开每个接口明细，实际以页面内调用为准）。

---

#### 7.4 Monitor（监控嵌入）模块

在不同构建条件（`MONITOR_APP`）下启用：

- `/monitor-apm-log/:indexId?` → `@/views/retrieve-v3/monitor/monitor.tsx`
- `/monitor-trace-log/:indexId?` → `@/views/retrieve-v3/monitor/monitor.tsx`

与检索模块的联动点：

- 若通过 `?from=monitor` 进入，`App` 会进入 iframe 模式（header 高度变量、公告/头部渲染逻辑会变化）。
- 当路由切换到 `retrieve` 时，router 会向 `window.parent` `postMessage` 同步参数，供上层监控应用接收处理。

---

### 8. API Key（http.request 的 name）如何映射到真实接口

代码中常见调用方式：

- `http.request('meta/menu', { query: ... })`
- `http.request('space/getMySpaceList', ...)`
- `http.request('retrieve/getLogTableHead', ...)`

其映射关系由 `src/services/index.js` 聚合，单个域文件（如 `src/services/meta.js`、`src/services/retrieve.ts`）声明 `{ url, method }`。

因此排查某个页面的请求路径时，建议顺序：

1. 在页面/Store 中找到 `http.request('<domain>/<apiName>')`
2. 进入 `src/services/<domain>.*` 找到对应常量，确认 `url/method`
3. 再结合 `src/api/index.js` 的默认配置（baseURL、headers、cancel/cache）理解请求行为

---


