# UpgradeCollectPluginResource

## 基本信息

- **源文件**：`resources/backend.py`
- **HTTP 端点**：`POST upgrade`
- **resource 路径**：`resource.collecting.upgrade_collect_plugin`
- **功能**：将采集配置升级到最新的插件版本
- **适配复杂度**：🟢 低～中

## 入参（RequestSerializer）

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| bk_biz_id | int | 是 | - | 业务ID |
| id | int | 是 | - | 采集配置ID |
| params | dict | 是 | - | 采集配置参数 |
| realtime | bool | 否 | False | 是否实时刷新缓存 |

## 出参

```python
{
    "id": int,
    "deployment_id": int,
    "can_rollback": bool,
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

### ORM 模型依赖
- `CollectConfigMeta`（含 `select_related("deployment_config")`）

### deploy 依赖
- `get_collect_installer()`
- `installer.upgrade(params)`

### 其他依赖
- `SaveCollectConfigResource.update_password_inplace()`：密码处理
- `resource.collecting.collect_config_list()`：实时刷新缓存时调用
- `append_metric_list_cache`：更新指标缓存

## bk-monitor-base 适配分析

### Base 已有能力（直接映射）
- **`save_and_install_metric_plugin_deployment()`**：以新版本（新 `MetricPlugin` / version 引用）重新保存并安装，对应旧版「升级插件」；等价于用新版本覆盖部署而非单独 `upgrade()` operation。
- **`get_installer()`**：安装路径仍按插件类型选择 Nodeman / K8s / SQL Installer（含 `install`/`run` 等）。

### 需 SaaS 层保留的逻辑
- **密码占位与回填**：`update_password_inplace` 等与前端 `params` 交互相关的逻辑仍在 SaaS，再写入 base payload。
- **指标与列表缓存**：`append_metric_list_cache`、`collect_config_list`（`realtime`）等 SaaS 缓存刷新保持不变。
- **`can_rollback` / `diff_node`**：若 base 返回结构与旧版 installer.upgrade 不一致，需在 SaaS 从 `get_metric_plugin_deployment_status()` 或升级响应中计算或映射。

### 入参/出参转换要点
- **入参**：`bk_biz_id`、`id`、`params`、`realtime` → 合并当前 deployment 与 `params` 为 `save_and_install` 请求；`realtime` 仅影响 SaaS 侧缓存刷新。
- **出参**：保持 `id`、`deployment_id`、`can_rollback`、`diff_node` 契约；字段从 base 响应或补充一次状态查询组装。

### 修订后的适配复杂度评估
- **🟢 低～中**：升级主路径由 `save_and_install` 承担；工作量在密码、缓存与 diff 展示对齐。

### 风险点
- `realtime` 触发列表刷新可能与保存接口形成调用链，需避免循环与风暴。
- `diff_node` 语义依赖安装器/状态接口，需与 `get_metric_plugin_deployment_status()` 字段对齐。

## 公共函数提取

| 可提取逻辑 | 描述 | 复用场景 |
|-----------|------|---------|
| `update_password_inplace` | 密码替换 | 保存、升级 |
| `update_metric_cache` | 指标缓存更新 | 保存、升级 |
