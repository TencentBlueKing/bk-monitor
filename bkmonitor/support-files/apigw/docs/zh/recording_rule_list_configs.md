### 功能描述

查询 RecordingRule 配置列表

`GET /app/recording_rule/list_configs/`

只返回当前租户、指定空间且 is_deleted=false 的规则。按更新时间和 ID 倒序，默认每页 20 条，最大 100 条。

返回 data.items、data.total、data.page、data.page_size。items 包含 ID、名称、app、path、输出表、声明版本、当前状态、期望状态、解析版本、conditions 和检查时间。列表仅返回本地状态，不逐条查询 BKBase。

### 请求参数

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| bk_biz_id | integer | 否 | 业务 ID，与 space_uid 至少提供一个 |
| space_uid | string | 否 | 空间 UID，与 bk_biz_id 至少提供一个 |
| name | string | 否 | 规则组名称，包含匹配 |
| app | string | 否 | AsCode 配置分组，精确匹配；空串表示非托管配置 |
| status | string | 否 | 本地聚合状态，精确匹配 |
| page | integer | 否 | ；默认 1 |
| page_size | integer | 否 | ；默认 20 |

bk_biz_id 与 space_uid 至少提供一个。租户取认证上下文，配置内容中不填写租户或空间字段。ID 必须属于当前租户、指定空间且未软删除。

### 请求示例

```text
bk_biz_id=2&page=1&page_size=20
```

### 返回结果

沿用网关标准的 result、code、message、data 响应结构。请求处理成功不等于下发成功；有 execution 的接口需同时检查 execution.succeeded。
