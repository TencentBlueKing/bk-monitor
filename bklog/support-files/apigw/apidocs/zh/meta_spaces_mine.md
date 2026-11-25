## 功能描述

获取空间列表及当前用户的业务访问权限。

## 请求参数

请求方式：`GET /meta/spaces/mine/`，参数通过 Query String 传递。

### 鉴权头

| 参数名称 | 参数类型 | 必须 | 参数说明 |
| --- | --- | --- | --- |
| bk_app_code | string | 是 | 蓝鲸应用 ID |
| bk_app_secret | string | 是 | 蓝鲸应用密钥 |
| bk_username | string | 是 | 查询空间权限和置顶信息的用户名 |

鉴权信息通过请求头 `X-Bkapi-Authorization` 传递，取值为上述字段构成的 JSON 字符串。

### 参数列表

| 字段 | 类型 | 必选 | 描述 |
| --- | --- | --- | --- |
| space_uid | string | 否 | 空间唯一标识，例如 `bkcc__2`；传入时仅查询该空间 |
| has_permission | bool | 否 | 默认 `false`，返回空间并标记当前用户权限；设为 `true` 时仅返回有业务访问权限的空间 |
| page | int | 否 | 页码，从 1 开始；与 `page_size` 同时传入时分页 |
| page_size | int | 否 | 每页条数，最小 1；与 `page` 同时传入时分页 |

## 请求参数示例

获取当前用户有权限的空间，每页 20 条：

```json
{
  "has_permission": true,
  "page": 1,
  "page_size": 20
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
      "id": 1,
      "space_type_id": "bkcc",
      "space_type_name": "业务",
      "space_id": "2",
      "space_name": "示例业务",
      "space_uid": "bkcc__2",
      "space_code": "example_biz",
      "bk_biz_id": 2,
      "time_zone": "Asia/Shanghai",
      "is_sticky": false,
      "permission": {"view_business_v2": true},
      "bk_tenant_id": "default"
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
| data | list | 空间列表，没有匹配结果时返回空列表；分页时不返回总条数 |
| data[].id | int | 空间记录 ID |
| data[].space_type_id | string | 空间类型，如 `bkcc`（业务）、`bcs`（容器项目）、`bkci`（研发项目）、`bksaas`（SaaS） |
| data[].space_type_name | string | 空间类型名称 |
| data[].space_id | string | 对应类型下的空间 ID |
| data[].space_name | string | 空间名称 |
| data[].space_uid | string | 空间唯一标识，格式为 `空间类型__空间 ID` |
| data[].space_code | string/null | 空间英文名称 |
| data[].bk_biz_id | int | 权限使用的业务标识，非业务空间可为负数 |
| data[].time_zone | string | 空间所在时区，未配置时为 `Asia/Shanghai` |
| data[].is_sticky | bool | 当前用户是否置顶该空间 |
| data[].permission | dict | 当前用户的权限标记 |
| data[].permission.view_business_v2 | bool | 当前用户是否有该空间的业务访问权限 |
| data[].bk_tenant_id | string | 租户 ID |

## 注意事项

- 未传 `has_permission` 时，无权限空间仍会出现在列表中，其权限标记为 `false`；传入 `has_permission=true` 才过滤无权限空间。
- 同时传入 `space_uid` 和 `has_permission=true` 时，若当前用户无该空间权限，返回空列表。
- 分页在权限过滤后执行；未同时传入 `page` 和 `page_size` 时不分页。
