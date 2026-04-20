### 功能描述

创建统计节点（按指定的降采样频率）

### 请求参数

| 字段           | 类型  | 必选 | 描述               |
|--------------|-----|----|------------------|
| table_id     | str | 是  | 结果表 ID           |
| agg_interval | int | 否  | 统计周期（秒），默认为 `60` |

### 请求参数示例

```json
{
    "table_id": "system.cpu_detail",
    "agg_interval": 60
}
```

### 响应参数

| 字段      | 类型     | 描述     |
|---------|--------|--------|
| result  | bool   | 请求是否成功 |
| code    | int    | 返回的状态码 |
| message | string | 描述信息   |
| data    | null   | 返回数据   |

### 响应参数示例

```json
{
    "result": true,
    "code": 200,
    "message": "OK",
    "data": null
}
```
