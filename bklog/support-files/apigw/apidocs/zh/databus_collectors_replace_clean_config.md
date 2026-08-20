## 功能描述

更新或创建普通日志采集项的清洗、存储与索引集配置。接口沿用采集项实例的管理权限，并按当前用户记录操作人。

## 请求

### 鉴权头

鉴权信息通过请求头 `X-Bkapi-Authorization` 传递：

| 参数名称 | 参数类型 | 必须 | 参数说明 |
| --- | --- | --- | --- |
| bk_app_code | string | 是 | 蓝鲸应用 ID |
| bk_app_secret | string | 是 | 蓝鲸应用 Secret |
| bk_username | string | 是 | 当前操作用户 |

### 路径参数

| 字段 | 类型 | 必选 | 描述 |
| --- | --- | --- | --- |
| collector_config_id | int | 是 | 采集项 ID |

### Body 参数

| 字段 | 类型 | 必选 | 描述 |
| --- | --- | --- | --- |
| table_id | string | 是 | 结果表英文名，不含业务前缀 |
| etl_config | string | 是 | 清洗类型 |
| etl_params | object | 是 | 清洗参数 |
| fields | array | 是 | 清洗字段完整列表 |
| storage_cluster_id | int | 是 | 存储集群 ID |
| retention | int | 是 | 保留天数 |
| allocation_min_days | int | 是 | 冷热数据生效天数，`0` 表示关闭冷热 |
| storage_replies | int | 否 | ES 副本数 |
| es_shards | int | 否 | ES 分片数 |

## 调用示例

```python
import json
import requests

url = "https://example.com/databus_collectors/1001/update_or_create_clean_config/"
headers = {
    "X-Bkapi-Authorization": json.dumps({
        "bk_app_code": "your app code",
        "bk_app_secret": "your app secret",
        "bk_username": "your name"
    })
}
payload = {
    "table_id": "app_runtime_log",
    "etl_config": "bk_log_text",
    "etl_params": {"retain_original_text": False},
    "fields": [],
    "storage_cluster_id": 1,
    "retention": 7,
    "allocation_min_days": 0,
    "storage_replies": 0,
    "es_shards": 1
}
response = requests.post(url, headers=headers, json=payload)
print(response.json())
```

## 返回结果示例

```json
{
    "result": true,
    "code": 0,
    "message": "",
    "data": {
        "collector_config_id": 1001,
        "collector_config_name": "应用运行日志",
        "etl_config": "bk_log_text",
        "index_set_id": 2001,
        "scenario_id": "log",
        "storage_cluster_id": 1,
        "retention": 7,
        "es_shards": 1
    }
}
```
