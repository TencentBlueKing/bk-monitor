## 功能描述

获取项目列表，并返回当前用户的业务访问权限。权限判断与 `/meta/spaces/mine/` 一致，保留项目接口原有的返回结构。

请求方式：`GET /meta/projects/mine/`。

## 请求参数

### 鉴权头

通过请求头 `X-Bkapi-Authorization` 传递 JSON 字符串：

```json
{
  "bk_app_code": "your_app_code",
  "bk_app_secret": "your_app_secret",
  "bk_username": "your_username"
}
```

调用应用需要具有本接口的网关访问权限，`bk_username` 用于指定查询业务权限的用户。

### 查询参数

| 字段 | 类型 | 必选 | 描述 |
| --- | --- | --- | --- |
| has_permission | bool | 否 | 默认 `false`，返回全部项目并标记当前用户的权限；设为 `true` 时仅返回有业务访问权限的项目 |

例如，`GET /meta/projects/mine/?has_permission=true` 仅获取当前用户有权限的项目。

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
      "project_manage": false,
      "permission": {"view_business_v2": false}
    }
  ]
}
```

`project_manage` 是兼容字段，与 `permission.view_business_v2` 均表示业务访问权限，不表示采集项等资源的操作权限。未传 `has_permission` 时，无权限项目仍会出现在列表中，其权限标记为 `false`；过滤模式下没有有权限的项目时，返回空列表。
