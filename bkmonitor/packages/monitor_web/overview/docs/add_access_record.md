### 功能描述

添加功能访问记录

### 请求参数

| 字段  | 类型   | 必选 | 描述       |
|-------|--------|------|------------|
| bk_biz_id | int | 是   | 业务ID |
| function | string | 是   | 功能名称, 可选值: dashboard, apm_service, metric_retrieve |
| config | json | 是   | 实例信息 |

#### config 字段说明

##### 仪表盘(function=dashboard)
| 字段 | 类型 | 描述 |
|------|------|------|
| dashboard_uid | string | 仪表盘UID |

##### APM服务(function=apm_service)
| 字段 | 类型 | 描述 |
|------|------|------|
| application_id | int | APM应用ID |
| service_name | string | 服务名称 |

### 请求参数示例

```json
{
    "bk_biz_id": 2,
    "function": "dashboard",
    "config": {"dashboard_uid": "1234567890"}
}
```

### 响应参数

| 字段 | 类型 | 描述 |
|------|------|------|
| result | bool | 是否成功 |
