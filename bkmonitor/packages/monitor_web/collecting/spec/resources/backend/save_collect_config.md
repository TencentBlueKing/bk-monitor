# SaveCollectConfigResource

## 基本信息

- **源文件**：`resources/backend.py`
- **HTTP 端点**：`POST save`
- **resource 路径**：`resource.collecting.save_collect_config`
- **功能**：新增或编辑采集配置，包含参数校验、虚拟插件创建、部署下发
- **适配复杂度**：🔴 高（最复杂的 Resource）

## 入参（RequestSerializer）

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| id | int | 否 | - | 采集配置ID（编辑时必填） |
| name | str | 是 | - | 采集配置名称 |
| bk_biz_id | int | 是 | - | 业务ID |
| collect_type | str | 是 | - | 采集方式 |
| target_object_type | str | 是 | - | 采集对象类型（HOST/SERVICE） |
| target_node_type | str | 是 | - | 采集目标类型（INSTANCE/TOPO/SERVICE_TEMPLATE/SET_TEMPLATE/CLUSTER/DYNAMIC_GROUP） |
| plugin_id | str | 是 | - | 插件ID |
| target_nodes | list | 是 | - | 节点列表（允许空） |
| remote_collecting_host | object | 否 | None | 远程采集配置 |
| remote_collecting_host.ip | str | 否 | - | 远程主机IP |
| remote_collecting_host.bk_cloud_id | int | 否 | - | 云区域ID |
| remote_collecting_host.bk_host_id | int | 否 | - | 主机ID |
| remote_collecting_host.bk_supplier_id | int | 否 | - | 供应商ID |
| remote_collecting_host.is_collecting_only | bool | 是 | - | 是否仅采集 |
| params | dict | 是 | - | 采集配置参数 |
| label | str | 是 | - | 二级标签 |
| operation | str | 否 | "EDIT" | 操作类型（EDIT/ADD_DEL） |
| metric_relabel_configs | list | 否 | [] | 指标重新标记配置 |

### metric_relabel_configs 子项

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| source_labels | list[str] | 是 | 源标签列表 |
| regex | str | 是 | 正则表达式 |
| action | str | 否 | 操作类型 |
| target_label | str | 否 | 目标标签 |
| replacement | str | 否 | 替换内容 |

### Serializer 校验逻辑

1. **目标类型校验**：校验 `target_object_type` 和 `target_node_type` 搭配是否合法
2. **目标节点字段校验**：不同类型要求不同字段（bk_inst_id/bk_obj_id、ip/bk_cloud_id、bk_host_id、bcs_cluster_id）
3. **日志关键字规则名称去重**
4. **密码校验**：克隆 Pushgateway 时密码不能为 bool
5. **目标字段整理**：统一 target_nodes 格式

## 出参

