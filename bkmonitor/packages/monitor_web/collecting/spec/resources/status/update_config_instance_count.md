# UpdateConfigInstanceCountResource

## 基本信息

- **源文件**：`resources/status.py`
- **HTTP 端点**：无直接 HTTP 端点
- **resource 路径**：`resource.collecting.update_config_instance_count`
- **功能**：更新启用中的采集配置的主机总数和异常数缓存
- **适配复杂度**：🟡 中

## 入参（RequestSerializer）

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| bk_biz_id | int | 是 | - | 业务ID |
| id | int | 是 | - | 采集配置ID |

## 出参

```python
None  # 无返回值，直接更新数据库缓存
```

## 核心依赖

### ORM 模型依赖
- `CollectConfigMeta`（含 `select_related("deployment_config")`）

### deploy 依赖（K8s 插件场景）
- `get_collect_installer()`
- `installer.status()`

### 外部 API 依赖（非 K8s 场景）
- `fetch_sub_statistics()`：节点管理订阅统计

## bk-monitor-base 适配分析

### 需 base 补齐的能力
1. **K8s 状态统计**：base 安装器需支持
2. **节点管理订阅统计**：base 需封装

### 风险点
- K8s 和非 K8s 两条路径
- 直接更新 `cache_data` 字段

## 公共函数提取

| 可提取逻辑 | 描述 | 复用场景 |
|-----------|------|---------|
| `fetch_sub_statistics` | 节点管理订阅统计 | 列表刷新、实例统计 |
| K8s 实例统计逻辑 | 遍历 installer.status() 统计错误/总数 | 列表、实例统计 |
