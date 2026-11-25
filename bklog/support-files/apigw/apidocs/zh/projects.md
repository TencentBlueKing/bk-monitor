## 功能描述

获取项目列表及当前用户的业务访问权限。

## 请求参数

### 鉴权头

| 参数名称 | 参数类型 | 必须 | 参数说明 |
| --- | --- | --- | --- |
| bk_app_code | string | 是 | 蓝鲸应用 ID |
| bk_app_secret | string | 是 | 蓝鲸应用密钥 |
| bk_username | string | 否 | 查询业务权限的用户名；未提供用户身份时权限标记为 `false` |

鉴权信息通过请求头 `X-Bkapi-Authorization` 传递，取值为上述字段构成的 JSON 字符串。

### 参数列表

参数通过 Query String 传递。

| 字段 | 类型 | 必选 | 描述 |
| --- | --- | --- | --- |
| has_permission | bool | 否 | 默认 `false`，返回全部项目并标记当前用户的权限；设为 `true` 时仅返回有业务访问权限的项目 |

## 请求参数示例

```json
{
  "has_permission": true
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
      "project_id": 1,
      "project_name": "[2] 示例业务",
      "bk_biz_id": 2,
      "time_zone": "Asia/Shanghai",
      "project_manage": true,
      "permission": {"view_business_v2": true}
    }
  ]
}
```

### 返回结果说明

| 字段 | 类型 | 描述 |
| --- | --- | --- |
| result | bool | 请求是否成功 |
| code | int | 返回状态码，`0` 表示成功 |
| message | string | 描述信息 |
| data | list | 项目列表，过滤模式下没有有权限的项目时返回空列表 |
| data[].project_id | int | 项目 ID |
| data[].project_name | string | 项目名称，格式为 `[业务 ID] 项目名称` |
| data[].bk_biz_id | int/null | 业务 ID，无关联业务时为 `null` |
| data[].time_zone | string | 项目所在时区 |
| data[].project_manage | bool | 兼容字段，与 `permission.view_business_v2` 一致，表示业务访问权限 |
| data[].permission | dict | 当前用户的权限标记 |
| data[].permission.view_business_v2 | bool | 当前用户是否有该业务的访问权限 |

## 注意事项

- 未传 `has_permission` 时，无权限项目仍会出现在列表中，其权限标记为 `false`；需要仅获取有权限的项目时，传入 `has_permission=true`。
- 兼容仅携带应用凭据的调用：未提供用户身份时，返回全部项目，`project_manage` 和 `permission.view_business_v2` 均为 `false`；此时传入 `has_permission=true` 返回空列表。
- 业务访问权限不表示采集项、索引集等资源的操作权限，具体操作仍需检查对应权限。
