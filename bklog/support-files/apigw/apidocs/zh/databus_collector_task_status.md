## 功能描述

查询单个日志采集项最近一次部署任务的执行状态。物理机和 Windows 返回节点管理任务实例；容器采集返回容器子配置的下发状态。

## 请求参数

### 鉴权头

| 参数名称 | 参数类型 | 必须 | 参数说明 |
| --- | --- | --- | --- |
| app_code | string | 是 | 蓝鲸应用 ID |
| app_secret | string | 是 | 蓝鲸应用密钥 |
| bk_username | string | 是 | 当前用户名 |

鉴权信息通过请求头 `X-Bkapi-Authorization` 传递。

### 路径与查询参数

| 字段 | 位置 | 类型 | 必选 | 描述 |
| --- | --- | --- | --- | --- |
| collector_config_id | path | int | 是 | 采集项 ID |
| task_id_list | query | string | 否 | 任务 ID，多个值用半角逗号分隔；只读模式不传时返回未就绪 |
| read_only | query | bool | 否 | 是否严格只读，默认 `true`；采集项没有订阅或任务 ID 时直接返回未就绪，不触发订阅创建。仅兼容旧调用时可显式传 `false`，该模式可能创建订阅并要求采集管理权限 |

## 调用示例

```python
import json
import requests

url = "https://example.com/databus_collectors/1001/task_status/"
headers = {
    "X-Bkapi-Authorization": json.dumps({
        "bk_app_code": "your app code",
        "bk_app_secret": "your app secret",
        "bk_username": "your name",
    })
}
response = requests.get(url, headers=headers, params={"task_id_list": "101,102", "read_only": True})
print(response.json())
```

## 返回结果示例

```json
{
  "result": true,
  "code": 0,
  "message": "",
  "data": {
    "task_ready": true,
    "contents": [
      {
        "child": [
          {
            "status": "SUCCESS",
            "task_id": 101,
            "instance_id": "host|instance|host|127.0.0.1-0-0"
          }
        ]
      }
    ]
  }
}
```
