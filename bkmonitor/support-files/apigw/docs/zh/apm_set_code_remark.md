# 设置 APM 返回码备注

从应用视角覆盖完整备注。先通过 `apm_get_code_remarks` 拉取完整列表，编辑后将列表放入 `remarks` 保存。

内部应用态接口，调用应用需获得网关资源授权。

## 0x01 请求

```text
POST /app/apm/service/set_code_remark/
```

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
      "service_names": ["checkout-api", "order-api"]
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

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `bk_biz_id` | `integer` | 是 | APM 应用所属业务 ID |
| `app_name` | `string` | 是 | APM 应用名 |
| `remarks[]` | `array<object>` | 是 | 应用完整备注列表，`[]` 清空全部用户备注 |
| `remarks[].kind` | `string` | 是 | `caller`（主调）或 `callee`（被调） |
| `remarks[].code` | `string` | 是 | 非空原始返回码 |
| `remarks[].remark` | `string` | 否 | 默认 `""`，空字符串不保留为配置 |
| `remarks[].is_global` | `boolean` | 否 | 默认 `false`，为 `true` 时应用内所有服务生效 |
| `remarks[].service_names` | `array<string>` | 条件必填 | 非全局备注必填且非空，全局备注必须为空或不传 |

- *[1] 请求顶层只传示例中的字段，调用方向和生效范围均在每条备注内设置。*
- *[2] 未提交的存量备注会被删除；删除单条备注时，从完整列表中移除该项后保存。*
- *[3] 同一服务、调用方向和返回码不得重复，全局备注按独立作用域校验。*
- *[4] 展示时同一返回码的优先级为服务备注 > 全局备注 > 内置 tRPC 备注，清空用户备注后仍可回退到内置备注。*

## 0x02 响应

```json
{
  "result": true,
  "code": 200,
  "message": "OK",
  "data": {}
}
```

`result` 表示请求是否成功，`code` 为接口状态码，`message` 为结果说明，成功时 `data` 为 `{}`。
