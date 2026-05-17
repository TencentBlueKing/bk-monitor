# CheckAdjectiveCollect

## 基本信息

- **源文件**：`resources/toolkit.py`
- **HTTP 端点**：`GET check_adjective_collect`
- **resource 路径**：`resource.collecting.check_adjective_collect`
- **功能**：检查游离态采集配置（已停用但节点管理订阅仍启用的配置），可选清理
- **适配复杂度**：🟡 中

## 入参（RequestSerializer）

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| clean | bool | 否 | False | 是否执行清理 |

## 出参

```python
[
    {
        "config_id": int,         # 采集配置ID
        "subscription_id": int,   # 订阅ID
    }
]
```

## 核心依赖

- `CollectConfigMeta`：查询已停用的采集配置
- `DeploymentConfigVersion`：获取订阅ID
- `api.node_man.subscription_info`：查询订阅状态
- `api.node_man.switch_subscription`：清理时停用订阅
- `get_collect_installer()`：清理时停止采集
- `get_request().user.is_superuser`：权限校验

## bk-monitor-base 适配分析

### 适配建议
- 运维工具类 Resource，建议保留在 SaaS 层
- 清理操作涉及节点管理订阅状态和安装器操作

### 风险点
- 需要超级管理员权限才能执行清理
- 涉及节点管理 API 调用
