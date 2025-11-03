### 功能描述

获取Grafana变量值，支持多种查询类型和场景

### 请求参数

| 字段      | 类型   | 必选 | 描述           |
| --------- | ------ | ---- | -------------- |
| bk_biz_id | int    | 是   | 业务ID         |
| type      | string | 是   | 查询类型       |
| scenario  | string | 否   | 场景，默认"os" |
| params    | dict   | 是   | 查询参数       |

#### type 字段说明

| 值        | 描述         | 适用场景                 |
| --------- | ------------ | ------------------------ |
| dimension | 维度查询     | 监控时序数据、日志数据等 |
| host      | 主机查询     | 操作系统场景             |
| cluster   | 集群查询     | Kubernetes场景           |
| namespace | 命名空间查询 | Kubernetes场景           |
| node      | 节点查询     | Kubernetes场景           |
| pod       | Pod查询      | Kubernetes场景           |
| container | 容器查询     | Kubernetes场景           |
| service   | 服务查询     | Kubernetes场景           |

#### scenario 字段说明

| 值         | 描述                 |
| ---------- | -------------------- |
| os         | 操作系统场景（默认） |
| kubernetes | Kubernetes场景       |

#### params 字段说明

##### dimension 类型的 params

| 字段              | 类型   | 必选 | 描述         |
| ----------------- | ------ | ---- | ------------ |
| data_source_label | string | 是   | 数据源标签   |
| data_type_label   | string | 是   | 数据类型标签 |
| field             | string | 是   | 查询字段     |
| metric_field      | string | 是   | 指标字段     |
| result_table_id   | string | 是   | 结果表ID     |
| where             | list   | 否   | 查询条件     |

##### Kubernetes 相关类型的 params

| 字段        | 类型   | 必选 | 描述         |
| ----------- | ------ | ---- | ------------ |
| label_field | string | 是   | 显示标签字段 |
| value_field | string | 是   | 值字段       |
| where       | list   | 否   | 查询条件     |

##### host 类型的 params

| 字段        | 类型   | 必选 | 描述         |
| ----------- | ------ | ---- | ------------ |
| label_field | string | 是   | 显示标签字段 |
| value_field | string | 是   | 值字段       |
| where       | list   | 否   | 查询条件     |

#### where 条件格式

| 字段   | 类型   | 必选 | 描述     |
| ------ | ------ | ---- | -------- |
| key    | string | 是   | 字段名   |
| method | string | 是   | 匹配方法 |
| value  | list   | 是   | 匹配值   |

### 请求参数示例

```json
{
    "bk_biz_id": 2,
    "type": "dimension",
    "scenario": "os",
    "params": {
        "data_source_label": "bk_monitor",
        "data_type_label": "time_series",
        "field": "device_name",
        "metric_field": "usage",
        "result_table_id": "system.cpu_summary",
        "where": []
    }
}
```

### 响应参数

| 字段    | 类型   | 描述         |
| ------- | ------ | ------------ |
| result  | bool   | 请求是否成功 |
| code    | int    | 返回的状态码 |
| message | string | 描述信息     |
| data    | list   | 变量值列表   |

#### data 字段说明

| 字段  | 类型   | 描述     |
| ----- | ------ | -------- |
| label | string | 显示标签 |
| value | string | 变量值   |

### 响应参数示例

```json
{
    "result": true,
    "code": 200,
    "message": "OK",
    "data": [
        {
            "label": "cpu-total",
            "value": "cpu-total"
        },
        {
            "label": "device-1",
            "value": "device-1"
        }
    ]
}
```

