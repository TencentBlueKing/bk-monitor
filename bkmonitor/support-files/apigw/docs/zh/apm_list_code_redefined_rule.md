# 查询 APM 返回码重定义规则

从应用视角拉取完整规则，编辑后通过 `apm_set_code_redefined_rule` 保存。内部应用态接口，调用应用需获得网关资源授权。

## 0x01 请求

```text
POST /app/apm/service/list_code_redefined_rule/
```

```json
{
  "bk_biz_id": 2,
  "app_name": "checkout"
}
```

`bk_biz_id`（`integer`）和 `app_name`（`string`）均必填，分别为 APM 应用所属业务 ID 和应用名。

## 0x02 响应

```json
{
  "result": true,
  "code": 200,
  "message": "OK",
  "data": [
    {
      "service_name": "checkout-api",
      "service_names": ["checkout-api", "order-api"],
      "kind": "caller",
      "is_global": false,
      "callee_server": "payment-api",
      "callee_service": "",
      "callee_method": "",
      "code_type_rules": {"success": "0", "exception": "3001,err_1", "timeout": "408"},
      "enabled": true,
      "updated_at": "2026-10-27T02:00:00Z"
    },
    {
      "service_name": "",
      "service_names": [],
      "kind": "callee",
      "is_global": true,
      "callee_server": "",
      "callee_service": "",
      "callee_method": "",
      "code_type_rules": {"success": "0", "exception": "3001", "timeout": "408"},
      "enabled": true,
      "updated_at": "2026-10-27T01:00:00Z"
    }
  ]
}
```

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `result` | `boolean` | 请求是否成功 |
| `code` | `integer` | 接口状态码，成功为 `200` |
| `message` | `string` | 结果说明 |
| `data[]` | `array<object>` | 完整规则列表，包含全局规则和未启用规则，按更新时间倒序排列，无配置时为 `[]` |
| `data[].kind` | `string` | `caller`（主调）或 `callee`（被调） |
| `data[].is_global` | `boolean` | `true` 表示应用内所有服务生效，`false` 表示仅指定服务生效 |
| `data[].service_names` | `array<string>` | 生效服务列表，全局规则为 `[]` |
| `data[].callee_server` | `string` | 被调服务名，空字符串表示不限，`callee` 规则固定为空 |
| `data[].callee_service` | `string` | 被调 RPC Service，空字符串表示不限 |
| `data[].callee_method` | `string` | 被调接口名，空字符串表示不限 |
| `data[].code_type_rules` | `object` | `success`、`exception`、`timeout` 对应返回码匹配字符串，多个返回码以英文逗号分隔 |
| `data[].enabled` | `boolean` | 是否启用 |
| `data[].updated_at` | `string` | 同组规则的最近更新时间，仅查询返回 |
| `data[].service_name` | `string` | 聚合前的一项服务名，仅查询返回，编辑范围使用 `service_names` |
