## 功能描述

删除指定索引集。删除操作需要索引集管理权限，调用前请确认该索引集不再被业务使用。

## 请求参数

### 鉴权头

| 参数名称    | 参数类型 | 必须 | 参数说明     |
| ----------- | -------- | ---- | ------------ |
| app_code    | string   | 是   | 蓝鲸应用ID   |
| app_secret  | string   | 是   | 蓝鲸应用秘钥 |
| bk_username | string   | 是   | 用户名称     |

鉴权信息通过请求头 `X-Bkapi-Authorization` 传递，取值为上述字段构成的 JSON 字符串。

### 路径参数

| 字段         | 类型 | 必选 | 描述      |
| ------------ | ---- | ---- | --------- |
| index_set_id | int  | 是   | 索引集 ID |

## 调用示例

```python
import json
import requests

url = "https://example.com/index_set/1001/"
headers = {
    "X-Bkapi-Authorization": json.dumps({
        "bk_app_code": "your app code",
        "bk_app_secret": "your app secret",
        "bk_username": "your name"
    })
}
response = requests.delete(url, headers=headers)
print(response.json())
```

## 返回结果示例

```json
{
    "result": true,
    "code": 0,
    "message": "",
    "data": null
}
```
