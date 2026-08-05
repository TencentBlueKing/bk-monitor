## 功能描述

删除指定索引集下日志聚类 Pattern 的已有标注。只能删除当前用户创建、且创建时间和内容均匹配的标注。

## 请求参数

### 鉴权头

以下两种鉴权方式二选一，不得混用。鉴权信息通过请求头 `X-Bkapi-Authorization` 传递，取值为对应字段构成的 JSON 字符串。

| 鉴权方式 | 参数名称 | 参数类型 | 必须 | 参数说明 |
| --- | --- | --- | --- | --- |
| 应用凭据 + 用户登录态 | app_code | string | 是 | 蓝鲸应用 ID |
| 应用凭据 + 用户登录态 | app_secret | string | 是 | 蓝鲸应用秘钥 |
| 应用凭据 + 用户登录态 | bk_token | string | 是 | 蓝鲸用户登录态 Token，用于校验用户身份 |
| Access Token | access_token | string | 是 | 同时包含应用和用户身份的 Access Token，必须单独使用 |

应用凭据 + 用户登录态方式：

```http
X-Bkapi-Authorization: {"bk_app_code":"your app code","bk_app_secret":"your app secret","bk_token":"your user token"}
```

Access Token 方式：

```http
X-Bkapi-Authorization: {"access_token":"your access token"}
```

使用 `access_token` 时，不要同时传递 `bk_app_code`、`bk_app_secret`、`bk_token` 或 `bk_username`。

### 路径参数

| 字段 | 类型 | 必选 | 描述 |
| --- | --- | --- | --- |
| index_set_id | int | 是 | 索引集 ID |

### 参数列表

| 字段 | 类型 | 必选 | 描述 |
| --- | --- | --- | --- |
| signature | string | 是 | Pattern 数据指纹，取自日志聚类查询结果中的 `data[].signature` |
| remark | string | 是 | 要删除的标注内容 |
| create_time | int | 是 | 待删除标注的创建时间，取自 `data.remark[]` 中对应条目的 `create_time`，单位为毫秒 |
| origin_pattern | string | 是 | Pattern 原始内容；没有原始 Pattern 时可传空字符串或 `null` |
| groups | object | 否 | Pattern 的分组字段和值，例如按 `serverIp`、`cloudId` 分组时传对应值；无分组时默认 `{}` |

## 调用示例

```python
import json
import requests

url = "https://example.com/pattern/1001/delete_remark/"
headers = {
    "X-Bkapi-Authorization": json.dumps({
        "bk_app_code": "your app code",
        "bk_app_secret": "your app secret",
        "bk_token": "your user token",
    })
}
payload = {
    "signature": "c0cc23b8686d931187fcd5ad636ce630",
    "remark": "数据库连接超时",
    "create_time": 1785746100000,
    "origin_pattern": "connect failed host=* port=*",
    "groups": {
        "serverIp": "127.0.0.1",
        "cloudId": "0"
    },
}

response = requests.delete(url, headers=headers, json=payload)
print(response.json())
```

## 请求参数示例

```json
{
  "signature": "c0cc23b8686d931187fcd5ad636ce630",
  "remark": "数据库连接超时",
  "create_time": 1785746100000,
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
    "updated_at": "2026-08-03T08:40:00Z",
    "updated_by": "bkms_user",
    "is_deleted": false,
    "deleted_at": null,
    "deleted_by": null
  }
}
```
