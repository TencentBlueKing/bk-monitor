### 功能描述

分页列表 RecordingRule V4 配置。

`POST /mcp/list_recording_rules/`

### 用户鉴权与业务权限

网关要求已验证的用户身份（`userVerifiedRequired=true`）。用户需拥有请求业务的 `view_recording_rule_v2` 权限。用户和租户只取认证上下文，应用身份不能替代用户鉴权。

`bk_biz_id` 必填；对象查询继续限定当前租户、业务空间和未软删除状态。

### 请求参数

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| bk_biz_id | string | 是 | Business ID used for user authorization. 业务 ID，用于用户权限校验。 |
| space_uid | string | 否 | Optional space UID; must match the business. 可选空间 UID，必须与业务一致。 |
| name | string | 否 | Filter by part of the group name. 按规则组名称模糊筛选。 |
| app | string | 否 | Filter by the owning AsCode app. 按托管的 AsCode app 筛选。 |
| status | string | 否 | Filter by local rule status. 按规则本地状态筛选。 |
| page | integer | 否 | Page number, starting at 1. 页码，从 1 开始。 |
| page_size | integer | 否 | Page size, up to 100. 每页数量，最多 100。 |

### 请求示例

```json
{
  "bk_biz_id": "2"
}
```

### 返回结果

返回结构和 `/app/recording_rule/list_configs/` 相同，外层使用 `result`、`code`、`message`、`data` 标准响应。

新建、修改的 `apply` 默认 `false`；保存成功与下发成功分别返回，需检查 `execution.succeeded`。后台仍遵循 `auto_refresh`。详情的 `with_status` 默认 `false`；启用时观测错误单独返回。软删除后规则立即对 MCP 不可见，Flow 删除失败由后台重试，历史保留。

统一 MCP 可通过 `lookup_tool` 检索 `recording_rule` 分类，再通过 `execute_tool` 调用相同工具和参数。写操作沿用 MCP 约定，需要用户确认并传 `confirm=true`。
