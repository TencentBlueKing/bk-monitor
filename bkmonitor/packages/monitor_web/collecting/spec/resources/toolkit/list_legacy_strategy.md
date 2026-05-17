# ListLegacyStrategy

## 基本信息

- **源文件**：`resources/toolkit.py`
- **HTTP 端点**：`GET list_legacy_strategy`
- **resource 路径**：`resource.collecting.list_legacy_strategy`
- **功能**：列出当前配置的告警策略中无效的部分（关联的采集/事件已删除）
- **适配复杂度**：🟢 低

## 入参（RequestSerializer）

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| bk_biz_id | int | 是 | - | 业务ID |

## 出参

```python
list[dict]  # 无效的 QueryConfigModel 列表
```

## 核心依赖

- `CustomEventGroup`：获取有效事件 RT 表
- `StrategyModel`：获取策略列表
- `QueryConfigModel`：查询关联的数据源配置

## bk-monitor-base 适配分析

### 适配建议
- 告警策略查询逻辑，可能保留在 SaaS 层
- 与 base 无直接关联，不依赖 collector 域

### 风险点
- 逻辑简单，风险低
