# CollectRunningStatusResource

## 基本信息

- **源文件**：`resources/status.py`
- **HTTP 端点**：`GET running_status`
- **resource 路径**：`resource.collecting.collect_running_status`
- **功能**：获取采集配置主机的运行状态（默认不进行差异比对），启停前预览
- **适配复杂度**：🟡 中（diff=False 但仍需节点结构 + 实例字段转换）
- **注意**：继承自 `CollectTargetStatusResource`，仅覆盖了 `RequestSerializer`（`diff` 默认为 `False`）

## 入参（RequestSerializer）

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| bk_biz_id | int | 是 | - | 业务ID |
| id | int | 是 | - | 采集配置ID |
| diff | bool | 否 | False | 是否只返回差异（默认不diff） |

## 出参

与 `CollectTargetStatusResource` 相同。

## bk-monitor-base 适配分析

> 继承自 `CollectTargetStatusResource`，但默认 `diff=False`，不涉及版本差异比对。

### Base 已有能力
- **`get_metric_plugin_deployment_status()`**：获取全量实例状态（无 diff），与此 Resource 的 `diff=False` 语义匹配。

### 仍需 SaaS 层处理的差异

即使 diff=False，Base `status()` 和旧版仍有以下结构性差异需要在 SaaS 转换：

1. **节点分组结构**：旧版返回 `{node_path, label_name, is_label, child}`，Base 返回 `{node_name, node_type, node_id, child}`
2. **实例字段**：
   - 旧版有 `task_id`、`plugin_version`，Base 没有
   - 旧版 `log` 是阶段名，Base 是错误日志文本
   - 旧版做 RUNNING → STARTING/STOPPING 状态转换，Base 不做
3. **`config_info`**：需从 `get_metric_plugin_deployment()` 组装

### 修订后的适配复杂度评估
- **🟡 中**：虽然免去了 diff 逻辑，但节点结构转换和实例字段补充仍需可观工作量。

### 风险点
- 与父类共享 compat 转换层；继承链上的行为变更需同步维护。
- 旧版 `log` 字段语义变化可能影响前端展示。
