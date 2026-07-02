## 功能描述

查询指定索引集的日志聚类配置。

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

url = "https://example.com/clustering_config/1001/config/"
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
        "collector_config_id": 1,
        "index_set_id": 1001,
        "bk_biz_id": 2,
        "min_members": 1,
        "max_dist_list": "0.1,0.3,0.5,0.7,0.9",
        "predefined_varibles": "",
        "delimeter": "",
        "max_log_length": 1000,
        "clustering_fields": "log",
        "filter_rules": []
    }
}
```

### 返回结果说明

| 参数名称            | 参数类型 | 参数说明             |
| ------------------- | -------- | -------------------- |
| collector_config_id | int      | 采集项 ID            |
| index_set_id        | int      | 索引集 ID            |
| clustering_fields   | string   | 参与聚类的字段       |
| min_members         | int      | 最小聚类数量         |
| max_dist_list       | string   | 聚类敏感度列表       |
| max_log_length      | int      | 最大日志长度         |
| filter_rules        | list     | 聚类过滤规则         |
