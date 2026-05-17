# CleanLegacySubscription

## 基本信息

- **源文件**：`resources/toolkit.py`
- **HTTP 端点**：`GET clean_legacy_subscription`
- **resource 路径**：`resource.collecting.clean_legacy_subscription`
- **功能**：停用并删除遗留的订阅配置
- **适配复杂度**：🟡 中

## 入参（RequestSerializer）

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| subscription_id | list[int] | 是 | - | 节点管理订阅ID列表 |
| action_type | str | 否 | "STOP" | 动作类型 |
| is_force | bool | 否 | False | 是否强制清理 |

## 出参

```python
[
    {
        "subscription_id": int,
        "result": bool,
        "message": str,       # 失败时的错误信息
        "task_id": int,       # 成功时的任务ID（来自 run_subscription）
    }
]
```

## 核心依赖

### 外部 API 依赖
- `api.node_man.subscription_info`：查询订阅详情
- `api.node_man.run_subscription`：执行订阅操作

### 外部依赖
- **直连节点管理数据库**：修改 `node_man_subscription` 表状态（enable/is_deleted）

## bk-monitor-base 适配分析

### 适配建议
- **建议保留在 SaaS 层**，与 `ListLegacySubscription` 同理
- 直接操作节点管理 DB + 调用节点管理 API

### 风险点
- 直连节点管理数据库的写操作（UPDATE SQL）
- 操作流程：恢复删除状态 → 执行操作 → 重新删除
