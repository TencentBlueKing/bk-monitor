# kernel_rpc_call

Kernel 类 RPC 通用入口，默认隐藏。

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
    "target_func_name": "info"
  }
}
```

## 内置函数

### info

返回当前环境基础信息，包括是否启用多租户模式、监控访问地址、站点前缀等。
