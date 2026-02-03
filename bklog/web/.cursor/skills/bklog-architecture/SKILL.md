---
name: bklog-architecture
description: 蓝鲸日志平台前端架构指南。提供项目整体架构、目录结构、路由系统、状态管理、数据流等核心设计说明。当需要了解项目架构、添加新模块、理解数据流或进行架构级改动时使用。
---

# BKLog 前端架构指南

## 技术栈

- **框架**: Vue 2 + TypeScript/TSX + 部分 Composition API
- **状态管理**: Vuex
- **路由**: Vue Router
- **UI 组件库**: bk-magic-vue (蓝鲸 MagicBox)
- **HTTP**: axios（封装在 `src/api/index.js`）

## 核心目录结构

```
src/
├── api/            # HTTP 请求封装（axios + 请求队列 + promise 缓存）
├── common/         # 公共工具（bkmagic.js, util.js, bus.js）
├── components/     # 公共组件
├── directives/     # 自定义指令
├── global/         # 全局组件（头部导航、空间选择等）
├── hooks/          # Vue Composition API hooks
├── mixins/         # Vue mixins
├── router/         # 路由配置
├── services/       # API 服务定义（URL + method 映射）
├── store/          # Vuex 状态管理
├── views/          # 页面视图
│   ├── retrieve-v3/   # 检索模块 V3（主要使用）
│   ├── manage/        # 管理模块
│   ├── dashboard/     # 仪表盘模块
│   └── ...
├── main.js         # 应用入口
├── app.tsx         # 根组件壳
└── preload.ts      # 预加载逻辑
```

## 应用启动流程

```
main.js 加载
    ↓
注册全局组件/mixin/plugin
    ↓
preload() 并行请求（空间列表、用户信息、全局配置、用户引导）
    ↓
getRouter() 创建路由实例
    ↓
dispatch('requestMenuList') 拉取菜单
    ↓
new Vue() 挂载应用
```

## 路由模块划分

| 模块 | 路径前缀 | 主要组件 |
|------|----------|----------|
| Retrieve | `/retrieve` | `@/views/retrieve-v3/index` |
| Manage | `/manage` | `@/views/manage/index.vue` |
| Dashboard | `/dashboard` | `@/views/dashboard/index` |
| Monitor | `/monitor-*` | `@/views/retrieve-v3/monitor/` |

## Store 模块结构

```javascript
// src/store/index.js
modules: {
  retrieve,   // 检索状态
  collect,    // 采集状态
  globals     // 全局状态
}

// 关键 state
state: {
  spaceUid,           // 空间 UID
  bkBizId,            // 业务 ID
  indexId,            // 当前索引集 ID
  indexItem,          // 检索参数
  topMenu,            // 顶部菜单
  globalsData,        // 全局配置
  userMeta            // 用户信息
}
```

## 数据流模式

### 典型的检索数据流

```
URL 参数解析
    ↓
store.commit('updateIndexItem', params)
    ↓
store.dispatch('retrieve/getIndexSetList')
    ↓
store.dispatch('requestIndexSetFieldInfo')
    ↓
store.dispatch('requestIndexSetQuery')
    ↓
组件渲染结果
```

### API 请求流程

```
组件 dispatch action
    ↓
action 调用 http.request('domain/apiName', config)
    ↓
services/index.js 查找 URL 映射
    ↓
api/index.js 发送请求（含拦截器、缓存、取消机制）
    ↓
返回数据 → commit mutation → 更新 state
```

## 路由守卫机制

- **beforeEach**: 取消 `cancelWhenRouteChange` 请求、外部版重定向、跨应用通信
- **afterEach**: 路由日志上报 `reportLogStore.reportRouteLog`

## 扩展资源

- 详细架构图: 参见 `.docs/架构图.md`
- 数据流说明: 参见 `.docs/README.md`
