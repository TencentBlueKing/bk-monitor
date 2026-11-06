### 功能描述

修改 RecordingRule 配置

`POST /app/recording_rule/update_config/`

完整替换指定规则组的可编辑配置，名称和空间不可修改。返回 data.saved=true、data.rule、data.config、data.execution。apply 默认 false；传 true 时立即解析下发。

下发失败保留新声明，execution.succeeded=false 并携带 error，可再次调用 apply_config。apply 不改变后台 auto_refresh 的设置。

### 请求参数

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| bk_biz_id | integer | 否 | 业务 ID，与 space_uid 至少提供一个 |
| space_uid | string | 否 | 空间 UID，与 bk_biz_id 至少提供一个 |
| id | integer | 是 | 规则组 ID，必须属于当前租户及指定空间且未软删除 |
| config | object/string | 是 | AsCode 单 group 对象或 YAML 字符串，不含外层 groups |
| apply | boolean | 否 | 是否立即解析下发，不改变 auto_refresh；默认 false |

bk_biz_id 与 space_uid 至少提供一个。租户取认证上下文，配置内容中不填写租户或空间字段。ID 必须属于当前租户、指定空间且未软删除。

### 请求示例

```json
{
  "bk_biz_id": 2,
  "id": 12,
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
  },
  "apply": true
}
```

### 返回结果

沿用网关标准的 result、code、message、data 响应结构。请求处理成功不等于下发成功；有 execution 的接口需同时检查 execution.succeeded。

下发前检查动态 JSON 配置 `RECORD_RULE_V4_CONFIG`（默认 `{"max_sources": 20, "max_rules": 20}`）。超限返回 `execution.succeeded=false`，`execution.error` 包含实际数量和上限；声明、成功解析的快照与此前已生效的 Flow 保留，不向 BKBase 提交本次 Flow。调整上限或配置后可再次调用 `apply_config`。
