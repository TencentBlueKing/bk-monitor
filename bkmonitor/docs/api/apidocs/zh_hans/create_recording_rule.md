### 功能描述

新建 RecordingRule V4 配置。

`POST /mcp/create_recording_rule/`

### 用户鉴权与业务权限

网关要求已验证的用户身份（`userVerifiedRequired=true`）。用户需拥有请求业务的 `manage_recording_rule_v2` 权限。用户和租户只取认证上下文，应用身份不能替代用户鉴权。

`bk_biz_id` 必填；对象查询继续限定当前租户、业务空间和未软删除状态。

### 请求参数

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| bk_biz_id | string | 是 | Business ID used for user authorization. 业务 ID，用于用户权限校验。 |
| space_uid | string | 否 | Optional space UID; must match the business. 可选空间 UID，必须与业务一致。 |
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
  "apply": false,
  "confirm": true
}
```

### 返回结果

返回结构和 `/app/recording_rule/create_config/` 相同，外层使用 `result`、`code`、`message`、`data` 标准响应。

新建、修改的 `apply` 默认 `false`；保存成功与下发成功分别返回，需检查 `execution.succeeded`。后台仍遵循 `auto_refresh`。详情的 `with_status` 默认 `false`；启用时观测错误单独返回。软删除后规则立即对 MCP 不可见，Flow 删除失败由后台重试，历史保留。

统一 MCP 可通过 `lookup_tool` 检索 `recording_rule` 分类，再通过 `execute_tool` 调用相同工具和参数。写操作沿用 MCP 约定，需要用户确认并传 `confirm=true`。

下发前检查动态 JSON 配置 `RECORD_RULE_V4_CONFIG`（默认 `{"max_sources": 20, "max_rules": 20, "max_series": 500000, "series_exempt_rule_ids": []}`）。超限返回 `execution.succeeded=false`，`execution.error` 包含实际数量和上限；声明、成功解析的快照与此前已生效的 Flow 保留，不向 BKBase 提交本次 Flow。调整上限或配置后可再次调用 `apply_config`。

下发为运行状态前逐条执行完整表达式的即时 `count(...)` 查询，统计当前输出 series 数量，默认上限 500,000（等于上限允许）。任一语句超限时整个规则组不下发，`execution.error` 包含规则、语句、实际数量、阈值及“请联系监控管理员进行评估，获得许可后再下发。”。查询超时、失败或结果不完整时同样阻止下发并提示重试；已保存声明与原运行 Flow 保留。保存和预解析不执行此查询；停止和删除跳过 series 检查，恢复运行重新检查。

管理员通过动态配置 `RECORD_RULE_V4_CONFIG.max_series` 调整阈值，设为 `0` 则全局跳过 series 查询和检查；或评估后把规则组 ID 加入 `series_exempt_rule_ids`（默认 `[]`）许可下发。豁免跳过 series 查询，不影响 source/rule 上限；配置修改后仍有效，移除 ID 撤销许可。普通请求参数不能绕过检查。配置变更沿用动态配置缓存刷新机制；获批后重新下发即可。检查仅反映下发时的数量，不保证运行期间始终低于阈值。
