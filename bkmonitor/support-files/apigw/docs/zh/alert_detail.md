### 功能描述

根据ID查询告警详情

### 请求参数

`查询字符串参数`

| 字段 | 类型  | 是否必选 | 描述    |
|----|-----|------|-------|
| id | str | 是    | 告警 ID |

### 请求参数示例

`查询字符串参数`

```json
{
  "id": "17604957408167049"
}
```

### 响应参数

| 字段      | 类型   | 描述     |
|---------|------|--------|
| result  | bool | 请求是否成功 |
| code    | int  | 返回的状态码 |
| message | str  | 描述信息   |
| data    | dict | 数据     |

#### data

| 字段                     | 类型         | 描述                                       |
|------------------------|------------|------------------------------------------|
| id                     | str        | 告警ID                                     |
| alert_name             | str        | 告警名称                                     |
| status                 | str        | 告警状态                                     |
| description            | str        | 告警触发的具体描述                                |
| severity               | int        | 告警级别                                     |
| metric                 | list[str]  | 指标信息                                     |
| labels                 | list[str]  | 告警标签列表                                   |
| bk_biz_id              | int        | 业务 ID                                    |
| ip                     | str        | 告警目标 IPv4 地址                             |
| ipv6                   | str        | 告警目标 IPv6 地址                             |
| bk_host_id             | int        | 主机 ID                                    |
| bk_cloud_id            | int        | 云区域 ID                                   |
| bk_service_instance_id | str        | 服务实例 ID                                  |
| bk_topo_node           | list[str]  | 拓扑节点路径                                   |
| assignee               | list[str]  | 告警负责人，对应页面上的通知人                          |
| appointee              | list[str]  | 指派负责人                                    |
| supervisor             | list[str]  | 升级关注人                                    |
| follower               | list[str]  | 关注人, 只可以查看，不可以操作                         |
| is_ack                 | bool       | 是否已确认                                    |
| is_shielded            | bool       | 是否被屏蔽                                    |
| shield_left_time       | str        | 屏蔽剩余时间                                   |
| shield_id              | list[str]  | 屏蔽规则 ID                                  |
| is_handled             | bool       | 是否已通知                                    |
| is_blocked             | bool       | 是否已流控                                    |
| strategy_id            | int        | 监控策略 ID                                  |
| create_time            | int        | 告警创建时间                                   |
| update_time            | int        | 告警最后更新时间                                 |
| begin_time             | int        | 告警开始时间                                   |
| end_time               | int        | 告警结束时间                                   |
| latest_time            | int        | 最新异常点时间                                  |
| first_anomaly_time     | int        | 首次异常时间                                   |
| target_type            | str        | 告警目标类型                                   |
| target                 | str        | 告警目标                                     |
| category               | str        | 告警类别                                     |
| tags                   | list[dict] | 自定义标签列表                                  |
| category_display       | str        | 类别显示名称                                   |
| duration               | str        | 持续时间                                     |
| ack_duration           | str        | 确认时长                                     |
| data_type              | str        | 数据类型                                     |
| converge_id            | str        | 聚合 ID                                    |
| event_id               | str        | 事件 ID                                    |
| plugin_id              | str        | 插件 ID                                    |
| plugin_display_name    | str        | 插件显示名称                                   |
| strategy_name          | str        | 策略名称                                     |
| stage_display          | str        | 当前处理阶段显示文本，如 `"已通知"`                     |
| dimensions             | list[dict] | 维度信息列表                                   |
| seq_id                 | int        | ID 中的序列号部分                               |
| dedupe_md5             | str        | 去重用的 MD5 值                               |
| dedupe_keys            | list[str]  | 用于去重的字段名列表                               |
| extra_info             | dict       | 告警的更多信息，例如：当时的策略快照                       |
| dimension_message      | str        | 维度摘要信息                                   |
| metric_display         | list[dict] | 指标显示信息                                   |
| target_key             | str        | 目标显示名称                                   |
| items                  | list[dict] | 策略项详情，包含查询配置、表达式等                        |
| extend_info            | dict       | 扩展主机信息，如主机名、拓扑路径等                        |
| graph_panel            | dict       | 图表面板配置，用于前端绘制指标曲线                        |
| relation_info          | str        | 拓扑关系摘要，如 `"集群(公共组件) 模块(kafka) 环境类型(正式)"` |

### 响应参数示例
```json
{
  "result": true,
  "code": 200,
  "message": "OK",
  "data": {
    "id": "17604957408167089",
    "alert_name": "xxx",
    "status": "ABNORMAL",
    "description": "xxxx",
    "severity": 2,
    "metric": [
      "xx.xxx.xxx.xxx",
      "xxxx"
    ],
    "bk_biz_id": 3,
    "ip": "127.0.0.1",
    "ipv6": "",
    "bk_host_id": 3456,
    "bk_cloud_id": 0,
    "bk_topo_node": ["module|1", "biz|2", "set|3"],
    "assignee": ["xxx1"],
    "appointee": ["xxx1"],
    "is_shielded": false,
    "shield_left_time": "0s",
    "is_handled": true,
    "strategy_id": 345,
    "create_time": 1760495740,
    "update_time": 1760495799,
    "begin_time": 1760495640,
    "end_time": null,
    "latest_time": 1760495700,
    "first_anomaly_time": 1760495400,
    "target_type": "HOST",
    "target": "127.0.0.1|2",
    "category": "os",
    "tags": [
      { "key": "device_name", "value": "eth1" }
    ],
    "duration": "5m",
    "data_type": "time_series",
    "converge_id": "17604957408168080",
    "event_id": "df0c4aff506255e700db965f1e5dece2.1760495700.1185.1304.3",
    "plugin_id": "xxxx",
    "plugin_display_name": "xxx",
    "strategy_name": "xxx",
    "stage_display": "已通知",
    "seq_id": 8168080,
    "dimension_message": "设备名(eth2) - 目标IP(127.0.0.1)",
    "target_key": "主机 127.0.0.1",
    "relation_info": "集群(公共组件) 模块(kafka) 环境类型(正式) "
  }
}
```
