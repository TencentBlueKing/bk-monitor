## 功能描述

获取指定动作和资源的权限申请数据及申请链接。

## 请求参数

请求方式：`POST /iam/meta/get_apply_data/`，`Content-Type: application/json`。

### 鉴权头

| 参数名称 | 参数类型 | 必须 | 参数说明 |
| --- | --- | --- | --- |
| bk_app_code | string | 是 | 蓝鲸应用 ID |
| bk_app_secret | string | 是 | 蓝鲸应用密钥 |
| bk_username | string | 是 | 当前操作用户的用户名 |

鉴权信息通过请求头 `X-Bkapi-Authorization` 传递，取值为上述字段构成的 JSON 字符串。

### 参数列表

| 字段 | 类型 | 必选 | 描述 |
| --- | --- | --- | --- |
| action_ids | list[string] | 否 | 待申请的动作 ID 列表，如 `view_business_v2`、`create_collection_v2`，默认空列表 |
| resources | list[dict] | 否 | 待申请的资源列表，默认空列表；有关联资源的动作应传入对应资源，见下表 |

### resources 参数

| 字段 | 类型 | 必选 | 描述 |
| --- | --- | --- | --- |
| type | string | 是 | 资源类型：`space`（空间/业务）、`collection`（采集项）、`indices`（索引集）、`es_source`（ES 源） |
| id | string | 是 | 资源实例 ID；`space` 使用空间的 `bk_biz_id`，其他类型使用对应资源 ID |

## 请求参数示例

获取业务 2 的采集新建权限申请信息：

```json
{
  "action_ids": ["create_collection_v2"],
  "resources": [
    {
      "type": "space",
      "id": "2"
    }
  ]
}
```

## 返回结果示例

以下为 IAM V3 模式的返回示例：

```json
{
  "result": true,
  "code": 0,
  "message": "",
  "data": {
    "apply_data": {
      "system_id": "bk_log_search",
      "system_name": "日志平台",
      "actions": [
        {
          "id": "create_collection_v2",
          "name": "采集新建",
          "related_resource_types": [
            {
              "system_id": "bk_monitorv3",
              "system_name": "监控平台",
              "type": "space",
              "type_name": "空间",
              "instances": [
                [
                  {
                    "type": "space",
                    "type_name": "空间",
                    "id": "2",
                    "name": "[业务] 示例业务"
                  }
                ]
              ]
            }
          ]
        }
      ]
    },
    "apply_url": "https://iam.example.com/apply-custom-perm?token=example"
  }
}
```

### 返回结果说明

| 字段 | 类型 | 描述 |
| --- | --- | --- |
| result | bool | 请求是否成功 |
| code | int | 返回状态码，`0` 表示成功 |
| message | string | 描述信息 |
| data | dict | 权限申请信息 |
| data.apply_data | dict | 用于展示申请内容的数据 |
| data.apply_data.provider | string | 申请来源，IAM V4 返回 `v4`，IAM V3 不返回该字段 |
| data.apply_data.system_id | string | 日志平台权限系统 ID |
| data.apply_data.system_name | string | 日志平台权限系统名称 |
| data.apply_data.actions | list | 待申请的动作列表 |
| data.apply_data.actions[].id | string | 动作 ID，具体名称与申请链接对应的权限模型一致 |
| data.apply_data.actions[].name | string | 动作名称 |
| data.apply_data.actions[].related_resource_types | list | 动作关联的资源类型列表 |
| data.apply_data.actions[].related_resource_types[].system_id | string | 资源所属权限系统 ID |
| data.apply_data.actions[].related_resource_types[].system_name | string | 资源所属权限系统名称 |
| data.apply_data.actions[].related_resource_types[].type | string | 资源类型 |
| data.apply_data.actions[].related_resource_types[].type_name | string | 资源类型名称 |
| data.apply_data.actions[].related_resource_types[].instances | list[list[dict]] | 资源实例链；每个节点包含 `type`、`type_name`、`id`、`name` |
| data.apply_url | string | 权限申请链接 |

## 注意事项

- 本接口不检查当前用户已有或缺少哪些权限，也不直接授予权限；检查已有权限应调用 `/iam/meta/check_allowed/`。
- 请求中的动作 ID 使用日志平台定义的名称，如 `create_collection_v2`。IAM V4 及双栈模式返回的申请数据中，动作 ID 去除 `_v2` 后缀，资源所属系统为日志平台自身系统；调用方应直接使用返回的申请数据和链接。
- 申请信息不可用时可能返回 `apply_data={}` 和空的 `apply_url`，调用方应检查链接是否为空。
