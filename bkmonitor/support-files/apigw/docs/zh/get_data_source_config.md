### 功能描述

获取数据源配置信息，用于查询指定业务、数据源和数据类型下的指标配置信息。

### 请求参数

| 字段              | 类型    | 必选 | 描述                       |
| ----------------- | ------- | ---- | -------------------------- |
| bk_biz_id         | int     | 是   | 业务ID                     |
| data_source_label | string  | 是   | 数据来源标签               |
| data_type_label   | string  | 是   | 数据类型标签               |
| return_dimensions | boolean | 否   | 是否返回维度信息，默认true |

### 请求参数示例

```json
{
    "bk_biz_id": 2,
    "data_source_label": "bk_monitor",
    "data_type_label": "time_series",
    "return_dimensions": true
}
```

### 响应参数

| 字段       | 类型   | 描述           |
| ---------- | ------ | -------------- |
| result     | bool   | 请求是否成功   |
| code       | int    | 返回的状态码   |
| message    | string | 描述信息       |
| data       | list   | 数据源配置列表 |
| request_id | string | 请求ID         |

#### data字段说明

| 字段              | 类型       | 描述             |
| ----------------- | ---------- | ---------------- |
| id                | string     | 结果表ID         |
| bk_data_id        | string     | 数据ID           |
| name              | string     | 数据源名称       |
| metrics           | list[dict] | 指标列表         |
| time_field        | string     | 时间字段         |
| is_platform       | bool       | 是否为平台级指标 |
| dimensions        | list[dict] | 维度列表         |

#### metrics字段说明

| 字段 | 类型   | 描述             |
| ---- | ------ | ---------------- |
| id   | string | 指标字段名称     |
| name | string | 指标字段描述名称 |

#### dimensions字段说明

| 字段         | 类型   | 描述           |
| ------------ | ------ | -------------- |
| id           | string | 维度唯一标识符 |
| name         | string | 维度名称       |
| is_dimension | bool   | 是否为维度标识 |
| type         | string | 维度数据类型   |

### 响应参数示例

```json
{
    "result": true,
    "code": 200,
    "message": "OK",
    "data": [
        {
            "id": "system.cpu_detail",
            "bk_data_id": "",
            "name": "",
            "metrics": [
                {
                    "id": "usage",
                    "name": "CPU单核使用率"
                },
                {
                    "id": "idle",
                    "name": "CPU单核空闲率"
                },
                {
                    "id": "iowait",
                    "name": "CPU单核等待IO的时间占比"
                },
                {
                    "id": "stolen",
                    "name": "CPU单核分配给虚拟机的时间占比"
                },
                {
                    "id": "system",
                    "name": "CPU单核系统程序使用占比"
                },
                {
                    "id": "user",
                    "name": "CPU单核用户程序使用占比"
                },
                {
                    "id": "nice",
                    "name": "低优先级程序在用户态执行的CPU占比"
                },
                {
                    "id": "interrupt",
                    "name": "硬件中断数的CPU占比"
                },
                {
                    "id": "softirq",
                    "name": "软件中断数的CPU占比"
                },
                {
                    "id": "guest",
                    "name": "内核在虚拟机上运行的CPU占比"
                }
            ],
            "time_field": "time",
            "is_platform": true,
            "dimensions": [
                {
                    "id": "bk_agent_id",
                    "name": "Agent ID",
                    "is_dimension": true,
                    "type": "string"
                },
                {
                    "id": "bk_biz_id",
                    "name": "业务ID",
                    "is_dimension": true,
                    "type": "string"
                },
                {
                    "id": "bk_cloud_id",
                    "name": "采集器云区域ID",
                    "is_dimension": true,
                    "type": "string"
                },
                {
                    "id": "bk_host_id",
                    "name": "采集主机ID",
                    "is_dimension": true,
                    "type": "string"
                },
                {
                    "id": "bk_target_cloud_id",
                    "name": "云区域ID",
                    "is_dimension": true,
                    "type": "string"
                },
                {
                    "id": "bk_target_host_id",
                    "name": "目标主机ID",
                    "is_dimension": true,
                    "type": "string"
                },
                {
                    "id": "bk_target_ip",
                    "name": "目标IP",
                    "is_dimension": true,
                    "type": "string"
                },
                {
                    "id": "device_name",
                    "name": "设备名",
                    "is_dimension": true,
                    "type": "string"
                },
                {
                    "id": "hostname",
                    "name": "主机名",
                    "is_dimension": true,
                    "type": "string"
                },
                {
                    "id": "ip",
                    "name": "采集器IP",
                    "is_dimension": true,
                    "type": "string"
                }
            ]
        }
    ]
}
```

### 注意事项

1. **request_id字段**：该字段由API网关自动生成，用于请求链路追踪和问题排查，通常出现在响应头中（如x-bkapi-request-id），而不是在JSON响应体中。

2. **return_dimensions参数**：当设置为false时，接口将不返回维度信息，可以显著减少响应数据量。

3. **平台级指标**：当is_platform为true时，表示该指标为平台级指标，适用于所有业务。

4. **数据源类型**：支持的数据源标签包括但不限于：bk_monitor、bk_monitor_collector、custom等。

5. **数据类型**：支持的数据类型标签包括但不限于：time_series、event、log等。