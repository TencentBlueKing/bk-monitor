---
name: bklog-api-services
description: BKLog API 服务层使用指南。包含 HTTP 请求封装、服务定义、API 调用模式和错误处理。当需要调用后端 API、添加新接口或理解请求机制时使用。
---

# BKLog API 服务指南

## 架构概述

```
组件/Store
    ↓
http.request('domain/apiName', config)
    ↓
src/services/index.js (URL 映射)
    ↓
src/api/index.js (axios 封装)
    ↓
后端 API
```

## 服务定义

### 目录结构

```
src/services/
├── index.js          # 服务聚合导出
├── retrieve.ts       # 检索相关 API
├── collect.js        # 采集相关 API
├── meta.js           # 元信息 API
├── indexSet.js       # 索引集 API
├── favorite.js       # 收藏 API
├── dashboard.js      # 仪表盘 API
├── masking.js        # 脱敏 API
├── archive.js        # 归档 API
└── ...
```

### 服务定义格式

```javascript
// src/services/example.js
export const getList = {
  url: '/api/path/',
  method: 'get',
};

export const createItem = {
  url: '/api/path/',
  method: 'post',
};

// 带路径参数
export const getDetail = {
  url: '/api/path/:id/',
  method: 'get',
};

// 带查询参数模板
export const getWithQuery = {
  url: '/api/path/?page=:page&size=:size',
  method: 'get',
};
```

## API 调用方式

### 基础调用

```javascript
import http from '@/api';

// GET 请求
const result = await http.request('retrieve/getIndexSetList', {
  query: { spaceUid, bkBizId },
});

// POST 请求
const result = await http.request('retrieve/getLogTableList', {
  params: { index_set_id: indexId },
  data: { keyword, start_time, end_time },
});
```

### 路径参数替换

```javascript
// 服务定义: url: '/search/index_set/:index_set_id/fields/'
const result = await http.request('retrieve/getLogTableHead', {
  params: { index_set_id: 123 },
});
// 实际请求: GET /search/index_set/123/fields/
```

### 通过 Store 调用

```javascript
// 在组件中
const store = useStore();

// dispatch 调用
await store.dispatch('requestIndexSetQuery');

// 带配置的 dispatch（第三个参数）
await store.dispatch('requestIndexSetFieldInfo', payload, {
  fromCache: true,        // 使用缓存
  cancelPrevious: true,   // 取消之前的请求
});
```

## HTTP 层特性

### 请求配置

```javascript
http.request('api/name', {
  // 路径参数（替换 URL 中的 :param）
  params: { id: 123 },
  
  // 查询参数
  query: { page: 1, size: 10 },
  
  // 请求体
  data: { name: 'test' },
  
  // 特殊配置
  config: {
    fromCache: true,              // 使用缓存
    clearCache: true,             // 清除缓存
    cancelPrevious: true,         // 取消之前同名请求
    cancelWhenRouteChange: true,  // 路由切换时取消（默认 true）
    catchIsShowMessage: true,     // 错误时显示消息（默认 true）
  },
});
```

### 请求拦截器

自动添加的 Headers:
- `X-Bk-Space-Uid`: 空间 UID（外部版）
- `Traceparent`: 追踪链路
- `X-BKLOG-TIMEZONE`: 时区信息

### 错误处理

| 错误码 | 处理方式 |
|--------|----------|
| 401 | 弹出登录框或跳转登录页 |
| 9900403 | 触发鉴权弹窗（authDialogData） |
| 其他 | 根据 `catchIsShowMessage` 显示 bkMessage |

## 常用 API 示例

### 检索相关

```javascript
// 获取索引集列表
await http.request('retrieve/getIndexSetList', {
  query: { spaceUid, bkBizId, is_group: true },
});

// 获取字段信息
await http.request('retrieve/getLogTableHead', {
  params: { index_set_id: indexId },
});

// 执行搜索
await http.request('retrieve/getLogTableList', {
  params: { index_set_id: indexId },
  data: {
    keyword,
    start_time,
    end_time,
    addition,
    size: 50,
  },
});

// 获取趋势图
await http.request('retrieve/getLogChartList', {
  params: { index_set_id: indexId },
  data: { keyword, start_time, end_time },
});
```

### 元信息相关

```javascript
// 获取空间列表
await http.request('space/getMySpaceList');

// 获取菜单
await http.request('meta/menu', {
  query: { spaceUid },
});

// 获取全局配置
await http.request('collect/globals');
```

### 收藏相关

```javascript
// 获取收藏列表
await http.request('favorite/getFavoriteByGroupList', {
  query: { spaceUid },
});

// 创建收藏
await http.request('favorite/createFavorite', {
  data: { name, params, group_id },
});
```

## 添加新 API

1. 在对应的 `src/services/xxx.js` 文件中定义：

```javascript
export const newApiName = {
  url: '/api/path/',
  method: 'post',
};
```

2. 确保在 `src/services/index.js` 中导入并导出

3. 调用：

```javascript
await http.request('domain/newApiName', { data: {} });
```

## TypeScript 类型

```typescript
// src/services/retrieve.ts 包含类型定义示例
export interface LogSearchResult {
  total: number;
  list: LogItem[];
  done: boolean;
  trace_id: string;
  // ...
}

export type IndexSetDataList = {
  space_uid: string;
  index_set_id: number;
  // ...
}[];
```
