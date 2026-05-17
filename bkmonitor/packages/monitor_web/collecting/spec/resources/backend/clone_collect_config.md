# CloneCollectConfigResource

## 基本信息

- **源文件**：`resources/backend.py`
- **HTTP 端点**：`POST clone`
- **resource 路径**：`resource.collecting.clone_collect_config`
- **功能**：克隆采集配置，支持日志/SNMP Trap 类型重新创建，其他类型复制配置
- **适配复杂度**：🟡 中（流程组合，无单一 clone API）

## 入参（RequestSerializer）

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| bk_biz_id | int | 是 | - | 业务ID |
| id | int | 是 | - | 采集配置ID |

## 出参

```python
None  # 无返回值
```

## 核心依赖

### ORM 模型依赖
- `CollectConfigMeta`（含 `select_related("deployment_config")`）
- `DeploymentConfigVersion`：复制部署配置

### 内部 Resource 依赖
- `resource.collecting.collect_config_detail`：获取详情用于克隆
- `resource.collecting.save_collect_config`：日志/SNMP Trap 类型走重新创建流程

### 业务逻辑
- 日志/SNMP Trap：调用 `save_collect_config` 重新创建，plugin_id 设为 `default_log`
- 其他类型：事务中复制 `DeploymentConfigVersion` 和 `CollectConfigMeta`
- 自动处理重名（追加 `_copy` 及序号）
- 克隆不克隆目标节点（target_nodes 置空）

## bk-monitor-base 适配分析

### Base 已有能力（直接映射）
- **组合流程（无独立 clone API）**：
  1. **`get_metric_plugin_deployment()`**：读出源部署与版本、插件参数，等价旧版读详情用于克隆。
  2. **`save_and_install_metric_plugin_deployment()`**：以新名称/新标识写入并安装，等价旧版「复制后保存+下发」。
- **模型对应**：`CollectConfigMeta` → `MetricPluginDeployment`；`DeploymentConfigVersion` → `MetricPluginDeploymentVersion`；`CollectorPluginMeta` → `MetricPlugin`。

### 需 SaaS 层保留的逻辑
- **重名与唯一名**：`generate_unique_name`（`_copy`、序号）仍在 SaaS。
- **日志 / SNMP Trap**：虚拟插件 `default_log` 等分支仍走「组装 DTO + `save_and_install`」，与旧版走 `save_collect_config` 等价，只是下游改为 base operation。
- **克隆不克隆目标**：`target_nodes` 置空等业务规则在 SaaS 组装请求体时处理。

### 入参/出参转换要点
- **入参**：`bk_biz_id`、`id`（源配置）→ 先 `get_metric_plugin_deployment`，再构造 `save_and_install` 的 payload（新 name、清空的 target、调整后的 plugin/version 引用）。
- **出参**：维持无 body 或按产品约定返回新 id；若 base `save_and_install` 返回新 deployment id，SaaS 可透传或写缓存。

### 修订后的适配复杂度评估
- **🟡 中**：base 已具备读+写装全能力，但克隆无单接口，SaaS 负责分支、命名与 DTO 两次转换。

### 风险点
- 两次调用之间的并发修改（源配置被改）需约定以 get 快照为准或加版本校验。
- 日志/Trap 与常规类型的参数结构差异大，易在映射到 base 时遗漏字段。

## 公共函数提取

| 可提取逻辑 | 描述 | 复用场景 |
|-----------|------|---------|
| `generate_unique_name` | 生成不重名的名称（追加 `_copy(n)`） | 克隆 |
