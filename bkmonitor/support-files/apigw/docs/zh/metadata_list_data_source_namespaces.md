### 功能描述

查询当前租户中指定 DataID 的命名空间登记记录，包含受管命名空间和通过 `apply_data_source` 注册的命名空间。调用方需要应用认证和该网关资源的权限。

### 请求参数

| 字段 | 类型 | 必选 | 描述 |
| --- | --- | --- | --- |
| bk_data_id | int | 是 | 数据源 ID，必须为正整数 |
| bk_tenant_id | string | 否 | 优先使用请求上下文的租户 ID |

### 请求示例

```http
GET /app/metadata/list_data_source_namespaces/?bk_data_id=1605502
```

### 响应示例

```json
{
  "result": true,
  "code": 200,
  "message": "OK",
  "data": [
    {"namespace": "bkmonitor", "name": "agent_event", "status": "Ok"},
    {"namespace": "shared", "name": "bkm_datasource_1605502", "status": ""}
  ]
}
```

每条记录包含命名空间 `namespace`、资源名 `name` 和 `DataIdConfig` 中保存的状态 `status`。独立命名空间的登记可能尚无状态，此时返回空字符串。同一命名空间下的不同资源分别列出，按命名空间和资源名排序。当前租户没有匹配记录时，`data` 返回空列表。
