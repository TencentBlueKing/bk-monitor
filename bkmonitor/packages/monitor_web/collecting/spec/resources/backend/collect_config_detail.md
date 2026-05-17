# CollectConfigDetailResource

## 基本信息

- **源文件**：`resources/backend.py`
- **HTTP 端点**：`GET config_detail`
- **resource 路径**：`resource.collecting.collect_config_detail`
- **功能**：获取单个采集配置的详细信息，包括部署参数、目标节点、插件信息
- **适配复杂度**：🟢 低～中

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
    "name": str,
    "bk_biz_id": int,
    "collect_type": str,
    "label": str,
    "target_object_type": str,
    "target_node_type": str,
    "target_nodes": list,
    "params": dict,                    # 部署参数（含 collector / plugin 两组）
    "remote_collecting_host": dict,    # 远程采集配置
    "plugin_info": dict,               # 插件版本详情（调用 get_plugin_version_detail）
    "target": list,                    # 解析后的目标节点详情
    "subscription_id": int,
    "label_info": dict,
    "create_time": datetime,
    "create_user": str,
    "update_time": datetime,
    "update_user": str,
}
```

## 核心依赖

### ORM 模型依赖
- `CollectConfigMeta`（含 `select_related("deployment_config")`）
- `DeploymentConfigVersion`
- `PluginVersionHistory`（获取 release 版本详情）

### 外部 API / Resource 依赖
- `resource.commons.get_host_instance_by_ip`：按 IP 获取主机实例
- `resource.commons.get_host_instance_by_node`：按拓扑节点获取主机实例
- `resource.commons.get_template`：获取模板信息
- `resource.commons.get_service_instance_by_node`：获取服务实例
- `api.cmdb.search_dynamic_group`：搜索动态分组

### 关键方法
- `password_convert()`：将密码类参数转为 bool（防止前端看到明文）
- `plugin.get_release_ver_by_config_ver()`：根据 config_version 获取 release 版本

## bk-monitor-base 适配分析

### Base 已有能力（直接映射）
- **`get_metric_plugin_deployment()`**：与旧版「采集配置详情」查询直接对应，承载部署参数、版本与插件维度的聚合读取。
- **领域模型对应关系**：`CollectConfigMeta` → `MetricPluginDeployment`；`DeploymentConfigVersion` → `MetricPluginDeploymentVersion`；`CollectorPluginMeta` → `MetricPlugin`。
- **`get_installer()`**：按插件类型选择 NodemanInstaller / K8sInstaller / SQLInstaller；详情只读路径以 deployment 查询为主，与安装器解耦。

### 需 SaaS 层保留的逻辑
- **目标节点展示解析**：`target`、`target_nodes` 等与 CMDB/拓扑/模板/动态分组相关的富化（如按 IP/节点查主机实例、`search_dynamic_group` 等）宜仍在 SaaS，base 提供结构化目标描述即可。
- **`plugin_info` 形态与密码脱敏**：若 base 返回字段与旧版 `get_plugin_version_detail`、`password_convert()` 不完全一致，需在 SaaS 做字段映射或追加调用插件/元数据能力。

### 入参/出参转换要点
- **入参**：`bk_biz_id`、`id`（采集配置 ID）→ 按 base API 约定映射为空间/部署主键（如 `space_uid` + deployment id，以实际接口为准）。
- **出参**：将 `MetricPluginDeployment`（及 version、plugin 嵌套）序列化为当前契约的 `params`、`remote_collecting_host`、`plugin_info`、`target`、`label_info`、`subscription_id` 等；时间、操作者字段与 base 命名对齐。

### 修订后的适配复杂度评估
- **🟢 低～中**：详情主数据已由 base 覆盖；主要工作量在 DTO 对齐与目标/插件信息的 SaaS 侧补全。

### 风险点
- 目标解析多分支仍依赖 CMDB 等资源，需约定 base 返回的最小字段集以免重复存储。
- `plugin_info`、密码类字段与旧版行为需逐项对照，避免破坏前端与其它 Resource（如克隆、前端详情）的契约。

## 公共函数提取

| 可提取逻辑 | 描述 | 复用场景 |
|-----------|------|---------|
| `get_collect_config_or_raise` | 获取采集配置，不存在则抛异常 | 几乎所有 Resource |
| `password_convert` | 密码脱敏 | 详情、前端详情 |
| `resolve_target_nodes` | 解析目标节点（按类型分发） | 详情、前端目标信息 |
