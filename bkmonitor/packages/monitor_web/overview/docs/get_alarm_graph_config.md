### 功能描述

获取首页告警图配置

### 请求参数

| 字段  | 类型   | 必选 | 描述       |
|-------|--------|------|------------|
| bk_biz_id | int | 否   | 业务ID，不传则获取第一个配置 |

### 请求参数示例

```json
{
    "bk_biz_id": 2
}
```

### 响应参数

| 字段 | 类型 | 描述 |
|------|------|------|
| bk_biz_id | int | 业务ID，如果为 null，表示无配置 |
| config | object | 配置， 如果为 null，表示无配置 |
| tags | array | 标签 |

#### config 字段说明
| 字段 | 类型 | 描述 |
|------|------|------|
| name | string | 名称 |
| strategy_ids | array | 策略ID |
| status | array | 策略状态 |

#### status 字段说明
| 字段 | 类型 | 描述 |
|------|------|------|
| strategy_id | int | 策略ID |
| name | string | 策略名称 |
| status | string | 策略状态, normal: 正常, disabled: 已禁用, shielded: 已屏蔽, deleted: 已删除 |

#### tags 字段说明
| 字段 | 类型 | 描述 |
|------|------|------|
| bk_biz_id | int | 业务ID |
| bk_biz_name | string | 业务名称 |

### 响应参数示例

```json
{
    "bk_biz_id": 2,
    "config": [
        {
            "name": "主机告警",
            "strategy_ids": [1, 2, 3],
            "status": [
                {"strategy_id": 1, "name": "主机策略1", "status": "normal"},
                {"strategy_id": 2, "name": "主机策略2", "status": "disabled"},
                {"strategy_id": 3, "name": "主机策略3", "status": "shielded"}
            ]
        },
        {
            "name": "服务告警",
            "strategy_ids": [4, 5, 6],
            "status": [
                {"strategy_id": 4, "name": "服务策略1", "status": "normal"},
                {"strategy_id": 5, "name": "服务策略2", "status": "disabled"},
                {"strategy_id": 6, "name": "服务策略3", "status": "shielded"}
            ]
        }
    ],
    "tags": [
        {"bk_biz_id": 2, "bk_biz_name": "蓝鲸"},
        {"bk_biz_id": 3, "bk_biz_name": "业务3"}
    ]
}
```
