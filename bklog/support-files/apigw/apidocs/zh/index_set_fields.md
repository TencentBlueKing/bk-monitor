## 功能描述

查询指定索引集的字段配置，返回字段列表、展示字段与排序字段。

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

### 参数列表

| 字段          | 类型   | 必选 | 描述                                                    |
| ------------- | ------ | ---- | ------------------------------------------------------- |
| scope         | string | 否   | 字段使用范围，枚举 `default`、`search_context`，默认 `default` |

## 调用示例

```python
import json
import requests

url = "https://example.com/search_index_set/1001/fields/"
headers = {
    "X-Bkapi-Authorization": json.dumps({
        "bk_app_code": "your app code",
        "bk_app_secret": "your app secret",
        "bk_username": "your name"
    })
}
response = requests.get(url, headers=headers, params={"scope": "default"})
print(response.json())
```

## 返回结果示例

```json
{
    "result": true,
    "code": 0,
    "message": "",
    "data": {
        "display_fields": ["dtEventTimeStamp", "log"],
        "fields": [
            {
                "field_name": "log",
                "field_alias": "日志",
                "field_type": "text",
                "is_display": true,
                "is_editable": true,
                "description": "日志",
                "es_doc_values": false
            },
            {
                "field_name": "dtEventTimeStamp",
                "field_alias": "时间",
                "field_type": "date",
                "is_display": true,
                "is_editable": true,
                "description": "数据时间",
                "es_doc_values": true
            }
        ],
        "sort_list": [],
        "time_field": "dtEventTimeStamp",
        "time_field_type": "date",
        "time_field_unit": "microsecond"
    }
}
```

### 返回结果说明

| 参数名称        | 参数类型 | 参数说明                        |
| --------------- | -------- | ------------------------------- |
| fields          | list     | 字段列表                        |
| fields.field_name | string | 字段名                          |
| fields.field_alias | string | 字段别名（为空时取 description）|
| fields.field_type | string | 字段类型                        |
| fields.is_analyzed | bool  | 是否分词字段                    |
| fields.es_doc_values | bool | 是否聚合字段                   |
| display_fields  | list     | 列表页默认展示的字段            |
| time_field      | string   | 时间字段                        |
