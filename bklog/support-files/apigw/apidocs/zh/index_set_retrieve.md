## 功能描述

查询指定索引集的详情。

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
response = requests.get(url, headers=headers)
print(response.json())
```

## 返回结果示例

```json
{
    "result": true,
    "code": 0,
    "message": "",
    "data": {
        "index_set_id": 1001,
        "index_set_name": "应用运行日志",
        "space_uid": "bkcc__2",
        "scenario_id": "bkdata",
        "scenario_name": "计算平台",
        "storage_cluster_id": 15,
        "category_id": "other_rt",
        "indexes": [
            {
                "bk_biz_id": 2,
                "result_table_id": "2_bklog.app",
                "time_field": "dtEventTimeStamp",
                "apply_status": "normal"
            }
        ],
        "time_field": "dtEventTimeStamp",
        "time_field_type": "date",
        "time_field_unit": "microsecond",
        "target_fields": ["path", "bk_host_id"],
        "sort_fields": ["gseIndex"],
        "is_active": true,
        "created_by": "user",
        "created_at": "2026-07-01 11:11:11+0800"
    }
}
```
