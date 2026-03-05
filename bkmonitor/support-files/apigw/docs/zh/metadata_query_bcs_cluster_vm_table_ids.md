### 功能描述

查询 BCS 集群 ID 接入 VM 的结果表信息

### 请求参数

| 字段             | 类型  | 必选 | 描述        |
|----------------|-----|----|-----------|
| bcs_cluster_id | str | 是  | BCS 集群 ID |

### 请求参数示例

```json
{
    "bcs_cluster_id": "BCS-K8S-00000"
}
```

### 响应参数

| 字段      | 类型     | 描述     |
|---------|--------|--------|
| result  | bool   | 请求是否成功 |
| code    | int    | 返回的状态码 |
| message | string | 描述信息   |
| data    | dict   | 返回数据   |

#### data 字段说明

| 字段                    | 类型   | 描述                              |
|-----------------------|------|---------------------------------|
| k8s_metric_rt         | str  | K8s 内置指标的 VM 结果表 ID（不存在时不返回该字段） |
| k8s_metric_data_id    | dict | K8s 内置指标的数据源 ID 信息（不存在时不返回该字段）  |
| custom_metric_rt      | str  | 自定义指标的 VM 结果表 ID（不存在时不返回该字段）    |
| custom_metric_data_id | dict | 自定义指标的数据源 ID 信息（不存在时不返回该字段）     |

#### k8s_metric_data_id / custom_metric_data_id 字段说明

| 字段                 | 类型  | 描述         |
|--------------------|-----|------------|
| bk_monitor_data_id | int | 监控平台数据源 ID |
| bk_base_data_id    | int | 计算平台数据源 ID |

### 响应参数示例

```json
{
    "result": true,
    "code": 200,
    "message": "OK",
    "data": {
        "k8s_metric_rt": "bkmonitor_k8s_metric_rt",
        "k8s_metric_data_id": {
            "bk_monitor_data_id": 1001,
            "bk_base_data_id": 2001
        },
        "custom_metric_rt": "bkmonitor_custom_metric_rt",
        "custom_metric_data_id": {
            "bk_monitor_data_id": 1002,
            "bk_base_data_id": 2002
        }
    }
}
```
