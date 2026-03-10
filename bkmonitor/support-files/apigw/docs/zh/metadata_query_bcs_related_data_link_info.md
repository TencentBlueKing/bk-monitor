### 功能描述

查询 bcs 集群相关数据链路信息

### 请求参数

| 字段             | 类型  | 必选 | 描述       |
|----------------|-----|----|----------|
| bcs_cluster_id | str | 是  | BCS 集群ID |

### 请求参数示例

```json
{
    "bcs_cluster_id": "BCS-K8S-00001"
}
```

### 响应参数

| 字段      | 类型     | 描述     |
|---------|--------|--------|
| result  | bool   | 请求是否成功 |
| code    | int    | 返回的状态码 |
| message | string | 描述信息   |
| data    | object | 返回数据   |

#### data 字段说明

| 字段           | 类型     | 描述           |
|--------------|--------|--------------|
| K8SMetric    | object | K8S 指标数据链路信息 |
| CustomMetric | object | 自定义指标数据链路信息  |
| K8SEvent     | object | K8S 事件数据链路信息 |

#### data 各链路对象字段说明

| 字段                 | 类型       | 描述                |
|--------------------|----------|-------------------|
| bk_data_id         | int      | 数据源ID             |
| data_name          | str      | 数据源名称             |
| result_table_id    | str      | 监控平台结果表ID         |
| vm_result_table_id | str/null | VM结果表ID，不存在时为null |

### 响应参数示例

```json
{
    "result": true,
    "code": 200,
    "message": "OK",
    "data": {
        "K8SMetric": {
            "bk_data_id": 1001,
            "data_name": "bcs_BCS-K8S-00001_k8s_metric",
            "result_table_id": "2_bkmonitor_time_series_1001.__default__",
            "vm_result_table_id": "2_bkmonitor_time_series_1001.__default__"
        },
        "CustomMetric": {
            "bk_data_id": 1002,
            "data_name": "bcs_BCS-K8S-00001_custom_metric",
            "result_table_id": "2_bkmonitor_time_series_1002.__default__",
            "vm_result_table_id": "2_bkmonitor_time_series_1002.__default__"
        },
        "K8SEvent": {
            "bk_data_id": 1003,
            "data_name": "bcs_BCS-K8S-00001_k8s_event",
            "result_table_id": "2_bkmonitor_time_series_1003.__default__",
            "vm_result_table_id": null
        }
    }
}
```
