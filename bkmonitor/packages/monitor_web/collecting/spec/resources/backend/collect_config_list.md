# CollectConfigListResource

## 基本信息

- **源文件**：`resources/backend.py`
- **HTTP 端点**：`POST config_list`
- **resource 路径**：`resource.collecting.collect_config_list`
- **功能**：获取采集配置列表信息，支持分页、搜索、排序、实时状态刷新
- **适配复杂度**：🔴 高

## 入参（RequestSerializer）

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| bk_biz_id | int | 否 | - | 业务ID，为空时按用户拥有的业务查询 |
| refresh_status | bool | 否 | - | 是否刷新实时状态 |
| search | dict | 否 | - | 搜索字段（支持 status/task_status/need_upgrade/fuzzy/其他字段） |
| order | str | 否 | - | 排序字段（支持 `-` 前缀倒序） |
| disable_service_type | bool | 否 | True | 不需要服务分类 |
| page | int | 否 | 1 | 页数（-1 表示不分页） |
| limit | int | 否 | 10 | 每页大小 |

## 出参

```python
{
    "type_list": [{"id": str, "name": str}],  # 采集类型列表
    "config_list": [
        {
            "id": int,
            "name": str,
            "bk_biz_id": int,
            "space_name": str,
            "collect_type": str,
            "status": str,           # 配置状态
            "task_status": str,      # 任务状态
            "target_object_type": str,
            "target_node_type": str,
            "plugin_id": str,
            "target_nodes_count": int,
            "need_upgrade": bool,
            "config_version": int,
            "info_version": int,
            "error_instance_count": int,
            "total_instance_count": int,
            "running_tasks": list,
            "label_info": dict,
            "label": str,
            "update_time": datetime,
            "update_user": str,
        }
    ],
    "total": int,
}
```

## 核心依赖

### ORM 模型依赖
- `CollectConfigMeta`：采集配置主表查询、缓存更新
- `CollectorPluginMeta`：插件信息查询
- `PluginVersionHistory`：插件版本查询（判断是否需要升级）
- `DeploymentConfigVersion`：部署配置（通过 select_related 关联）

### 外部 API 依赖
- `SpaceApi.list_spaces()`：获取空间列表
- `SpaceApi.get_space_detail()`：获取空间详情
- `api.metadata.query_data_source_by_space_uid()`：查询数据源
- `api.node_man.fetch_subscription_statistic`：节点管理订阅统计（通过 `fetch_sub_statistics`）

### 内部 Resource 依赖
- `resource.space.get_bk_biz_ids_by_user`：按用户获取业务ID

### deploy 依赖
- `get_collect_installer()`：K8s 插件需单独获取状态

## bk-monitor-base 适配分析

### Base 已有能力（直接映射）

| 旧逻辑 | Base 对应 | 说明 |
|--------|----------|------|
| 采集配置列表查询 | `list_metric_plugin_deployments()` | 基础列表+分页已有 |
| 插件信息获取 | `get_metric_plugin()` / `list_metric_plugins()` | 批量获取插件信息 |
| 状态查询 | `get_metric_plugin_deployment_status()` | 基于 installer 的状态查询 |
| 部署项数量统计 | `list_metric_plugin_deployments()` 返回的 total | 已有 |

### 适配方案

```python
# 新版 new.py 中的实现骨架
def perform_request(self, validated_data):
    bk_tenant_id = get_bk_tenant_id()

    # 1. 调用 base 获取部署项列表
    deployments, total = list_metric_plugin_deployments(
        bk_tenant_id=bk_tenant_id,
        bk_biz_ids=[validated_data["bk_biz_id"]] if validated_data.get("bk_biz_id") else None,
        plugin_types=...,
        limit=validated_data.get("limit"),
        offset=(validated_data.get("page", 1) - 1) * validated_data.get("limit", 10),
    )

    # 2. 批量获取关联的插件信息（避免 N+1）
    plugin_ids = list({d.plugin_id for d in deployments})
    plugins, _ = list_metric_plugins(
        bk_tenant_id=bk_tenant_id,
        plugin_ids=plugin_ids,
    )
    plugin_map = {p["id"]: p for p in plugins}

    # 3. 批量转换为旧版格式
    config_list = [
        convert_deployment_to_legacy_list_item(d, plugin_map.get(d.plugin_id))
        for d in deployments
    ]

    # 4. SaaS 层补充：need_upgrade / status 刷新 / 空间信息
    ...

    return {"config_list": config_list, "total": total, "type_list": ...}
```

### 需 SaaS 层保留的逻辑

1. **状态实时刷新**：旧版 `refresh_status` 参数触发 `fetch_sub_statistics`，base 层未集成批量统计接口
2. **need_upgrade 检测**：比较 `deployment.plugin_version` 与 `plugin.release_version`
3. **空间/业务权限过滤**：`SpaceApi` 和 `data_source_by_space_uid` 逻辑保留 SaaS 层
4. **cache_data 缓存**：旧版的 `error_instance_count` / `total_instance_count` 来自 `cache_data`
5. **搜索/排序分层**：
   - `status`（运行态）与 `fuzzy` 已下推到 base 列表 API
   - `task_status` 中的 `PREPARING/DEPLOYING/STARTING/STOPPING/STOPPED` 已翻译为 base 原子状态下推
   - `task_status=SUCCESS/WARNING/FAILED` 与 `need_upgrade` 仍由 SaaS 层结合实例统计/版本信息补充过滤

### 风险点
- Base `list_metric_plugin_deployments()` 过滤能力有限（仅支持 bk_biz_ids / plugin_types / plugin_ids），旧版复杂搜索需 SaaS 层补充
- 旧版 `cache_data` 中的实例统计需从状态查询接口获取或维护独立缓存
- 空间数据源过滤逻辑复杂，需保留现有实现
- 适配复杂度修订为 🟡 中（基础列表 base 已有，额外逻辑在 SaaS 层）

## 公共函数提取

| 可提取逻辑 | 描述 | 复用场景 |
|-----------|------|---------|
| `fetch_sub_statistics` | 批量获取节点管理订阅统计 | `CollectConfigListResource`、`UpdateConfigInstanceCountResource` |
| `get_realtime_data` | 获取实时状态并更新缓存 | 列表刷新、状态查询 |
| `need_upgrade` | 检查采集配置是否需要升级 | 列表、统计 |
| 空间过滤逻辑 | 按业务/空间过滤采集配置 | 列表、统计 |
