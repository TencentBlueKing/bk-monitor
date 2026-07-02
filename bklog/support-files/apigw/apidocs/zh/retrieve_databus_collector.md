## 功能描述

查询普通日志采集项详情，返回采集场景、目标范围、采集配置、清洗配置与存储信息等。

## 请求参数

### 鉴权头

| 参数名称    | 参数类型 | 必须 | 参数说明     |
| ----------- | -------- | ---- | ------------ |
| app_code    | string   | 是   | 蓝鲸应用ID   |
| app_secret  | string   | 是   | 蓝鲸应用秘钥 |
| bk_username | string   | 是   | 用户名称     |

鉴权信息通过请求头 `X-Bkapi-Authorization` 传递，取值为上述字段构成的 JSON 字符串。

### 路径参数

| 字段                | 类型 | 必选 | 描述      |
| ------------------- | ---- | ---- | --------- |
| collector_config_id | int  | 是   | 采集项 ID |

## 调用示例

```python
import json
import requests

url = "https://example.com/databus_collectors/1001/"
headers = {
    "X-Bkapi-Authorization": json.dumps({
        "bk_app_code": "your app code",
        "bk_app_secret": "your app secret",
        "bk_username": "your name"
    })
}
response = requests.get(url, headers=headers)
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
        "collector_config_name_en": "app_runtime_log",
        "collector_scenario_id": "row",
        "category_id": "os",
        "bk_biz_id": 2,
        "target_object_type": "HOST",
        "target_node_type": "TOPO",
        "target_nodes": [{"bk_inst_id": 2, "bk_obj_id": "biz"}],
        "params": {
            "paths": ["/var/log/app/*.log"],
            "conditions": {"type": "match"}
        },
        "etl_config": "bk_log_text",
        "storage_cluster_id": 1,
        "retention": 7,
        "index_set_id": 2001,
        "is_active": true
    }
}
```
