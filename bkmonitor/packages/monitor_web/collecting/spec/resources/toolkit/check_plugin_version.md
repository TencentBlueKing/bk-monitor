# CheckPluginVersionResource

## 基本信息

- **源文件**：`resources/toolkit.py`
- **HTTP 端点**：`POST check_plugin_version`
- **resource 路径**：`resource.collecting.check_plugin_version`
- **功能**：采集下发前校验目标主机的插件版本是否满足最低要求（当前仅校验进程采集）
- **适配复杂度**：🟡 中

## 入参（RequestSerializer）

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| target_nodes | list[dict] | 是 | - | 目标实例列表 |
| target_node_type | str | 是 | - | 采集目标类型 |
| collect_type | str | 是 | - | 采集方式 |
| bk_biz_id | int | 是 | - | 业务ID |

## 出参

```python
{
    "result": bool,                   # 校验是否通过
    "plugin_version": dict,           # 推荐的插件版本
    "invalid_host": {
        "bkmonitorbeat": [(ip, bk_cloud_id), ...]  # 不满足版本的主机
    }
}
```

## 核心依赖

### 外部 API 依赖
- `api.cmdb.get_host_by_ip`：按 IP 获取主机
- `api.cmdb.get_host_by_topo_node`：按拓扑获取主机
- `api.cmdb.get_host_by_template`：按模板获取主机
- `api.cmdb.execute_dynamic_group`：执行动态分组
- `api.node_man.plugin_search`：搜索主机插件版本

### 常量
- `PLUGIN_VERSION`：最低版本依赖
- `RECOMMENDED_VERSION`：推荐版本

## bk-monitor-base 适配分析

### 可适配部分
- 主机获取逻辑 → 可复用 CMDB API
- 版本比较逻辑

### 需 base 补齐的能力
- 目标主机解析（按不同 target_node_type）
- 节点管理插件版本查询

### 风险点
- 使用已废弃的 `distutils.version.StrictVersion`
- 当前仅校验 PROCESS 类型，其他类型直接跳过
- `get_host_ids` 中的主机获取逻辑与 `SaveCollectConfigResource` 的目标解析有重叠

## 公共函数提取

| 可提取逻辑 | 描述 | 复用场景 |
|-----------|------|---------|
| `resolve_host_ids_by_target` | 按目标类型解析主机ID列表 | 版本校验、目标解析 |
