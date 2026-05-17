# BatchRevokeTargetNodesResource

## 基本信息

- **源文件**：`resources/backend.py`
- **HTTP 端点**：`POST batch_revoke`
- **resource 路径**：`resource.collecting.batch_revoke_target_nodes`
- **功能**：批量终止采集配置下所有部署中的实例
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
- `installer.revoke()`：无参调用，终止所有实例

## bk-monitor-base 适配分析

与 `RevokeTargetNodesResource` 类似，区别在于不传 instance_ids（终止全部）。

### 风险点
- 逻辑简单，风险低
