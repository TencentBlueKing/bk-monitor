### 功能描述

修改 RecordingRule V4 配置。

`POST /mcp/update_recording_rule/`

### 用户鉴权与业务权限

网关要求已验证的用户身份（`userVerifiedRequired=true`）。用户需拥有请求业务的 `manage_recording_rule_v2` 权限。用户和租户只取认证上下文，应用身份不能替代用户鉴权。

`bk_biz_id` 必填；对象查询继续限定当前租户、业务空间和未软删除状态。

### 请求参数

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| bk_biz_id | string | 是 | Business ID used for user authorization. 业务 ID，用于用户权限校验。 |
| space_uid | string | 否 | Optional space UID; must match the business. 可选空间 UID，必须与业务一致。 |
| id | integer | 是 | Active rule ID from list_recording_rules in this business. 当前业务内未软删除的规则 ID，通过 list_recording_rules 获取。 |
| config | object/string | 是 | One AsCode group object or YAML string, without the outer groups field. 单个 AsCode group 对象或 YAML 字符串，不含外层 groups。 |
| apply | boolean | 否 | Resolve and apply immediately; defaults to false and does not change auto_refresh. 是否立即解析下发，默认 false，不改变 auto_refresh。 |
| confirm | boolean | 是 | Must be true after explicit user confirmation. 用户明确确认后必须传 true。 |

### 请求示例

```json
{
  "bk_biz_id": "2",
  "config": {
    "name": "cpu_summary",
    "interval": "1min",
    "bkmonitor": {
      "auto_refresh": false
    },
    "rules": [
      {
        "record": "cpu_avg",
        "expr": "avg(system_cpu_usage)"
      }
    ]
  },
  "id": 42,
  "apply": false,
  "confirm": true
}
```

### 返回结果

返回结构和 `/app/recording_rule/update_config/` 相同，外层使用 `result`、`code`、`message`、`data` 标准响应。

新建、修改的 `apply` 默认 `false`；保存成功与下发成功分别返回，需检查 `execution.succeeded`。后台仍遵循 `auto_refresh`。详情的 `with_status` 默认 `false`；启用时观测错误单独返回。软删除后规则立即对 MCP 不可见，Flow 删除失败由后台重试，历史保留。

统一 MCP 可通过 `lookup_tool` 检索 `recording_rule` 分类，再通过 `execute_tool` 调用相同工具和参数。写操作沿用 MCP 约定，需要用户确认并传 `confirm=true`。

下发前检查动态 JSON 配置 `RECORD_RULE_V4_CONFIG`（默认 `{"max_sources": 20, "max_rules": 20}`）。超限返回 `execution.succeeded=false`，`execution.error` 包含实际数量和上限；声明、成功解析的快照与此前已生效的 Flow 保留，不向 BKBase 提交本次 Flow。调整上限或配置后可再次调用 `apply_config`。
