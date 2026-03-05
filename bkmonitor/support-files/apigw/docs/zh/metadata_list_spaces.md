### 功能描述

查询空间实例列表

### 请求参数

| 字段                     | 类型   | 必选 | 描述                                       |
|------------------------|------|----|------------------------------------------|
| space_uid              | str  | 否  | 空间唯一标识，格式为 `{space_type_id}__{space_id}` |
| space_type_id          | str  | 否  | 空间类型 ID                                  |
| space_id               | str  | 否  | 空间 ID                                    |
| space_name             | str  | 否  | 空间名称，支持模糊查询                              |
| id                     | int  | 否  | 空间自增 ID                                  |
| is_exact               | bool | 否  | 是否精确查询，默认为 false                         |
| is_detail              | bool | 否  | 是否返回更详细信息，默认为 false                      |
| page                   | int  | 否  | 页数，默认为 1                                 |
| page_size              | int  | 否  | 每页的数量，最大 1000，默认为 10                     |
| exclude_platform_space | bool | 否  | 是否过滤掉平台级的空间，默认为 true                     |
| include_resource_id    | bool | 否  | 是否包含资源 ID，默认为 false                      |

### 请求参数示例

```json
{
    "space_type_id": "bkcc",
    "page": 1,
    "page_size": 10
}
```

### 响应参数

| 字段      | 类型   | 描述     |
|---------|------|--------|
| result  | bool | 请求是否成功 |
| code    | int  | 返回的状态码 |
| message | str  | 描述信息   |
| data    | dict | 分页空间列表 |

#### data 字段说明

| 字段    | 类型         | 描述     |
|-------|------------|--------|
| count | int        | 空间总数   |
| list  | list[dict] | 空间实例列表 |

#### data.list 元素字段说明

| 字段            | 类型   | 描述                                       |
|---------------|------|------------------------------------------|
| id            | int  | 空间自增 ID                                  |
| space_uid     | str  | 空间唯一标识，格式为 `{space_type_id}__{space_id}` |
| space_type_id | str  | 空间类型 ID                                  |
| space_id      | str  | 空间 ID                                    |
| space_code    | str  | 空间英文编码                                   |
| space_name    | str  | 空间名称                                     |
| display_name  | str  | 空间显示名称，格式为 `[类型名称] 空间名称`                 |
| status        | str  | 空间状态                                     |
| time_zone     | str  | 时区，默认为 `Asia/Shanghai`                   |
| language      | str  | 默认语言，默认为 `zh-hans`                       |
| is_bcs_valid  | bool | BCS 是否可用                                 |
| is_global     | bool | 是否跨业务管理可用                                |

> 当 `include_resource_id=true` 或 `is_detail=true` 时，每个元素额外包含以下字段：

| 字段           | 类型         | 描述                                              |
|--------------|------------|-------------------------------------------------|
| resources    | list[dict] | 关联的资源列表，每项包含 `resource_type`、`resource_id`      |
| data_sources | list[dict] | 关联的数据源列表，每项包含 `bk_data_id`、`from_authorization` |

### 响应参数示例

```json
{
    "result": true,
    "code": 200,
    "message": "OK",
    "data": {
        "count": 1,
        "list": [
            {
                "id": 1,
                "space_uid": "bkcc__2",
                "space_type_id": "bkcc",
                "space_id": "2",
                "space_code": "",
                "space_name": "蓝鲸",
                "display_name": "[业务] 蓝鲸",
                "status": "normal",
                "time_zone": "Asia/Shanghai",
                "language": "zh-hans",
                "is_bcs_valid": false,
                "is_global": false
            }
        ]
    }
}
```
