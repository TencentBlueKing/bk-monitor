### 功能描述

导入插件API（无前端交互版本）

### 请求参数

| 字段          | 类型   | 必选 | 描述                     |
|-------------|------|----|------------------------|
| bk_biz_id   | int  | 是  | 业务ID，0表示全业务插件          |
| file_data   | file | 是  | 插件文件（tar.gz格式的插件包）     |
| metric_json | dict | 否  | 指标JSON配置，用于覆盖插件包中的指标配置 |

### 请求参数示例

`Content-Type: multipart/form-data`

```json
{
    "bk_biz_id": 2,
    "file_data": "二进制文件内容",
    "metric_json": {}
}
```

### 响应参数

| 字段      | 类型     | 描述              |
|---------|--------|-----------------|
| result  | bool   | 请求是否成功          |
| code    | int    | 返回的状态码          |
| message | string | 描述信息            |
| data    | bool   | 返回数据，导入成功返回true |

### 响应参数示例

```json
{
    "result": true,
    "code": 200,
    "message": "OK",
    "data": true
}
```
