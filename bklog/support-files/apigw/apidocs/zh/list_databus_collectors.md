## 功能描述

分页查询普通日志采集项列表，运行状态需通过异步状态接口获取。

## 请求参数

### 鉴权头

| 参数名称    | 参数类型 | 必须 | 参数说明     |
| ----------- | -------- | ---- | ------------ |
| app_code    | string   | 是   | 蓝鲸应用ID   |
| app_secret  | string   | 是   | 蓝鲸应用秘钥 |
| bk_username | string   | 是   | 用户名称     |

鉴权信息通过请求头 `X-Bkapi-Authorization` 传递，取值为上述字段构成的 JSON 字符串。

### 参数列表

| 字段              | 类型   | 必选 | 描述                                       |
| ----------------- | ------ | ---- | ------------------------------------------ |
| bk_biz_id         | int    | 是   | 业务 ID                                    |
| page              | int    | 是   | 页码                                       |
| pagesize          | int    | 是   | 每页条数                                   |
| keyword           | string | 否   | 采集项名称搜索关键字                       |
| collector_id_list | string | 否   | 采集项 ID 过滤，逗号分隔，如 `1,2,3`       |

## 调用示例

```python
import json
import requests

url = "https://example.com/databus_collectors/"
headers = {
    "X-Bkapi-Authorization": json.dumps({
        "bk_app_code": "your app code",
        "bk_app_secret": "your app secret",
        "bk_username": "your name"
    })
}
params = {"bk_biz_id": 2, "page": 1, "pagesize": 20}
response = requests.get(url, headers=headers, params=params)
print(response.json())
```

## 返回结果示例

```json
{
    "result": true,
    "code": 0,
    "message": "",
    "data": {
        "count": 10,
        "total_page": 1,
        "results": [
            {
                "collector_config_id": 1,
                "collector_config_name": "应用运行日志",
                "collector_scenario_id": "row",
                "collector_scenario_name": "行日志",
                "category_id": "os",
                "bk_biz_id": 2,
                "is_active": true,
                "created_by": "user",
                "created_at": "2026-07-01 11:11:11"
            }
        ]
    }
}
```

### 返回结果说明

| 参数名称                     | 参数类型 | 参数说明   |
| ---------------------------- | -------- | ---------- |
| count                        | int      | 总数       |
| total_page                   | int      | 总页数     |
| results                      | array    | 采集项列表 |
| results.collector_config_id  | int      | 采集项 ID  |
| results.collector_config_name | string  | 采集项名称 |
| results.collector_scenario_id | string  | 采集类型   |
| results.category_id          | string   | 数据分类   |
| results.is_active            | bool     | 是否启用   |
