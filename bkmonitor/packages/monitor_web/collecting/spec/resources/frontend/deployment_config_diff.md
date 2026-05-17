# DeploymentConfigDiffResource

## 基本信息

- **源文件**：`resources/frontend.py`
- **HTTP 端点**：`GET deployment_diff`
- **resource 路径**：`resource.collecting.deployment_config_diff`
- **功能**：获取采集配置的部署配置差异，用于列表页重新进入执行中的采集配置
- **适配复杂度**：🟢 低

## 入参（RequestSerializer）

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| bk_biz_id | int | 是 | - | 业务ID |
| id | int | 是 | - | 采集配置ID |

## 出参

```python
{
    "is_modified": bool,
    "added": list,       # 新增的目标节点
    "updated": list,     # 更新的目标节点
    "removed": list,     # 移除的目标节点
    "unchanged": list,   # 未变更的目标节点
}
```

## 核心依赖

### ORM 模型依赖
- `CollectConfigMeta`
- `DeploymentConfigVersion`：获取上一版本并计算 diff

### 关键方法
- `last_version.show_diff(current_deployment_config)`：计算两份部署配置的差异
- ROLLBACK 操作时取 `parent_id` 对应的版本

## bk-monitor-base 适配分析

### 可适配部分
- 配置差异比对 → base 需提供 `diff_deployment_config` 能力

### 需 base 补齐的能力
- 部署配置版本管理和 diff 计算

### 风险点
- `show_diff()` 是 `DeploymentConfigVersion` 模型方法，base 侧需等价实现
- ROLLBACK 场景下取上一版本的逻辑稍有不同
