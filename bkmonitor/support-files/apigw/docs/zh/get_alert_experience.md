### 功能描述

获取告警处理经验

### 请求参数

| 字段        | 类型   | 必选 | 描述                                      |
|-----------|------|----|------------------------------------------|
| bk_biz_id | int  | 是  | 业务ID                                    |
| alert_id  | str  | 否  | 告警ID（alert_id和metric_id至少提供一个）          |
| metric_id | str  | 否  | 指标ID（alert_id和metric_id至少提供一个，多个指标用逗号分隔） |

**注意**：`alert_id` 和 `metric_id` 不能同时为空，至少需要提供其中一个参数。

### 请求参数示例

**通过告警ID查询：**

```json
{
    "bk_biz_id": 2,
    "alert_id": "16424876305819838"
}
```

**通过指标ID查询：**

```json
{
    "bk_biz_id": 2,
    "metric_id": "system.cpu.usage,system.mem.usage"
}
```

### 响应参数

| 字段      | 类型     | 描述     |
|---------|--------|--------|
| result  | bool   | 请求是否成功 |
| code    | int    | 返回的状态码 |
| message | string | 描述信息   |
| data    | list   | 返回数据   |

#### data 元素字段说明

| 字段          | 类型     | 描述                                                    |
|-------------|--------|-------------------------------------------------------|
| id          | int    | 处理经验ID                                               |
| bk_biz_id   | int    | 业务ID                                                 |
| alert_name  | string | 告警名称                                                 |
| metric      | list   | 指标列表                                                 |
| type        | string | 类型，可选值：\"metric\"（指标级别）、\"dimension\"（维度级别）            |
| conditions  | list   | 匹配条件列表（仅dimension类型有效）                               |
| description | string | 处理经验描述                                               |
| is_match    | bool   | 是否匹配当前告警（true表示完全匹配，false表示不匹配或部分匹配）                |
| create_user | string | 创建人                                                  |
| create_time | string | 创建时间                                                 |
| update_user | string | 更新人                                                  |
| update_time | string | 更新时间                                                 |

#### conditions 元素字段说明

| 字段        | 类型     | 描述                                    |
|-----------|--------|---------------------------------------|
| key       | string | 维度键名                                 |
| value     | list   | 维度值列表                                |
| method    | string | 匹配方法，如\"eq\"（等于）、\"neq\"（不等于）、\"reg\"（正则） |
| condition | string | 条件关系，如\"and\"、\"or\"                   |

### 响应参数示例

```json
{
    "result": true,
    "code": 200,
    "message": "OK",
    "data": [
        {
            "id": 1,
            "bk_biz_id": 2,
            "alert_name": "CPU使用率过高",
            "metric": ["system.cpu.usage"],
            "type": "metric",
            "conditions": [],
            "description": "1. 检查是否有异常进程占用CPU\n2. 查看系统负载情况\n3. 必要时重启相关服务",
            "is_match": true,
            "create_user": "admin",
            "create_time": "2024-01-01 10:00:00",
            "update_user": "admin",
            "update_time": "2024-01-01 10:00:00"
        },
        {
            "id": 2,
            "bk_biz_id": 2,
            "alert_name": "CPU使用率过高",
            "metric": ["system.cpu.usage"],
            "type": "dimension",
            "conditions": [
                {
                    "key": "ip",
                    "value": ["127.0.0.1"],
                    "method": "eq",
                    "condition": "and"
                }
            ],
            "description": "针对特定IP的处理建议",
            "is_match": false,
            "create_user": "admin",
            "create_time": "2024-01-02 10:00:00",
            "update_user": "admin",
            "update_time": "2024-01-02 10:00:00"
        }
    ]
}
```
