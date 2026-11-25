## 功能描述

检查当前用户对指定动作和资源是否有权限。

## 请求参数

### 鉴权头

| 参数名称 | 参数类型 | 必须 | 参数说明 |
| --- | --- | --- | --- |
| bk_app_code | string | 是 | 蓝鲸应用 ID |
| bk_app_secret | string | 是 | 蓝鲸应用密钥 |
| bk_username | string | 是 | 检查权限的用户名 |

鉴权信息通过请求头 `X-Bkapi-Authorization` 传递，取值为上述字段构成的 JSON 字符串。

### 参数列表

| 字段 | 类型 | 必选 | 描述 |
| --- | --- | --- | --- |
| action_ids | list[string] | 否 | 待检查的动作 ID 列表，如 `view_business_v2`、`create_collection_v2`；默认空列表，不传时返回空列表 |
| resources | list[dict] | 否 | 资源列表，默认空列表；有关联资源的动作应传入对应资源，见下表 |

### resources 参数

| 字段 | 类型 | 必选 | 描述 |
| --- | --- | --- | --- |
| type | string | 是 | 资源类型：`space`（空间/业务）、`collection`（采集项）、`indices`（索引集）、`es_source`（ES 源） |
| id | string | 是 | 资源实例 ID；`space` 使用空间的 `bk_biz_id`，其他类型使用对应资源 ID |

## 请求参数示例

检查用户是否有业务 2 的访问和采集新建权限：

```json
{
  "action_ids": ["view_business_v2", "create_collection_v2"],
  "resources": [
    {
      "type": "space",
      "id": "2"
    }
  ]
}
```

## 返回结果示例

```json
{
  "result": true,
  "code": 0,
  "message": "",
  "data": [
    {
      "action_id": "view_business_v2",
      "is_allowed": true
    },
    {
      "action_id": "create_collection_v2",
      "is_allowed": false
    }
  ]
}
```

### 返回结果说明

| 字段 | 类型 | 描述 |
| --- | --- | --- |
| result | bool | 请求是否成功，不表示用户有权限 |
| code | int | 返回状态码，`0` 表示成功 |
| message | string | 描述信息 |
| data | list | 各动作的权限检查结果，顺序与 `action_ids` 一致 |
| data[].action_id | string | 请求中的动作 ID |
| data[].is_allowed | bool | 当前用户对指定动作和资源是否有权限 |

## 注意事项

- 应根据 `data[].is_allowed` 判断权限，外层 `result=true` 仅表示请求执行成功。
