### 功能描述

获取首页功能入口

### 请求参数

| 字段  | 类型   | 必选 | 描述       |
|-------|--------|------|------------|
| type | string | 是   | 类型, 可选值: recent, favorite |
| functions | list | 是   | 功能列表, 可选值: dashboard, apm_service, log_retrieve, metric_retrieve |
| limit | int | 否   | 限制, 默认10 |

### 请求参数示例

```json
{
    "type": "recent",
    "functions": ["dashboard", "apm_service"],
    "limit": 10
}
```

### 响应参数

| 字段 | 类型 | 描述 |
|------|------|------|
| function | string | 功能名称 |
| name | string | 功能名称 |
| items | list | 功能入口列表 |

#### items 字段说明

##### 仪表盘(type=dashboard)
| 字段 | 类型 | 描述 |
|------|------|------|
| bk_biz_id | int | 业务ID |
| bk_biz_name | string | 业务名称 |
| dashboard_uid | string | 仪表盘UID |
| dashboard_title | string | 仪表盘标题 |
| dashboard_slug | string | 仪表盘slug |

##### APM服务(type=apm_service)
| 字段 | 类型 | 描述 |
|------|------|------|
| bk_biz_id | int | 业务ID |
| bk_biz_name | string | 业务名称 |
| application_id | int | APM应用ID |
| app_name | string | 应用名称 |
| service_name | string | 服务名称 |
| app_alias | string | 应用别名 |

##### 日志索引集(type=log_retrieve)

TODO

##### 指标集(type=metric_retrieve)

TODO

##### 其他类型，方便后续扩展
| 字段 | 类型 | 描述 |
|------|------|------|
| bk_biz_id | int | 业务ID |
| bk_biz_name | string | 业务名称 |
| name | string | 名称 |
| url | string | 链接 |


### 响应参数示例

```json
[
    {
        "function": "dashboard",
        "name": "仪表盘",
        "items": [
            {
                "bk_biz_id": 2,
                "bk_biz_name": "蓝鲸",
                "dashboard_uid": "1234567890",
                "dashboard_title": "主机查看",
                "dashboard_slug": "host-view"
            }
        ]
    }
]
```