# RollbackDeploymentConfigResource

## 基本信息

- **源文件**：`resources/backend.py`
- **HTTP 端点**：`POST rollback`
- **resource 路径**：`resource.collecting.rollback_deployment_config`
- **功能**：回滚采集配置到上一个部署版本
- **适配复杂度**：🟡 中（Base 无 rollback，SaaS 组合实现）

## 入参（RequestSerializer）

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| bk_biz_id | int | 是 | - | 业务ID |
| id | int | 是 | - | 采集配置ID |

## 出参

```python
{
    "id": int,
    "deployment_id": int,
    "diff_node": {
        "is_modified": bool,
        "added": list,
        "removed": list,
        "unchanged": list,
        "updated": list,
    }
}
```

## 核心依赖

- `CollectConfigMeta`（含 `select_related("deployment_config")`）
- `collect_config.allow_rollback`：回滚前置校验
- `get_collect_installer()`
- `installer.rollback()`

## bk-monitor-base 适配分析

### Base 已有能力（直接映射）
- **无独立 rollback**：Base Installer **不提供 `rollback`**；不存在与旧版 `installer.rollback()` 一一对应的 operation。
- **可复用能力**：通过 **`get_metric_plugin_deployment()`** 读取当前与历史版本信息（视 base 是否暴露多版本/上一版本），再调用 **`save_and_install_metric_plugin_deployment()`** 将部署回写到目标版本并重新安装，从而在效果上模拟回滚。

### 需 SaaS 层保留的逻辑
- **`allow_rollback` 与版本选择**：旧版 `CollectConfigMeta.allow_rollback` 及「上一版本」解析在 SaaS 实现；校验通过后再组 `save_and_install` payload。
- **diff 结构**：`diff_node` 可与升级类似，来自状态接口或 SaaS 比对逻辑。

### 入参/出参转换要点
- **入参**：`bk_biz_id`、`id` → 解析可回滚目标版本 → 构造与「升级」同形的 `save_and_install` 请求（插件版本/参数指向历史版本）。
- **出参**：保持 `id`、`deployment_id`、`diff_node` 与旧版一致；数据来源于 base 写操作返回值及可选的 **`get_metric_plugin_deployment_status()`**。

### 修订后的适配复杂度评估
- **🟡 中**：核心安装能力在 base，但回滚全流程需 SaaS 显式组合与校验，复杂度高于单一 operation 封装。

### 风险点
- 与旧版 `rollback()` 原子性、错误语义可能不一致，需约定失败时状态与重试策略。
- 历史版本可用性、签名/插件下架等边界需在 SaaS 与 base 字段能力上对齐。
