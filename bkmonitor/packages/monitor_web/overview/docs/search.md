### 功能描述

全局搜索接口,支持搜索告警、策略、Trace、APM应用和主机信息

#### 请求参数

| 字段  | 类型   | 必选 | 描述       |
|-------|--------|------|------------|
| query | string | 是   | 搜索关键字 |

#### 请求参数示例

```json
{
    "query": "127.0.0.1"
}
```

### 返回结果

返回的是 event-stream 格式的数据流

data: 字段格式如下

| 字段 | 类型   | 描述     |
|------|--------|----------|
| type | string | 结果类型 |
| name | string | 结果名称 |
| items | array[object]  | 搜索结果列表 |

event: start/end 表示搜索开始和结束

#### type 可能的值

- alert: 告警事件
- strategy: 告警策略
- trace: Trace
- apm_application: APM应用
- host: 主机监控

#### items 字段说明

##### 告警类型(type=alert)

| 字段 | 类型 | 描述 |
|------|------|------|
| bk_biz_id | int | 业务ID |
| bk_biz_name | string | 业务名称 |
| name | string | 告警名称 |
| alert_id | int | 告警ID |
| start_time | int | 开始时间 |
| end_time | int | 结束时间 |

##### 策略类型(type=strategy)

| 字段 | 类型 | 描述 |
|------|------|------|
| bk_biz_id | int | 业务ID |
| bk_biz_name | string | 业务名称 |
| name | string | 策略名称 |
| strategy_id | int | 策略ID |

##### Trace类型(type=trace)

| 字段 | 类型 | 描述 |
|------|------|------|
| bk_biz_id | int | 业务ID |
| bk_biz_name | string | 业务名称 |
| name | string | Trace ID |
| trace_id | string | Trace ID |
| app_name | string | 应用名称 |
| app_alias | string | 应用别名 |
| application_id | int | 应用ID |

##### APM应用类型(type=apm_application)

| 字段 | 类型 | 描述 |
|------|------|------|
| bk_biz_id | int | 业务ID |
| bk_biz_name | string | 业务名称 |
| name | string | 应用名称 |
| app_name | string | 应用名称 |
| app_alias | string | 应用别名 |
| application_id | int | 应用ID |

##### 主机类型(type=host)

| 字段 | 类型 | 描述 |
|------|------|------|
| bk_biz_id | int | 业务ID |
| bk_biz_name | string | 业务名称 |
| name | string | IP地址 |
| bk_host_innerip | string | 内网IP |
| bk_cloud_id | int | 云区域ID |
| bk_cloud_name | string | 云区域名称 |
| bk_host_name | string | 主机名 |
| bk_host_id | int | 主机ID |

##### 其他类型，方便后续扩展
| 字段 | 类型 | 描述 |
|------|------|------|
| bk_biz_id | int | 业务ID |
| bk_biz_name | string | 业务名称 |
| name | string | 名称 |
| url | string | 链接 |

#### 返回结果示例

event-stream data示例

```
data: {"type": "host", "items": [{"bk_biz_id": 2, "bk_biz_name": "蓝鲸", "name": "127.0.0.1", "bk_host_innerip": "127.0.0.1", "bk_cloud_id": 0, "bk_cloud_name": "默认云区域", "bk_host_name": "host-1", "bk_host_id": 12345}]}
```

```json
{
    "type": "host",
    "items": [
        {
            "bk_biz_id": 2,
            "bk_biz_name": "蓝鲸",
            "name": "127.0.0.1",
            "bk_host_innerip": "127.0.0.1",
            "bk_cloud_id": 0,
            "bk_cloud_name": "默认云区域",
            "bk_host_name": "host-1",
            "bk_host_id": 12345
        }
    ]
}
``` 

event-stream event 示例

```
event: start
```

```
event: end
```
