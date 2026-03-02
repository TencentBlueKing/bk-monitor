### 功能描述

修改指定数据源的来源平台配置信息

### 请求参数

| 字段            | 类型        | 必选 | 描述                                               |
|---------------|-----------|----|--------------------------------------------------|
| data_id_list  | list[int] | 是  | 数据源 ID 列表                                        |
| source_system | str       | 是  | 数据源 ID 来源平台，可选值：`bkgse`（蓝鲸 GSE）、`bkdata`（蓝鲸数据平台） |

### 请求参数示例

```json
{
    "data_id_list": [1001, 1002, 1003],
    "source_system": "bkgse"
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
