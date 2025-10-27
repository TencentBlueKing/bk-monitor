### 功能描述

导出配置到指定业务，支持将策略配置和视图配置从一个业务导出到另一个业务。

### 请求参数

| 字段                | 类型 | 必选 | 描述                     |
| ------------------- | ---- | ---- | ------------------------ |
| bk_biz_id           | int  | 是   | 当前业务ID               |
| strategy_config_ids | list | 否   | 需要导出的策略配置ID列表 |
| view_config_ids     | list | 否   | 需要导出的视图配置ID列表 |
| target_bk_biz_id    | int  | 是   | 目标业务ID               |

### 请求参数示例

```json
{
    "bk_biz_id": 2,
    "strategy_config_ids": [1001, 1002, 1003],
    "view_config_ids": [2001, 2002],
    "target_bk_biz_id": 3
}
```

### 响应参数

| 字段    | 类型   | 描述         |
| ------- | ------ | ------------ |
| result  | bool   | 请求是否成功 |
| code    | int    | 返回的状态码 |
| message | string | 描述信息     |
| data    | dict   | 导出结果数据 |

#### data 字段说明

| 字段              | 类型 | 描述             |
| ----------------- | ---- | ---------------- |
| config_list       | list | 配置导出结果列表 |
| all_count         | dict | 总体统计信息     |
| strategy_count    | dict | 策略配置统计信息 |
| view_count        | dict | 视图配置统计信息 |
| import_history_id | int  | 导入历史记录ID   |

#### config_list 字段说明

| 字段        | 类型   | 描述                       |
| ----------- | ------ | -------------------------- |
| name        | string | 配置名称                   |
| uuid        | string | 配置UUID                   |
| file_status | string | 文件状态（success/failed） |
| error_msg   | string | 错误信息（失败时返回）     |
| label       | string | 配置标签信息               |
| type        | string | 配置类型                   |

#### all_count/strategy_count/view_count 字段说明

| 字段    | 类型 | 描述         |
| ------- | ---- | ------------ |
| total   | int  | 总配置数量   |
| success | int  | 成功导入数量 |
| failed  | int  | 失败导入数量 |

### 响应参数示例

```json
{
    "result": true,
    "code": 200,
    "message": "OK",
    "data": {
        "config_list": [
            {
                "name": "CPU使用率告警",
                "uuid": "abc123-def456",
                "file_status": "success",
                "error_msg": "",
                "label": "主机监控-CPU",
                "type": "strategy"
            },
            {
                "name": "内存使用率告警",
                "uuid": "ghi789-jkl012",
                "file_status": "failed",
                "error_msg": "目标业务不存在相关插件",
                "label": "主机监控-内存",
                "type": "strategy"
            },
            {
                "name": "业务概览视图",
                "uuid": "mno345-pqr678",
                "file_status": "success",
                "error_msg": "",
                "label": "业务视图",
                "type": "view"
            }
        ],
        "all_count": {
            "total": 3,
            "success": 2,
            "failed": 1
        },
        "strategy_count": {
            "total": 2,
            "success": 1,
            "failed": 1
        },
        "view_count": {
            "total": 1,
            "success": 1,
            "failed": 0
        },
        "import_history_id": 12345
    }
}
```

