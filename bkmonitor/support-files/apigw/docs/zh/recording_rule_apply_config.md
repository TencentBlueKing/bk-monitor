### 功能描述

解析下发 RecordingRule 配置

`POST /app/recording_rule/apply_config/`

对已保存的当前声明执行输出元数据准备、指标解析和 Flow 下发，沿用配置中的 running/stopped 期望状态。返回 data.rule 和 data.execution。

execution.succeeded 表示本次执行是否成功；失败时携带 error，并保留当前声明供重试。它不表示已完成数据产出验收。

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
