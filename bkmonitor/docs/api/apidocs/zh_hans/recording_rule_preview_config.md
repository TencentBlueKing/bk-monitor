### 功能描述

预解析 RecordingRule 配置

`POST /app/recording_rule/preview_config/`

调用查询服务解析 MetricQL、来源 VMRT 和 BKBase 来源资源信息。不会写入规则、版本、事件、输出资源或下发 Flow。编辑预览可传 id，以排除已有规则自身的输出；名称不可修改。

返回 data.config（规范化单 group）和 data.records。每条结果包含 record、metricql、labels、interval、src_vm_table_ids、src_result_table_configs。解析失败会定位到 config.rules[index]。

### 请求参数

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| bk_biz_id | integer | 否 | 业务 ID，与 space_uid 至少提供一个 |
| space_uid | string | 否 | 空间 UID，与 bk_biz_id 至少提供一个 |
| config | object/string | 是 | AsCode 单 group 对象或 YAML 字符串，不含外层 groups |
| id | integer | 否 | 规则组 ID，必须属于当前租户及指定空间且未软删除 |

bk_biz_id 与 space_uid 至少提供一个。租户取认证上下文，配置内容中不填写租户或空间字段。ID 必须属于当前租户、指定空间且未软删除。

### 请求示例

```json
{
  "bk_biz_id": 2,
  "config": {
    "name": "cpu_summary",
    "interval": "1min",
    "labels": {
      "env": "prod"
    },
    "bkmonitor": {
      "description": "CPU 平均使用率",
      "auto_refresh": false,
      "desired_status": "running"
    },
    "rules": [
      {
        "record": "cpu_usage_avg",
        "expr": "avg(system_cpu_usage)"
      }
    ]
  }
}
```

### 返回结果

沿用网关标准的 result、code、message、data 响应结构。请求处理成功不等于下发成功；有 execution 的接口需同时检查 execution.succeeded。

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
