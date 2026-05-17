# GetTrapCollectorPluginResource

## 基本信息

- **源文件**：`resources/snmp_trap.py`
- **HTTP 端点**：无直接 HTTP 端点（被 `SaveCollectConfigResource` 内部调用）
- **resource 路径**：`resource.collecting.get_trap_collector_plugin`
- **功能**：获取或创建 SNMP Trap 采集配置对应的虚拟插件
- **适配复杂度**：🟡 中

## 入参（RequestSerializer）

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| plugin_id | str | 是 | - | 插件ID |
| label | str | 是 | - | 二级标签 |
| bk_biz_id | int | 是 | - | 业务ID |
| id | int | 否 | - | 采集配置ID（编辑时提供） |
| params | object | 否 | - | 采集配置信息 |
| params.snmp_trap | object | 是 | - | SNMP Trap 配置 |
| params.snmp_trap.server_port | int | 是 | - | Trap 服务端口 |
| params.snmp_trap.listen_ip | str | 是 | - | Trap 监听地址 |
| params.snmp_trap.yaml | dict | 是 | - | yaml 配置文件 |
| params.snmp_trap.community | str | 否 | "" | 团体名 |
| params.snmp_trap.aggregate | bool | 是 | - | 是否按周期聚合 |
| params.snmp_trap.version | str | 是 | - | SNMP 版本（v1/2c/v2c/v3） |
| params.snmp_trap.auth_info | list | 否 | [] | V3 认证信息 |

### auth_info 子项（V3 认证）

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| security_name | str | 否 | 安全名 |
| context_name | str | 否 | 上下文名称 |
| security_level | str | 否 | 安全级别 |
| authentication_protocol | str | 否 | 验证协议 |
| authentication_passphrase | str | 否 | 验证口令 |
| privacy_protocol | str | 否 | 隐私协议 |
| privacy_passphrase | str | 否 | 私钥 |
| authoritative_engineID | str | 否 | 设备ID |

## 出参

```python
str  # 插件ID（新建时为 "trap_" + uuid，编辑时为原 plugin_id）
```

## 核心依赖

- `PluginManagerFactory.get_manager(plugin_type=PluginType.SNMP_TRAP)`
- `plugin_manager.get_params()`：生成插件参数
- `resource.plugin.create_plugin()`：创建新插件（首次）
- `plugin_manager.update_version()`：更新版本（编辑）
- `shortuuid.uuid()`：生成插件ID

## bk-monitor-base 适配分析

### 可适配部分
- 虚拟插件创建 → base 的 `metric_plugin` 域已有插件创建能力

### 需 base 补齐的能力
1. **SNMP Trap 虚拟插件管理**：base 需支持 SNMP Trap 类型的虚拟插件创建/更新
2. **PluginManagerFactory 适配**：SNMP Trap 类型的 Manager 需在 base 侧实现

### 风险点
- 依赖 `PluginManagerFactory` 获取 SNMP Trap 类型的 Manager
- plugin 模块适配后，此处需对齐新的插件创建方式
- `resource.plugin.create_plugin` 在 plugin 适配后行为可能变化

### 适配方案
- 新版应通过 base 的 `metric_plugin` 域操作 SNMP Trap 虚拟插件
- 需确保 base 侧 `create_metric_plugin` 支持 SNMP_TRAP 类型
