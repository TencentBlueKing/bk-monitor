### 功能描述

全量保存应用的返回码重定义规则，并向 APM 同步下发生效配置。

内部应用态接口，调用应用需获得网关资源授权。

### 请求参数

| 字段 | 类型 | 必选 | 描述 |
| --- | --- | --- | --- |
| `bk_biz_id` | int | 是 | APM 应用所属业务 ID |
| `app_name` | string | 是 | APM 应用名 |
| `rules` | List[dict] | 是 | 应用完整规则列表，未提交的规则会被删除，`[]` 清空全部规则 |

#### rules 元素说明

| 字段 | 类型 | 必选 | 描述 |
| --- | --- | --- | --- |
| `kind` | string | 是 | `caller`（主调）或 `callee`（被调） |
| `is_global` | bool | 否 | 默认 `false`，为 `true` 时应用内所有服务生效 |
| `service_names` | List[string] | 条件必选 | `is_global=false` 时必填且非空，全局规则传 `[]` |
| `callee_server` | string | 是 | 被调服务名，空字符串表示不限，`callee` 规则会被置空 |
| `callee_service` | string | 是 | 被调 RPC Service，空字符串表示不限 |
| `callee_method` | string | 是 | 被调接口名，空字符串表示不限 |
| `code_type_rules` | dict | 是 | `success`、`exception`、`timeout` 对应返回码匹配字符串，多个返回码以英文逗号分隔 |
| `enabled` | bool | 否 | 默认 `true`，禁用规则仍保存，但不下发 |

- *[1] 同一作用域和服务内，`(kind, callee_server, callee_service, callee_method)` 组合不得重复。*
- *[2] 服务级规则优先于全局规则。*
- *[3] 保存成功不表示采集端配置立即生效。*

### 请求参数示例

```json
{
    "bk_biz_id": 2,
    "app_name": "checkout",
    "rules": [
        {
            "kind": "caller",
            "is_global": false,
            "service_names": [
                "checkout-api",
                "order-api"
            ],
            "callee_server": "payment-api",
            "callee_service": "",
            "callee_method": "",
            "code_type_rules": {
                "success": "0",
                "exception": "3001,err_1",
                "timeout": "408"
            },
            "enabled": true
        },
        {
            "kind": "callee",
            "is_global": true,
            "service_names": [],
            "callee_server": "",
            "callee_service": "",
            "callee_method": "",
            "code_type_rules": {
                "success": "0",
                "exception": "3001",
                "timeout": "408"
            },
            "enabled": true
        }
    ]
}
```

### 响应参数

| 字段 | 类型 | 描述 |
| --- | --- | --- |
| `result` | bool | 请求是否成功 |
| `code` | int | 接口状态码，成功为 `200` |
| `message` | string | 结果说明 |
| `data` | dict | 成功时为 `{}` |

### 响应参数示例

```json
{
    "result": true,
    "code": 200,
    "message": "OK",
    "data": {}
}
```

### 使用说明

1. 调用 `apm_list_code_redefined_rule`，获取完整的 `data` 列表。
2. 编辑列表中的规则，删除时移除对应项。
3. 将完整列表作为 `rules` 提交，顶层仅传 `bk_biz_id`、`app_name` 和 `rules`。
