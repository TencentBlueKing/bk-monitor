### 功能描述

从应用视角覆盖完整返回码重定义规则，并向 APM 下发生效配置。先通过 `apm_list_code_redefined_rule` 拉取完整列表，编辑后将列表放入 `rules` 保存。

内部应用态接口，调用应用需获得网关资源授权。

### 请求参数

| 字段 | 类型 | 必选 | 描述 |
| --- | --- | --- | --- |
| bk_biz_id | int | 是 | APM 应用所属业务 ID |
| app_name | string | 是 | APM 应用名 |
| rules | List[dict] | 是 | 应用完整规则列表，`[]` 清空全部规则 |

#### rules 元素说明

| 字段 | 类型 | 必选 | 描述 |
| --- | --- | --- | --- |
| kind | string | 是 | `caller`（主调）或 `callee`（被调） |
| is_global | bool | 否 | 默认 `false`，为 `true` 时应用内所有服务生效 |
| service_names | List[string] | 条件必选 | 非全局规则必选且非空，全局规则传 `[]` |
| callee_server | string | 是 | 被调服务名，空字符串表示不限，`callee` 规则会被置空 |
| callee_service | string | 是 | 被调 RPC Service，空字符串表示不限 |
| callee_method | string | 是 | 被调接口名，空字符串表示不限 |
| code_type_rules | dict | 是 | `success`、`exception`、`timeout` 对应返回码匹配字符串，多个返回码以英文逗号分隔 |
| enabled | bool | 否 | 默认 `true`，禁用规则仍保存，但不下发 |

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
| result | bool | 请求是否成功 |
| code | int | 返回的状态码，成功为 `200` |
| message | string | 结果说明 |
| data | dict | 成功时为 `{}` |

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

1. 请求顶层只传示例中的字段，调用方向和生效范围均在每条规则内设置。

2. 接口全量覆盖应用配置，未出现在 `rules` 中的存量规则会被删除，包括全局规则；删除单条规则时，从完整列表中移除该项后保存。

3. 同一作用域、服务、调用方向和三个 `callee_*` 维度的组合不得重复，服务规则优先于全局规则。

4. 规则保存后同步下发，接口不等待采集端配置生效。
