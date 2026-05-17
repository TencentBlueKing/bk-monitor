# RevokeTargetNodesResource

## 基本信息

- **源文件**：`resources/backend.py`
- **HTTP 端点**：`POST revoke`
- **resource 路径**：`resource.collecting.revoke_target_nodes`
- **功能**：终止部分部署中的实例
- **适配复杂度**：🟢 低

## 入参（RequestSerializer）

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| bk_biz_id | int | 是 | - | 业务ID |
| id | int | 是 | - | 采集配置ID |
| instance_ids | list | 是 | - | 需要终止的实例ID列表 |

## 出参

```python
"success"  # 字符串
```

## 核心依赖

- `CollectConfigMeta`（含 `select_related("deployment_config")`）
- `get_collect_installer()`
- `installer.revoke(instance_ids=instance_ids)`

## bk-monitor-base 适配分析

### 需 base 补齐的能力
- 安装器 `revoke()` 接口

### 风险点
- 逻辑简单，风险低

## 公共函数提取

与 `BatchRevokeTargetNodesResource` 共享安装器获取逻辑。
