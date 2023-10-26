# Access

模块负责对接各种数据源、事件源、告警源，并对数据进行维度补充，范围过滤，最后输出标准数据

## 功能

- 配置来源
    - 来源文件
    - 来源配置中心（zk、consul、redis等）


- 支持的数据源类型：
    - 支持下面两个平台的数据来源，两种数据类型
    - BKDATA \ BKMONITOR
        - time_series: 来源于监控自身的TSDB
        - log: 来源蓝鲸数据平台的TSDB

- 支持的事件源类型：
    - kafka，目前只支持这一种

- 支持的告警源类型（功能暂时没有）
    - kafka / redis 

- 维度补充方式：
    - 目前支持一种，对主机的数据补充节点（集群、模块）信息。
    - 支持用户自定义，自己补充任意数据
    

- 范围过滤
    - 对监控目标的过滤，按配置来。只支持数据中有的维度，没有的则忽略


- 标准输出数据格式

- data

```json
{
    "record_id":"f7659f5811a0e187c71d119c7d625f23.1569246480",
    "value":1.38,
    "values":{
        "timestamp":1569246480,
        "load5":1.38
    },
    "dimensions":{
        "bk_target_ip":"127.0.0.1"
    },
    "time":1569246480
}
```

- event

```json
{
    "data": {
        "record_id": "{dimensions_md5}.{timestamp}",
        "dimensions": {
            "bk_target_ip": "127.0.0.1",
            "bk_target_cloud_id": "0",
            "bk_topo_node": ["biz|2", "set|5", "module|6"]
        },
        "value": "This service is offline",
        "time": 1551482964,
        "raw_data": {
           "_bizid_" : 0,
           "_cloudid_" : 0,
           "_server_" : "127.0.0.1",
           "_time_" : "2019-03-02 15:29:24",
           "_utctime_" : "2019-03-02 07:29:24",
           "_value_" : [ "This service is offline" ]
        }
    },
    "anomaly": {
        "1": {
            "anomaly_message": "This service is offline",
            "anomaly_id": "{dimensions_md5}.{timestamp}.{strategy_id}.{item_id}.{level}",
            "anomaly_time": "2019-03-02 07:29:24"
        }
    },
    "strategy_snapshot_key": "xxx"
}
```

- alert

```json
{

}
```

## 其他

- 模块需统计指标数据，能代表目前的处理能力
- 完善的日志记录
- 单元测试