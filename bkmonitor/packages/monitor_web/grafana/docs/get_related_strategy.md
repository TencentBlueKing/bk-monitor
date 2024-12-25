### 功能描述

获取与指定 Grafana 图表相关的监控策略。

### 请求参数

| 字段 | 类型 | 必选 | 描述 |
|------|------|------|------|
| bk_biz_id | int | 是 | 业务ID |
| dashboard_uid | string | 是 | 仪表盘UID |
| panel_id | int | 否 | 图表ID |

### 请求参数示例
```json
{
    "bk_biz_id": 1,
    "dashboard_uid": "dashboard-uid",
    "panel_id": 1
}
```

### 响应参数

| 字段 | 类型 | 描述 |
|------|------|------|
| dashboard_uid | string | 仪表盘UID |
| variables | object | 变量映射,格式为{"变量名": ["变量值"]} |
| panel_id | int | 图表ID |
| ref_id | string | 图表RefID |
| strategy_id | int | 策略ID |
| strategy_name | string | 策略名称 |
| is_enabled | bool | 策略是否启用 |
| is_invalid | bool | 策略是否无效 |
| invalid_type | string | 策略无效类型 |


### 响应参数示例
```json
[
    {
        "dashboard_uid": "dashboard-uid",
        "variables": {"var1": ["value1"]},
        "panel_id": 1,
        "ref_id": "A",
        "strategy_id": 1,
        "strategy_name": "CPU使用率告警",
        "is_enabled": true,
        "is_invalid": false,
        "invalid_type": ""
    }
]

```