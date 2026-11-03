### 功能描述

全量保存应用的返回码备注，支持指定服务列表或全局生效。

内部应用态接口，调用应用需获得网关资源授权。

### 请求参数

| 字段 | 类型 | 必选 | 描述 |
| --- | --- | --- | --- |
| `bk_biz_id` | int | 是 | APM 应用所属业务 ID |
| `app_name` | string | 是 | APM 应用名 |
| `remarks` | List[dict] | 是 | 应用完整备注列表，未提交的备注会被删除，`[]` 清空全部用户备注 |

#### remarks 元素说明

| 字段 | 类型 | 必选 | 描述 |
| --- | --- | --- | --- |
| `kind` | string | 是 | `caller`（主调）或 `callee`（被调） |
| `code` | string | 是 | 非空原始返回码 |
| `remark` | string | 否 | 默认 `""`，为空时不保存该项 |
| `is_global` | bool | 否 | 默认 `false`，为 `true` 时应用内所有服务生效 |
| `service_names` | List[string] | 条件必选 | `is_global=false` 时必填且非空，全局备注传 `[]` 或不传 |

- *[1] 同一服务内的 `(kind, code)` 组合不得重复，全局备注单独校验。*
- *[2] 备注按服务级 > 全局 > 内置 tRPC 的顺序匹配。*
- *[3] 清空用户备注后仍保留内置备注。*

### 请求参数示例

```json
{
    "bk_biz_id": 2,
    "app_name": "checkout",
    "remarks": [
        {
            "kind": "caller",
            "code": "3001",
            "remark": "库存不足",
            "is_global": false,
            "service_names": [
                "checkout-api",
                "order-api"
            ]
        },
        {
            "kind": "callee",
            "code": "408",
            "remark": "请求超时",
            "is_global": true,
            "service_names": []
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

1. 调用 `apm_get_code_remarks`，获取完整的 `data` 列表。
2. 编辑列表中的备注，删除时移除对应项。
3. 将完整列表作为 `remarks` 提交，顶层仅传 `bk_biz_id`、`app_name` 和 `remarks`。
