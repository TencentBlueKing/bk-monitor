# FrontendCollectConfigTargetInfoResource

## 基本信息

- **源文件**：`resources/frontend.py`
- **HTTP 端点**：`GET frontend_target_info`
- **resource 路径**：`resource.collecting.frontend_collect_config_target_info`
- **功能**：获取采集配置的采集目标列表，供前端表格展示
- **适配复杂度**：🟡 中

## 入参（RequestSerializer）

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| bk_biz_id | int | 是 | - | 业务ID |
| id | int | 是 | - | 采集配置ID |

## 出参

```python
{
    "target_node_type": str,
    "table_data": [
        # INSTANCE 类型
        {"display_name": str, "bk_host_id": int, "ip": str, "agent_status": str, "bk_cloud_name": str},
        # TOPO / TEMPLATE 类型
        {"bk_inst_name": str, "count": int, "labels": list},
        # DYNAMIC_GROUP 类型
        {"bk_inst_name": str, "count": int},
    ]
}
```

## 核心依赖

### 内部 Resource 依赖
- `resource.collecting.collect_config_detail`：获取底层详情
- `resource.commons.get_nodes_by_template`：模板类型获取节点数

### 特殊逻辑
- 按 `target_node_type` 分4种路径组装 `table_data`
  - `INSTANCE`：直接从 target 列表获取
  - `SET_TEMPLATE` / `SERVICE_TEMPLATE`：调用 `get_nodes_by_template`
  - `DYNAMIC_GROUP`：从 target 列表获取名称和数量
  - 其他（TOPO）：从 target 列表获取节点名称和数量

## bk-monitor-base 适配分析

### 可适配部分
- 纯展示层，依赖 `collect_config_detail` 的适配

### 风险点
- 模板类型需调用 `get_nodes_by_template`，这是 commons 模块的能力

## 公共函数提取

| 可提取逻辑 | 描述 | 复用场景 |
|-----------|------|---------|
| `format_target_table_data` | 按节点类型格式化目标表格数据 | 前端目标信息 |
