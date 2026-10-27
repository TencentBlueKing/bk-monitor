### 功能描述

从应用视角覆盖完整返回码备注。先通过 `apm_get_code_remarks` 拉取完整列表，编辑后将列表放入 `remarks` 保存。

内部应用态接口，调用应用需获得网关资源授权。

### 请求参数

| 字段 | 类型 | 必选 | 描述 |
| --- | --- | --- | --- |
| bk_biz_id | int | 是 | APM 应用所属业务 ID |
| app_name | string | 是 | APM 应用名 |
| remarks | List[dict] | 是 | 应用完整备注列表，`[]` 清空全部用户备注 |

#### remarks 元素说明

| 字段 | 类型 | 必选 | 描述 |
| --- | --- | --- | --- |
| kind | string | 是 | `caller`（主调）或 `callee`（被调） |
| code | string | 是 | 非空原始返回码 |
| remark | string | 否 | 默认 `""`，空字符串不保留为配置 |
| is_global | bool | 否 | 默认 `false`，为 `true` 时应用内所有服务生效 |
| service_names | List[string] | 条件必选 | 非全局备注必选且非空，全局备注必须为空或不传 |

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

1. 请求顶层只传示例中的字段，调用方向和生效范围均在每条备注内设置。

2. 接口全量覆盖应用配置，未提交的存量备注会被删除；删除单条备注时，从完整列表中移除该项后保存。

3. 同一服务、调用方向和返回码不得重复，全局备注按独立作用域校验。

4. 展示时同一返回码的优先级为服务备注 > 全局备注 > 内置 tRPC 备注，清空用户备注后仍可回退到内置备注。
