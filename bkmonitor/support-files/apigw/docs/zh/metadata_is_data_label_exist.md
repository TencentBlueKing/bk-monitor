### 功能描述

判断结果表中是否存在指定data_label

### 请求参数

| 字段         | 类型  | 必选 | 描述                                                     |
|------------|-----|----|--------------------------------------------------------|
| bk_data_id | int | 否  | 数据源ID，如果提供则排除该数据源下的结果表（相同data_id的结果表使用的data_label允许重复） |
| data_label | str | 是  | 数据标签                                                   |

### 请求参数示例

```json
{
  "bk_data_id": 1001,
  "data_label": "custom_label_001"
}
```

### 响应参数

| 字段      | 类型     | 描述       |
|---------|--------|----------|
| result  | bool   | 请求是否成功   |
| code    | int    | 返回的状态码   |
| message | string | 描述信息     |
| data    | bool   | 数据标签是否存在 |

### 响应参数示例

```json
{
  "message": "OK",
  "code": 200,
  "data": true,
  "result": true
}
```
