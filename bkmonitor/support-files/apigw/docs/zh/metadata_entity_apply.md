### 功能描述

创建或更新应用实体资源（声明式API）

### 请求参数

| 字段        | 类型     | 必选 | 描述                                                   |
|-----------|--------|----|------------------------------------------------------|
| kind      | string | 是  | 实体类型                                                 |
| metadata  | dict   | 是  | 资源元数据                                                |
| spec      | dict   | 是  | 资源配置，根据不同的实体类型有不同的字段                                 |
| bk_biz_id | int    | 否  | 业务ID，可选。如果提供，会自动转换为 space_uid 并覆盖 metadata.namespace |

#### metadata 字段说明

| 字段        | 类型     | 必选 | 描述                                |
|-----------|--------|----|-----------------------------------|
| namespace | string | 否  | 命名空间，可选。如果提供了 bk_biz_id，则会被自动转换覆盖 |
| name      | string | 是  | 资源名称                              |
| labels    | dict   | 否  | 标签，键值对格式，key和value均为string类型      |

### 请求参数示例

```json
{
    "kind": "CustomRelationStatus",
    "metadata": {
        "namespace": "default",
        "name": "relation-001",
        "labels": {
            "env": "production",
            "app": "monitor"
        }
    },
    "spec": {
        "from_resource": "source_entity",
        "to_resource": "target_entity"
    }
}
```

或使用 bk_biz_id：

```json
{
    "kind": "CustomRelationStatus",
    "metadata": {
        "name": "relation-001",
        "labels": {
            "env": "production",
            "app": "monitor"
        }
    },
    "spec": {
        "from_resource": "source_entity",
        "to_resource": "target_entity"
    },
    "bk_biz_id": 2
}
```

### 响应参数

| 字段      | 类型     | 描述     |
|---------|--------|--------| 
| result  | bool   | 请求是否成功 |
| code    | int    | 返回的状态码 |
| message | string | 描述信息   |
| data    | dict   | 数据     |

#### data字段说明

| 字段       | 类型     | 描述    |
|----------|--------|-------| 
| kind     | string | 实体类型  |
| metadata | dict   | 资源元数据 |
| spec     | dict   | 资源配置  |

#### data.metadata 字段说明

| 字段                | 类型     | 描述                           |
|-------------------|--------|------------------------------| 
| namespace         | string | 命名空间                         |
| name              | string | 资源名称                         |
| labels            | dict   | 标签，键值对格式，key和value均为string类型 |
| generation        | int    | 版本号                          |
| creationTimestamp | string | 创建时间                         |
| uid               | string | 资源唯一标识                       |

### 响应参数示例

```json
{
    "result": true,
    "code": 200,
    "message": "OK",
    "data": {
        "kind": "CustomRelationStatus",
        "metadata": {
            "namespace": "default",
            "name": "relation-001",
            "labels": {
                "env": "production",
                "app": "monitor"
            },
            "generation": 1,
            "creationTimestamp": "2021-01-01T00:00:00Z",
            "uid": "b194835f-7726-474d-b21f-cf5c859c11e6"
        },
        "spec": {
            "from_resource": "source_entity",
            "to_resource": "target_entity"
        }
    }
}
```
