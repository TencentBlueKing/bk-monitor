### 功能描述

查询接入 VM 的数据链路信息

### 请求参数

| 字段         | 类型  | 必选 | 描述     |
|------------|-----|----|--------|
| bk_data_id | int | 是  | 数据源 ID |

### 请求参数示例

```json
{
    "bk_data_id": 1001
}
```

### 响应参数

| 字段      | 类型   | 描述     |
|---------|------|--------|
| result  | bool | 请求是否成功 |
| code    | int  | 返回的状态码 |
| message | str  | 描述信息   |
| data    | dict | 链路详情   |

#### data 字段说明

| 字段                | 类型         | 描述       |
|-------------------|------------|----------|
| bk_data_id        | int        | 数据源 ID   |
| is_enabled        | bool       | 数据源是否启用  |
| etl_config        | str        | 清洗模板配置   |
| option            | dict       | 数据源配置项   |
| result_table_list | list[dict] | 关联的结果表列表 |

#### data.result_table_list 元素字段说明

| 字段              | 类型         | 描述                           |
|-----------------|------------|------------------------------|
| result_table    | str        | 结果表 ID                       |
| field_list      | list[dict] | 字段列表（自定义上报类型时为空列表）           |
| schema_type     | str        | Schema 类型                    |
| option          | dict       | 结果表配置项                       |
| bk_base_data_id | int        | 计算平台数据源 ID（未接入 VM 时为 `null`） |

### 响应参数示例

```json
{
    "result": true,
    "code": 200,
    "message": "OK",
    "data": {
        "bk_data_id": 1001,
        "is_enabled": true,
        "etl_config": "bk_standard_v2_time_series",
        "option": {},
        "result_table_list": [
            {
                "result_table": "2_bkmonitor_time_series_1001.__default__",
                "field_list": [
                    {
                        "field_name": "value",
                        "field_type": "float",
                        "tag": "metric",
                        "alias_name": "",
                        "description": "",
                        "is_config_by_user": true
                    }
                ],
                "schema_type": "free",
                "option": {},
                "bk_base_data_id": 12345
            }
        ]
    }
}
```
