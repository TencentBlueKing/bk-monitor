### 功能描述

创建空间实例

### 请求参数

| 字段            | 类型         | 必选 | 描述                                       |
|---------------|------------|----|------------------------------------------|
| space_uid     | str        | 否  | 空间唯一标识，格式为 `{space_type_id}__{space_id}` |
| space_type_id | str        | 否  | 空间类型 ID，与 space_id 配合使用                  |
| space_id      | str        | 否  | 空间 ID，与 space_type_id 配合使用               |
| creator       | str        | 是  | 创建者                                      |
| space_name    | str        | 是  | 空间中文名称                                   |
| resources     | list[dict] | 否  | 关联的资源列表，默认为空                             |
| space_code    | str        | 否  | 空间编码，默认为空                                |

#### resources 元素字段说明

| 字段            | 类型  | 必选 | 描述   |
|---------------|-----|----|------|
| resource_type | str | 是  | 资源类型 |
| resource_id   | str | 是  | 资源标识 |

### 请求参数示例

```json
{
    "space_type_id": "bkci",
    "space_id": "myproject",
    "creator": "admin",
    "space_name": "我的项目",
    "resources": [
        {
            "resource_type": "bcs",
            "resource_id": "BCS-K8S-00001"
        }
    ]
}
```

### 响应参数

| 字段      | 类型   | 描述        |
|---------|------|-----------|
| result  | bool | 请求是否成功    |
| code    | int  | 返回的状态码    |
| message | str  | 描述信息      |
| data    | dict | 创建的空间实例信息 |

#### data 字段说明

| 字段            | 类型   | 描述                                       |
|---------------|------|------------------------------------------|
| id            | int  | 空间自增 ID                                  |
| space_uid     | str  | 空间唯一标识，格式为 `{space_type_id}__{space_id}` |
| bk_tenant_id  | str  | 租户id                                     |
| space_type_id | str  | 空间类型 ID                                  |
| space_id      | str  | 空间 ID                                    |
| space_code    | str  | 空间英文编码                                   |
| space_name    | str  | 空间名称                                     |
| status        | str  | 空间状态                                     |
| time_zone     | str  | 时区，默认为 `Asia/Shanghai`                   |
| language      | str  | 默认语言，默认为 `zh-hans`                       |
| is_bcs_valid  | bool | BCS 是否可用                                 |
| is_global     | bool | 是否跨业务管理可用                                |
| creator       | str  | 创建者                                      |
| create_time   | str  | 创建时间，格式为 `YYYY-MM-DD HH:MM:SS`           |
| updater       | str  | 更新者                                      |
| update_time   | str  | 更新时间，格式为 `YYYY-MM-DD HH:MM:SS`           |

### 响应参数示例

```json
{
    "result": true,
    "code": 200,
    "message": "OK",
    "data": {
        "id": 10,
        "space_uid": "bkci__myproject",
        "bk_tenant_id": "system",
        "space_type_id": "bkci",
        "space_id": "myproject",
        "space_code": "",
        "space_name": "我的项目",
        "status": "normal",
        "time_zone": "Asia/Shanghai",
        "language": "zh-hans",
        "is_bcs_valid": false,
        "is_global": false,
        "creator": "admin",
        "create_time": "2023-01-01 00:00:00",
        "updater": "admin",
        "update_time": "2023-01-01 00:00:00"
    }
}
```
