# CollectTargetStatusResource

## 基本信息

- **源文件**：`resources/status.py`
- **HTTP 端点**：`GET status`
- **resource 路径**：`resource.collecting.collect_target_status`
- **功能**：获取采集配置下发状态（默认进行差异比对）
- **适配复杂度**：🔴 高（diff 模式在 base 完全缺失）

## 入参（RequestSerializer）

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| bk_biz_id | int | 是 | - | 业务ID |
| id | int | 是 | - | 采集配置ID |
| diff | bool | 否 | True | 是否只返回差异 |
| auto_running_tasks | list | 否 | - | 自动运行的任务 |

## 出参

```python
{
    "config_info": dict,     # collect_config.get_info() 的返回值
    "contents": list[dict],  # installer.status(diff=diff) 的返回值
}
```

### contents 结构（diff=True，TOPO 场景）

```python
[
    {
        "child": [...实例列表...],
        "node_path": "蓝鲸/公共组件/kafka",  # 拓扑路径
        "label_name": "ADD",                  # 差异类型 ADD/REMOVE/UPDATE/RETRY
        "is_label": True,
    },
]
```

### contents 结构（diff=False）

```python
[
    {
        "child": [...实例列表...],
        "node_path": "蓝鲸/公共组件/kafka",
        "label_name": "",
        "is_label": False,
    },
]
```

## 核心依赖

- `CollectConfigMeta`（含 `select_related("deployment_config")`）
- `collect_config.get_info()`：获取采集配置摘要信息
- `get_collect_installer()`
- `installer.status(diff=diff)`：获取部署状态（含差异比对）

## bk-monitor-base 适配分析

> ⚠️ **这是新旧差异最大的 Resource。** 详见 [base_capability_mapping.md § 4.5](../../../spec/base_capability_mapping.md)

### Base 已有能力

- **`get_metric_plugin_deployment_status()`**：调用 `installer.status()` 获取全量实例状态
- **`get_installer()`**：NodemanInstaller / K8sInstaller / SQLInstaller 分发

### Base 缺失的关键能力

1. **diff 模式（版本差异比对）完全缺失**
   - 旧版 `status(diff=True)` 会比较 `current_version.target_nodes` 与 `last_version.target_nodes`，将节点分为 ADD/REMOVE/UPDATE/RETRY
   - Base `status()` 没有 diff 参数，也没有上一版本的概念
   - 前端依赖这些差异分类来展示「本次变更了什么」

2. **节点分组结构不同**
   - 旧版：按 `diff_type` + `node_path` 分组，返回 `label_name`/`is_label`
   - Base：按拓扑节点分组，返回 `node_name`/`node_type`/`node_id`/`bk_obj_id`/`bk_inst_id`

3. **实例字段差异**
   - 旧版有 `task_id`、`plugin_version`，Base 没有
   - 旧版 `log` 是阶段名（"步骤名-子步骤名"），Base 是错误日志文本
   - 旧版做状态转换（RUNNING → STARTING/STOPPING），Base 不做

### 需 SaaS 层实现的逻辑

1. **diff 模式**：获取上一版本 target_nodes，与当前版本做差异比对，按 ADD/UPDATE/RETRY 分组
2. **节点结构转换**：将 Base 的 `node_name/node_type` 转为旧版 `node_path/label_name/is_label`
3. **实例字段补充**：从 deployment_version 补充 `plugin_version`，从结果补充 `task_id`
4. **状态转换**：根据 deployment.status 推断 last_operation，将 RUNNING/PENDING 转为 STARTING/STOPPING
5. **遗留 IP 兼容**：旧版有 IP→bk_host_id 转换，Base 无此逻辑
6. **`config_info`**：从 `get_metric_plugin_deployment()` 组装

### 入参/出参转换要点

- **入参**：`diff` 参数不传给 base（base 不支持），在 SaaS 层处理
- **出参**：需要将 base status() 的 `[{node_name, node_type, child}]` 转换为旧版 `[{node_path, label_name, is_label, child}]`

### 适配复杂度评估
- **🔴 高**：diff 模式缺失是架构级差异，需在 SaaS compat 层实现完整的版本差异比对+节点分类+字段转换

### 风险点
- diff 逻辑的正确性直接影响前端展示「本次变更」的体验
- 旧版使用 `TopoTree.convert_to_topo_link()` 计算拓扑路径，Base 使用 `find_topo_node_path()`，路径格式可能有细微差异
- 模板→节点转换逻辑不同（旧版 `api.cmdb.get_module/get_set`，Base `cmdb_api.list_set_template/list_service_template`）
- 被 `CollectRunningStatusResource` 和 `CollectInstanceStatusResource` 继承，转换层需确保两者兼容
