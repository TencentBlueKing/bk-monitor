# IsTaskReady

## 基本信息

- **源文件**：`resources/toolkit.py`
- **HTTP 端点**：`POST is_task_ready`
- **resource 路径**：`resource.collecting.is_task_ready`
- **功能**：向节点管理轮询任务是否已经初始化完成
- **适配复杂度**：🟢 低

## 入参（RequestSerializer）

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| bk_biz_id | int | 是 | - | 业务ID |
| collect_config_id | int | 是 | - | 采集配置ID |

## 出参

```python
bool  # True 表示任务就绪
```

## 核心依赖

- `CollectConfigMeta`（含 `select_related("deployment_config")`）
- `api.node_man.check_task_ready`：节点管理 API
- `deployment_config.subscription_id`
- `deployment_config.task_ids`

## bk-monitor-base 适配分析

### 可适配部分
- 采集配置查询 → base 提供
- 节点管理 API 调用 → base 可封装

### 风险点
- 非节点管理部署的采集直接返回 True
- 兼容旧版节点管理（无 `check_task_ready` API 时返回 True）
