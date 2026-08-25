## 功能描述

返回 Fast Update 字段校验所需的最小采集项上下文，不读取清洗、存储、目标或订阅详情。

## 请求参数

### 鉴权头

| 参数名称 | 参数类型 | 必须 | 参数说明 |
| --- | --- | --- | --- |
| app_code | string | 是 | 蓝鲸应用 ID |
| app_secret | string | 是 | 蓝鲸应用密钥 |
| bk_username | string | 是 | 当前用户名 |

### 路径与查询参数

| 字段 | 位置 | 类型 | 必选 | 描述 |
| --- | --- | --- | --- | --- |
| collector_config_id | path | int | 是 | 采集项 ID |
| enforce_permission | query | bool | 否 | 白名单应用是否仍强制按当前用户校验采集项管理权限，默认 `false` |

## 调用示例

```python
import json
import requests

url = "https://example.com/databus_collectors/1001/update_context/"
headers = {
    "X-Bkapi-Authorization": json.dumps({
        "bk_app_code": "your app code",
        "bk_app_secret": "your app secret",
        "bk_username": "your name",
    })
}
response = requests.get(url, headers=headers, params={"enforce_permission": True})
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
    "bk_biz_id": 2,
    "environment": "container",
    "collector_scenario_id": "row",
    "yaml_config_enabled": false,
    "subscription_id": null
  }
}
```
