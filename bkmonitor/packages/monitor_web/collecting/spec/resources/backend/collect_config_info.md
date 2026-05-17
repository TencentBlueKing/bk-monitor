# CollectConfigInfoResource

## 基本信息

- **源文件**：`resources/backend.py`
- **HTTP 端点**：无直接 HTTP 端点（通过 `kernel_api` 暴露）
- **resource 路径**：`resource.collecting.collect_config_info`
- **功能**：提供给 kernel API 使用，返回全部采集配置的原始数据
- **适配复杂度**：🟢 低

## 入参

无入参。

## 出参

```python
list[dict]  # CollectConfigMeta.objects.all().values() 的全量数据
```

## 核心依赖

- `CollectConfigMeta.objects.all().values()`

## bk-monitor-base 适配分析

### 可适配部分
- 全量查询 → base 需提供 `list_all_collect_configs` operation

### 风险点
- 返回全量数据，性能风险（但供内部 kernel API 使用）
- 无 Serializer 校验，输出格式为 ORM values() 的原始 dict
- base 侧返回格式需与 ORM values() 保持一致