```python
{
    "id": int,               # 采集配置ID
    "deployment_id": int,    # 部署配置ID
    "can_rollback": bool,    # 是否可回滚
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
- `CollectConfigMeta`：创建或更新
- `CollectorPluginMeta`：获取插件信息
- `DeploymentConfigVersion`：部署配置

### deploy 依赖
- `get_collect_installer()`
- `installer.install(data, operation)`：核心部署操作

### 虚拟插件创建（`get_collector_plugin` 方法）
- **LOG 类型**：`PluginManagerFactory.get_manager(plugin_type=PluginType.LOG)` → `create_plugin` / `update_version`
- **PROCESS 类型**：`PluginManagerFactory.get_manager(plugin="bkprocessbeat", plugin_type=PluginType.PROCESS)` → `touch()`
- **SNMP_TRAP 类型**：调用 `resource.collecting.get_trap_collector_plugin`
- **K8S 类型**：`PluginManagerFactory.get_manager(plugin_type=PluginType.K8S)` → `create_plugin` / `update_version`

### 其他依赖
- `DatalinkDefaultAlarmStrategyLoader`：创建默认告警策略
- `append_metric_list_cache`：更新指标缓存
- `update_password_inplace()`：密码字段替换
- `roll_back_result_table()`：创建失败时回滚结果表

## bk-monitor-base 适配分析

### Base 已有能力（直接映射）

| 旧逻辑 | Base 对应 | 说明 |
|--------|----------|------|
| 创建/更新采集配置 + 部署下发 | `save_and_install_metric_plugin_deployment()` | **核心能力已有** |
| `get_collect_installer()` → `installer.install()` | `get_installer()` → `installer.install(deployment_version)` | 安装器已有 |
| `DeploymentConfigVersion` 创建 | 在 `save_and_install` 内自动创建 `MetricPluginDeploymentVersionModel` | 自动处理 |
| 版本差异比对 → `diff_node` | `BaseInstaller.get_version_diff()` | 结果格式需转换 |
| NodeManInstaller / K8sInstaller | `NodemanInstaller` / `K8sInstaller` / `SQLInstaller` | 类型更丰富 |

### 入参转换核心

```python
# 旧版入参 → Base CreateOrUpdateDeploymentParams
def convert_save_params_to_base(data: dict, bk_tenant_id: str) -> CreateOrUpdateDeploymentParams:
    return CreateOrUpdateDeploymentParams(
        id=data.get("id"),                        # 编辑时有值
        name=data["name"],
        plugin_id=data["plugin_id"],
        plugin_version=_resolve_plugin_version(bk_tenant_id, data["plugin_id"]),
        target_scope=MetricPluginDeploymentScope(
            node_type=data["target_node_type"],
            nodes=data["target_nodes"],
        ),
        remote_scope=_convert_remote_host_to_scope(data.get("remote_collecting_host")),
        params=data.get("params", {}),
    )
```

### 出参转换核心

```python
# Base 返回 → 旧版响应格式
# save_and_install 返回 installer.install() 的结果
# 需要包装为:
{
    "id": deployment.id,
    "deployment_id": deployment.id,
    "can_rollback": version.version > 1,  # 有上一版本即可回滚
    "diff_node": convert_version_diff_to_legacy(diff_result),
}
```

### 需 SaaS 层保留的逻辑

1. **虚拟插件创建**（`get_collector_plugin` 方法）：
   - LOG / PROCESS / K8S → 调用 base `create_metric_plugin()` 或 `create_metric_plugin_version()`
   - SNMP_TRAP → base 已有 `SNMPTrapPluginManager`
2. **密码处理**：`update_password_inplace` 保留 SaaS 层
3. **默认告警策略**：`DatalinkDefaultAlarmStrategyLoader` 保留 SaaS 层
4. **指标缓存更新**：`append_metric_list_cache` 保留 SaaS 层
5. **结果表回滚**：`roll_back_result_table` 保留 SaaS 层
6. **Serializer 校验**：target_nodes 校验逻辑保留 SaaS 层

### 风险点
- 入参中的 `operation`（EDIT / ADD_DEL）在 base 中无对应概念，base 统一为 install
- `remote_collecting_host` 是单主机格式，base 的 `remote_scope` 是 scope 格式（含 node_type + nodes），需做结构适配
- 虚拟插件创建仍然复杂，但可借助 base 的 `create_metric_plugin()` 简化
- `can_rollback` 需从版本号判断（version > 1）
- K8S 类型依赖 `settings.TENCENT_CLOUD_METRIC_PLUGIN_CONFIG` 配置

## 公共函数提取

| 可提取逻辑 | 描述 | 复用场景 |
|-----------|------|---------|
| `get_collector_plugin` | 按 collect_type 获取/创建虚拟插件 | 保存、克隆 |
| `update_password_inplace` | 密码参数替换为实际值 | 保存、升级 |
| `validate_target_nodes` | 目标节点校验和格式化 | 保存（Serializer.validate） |
| `roll_back_result_table` | 创建失败时回滚结果表 | 保存 |
| `update_metric_cache` | 更新指标缓存 | 保存、升级 |
