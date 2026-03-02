### 功能描述

【告警V2】K8S场景列表查询

### 请求参数

| 字段       | 类型  | 必选 | 描述   |
|----------|-----|----|------|
| alert_id | str | 是  | 告警ID |

### 请求参数示例

```json
{
    "alert_id": "f1c6877ba046e2d32bfd8393b4dd26f7.1763554080.2860.2978.2"
}
```

### 响应参数

| 字段      | 类型        | 描述     |
|---------|-----------|--------|
| result  | bool      | 请求是否成功 |
| code    | int       | 返回的状态码 |
| message | string    | 描述信息   |
| data    | list[str] | 观测场景列表 |

#### data 元素说明

观测场景字符串，可选值：

- `performance`: 性能场景（适用于Pod、Workload）
- `network`: 网络场景（适用于Pod、Workload、Service）
- `capacity`: 容量场景（适用于Node）

### 响应参数示例

```json
{
    "result": true,
    "code": 200,
    "message": "OK",
    "data": ["performance", "network"]
}
```
