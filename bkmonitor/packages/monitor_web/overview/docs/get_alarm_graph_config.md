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
| strategy_ids | list | 策略ID |

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
        {"name": "主机告警", "strategy_ids": [1, 2, 3]},
        {"name": "服务告警", "strategy_ids": [4, 5, 6]}
    ],
    "tags": [
        {"bk_biz_id": 2, "bk_biz_name": "蓝鲸"},
        {"bk_biz_id": 3, "bk_biz_name": "业务3"}
    ]
}
```
