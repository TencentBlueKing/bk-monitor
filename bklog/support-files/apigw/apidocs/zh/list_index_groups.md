## 功能描述

查询指定空间内的索引组列表。

## 请求参数

### 鉴权头

| 参数名称 | 参数类型 | 必须 | 参数说明 |
| --- | --- | --- | --- |
| bk_app_code | string | 是 | 蓝鲸应用 ID |
| bk_app_secret | string | 是 | 蓝鲸应用秘钥 |
| bk_username | string | 是 | 用户名称 |

鉴权信息通过请求头 `X-Bkapi-Authorization` 传递，取值为上述字段构成的 JSON 字符串。

### 参数列表

| 字段 | 类型 | 必选 | 描述 |
| --- | --- | --- | --- |
| space_uid | string | 是 | 空间唯一标识，例如 `bkcc__2` |

## 调用示例

```python
import json
import requests

url = "https://example.com/index_group/"
headers = {
    "X-Bkapi-Authorization": json.dumps({
        "bk_app_code": "your app code",
        "bk_app_secret": "your app secret",
        "bk_username": "your name",
    })
}
response = requests.get(url, headers=headers, params={"space_uid": "bkcc__2"})
print(response.json())
```

## 返回结果示例

```json
{
  "result": true,
  "code": 0,
  "message": "",
  "data": {
    "total": 1,
    "list": [
      {
        "index_set_id": 899,
        "index_set_name": "first_group",
        "index_count": 2,
        "deletable": true
      }
    ]
  }
}
```

### 返回结果说明

| 参数名称 | 参数类型 | 参数说明 |
| --- | --- | --- |
| total | int | 当前空间的采集项总数 |
| list | array | 索引组列表 |
| list.index_set_id | int | 索引组 ID，可作为 `parent_index_set_ids` 的元素 |
| list.index_set_name | string | 索引组名称 |
| list.index_count | int | 索引组包含的索引集数量 |
