### 功能描述

查询 RecordingRule 配置

`GET /app/recording_rule/get_config/`

返回 data.rule、data.config 和 data.observation。默认 with_status=false，只读取本地配置，observation=null。

with_status=true 时查询已下发 Flow，observation 包含 succeeded、flow_status 和 error；观测结果按现有逻辑记录到本地状态和事件。查询失败仍返回配置并携带观测错误。尚未下发时不请求 BKBase，返回 flow_status=null 和“尚未下发 Flow”。

### 请求参数

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| bk_biz_id | integer | 否 | 业务 ID，与 space_uid 至少提供一个 |
| space_uid | string | 否 | 空间 UID，与 bk_biz_id 至少提供一个 |
| id | integer | 是 | 规则组 ID，必须属于当前租户及指定空间且未软删除 |
| with_status | boolean | 否 | 是否查询已下发 Flow 的实时状态；默认 false |

bk_biz_id 与 space_uid 至少提供一个。租户取认证上下文，配置内容中不填写租户或空间字段。ID 必须属于当前租户、指定空间且未软删除。

### 请求示例

```text
bk_biz_id=2&id=12&with_status=true
```

### 返回结果

沿用网关标准的 result、code、message、data 响应结构。请求处理成功不等于下发成功；有 execution 的接口需同时检查 execution.succeeded。
