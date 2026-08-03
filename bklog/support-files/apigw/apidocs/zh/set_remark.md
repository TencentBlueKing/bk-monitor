## 功能描述

为指定索引集下的日志聚类 Pattern 新增一条标注（备注）。标注会关联 Pattern 的数据指纹、原始 Pattern 和分组信息，并记录当前调用用户。

## 请求参数

### 鉴权头

| 参数名称 | 参数类型 | 必须 | 参数说明 |
| --- | --- | --- | --- |
| app_code | string | 是 | 蓝鲸应用 ID |
| app_secret | string | 是 | 蓝鲸应用秘钥 |
| bk_token | string | 是 | 蓝鲸用户登录态 Token，用于校验用户身份 |

鉴权信息通过请求头 `X-Bkapi-Authorization` 传递，取值为上述字段构成的 JSON 字符串。也可以使用应用 + 用户 `access_token`，将 `bk_token` 替换为 `access_token`；不要通过 `bk_username` 直接传入用户名。

### 路径参数

| 字段 | 类型 | 必选 | 描述 |
| --- | --- | --- | --- |
| index_set_id | int | 是 | 索引集 ID |

### 参数列表

| 字段 | 类型 | 必选 | 描述 |
| --- | --- | --- | --- |
| signature | string | 是 | Pattern 数据指纹，取自日志聚类查询结果中的 `data[].signature` |
| remark | string | 是 | 标注内容，不能为空 |
| origin_pattern | string | 是 | Pattern 原始内容；没有原始 Pattern 时可传空字符串或 `null` |
| groups | object | 否 | Pattern 的分组字段和值，例如按 `serverIp`、`cloudId` 分组时传对应值；无分组时默认 `{}` |

## 调用示例

```python
import json
import requests

url = "https://example.com/pattern/1001/remark/"
headers = {
    "X-Bkapi-Authorization": json.dumps({
        "bk_app_code": "your app code",
        "bk_app_secret": "your app secret",
        "bk_token": "your user token",
    })
}
payload = {
    "signature": "c0cc23b8686d931187fcd5ad636ce630",
    "remark": "数据库连接异常",
    "origin_pattern": "connect failed host=* port=*",
    "groups": {
        "serverIp": "127.0.0.1",
        "cloudId": "0"
    },
}

response = requests.post(url, headers=headers, json=payload)
print(response.json())
```

## 请求参数示例

```json
{
  "signature": "c0cc23b8686d931187fcd5ad636ce630",
  "remark": "数据库连接异常",
  "origin_pattern": "connect failed host=* port=*",
  "groups": {
    "serverIp": "127.0.0.1",
    "cloudId": "0"
  }
}
```

## 返回结果示例

```json
{
  "result": true,
  "code": 0,
  "message": "",
  "data": {
    "id": 1,
    "bk_biz_id": 2,
    "signature": "c0cc23b8686d931187fcd5ad636ce630",
    "origin_pattern": "connect failed host=* port=*",
    "groups": {
      "serverIp": "127.0.0.1",
      "cloudId": "0"
    },
    "group_hash": "4a6f0e4c4cf7b1e1f4d5f3fb6e0a1c2d",
    "remark": [
      {
        "remark": "数据库连接异常",
        "username": "bkms_user",
        "create_time": 1785745800000
      }
    ],
    "owners": [],
    "strategy_id": 0,
    "strategy_enabled": false,
    "source_app_code": "bkms",
    "notice_group_id": 0,
    "created_at": "2026-08-03T08:30:00Z",
    "created_by": "bkms_user",
    "updated_at": "2026-08-03T08:30:00Z",
    "updated_by": "bkms_user",
    "is_deleted": false,
    "deleted_at": null,
    "deleted_by": null
  }
}
```
