# ListLegacySubscription

## 基本信息

- **源文件**：`resources/toolkit.py`
- **HTTP 端点**：`GET list_legacy_subscription`
- **resource 路径**：`resource.collecting.list_legacy_subscription`
- **功能**：获取各个采集项遗留的订阅配置及节点管理中无效的订阅任务
- **适配复杂度**：🟡 中

## 入参

无入参。

## 出参

```python
{
    "detail": [
        {
            "id": int,
            "name": str,
            "bk_biz_id": int,
            "deployment_config_id": int,
            "deployment_config__subscription_id": int,
            "is_deleted": bool,
            "legacy_subscription_ids": list[int],    # 需要清理的订阅ID
            "deleted_subscription_ids": list[int],   # 已正常卸载的订阅ID
        }
    ],
    "total_legacy_subscription_ids": list[int],      # 全局遗留订阅ID
    "wild_subscription_ids": list[int],              # 野生订阅ID（不属于任何采集配置）
}
```

## 核心依赖

### ORM 模型依赖
- `CollectConfigMeta.origin_objects`：含已删除的采集配置
- `DeploymentConfigVersion.origin_objects`：含已删除的部署配置

### 外部依赖
- **直连节点管理数据库**：`connections["nodeman"]` 执行原生 SQL
  - 查询自动触发的订阅任务
  - 查询监控插件采集的订阅列表

## bk-monitor-base 适配分析

### 适配建议
- **建议保留在 SaaS 层**，不迁入 base
- 该 Resource 直连节点管理 DB 执行原生 SQL，属于运维工具类功能
- base 侧不太适合封装直连第三方数据库的逻辑

### 风险点
- 直连节点管理数据库（`nodeman`）的 SQL 操作
- `origin_objects`（包含软删除记录）的查询方式需 base 侧对齐
- 运维工具类 Resource，优先级较低

### 适配方案
- 新版可保持原逻辑不变，或标记为 legacy-only（不在新版实现）
