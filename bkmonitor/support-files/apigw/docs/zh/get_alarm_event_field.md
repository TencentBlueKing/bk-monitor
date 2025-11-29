### 功能描述

获取告警事件字段

### 请求参数

| 字段名      | 类型  | 是否必选 | 描述 |
|----------|-----|----------|------|
| bk_biz_id | int | 是       | 业务ID |
| start_time | int | 否       | 查询开始时间；若未提供，默认为当前时间前7天 |
| end_time | int | 否       | 查询结束时间；若未提供，默认为当前时间 |

### 请求参数示例
```json
{
  "bk_biz_id": 2
}
```

### 响应参数

| 字段      | 类型   | 描述     |
|---------|------|--------|
| result  | bool | 请求是否成功 |
| code    | int  | 返回的状态码 |
| message | str  | 描述信息   |
| data    | list    | 数据     |

#### data

| 字段      | 类型  | 描述     |
|---------|-----|--------|
| id  | str | 字段唯一标识 |
| name    | str | 字段显示名称 |
| is_dimension | bool   | 是否是维度字段 |

### 响应参数示例
```json
{
  "result": true,
  "code": 200,
  "message": "OK",
  "data": [
    {
    "id": "severity",
    "name": "告警级别",
    "is_dimension": true
  },
  {
    "id": "status",
    "name": "告警状态",
    "is_dimension": true
  },
  {
    "id": "alert_name",
    "name": "告警名称",
    "is_dimension": true
  },
  {
    "id": "strategy_id",
    "name": "策略ID",
    "is_dimension": true
  },
  {
    "id": "event.ip",
    "name": "IP",
    "is_dimension": true
  },
  {
    "id": "event.bk_cloud_id",
    "name": "云区域ID",
    "is_dimension": true
  },
  {
    "id": "tags.device_name",
    "name": "device_name",
    "is_dimension": true
  },
  {
    "id": "tags.service",
    "name": "service",
    "is_dimension": true
  }
  ]
}
```
