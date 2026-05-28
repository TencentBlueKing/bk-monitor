# admin_resource_call

Admin Resource 通用调用入口，默认隐藏。

## 请求参数

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| func_name | string | 是 | 要调用的函数名 |
| params | object | 否 | 函数入参字典，默认 `{}` |

## 特殊协议

### 查询函数列表

```json
{
  "func_name": "__meta__",
  "params": {
    "action": "list"
  }
}
```

### 查询函数详细说明

```json
{
  "func_name": "__meta__",
  "params": {
    "action": "detail",
    "target_func_name": "bklog.collector.list"
  }
}
```
