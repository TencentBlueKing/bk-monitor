# DeleteCollectConfigResource

## 基本信息

- **源文件**：`resources/backend.py`
- **HTTP 端点**：`POST delete`
- **resource 路径**：`resource.collecting.delete_collect_config`
- **功能**：删除采集配置，卸载部署，清理关联告警策略
- **适配复杂度**：🟢 低～中

## 入参（RequestSerializer）

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| bk_biz_id | int | 是 | - | 业务ID |
| id | int | 是 | - | 采集配置ID |

## 出参

```python
None
```

## 核心依赖

### ORM 模型依赖
- `CollectConfigMeta`（含 `select_related("deployment_config")`）

### deploy 依赖
- `get_collect_installer()`：获取安装器
- `installer.uninstall()`：卸载

### 其他依赖
- `DatalinkDefaultAlarmStrategyLoader`：清理内置链路健康策略
- `get_global_user()`：获取当前用户
- 判断用户是否还有其他采集配置（决定是否从告警组移除）

## bk-monitor-base 适配分析

### Base 已有能力（直接映射）
- **`delete_metric_plugin_deployment()`**：对应旧版删除采集配置（含部署卸载语义）；与 Installer 的 **`uninstall`** 能力配合，由 `metric_plugin` 域完成主流程。
- **`get_installer()`**：按插件类型选择 NodemanInstaller / K8sInstaller / SQLInstaller。

### 需 SaaS 层保留的逻辑
- **内置链路告警策略清理**：`DatalinkDefaultAlarmStrategyLoader` 等与 monitoring/SaaS 域耦合的逻辑仍在 SaaS，在 base 删除成功后异步或同步触发。
- **告警组成员调整**：「用户是否还有其他采集配置」等判断与 SaaS 用户模型绑定，保留在 SaaS。
- **事务边界**：若 base `delete_metric_plugin_deployment` 已保证部署与元数据一致性，SaaS 侧仅保证与告警清理的顺序或补偿策略。

### 入参/出参转换要点
- **入参**：`bk_biz_id`、`id` → 映射为 base 侧 deployment 标识。
- **出参**：旧版返回 `None`；若 base 返回删除结果体，SaaS 可忽略或记录日志。

### 修订后的适配复杂度评估
- **🟢 低～中**：删除/卸载核心已在 base；复杂度集中在 SaaS 告警与账号周边清理。

### 风险点
- SaaS 告警清理失败与 base 已删除状态不一致时，需幂等或补偿设计。
- 多环境（K8s/SQL/节点管理）下删除耗时与错误表现可能不同，错误信息需对用户可理解。

## 公共函数提取

| 可提取逻辑 | 描述 | 复用场景 |
|-----------|------|---------|
| `get_collect_config_or_raise` | 获取采集配置 | 多个 Resource |
| 告警策略清理逻辑 | `DatalinkDefaultAlarmStrategyLoader` 调用 | 删除、批量操作 |
