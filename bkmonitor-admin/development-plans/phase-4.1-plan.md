# 4.1 期开发计划

## 概述

4.1 期聚焦于 bkmonitor-admin 的体验优化，包括存储集群详情的 ClusterConfig 展示优化、查询路由历史记录、以及筛选条件调整。

## 任务列表

### 1. 存储集群详情 - ClusterConfig 表格化展示 + 实时获取 component_config

**当前状态：**

- 存储集群详情页的 ClusterConfig 按 namespace 分组，以折叠面板展示
- 每个 config 仅显示 namespace 名称，需要展开才能看到 kind/name 等字段
- component_config 在集群详情接口中一次性返回，可能为 null（获取失败）

**目标：**

- 将 ClusterConfig 改为 DataTable 表格展示，列出主要字段（namespace, kind, name, created_at, updated_at）
- 每行增加"获取配置"按钮，实时调用 API 获取该条记录的 component_config
- 获取到的配置以 JSON 文本框形式展示（支持查看/折叠）

**涉及文件：**

- `src/features/cluster-info/ClusterInfoDetailPage.tsx`
- `src/features/cluster-info/api.ts`
- `src/features/cluster-info/schemas.ts`
- `src/features/cluster-info/queries.ts`
- `src/features/kernel-rpc/operations.ts`

**技术要点：**

- 新增 `cluster_info.component_config` operation
- 点击按钮时触发 API 请求，结果在行内或弹窗中以 `<textarea>` 显示 JSON

---

### 2. 查询路由 - 历史查询记录

**当前状态：**

- 查询条件仅保存在 URL search params 中，刷新或切换页面后丢失
- 同样的查询需要反复手动输入

**目标：**

- 支持按环境 + 租户区分的查询历史记录
- 记录保存在浏览器 localStorage 中
- 保留最近 N 次（默认 5 次）查询记录
- 提供下拉选择或列表，方便快速回填查询条件

**涉及文件：**

- `src/features/query-route/QueryRoutePage.tsx`
- `src/features/query-route/utils.ts`（新增历史记录工具函数）

**技术要点：**

- localStorage key 格式：`qr_history_{environment_id}_{tenant_id}`
- 存储结构：`QueryRouteDraft` 数组，最新的在前
- 去重：相同查询条件不重复记录

---

### 3. 筛选条件调整 - ClusterInfoListPage

**当前状态：**

- `is_default_cluster` 是高级筛选条件（`advanced: true`），需要点击展开才能使用

**目标：**

- 将 `is_default_cluster` 改为基础筛选条件（`advanced: false` 或移除 `advanced` 字段）

**涉及文件：**

- `src/features/cluster-info/ClusterInfoListPage.tsx`

---

### 4. 筛选条件调整 - ResultTableListPage

**当前状态：**

- `is_enable` 和 `is_deleted` 是高级筛选条件（`advanced: true`）
- `is_deleted` 没有默认值

**目标：**

- 将 `is_enable` 和 `is_deleted` 改为基础筛选条件
- `is_deleted` 默认选中 `false`，即默认只显示未删除的 ResultTable

**涉及文件：**

- `src/features/result-table/ResultTableListPage.tsx`

**技术要点：**

- 设置 `isDeleted` 的 draft 初始值为 `'false'`
- 修改 `FILTER_FIELDS` 移除 `advanced: true`

---

## 验证要求

1. `pnpm format:check` - 格式检查
2. `pnpm lint` - 代码规范检查
3. `pnpm typecheck` - 类型检查
4. 关键页面手动验证：
   - 存储集群详情页 ClusterConfig 表格及 component_config 实时获取
   - 查询路由历史记录存取和回填
   - ClusterInfo 默认集群筛选在基础区域可见
   - ResultTable 启用/删除筛选在基础区域可见，默认筛选 is_deleted=false
