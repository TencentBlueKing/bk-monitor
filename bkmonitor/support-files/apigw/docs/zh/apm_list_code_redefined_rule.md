### 功能描述

从应用视角拉取完整返回码重定义规则，编辑后通过 `apm_set_code_redefined_rule` 保存。

内部应用态接口，调用应用需获得网关资源授权。

### 请求参数

| 字段 | 类型 | 必选 | 描述 |
| --- | --- | --- | --- |
| bk_biz_id | int | 是 | APM 应用所属业务 ID |
| app_name | string | 是 | APM 应用名 |

### 请求参数示例

```json
{
    "bk_biz_id": 2,
    "app_name": "checkout"
}
```

### 响应参数

| 字段 | 类型 | 描述 |
| --- | --- | --- |
| result | bool | 请求是否成功 |
| code | int | 返回的状态码，成功为 `200` |
| message | string | 结果说明 |
| data | List[dict] | 应用完整配置列表，无配置时为 `[]` |

#### data 字段说明（每个元素为一项配置）

| 字段 | 类型 | 描述 |
| --- | --- | --- |
| kind | string | `caller`（主调）或 `callee`（被调） |
| is_global | bool | `true` 表示应用内所有服务生效，`false` 表示仅指定服务生效 |
| service_names | List[string] | 生效服务列表，全局规则为 `[]` |
| callee_server | string | 被调服务名，空字符串表示不限，`callee` 规则固定为空 |
| callee_service | string | 被调 RPC Service，空字符串表示不限 |
| callee_method | string | 被调接口名，空字符串表示不限 |
| code_type_rules | dict | `success`、`exception`、`timeout` 对应返回码匹配字符串，多个返回码以英文逗号分隔 |
| enabled | bool | 是否启用 |
| updated_at | string | 同组规则的最近更新时间，仅查询返回 |
| service_name | string | 聚合前的一项服务名，仅查询返回，编辑范围使用 `service_names` |

### 响应参数示例

```json
{
    "result": true,
    "code": 200,
    "message": "OK",
    "data": [
        {
            "service_name": "checkout-api",
            "service_names": [
                "checkout-api",
                "order-api"
            ],
            "kind": "caller",
            "is_global": false,
            "callee_server": "payment-api",
            "callee_service": "",
            "callee_method": "",
            "code_type_rules": {
                "success": "0",
                "exception": "3001,err_1",
                "timeout": "408"
            },
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
            "code_type_rules": {
                "success": "0",
                "exception": "3001",
                "timeout": "408"
            },
            "enabled": true,
            "updated_at": "2026-10-27T01:00:00Z"
        }
    ]
}
```

### 使用说明

1. 返回列表包含全局规则和未启用规则，按更新时间倒序排列。
