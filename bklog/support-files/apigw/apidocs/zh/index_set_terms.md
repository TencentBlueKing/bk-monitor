## 功能描述

对指定索引集的一个或多个字段执行 terms 聚合，返回字段值及对应的日志数量。

## 请求参数

### 鉴权头

| 参数名称      | 参数类型 | 必须 | 参数说明     |
| ------------- | -------- | ---- | ------------ |
| bk_app_code   | string   | 是   | 蓝鲸应用 ID  |
| bk_app_secret | string   | 是   | 蓝鲸应用秘钥 |
| bk_username   | string   | 是   | 用户名称     |

鉴权信息通过请求头 `X-Bkapi-Authorization` 传递，取值为上述字段构成的 JSON 字符串。

### 路径参数

| 字段         | 类型 | 必选 | 描述      |
| ------------ | ---- | ---- | --------- |
| index_set_id | int  | 是   | 索引集 ID |

### 参数列表

| 字段           | 类型         | 必选 | 描述                                                    |
| -------------- | ------------ | ---- | ------------------------------------------------------- |
| fields         | list[string] | 是   | 需要聚合的字段列表                                      |
| start_time     | string/int   | 否   | 查询开始时间，支持时间字符串或时间戳                    |
| end_time       | string/int   | 否   | 查询结束时间，支持时间字符串或时间戳                    |
| time_range     | string       | 否   | 相对时间范围标识                                        |
| time_dimension | int          | 否   | 默认查询最近 1 天；传 `-1` 表示不限制时间范围           |
| keyword        | string       | 否   | 日志检索关键字                                          |
| addition       | list         | 否   | 结构化过滤条件                                          |
| host_scopes    | object       | 否   | 主机范围过滤条件                                        |
| size           | int          | 否   | 每个字段返回的聚合桶数量，默认 `100`                    |
| order          | object       | 否   | 聚合排序，例如 `{"_count": "desc"}`                      |
| bk_biz_id      | int          | 否   | 业务 ID；启用统一查询时用于查询路由                     |

## 调用示例

```python
import json

import requests

url = "https://example.com/search/index_set/1001/aggs/terms/"
headers = {
    "X-Bkapi-Authorization": json.dumps({
        "bk_app_code": "your app code",
        "bk_app_secret": "your app secret",
        "bk_username": "your name",
    })
}
data = {
    "start_time": "2026-08-11 00:00:00",
    "end_time": "2026-08-11 23:59:59",
    "keyword": "*",
    "fields": ["level", "serverIp"],
    "size": 100,
    "order": {"_count": "desc"},
}
response = requests.post(url, headers=headers, json=data)
print(response.json())
```

## 返回结果示例

```json
{
  "result": true,
  "code": 0,
  "message": "",
  "data": {
    "aggs": {
      "level": [
        ["INFO", 120],
        ["ERROR", 8]
      ]
    },
    "aggs_items": {
      "level": ["INFO", "ERROR"]
    }
  }
}
```

### 返回结果说明

| 参数名称   | 参数类型 | 参数说明                                   |
| ---------- | -------- | ------------------------------------------ |
| aggs       | object   | 各字段的聚合结果，元素为 `[字段值, 数量]` |
| aggs_items | object   | 各字段的聚合值列表                         |
