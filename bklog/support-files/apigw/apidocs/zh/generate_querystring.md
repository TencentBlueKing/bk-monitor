## 功能描述

将结构化检索条件转换为日志检索使用的 QueryString。

## 请求参数

### 鉴权头

| 参数名称      | 参数类型 | 必须 | 参数说明     |
| ------------- | -------- | ---- | ------------ |
| bk_app_code   | string   | 是   | 蓝鲸应用 ID  |
| bk_app_secret | string   | 是   | 蓝鲸应用秘钥 |
| bk_username   | string   | 是   | 用户名称     |

鉴权信息通过请求头 `X-Bkapi-Authorization` 传递，取值为上述字段构成的 JSON 字符串。

### 参数列表

| 字段     | 类型            | 必选 | 描述                 |
| -------- | --------------- | ---- | -------------------- |
| addition | list[condition] | 是   | 需要转换的结构化条件 |

#### condition

| 字段     | 类型   | 必选 | 描述                                             |
| -------- | ------ | ---- | ------------------------------------------------ |
| field    | string | 是   | 字段名                                           |
| operator | string | 是   | 操作符，例如 `=`, `!=`, `contains match phrase` |
| value    | list   | 是   | 条件值列表                                       |

## 调用示例

```python
import json

import requests

url = "https://example.com/search/index_set/generate_querystring/"
headers = {
    "X-Bkapi-Authorization": json.dumps({
        "bk_app_code": "your app code",
        "bk_app_secret": "your app secret",
        "bk_username": "your name",
    })
}
data = {
    "addition": [
        {"field": "level", "operator": "=", "value": ["ERROR", "WARN"]},
        {"field": "service", "operator": "!=", "value": ["healthcheck"]},
    ]
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
    "querystring": "level: (\"ERROR\" OR \"WARN\") AND NOT service: \"healthcheck\""
  }
}
```

### 返回结果说明

| 参数名称    | 参数类型 | 参数说明                      |
| ----------- | -------- | ----------------------------- |
| querystring | string   | 转换生成的 QueryString 字符串 |
