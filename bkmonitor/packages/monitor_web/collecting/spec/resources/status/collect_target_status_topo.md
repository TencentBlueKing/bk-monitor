# CollectTargetStatusTopoResource

## 基本信息

- **源文件**：`resources/status.py`
- **HTTP 端点**：无直接端点（被 `FrontendTargetStatusTopoResource` 调用）
- **resource 路径**：`resource.collecting.collect_target_status_topo`
- **功能**：获取检查视图左侧数据（IP 列表或 Topo 树），含无数据检测
- **适配复杂度**：🔴 高

## 入参（RequestSerializer）

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| bk_biz_id | int | 是 | - | 业务ID |
| id | int | 是 | - | 采集配置ID |

## 出参

```python
[
    # TOPO 类型：递归 Topo 树
    {
        "id": str,                    # "bk_obj_id|bk_inst_id"
        "name": str,
        "bk_obj_id": str,
        "bk_obj_name": str,
        "bk_inst_id": int,
        "bk_inst_name": str,
        "children": [...],           # 子节点或实例列表
    },
    # INSTANCE 类型：实例列表
    {
        "id": int,
        "name": str,
        "ip": str,
        "bk_cloud_id": int,
        "status": str,
        "bk_host_id": int,
        "alias_name": str,
    },
    # DYNAMIC_GROUP 类型：分组节点 + 子实例
    {...}
]
```

## 核心依赖

### ORM 模型依赖
- `CollectConfigMeta`（含 `select_related("deployment_config")`）
- `PluginVersionHistory`：获取最新版本
- `CustomEventGroup`：日志关键字/SNMP Trap 的事件组

### 外部 API 依赖
- `api.cmdb.get_topo_tree`：获取业务 Topo 树
- `api.metadata.query_time_series_group`：查询时序分组（split_measurement 场景）

### deploy 依赖
- `get_collect_installer()`
- `installer.status(diff=False)`：获取完整状态

### 数据查询依赖
- `BkMonitorLogDataSource`：日志数据源查询（NoData 检测）
- `TSDataBase`：时序数据查询（NoData 检测）
- `ResultTable`：结果表配置

### 关键方法
- `nodata_test()`：无数据检测（日志关键字走 `BkMonitorLogDataSource`，其他走 `TSDataBase`）
- `fetch_latest_version_by_config()`：获取最新子配置版本
- `get_instance_info()`：获取实例信息
- `create_topo_tree()`：递归构建 Topo 树

## bk-monitor-base 适配分析

### 可适配部分
- 状态获取 → 依赖安装器的 `status()` 方法
- 枚举常量 → base 已有对应枚举

### 需 base 补齐的能力
1. **无数据检测**：需 base 封装 NoData 检测逻辑（或保留在 SaaS 层）
2. **Topo 树构建**：依赖 CMDB API + 安装器状态
3. **结果表配置**：`is_split_measurement` 场景
4. **日志/Trap 数据源查询**：`BkMonitorLogDataSource`

### 风险点
- **最复杂的状态类 Resource**
- NoData 检测涉及两条数据查询路径（日志 vs 时序）
- Topo 树构建涉及递归 + 模块映射
- `is_split_measurement` 判断需插件元数据
- 采集周期（period）用于计算 NoData 时间窗口

## 公共函数提取

| 可提取逻辑 | 描述 | 复用场景 |
|-----------|------|---------|
| `nodata_test` | 无数据检测 | Topo 状态 |
| `get_instance_info` | 实例信息格式化 | Topo 状态 |
| `create_topo_tree` | Topo 树构建 | Topo 状态 |
| `fetch_latest_version_by_config` | 获取最新插件版本 | Topo 状态 |
