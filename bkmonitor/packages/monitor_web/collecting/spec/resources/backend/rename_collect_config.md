# RenameCollectConfigResource

## 基本信息

- **源文件**：`resources/backend.py`
- **HTTP 端点**：`POST rename`
- **resource 路径**：`resource.collecting.rename_collect_config`
- **功能**：修改采集配置的名称
- **适配复杂度**：🟢 低

## 入参（RequestSerializer）

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| bk_biz_id | int | 是 | - | 业务ID |
| id | int | 是 | - | 采集配置ID |
| name | str | 是 | - | 新名称 |

## 出参

```python
"success"  # 字符串
```

## 核心依赖

- `CollectConfigMeta.objects.filter().update()`：直接 ORM 更新

## bk-monitor-base 适配分析

### 可适配部分
- 简单更新操作 → base 需提供 `rename_collect_config` operation

### 需 base 补齐的能力
- 采集配置更新 API（部分字段更新）

### 风险点
- 逻辑非常简单，风险极低
- 无复杂业务逻辑

## 公共函数提取

无特别需要提取的公共逻辑。
