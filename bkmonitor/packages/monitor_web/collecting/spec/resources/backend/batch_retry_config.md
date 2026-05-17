# BatchRetryConfigResource / BatchRetryResource

## 基本信息

- **源文件**：`resources/backend.py`
- **HTTP 端点**：`POST batch_retry`（列表页） / `POST batch_retry_detailed`（详情页）
- **resource 路径**：`resource.collecting.batch_retry_config` / `resource.collecting.batch_retry`
- **功能**：重试所有失败的实例。`BatchRetryResource` 直接继承 `BatchRetryConfigResource`，无额外逻辑
- **适配复杂度**：🟢 低

## 入参（RequestSerializer）

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| bk_biz_id | int | 是 | - | 业务ID |
| id | int | 是 | - | 采集配置ID |

## 出参

```python
"success"  # 字符串
```

## 核心依赖

- `CollectConfigMeta`（含 `select_related("deployment_config")`）
- `get_collect_installer()`
- `installer.retry()`：无参调用，重试所有失败实例

## bk-monitor-base 适配分析

### 需 base 补齐的能力
- 安装器 `retry()` 接口

### 风险点
- 逻辑简单，风险低
- `BatchRetryResource` 是空继承，可考虑合并
