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

下发前检查动态 JSON 配置 `RECORD_RULE_V4_CONFIG`（默认 `{"max_sources": 20, "max_rules": 20, "max_series": 500000, "series_exempt_rule_ids": []}`）。超限返回 `execution.succeeded=false`，`execution.error` 包含实际数量和上限；声明、成功解析的快照与此前已生效的 Flow 保留，不向 BKBase 提交本次 Flow。调整上限或配置后可再次调用 `apply_config`。

下发为运行状态前逐条执行完整表达式的即时 `count(...)` 查询，统计当前输出 series 数量，默认上限 500,000（等于上限允许）。任一语句超限时整个规则组不下发，`execution.error` 包含规则、语句、实际数量、阈值及“请联系监控管理员进行评估，获得许可后再下发。”。查询超时、失败或结果不完整时同样阻止下发并提示重试；已保存声明与原运行 Flow 保留。保存和预解析不执行此查询；停止和删除跳过 series 检查，恢复运行重新检查。

管理员通过动态配置 `RECORD_RULE_V4_CONFIG.max_series` 调整阈值，设为 `0` 则全局跳过 series 查询和检查；或评估后把规则组 ID 加入 `series_exempt_rule_ids`（默认 `[]`）许可下发。豁免跳过 series 查询，不影响 source/rule 上限；配置修改后仍有效，移除 ID 撤销许可。普通请求参数不能绕过检查。配置变更沿用动态配置缓存刷新机制；获批后重新下发即可。检查仅反映下发时的数量，不保证运行期间始终低于阈值。
