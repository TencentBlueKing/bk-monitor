# ListRelatedStrategy

## 基本信息

- **源文件**：`resources/toolkit.py`
- **HTTP 端点**：`POST list_related_strategy`
- **resource 路径**：`resource.collecting.list_related_strategy`
- **功能**：列出指定采集配置的所有关联告警策略（分模糊和精准匹配）
- **适配复杂度**：🟢 低

## 入参（RequestSerializer）

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| bk_biz_id | int | 是 | - | 业务ID |
| collect_config_id | int | 是 | - | 采集配置ID |

## 出参

```python
{
    "fuzzy_strategies": [
        {"strategy_id": int, "strategy_name": str}
    ],
    "accurate_strategies": [
        {"strategy_id": int, "strategy_name": str}
    ],
}
```

## 核心依赖

- `CollectConfigMeta`：获取采集配置
- `MetricListCache`：获取指标缓存
- `QueryConfigModel`：查询策略的指标配置
- `StrategyModel`：获取策略信息

### 匹配逻辑
- **模糊匹配**：通过 `metric_id` 关联找到策略
- **精准匹配**：检查 `agg_condition` 中 `bk_collect_config_id` 是否包含当前配置
- 日志/SNMP Trap 类型不区分模糊和精准

## bk-monitor-base 适配分析

### 适配建议
- 策略查询逻辑保留在 SaaS 层
- 仅需从 base 获取采集配置信息（`CollectConfigMeta`）

### 风险点
- `MetricListCache` 是 SaaS 层缓存表，base 侧无对应
