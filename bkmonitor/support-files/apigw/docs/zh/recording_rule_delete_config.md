### 功能描述

软删除 RecordingRule 配置

`POST /app/recording_rule/delete_config/`

先设置 is_deleted=true 并声明删除，再执行 Flow 删除。软删除后，公共配置接口和 AsCode 入口立即不可见；重复删除返回对象不存在。Admin 维持原有行为。

返回 data.is_deleted=true、data.rule 和 data.execution。Flow 删除失败时 execution.succeeded=false，后台继续重试；规则、版本及事件记录保留。deleted_at 仍表示 Flow 删除完成时间。

### 请求参数

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| bk_biz_id | integer | 否 | 业务 ID，与 space_uid 至少提供一个 |
| space_uid | string | 否 | 空间 UID，与 bk_biz_id 至少提供一个 |
| id | integer | 是 | 规则组 ID，必须属于当前租户及指定空间且未软删除 |

bk_biz_id 与 space_uid 至少提供一个。租户取认证上下文，配置内容中不填写租户或空间字段。ID 必须属于当前租户、指定空间且未软删除。

### 请求示例

```json
{
  "bk_biz_id": 2,
  "id": 12
}
```

### 返回结果

沿用网关标准的 result、code、message、data 响应结构。请求处理成功不等于下发成功；有 execution 的接口需同时检查 execution.succeeded。
