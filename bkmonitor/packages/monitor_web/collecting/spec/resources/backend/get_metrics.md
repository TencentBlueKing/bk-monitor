# GetMetricsResource

## 基本信息

- **源文件**：`resources/backend.py`
- **HTTP 端点**：`GET metrics`
- **resource 路径**：`resource.collecting.get_metrics`
- **功能**：获取采集配置对应插件版本的指标参数
- **适配复杂度**：🟢 低

## 入参（RequestSerializer）

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| bk_biz_id | int | 是 | - | 业务ID |
| id | int | 是 | - | 采集配置ID |

## 出参

```python
list  # deployment_config.metrics 的值，即插件版本的指标 JSON
```

## 核心依赖

- `CollectConfigMeta`（含 `select_related("deployment_config")`）
- `deployment_config.metrics`：获取部署配置关联的指标信息

## bk-monitor-base 适配分析

### 可适配部分
- 指标查询 → base 可通过采集配置获取关联的指标信息

### 需 base 补齐的能力
- 采集配置关联指标的查询 API

### 风险点
- 逻辑简单，风险极低
