# Kernel RPC 与数据接口设计

## 现有协议

bkmonitor 后端已有 `kernel_api/rpc` 通用入口，请求体保持很小：

```json
{
  "func_name": "metadata_related_info",
  "params": {
    "bk_data_id": 50010,
    "bk_tenant_id": "system"
  }
}
```

返回体包含：

```json
{
  "func_name": "metadata_related_info",
  "protocol": "call",
  "result": {}
}
```

元信息协议：

```json
{
  "func_name": "__meta__",
  "params": {
    "action": "list"
  }
}
```

```json
{
  "func_name": "__meta__",
  "params": {
    "action": "detail",
    "target_func_name": "metadata_related_info"
  }
}
```

## 设计目标

一期页面虽然只做传统 admin 展示，但 API 需要天然适合 AI Agent 后续调用：

- 操作名稳定。
- 入参和出参有机器可读 schema。
- 有示例参数和响应示例。
- 有安全级别。
- 有稳定错误结构。
- 有 trace 信息，便于排障和审计。
- 有环境上下文，便于管理多套 bkmonitor 平台。

## RPC Client 与 BFF

浏览器不直接请求 bkmonitor APIGW，也不在资源查询请求中携带 `app_code` / `secret_key`。前端只暴露一个基础 client，并统一调用本地 Admin API：

```ts
kernelRpc.call<T>(options: {
  environment: AdminEnvironment;
  operation: AdminOperation;
  params: Record<string, unknown>;
}): Promise<T>
```

前端请求体发送到 `/admin-api/kernel-rpc/call`：

```json
{
  "environment_id": "prod-main",
  "operation": "datasource.detail",
  "params": {
    "bk_tenant_id": "system",
    "bk_data_id": 50010
  }
}
```

Admin API/BFF 根据 `environment_id` 从配置库读取 APIGW 地址、`app_code`、`secret_key` 和 Kernel RPC path，再由后台请求目标 bkmonitor。请求 APIGW 时使用 `X-Bkapi-Authorization`：

```text
X-Bkapi-Authorization: {"bk_app_code":"...","bk_app_secret":"..."}
X-Bk-Tenant-Id: system
```

这里的 `X-Bk-Tenant-Id` 是应用调用 APIGW 的租户，管理端固定使用默认租户 `system`。资源查询租户只作为 RPC body 中的 `params.bk_tenant_id` 传递。

在基础 client 之上再封装资源服务：

```ts
datasourceApi.list(params)
datasourceApi.detail(bkDataId, bkTenantId)
resultTableApi.list(params)
resultTableApi.detail(tableId, bkTenantId)
resultTableApi.fields(params)
```

页面不直接调用 `kernelRpc.call`，除非是未来的调试控制台。

## Agent-facing Operation

后续建议不要把 `kernel_rpc` 的 Python 函数名直接暴露为唯一抽象，而是在 admin 项目中维护一层稳定 operation：

```json
{
  "name": "datasource.detail",
  "title": "查询 DataSource 详情",
  "description": "根据 bk_data_id 和 bk_tenant_id 查询数据源及其关联信息",
  "safety_level": "read",
  "input_schema": {},
  "output_schema": {},
  "examples": []
}
```

operation 可以映射到后端 `kernel_rpc.func_name`，但前端、文档和未来 Agent 优先面向 operation。

所有 operation 必须绑定环境上下文：

```json
{
  "environment_id": "prod-main",
  "operation": "datasource.detail",
  "params": {
    "bk_tenant_id": "system",
    "bk_data_id": 50010
  }
}
```

## 统一响应 envelope

建议新增 admin 专用只读 RPC 时使用稳定 envelope：

```json
{
  "data": {},
  "trace_id": "00-...",
  "warnings": [],
  "meta": {
    "environment_id": "prod-main",
    "operation": "datasource.detail",
    "safety_level": "read"
  }
}
```

错误结构：

```json
{
  "code": "RESOURCE_NOT_FOUND",
  "message": "未找到匹配资源",
  "details": {},
  "trace_id": "00-..."
}
```

## 一期需要后端补充的 RPC

现有 `metadata_related_info` 更适合关联详情排查，不适合作为 admin 列表接口。为了支撑一期页面，建议补充只读 RPC：

详细函数规划见 [后端 Admin RPC 函数规划](./backend-admin-rpc.md)。后端实现位置建议为 `kernel_api/rpc/functions/admin/`。

### admin.tenant.list

用途：租户列表检索，用于顶部当前租户 ID 切换。

Agent operation：`tenant.list`

Safety level：`read`

返回：

- 分页信息
- 租户 ID、名称、来源
- DataSource / ResultTable 数量摘要

### admin.datasource.list

用途：DataSource 列表检索。

Agent operation：`datasource.list`

Safety level：`read`

核心过滤：

- `bk_tenant_id`
- `bk_data_id`
- `data_name`
- `created_from`
- `source_label`
- `type_label`
- `is_enable`
- `is_platform_data_id`
- `space_uid`
- `table_id`

返回：

- 分页信息
- DataSource 轻量字段
- 关联 ResultTable 数量
- SpaceDataSource 数量
- DataSourceOption 数量

### admin.datasource.detail

用途：DataSource 详情。

Agent operation：`datasource.detail`

Safety level：`read`

入参：

- `bk_tenant_id`
- `bk_data_id`

返回：

- DataSource 全量展示字段
- DataSourceOption
- SpaceDataSource
- DataSourceResultTable
- DataIdConfig
- 关联 ResultTable 摘要

### admin.result_table.list

用途：ResultTable 列表检索。

Agent operation：`result_table.list`

Safety level：`read`

核心过滤：

- `bk_tenant_id`
- `table_id`
- `table_name_zh`
- `bk_biz_id`
- `data_label`
- `label`
- `schema_type`
- `default_storage`
- `is_enable`
- `is_deleted`
- `is_builtin`
- `bk_data_id`

返回：

- 分页信息
- ResultTable 轻量字段
- 字段数量
- 关联 DataSource 数量
- ESStorage / AccessVMRecord / 自定义分组摘要状态

### admin.result_table.detail

用途：ResultTable 详情。

Agent operation：`result_table.detail`

Safety level：`read`

入参：

- `bk_tenant_id`
- `table_id`

返回：

- ResultTable 全量展示字段
- ResultTableOption
- DataSourceResultTable 与 DataSource 摘要
- TimeSeriesGroup / EventGroup / LogGroup
- ESStorage
- AccessVMRecord
- 关联诊断入口提示

### admin.result_table.field_list

用途：字段独立分页查询。

Agent operation：`result_table.field_list`

Safety level：`read`

核心过滤：

- `bk_tenant_id`
- `table_id`
- `field_name`
- `field_type`
- `tag`
- `is_config_by_user`
- `is_disabled`
- `has_option`

返回：

- 分页字段列表
- 可选的 FieldOption 摘要

## 接口设计约束

- 列表接口必须分页，默认 page size 不超过 50。
- 详情接口可以按 tab 懒加载，避免一次性拉取大量字段。
- ResultTableField 必须独立分页，禁止作为 ResultTable 列表字段直接返回。
- 列表过滤尽量使用已有索引字段，不为模糊查询牺牲后端数据查询稳定性。
- 多租户模式下，所有接口都要显式返回 effective `bk_tenant_id`。
- 多环境模式下，所有接口调用和响应 meta 都要显式携带 `environment_id`。
- 每个接口必须提供 input schema、output schema、examples 和 safety level。
- 高成本查询需要返回 warning，不能静默执行超大范围扫描。
