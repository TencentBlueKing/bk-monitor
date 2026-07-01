## 功能描述

查询当前调用方在指定空间内有日志检索权限的索引集列表。

## 请求参数

### 鉴权头

| 参数名称    | 参数类型 | 必须 | 参数说明     |
| ----------- | -------- | ---- | ------------ |
| app_code    | string   | 是   | 蓝鲸应用ID   |
| app_secret  | string   | 是   | 蓝鲸应用秘钥 |
| bk_username | string   | 是   | 用户名称     |

鉴权信息通过请求头 `X-Bkapi-Authorization` 传递，取值为上述字段构成的 JSON 字符串。

### 参数列表

| 字段      | 类型   | 必选 | 描述                                   |
| --------- | ------ | ---- | -------------------------------------- |
| space_uid | string | 是   | 空间唯一标识，例如 `bkcc__2`           |
| is_group  | bool   | 否   | 是否按索引组分组展示，默认 `false`     |

## 调用示例

```python
import json
import requests

url = "https://example.com/search_index_set/"
headers = {
    "X-Bkapi-Authorization": json.dumps({
        "bk_app_code": "your app code",
        "bk_app_secret": "your app secret",
        "bk_username": "your name"
    })
}
params = {"space_uid": "bkcc__2", "is_group": False}
response = requests.get(url, headers=headers, params=params)
print(response.json())
```

## 返回结果示例

```json
{
    "result": true,
    "code": 0,
    "message": "",
    "data": [
        {
            "index_set_id": 1,
            "index_set_name": "索引集名称",
            "scenario_id": "接入场景",
            "scenario_name": "接入场景名称",
            "storage_cluster_id": "存储集群ID",
            "indices": [
                {
                    "result_table_id": "结果表id",
                    "result_table_name": "结果表名称"
                }
            ],
            "time_field": "dtEventTimeStamp",
            "time_field_type": "date",
            "time_field_unit": "microsecond",
            "tags": [{"name": "test", "color": "xxx"}],
            "is_favorite": true
        }
    ]
}
```

### 返回结果说明

| 参数名称     | 参数类型 | 参数说明             |
| ------------ | -------- | -------------------- |
| index_set_id | int      | 索引集 ID            |
| index_set_name | string | 索引集名称           |
| scenario_id  | string   | 接入场景             |
| indices      | list     | 索引集包含的结果表   |
| time_field   | string   | 时间字段             |
| tags         | list     | 索引集标签           |
| is_favorite  | bool     | 是否为收藏索引集     |
