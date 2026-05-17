# FetchCollectConfigStat

## 基本信息

- **源文件**：`resources/toolkit.py`
- **HTTP 端点**：`GET fetch_collect_config_stat`
- **resource 路径**：`resource.collecting.fetch_collect_config_stat`
- **功能**：获取采集配置列表统计信息（按类型分组统计状态数量）
- **适配复杂度**：🟢 低

## 入参（RequestSerializer）

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| bk_biz_id | int | 否 | - | 业务ID |

## 出参

```python
[
    {
        "id": str,       # 采集类型ID
        "name": str,     # 采集类型名称
        "nums": {
            "STARTED": int,
            "STOPPED": int,
            "WARNING": int,
            "need_upgrade": int,
            ...
        }
    }
]
```

## 核心依赖

- `CollectConfigMeta`：查询所有采集配置
- `COLLECT_TYPE_CHOICES`：采集类型常量
- `cache_data`：从缓存数据中读取状态信息

## bk-monitor-base 适配分析

### 可适配部分
- 采集配置查询 → base 提供
- 类型常量 → base 已有

### 需 base 补齐的能力
- 采集配置统计查询 API（按类型分组统计）

### 风险点
- 依赖 `cache_data` 中的预计算状态信息
- 排除了 `log` 和 `Built-In` 类型
