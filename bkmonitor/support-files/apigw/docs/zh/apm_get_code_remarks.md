### 功能描述

查询应用的完整返回码备注。

内部应用态接口，调用应用需获得网关资源授权。

### 请求参数

| 字段 | 类型 | 必选 | 描述 |
| --- | --- | --- | --- |
| `bk_biz_id` | int | 是 | APM 应用所属业务 ID |
| `app_name` | string | 是 | APM 应用名 |

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
| `result` | bool | 请求是否成功 |
| `code` | int | 接口状态码，成功为 `200` |
| `message` | string | 结果说明 |
| `data` | List[dict] | 用户保存的完整备注，不含内置备注，无配置时为 `[]` |

#### data 元素说明

| 字段 | 类型 | 描述 |
| --- | --- | --- |
| `kind` | string | `caller`（主调）或 `callee`（被调） |
| `code` | string | 原始返回码 |
| `remark` | string | 返回码说明 |
| `is_global` | bool | `true` 表示应用内所有服务生效，`false` 表示仅指定服务生效 |
| `service_names` | List[string] | 生效服务列表，全局备注为 `[]` |

### 响应参数示例

```json
{
    "result": true,
    "code": 200,
    "message": "OK",
    "data": [
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
