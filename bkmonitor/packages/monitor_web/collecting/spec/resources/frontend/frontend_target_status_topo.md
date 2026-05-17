# FrontendTargetStatusTopoResource

## 基本信息

- **源文件**：`resources/frontend.py`
- **HTTP 端点**：`POST target_status_topo`
- **resource 路径**：`resource.collecting.frontend_target_status_topo`
- **功能**：获取检查视图页左侧 Topo 树，展示采集状态
- **适配复杂度**：🟡 中

## 入参（RequestSerializer）

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| bk_biz_id | int | 是 | - | 业务ID |
| id | int | 是 | - | 采集配置ID |
| only_instance | bool | 否 | False | 是否只显示实例列表 |

## 出参

```python
[
    {
        "name": str,
        "id": str,
        "status": str,          # 实例节点才有
        "alias_name": str,      # 主机节点才有
        "children": [...],      # 递归子节点
        "target": dict,         # only_instance=True 时才有
    }
]
```

## 核心依赖

### 内部 Resource 依赖
- `resource.collecting.collect_target_status_topo`：获取底层 Topo 数据

### ORM 模型依赖
- `CollectConfigMeta`（含 `select_related("deployment_config")`）

### 工具依赖
- `get_host_view_display_fields`：获取主机显示字段
- `foreach_topo_tree`：遍历 Topo 树

### 特殊逻辑
- `handle_node`：处理节点，根据类型（服务实例/主机/拓扑/动态分组）补充字段
- INSTANCE/DYNAMIC_GROUP 类型：平铺处理
- TOPO 类型：递归遍历 + 去除空节点

## bk-monitor-base 适配分析

### 可适配部分
- 纯展示层加工，依赖 `CollectTargetStatusTopoResource` 的适配

### 风险点
- `foreach_topo_tree` 是 commons 模块的工具函数
- `only_instance` 模式需遍历填充 target 字段

## 公共函数提取

| 可提取逻辑 | 描述 | 复用场景 |
|-----------|------|---------|
| `handle_topo_node` | Topo 节点信息处理 | 前端 Topo 树 |
