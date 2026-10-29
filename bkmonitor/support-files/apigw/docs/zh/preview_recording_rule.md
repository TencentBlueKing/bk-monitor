### 功能描述

预解析 RecordingRule V4 配置。

`POST /mcp/preview_recording_rule/`

### 用户鉴权与业务权限

网关要求已验证的用户身份（`userVerifiedRequired=true`）。用户需拥有请求业务的 `view_recording_rule_v2` 权限。用户和租户只取认证上下文，应用身份不能替代用户鉴权。

`bk_biz_id` 必填；对象查询继续限定当前租户、业务空间和未软删除状态。

### 请求参数

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| bk_biz_id | string | 是 | Business ID used for user authorization. 业务 ID，用于用户权限校验。 |
| space_uid | string | 否 | Optional space UID; must match the business. 可选空间 UID，必须与业务一致。 |
| config | object/string | 是 | One AsCode group object or YAML string, without the outer groups field. 单个 AsCode group 对象或 YAML 字符串，不含外层 groups。 |
| id | integer | 否 | Active rule ID from list_recording_rules in this business. 当前业务内未软删除的规则 ID，通过 list_recording_rules 获取。 |

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
  }
}
```

### 返回结果

返回结构和 `/app/recording_rule/preview_config/` 相同，外层使用 `result`、`code`、`message`、`data` 标准响应。

新建、修改的 `apply` 默认 `false`；保存成功与下发成功分别返回，需检查 `execution.succeeded`。后台仍遵循 `auto_refresh`。详情的 `with_status` 默认 `false`；启用时观测错误单独返回。软删除后规则立即对 MCP 不可见，Flow 删除失败由后台重试，历史保留。

统一 MCP 可通过 `lookup_tool` 检索 `recording_rule` 分类，再通过 `execute_tool` 调用相同工具和参数。写操作沿用 MCP 约定，需要用户确认并传 `confirm=true`。

预解析还返回 `data.deployment_check`。解析成功与可下发分别判定；超限时保留 `config` 和 `records`，并返回 `can_apply=false`，不写库或下发：

```json
{
  "can_apply": false,
  "source_count": 21,
  "max_sources": 20,
  "rule_count": 1,
  "max_rules": 20,
  "errors": [{
    "code": "SOURCE_LIMIT_EXCEEDED",
    "message": "Flow source 数量 21 超过上限 20（max_sources）",
    "path": "config.rules",
    "actual": 21,
    "limit": 20
  }]
}
```

上限读取动态 JSON 配置 `RECORD_RULE_V4_CONFIG`，默认 `{"max_sources": 20, "max_rules": 20}`。source 按整个 group 的来源 ResultTable namespace/name 去重，rules 按 group 下规则条数计数。修改动态配置后，下发会按当前生效值重新判断，预解析通过不代表后续下发一定通过。

### 预解析错误协议

已通过网关与基础参数校验后的预解析业务错误，API、独立 MCP 和 Unified MCP 使用相同的错误条目。每条包含 `code`（稳定错误码）、`message`（原因）和 `path`（配置位置）；部署超限额外包含整数 `actual` 和 `limit`。调用方应按错误码判断，不依赖错误文字。

| 错误码 | 含义 | path | 结果与处理 |
|---|---|---|---|
| INVALID_CONFIG | YAML、group 或规则配置不合法；编辑时修改规则组名称 | config 或 config.name | result=false，修正配置后重试 |
| INVALID_SPACE | 业务/空间不匹配，或当前租户下空间不存在 | bk_biz_id 或 space_uid | result=false，修正业务/空间入参 |
| RULE_NOT_FOUND | 编辑预解析 ID 不属于当前租户/空间，或规则已软删除 | id | result=false，查询有效 ID |
| RESOLVE_FAILED | 表达式检查、MetricQL 解析、VMRT 或来源资源映射失败 | config.rules[index] | result=false，按 message 修正查询/来源或排查依赖服务 |
| SOURCE_LIMIT_EXCEEDED | 去重后的来源数量超过 max_sources | config.rules | HTTP 200，解析结果保留，deployment_check.can_apply=false |
| RULE_LIMIT_EXCEEDED | group 下规则条数超过 max_rules | config.rules | HTTP 200，解析结果保留，deployment_check.can_apply=false |

前四类失败沿用后台 API 的 HTTP 200 错误信封：`result=false`、外层 `code=3300004`，业务错误位于 `data.errors`。示例列出关键字段：

```json
{
  "result": false,
  "code": 3300004,
  "message": "config.rules[0]: query unavailable",
  "data": {
    "errors": [{
      "code": "RESOLVE_FAILED",
      "message": "query unavailable",
      "path": "config.rules[0]"
    }]
  }
}
```

后两类超限属于部署判定，错误位于 `data.deployment_check.errors`，可同时返回两条。解析成功时调用方还需检查 `deployment_check.can_apply`；超限配置仍允许保存，但真实下发会再次检查并拒绝超限 Flow。

Unified MCP 的 `execute_tool` 成功信封多一层工具结果，部署判定位于 `data.data.deployment_check`；业务预解析失败仍使用上述 `data.errors` 错误信封。网关鉴权、基础字段缺失/类型错误及 Unified MCP 自身的 Schema 校验错误继续使用平台通用协议。
