# 查询 APM 返回码备注

从应用视角拉取完整备注，编辑后通过 `apm_set_code_remark` 保存。内部应用态接口，调用应用需获得网关资源授权。

## 0x01 请求

```text
POST /app/apm/service/get_code_remarks/
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

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `result` | `boolean` | 请求是否成功 |
| `code` | `integer` | 接口状态码，成功为 `200` |
| `message` | `string` | 结果说明 |
| `data[]` | `array<object>` | 完整用户备注列表，无配置时为 `[]`，不含内置备注 |
| `data[].kind` | `string` | `caller`（主调）或 `callee`（被调） |
| `data[].code` | `string` | 原始返回码 |
| `data[].remark` | `string` | 返回码说明 |
| `data[].is_global` | `boolean` | `true` 表示应用内所有服务生效，`false` 表示仅指定服务生效 |
| `data[].service_names` | `array<string>` | 生效服务列表，全局备注为 `[]` |
