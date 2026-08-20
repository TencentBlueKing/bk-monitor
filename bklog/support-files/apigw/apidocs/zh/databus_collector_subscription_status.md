## 功能描述

查询单个日志采集项当前订阅运行状态。物理机和 Windows 返回采集器插件实例状态；容器采集返回容器子配置状态。

## 请求参数

### 鉴权头

| 参数名称 | 参数类型 | 必须 | 参数说明 |
| --- | --- | --- | --- |
| app_code | string | 是 | 蓝鲸应用 ID |
| app_secret | string | 是 | 蓝鲸应用密钥 |
| bk_username | string | 是 | 当前用户名 |

鉴权信息通过请求头 `X-Bkapi-Authorization` 传递。

### 路径参数

| 字段 | 类型 | 必选 | 描述 |
| --- | --- | --- | --- |
| collector_config_id | int | 是 | 采集项 ID |

### 查询参数

| 字段 | 类型 | 必选 | 描述 |
| --- | --- | --- | --- |
| include_plugin_status | bool | 否 | 是否查询插件名称与版本，默认 `true`；仅关心运行状态时可设为 `false` |

## 调用示例

```python
import json
import requests

url = "https://example.com/databus_collectors/1001/subscription_status/"
headers = {
    "X-Bkapi-Authorization": json.dumps({
        "bk_app_code": "your app code",
        "bk_app_secret": "your app secret",
        "bk_username": "your name",
    })
}
response = requests.get(url, headers=headers, params={"include_plugin_status": False})
print(response.json())
```

## 返回结果示例

```json
{
  "result": true,
  "code": 0,
  "message": "",
  "data": {
    "contents": [
      {
        "child": [
          {
            "status": "SUCCESS",
            "instance_id": "host|instance|host|127.0.0.1-0-0",
            "plugin_version": "3.0.10"
          }
        ]
      }
    ]
  }
}
```
