### 功能描述

查询BCS相关指标信息

### 请求参数

| 字段              | 类型        | 必选 | 描述                                              |
|-----------------|-----------|----|-------------------------------------------------|
| bk_biz_ids      | list[int] | 否  | 业务ID列表，为null时查询所有业务；传入0时获取K8s系统内置指标             |
| cluster_ids     | list[str] | 否  | BCS集群ID列表，为null时查询所有集群                          |
| dimension_name  | str       | 否  | 维度名称，与 `dimension_value` 同时存在时生效，用于过滤指标，默认为空字符串 |
| dimension_value | str       | 否  | 维度取值，与 `dimension_name` 同时存在时生效，用于过滤指标，默认为空字符串  |

### 请求参数示例

```json
{
    "bk_biz_ids": [2],
    "cluster_ids": ["BCS-K8S-00001"],
    "dimension_name": "namespace",
    "dimension_value": "default"
}
```

### 响应参数

| 字段      | 类型     | 描述     |
|---------|--------|--------|
| result  | bool   | 请求是否成功 |
| code    | int    | 返回的状态码 |
| message | string | 描述信息   |
| data    | list   | 返回数据   |

#### data 元素字段说明

| 字段          | 类型        | 描述                        |
|-------------|-----------|---------------------------|
| field_name  | str       | 指标名称                      |
| description | str       | 指标描述                      |
| unit        | str       | 指标单位                      |
| type        | str       | 指标类型（如 `double`、`string`） |
| bk_biz_ids  | list[int] | 关联的业务ID列表                 |
| bk_data_ids | list[int] | 关联的DataID列表               |
| cluster_ids | list[str] | 关联的BCS集群ID列表              |
| dimensions  | list      | 维度列表                      |
| label       | str       | 标签（如 `kubernetes`）        |

#### dimensions 元素字段说明

| 字段          | 类型  | 必有 | 描述              |
|-------------|-----|----|-----------------|
| field_name  | str | 是  | 维度名称            |
| description | str | 是  | 维度描述            |
| unit        | str | 否  | 维度单位（维度字段存在时返回） |
| type        | str | 否  | 维度类型（维度字段存在时返回） |

### 响应参数示例

```json
{
    "result": true,
    "code": 200,
    "message": "OK",
    "data": [
        {
            "field_name": "container_cpu_usage_seconds_total",
            "description": "容器CPU使用总量",
            "unit": "s",
            "type": "double",
            "bk_biz_ids": [2],
            "bk_data_ids": [1001],
            "cluster_ids": ["BCS-K8S-00001"],
            "dimensions": [
                {
                    "field_name": "namespace",
                    "description": "命名空间",
                    "unit": "",
                    "type": "string"
                },
                {
                    "field_name": "pod",
                    "description": "Pod名称",
                    "unit": "",
                    "type": "string"
                }
            ],
            "label": "kubernetes"
        }
    ]
}
```
